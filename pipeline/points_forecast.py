"""
Next-5-games points forecasts for my ESPN and Yahoo players -> basketball.forecast_roster,
points_forecasts, model_runs, and a local MLflow tracking store (mlflow/ at the repo root).

Replaces base_model.py + machine_learning_models.py + model_pooling.py. Models, inputs, backtest and
champion rules are documented in pipeline/forecast_models.py.

Steps
    1. Read league-wide box scores (3 seasons + this one), my rosters, ESPN positions, the schedule.
    2. Build team rest, opponent defence/pace (rolling, as of each date) and per-game inputs.
    3. Per rostered player: rolling-origin backtest of every statistical model, then a final fit and
       a forecast of the team's next 5 games (parallel across players).
    4. XGBoost per position group (PG/SG/SF/PF/C): backtest models at up to 3 cutoffs (each player scored
       by the newest one that is safe for them), and a final model on everything (logged + registered).
    4b. TFT and DeepAR per position group (pipeline/deep_models.py), same cutoffs and origins. Their
       models are cached in mlflow/deep_cache/ and retrained weekly; other days they only predict.
    5. Roster default model, per-player champion (Diebold-Mariano), 80% ranges: backtest errors, or
       TFT / DeepAR's own quantiles when those cover 70-90% of backtest actuals.
    6. Write this run's rows (DELETE + INSERT for today's run_date, one transaction) and log to MLflow.

Needs sql_files/migrations/2026-11-11_points_forecasts.sql run once. Run pipeline.historicals first
so last night's games are in.

Run from the repo root, in basketball-env-useme-v11052026:
    python -m pipeline.points_forecast                    # full run
    python -m pipeline.points_forecast --dry-run          # no DB writes, no MLflow
    python -m pipeline.points_forecast --players brownja02,adebaba01 --dry-run
    python -m pipeline.points_forecast --deep retrain     # force TFT/DeepAR retraining (~1 h); --deep skip leaves them out
    mlflow ui --backend-store-uri sqlite:///mlflow/mlflow.db     # browse runs at http://127.0.0.1:5000
"""
import argparse
import ast
import datetime as dt
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import mysql.connector as mysql
from joblib import Parallel, delayed

from pipeline import forecast_models as fm
from pipeline.free_agents_backfill import match_slugs
from shared import season_calendar
from shared.my_functions import name_key

REPO_ROOT = Path(__file__).resolve().parents[1]
MLFLOW_DIR = REPO_ROOT / 'mlflow'
EXPERIMENT = 'points_forecast'
STAT_MIN_GAMES = 30      # fewer games than this since last season's start -> use the whole 3-season window

FC_COLS = ['run_date', 'slug', 'model', 'horizon', 'game_date', 'team', 'opponent', 'home', 'rest_days',
           'opp_def_rank', 'prediction', 'lo80', 'hi80', 'p_play', 'expected_points', 'play_note', 'champion']
RUN_COLS = ['run_date', 'slug', 'model', 'label', 'family', 'params', 'n_games', 'n_origins', 'mae', 'mae_h1',
            'mae_h2', 'mae_h3', 'mae_h4', 'mae_h5', 'skill', 'aicc', 'ljung_box_p', 'champion',
            'champion_reason', 'mlflow_run_id']
ROSTER_COLS = ['league', 'name', 'slug', 'positions', 'team', 'injury_status', 'run_date']


def connect():
    return mysql.connect(host=os.environ.get('sports_db_admin_host'), user=os.environ.get('sports_db_admin_user'),
                         password=os.environ.get('sports_db_admin_pw'), port=os.environ.get('sports_db_admin_port'),
                         database='basketball')


def query(cn, sql, params=()):
    cur = cn.cursor()
    cur.execute(sql, params)
    df = pd.DataFrame(cur.fetchall(), columns=cur.column_names)
    cur.close()
    return df


####################################################################################################
# 001 - LOAD
####################################################################################################

