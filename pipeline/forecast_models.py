"""
Points forecasting: features, models, rolling-origin backtest and champion selection.

Used by pipeline/points_forecast.py (the runner, which reads MySQL and writes the results).
Everything here works on DataFrames in real points; nothing is scaled.

Models (MODELS below)
    baselines    NAIVE (last game), SEASON_MEAN, MEAN_10, SES (simple exponential smoothing)
    statistical  ETS_DAMPED, THETA, ARIMA (order picked by AICc), ARIMAX (ARMA errors + inputs),
                 LOCAL_LEVEL (Kalman), NEGBIN (count GLM + inputs), MIN_X_PPM (minutes x points
                 per minute), MIN_X_PPM_EB (the same, shrunk toward the player's longer-run rate
                 and the position average)
    ml           XGB: one XGBoost model per position group (PG/SG/SF/PF/C), trained on every
                 eligible player's games with lag features, direct multi-horizon (h is a feature)

Inputs used by ARIMAX / NEGBIN / XGB (all known before tip-off)
    min_proj   projected minutes: EWM of the player's minutes through the previous game
    home, rest (team days off, capped at 4), b2b
    opp_def    opponent points allowed over its last 15 games minus the league average (30 days)
    opp_pace   the same for possessions

Backtest
    For each player, the last N_ORIGINS(+H-1) games are origins. At origin o every model is
    refit on games [0, o) and forecasts games o..o+4. Errors are in points, signed actual-pred.
    XGB is trained once with a cutoff before the earliest origin of any rostered player, so it
    never sees a target it is scored on.

Champion
    The roster default is the model with the best mean skill (1 - MAE/naive MAE) across players.
    A player switches to their own best model only if a Diebold-Mariano test says it is better
    than the default (one-sided p < DM_ALPHA / number of challengers, i.e. Bonferroni, because their
    best is picked from all of them; at least DM_MIN_ORIGINS origins).
"""
import json
import warnings

import numpy as np
import pandas as pd
from scipy import stats
import statsmodels.api as sm
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from statsmodels.tsa.statespace.sarimax import SARIMAX
from statsmodels.tsa.statespace.structural import UnobservedComponents
from statsmodels.tsa.forecasting.theta import ThetaModel
from statsmodels.tsa.stattools import kpss
from statsmodels.stats.diagnostic import acorr_ljungbox

warnings.filterwarnings('ignore')

H = 5                    # forecast horizon: the team's next 5 games
N_ORIGINS = 20           # backtest origins with a full 5-game horizon (plus H-1 shorter ones at the end)
MIN_TRAIN = 6            # games needed before the first origin
DM_ALPHA, DM_MIN_ORIGINS = 0.10, 8
EXOG = ['min_proj', 'home', 'b2b', 'opp_def', 'opp_pace']
POSITIONS = ['PG', 'SG', 'SF', 'PF', 'C']
REST_CAP = 4

MODELS = {   # key: (label, family)
    'NAIVE': ('Naive (last game)', 'baseline'),
    'SEASON_MEAN': ('Season average', 'baseline'),
    'MEAN_10': ('Rolling mean (10)', 'baseline'),
    'SES': ('Simple exp. smoothing', 'baseline'),
    'ETS_DAMPED': ('ETS damped trend', 'statistical'),
    'THETA': ('Theta', 'statistical'),
    'ARIMA': ('ARIMA (auto)', 'statistical'),
    'ARIMAX': ('ARIMAX (inputs)', 'statistical'),
    'LOCAL_LEVEL': ('Local level (Kalman)', 'statistical'),
    'NEGBIN': ('Negative binomial', 'statistical'),
    'MIN_X_PPM': ('Minutes x pts/min', 'statistical'),
    'MIN_X_PPM_EB': ('Minutes x pts/min, shrunk', 'statistical'),
    'XGB': ('XGBoost by position', 'ml'),
}


####################################################################################################
# 001 - LEAGUE-LEVEL FEATURES
####################################################################################################

