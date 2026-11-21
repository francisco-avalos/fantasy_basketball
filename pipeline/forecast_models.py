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
    dl           TFT, DEEPAR: one of each per position group, in pipeline/deep_models.py

Inputs used by ARIMAX / NEGBIN / XGB (all known before tip-off; ARIMAX leaves out tm_out_usg, see EXOG)
    min_lag5   minutes EWM through the player's game 5 games before the target, the same at every horizon in
               training, backtest and forecast (it used to be refreshed every game in training and frozen at the
               origin when forecasting); XGB also sees the EWM at the origin
    home, rest (team days off, capped at 4), b2b
    opp_def    opponent defensive rating: points allowed per 100 possessions over its last 15 games minus the league
               average (30 days). Points allowed per game, used before, also measures pace and overlapped opp_pace,
               which made ARIMAX / NEGBIN's linear coefficients unstable.
    opp_pace   possessions per game over its last 15 games minus the league average
    tm_out_usg teammates out: the sum, over teammates with an injury / non-medical episode open, of their usage
               share x minutes share (their share of the team's possessions per game), as of their last game.
               NEGBIN trains on each game's own value; XGB takes the origin game's value for all 5 targets (h lets
               it learn how fast it fades); the backtest and the forecast carry the value known at the origin to
               all 5 games. The forecast also counts teammates ESPN lists OUT / SUSPENSION today
               (teammates_out_now).

XGB-only features (origin_features)
    usg_ewm       usage share of team possessions while on the floor, (FGA + 0.44 FTA + TOV) x (team minutes / 5)
                  / (minutes x team usage), minutes-weighted EWM. Per-minute volume, used before, grew with pace.
    role          started_last, start_rate5: a starter = top 5 on his team in minutes that game (the box scores
                  have no starter flag)
    team change   games_on_team (since his last team change in the 3-season window, capped at 40), new_team
                  (changed team, <= 20 games since), usg_ewm_team (usage on the current team only). A player on
                  a new team since his last game is forecast with games_on_team = 0, new_team = 1 (ROLE_RESET).
                  MIN_X_PPM(_EB) project minutes from the current team's games once there are TEAM_MIN_GAMES.

Team-game grid and playing time
    basketball-reference only lists players who got on the floor, so a missed game has no row. player_grid
    rebuilds every team game a player was on the roster for (each stint's first to last game, and the latest
    stint on to today while ESPN still lists him on that team), played = 1 when he has a box score. Missed
    games are tagged from player_injury_cycles: injury (an episode open that day), non_medical (suspension,
    personal), or unexplained (coach's decision, rest, G League, an unlogged DTD).
    The scoring models are "points if he plays": trained on games played, minutes averaged over games played.
    A separate classifier (fit_play_model) gives the chance he plays each of the team's next 5 games, from the
    open injury episode, runs of missed games, recent minutes and back-to-backs. expected points = chance x
    points if he plays. points_forecast.play_forecast then applies today's ESPN status (no status history to
    train on yet, so these are caps, not features): OUT -> P(back by that game) from his own survival curve
    and the historical OUT rate for the next game, DAY_TO_DAY -> the historical day-to-day rate for the next
    game (status_play_rates), ACTIVE while the transaction log still has him out -> the episode is ignored.

Backtest
    For each player, the last N_ORIGINS(+H-1) games played are origins. At origin o every model is refit on
    games [0, o) and forecasts the TEAM's next 5 games after it (the same games the live forecast covers:
    horizon h = the h-th team game, not the h-th game he plays). Errors (signed actual - pred, in points) are
    scored on the games he played; predictions for every game are kept for the expected-points score.
    XGB / TFT / DeepAR backtest models train only on targets on or before a cutoff. A player's own safe
    cutoff is the last game before their first origin. One cutoff for the whole roster would be the
    earliest of those (a long-injured player's, 2025-10-24 on 2026-11-12, against a median of
    2026-03-10), so up to N_CUTOFFS cutoffs are picked to minimise total staleness
    (backtest_cutoffs) and each player is scored by the model with the newest cutoff that is still safe
    for them (newest_cutoff). No player is ever scored on a game their model trained on.

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

from shared import season_calendar

warnings.filterwarnings('ignore')

H = 5                    # forecast horizon: the team's next 5 games
N_ORIGINS = 20           # backtest origins with a full 5-game horizon (plus H-1 shorter ones at the end)
MIN_TRAIN = 6            # games needed before the first origin
EXOG_MIN_TRAIN = 20      # ARIMAX / NEGBIN drop their inputs below this many training games (coefficients from
                         # a handful of games extrapolate wildly: one 7-game window predicted 4e8 points)