def load(cn, today, season_year):
    train_start = season_calendar.season_bounds(season_year - 3)[0].date()
    box = query(cn, """
        SELECT slug, name, date, team, opponent, location, seconds_played,
               attempted_field_goals AS fga, attempted_free_throws AS fta,
               attempted_three_point_field_goals AS fg3a, turnovers AS tov, offensive_rebounds AS orb, points
        FROM basketball.historical_player_data WHERE date >= %s AND date < %s;""", (train_start, today))
    box['date'] = pd.to_datetime(box['date'])
    for c in ['seconds_played', 'fga', 'fta', 'fg3a', 'tov', 'orb', 'points']:
        box[c] = box[c].astype(float)
    box['minutes'] = box['seconds_played'] / 60
    box['home'] = (box['location'] == 'Location.HOME').astype(float)
    box = box[season_calendar.is_in_season(box['date'])].copy()          # regular season only
    box['season'] = season_calendar.season_of(box['date'])

    sched = query(cn, 'SELECT start_time, away_team, home_team FROM basketball.high_level_nba_team_schedules;')
    sched['date'] = (pd.to_datetime(sched['start_time'], utc=True).dt.tz_convert('US/Eastern')
                     .dt.tz_localize(None).dt.normalize())
    sched = sched[sched['date'] >= pd.Timestamp(today)]
    future = pd.concat([
        sched.assign(team=sched['home_team'], opponent=sched['away_team'], home=1.0),
        sched.assign(team=sched['away_team'], opponent=sched['home_team'], home=0.0)])[['date', 'team', 'opponent', 'home']]

    rosters = []
    for league, table in [('espn', 'live_espn_players'), ('yahoo', 'live_yahoo_players')]:
        try:
            r = query(cn, f'SELECT name, injury_status FROM basketball.{table};')
        except mysql.Error:
            r = query(cn, f'SELECT name FROM basketball.{table};').assign(injury_status=None)
        rosters.append(r.assign(league=league))
    roster = pd.concat(rosters, ignore_index=True)
    positions = query(cn, 'SELECT player_name, player_roles FROM basketball.espn_player_positions;')
    crosswalk = query(cn, 'SELECT full_name, bbrefid FROM basketball.master_names_list_temp;')
    episodes = query(cn, """
        SELECT slug, player_name, start_date, end_date, end_reason, category, curve_group, is_dtd, out_for_season,
               out_indefinitely, stated_days
        FROM basketball.player_injury_cycles WHERE slug IS NOT NULL AND start_date >= %s;""",
                     (train_start - dt.timedelta(days=365),))
    for c in ['start_date', 'end_date']:
        episodes[c] = pd.to_datetime(episodes[c])
    try:                       # today's ESPN snapshot (pipeline/espn_player_positions.py); latest day if not today
        status = query(cn, """SELECT slug, team, injury_status, snapshot_date FROM basketball.nba_injury_status
                               WHERE snapshot_date = (SELECT MAX(snapshot_date) FROM basketball.nba_injury_status)
                                 AND slug IS NOT NULL;""")
        curves = query(cn, 'SELECT slug, start_date, days, probabilities FROM basketball.injury_player_curves;')
    except mysql.Error:        # before sql_files/migrations/2026-11-21_forecast_inputs.sql
        status = pd.DataFrame(columns=['slug', 'team', 'injury_status', 'snapshot_date'])
        curves = pd.DataFrame(columns=['slug', 'start_date', 'days', 'probabilities'])
    if len(status) and (today - pd.Timestamp(status['snapshot_date'].iloc[0]).date()).days > 1:
        status = status.iloc[0:0]  # a stale snapshot says nothing about today: no status adjustment
    status = status.drop_duplicates('slug')
    curves['start_date'] = pd.to_datetime(curves['start_date'])
    curves['probabilities'] = curves['probabilities'].astype(float)
    return box, future, roster, positions, crosswalk, train_start, episodes, status, curves


def resolve_roster(roster, box, crosswalk):
    """live_*_players names -> slugs (same matching as free_agents_backfill), latest-played slug wins."""
    names = box.sort_values('date').drop_duplicates('slug', keep='last')[['name', 'slug', 'date']]
    pairs, unmatched, _ = match_slugs(sorted(roster['name'].unique()), names[['name', 'slug']], crosswalk)
    last = names.set_index('slug')['date']
    best = {}
    for n, s in pairs:
        if s in last.index and (n not in best or last[s] > last[best[n]]):
            best[n] = s
    out = roster.assign(slug=roster['name'].map(best))
    missing = sorted(set(out.loc[out['slug'].isna(), 'name']))
    return out[out['slug'].notna()].copy(), missing


def position_groups(positions, box):
    """slug -> set of PG/SG/SF/PF/C from ESPN eligibility (name_key match, unique only)."""
    by_key = {}
    for n, s in box[['name', 'slug']].drop_duplicates().itertuples(index=False):
        by_key.setdefault(name_key(n), set()).add(s)
    out = {}
    for n, roles in positions.itertuples(index=False):
        slugs = by_key.get(name_key(n), set())
        if len(slugs) != 1:
            continue
        try:
            groups = {r for r in ast.literal_eval(roles) if r in fm.POSITIONS}   # a Python list literal
        except Exception:
            continue
        if groups:
            out[next(iter(slugs))] = groups
    return out


####################################################################################################
# 002 - PER-PLAYER INPUTS
####################################################################################################

def future_rows(team, df, future, rest, ratings, today, opp_rank, out_now=None):
    """The team's next H scheduled games with their inputs. `team` is today's ESPN team when known (a player
    traded since his last game gets his new team's schedule), else the team of his latest game. out_now:
    forecast_models.teammates_out_now(); tm_out_usg is today's value carried to all H games."""
    f = future[future['team'] == team].sort_values('date').head(fm.H).reset_index(drop=True)
    if f.empty:
        return f
    f = f.merge(rest, on=['team', 'date'], how='left')
    f['rest'] = f['rest'].fillna(fm.REST_CAP)
    f['b2b'] = (f['rest'] == 0).astype(float)
    r = fm.ratings_asof(ratings, f['opponent'], [pd.Timestamp(today)] * len(f))
    f['opp_def'], f['opp_pace'] = r['opp_def'].values, r['opp_pace'].values
    f['h'] = np.arange(1, len(f) + 1)
    m = df['min_ewm'].values
    f['min_lag5'] = [fm.min_lag5_at(m, len(df) - 1, h) for h in f['h']]
    f['days_ahead'] = (f['date'] - df['date'].iloc[-1]).dt.days
    f['moved'] = team != df['team'].iloc[-1]          # on a new team since his last game
    me = df['slug'].iloc[-1]
    f['tm_out_usg'] = sum(v for s, v in (out_now or {}).get(team, {}).items() if s != me)
    f['opp_def_rank'] = f['opponent'].map(opp_rank)
    return f