def team_games(box):
    """One row per team-game from league-wide box scores: points, possessions, points allowed, pace."""
    b = box.assign(poss=box['fga'] - box['orb'] + box['tov'] + 0.44 * box['fta'])
    g = b.groupby(['date', 'team', 'opponent', 'home'], as_index=False)[['points', 'poss']].sum()
    opp = g[['date', 'team', 'points', 'poss']].rename(
        columns={'team': 'opponent', 'points': 'opp_points', 'poss': 'opp_poss'})
    g = g.merge(opp, on=['date', 'opponent'], how='left')
    g['pace'] = (g['poss'] + g['opp_poss']) / 2
    return g


def team_ratings(tg, window=15):
    """Per team and game date: defence (points allowed) and pace over its last `window` games
    through that date, relative to the league average over the previous 30 days.
    opp_def > 0 means the team allows more than average (a good matchup)."""
    tg = tg.sort_values(['team', 'date']).copy()
    grp = tg.groupby('team')
    tg['allowed_roll'] = grp['opp_points'].transform(lambda s: s.rolling(window, min_periods=3).mean())
    tg['pace_roll'] = grp['pace'].transform(lambda s: s.rolling(window, min_periods=3).mean())
    daily = tg.groupby('date')[['points', 'pace']].mean().sort_index()
    league = daily.rolling('30D').mean().rename(columns={'points': 'lg_pts', 'pace': 'lg_pace'})
    tg = tg.merge(league, left_on='date', right_index=True, how='left')
    tg['opp_def'] = tg['allowed_roll'] - tg['lg_pts']
    tg['opp_pace'] = tg['pace_roll'] - tg['lg_pace']
    return tg[['team', 'date', 'opp_def', 'opp_pace', 'allowed_roll']].dropna()


def ratings_asof(ratings, teams, asof):
    """Ratings of `teams` using games through `asof` (inclusive). Missing -> league average (0)."""
    q = pd.DataFrame({'team': np.asarray(teams), 'date': pd.to_datetime(np.asarray(asof))})
    q['_i'] = np.arange(len(q))
    ok = q['team'].notna() & q['date'].notna()
    out = pd.DataFrame({'opp_def': 0.0, 'opp_pace': 0.0, 'allowed_roll': np.nan}, index=q['_i'])
    if ok.any():
        m = pd.merge_asof(q[ok].sort_values('date'), ratings.sort_values('date'), on='date', by='team')
        m = m.set_index('_i')
        out.loc[m.index, ['opp_def', 'opp_pace', 'allowed_roll']] = m[['opp_def', 'opp_pace', 'allowed_roll']].values
    out[['opp_def', 'opp_pace']] = out[['opp_def', 'opp_pace']].fillna(0.0)
    return out.reset_index(drop=True)


def team_rest(team_dates):
    """team, date (played and scheduled) -> rest days before each game, capped at REST_CAP."""
    d = team_dates[['team', 'date']].drop_duplicates().sort_values(['team', 'date']).copy()
    d['rest'] = d.groupby('team')['date'].diff().dt.days.sub(1).clip(0, REST_CAP).fillna(REST_CAP)
    return d


####################################################################################################
# 002 - PLAYER GAME TABLE
####################################################################################################

def player_games(box, rest, ratings):
    """Played games (minutes > 0) with the inputs each one had before tip-off."""
    pg = box[box['minutes'] > 0].sort_values(['slug', 'date']).reset_index(drop=True)
    pg = pg.merge(rest, on=['team', 'date'], how='left')
    pg['rest'] = pg['rest'].fillna(REST_CAP)
    pg['b2b'] = (pg['rest'] == 0).astype(float)
    r = ratings_asof(ratings, pg['opponent'], pg['date'] - pd.Timedelta(days=1))
    pg['opp_def'], pg['opp_pace'] = r['opp_def'].values, r['opp_pace'].values
    g = pg.groupby('slug', sort=False)['minutes']
    pg['min_ewm'] = g.transform(lambda s: s.ewm(alpha=0.25).mean())      # through this game
    pg['min_proj'] = pg.groupby('slug', sort=False)['min_ewm'].shift(1)   # through the previous game
    pg['min_proj'] = pg['min_proj'].fillna(pg['minutes'].median())
    return pg