DM_ALPHA, DM_MIN_ORIGINS = 0.10, 8
EXOG = ['min_lag5', 'home', 'b2b', 'opp_def', 'opp_pace']       # ARIMAX's inputs; NEGBIN adds tm_out_usg (_nb_design).
# tm_out_usg made ARIMAX worse (backtest MAE 6.27 -> 6.30): for one player it is mostly 0 with rare spikes, too
# little to estimate a coefficient from a single series. NEGBIN's recency-weighted GLM handled it (6.24 -> 6.23).
POSITIONS = ['PG', 'SG', 'SF', 'PF', 'C']
REST_CAP = 4
N_CUTOFFS = 3            # backtest-model cutoffs for the ML / DL models (each costs one more backtest fit)

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
    'TFT': ('Temporal Fusion Transformer', 'dl'),      # pipeline/deep_models.py
    'DEEPAR': ('DeepAR (neg. binomial)', 'dl'),
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
    """Per team and game date: defensive rating (points allowed per 100 possessions) and pace over its last
    `window` games through that date, relative to the league average over the previous 30 days.
    opp_def > 0 means the team allows more per possession than average (a good matchup). allowed_roll is the
    rolling defensive rating itself (the page's opponent-defence rank)."""
    tg = tg.sort_values(['team', 'date']).copy()
    grp = tg.groupby('team')
    roll = lambda col: grp[col].transform(lambda s: s.rolling(window, min_periods=3).sum())
    tg['allowed_roll'] = 100 * roll('opp_points') / roll('pace')
    tg['pace_roll'] = grp['pace'].transform(lambda s: s.rolling(window, min_periods=3).mean())
    tg['rtg'] = 100 * tg['points'] / tg['pace']
    daily = tg.groupby('date')[['rtg', 'pace']].mean().sort_index()
    league = daily.rolling('30D').mean().rename(columns={'rtg': 'lg_rtg', 'pace': 'lg_pace'})
    tg = tg.merge(league, left_on='date', right_index=True, how='left')
    tg['opp_def'] = tg['allowed_roll'] - tg['lg_rtg']
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
    # usage rate: share of the team's possessions he used while on the floor (FGA + 0.44 FTA + TOV), team totals
    # from the same box scores. Per-minute volume, used before, grows with team pace.
    tm = box.groupby(['team', 'date'], as_index=False).agg(t_fga=('fga', 'sum'), t_fta=('fta', 'sum'),
                                                          t_tov=('tov', 'sum'), t_min=('minutes', 'sum'))
    pg = pg.merge(tm, on=['team', 'date'], how='left')
    use, t_use = pg['fga'] + 0.44 * pg['fta'] + pg['tov'], pg['t_fga'] + 0.44 * pg['t_fta'] + pg['t_tov']
    pg['usg_share'] = (use * (pg['t_min'] / 5) / (pg['minutes'] * t_use)).where(t_use > 0).clip(0, 0.6).fillna(0.15)
    pg = pg.drop(columns=['t_fga', 't_fta', 't_tov', 't_min'])
    # role proxy: a starter = top 5 on his team in minutes that game (box scores carry no starter flag)
    rk = box.assign(_r=box.groupby(['team', 'date'])['minutes'].rank(ascending=False, method='first'))
    pg = pg.merge(rk[['slug', 'date', '_r']], on=['slug', 'date'], how='left')
    pg['started'] = (pg['_r'] <= 5).astype(float)
    pg = pg.drop(columns=['_r'])
    # team stints: a new stint each time his team changes (a trade or signing inside the 3-season window)
    pg['stint'] = (pg['team'] != pg.groupby('slug', sort=False)['team'].shift()).groupby(pg['slug']).cumsum() - 1
    pg['games_on_team'] = pg.groupby(['slug', 'stint'], sort=False).cumcount() + 1
    g = pg.groupby('slug', sort=False)['minutes']
    pg['min_ewm'] = g.transform(lambda s: s.ewm(alpha=0.25).mean())      # through this game
    pg['min_lag5'] = pg.groupby('slug', sort=False)['min_ewm'].shift(H)  # through the game 5 games before
    # a player's first H games: his EWM after game 0 (the same clamp min_lag5_at uses), not a league median,
    # which made the column near-constant for short series and blew up the input models' extrapolation
    pg['min_lag5'] = pg['min_lag5'].fillna(pg.groupby('slug', sort=False)['min_ewm'].transform('first'))
    return pg


