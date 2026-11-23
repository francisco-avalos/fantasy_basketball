"""
forecast_drift_monitor.py
-------------------------
Live drift checks for the points forecasts (pipeline/points_forecast.py), written to
basketball.forecast_model_monitoring, with a "model health" summary for the GitHub Actions run page.

Every nightly run logs all 15 models' forecasts (points_forecasts) and each model's backtest error per
player and horizon (model_runs). Once a game is played, each logged forecast can be scored against the
error its own run's backtest promised. The backtest is redone nightly on each player's last 20 games and
XGBoost refits nightly, so staleness is mostly absorbed. Live error well above the backtest's means one of
    - an optimistic backtest (a leak: ARIMAX / NEGBIN's backtest sees opponent form a few days ahead),
    - inputs that exist only at forecast time (projected min_lag5, ESPN teammates out, the status caps),
    - or a real change (roles, league scoring, the start of a season).
The checks below are built to tell those apart.

    0  data_inputs       box scores, forecast run, ESPN snapshot and schedule up to date; roster positions;
                         PSI of the main XGB inputs over the last 14 days vs the rows before (> 0.2)
    1  live_vs_backtest  per model and week: live skill (1 - MAE / NAIVE's MAE on the same forecasts)
                         against the skill its runs' backtests promised (same ratio of backtest MAEs at each
                         forecast's horizon). Alert when the gap is below -0.05 with a 95% bootstrap interval
                         below 0, in each of the last 2 weeks
    2  bias              mean (forecast - points) on games played: |bias| > 0.75 with the interval on one
                         side of 0, 2 weeks running
    3  coverage          share of games played inside the 80% range: outside 70-90%, 2 weeks running
    4  ranking           paired weekly comparison of the roster default (most players' champion) against
                         each other model on the same player-games; alert when one beats it at
                         p < 0.10 / (number of challengers) in each of the last 3 weeks
    5  playing_time      p_play over the last 14 days: Brier (> 0.13), calibration by band (> 0.15 off),
                         expected points vs "assume he plays" on every team game, and how often players ESPN
                         listed OUT / DAY_TO_DAY on the run date played game 1 vs the p_play given (28 days)
    6  season_start      champion live MAE / backtest MAE since the season started, for players with no
                         games last season, players on a new team, and players with < 10 games this season.
                         Alerts (> x1.25 with the interval above 1) only in the first 45 in-season days

Scored rows: forecasts from runs since the first one with p_play (2026-11-21, the team-game definitions;
earlier runs counted horizons in games played) or --since, game dates in the last 63 days, only games the
team actually played (a box score exists for its team that day) and only days box scores are loaded for.
A game forecast by several runs at the same horizon (off days) counts once, from the latest run.
A "week" is a 7-day window ending on the last day box scores are loaded for (then the 7 days before it,
...), so a check always uses the freshest games whatever weekday it runs; a window needs 30 player-games
before it can alert.
"Points if he plays" (prediction) is scored on games he played; expected points on every team game, a
missed game counting as 0. Bootstrap intervals resample player-games (all horizons and models of one
player's game move together), 1000 draws.

Statuses: ok, alert, info (too little data to judge, or a reference value). Nothing here changes a model:
an alert is a prompt to look (CLAUDE.md lists what each one usually means), and the workflow step never
fails the run. Weekly; nightly for the first 30 in-season days of a season.

Run from the repo root (env: basketball-env-useme-v11052026), after points_forecast:
    python -m pipeline.forecast_drift_monitor                  # run the checks if due; print the summary
    python -m pipeline.forecast_drift_monitor --force          # run them now
    python -m pipeline.forecast_drift_monitor --dry-run        # run them now, print, write nothing
    python -m pipeline.forecast_drift_monitor --summary-only   # print the latest stored results
    python -m pipeline.forecast_drift_monitor --dry-run --since 2026-11-11   # score older runs too
Needs sql_files/migrations/2026-11-22_forecast_model_monitoring.sql.
"""

import argparse
import datetime as dt
import math
import os
import warnings

import numpy as np
import pandas as pd
import mysql.connector as mysql

from shared import season_calendar as cal

warnings.filterwarnings('ignore')

config = {'host': os.environ.get('sports_db_admin_host'), 'user': os.environ.get('sports_db_admin_user'),
          'password': os.environ.get('sports_db_admin_pw'), 'port': os.environ.get('sports_db_admin_port'),
          'database': 'basketball'}