def origin_features(pg):
    """Lag features at each player-game, using that game and the ones before it (XGB inputs)."""
    g = pg.groupby('slug', sort=False)
    f = pd.DataFrame(index=pg.index)
    roll = lambda col, n, fn='mean': g[col].transform(lambda s: getattr(s.rolling(n, min_periods=1), fn)())
    ewm = lambda col, a: g[col].transform(lambda s: s.ewm(alpha=a).mean())
    f['pts_last'] = pg['points']
    f['pts_mean3'] = roll('points', 3)
    f['pts_mean5'] = roll('points', 5)
    f['pts_mean10'] = roll('points', 10)
    f['pts_std10'] = g['points'].transform(lambda s: s.rolling(10, min_periods=2).std())
    f['pts_ewm'] = ewm('points', 0.15)
    f['min_last'] = pg['minutes']
    f['min_mean5'] = roll('minutes', 5)
    f['min_ewm'] = pg['min_ewm']
    pts_w, min_w = ewm('points', 0.1), ewm('minutes', 0.1)
    f['ppm_ewm'] = pts_w / min_w.where(min_w > 0)
    use = pg['fga'] + 0.44 * pg['fta'] + pg['tov']
    f['usg_ewm'] = pg.assign(_u=use).groupby('slug', sort=False)['_u'].transform(
        lambda s: s.ewm(alpha=0.1).mean()) / min_w.where(min_w > 0)
    f['fga_mean5'] = roll('fga', 5)
    f['fta_mean5'] = roll('fta', 5)
    f['fg3a_mean5'] = roll('fg3a', 5)
    gs = pg.groupby(['slug', 'season'], sort=False)['points']
    f['season_mean'] = gs.transform(lambda s: s.expanding().mean())
    f['games_season'] = gs.cumcount() + 1
    f['gap_before'] = g['date'].diff().dt.days.clip(0, 30).fillna(30)
    return f


TARGET_FEATS = ['h', 'home', 'rest', 'b2b', 'opp_def', 'opp_pace', 'days_ahead']


def xgb_training_rows(pg, feats, ratings):
    """Direct multi-horizon rows: features at game t, target = points at the player's game t+h."""
    out = []
    g = pg.groupby('slug', sort=False)
    for h in range(1, H + 1):
        nxt = g[['date', 'points', 'opponent', 'home', 'rest', 'b2b']].shift(-h)
        rows = feats.copy()
        rows['slug'], rows['origin_date'], rows['t'] = pg['slug'], pg['date'], g.cumcount()
        rows['h'] = h
        rows['home'], rows['rest'], rows['b2b'] = nxt['home'], nxt['rest'], nxt['b2b']
        r = ratings_asof(ratings, nxt['opponent'], pg['date'])          # opponent form as of the origin
        rows['opp_def'], rows['opp_pace'] = r['opp_def'].values, r['opp_pace'].values
        rows['days_ahead'] = (nxt['date'] - pg['date']).dt.days
        rows['target'], rows['target_date'] = nxt['points'], nxt['date']
        out.append(rows[rows['target'].notna()])
    return pd.concat(out, ignore_index=True)


XGB_FEATS = ['pts_last', 'pts_mean3', 'pts_mean5', 'pts_mean10', 'pts_std10', 'pts_ewm', 'min_last', 'min_mean5',
             'min_ewm', 'ppm_ewm', 'usg_ewm', 'fga_mean5', 'fta_mean5', 'fg3a_mean5', 'season_mean',
             'games_season', 'gap_before'] + TARGET_FEATS

XGB_PARAMS = dict(n_estimators=800, learning_rate=0.03, max_depth=4, min_child_weight=20, subsample=0.8,
                  colsample_bytree=0.8, reg_lambda=1.0, objective='reg:absoluteerror', tree_method='hist',
                  early_stopping_rounds=50, n_jobs=4, random_state=42)