def min_lag5_at(min_ewm, last, h):
    """min_lag5 for the target h team games after played game index `last`: the EWM through game last + h - H,
    as if he plays every game in between (the definition training uses on games played)."""
    i = last + h - H
    return float(min_ewm[max(i, 0)])


####################################################################################################
# 002b - TEAM-GAME GRID AND PLAYING TIME
####################################################################################################

def team_game_table(box, future):
    """Every team game: played (from league-wide box scores) and scheduled."""
    past = box[['team', 'date', 'opponent', 'home']].drop_duplicates(['team', 'date'])
    return (pd.concat([past, future[['team', 'date', 'opponent', 'home']]])
            .drop_duplicates(['team', 'date']).sort_values(['team', 'date']).reset_index(drop=True))


def player_grid(pg, team_tbl, current_team, today):
    """One row per team game a player was on the roster for, played or not (see the module docstring).
    current_team: slug -> 'Team.X' from today's ESPN snapshot (extends the latest stint to today)."""
    p = pg[['slug', 'date', 'team', 'points', 'minutes']].sort_values(['slug', 'date'])
    stint = (p['team'] != p.groupby('slug')['team'].shift()).cumsum()
    st = p.assign(stint=stint).groupby(['slug', 'stint', 'team'], as_index=False).agg(first=('date', 'min'),
                                                                                       last=('date', 'max'))
    latest = st.groupby('slug')['stint'].transform('max') == st['stint']
    ext = latest & (st['slug'].map(current_team) == st['team'])
    st.loc[ext, 'last'] = pd.Timestamp(today) - pd.Timedelta(days=1)
    g = st.merge(team_tbl[['team', 'date', 'opponent', 'home']], on='team')
    g = g[(g['date'] >= g['first']) & (g['date'] <= g['last'])]
    g = g.merge(p[['slug', 'date', 'points', 'minutes']], on=['slug', 'date'], how='left')
    g['played'] = g['minutes'].notna().astype(int)
    return g.drop(columns=['first', 'last']).sort_values(['slug', 'date']).reset_index(drop=True)


INJURY_CATS = ('injury', 'illness', 'unspecified')


def episode_state(slugs, dates, episodes):
    """Injury episode open at the end of each (slug, date): the latest episode started on or before the date and
    not yet ended (end_date > date; an 'open' episode never ends). Columns ep_* aligned with the inputs."""
    q = pd.DataFrame({'slug': np.asarray(slugs), 'date': pd.to_datetime(np.asarray(dates))})
    q['_i'] = np.arange(len(q))
    cols = ['start_date', 'end', 'category', 'is_dtd', 'out_for_season', 'out_indefinitely', 'stated_days']
    out = pd.DataFrame(index=q['_i'], columns=cols)
    if episodes is not None and len(episodes):
        ep = episodes.dropna(subset=['slug']).copy()
        ep['end'] = ep['end_date'].where(ep['end_reason'] != 'open', pd.Timestamp('2100-01-01'))
        m = pd.merge_asof(q.sort_values('date'), ep.sort_values('start_date')[['slug'] + cols],
                          left_on='date', right_on='start_date', by='slug', direction='backward').set_index('_i')
        m.loc[~(m['end'] > m['date']), cols] = np.nan                   # that episode already ended
        out.loc[m.index, cols] = m[cols].values
    out = out.reset_index(drop=True)
    inj = out['category'].isin(INJURY_CATS)
    clock = lambda d: np.asarray(season_calendar.clock(pd.to_datetime(d)), dtype=float)
    days = np.full(len(q), np.nan)
    ok = inj.values | (out['category'] == 'non_medical').values
    if ok.any():
        days[ok] = clock(q['date'].values[ok]) - clock(out.loc[ok, 'start_date'].values)
    return pd.DataFrame({
        'inj_open': inj.astype(float).values, 'nonmed_open': (out['category'] == 'non_medical').astype(float).values,
        'ep_days': np.clip(days, 0, 120), 'ep_dtd': pd.to_numeric(out['is_dtd'], errors='coerce').fillna(0).values,
        'ep_out_season': pd.to_numeric(out['out_for_season'], errors='coerce').fillna(0).values,
        'ep_out_indef': pd.to_numeric(out['out_indefinitely'], errors='coerce').fillna(0).values,
        'has_stated': pd.to_numeric(out['stated_days'], errors='coerce').notna().astype(float).values,
        'ep_stated_left': (pd.to_numeric(out['stated_days'], errors='coerce').values - days),
        'ep_start': pd.to_datetime(out['start_date']).values})