EVERY_DAYS = 7
SEASON_START_DAYS, SEASON_START_ALERT_DAYS = 30, 45   # nightly checks / segment alerts in a season's first days
LOOKBACK_DAYS = 63
MIN_WEEK_N = 30                  # player-games a week needs before it can alert
SKILL_GAP, BIAS_MAX = 0.05, 0.75
COV_LO, COV_HI = 0.70, 0.90
RANK_ALPHA, RANK_WEEKS = 0.10, 3
BRIER_MAX, CAL_GAP, CAP_GAP = 0.13, 0.15, 0.10
PLAY_DAYS, STATUS_DAYS, MIN_PLAY_N, MIN_STATUS_N, MIN_BAND_N = 14, 28, 100, 30, 30
SEG_RATIO, SEG_MIN_N = 1.25, 30
PSI_MAX, PSI_RECENT_DAYS, PSI_MIN_N = 0.2, 14, 200
PSI_FEATS = ['min_lag5', 'min_ewm', 'usg_ewm', 'pts_ewm', 'opp_def', 'opp_pace', 'tm_out_usg', 'rest']
BOX_MAX_AGE, RUN_MAX_AGE, ESPN_MAX_AGE, POS_MISSING_MAX = 2, 1, 1, 0.2
B = 1000
REF = 'NAIVE'
HISTORIC_CAPS = 'game-1 caps from history: OUT 17%, day-to-day 46%'
CHECKS = [('data_inputs', 'Data and inputs'), ('live_vs_backtest', 'Live vs backtest skill'), ('bias', 'Bias'),
          ('coverage', '80% range coverage'), ('ranking', 'Model ranking'), ('playing_time', 'Chance of playing'),
          ('season_start', 'Season-start segments')]
COLS = ['run_date', 'check_name', 'unit', 'metric', 'value', 'threshold', 'status', 'n', 'detail']


def row(check, metric, value=None, threshold=None, status='ok', n=None, detail='', unit=''):
    num = lambda v: None if v is None or (isinstance(v, float) and not np.isfinite(v)) else float(v)
    return {'check_name': check, 'unit': unit, 'metric': metric, 'value': num(value), 'threshold': num(threshold),
            'status': status, 'n': None if n is None else int(n), 'detail': detail[:500]}


def query(sql, params=()):
    cn = mysql.connect(**config)
    try:
        cur = cn.cursor()
        cur.execute(sql, params)
        df = pd.DataFrame(cur.fetchall(), columns=cur.column_names)
        cur.close()
        return df
    finally:
        cn.close()


def day(d):
    d = pd.Timestamp(d)
    return f'{d:%b} {d.day}'


def pct(v, signed=False):
    return '–' if v is None or not np.isfinite(v) else (f'{v:+.0%}' if signed else f'{v:.0%}')


def boot(d, cols, stat, seed=0):
    """Point value and 95% interval of stat(*column sums), resampling player-games (slug, game_date)."""
    g = d.groupby(['slug', 'game_date'])[cols].sum()
    v = g.to_numpy(float)
    if len(v) == 0:
        return np.nan, np.nan, np.nan, 0
    with np.errstate(divide='ignore', invalid='ignore'):
        point = float(stat(*v.sum(0)))
        w = np.random.default_rng(seed).multinomial(len(v), np.full(len(v), 1 / len(v)), size=B)
        reps = np.asarray(stat(*(w @ v).T), float)
    reps = reps[np.isfinite(reps)]
    lo, hi = (np.percentile(reps, [2.5, 97.5]) if len(reps) else (np.nan, np.nan))
    return point, float(lo), float(hi), len(v)


def season_info(today):
    """(in_season, this season's start, in-season days since it)."""
    ts = pd.Timestamp(today)
    in_season = bool(cal.is_in_season(ts))
    season = cal.season_of(ts)
    start = cal.season_bounds(season)[0]
    if ts < start:                                   # before opening night: last season's numbers
        start = cal.season_bounds(season - 1)[0]
    days_in = cal.inseason_days(start, ts) if in_season else None
    return in_season, start.date(), days_in


# ---------------------------------------------------------------------------
# Scored forecasts
# ---------------------------------------------------------------------------

def default_since():
    d = query('SELECT MIN(run_date) AS d FROM basketball.points_forecasts WHERE p_play IS NOT NULL')['d'].iloc[0]
    return d