def fit_xgb(rows):
    """One position group's model. The last 10% of origin dates are the early-stopping set."""
    from xgboost import XGBRegressor
    rows = rows.sort_values('origin_date')
    cut = rows['origin_date'].quantile(0.9)
    tr, va = rows[rows['origin_date'] < cut], rows[rows['origin_date'] >= cut]
    model = XGBRegressor(**XGB_PARAMS)
    model.fit(tr[XGB_FEATS], tr['target'], eval_set=[(va[XGB_FEATS], va['target'])], verbose=False)
    val_mae = float(np.mean(np.abs(model.predict(va[XGB_FEATS]) - va['target'])))
    return model, {'n_train': int(len(tr)), 'n_val': int(len(va)), 'val_mae': val_mae,
                   'best_iteration': int(model.best_iteration)}


####################################################################################################
# 003 - STATISTICAL MODELS (each: fit(train_df, future_df, ctx) -> predictions, params, diagnostics)
####################################################################################################

def _lb(resid):
    resid = np.asarray(resid, dtype=float)
    resid = resid[np.isfinite(resid)]
    if len(resid) < 15:
        return None
    return float(acorr_ljungbox(resid, lags=[10], return_df=True)['lb_pvalue'].iloc[0])


def _aicc(res):
    return float(getattr(res, 'aicc', np.nan))


def m_naive(df, fut, ctx):
    return np.repeat(df['points'].iloc[-1], len(fut)), {}, {}


def m_season_mean(df, fut, ctx):
    s = df[df['season'] == df['season'].iloc[-1]]['points']
    return np.repeat(s.mean(), len(fut)), {'games': int(len(s))}, {}


def m_mean10(df, fut, ctx):
    return np.repeat(df['points'].tail(10).mean(), len(fut)), {'window': 10}, {}


def m_ses(df, fut, ctx):
    r = ExponentialSmoothing(df['points'].values, trend=None, initialization_method='estimated').fit()
    return (r.forecast(len(fut)), {'alpha': r.params['smoothing_level'], 'level': float(r.level[-1])},
            {'aicc': _aicc(r), 'ljung_box_p': _lb(r.resid)})


def m_ets_damped(df, fut, ctx):
    r = ExponentialSmoothing(df['points'].values, trend='add', damped_trend=True,
                             initialization_method='estimated').fit()
    p = r.params
    return (r.forecast(len(fut)), {'alpha': p['smoothing_level'], 'beta': p['smoothing_trend'],
                                   'phi': p['damping_trend'], 'level': float(r.level[-1]),
                                   'trend': float(r.trend[-1])},
            {'aicc': _aicc(r), 'ljung_box_p': _lb(r.resid)})


def m_theta(df, fut, ctx):
    r = ThetaModel(df['points'].values, period=1, deseasonalize=False).fit()
    return (np.asarray(r.forecast(len(fut))), {'theta': 2.0, 'alpha': float(r.params['alpha']),
                                                 'drift_b0': float(r.params['b0'])}, {})


def select_arima(y):
    """(p, d, q): d from a KPSS test, then p, q in 0..2 by AICc. Constant when d == 0."""
    y = np.asarray(y, dtype=float)
    d = 0
    try:
        if len(y) >= 12 and kpss(y, regression='c', nlags='auto')[1] < 0.05:
            d = 1
    except Exception:
        pass
    best, best_aicc = (1, d, 0), np.inf
    for p in range(3):
        for q in range(3):
            try:
                r = SARIMAX(y, order=(p, d, q), trend='c' if d == 0 else 'n').fit(disp=False)
                if r.aicc < best_aicc:
                    best, best_aicc = (p, d, q), r.aicc
            except Exception:
                continue
    return best


def _arma_params(r):
    return {k: float(v) for k, v in zip(r.param_names, np.asarray(r.params))}


def m_arima(df, fut, ctx):
    order = ctx.get('arima_order') or (1, 0, 1)
    r = SARIMAX(df['points'].values, order=order, trend='c' if order[1] == 0 else 'n').fit(disp=False)
    prm = {'order': list(order), **_arma_params(r)}
    return r.forecast(len(fut)), prm, {'aicc': _aicc(r), 'ljung_box_p': _lb(r.resid[order[1]:])}