def grid_features(grid, episodes, rest, ratings):
    """Grid + absence reason, the state after each team game (origin features for the playing-time model and
    games_since_return for the scoring models) and the pre-game inputs of each game (as player_games does)."""
    g = grid.sort_values(['slug', 'date']).reset_index(drop=True)
    st = episode_state(g['slug'], g['date'], episodes)
    g = pd.concat([g, st], axis=1)
    g['reason'] = np.where(g['played'] == 1, 'played', np.where(g['inj_open'] == 1, 'injury',
                           np.where(g['nonmed_open'] == 1, 'non_medical', 'unexplained')))
    miss = 1 - g['played']
    run = (g['played'] != g.groupby('slug')['played'].shift()).cumsum()
    g['miss_streak'] = miss.groupby(run).cumsum() * miss
    unex = (g['reason'] == 'unexplained').astype(int)
    urun = (unex != unex.groupby(g['slug']).shift()).cumsum()
    g['unexpl_streak'] = unex.groupby(urun).cumsum() * unex
    by = g.groupby('slug', sort=False)['played']
    g['played5'] = by.transform(lambda s: s.rolling(5, min_periods=1).mean())
    g['played10'] = by.transform(lambda s: s.rolling(10, min_periods=1).mean())
    mins = g['minutes'].where(g['played'] == 1)
    g['min_ewm_o'] = mins.groupby(g['slug']).transform(lambda s: s.ewm(alpha=0.25, ignore_na=True).mean()).fillna(0)
    # games played since the end of the last run of 3+ missed team games (capped)
    gsr = np.zeros(len(g))
    for idx in g.groupby('slug', sort=False).indices.values():
        pl, ms = g['played'].values[idx], g['miss_streak'].values[idx]
        c = 15
        for k, i in enumerate(idx):
            if pl[k] == 1:
                c = 1 if (k > 0 and ms[k - 1] >= 3) else min(c + 1, 15)
            gsr[i] = c
    g['games_since_return'] = gsr
    g = g.merge(rest, on=['team', 'date'], how='left')
    g['rest'] = g['rest'].fillna(REST_CAP)
    g['b2b'] = (g['rest'] == 0).astype(float)
    r = ratings_asof(ratings, g['opponent'], g['date'] - pd.Timedelta(days=1))
    g['opp_def'], g['opp_pace'] = r['opp_def'].values, r['opp_pace'].values
    return g


def player_importance(pg):
    """Share of his team's possessions a player uses per game, through each game played: usage share (minutes-
    weighted EWM) x minutes EWM / 48."""
    g = pg.groupby('slug', sort=False)
    u = pg.assign(_u=pg['usg_share'] * pg['minutes']).groupby('slug', sort=False)['_u'].transform(
        lambda s: s.ewm(alpha=0.1).mean())
    m = g['minutes'].transform(lambda s: s.ewm(alpha=0.1).mean())
    return (u / m.where(m > 0)).fillna(0) * pg['min_ewm'].clip(0, 48) / 48


def teammate_absence(gf, pg):
    """tm_out_usg for every grid row (see the module docstring): teammates on the same team-game who are out
    with an episode open that day, each weighted by his importance through his last game played. Adds
    'importance' and 'tm_out_usg' to gf; returns (gf, pg with tm_out_usg)."""
    imp = pg[['slug', 'date']].assign(importance=player_importance(pg).values)
    g = gf.merge(imp, on=['slug', 'date'], how='left')
    g['importance'] = g.groupby('slug', sort=False)['importance'].ffill().fillna(0)
    out = ((g['played'] == 0) & g['reason'].isin(['injury', 'non_medical'])).astype(float)
    g['_out'] = out * g['importance']
    team = g.groupby(['team', 'date'])['_out'].transform('sum')
    g['tm_out_usg'] = (team - g['_out']).clip(lower=0)
    pg = pg.merge(g[['slug', 'date', 'tm_out_usg']], on=['slug', 'date'], how='left')
    pg['tm_out_usg'] = pg['tm_out_usg'].fillna(0)
    return g.drop(columns=['_out']), pg


OUT_STATUSES = ('OUT', 'SUSPENSION')