def load_scored(today, since):
    lo = max(since, today - dt.timedelta(days=LOOKBACK_DAYS))
    f = query("""
        SELECT F.run_date, F.slug, F.model, F.horizon, F.game_date, F.team, F.prediction, F.lo80, F.hi80,
               F.p_play, F.expected_points, F.champion,
               R.mae, R.mae_h1, R.mae_h2, R.mae_h3, R.mae_h4, R.mae_h5
        FROM basketball.points_forecasts F
        LEFT JOIN basketball.model_runs R ON R.run_date = F.run_date AND R.slug = F.slug AND R.model = F.model
        WHERE F.run_date >= %s AND F.game_date >= %s AND F.game_date < %s;""", (since, lo, today))
    last_box = query('SELECT MAX(date) AS d FROM basketball.historical_player_data')['d'].iloc[0]
    if f.empty or last_box is None:
        return f.assign(played=pd.Series(dtype=bool)), last_box
    box = query('SELECT slug, date, team, points, seconds_played FROM basketball.historical_player_data '
                'WHERE date >= %s AND date < %s;', (lo, today))
    for c in ['prediction', 'lo80', 'hi80', 'p_play', 'expected_points', 'mae'] + [f'mae_h{h}' for h in range(1, 6)]:
        f[c] = pd.to_numeric(f[c], errors='coerce')
    box['points'] = pd.to_numeric(box['points'], errors='coerce')
    box['seconds_played'] = pd.to_numeric(box['seconds_played'], errors='coerce')

    f = f[f['game_date'] <= last_box]
    team_days = box[['team', 'date']].drop_duplicates().rename(columns={'date': 'game_date'}).assign(team_played=1)
    f = f.merge(team_days, on=['team', 'game_date'], how='inner')        # postponed / unloaded games drop out
    f = f.merge(box[['slug', 'date', 'points', 'seconds_played']].rename(columns={'date': 'game_date'}),
                on=['slug', 'game_date'], how='left')
    f['played'] = f['seconds_played'].fillna(0) > 0
    f['actual'] = np.where(f['played'], f['points'].fillna(0), 0.0)
    f = f.sort_values('run_date').drop_duplicates(['slug', 'game_date', 'model', 'horizon'], keep='last')
    h_mae = f[[f'mae_h{h}' for h in range(1, 6)]].to_numpy()
    idx = f['horizon'].astype(int).clip(1, 5).to_numpy() - 1
    f['exp'] = h_mae[np.arange(len(f)), idx]
    f['exp'] = f['exp'].fillna(f['mae'])
    f['err'] = f['prediction'] - f['actual']
    f['abs_err'] = f['err'].abs()
    f['hit'] = ((f['actual'] >= f['lo80']) & (f['actual'] <= f['hi80'])).astype(float)
    f['one'] = 1.0
    back = (pd.Timestamp(last_box) - pd.to_datetime(f['game_date'])).dt.days // 7
    f['week'] = (pd.Timestamp(last_box) - pd.to_timedelta(7 * back, unit='D')).dt.date    # the window's last day
    return f.reset_index(drop=True), last_box


def complete_weeks(f, last_box):
    """7-day windows (labelled by their last day) back from the last loaded box-score day, oldest first."""
    if f.empty:
        return []
    return sorted(f['week'].unique())


def default_model():
    d = query("""SELECT model, COUNT(*) AS n FROM basketball.model_runs
                 WHERE run_date = (SELECT MAX(run_date) FROM basketball.model_runs) AND champion = 1
                 GROUP BY model ORDER BY n DESC LIMIT 1;""")
    return d['model'].iloc[0] if len(d) else 'XGB'


# ---------------------------------------------------------------------------
# 0. Data and inputs
# ---------------------------------------------------------------------------

def psi(recent, ref):
    edges = np.unique(np.nanquantile(ref, np.linspace(0.1, 0.9, 9)))
    p = np.bincount(np.searchsorted(edges, recent, side='right'), minlength=len(edges) + 1) + 0.5
    q = np.bincount(np.searchsorted(edges, ref, side='right'), minlength=len(edges) + 1) + 0.5
    p, q = p / p.sum(), q / q.sum()
    return float(((p - q) * np.log(p / q)).sum())


def input_frame(today):
    """League-wide played games with the XGB inputs, built the way points_forecast builds them."""
    from pipeline import points_forecast as pf
    from pipeline import forecast_models as fm
    season_year = int(os.environ.get('season_year'))
    cn = pf.connect()
    try:
        box, future, _, _, _, _, episodes, status, _ = pf.load(cn, today, season_year)
    finally:
        cn.close()
    current_team = {sl: t for sl, t in zip(status['slug'], status['team']) if isinstance(t, str)}
    tg = fm.team_games(box)
    ratings = fm.team_ratings(tg)
    rest = fm.team_rest(pd.concat([tg[['team', 'date']], future[['team', 'date']]]))
    pg = fm.player_games(box, rest, ratings)
    grid = fm.player_grid(pg, fm.team_game_table(box, future), current_team, today)
    gf = fm.grid_features(grid, episodes, rest, ratings)
    pg = pg.merge(gf[['slug', 'date', 'games_since_return']], on=['slug', 'date'], how='left')
    gf, pg = fm.teammate_absence(gf, pg)
    feats = fm.origin_features(pg)
    x = pg[['date']].copy()
    for c in PSI_FEATS:
        x[c] = (pg[c] if c in pg else feats[c]).astype(float).values
    return x