def m_arimax(df, fut, ctx):
    p, _, q = ctx.get('arima_order') or (1, 0, 1)
    p, q = min(p, 1), min(q, 1)               # keep it small: inputs carry the signal
    X = df[EXOG].astype(float).values
    r = SARIMAX(df['points'].values, exog=X, order=(p, 0, q), trend='c').fit(disp=False)
    names = {f'x{i + 1}': c for i, c in enumerate(EXOG)}
    prm = {'order': [p, 0, q], **{names.get(k, k): v for k, v in _arma_params(r).items()}}
    return (r.forecast(len(fut), exog=fut[EXOG].astype(float).values), prm,
            {'aicc': _aicc(r), 'ljung_box_p': _lb(r.resid)})


def m_local_level(df, fut, ctx):
    r = UnobservedComponents(df['points'].values, level='local level').fit(disp=False)
    prm = _arma_params(r)
    if prm.get('sigma2.irregular'):
        prm['signal_to_noise'] = prm.get('sigma2.level', 0.0) / prm['sigma2.irregular']
    return r.forecast(len(fut)), prm, {'aicc': _aicc(r), 'ljung_box_p': _lb(r.resid[1:])}


def _nb_design(d):
    X = pd.DataFrame({'log_min': np.log(d['min_proj'].clip(lower=1.0)), 'home': d['home'], 'b2b': d['b2b'],
                      'opp_def': d['opp_def'], 'opp_pace': d['opp_pace']}).astype(float)
    return sm.add_constant(X, has_constant='add')


def m_negbin(df, fut, ctx, half_life=30):
    """Count GLM, log link: log E[pts] = b0 + b1 log(min_proj) + home + b2b + opponent defence/pace.
    Recent games weigh more (half-life in games). Dispersion alpha by moments from a Poisson fit."""
    X, y = _nb_design(df), df['points'].values
    w = 0.5 ** ((len(df) - 1 - np.arange(len(df))) / half_life)
    pois = sm.GLM(y, X, family=sm.families.Poisson(), var_weights=w).fit()
    mu = pois.fittedvalues
    alpha = float(np.clip(np.sum(w * ((y - mu) ** 2 - mu) / mu ** 2) / np.sum(w), 1e-3, 5))
    r = sm.GLM(y, X, family=sm.families.NegativeBinomial(alpha=alpha), var_weights=w).fit()
    prm = {k: float(v) for k, v in r.params.items()}
    prm['alpha_dispersion'] = alpha
    return np.asarray(r.predict(_nb_design(fut))), prm, {'ljung_box_p': _lb(y - r.fittedvalues)}


def _weighted_rate(df, half_life):
    w = 0.5 ** ((len(df) - 1 - np.arange(len(df))) / half_life)
    return float(np.sum(w * df['points'])), float(np.sum(w * df['minutes']))


def m_min_x_ppm(df, fut, ctx):
    """points = projected minutes x points per minute (both exponentially weighted)."""
    P, M = _weighted_rate(df, 15)
    ppm = P / M if M > 0 else 0.0
    mins = float(df['minutes'].ewm(alpha=0.25).mean().iloc[-1])
    return np.repeat(mins * ppm, len(fut)), {'proj_minutes': mins, 'pts_per_min': ppm}, {}


def m_min_x_ppm_eb(df, fut, ctx):
    """As MIN_X_PPM, with points/minute shrunk (empirical Bayes): recent rate -> the player's rate over
    all games in the window -> the position-group rate, each with prior strength kappa minutes."""
    mu_g, kappa = ctx.get('ppm_prior', (0.45, 300.0))
    P_all, M_all = float(df['points'].sum()), float(df['minutes'].sum())
    long_run = (P_all + kappa * mu_g) / (M_all + kappa)
    P, M = _weighted_rate(df, 15)
    ppm = (P + kappa * long_run) / (M + kappa)
    mins = float(df['minutes'].ewm(alpha=0.25).mean().iloc[-1])
    return (np.repeat(mins * ppm, len(fut)),
            {'proj_minutes': mins, 'pts_per_min': ppm, 'recent_ppm': P / M if M else None,
             'long_run_ppm': long_run, 'group_ppm': mu_g, 'kappa_minutes': kappa}, {})