def teammates_out_now(gf, episodes, status, current_team, today, recent_days=21):
    """For the forecast: {team: {slug: importance}} of players out today. A player belongs to his team in
    today's ESPN snapshot, else to the team of his latest grid row if that is within `recent_days`. Out = an
    injury / non-medical episode open today, or ESPN status OUT / SUSPENSION."""
    last = gf.sort_values('date').groupby('slug').tail(1).set_index('slug')
    last = last[last['date'] >= pd.Timestamp(today) - pd.Timedelta(days=recent_days)]
    team = {s: current_team.get(s, t) for s, t in last['team'].items()}
    team.update({s: t for s, t in current_team.items() if s in last.index})
    slugs = list(team)
    st = episode_state(slugs, [pd.Timestamp(today)] * len(slugs), episodes)
    out = set(np.asarray(slugs)[(st['inj_open'] + st['nonmed_open']).values > 0])
    if status is not None and len(status):
        out |= set(status.loc[status['injury_status'].isin(OUT_STATUSES), 'slug'].dropna())
    res = {}
    for s in out:
        if s in team and s in last.index:
            res.setdefault(team[s], {})[s] = float(last.loc[s, 'importance'])
    return res


def status_play_rates(gf):
    """Historical chance of playing the next team game, used to cap the forecast by today's ESPN status (we have
    no status history to train on yet): DAY_TO_DAY = after a day-to-day episode with at most one game missed;
    OUT = after any other open injury episode. From the grid, every season loaded."""
    g = gf.sort_values(['slug', 'date'])
    prev = g.groupby('slug', sort=False)[['inj_open', 'ep_dtd', 'miss_streak']].shift()
    dtd = (prev['inj_open'] == 1) & (prev['ep_dtd'] == 1) & (prev['miss_streak'] <= 1)
    out = (prev['inj_open'] == 1) & (prev['ep_dtd'] == 0)
    return {'DAY_TO_DAY': float(g.loc[dtd, 'played'].mean()), 'OUT': float(g.loc[out, 'played'].mean()),
            'n_dtd': int(dtd.sum()), 'n_out': int(out.sum())}


PLAY_FEATS = ['inj_open', 'nonmed_open', 'ep_days', 'ep_dtd', 'ep_out_season', 'ep_out_indef', 'has_stated',
              'ep_stated_left', 'miss_streak', 'unexpl_streak', 'played5', 'played10', 'min_ewm_o',
              'games_since_return', 'h', 'days_ahead', 'b2b']
PLAY_MAX_DAYS = 21          # playing-time rows: only targets this close to the origin (no offseason jumps)
PLAY_PARAMS = dict(n_estimators=500, learning_rate=0.05, max_depth=4, min_child_weight=50, subsample=0.8,
                   colsample_bytree=0.8, objective='binary:logistic', eval_metric='logloss', tree_method='hist',
                   early_stopping_rounds=40, n_jobs=4, random_state=42)


def play_rows(gf):
    """Direct multi-horizon rows for the playing-time model: state after team game t, target = played at the
    team's game t+h (h = 1..H)."""
    out = []
    by = gf.groupby('slug', sort=False)
    for h in range(1, H + 1):
        nxt = by[['date', 'played', 'b2b']].shift(-h)
        r = gf[[c for c in PLAY_FEATS if c in gf and c not in ('h', 'days_ahead', 'b2b')]].copy()
        r['slug'], r['origin_date'], r['h'] = gf['slug'], gf['date'], h
        r['days_ahead'] = (nxt['date'] - gf['date']).dt.days
        r['b2b'], r['target'], r['target_date'] = nxt['b2b'], nxt['played'], nxt['date']
        out.append(r[r['target'].notna() & (r['days_ahead'] <= PLAY_MAX_DAYS)])
    rows = pd.concat(out, ignore_index=True)
    rows['ep_stated_left'] = rows['ep_stated_left'].fillna(-99)
    return rows


def fit_play_model(rows):
    """XGBoost classifier, chance of playing. Last 10% of target dates = early-stopping set."""
    from xgboost import XGBClassifier
    rows = rows.sort_values('target_date')
    cut = rows['target_date'].quantile(0.9)
    tr, va = rows[rows['target_date'] < cut], rows[rows['target_date'] >= cut]
    model = XGBClassifier(**PLAY_PARAMS)
    model.fit(tr[PLAY_FEATS].astype(float), tr['target'].astype(int),
              eval_set=[(va[PLAY_FEATS].astype(float), va['target'].astype(int))], verbose=False)
    return model