def check_data_inputs(today, in_season):
    out = []

    def age_row(metric, sql, max_age, what):
        last = query(sql).iloc[0, 0]
        age = (today - pd.Timestamp(last).date()).days if last is not None else None
        status = 'info' if not in_season else ('alert' if age is None or age > max_age else 'ok')
        out.append(row('data_inputs', metric, age, max_age, status,
                       detail=f'{what}: latest {last}' + ('' if in_season else ' (offseason)')
                              + (f' ({age} days old; alert above {max_age})' if age is not None else '')))
    age_row('box_score_age_days', 'SELECT MAX(date) FROM basketball.historical_player_data', BOX_MAX_AGE, 'box scores')
    age_row('forecast_run_age_days', 'SELECT MAX(run_date) FROM basketball.points_forecasts', RUN_MAX_AGE,
            'forecast run')
    try:
        age_row('espn_snapshot_age_days', 'SELECT MAX(snapshot_date) FROM basketball.nba_injury_status',
                ESPN_MAX_AGE, 'ESPN status snapshot')
    except mysql.Error as e:
        out.append(row('data_inputs', 'espn_snapshot_age_days', status='info', detail=f'nba_injury_status: {e}'))

    sched = query('SELECT start_time FROM basketball.high_level_nba_team_schedules')
    dates = pd.to_datetime(sched['start_time'], utc=True).dt.tz_convert('US/Eastern').dt.date
    last_sched = max(dates) if len(dates) else None
    season_end = cal.season_bounds(cal.season_of(pd.Timestamp(today)))[1].date()
    need = min(today + dt.timedelta(days=7), season_end)
    short = in_season and (last_sched is None or last_sched < need)
    out.append(row('data_inputs', 'schedule_last_date', None, None, 'alert' if short else ('ok' if in_season else 'info'),
                   detail=f'schedule runs to {last_sched}' + (f'; the next 5 games need games through at least {need}'
                                                              if short else '')))

    ros = query('SELECT slug, positions FROM basketball.forecast_roster')
    miss = float((ros['positions'].fillna('') == '').mean()) if len(ros) else 0.0
    out.append(row('data_inputs', 'roster_positions_missing', miss, POS_MISSING_MAX,
                   'alert' if miss > POS_MISSING_MAX else 'ok', n=len(ros),
                   detail=f'{miss:.0%} of {len(ros)} rostered players have no ESPN position (XGB uses every '
                          f'position model for them)'))

    try:
        x = input_frame(today)
        last = x['date'].max()
        rec = x[x['date'] > last - pd.Timedelta(days=PSI_RECENT_DAYS)]
        ref = x[x['date'] <= last - pd.Timedelta(days=PSI_RECENT_DAYS)]
        for c in PSI_FEATS:
            r, q = rec[c].dropna().to_numpy(), ref[c].dropna().to_numpy()
            if len(r) < PSI_MIN_N or len(q) < 1000:
                out.append(row('data_inputs', f'psi_{c}', status='info', n=len(r),
                               detail=f'{c}: {len(r)} recent player-games, too few to compare'))
                continue
            v = psi(r, q)
            out.append(row('data_inputs', f'psi_{c}', v, PSI_MAX, 'alert' if v > PSI_MAX else 'ok', n=len(r),
                           detail=f'{c}: PSI {v:.3f} over the last {PSI_RECENT_DAYS} days ({len(r):,} player-games, '
                                  f'mean {r.mean():.2f}) vs the {len(q):,} before (mean {q.mean():.2f}); '
                                  f'alert above {PSI_MAX}'))
    except Exception as e:                               # the input check must never sink the others
        out.append(row('data_inputs', 'psi', status='info', detail=f'input drift not computed: {type(e).__name__}: {e}'))
    return out


# ---------------------------------------------------------------------------
# 1-3. Live vs backtest, bias, coverage (per model, per week)
# ---------------------------------------------------------------------------

def _weekly(d, weeks, cols, stat):
    return [(w, *boot(d[d['week'] == w], cols, stat)) for w in weeks]


def check_live_vs_backtest(f, weeks, since):
    p = f[f['played']]
    if not weeks:
        return [row('live_vs_backtest', 'scored_weeks', 0, None, 'info', n=p[['slug', 'game_date']].drop_duplicates().shape[0],
                    detail=f'collecting data: no week of scored forecasts from runs since {since} yet')]
    key = ['run_date', 'slug', 'horizon', 'game_date', 'week']
    L = p.pivot_table(index=key, columns='model', values='abs_err')
    E = p.pivot_table(index=key, columns='model', values='exp')
    last2 = weeks[-2:]
    out = [row('live_vs_backtest', 'scored_weeks', len(weeks), None, 'info',
               n=p[p['week'].isin(weeks)][['slug', 'game_date']].drop_duplicates().shape[0],
               detail=f'{len(weeks)} complete week(s) scored (games played, runs since {since}); '
                      f'latest week to {day(weeks[-1])}')]
    if REF not in L:
        return out
    for m in [c for c in L.columns if c != REF]:
        ok = L[m].notna() & L[REF].notna() & E[m].notna() & E[REF].notna()
        d = pd.DataFrame({'Em': E[m], 'En': E[REF], 'Lm': L[m], 'Ln': L[REF]})[ok].reset_index()
        # gap = live skill - backtest skill = (1 - Lm/Ln) - (1 - Em/En)
        res = _weekly(d, last2, ['Em', 'En', 'Lm', 'Ln'], lambda Em, En, Lm, Ln: Em / En - Lm / Ln)
        bad = [n >= MIN_WEEK_N and g < -SKILL_GAP and hi < 0 for _, g, _, hi, n in res]
        alert = len(res) == 2 and all(bad)
        w, g, lo, hi, n = res[-1]
        dw = d[d['week'] == w]
        live_sk, bt_sk = 1 - dw['Lm'].sum() / dw['Ln'].sum(), 1 - dw['Em'].sum() / dw['En'].sum()
        ratio = dw['Lm'].sum() / dw['Em'].sum()
        prev = f'; week to {day(res[0][0])}: gap {res[0][1]:+.2f} ({res[0][4]})' if len(res) == 2 else ''
        status = 'alert' if alert else ('ok' if n >= MIN_WEEK_N else 'info')
        out.append(row('live_vs_backtest', 'skill_gap', g, -SKILL_GAP, status, n=n, unit=m,
                       detail=f'week to {day(w)}: live skill {pct(live_sk, True)} vs backtest {pct(bt_sk, True)} '
                              f'(gap {g:+.2f}, 95% CI {lo:+.2f} to {hi:+.2f}, {n} player-games); live MAE '
                              f'{dw["Lm"].mean():.2f} vs backtest {dw["Em"].mean():.2f} (x{ratio:.2f}){prev}'))
    d = pd.DataFrame({'Ln': L[REF], 'En': E[REF]}).dropna().reset_index()
    dw = d[d['week'] == weeks[-1]]
    if len(dw):
        out.append(row('live_vs_backtest', 'mae_ratio', dw['Ln'].sum() / dw['En'].sum(), None, 'info', unit=REF,
                       n=dw[['slug', 'game_date']].drop_duplicates().shape[0],
                       detail=f'week to {day(weeks[-1])}: the reference (last game) live MAE {dw["Ln"].mean():.2f} vs '
                              f'backtest {dw["En"].mean():.2f}; a hard week for every model shows up here, not as drift'))
    return out