def player_frame(pg, slug, stat_start):
    d = pg[pg['slug'] == slug]
    recent = d[d['date'] >= pd.Timestamp(stat_start)]
    return (recent if len(recent) >= STAT_MIN_GAMES else d).reset_index(drop=True)


####################################################################################################
# 003 - XGBOOST BY POSITION
####################################################################################################

def xgb_backtest_and_fit(pg, feats, ratings, gf, groups, roster_frames, roster_groups, fut_by_slug, needed, cutoffs,
                         log):
    """Per position: one backtest model per cutoff in use (each player scored by the newest one that is safe
    for them, see forecast_models.backtest_cutoffs) and a final model on everything. Trained on target games
    played; backtest predictions are kept for every team game (expected-points score)."""
    all_rows = fm.xgb_training_rows(pg, feats, ratings, gf)
    all_rows = all_rows[np.isfinite(all_rows['days_ahead'])]
    rows = all_rows[all_rows['played'] == 1]
    log(f'XGB: {len(rows):,} training rows; backtest cutoffs {", ".join(str(c.date()) for c in cutoffs)}')
    last_feat = feats.groupby(pg['slug']).tail(1).assign(slug=pg['slug'])
    last_feat = last_feat.set_index('slug')

    bt_pred, bt_all, final_pred, models, infos = {}, {}, {}, {}, {}
    for pos in fm.POSITIONS:
        members = {s for s, g in groups.items() if pos in g}
        grp = rows[rows['slug'].isin(members)]
        need = [s for s, g in roster_groups.items() if pos in g]
        if len(grp) < 2000:
            log(f'  {pos}: only {len(grp)} rows, skipped')
            continue
        t0 = time.time()
        bt_models = {c: fm.fit_xgb(grp[grp['target_date'] <= c])[0]
                     for c in {fm.newest_cutoff(needed.get(s), cutoffs) for s in need} - {None}}
        model, info = fm.fit_xgb(grp)
        info.update(n_players=len(members), backtest_cutoffs=','.join(str(c.date()) for c in sorted(bt_models)))
        models[pos], infos[pos] = model, info
        log(f'  {pos}: {len(members)} players, {info["n_train"]:,} rows, val MAE {info["val_mae"]:.2f}, '
            f'{time.time() - t0:.0f}s')
        for slug in need:
            df = roster_frames[slug]
            origins = fm.origins_for(len(df))
            bt_model = bt_models.get(fm.newest_cutoff(needed.get(slug), cutoffs))
            if origins and bt_model is not None:
                o_dates = df['date'].iloc[[o - 1 for o in origins]].values
                ev = all_rows[(all_rows['slug'] == slug) & all_rows['origin_date'].isin(o_dates)]
                if not ev.empty:
                    k = pd.Series(range(len(origins)), index=pd.to_datetime(o_dates))
                    e = np.full((len(origins), fm.H), np.nan)
                    a = np.full((len(origins), fm.H), np.nan)
                    p = bt_model.predict(ev[fm.XGB_FEATS].astype(float))
                    ki, hi = k[ev['origin_date']].values, ev['h'].values - 1
                    e[ki, hi] = np.where(ev['played'].values == 1, ev['target'].values - p, np.nan)
                    a[ki, hi] = p
                    bt_pred.setdefault(slug, []).append(e)
                    bt_all.setdefault(slug, []).append(a)
            fut = fut_by_slug.get(slug)
            if fut is not None and not fut.empty and slug in last_feat.index:
                X = pd.DataFrame([last_feat.loc[slug]] * len(fut)).reset_index(drop=True)
                for c in fm.TARGET_FEATS:
                    X[c] = fut[c].values
                if fut['moved'].any():                    # traded since his last game: no games on the new team
                    for c, v in fm.ROLE_RESET.items():
                        X[c] = v
                final_pred.setdefault(slug, []).append(model.predict(X[fm.XGB_FEATS].astype(float)))
    # a player in several groups gets the mean of those models (errors averaged the same way)
    errors = {s: actual_minus_mean(v) for s, v in bt_pred.items()}
    preds = {s: np.nanmean(np.stack(v), axis=0) if len(v) > 1 else v[0] for s, v in bt_all.items()}
    forecast = {s: np.mean(v, axis=0) for s, v in final_pred.items()}
    return errors, preds, forecast, models, infos


def actual_minus_mean(errs):
    """Errors are actual - pred; the mean prediction's error is the mean of the errors."""
    return np.nanmean(np.stack(errs), axis=0) if len(errs) > 1 else errs[0]


####################################################################################################
# 003b - CHANCE OF PLAYING
####################################################################################################

def _play_X(origin, targets, origin_date):
    """Feature rows for one origin (a grid row, i.e. the state after a team game) and its target games."""
    base = {c: origin[c] for c in fm.PLAY_FEATS if c not in ('h', 'days_ahead', 'b2b')}
    X = pd.DataFrame([base] * len(targets))
    X['h'] = np.arange(1, len(targets) + 1)
    X['days_ahead'] = (pd.to_datetime(targets['date']).values - np.datetime64(origin_date)) / np.timedelta64(1, 'D')
    X['b2b'] = targets['b2b'].values
    X['ep_stated_left'] = pd.to_numeric(X['ep_stated_left'], errors='coerce').fillna(-99)
    return X[fm.PLAY_FEATS].astype(float)