def play_scores(y, p, baseline):
    """Brier / log loss / AUC of p, and the same Brier for a baseline (share of the last 10 games played)."""
    from sklearn.metrics import roc_auc_score, log_loss
    y, p, b = np.asarray(y, float), np.clip(np.asarray(p, float), 1e-4, 1 - 1e-4), np.clip(np.asarray(baseline, float), 1e-4, 1 - 1e-4)
    return {'n': int(len(y)), 'played_rate': float(y.mean()), 'brier': float(np.mean((p - y) ** 2)),
            'brier_baseline': float(np.mean((b - y) ** 2)), 'log_loss': float(log_loss(y, p, labels=[0, 1])),
            'auc': float(roc_auc_score(y, p)) if 0 < y.mean() < 1 else float('nan')}


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
    # usage share, minutes-weighted (a 30-minute game counts more than a 5-minute one)
    f['usg_ewm'] = pg.assign(_u=pg['usg_share'] * pg['minutes']).groupby('slug', sort=False)['_u'].transform(
        lambda s: s.ewm(alpha=0.1).mean()) / min_w.where(min_w > 0)
    f['fga_mean5'] = roll('fga', 5)
    f['fta_mean5'] = roll('fta', 5)
    f['fg3a_mean5'] = roll('fg3a', 5)
    gs = pg.groupby(['slug', 'season'], sort=False)['points']
    f['season_mean'] = gs.transform(lambda s: s.expanding().mean())
    f['games_season'] = gs.cumcount() + 1
    f['gap_before'] = g['date'].diff().dt.days.clip(0, 30).fillna(30)
    f['games_since_return'] = pg['games_since_return'] if 'games_since_return' in pg else 15.0
    # role and team (step 7): starter share of the last 5, starter last game, games on his current team, a
    # flag for a team change in the window with <= 20 games since, and usage share on the current team only
    f['started_last'] = pg['started']
    f['start_rate5'] = roll('started', 5)
    f['games_on_team'] = pg['games_on_team'].clip(upper=40).astype(float)
    f['new_team'] = ((pg['stint'] > 0) & (pg['games_on_team'] <= 20)).astype(float)
    gt = pg.assign(_u=pg['usg_share'] * pg['minutes']).groupby(['slug', 'stint'], sort=False)
    f['usg_ewm_team'] = (gt['_u'].transform(lambda s: s.ewm(alpha=0.1).mean())
                         / gt['minutes'].transform(lambda s: s.ewm(alpha=0.1).mean()).where(lambda m: m > 0))
    return f


TARGET_FEATS = ['h', 'home', 'rest', 'b2b', 'opp_def', 'opp_pace', 'days_ahead', 'tm_out_usg']


def xgb_training_rows(pg, feats, ratings, gf):
    """Direct multi-horizon rows: features at played game t, target = points at the TEAM's h-th game after it
    (from the grid gf). Rows whose target game he missed are kept with played = 0 (predicted for the
    expected-points score, never trained on)."""
    key = gf[['slug', 'date']].reset_index().rename(columns={'index': 'gpos'})
    pos = pg[['slug', 'date']].merge(key, on=['slug', 'date'], how='left')['gpos'].values
    cols = ['slug', 'date', 'points', 'played', 'opponent', 'home', 'rest', 'b2b']
    out = []
    for h in range(1, H + 1):
        nxt = gf[cols].shift(-h)                    # gf is sorted by slug, date; a different slug is dropped below
        ok = ~np.isnan(pos)
        t = pd.DataFrame(index=pg.index, columns=nxt.columns)
        t.loc[ok] = nxt.iloc[pos[ok].astype(int)].values
        t = t[t['slug'] == pg['slug']]                                      # next grid row is the same player's
        rows = feats.loc[t.index].copy()
        rows['slug'], rows['origin_date'], rows['h'] = pg.loc[t.index, 'slug'], pg.loc[t.index, 'date'], h
        rows['home'], rows['rest'], rows['b2b'] = (pd.to_numeric(t['home']), pd.to_numeric(t['rest']),
                                                   pd.to_numeric(t['b2b']))
        r = ratings_asof(ratings, t['opponent'], rows['origin_date'])       # opponent form as of the origin
        rows['opp_def'], rows['opp_pace'] = r['opp_def'].values, r['opp_pace'].values
        rows['days_ahead'] = (pd.to_datetime(t['date']) - rows['origin_date']).dt.days
        rows['tm_out_usg'] = pg.loc[t.index, 'tm_out_usg'].values                 # as known at the origin
        rows['target'] = pd.to_numeric(t['points'])
        rows['played'] = pd.to_numeric(t['played'])
        rows['target_date'] = pd.to_datetime(t['date'])
        out.append(rows)
    return pd.concat(out, ignore_index=True)