def check_bias(f, weeks):
    p = f[f['played']]
    if not weeks:
        return [row('bias', 'bias', status='info', detail='collecting data')]
    out = []
    for m, d in p.groupby('model'):
        res = _weekly(d, weeks[-2:], ['err', 'one'], lambda e, o: e / o)
        bad = [n >= MIN_WEEK_N and abs(b) > BIAS_MAX and (lo > 0 or hi < 0) for _, b, lo, hi, n in res]
        same_side = len({np.sign(b) for _, b, _, _, _ in res}) == 1
        alert = len(res) == 2 and all(bad) and same_side
        w, b, lo, hi, n = res[-1]
        prev = f'; week to {day(res[0][0])}: {res[0][1]:+.2f}' if len(res) == 2 else ''
        out.append(row('bias', 'bias', b, BIAS_MAX, 'alert' if alert else ('ok' if n >= MIN_WEEK_N else 'info'),
                       n=n, unit=m, detail=f'week to {day(w)}: forecast - points {b:+.2f} (95% CI {lo:+.2f} to '
                                           f'{hi:+.2f}, {n} player-games; + = too high){prev}'))
    return out


def check_coverage(f, weeks):
    p = f[f['played'] & f['lo80'].notna()]
    if not weeks:
        return [row('coverage', 'coverage80', status='info', detail='collecting data')]
    out = []
    for m, d in p.groupby('model'):
        res = [(w, dw['hit'].mean(), dw[['slug', 'game_date']].drop_duplicates().shape[0])
               for w in weeks[-2:] for dw in [d[d['week'] == w]] if len(dw)]
        if not res:
            continue
        bad = [n >= MIN_WEEK_N and not (COV_LO <= c <= COV_HI) for _, c, n in res]
        alert = len(res) == 2 and all(bad)
        w, c, n = res[-1]
        prev = f'; week to {day(res[0][0])}: {res[0][1]:.0%}' if len(res) == 2 else ''
        out.append(row('coverage', 'coverage80', c, None, 'alert' if alert else ('ok' if n >= MIN_WEEK_N else 'info'),
                       n=n, unit=m, detail=f'week to {day(w)}: {c:.0%} of games played inside the 80% range '
                                           f'(alert outside {COV_LO:.0%}-{COV_HI:.0%}){prev}'))
    return out


# ---------------------------------------------------------------------------
# 4. Ranking: the roster default against every other model, paired
# ---------------------------------------------------------------------------

def check_ranking(f, weeks, default):
    p = f[f['played']]
    if len(weeks) < 1 or default not in set(p['model']):
        return [row('ranking', 'default_model', status='info', unit=default,
                    detail=f'roster default {default} (most players\' champion); collecting data')]
    use = weeks[-RANK_WEEKS:]
    cm = p[p['week'].isin(use)].groupby(['week', 'slug', 'game_date', 'model'])['abs_err'].mean().unstack('model')
    challengers = [m for m in cm.columns if m != default]
    alpha = RANK_ALPHA / max(len(challengers), 1)
    out = [row('ranking', 'default_model', None, None, 'info', unit=default,
               detail=f'roster default {default} (most players\' champion); each model must beat it at '
                      f'p < {alpha:.4f} in each of the last {RANK_WEEKS} weeks to alert')]
    for m in challengers:
        ps, wins = [], 0
        for w in use:
            d = cm.loc[w][[default, m]].dropna() if w in cm.index.get_level_values(0) else pd.DataFrame()
            if len(d) < MIN_WEEK_N:
                ps.append(np.nan)
                continue
            diff = (d[default] - d[m]).to_numpy()            # > 0: the challenger was closer
            sd = diff.std(ddof=1)
            z = diff.mean() / (sd / math.sqrt(len(diff))) if sd > 0 else 0.0
            pv = 0.5 * math.erfc(z / math.sqrt(2))
            ps.append(pv)
            wins += pv < alpha
        alert = len(use) == RANK_WEEKS and wins == RANK_WEEKS
        sub = p[p['week'].isin(use)]
        mae_m, mae_d = sub.loc[sub['model'] == m, 'abs_err'].mean(), sub.loc[sub['model'] == default, 'abs_err'].mean()
        out.append(row('ranking', 'beats_default_weeks', wins, RANK_WEEKS, 'alert' if alert else 'ok',
                       n=int(cm[m].notna().sum()), unit=m,
                       detail=f'beat {default} in {wins} of the last {len(use)} week(s) (p '
                              + ', '.join('–' if not np.isfinite(x) else f'{x:.3f}' for x in ps)
                              + f'); live MAE {mae_m:.2f} vs {mae_d:.2f}'))
    return out