STAT_FITS = {'NAIVE': m_naive, 'SEASON_MEAN': m_season_mean, 'MEAN_10': m_mean10, 'SES': m_ses,
             'ETS_DAMPED': m_ets_damped, 'THETA': m_theta, 'ARIMA': m_arima, 'ARIMAX': m_arimax,
             'LOCAL_LEVEL': m_local_level, 'NEGBIN': m_negbin, 'MIN_X_PPM': m_min_x_ppm,
             'MIN_X_PPM_EB': m_min_x_ppm_eb}


def ppm_priors(pg, groups_by_slug):
    """Per position group: (minutes-weighted pts/min, kappa) by method of moments across players.
    kappa = within-player noise per minute / between-player variance of true rates, in minutes."""
    tot = pg.groupby('slug')[['points', 'minutes']].sum()
    tot = tot[tot['minutes'] >= 100]
    resid = pg.merge((tot['points'] / tot['minutes']).rename('rate'), left_on='slug', right_index=True)
    s2 = float(((resid['points'] - resid['rate'] * resid['minutes']) ** 2).sum() / resid['minutes'].sum())
    out = {}
    for pos in POSITIONS + ['ALL']:
        slugs = tot.index if pos == 'ALL' else [s for s in tot.index if pos in groups_by_slug.get(s, ())]
        t = tot.loc[[s for s in slugs if s in tot.index]]
        if len(t) < 10:
            continue
        rate = t['points'] / t['minutes']
        mu = float(t['points'].sum() / t['minutes'].sum())
        tau2 = float(np.var(rate) - np.mean(s2 / t['minutes']))
        out[pos] = (mu, float(np.clip(s2 / tau2, 50, 2000)) if tau2 > 0 else 2000.0)
    return out


####################################################################################################
# 004 - BACKTEST, PER PLAYER
####################################################################################################

def origins_for(n):
    return list(range(max(MIN_TRAIN, n - N_ORIGINS - H + 1), n))


def run_player(slug, df, fut, ctx):
    """Backtest every statistical model on one player's games, then fit on all games and forecast `fut`.
    Returns {'errors': {model: (n_origins, H) signed actual - pred}, 'forecast': {model: array},
             'params': {model: dict}, 'diag': {model: dict}, 'failed': {model: msg}}."""
    df = df.reset_index(drop=True)
    n = len(df)
    origins = origins_for(n)
    ctx = dict(ctx)
    ctx['arima_order'] = select_arima(df['points'].values[:origins[0]] if origins else df['points'].values)
    errors = {m: np.full((len(origins), H), np.nan) for m in STAT_FITS}
    failed = {}
    for k, o in enumerate(origins):
        tr, te = df.iloc[:o], df.iloc[o:o + H].copy()
        te['min_proj'] = df['min_ewm'].iloc[o - 1]          # minutes projection known at the origin
        for m, fit in STAT_FITS.items():
            try:
                p = np.asarray(fit(tr, te, ctx)[0], dtype=float)
                errors[m][k, :len(te)] = te['points'].values - p
            except Exception as e:
                failed.setdefault(m, f'{type(e).__name__}: {e}')
    forecast, params, diag = {}, {}, {}
    final_ctx = dict(ctx, arima_order=select_arima(df['points'].values))
    for m, fit in STAT_FITS.items():
        try:
            p, prm, dg = fit(df, fut, final_ctx)
            forecast[m] = np.asarray(p, dtype=float)
            params[m], diag[m] = _clean(prm), _clean(dg)
        except Exception as e:
            failed[m] = f'{type(e).__name__}: {e}'
    return {'slug': slug, 'n_games': n, 'origins': origins, 'errors': errors, 'forecast': forecast,
            'params': params, 'diag': diag, 'failed': failed}