XGB_FEATS = ['pts_last', 'pts_mean3', 'pts_mean5', 'pts_mean10', 'pts_std10', 'pts_ewm', 'min_last', 'min_mean5',
             'min_ewm', 'ppm_ewm', 'usg_ewm', 'fga_mean5', 'fta_mean5', 'fg3a_mean5', 'season_mean',
             'games_season', 'gap_before', 'games_since_return', 'started_last', 'start_rate5', 'games_on_team',
             'new_team', 'usg_ewm_team'] + TARGET_FEATS
ROLE_RESET = {'games_on_team': 0.0, 'new_team': 1.0}   # forecast for a player on a new team since his last game

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
    if len(df) < EXOG_MIN_TRAIN:              # too few games to estimate input effects: plain ARMA
        r = SARIMAX(df['points'].values, order=(p, 0, q), trend='c').fit(disp=False)
        return (r.forecast(len(fut)), {'order': [p, 0, q], 'inputs': 'dropped (few games)', **_arma_params(r)},
                {'aicc': _aicc(r), 'ljung_box_p': _lb(r.resid)})
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
    X = pd.DataFrame({'log_min': np.log(d['min_lag5'].astype(float).clip(lower=1.0)), 'home': d['home'], 'b2b': d['b2b'],
                      'opp_def': d['opp_def'], 'opp_pace': d['opp_pace'], 'tm_out_usg': d['tm_out_usg']}).astype(float)
    return sm.add_constant(X, has_constant='add')


def m_negbin(df, fut, ctx, half_life=30):
    """Count GLM, log link: log E[pts] = b0 + b1 log(min_lag5) + home + b2b + opponent defence/pace.
    Recent games weigh more (half-life in games). Dispersion alpha by moments from a Poisson fit."""
    X, y = _nb_design(df), df['points'].values
    Xf = _nb_design(fut)
    if len(df) < EXOG_MIN_TRAIN:              # too few games to estimate input effects: weighted mean only
        X, Xf = X[['const']], Xf[['const']]
    w = 0.5 ** ((len(df) - 1 - np.arange(len(df))) / half_life)
    pois = sm.GLM(y, X, family=sm.families.Poisson(), var_weights=w).fit()
    mu = pois.fittedvalues
    alpha = float(np.clip(np.sum(w * ((y - mu) ** 2 - mu) / mu ** 2) / np.sum(w), 1e-3, 5))
    r = sm.GLM(y, X, family=sm.families.NegativeBinomial(alpha=alpha), var_weights=w).fit()
    prm = {k: float(v) for k, v in r.params.items()}
    prm['alpha_dispersion'] = alpha
    return np.asarray(r.predict(Xf)), prm, {'ljung_box_p': _lb(y - r.fittedvalues)}


def _weighted_rate(df, half_life):
    w = 0.5 ** ((len(df) - 1 - np.arange(len(df))) / half_life)
    return float(np.sum(w * df['points'])), float(np.sum(w * df['minutes']))


TEAM_MIN_GAMES = 3      # after a team change, project minutes from the new team's games once he has this many


def _proj_minutes(df):
    """Minutes EWM; after a team change, from his games on the current team only (if >= TEAM_MIN_GAMES)."""
    m = df['minutes']
    if 'team' in df and df['team'].nunique() > 1:
        run = (df['team'] != df['team'].iloc[-1])[::-1].cumsum()[::-1] == 0     # trailing games on today's team
        if run.sum() >= TEAM_MIN_GAMES and not run.all():
            m = m[run]
    return float(m.ewm(alpha=0.25).mean().iloc[-1])


def m_min_x_ppm(df, fut, ctx):
    """points = projected minutes x points per minute (both exponentially weighted; minutes from the current
    team's games after a team change)."""
    P, M = _weighted_rate(df, 15)
    ppm = P / M if M > 0 else 0.0
    mins = _proj_minutes(df)
    return np.repeat(mins * ppm, len(fut)), {'proj_minutes': mins, 'pts_per_min': ppm}, {}


def m_min_x_ppm_eb(df, fut, ctx):
    """As MIN_X_PPM, with points/minute shrunk (empirical Bayes): recent rate -> the player's rate over
    all games in the window -> the position-group rate, each with prior strength kappa minutes."""
    mu_g, kappa = ctx.get('ppm_prior', (0.45, 300.0))
    P_all, M_all = float(df['points'].sum()), float(df['minutes'].sum())
    long_run = (P_all + kappa * mu_g) / (M_all + kappa)
    P, M = _weighted_rate(df, 15)
    ppm = (P + kappa * long_run) / (M + kappa)
    mins = _proj_minutes(df)
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