# ---------------------------------------------------------------------------
# 5. Chance of playing
# ---------------------------------------------------------------------------

def check_playing_time(f, last_box):
    c = f[(f['champion'] == 1) & f['p_play'].notna()]
    if c.empty:
        return [row('playing_time', 'brier', status='info', detail='collecting data: no scored forecasts with p_play yet')]
    out = []
    c14 = c[c['game_date'] > last_box - dt.timedelta(days=PLAY_DAYS)]
    y, pp = c14['played'].astype(float).to_numpy(), c14['p_play'].to_numpy()
    n = len(c14)
    enough = n >= MIN_PLAY_N
    if n:
        brier, base = float(np.mean((pp - y) ** 2)), float(np.mean((y.mean() - y) ** 2))
        out.append(row('playing_time', 'brier', brier, BRIER_MAX, 'alert' if enough and brier > BRIER_MAX else
                       ('ok' if enough else 'info'), n=n,
                       detail=f'last {PLAY_DAYS} days: Brier {brier:.3f} on {n} forecast-games (played {y.mean():.0%}; '
                              f'a flat {y.mean():.0%} would score {base:.3f}; backtest 0.110; alert above {BRIER_MAX})'))
        bands = pd.cut(pp, [0, .25, .5, .75, .9, 1.0001], right=False,
                       labels=['<25%', '25-50%', '50-75%', '75-90%', '90%+'])
        tab = pd.DataFrame({'band': bands, 'p': pp, 'y': y}).groupby('band').agg(n=('y', 'size'), p=('p', 'mean'),
                                                                                  y=('y', 'mean'))
        tab = tab[tab['n'] > 0]
        judged = tab[tab['n'] >= MIN_BAND_N]
        gap = float((judged['y'] - judged['p']).abs().max()) if len(judged) else np.nan
        out.append(row('playing_time', 'calibration_max_gap', gap, CAL_GAP,
                       'alert' if np.isfinite(gap) and gap > CAL_GAP else ('ok' if len(judged) else 'info'), n=n,
                       detail='said vs played: ' + '; '.join(f'{b} {r.p:.0%} vs {r.y:.0%} ({int(r.n)})'
                                                             for b, r in tab.iterrows())
                              + f' (alert when a band with {MIN_BAND_N}+ is {CAL_GAP:.0%} off)'))
        e_exp = np.abs(c14['actual'] - c14['expected_points']).mean()
        e_all = np.abs(c14['actual'] - c14['prediction']).mean()
        out.append(row('playing_time', 'expected_vs_assume_plays', e_exp / e_all if e_all else np.nan, 1.0,
                       'alert' if enough and e_exp >= e_all else ('ok' if enough else 'info'), n=n,
                       detail=f'every team game, a missed game = 0: expected points MAE {e_exp:.2f} vs assuming he '
                              f'plays {e_all:.2f} (backtest 6.67 vs 6.82); alert when p_play stops helping'))
    try:
        st = query('SELECT slug, snapshot_date, injury_status FROM basketball.nba_injury_status '
                   'WHERE snapshot_date >= %s AND slug IS NOT NULL',
                   (last_box - dt.timedelta(days=STATUS_DAYS + 7),)).drop_duplicates(['slug', 'snapshot_date'])
    except mysql.Error:
        st = pd.DataFrame(columns=['slug', 'snapshot_date', 'injury_status'])
    g1 = c[(c['horizon'] == 1) & (c['game_date'] > last_box - dt.timedelta(days=STATUS_DAYS))]
    g1 = g1.merge(st.rename(columns={'snapshot_date': 'run_date'}), on=['slug', 'run_date'], how='inner')
    g1['grp'] = g1['injury_status'].map({'OUT': 'OUT', 'SUSPENSION': 'OUT', 'DAY_TO_DAY': 'DAY_TO_DAY'})
    for grp in ['OUT', 'DAY_TO_DAY']:
        d = g1[g1['grp'] == grp]
        if d.empty:
            out.append(row('playing_time', 'status_played_gap', status='info', unit=grp, n=0,
                           detail=f'no game-1 forecasts for players ESPN listed {grp} in the last {STATUS_DAYS} days'))
            continue
        obs, said = float(d['played'].mean()), float(d['p_play'].mean())
        judged = len(d) >= MIN_STATUS_N
        out.append(row('playing_time', 'status_played_gap', obs - said, CAP_GAP,
                       'alert' if judged and abs(obs - said) > CAP_GAP else ('ok' if judged else 'info'),
                       n=len(d), unit=grp,
                       detail=f'ESPN {grp} on the run date, game 1 ({STATUS_DAYS} days): played {obs:.0%} vs p_play '
                              f'{said:.0%} on average, {len(d)} games ({HISTORIC_CAPS})'))
    return out