def play_backtest_and_fit(gf, frames, results, needed, cutoffs, log):
    """Playing-time classifier: one backtest model per cutoff in use (trained on targets on or before it, like
    XGB) predicting each roster player's backtest targets, and a final model on everything.
    -> ({slug: (n_origins, H) chance of playing}, final model, scores on the backtest targets)."""
    rows = fm.play_rows(gf)
    use = {s: fm.newest_cutoff(needed.get(s), cutoffs) for s in frames}
    t0 = time.time()
    models = {c: fm.fit_play_model(rows[rows['target_date'] <= c]) for c in set(use.values()) - {None}}
    final = fm.fit_play_model(rows)
    p_bt, ys, ps, bs = {}, [], [], []
    for s, df in frames.items():
        r, model = results.get(s), models.get(use[s])
        if r is None or model is None or not r['origins']:
            continue
        g = gf[gf['slug'] == s].reset_index(drop=True)
        P = np.full((len(r['origins']), fm.H), np.nan)
        for k, o in enumerate(r['origins']):
            d = df['date'].iloc[o - 1]
            at = g.index[g['date'] == d]
            tg = g[g['date'] > d].head(fm.H)
            if not len(at) or tg.empty:
                continue
            P[k, :len(tg)] = model.predict_proba(_play_X(g.loc[at[0]], tg, d))[:, 1]
            ys += list(tg['played'].values)
            ps += list(P[k, :len(tg)])
            bs += [g.loc[at[0], 'played10']] * len(tg)
        p_bt[s] = P
    sc = fm.play_scores(ys, ps, bs) if ys else {}
    log(f'playing-time model: {len(rows):,} rows, {len(models)} backtest models + final, {time.time() - t0:.0f}s; '
        + (f"roster backtest Brier {sc['brier']:.3f} vs {sc['brier_baseline']:.3f} (share of last 10 played), "
           f"AUC {sc['auc']:.3f}, played {sc['played_rate']:.0%} of {sc['n']} games" if sc else 'no backtest'))
    return p_bt, final, sc


EP_COLS = ['inj_open', 'nonmed_open', 'ep_days', 'ep_dtd', 'ep_out_season', 'ep_out_indef', 'has_stated',
           'ep_stated_left']


def back_by(curves, slug, start, today, dates):
    """P(back by each date | still out today) from his own curve (injury_player_curves), or None."""
    c = curves[(curves['slug'] == slug) & (curves['start_date'] == pd.Timestamp(start))]
    if c.empty:
        return None
    S = c.sort_values('days')['probabilities'].values
    clock = lambda d: float(season_calendar.clock(pd.Timestamp(d)))
    s_at = lambda t: S[int(np.clip(round(t), 0, len(S) - 1))]
    d0 = clock(today) - clock(start)
    s0 = max(s_at(d0), 1e-6)
    return np.array([1 - min(s_at(clock(d) - clock(start)) / s0, 1.0) for d in dates])


def play_forecast(model, gf, slug, fut, episodes, today, status=None, rates=None, curves=None):
    """Chance of playing each of `fut`'s games: the state after his latest team game, with the injury-episode
    inputs re-read as of today (a move logged since that game counts), then today's ESPN status:
      ACTIVE with an episode still open in our data -> the episode inputs are cleared (the transaction log lags
        a return; ESPN's list is fresher);
      OUT -> each game capped at P(back by that game) from his own survival curve, and the next game also at
        the historical OUT rate (forecast_models.status_play_rates);
      DAY_TO_DAY -> the next game capped at the historical day-to-day rate.
    -> (array, note)."""
    g = gf[gf['slug'] == slug]
    if g.empty or fut.empty:
        return np.ones(len(fut)), ''
    espn = status.get(slug) if status else None
    origin = g.iloc[-1].copy()
    st = fm.episode_state([slug], [pd.Timestamp(today)], episodes).iloc[0]
    cleared = espn == 'ACTIVE' and (st['inj_open'] == 1 or st['nonmed_open'] == 1)
    for c in EP_COLS:
        origin[c] = 0.0 if cleared else st[c]
    p = model.predict_proba(_play_X(origin, fut, origin['date']))[:, 1]
    note = ''
    if espn in fm.OUT_STATUSES and rates:
        p[0] = min(p[0], rates['OUT'])
        if st['inj_open'] == 1:
            b = back_by(curves, slug, st['ep_start'], today, fut['date']) if curves is not None else None
            if b is not None:
                p = np.minimum(p, b)
    elif espn == 'DAY_TO_DAY' and rates:
        p[0] = min(p[0], rates['DAY_TO_DAY'])
    tag = {'OUT': 'ESPN: out', 'SUSPENSION': 'ESPN: suspended', 'DAY_TO_DAY': 'ESPN: day-to-day'}.get(espn)
    if cleared:
        note = 'ESPN lists him active (return not logged yet)'
    elif st['inj_open'] == 1 or st['nonmed_open'] == 1:
        ep = episodes[(episodes['slug'] == slug) & (episodes['start_date'] == st['ep_start'])]
        what = ep['curve_group'].iloc[0] if len(ep) else 'absence'
        note = f"{'out' if st['inj_open'] == 1 else 'away'} since {pd.Timestamp(st['ep_start']):%b %-d} ({what}), " \
               f"in-season day {int(st['ep_days'])}"
    elif origin['unexpl_streak'] > 0:
        note = f"missed his last {int(origin['unexpl_streak'])} team game(s) with no injury listed"
    if tag:
        note = f'{tag} · {note}' if note else tag
    return p, note[:120]