def _clean(d):
    out = {}
    for k, v in d.items():
        if isinstance(v, (np.floating, np.integer)):
            v = v.item()
        if isinstance(v, float) and not np.isfinite(v):
            v = None
        out[k] = v
    return out


####################################################################################################
# 005 - SCORING AND CHAMPION
####################################################################################################

def mae_table(errors):
    """{model: (n_origins, H)} -> DataFrame model x [mae, mae_h1..mae_h5]."""
    rows = {}
    for m, e in errors.items():
        a = np.abs(e)
        if np.isnan(a).all():
            continue
        rows[m] = {'mae': np.nanmean(a), **{f'mae_h{h + 1}': (np.nanmean(a[:, h]) if (~np.isnan(a[:, h])).any()
                                                              else np.nan) for h in range(H)}}
    return pd.DataFrame(rows).T


def dm_pvalue(err_a, err_b):
    """One-sided Diebold-Mariano: H1 = model b has lower absolute error than model a.
    Loss per origin = mean |error| over its horizons; Newey-West variance with H-1 lags."""
    la, lb = np.nanmean(np.abs(err_a), axis=1), np.nanmean(np.abs(err_b), axis=1)
    d = la - lb
    d = d[np.isfinite(d)]
    n = len(d)
    if n < DM_MIN_ORIGINS:
        return np.nan
    dc = d - d.mean()
    lrv = dc @ dc / n
    for k in range(1, H):
        lrv += 2 * (1 - k / H) * (dc[k:] @ dc[:-k]) / n
    if lrv <= 0:
        lrv = dc @ dc / n
    if lrv <= 0:
        return np.nan
    t = d.mean() / np.sqrt(lrv / n)
    return float(1 - stats.t.cdf(t, n - 1))


def roster_default(tables):
    """Best mean skill (1 - MAE / naive MAE) across players with enough origins."""
    skills = {}
    for slug, t in tables.items():
        if 'NAIVE' not in t.index or t.attrs.get('n_origins', 0) < DM_MIN_ORIGINS:
            continue
        for m in t.index:
            skills.setdefault(m, []).append(1 - t.loc[m, 'mae'] / t.loc['NAIVE', 'mae'])
    if not skills:
        return 'MEAN_10', {}
    mean_skill = {m: float(np.mean(v)) for m, v in skills.items() if len(v) >= max(1, 0.8 * max(map(len, skills.values())))}
    return max(mean_skill, key=mean_skill.get), mean_skill


def pick_champion(t, errors, default):
    """Champion for one player: the roster default unless their own best is significantly better."""
    if t.empty:
        return default, 'no backtest (too few games): roster default'
    best = t['mae'].astype(float).idxmin()
    if default not in t.index:
        return best, 'roster default unavailable: lowest backtest MAE'
    if best == default:
        return default, 'roster default and this player\'s lowest backtest MAE'
    # `best` is the minimum of len(t) - 1 challengers, so Bonferroni-correct the threshold
    p, alpha = dm_pvalue(errors[default], errors[best]), DM_ALPHA / max(1, len(t) - 1)
    if np.isfinite(p) and p < alpha:
        return best, f'beats roster default {MODELS[default][0]} (Diebold-Mariano p={p:.4f} < {alpha:.4f})'
    reason = 'too few origins to test' if not np.isfinite(p) else f'p={p:.3f}, needs < {alpha:.4f}'
    return default, f'roster default; {MODELS[best][0]} not significantly better ({reason})'


def interval(errors_m, pooled=None):
    """80% range offsets (10th, 90th percentile of signed errors, all horizons pooled)."""
    e = errors_m[np.isfinite(errors_m)] if errors_m is not None else np.array([])
    if len(e) < 15 and pooled is not None and len(pooled):
        e = pooled
    if len(e) == 0:
        return np.nan, np.nan
    return float(np.quantile(e, 0.10)), float(np.quantile(e, 0.90))


def to_json(d):
    return json.dumps({k: (round(v, 4) if isinstance(v, float) else v) for k, v in d.items()})