# ---------------------------------------------------------------------------
# 6. Season-start segments
# ---------------------------------------------------------------------------

def check_season_start(f, today, in_season, start, days_in):
    head = row('season_start', 'in_season_day', days_in, SEASON_START_ALERT_DAYS, 'info',
               detail=(f'in-season day {days_in} (season started {start}): checks run nightly through day '
                       f'{SEASON_START_DAYS}, segment alerts through day {SEASON_START_ALERT_DAYS}')
               if in_season else 'offseason')
    c = f[(f['champion'] == 1) & f['played'] & (pd.to_datetime(f['game_date']) >= pd.Timestamp(start))]
    if c.empty:
        return [head]
    prev_start = cal.season_bounds(cal.season_of(pd.Timestamp(start)) - 1)[0].date()
    slugs = sorted(c['slug'].unique())
    ph = ', '.join(['%s'] * len(slugs))
    hist = query(f'SELECT slug, date, team FROM basketball.historical_player_data WHERE slug IN ({ph}) '
                 f'AND date >= %s AND seconds_played > 0 ORDER BY date', (*slugs, prev_start))
    last_season = hist[hist['date'] < start]
    last_team = last_season.groupby('slug')['team'].last()
    this = hist[hist['date'] >= start]
    c = c.copy()
    c['no_last_season'] = ~c['slug'].isin(last_team.index)
    c['new_team'] = c['slug'].map(last_team).notna() & (c['slug'].map(last_team) != c['team'])
    games_before = [int(((this['slug'] == s) & (this['date'] < g)).sum()) for s, g in zip(c['slug'], c['game_date'])]
    c['few_games'] = np.array(games_before) < 10
    c['everyone_else'] = ~(c['no_last_season'] | c['new_team'] | c['few_games'])
    labels = {'no_last_season': 'no games last season', 'new_team': 'on a new team since last season',
              'few_games': 'fewer than 10 games this season', 'everyone_else': 'everyone else'}
    may_alert = in_season and days_in is not None and days_in <= SEASON_START_ALERT_DAYS
    out = [head]
    for seg, label in labels.items():
        d = c[c[seg]]
        if d.empty:
            continue
        r, lo, hi, n = boot(d, ['abs_err', 'exp'], lambda a, e: a / e)
        alert = may_alert and n >= SEG_MIN_N and r > SEG_RATIO and lo > 1
        out.append(row('season_start', 'mae_ratio', r, SEG_RATIO, 'alert' if alert else 'info', n=n, unit=seg,
                       detail=f'{label}: champion live MAE {d["abs_err"].mean():.2f} vs backtest {d["exp"].mean():.2f} '
                              f'(x{r:.2f}, 95% CI {lo:.2f}-{hi:.2f}, {n} player-games since {start})'))
    return out


# ---------------------------------------------------------------------------
# Store + summary
# ---------------------------------------------------------------------------

def write(rows, today):
    cn = mysql.connect(**config)
    cur = cn.cursor()
    try:
        cur.execute('DELETE FROM basketball.forecast_model_monitoring WHERE run_date = %s;', (today,))
        cur.executemany(f'INSERT INTO basketball.forecast_model_monitoring ({", ".join(COLS)}) '
                        f'VALUES ({", ".join(["%s"] * len(COLS))});',
                        [tuple(today if c == 'run_date' else r[c] for c in COLS) for r in rows])
        cn.commit()
    except Exception:
        cn.rollback()
        raise
    finally:
        cur.close()
        cn.close()
    print(f'basketball.forecast_model_monitoring: {len(rows)} rows for {today}')