####################################################################################################
# 004 - MLFLOW
####################################################################################################

def mlflow_setup():
    import mlflow
    MLFLOW_DIR.mkdir(exist_ok=True)
    mlflow.set_tracking_uri(f'sqlite:///{MLFLOW_DIR / "mlflow.db"}')
    if mlflow.get_experiment_by_name(EXPERIMENT) is None:
        mlflow.create_experiment(EXPERIMENT, artifact_location=(MLFLOW_DIR / 'artifacts').as_uri())
    mlflow.set_experiment(EXPERIMENT)
    # A Linux test container logged every SQLAlchemy ORM step at DEBUG once MLflow had created a new
    # mlflow.db (not reproducible on the Mac); keep the store's own loggers quiet either way.
    import logging
    for name in ('sqlalchemy', 'alembic'):
        logging.getLogger(name).setLevel(logging.WARNING)
    return mlflow


def log_deep(mlflow, deep_fitted):
    """One nested run per TFT / DeepAR position model. A model trained in this run is also logged and
    registered (points_tft_PG, …); a cached one only logs its training metadata."""
    from pipeline import deep_models as dm
    import mlflow.pytorch
    for kind, by_pos in deep_fitted.items():
        for pos, (model, meta) in by_pos.items():
            with mlflow.start_run(run_name=f'{kind.lower()}-{pos}', nested=True):
                mlflow.log_params({**dm.HPARAMS[kind], **{k: v for k, v in dm.TRAIN.items()}, 'spec': dm.SPEC,
                                   'enc_len': dm.ENC_LEN, 'known': ','.join(dm.KNOWN),
                                   'observed': ','.join(dm.OBSERVED[kind]), 'trained': meta['trained'],
                                   'trained_now': meta['trained_now'], 'last_game': meta.get('last_game')})
                mlflow.log_metrics({k: float(v) for k, v in meta.items()
                                    if isinstance(v, (int, float)) and not isinstance(v, bool)})
                if meta['trained_now']:
                    try:
                        mlflow.pytorch.log_model(model, artifact_path='model',
                                                 registered_model_name=f'points_{kind.lower()}_{pos}')
                    except Exception as e:                      # keep the checkpoint at least
                        print(f'{kind} {pos}: MLflow log_model failed ({type(e).__name__}: {e}); logging the checkpoint')
                        mlflow.log_artifact(str(dm.CACHE_DIR / f'{kind.lower()}_{pos}_final.ckpt'))


def log_mlflow(today, summary, xgb_models, xgb_infos, runs, forecasts, player_meta, deep_fitted=None):
    mlflow = mlflow_setup()
    import mlflow.xgboost
    run_ids = {}
    with mlflow.start_run(run_name=f'points-{today}') as parent:
        mlflow.log_params({'run_date': str(today), 'horizon': fm.H, 'n_origins': fm.N_ORIGINS,
                           'n_players': runs['slug'].nunique(), 'models': ','.join(fm.MODELS),
                           'roster_default': summary['default'], 'exog': ','.join(fm.EXOG)})
        mlflow.log_metrics({f'mean_skill.{m}': v for m, v in summary['mean_skill'].items()})
        mlflow.log_metrics({k: float(v) for k, v in summary.get('extra', {}).items() if np.isfinite(v)})
        mlflow.log_metrics({f'mean_mae.{m}': float(v) for m, v in
                            runs.groupby('model')['mae'].mean().dropna().items()})
        mlflow.log_text(runs.to_csv(index=False), 'model_runs.csv')
        mlflow.log_text(forecasts.to_csv(index=False), 'points_forecasts.csv')
        for pos, model in xgb_models.items():
            with mlflow.start_run(run_name=f'xgb-{pos}', nested=True):
                mlflow.log_params({k: v for k, v in fm.XGB_PARAMS.items()})
                mlflow.log_param('features', ','.join(fm.XGB_FEATS))
                mlflow.log_metrics({k: float(v) for k, v in xgb_infos[pos].items() if isinstance(v, (int, float))})
                imp = dict(zip(fm.XGB_FEATS, map(float, model.feature_importances_)))
                mlflow.log_dict(dict(sorted(imp.items(), key=lambda kv: -kv[1])), 'feature_importance.json')
                mlflow.xgboost.log_model(model, artifact_path='model', registered_model_name=f'points_xgb_{pos}')
        if deep_fitted:
            log_deep(mlflow, deep_fitted)
        for slug, g in runs.groupby('slug'):
            with mlflow.start_run(run_name=f'{player_meta.get(slug, slug)} ({slug})', nested=True) as r:
                champ = g.loc[g['champion'] == 1, 'model']
                mlflow.log_params({'slug': slug, 'champion': champ.iloc[0] if len(champ) else None,
                                   'n_games': int(g['n_games'].iloc[0])})
                mlflow.log_metrics({f'mae.{m}': float(v) for m, v in zip(g['model'], g['mae']) if pd.notna(v)})
                mlflow.log_dict({m: p for m, p in zip(g['model'], g['params'])}, 'params.json')
                run_ids[slug] = r.info.run_id
        run_ids['_parent'] = parent.info.run_id
    return run_ids