def backtest_targets(df, grid_s, origins):
    """For each origin (after played game o-1): the team's next H games from the player's grid, with their
    pre-game inputs and min_lag5. -> list of DataFrames (points NaN where he didn't play)."""
    m = df['min_ewm'].values
    out = []
    for o in origins:
        d = df['date'].iloc[o - 1]
        te = grid_s[grid_s['date'] > d].head(H).copy().reset_index(drop=True)
        te['h'] = np.arange(1, len(te) + 1)
        te['min_lag5'] = [min_lag5_at(m, o - 1, h) for h in te['h']]
        te['tm_out_usg'] = float(df['tm_out_usg'].iloc[o - 1])            # teammates out, as known at the origin
        te['points'] = te['points'].where(te['played'] == 1)
        out.append(te)
    return out


def run_player(slug, df, fut, ctx, grid_s):
    """Backtest every statistical model on one player's games, then fit on all games and forecast `fut`.
    Returns {'errors': {model: (n_origins, H) signed actual - pred, NaN where he didn't play},
             'preds': {model: (n_origins, H) predictions for every team game}, 'played': (n_origins, H),
             'forecast': {model: array}, 'params': {model: dict}, 'diag': {model: dict}, 'failed': {model: msg}}."""
    df = df.reset_index(drop=True)
    n = len(df)
    origins = origins_for(n)
    ctx = dict(ctx)
    ctx['arima_order'] = select_arima(df['points'].values[:origins[0]] if origins else df['points'].values)
    errors = {m: np.full((len(origins), H), np.nan) for m in STAT_FITS}
    preds = {m: np.full((len(origins), H), np.nan) for m in STAT_FITS}
    played = np.full((len(origins), H), np.nan)
    failed = {}
    for k, (o, te) in enumerate(zip(origins, backtest_targets(df, grid_s, origins))):
        if te.empty:
            continue
        tr = df.iloc[:o]
        played[k, :len(te)] = te['played'].values
        for m, fit in STAT_FITS.items():
            try:
                p = np.asarray(fit(tr, te, ctx)[0], dtype=float)[:len(te)]
                preds[m][k, :len(te)] = p
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
    return {'slug': slug, 'n_games': n, 'origins': origins, 'errors': errors, 'preds': preds, 'played': played,
            'forecast': forecast, 'params': params, 'diag': diag, 'failed': failed}


def _clean(d):
    out = {}
    for k, v in d.items():
        if isinstance(v, (np.floating, np.integer)):
            v = v.item()
        if isinstance(v, float) and not np.isfinite(v):
            v = None
        out[k] = v
    return out


def player_cutoff(df):
    """Latest training cutoff that is safe for this player: the date of the last game before their first
    backtest origin (None without origins)."""
    o = origins_for(len(df))
    return df['date'].iloc[o[0] - 1] if o else None


def backtest_cutoffs(needed, k=N_CUTOFFS):
    """Per-player safe cutoffs -> at most k cutoffs, chosen so that sum over players of (own cutoff - cutoff
    used) in in-season days is minimal when each uses the newest cutoff at or before their own. Exact: dynamic
    programming over the sorted distinct dates; a segment's cutoff is its earliest date."""
    dates = pd.Series(pd.to_datetime([d for d in needed if d is not None]))
    if dates.empty:
        return []
    cnt = dates.value_counts().sort_index()
    u, w = cnt.index, cnt.values
    m, k = len(u), min(k, len(u))
    day = np.asarray(season_calendar.clock(u), dtype=float)      # in-season days: the offseason has no games

    def cost(i, j):          # players with dates u[i..j], all using u[i]
        return float(np.sum(w[i:j + 1] * (day[i:j + 1] - day[i])))
    best = {(0, j): (cost(0, j), [0]) for j in range(m)}           # (segments - 1, last index) -> (cost, starts)
    for t in range(1, k):
        for j in range(t, m):
            best[(t, j)] = min((best[(t - 1, i - 1)][0] + cost(i, j), best[(t - 1, i - 1)][1] + [i])
                               for i in range(t, j + 1))
    _, starts = min(best[(t, m - 1)] for t in range(k))
    return [u[i] for i in starts]


def newest_cutoff(own, cutoffs):
    """The newest of `cutoffs` at or before this player's own safe cutoff (None if there is none)."""
    ok = [c for c in cutoffs if c is not None and own is not None and pd.Timestamp(c) <= pd.Timestamp(own)]
    return max(ok) if ok else None


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