def summarize(rows, run_date, today, every_days):
    """Markdown 'model health' block, plus ::warning:: annotations under GitHub Actions."""
    default = next((r['unit'] for r in rows if r['check_name'] == 'ranking' and r['metric'] == 'default_model'), None)
    lines = ['### Model health: points forecasts', '',
             f'Checks run {run_date} (next {run_date + dt.timedelta(days=every_days) if run_date else today}) · '
             f'roster default {default or "?"}', '', '| Check | Status | Detail |', '|---|---|---|']
    lead = {'data_inputs': ('', 'box_score_age_days'), 'live_vs_backtest': (default, 'skill_gap'),
            'bias': (default, 'bias'), 'coverage': (default, 'coverage80'), 'ranking': (default, 'default_model'),
            'playing_time': ('', 'brier'), 'season_start': ('', 'in_season_day')}
    alerts = []
    for key, title in CHECKS:
        rs = [r for r in rows if r['check_name'] == key]
        bad = [r for r in rs if r['status'] == 'alert']
        alerts += [(title, r) for r in bad]
        if not rs:
            status, detail = '➖ not run', ''
        elif bad:
            status = f'⚠️ {len(bad)} alert{"s" if len(bad) > 1 else ""}'
            detail = '; '.join(f'{r["unit"] + " " if r["unit"] else ""}{r["metric"]}: {r["detail"]}' for r in bad[:3])
        else:
            status = '✅ ok' if any(r['status'] == 'ok' for r in rs) else 'ℹ️ info'
            u, m = lead[key]
            first = next((r for r in rs if r['metric'] == m and r['unit'] == (u or '')), None) \
                or next((r for r in rs if r['metric'] == m), rs[0])
            detail = (f'{first["unit"]}: ' if first['unit'] and key != 'ranking' else '') + first['detail']
        lines.append(f'| {title} | {status} | {str(detail).replace("|", "/")} |')
    if alerts:
        lines += ['', '**Alerts**', ''] + [f'- {t} · {r["unit"] + " · " if r["unit"] else ""}{r["metric"]}: '
                                          f'{r["detail"]}' for t, r in alerts]
    md = '\n'.join(lines) + '\n'
    print('\n' + md)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as fh:
            fh.write(md)
    if os.environ.get('GITHUB_ACTIONS') == 'true':
        esc = lambda s: s.replace('%', '%25').replace('\r', '%0D').replace('\n', '%0A')
        for t, r in alerts[:10]:
            print(f'::warning title=Points model health ({t})::'
                  + esc(f'{r["unit"] + " · " if r["unit"] else ""}{r["metric"]}: {r["detail"]}'))
        if len(alerts) > 10:
            print(f'::warning title=Points model health::{len(alerts) - 10} more alerts in the run summary')


def run_checks(today, since):
    in_season, start, days_in = season_info(today)
    f, last_box = load_scored(today, since)
    weeks = complete_weeks(f, last_box) if last_box is not None else []
    default = default_model()
    n_games = f[f['played']][['slug', 'game_date']].drop_duplicates().shape[0] if len(f) else 0
    print(f'{len(f):,} scored forecast rows ({n_games} player-games played) from runs since {since}; box scores '
          f'through {last_box}; {len(weeks)} complete week(s); default {default}')
    rows = check_data_inputs(today, in_season)
    if len(f):
        rows += (check_live_vs_backtest(f, weeks, since) + check_bias(f, weeks) + check_coverage(f, weeks)
                 + check_ranking(f, weeks, default) + check_playing_time(f, last_box)
                 + check_season_start(f, today, in_season, start, days_in))
    else:
        wait = f'collecting data: no forecast from runs since {since} has been played yet'
        rows += [row('live_vs_backtest', 'scored_weeks', 0, None, 'info', detail=wait),
                 row('bias', 'bias', status='info', detail=wait),
                 row('coverage', 'coverage80', status='info', detail=wait),
                 row('ranking', 'default_model', status='info', unit=default,
                     detail=f'roster default {default} (most players\' champion); {wait}'),
                 row('playing_time', 'brier', status='info', detail=wait)]
        rows += check_season_start(f, today, in_season, start, days_in)
    return rows


def cadence(today):
    in_season, _, days_in = season_info(today)
    return 1 if in_season and days_in is not None and days_in <= SEASON_START_DAYS else EVERY_DAYS


def main():
    ap = argparse.ArgumentParser(description='Live drift checks for the points forecasts')
    ap.add_argument('--force', action='store_true', help='run the checks even if they are not due')
    ap.add_argument('--dry-run', action='store_true', help='run the checks, print them, write nothing')
    ap.add_argument('--summary-only', action='store_true', help='only print the latest stored results')
    ap.add_argument('--since', help='score forecasts from runs on or after this date (default: first run with p_play)')
    args = ap.parse_args()
    today = dt.date.today()
    every = cadence(today)

    try:
        last = query('SELECT MAX(run_date) AS d FROM basketball.forecast_model_monitoring')['d'].iloc[0]
    except mysql.Error as e:
        print(f'forecast_model_monitoring not available ({e}); run '
              'sql_files/migrations/2026-11-22_forecast_model_monitoring.sql once.')
        if not args.dry_run:
            return 0
        last = None
    due = last is None or (today - last).days >= every
    if not (args.summary_only or (not args.force and not args.dry_run and not due)):
        since = pd.Timestamp(args.since).date() if args.since else default_since()
        if since is None:
            print('no forecast run with p_play yet: nothing to score (use --since to score older runs)')
            since = today
        rows = run_checks(today, since)
        if args.dry_run:
            summarize(rows, today, today, every)
            print('dry run: nothing written')
            return 0
        write(rows, today)
    elif not args.summary_only:
        print(f'checks last ran {last}; next run due {last + dt.timedelta(days=every)} (use --force to run now)')

    stored = query('SELECT * FROM basketball.forecast_model_monitoring WHERE run_date = '
                   '(SELECT MAX(run_date) FROM basketball.forecast_model_monitoring)')
    if stored.empty:
        print('no monitoring results stored yet')
        return 0
    rows = [{k: (None if isinstance(v, float) and np.isnan(v) else v) for k, v in r.items()}
            for r in stored.to_dict('records')]
    summarize(rows, stored['run_date'].iloc[0], today, every)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