####################################################################################################
# 005 - WRITE
####################################################################################################

def write(cn, today, roster_rows, forecasts, runs):
    def values(df, cols):
        return [tuple(None if (isinstance(v, float) and not np.isfinite(v)) or v is pd.NaT or v is None
                      else (v.item() if isinstance(v, np.generic) else v) for v in r)
                for r in df[cols].itertuples(index=False)]
    try:
        cur = cn.cursor()
        cur.execute('DELETE FROM basketball.forecast_roster;')
        cur.execute('DELETE FROM basketball.points_forecasts WHERE run_date = %s;', (today,))
        cur.execute('DELETE FROM basketball.model_runs WHERE run_date = %s;', (today,))
        for table, df, cols in [('forecast_roster', roster_rows, ROSTER_COLS), ('points_forecasts', forecasts, FC_COLS),
                                ('model_runs', runs, RUN_COLS)]:
            cur.executemany(f"INSERT INTO basketball.{table} ({', '.join(cols)}) VALUES ({', '.join(['%s'] * len(cols))});",
                            values(df, cols))
        cn.commit()
        cur.close()
    except mysql.Error:
        cn.rollback()
        raise


####################################################################################################
# 006 - MAIN
####################################################################################################

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true', help='no DB writes and no MLflow logging')
    ap.add_argument('--no-mlflow', action='store_true')
    ap.add_argument('--players', help='comma-separated slugs (default: both rosters)')
    ap.add_argument('--jobs', type=int, default=-1, help='parallel workers for the per-player backtests')
    ap.add_argument('--deep', choices=['auto', 'retrain', 'load', 'skip'], default='auto',
                    help='TFT/DeepAR: auto = reuse cached models younger than a week; retrain = always; '
                         'load = reuse any cached model (still retrains on a leak); skip = leave them out')
    args = ap.parse_args()

    t_start = time.time()
    log = lambda m: print(f'[{time.time() - t_start:6.0f}s] {m}', flush=True)
    today = dt.date.today()
    season_year = int(os.environ.get('season_year'))
    stat_start = season_calendar.season_bounds(season_year - 1)[0].date()

    cn = connect()
    try:
        box, future, roster, positions, crosswalk, train_start, episodes, status, curves = load(cn, today, season_year)
        current_team = {sl: t for sl, t in zip(status['slug'], status['team']) if isinstance(t, str)}
        log(f'{len(box):,} box-score rows since {train_start}; {future["date"].nunique()} future game dates')
        roster, missing = resolve_roster(roster, box, crosswalk)
        if missing:
            log(f'roster names with no slug (skipped): {", ".join(missing)}')
        if args.players:
            roster = roster[roster['slug'].isin(args.players.split(','))]
        if roster.empty:
            sys.exit('No rostered player resolved to a slug.')

        groups = position_groups(positions, box)
        tg = fm.team_games(box)
        ratings = fm.team_ratings(tg)
        rest = fm.team_rest(pd.concat([tg[['team', 'date']], future[['team', 'date']]]))
        pg = fm.player_games(box, rest, ratings)
        grid = fm.player_grid(pg, fm.team_game_table(box, future), current_team, today)
        gf = fm.grid_features(grid, episodes, rest, ratings)
        pg = pg.merge(gf[['slug', 'date', 'games_since_return']], on=['slug', 'date'], how='left')
        gf, pg = fm.teammate_absence(gf, pg)
        out_now = fm.teammates_out_now(gf, episodes, status, current_team, today)
        log(f'teammates out today: {sum(len(v) for v in out_now.values())} players on {len(out_now)} teams')
        this = gf[season_calendar.season_of(gf['date']) == season_calendar.season_of(gf['date'].max())]
        log(f'team-game grid: {len(gf):,} rows, {1 - gf["played"].mean():.1%} missed; this season '
            + ', '.join(f'{k} {v}' for k, v in this.loc[this['played'] == 0, 'reason'].value_counts().items()))
        latest = ratings.sort_values('date').groupby('team').tail(1).set_index('team')
        opp_rank = latest['allowed_roll'].rank(ascending=False, method='min').astype(int)
        priors = fm.ppm_priors(pg, groups)
        log(f'{pg["slug"].nunique():,} players, {len(pg):,} games; positions for {len(groups):,} players')

        slugs = sorted(roster['slug'].unique())
        frames, futs, ctxs, grids = {}, {}, {}, {}
        for s in slugs:
            df = player_frame(pg, s, stat_start)
            if len(df) < 2:
                log(f'{s}: {len(df)} games, skipped')
                continue
            team = current_team.get(s) or df['team'].iloc[-1]
            if team != df['team'].iloc[-1]:
                log(f'{s}: on {team} now (last game for {df["team"].iloc[-1]}): forecasting the new team\'s schedule')
            fut = future_rows(team, df, future, rest, ratings, today, opp_rank, out_now)
            if fut.empty:
                log(f'{s}: no scheduled games, skipped')
                continue
            g = groups.get(s) or {'ALL'}
            pri = [priors[p] for p in g if p in priors] or [priors['ALL']]
            frames[s], futs[s] = df, fut
            grids[s] = gf[gf['slug'] == s].reset_index(drop=True)
            ctxs[s] = {'ppm_prior': (float(np.mean([p[0] for p in pri])), float(np.mean([p[1] for p in pri])))}
        roster_groups = {s: groups.get(s, set(fm.POSITIONS)) for s in frames}

        log(f'backtesting {len(fm.STAT_FITS)} statistical models for {len(frames)} players …')
        results = Parallel(n_jobs=args.jobs, backend='loky')(
            delayed(fm.run_player)(s, frames[s], futs[s], ctxs[s], grids[s]) for s in frames)
        results = {r['slug']: r for r in results}
        log('statistical backtests done')

        feats = fm.origin_features(pg)
        needed = {s: fm.player_cutoff(df) for s, df in frames.items()}      # each player's latest safe cutoff
        cutoffs = fm.backtest_cutoffs(needed.values())
        assigned = {s: fm.newest_cutoff(c, cutoffs) for s, c in needed.items()}
        xgb_err, xgb_preds, xgb_fc, xgb_models, xgb_infos = xgb_backtest_and_fit(
            pg, feats, ratings, gf, groups, frames, roster_groups, futs, needed, cutoffs, log)
        for s, r in results.items():
            if s in xgb_err:
                r['errors']['XGB'] = xgb_err[s]
                r['preds']['XGB'] = xgb_preds[s]
            if s in xgb_fc:
                r['forecast']['XGB'] = xgb_fc[s]
                r['params']['XGB'] = {'positions': ','.join(sorted(roster_groups[s])),
                                      'backtest_cutoff': str(assigned[s].date()) if assigned.get(s) is not None else None,
                                      **{f'{p}_val_mae': round(xgb_infos[p]['val_mae'], 3)
                                         for p in sorted(roster_groups[s]) if p in xgb_infos}}

        deep_fitted, bands = {}, {}
        if args.deep != 'skip':
            from pipeline import deep_models as dm          # imports torch: only when used
            log(f'TFT + DeepAR by position (cache {dm.CACHE_DIR}, mode {args.deep}) …')
            deep_out, deep_fitted = dm.run(pg, groups, frames, roster_groups, futs,
                                           {s: r['origins'] for s, r in results.items()}, needed, cutoffs,
                                           args.deep, log, grids)
            for m, d in deep_out.items():
                cov = dm.coverage(d['hits'])
                native = 0.70 <= cov <= 0.90                     # use the model's own range only if calibrated
                log(f'{m}: backtest coverage of its own 80% range {cov:.0%} -> '
                    f'{"model quantiles" if native else "backtest-error range"}')
                for s, r in results.items():
                    if s in d['errors']:
                        r['errors'][m] = d['errors'][s]
                        r['preds'][m] = d['preds'][s]
                    if s in d['forecast']:
                        r['forecast'][m] = d['forecast'][s]
                        r['params'][m] = {**d['params'][s], 'cov80_own_range': round(cov, 3),
                                          'range': 'model quantiles' if native else 'backtest errors'}
                        if native:
                            bands.setdefault(s, {})[m] = d['band'][s]
            log('deep models done')

        # ---- chance of playing ----
        p_bt, play_model, play_sc = play_backtest_and_fit(gf, frames, results, needed, cutoffs, log)
        rates = fm.status_play_rates(gf)
        espn = dict(zip(status['slug'], status['injury_status']))
        log(f'ESPN status caps: day-to-day {rates["DAY_TO_DAY"]:.0%} (n={rates["n_dtd"]:,}), '
            f'out {rates["OUT"]:.0%} (n={rates["n_out"]:,}); snapshot {"used" if espn else "missing or stale"}')
        p_fc = {s: play_forecast(play_model, gf, s, futs[s], episodes, today, espn, rates, curves) for s in results}
        for s, (p, note) in sorted(p_fc.items()):
            if note:
                log(f'  {s}: play {" ".join(f"{x:.0%}" for x in p)} · {note}')

        # ---- champion + intervals ----
        tables = {}
        for s, r in results.items():
            t = fm.mae_table(r['errors'])
            t.attrs['n_origins'] = len(r['origins'])
            tables[s] = t
        default, mean_skill = fm.roster_default(tables)
        pooled = {m: np.concatenate([r['errors'][m][np.isfinite(r['errors'][m])] for r in results.values()
                                     if m in r['errors']]) for m in fm.MODELS
                  if any(m in r['errors'] for r in results.values())}

        fc_rows, run_rows = [], []
        exp_err = {'if_plays': [], 'expected': [], 'assume_plays': []}
        for s, r in results.items():
            t = tables[s]
            champ, reason = fm.pick_champion(t, r['errors'], default)
            if champ not in r['forecast']:
                champ, reason = 'MEAN_10', 'champion failed to fit: rolling mean fallback'
            fut = futs[s]
            # expected-points score of the champion on every team game (a missed game counts as 0 points)
            pm, P, pl, e = r['preds'].get(champ), p_bt.get(s), r['played'], r['errors'].get(champ)
            if pm is not None and P is not None and e is not None:
                ok = np.isfinite(pm) & np.isfinite(P) & np.isfinite(pl)
                a0 = np.where(pl == 1, e + pm, 0.0)
                exp_err['if_plays'] += list(np.abs(e[ok & (pl == 1)]))
                exp_err['expected'] += list(np.abs((a0 - P * pm)[ok]))
                exp_err['assume_plays'] += list(np.abs((a0 - pm)[ok]))
            p_play, note = p_fc.get(s, (np.ones(len(fut)), ''))
            naive = t.loc['NAIVE', 'mae'] if 'NAIVE' in t.index else np.nan
            for m, (label, family) in fm.MODELS.items():
                if m not in r['forecast']:
                    continue
                lo, hi = fm.interval(r['errors'].get(m), pooled.get(m))
                pred = np.clip(r['forecast'][m], 0, None)
                band = bands.get(s, {}).get(m)                   # TFT / DeepAR's own quantiles, when calibrated
                for i, row in fut.iterrows():
                    if i >= len(pred):
                        break
                    lo80, hi80 = ((band[0][i], band[1][i]) if band is not None else (pred[i] + lo, pred[i] + hi))
                    fc_rows.append({'run_date': today, 'slug': s, 'model': m, 'horizon': int(row['h']),
                                    'game_date': row['date'].date(), 'team': row['team'], 'opponent': row['opponent'],
                                    'home': int(row['home']), 'rest_days': int(row['rest']),
                                    'opp_def_rank': None if pd.isna(row['opp_def_rank']) else int(row['opp_def_rank']),
                                    'prediction': float(pred[i]), 'lo80': max(0.0, float(lo80)),
                                    'hi80': float(hi80), 'p_play': float(p_play[i]),
                                    'expected_points': float(pred[i] * p_play[i]), 'play_note': note or None,
                                    'champion': int(m == champ)})
                mt = t.loc[m] if m in t.index else pd.Series(dtype=float)
                dg = r['diag'].get(m, {})
                run_rows.append({'run_date': today, 'slug': s, 'model': m, 'label': label, 'family': family,
                                 'params': fm.to_json(r['params'].get(m, {})), 'n_games': r['n_games'],
                                 'n_origins': len(r['origins']), 'mae': mt.get('mae'),
                                 **{f'mae_h{h}': mt.get(f'mae_h{h}') for h in range(1, fm.H + 1)},
                                 'skill': (1 - mt.get('mae') / naive) if mt.get('mae') is not None and naive else None,
                                 'aicc': dg.get('aicc'), 'ljung_box_p': dg.get('ljung_box_p'),
                                 'champion': int(m == champ), 'champion_reason': reason if m == champ else None,
                                 'mlflow_run_id': None})
            if r['failed']:
                log(f'{s}: failures {r["failed"]}')
        forecasts, runs = pd.DataFrame(fc_rows), pd.DataFrame(run_rows)
        team_of = {s: futs[s]['team'].iloc[0] for s in futs}
        roster_rows = roster.assign(
            positions=roster['slug'].map(lambda s: ','.join(p for p in fm.POSITIONS if p in groups.get(s, ()))),
            team=roster['slug'].map(team_of), run_date=today).drop_duplicates(['league', 'slug'])

        # ---- report ----
        print('\nRoster default (mean skill vs naive across players):')
        for m, v in sorted(mean_skill.items(), key=lambda kv: -kv[1]):
            print(f'  {fm.MODELS[m][0]:<28} {v:+.1%}{"   <- default" if m == default else ""}')
        champs = runs[runs['champion'] == 1]
        print('\nChampions:', champs['model'].value_counts().to_dict())
        print(runs.groupby('model')['mae'].mean().sort_values().round(2).to_string())
        exp_mae = {k: float(np.mean(v)) for k, v in exp_err.items() if v}
        if exp_mae:
            print(f"\nChampion backtest, every team game (a missed game = 0 points): expected points (x chance of "
                  f"playing) MAE {exp_mae.get('expected', np.nan):.2f} vs assuming he plays "
                  f"{exp_mae.get('assume_plays', np.nan):.2f}; games played only (points if he plays) "
                  f"{exp_mae.get('if_plays', np.nan):.2f}")

        if args.dry_run:
            log('dry run: nothing written, nothing logged')
            return
        if not args.no_mlflow:
            meta = dict(zip(roster['slug'], roster['name']))
            extra = {**{f'champion_mae.{k}': v for k, v in exp_mae.items()},
                     **{f'play.{k}': v for k, v in play_sc.items() if isinstance(v, (int, float))}}
            ids = log_mlflow(today, {'default': default, 'mean_skill': mean_skill, 'extra': extra}, xgb_models,
                             xgb_infos, runs, forecasts, meta, deep_fitted)
            runs['mlflow_run_id'] = runs['slug'].map(ids)
            log(f'MLflow run {ids["_parent"]} logged to {MLFLOW_DIR}')
        write(cn, today, roster_rows, forecasts, runs)
        log(f'wrote {len(forecasts)} forecasts, {len(runs)} model rows, {len(roster_rows)} roster rows')
        if not args.no_mlflow:
            try:                                    # newest 30 versions + one per week; never fails the run
                from pipeline import mlflow_retention
                mlflow_retention.prune(log=log)
            except Exception as e:
                log(f'MLflow retention skipped ({type(e).__name__}: {e})')
    finally:
        cn.close()


if __name__ == '__main__':
    main()
