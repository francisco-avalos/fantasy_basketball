"""
injury_drift_monitor.py
-----------------------
Weekly drift checks for the injury survival curves (pipeline/injury_probabilities_basketball.py), written
to basketball.injury_model_monitoring, with a "model health" summary for the GitHub Actions run page.

Why: the data drifts (mean in-season days out fell from 34.8 in 2000-05 to 10.9 in 2021+, and the
"unspecified" share from ~32% of a season to under 1%), the refit runs on a timer, and a curve that is a
few days off never raises an error. These checks make drift visible, and tell data problems apart from it.

    0  data_quality     injury log and box scores up to date; every scheduled game day has box scores and
                        injury transactions; share of injury episodes with no player match
    1  season_backtest  the published model type fitted on seasons before the latest completed season and
                        scored on it, against the same score for the season before (IBS +10% or
                        calibration error > 0.06 -> alert). Scores also go to injury_model_evaluations.
    2  calibration      each published curve against the Kaplan-Meier of episodes from the last 365 days, at
                        days 7 / 14 / 30, for curve groups with >= 40 such episodes (smaller ones pooled by
                        body region). Alert when the gap is > 0.10 AND outside the KM 95% band.
    3  mix_labels       last 90 days against the latest completed season: PSI of the category and curve-group
                        mix (> 0.2), severity-flag rates (x2 either way), share of recent episodes whose note
                        needed Claude (> 15%), and the unspecified share (> 10 points of change)

Statuses: ok, alert, info. Nothing here changes the curves: an alert is a prompt to look (see CLAUDE.md for
what to do about each), and the workflow step never fails the run.

Run from the repo root (env: basketball-env-useme-v11052026), after injury_mapping:
    python -m pipeline.injury_drift_monitor                 # run the checks if 7+ days since the last run; print the summary
    python -m pipeline.injury_drift_monitor --force         # run them now
    python -m pipeline.injury_drift_monitor --dry-run       # run them now, print, write nothing
    python -m pipeline.injury_drift_monitor --summary-only  # print the latest stored results
Needs sql_files/migrations/2026-11-20_injury_model_monitoring.sql.
"""

import argparse
import datetime as dt
import os
import warnings

import numpy as np
import pandas as pd
import mysql.connector as mysql
from lifelines import KaplanMeierFitter

from pipeline import injury_probabilities_basketball as ip
from shared import season_calendar as cal

warnings.filterwarnings('ignore')

config = ip.config
EVERY_DAYS = 7
CAL_TIMES = (7, 14, 30)
CAL_MIN_N, CAL_MIN_AT_RISK, CAL_GAP = 40, 10, 0.10
RECENT_DAYS, MIX_RECENT_DAYS = 365, 90
IBS_RISE, CAL_MAE_MAX = 0.10, 0.06
PSI_MAX, SEV_RATIO, LLM_SHARE_MAX, UNSPEC_PP = 0.2, 2.0, 0.15, 0.10
UNMATCHED_MAX = 0.02
CHECKS = [('data_quality', 'Data quality'), ('season_backtest', 'Season backtest'),
          ('calibration', 'Calibration by curve group'), ('mix_labels', 'Mix and labels')]
COLS = ['run_date', 'check_name', 'unit', 'metric', 'value', 'threshold', 'status', 'n', 'detail']


def row(check, metric, value=None, threshold=None, status='ok', n=None, detail='', unit=''):
    num = lambda v: None if v is None or (isinstance(v, float) and not np.isfinite(v)) else float(v)
    return {'check_name': check, 'unit': unit, 'metric': metric, 'value': num(value), 'threshold': num(threshold),
            'status': status, 'n': None if n is None else int(n), 'detail': detail[:500]}


def season_name(s):
    return f'{int(s) - 1}-{str(int(s))[2:]}'


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


# ---------------------------------------------------------------------------
# 0. Data quality
# ---------------------------------------------------------------------------

def check_data_quality(today):
    out = []
    in_season = bool(cal.is_in_season(pd.Timestamp(today)))
    for metric, sql, max_age in [('injury_log_age_days', 'SELECT MAX(day) FROM basketball.hist_player_inj', 3),
                                 ('box_score_age_days', 'SELECT MAX(date) FROM basketball.historical_player_data', 2)]:
        last = query(sql).iloc[0, 0]
        age = (today - pd.Timestamp(last).date()).days if last is not None else None
        status = 'info' if not in_season else ('alert' if age is None or age > max_age else 'ok')
        out.append(row('data_quality', metric, age, max_age, status,
                       detail=f'latest {last}' + ('' if in_season else ' (offseason)')))

    start = today - dt.timedelta(days=60)
    sched = query('SELECT start_time FROM basketball.high_level_nba_team_schedules')
    game_days = set(pd.to_datetime(sched['start_time'], utc=True).dt.tz_convert('US/Eastern').dt.date)
    game_days = sorted(d for d in game_days if start <= d < today)
    box = set(query('SELECT DISTINCT date FROM basketball.historical_player_data WHERE date >= %s', (start,))['date'])
    inj = set(query('SELECT DISTINCT day FROM basketball.hist_player_inj WHERE day >= %s', (start,))['day'])
    no_box = [d for d in game_days if d < today - dt.timedelta(days=1) and d not in box]
    no_inj = [d for d in game_days if d <= today - dt.timedelta(days=2) and d not in inj]
    fmt = lambda ds: ', '.join(str(d) for d in ds[:8]) + (f' (+{len(ds) - 8} more)' if len(ds) > 8 else '')
    out.append(row('data_quality', 'game_days_without_box_scores', len(no_box), 0, 'alert' if no_box else 'ok',
                   n=len(game_days), detail=fmt(no_box) or f'all {len(game_days)} scheduled game days in the last 60 have box scores'))
    out.append(row('data_quality', 'game_days_without_injury_moves', len(no_inj), 0, 'alert' if no_inj else 'ok',
                   n=len(game_days), detail=(fmt(no_inj) + ': re-fetch these days (a failed fetch, or a genuinely quiet day)')
                   if no_inj else 'every scheduled game day in the last 60 has injury transactions'))

    um = query('SELECT AVG(slug IS NULL) AS share, COUNT(*) AS n FROM basketball.player_injury_cycles '
               'WHERE start_date >= %s', (today - dt.timedelta(days=RECENT_DAYS),))
    share, n = float(um['share'].iloc[0] or 0), int(um['n'].iloc[0])
    out.append(row('data_quality', 'unmatched_episode_share', share, UNMATCHED_MAX,
                   'alert' if share > UNMATCHED_MAX else 'ok', n=n,
                   detail=f'{share:.1%} of {n} episodes in the last {RECENT_DAYS} days have no player match'))
    return out


# ---------------------------------------------------------------------------
# 1. Season backtest
# ---------------------------------------------------------------------------

def _backtest(df, season, model_name):
    tr_raw, te_raw = df[df['season'] < season], df[df['season'] == season]
    train, mapping, medians = ip.setup(tr_raw)
    test, _, _ = ip.setup(pd.concat([tr_raw, te_raw]), mapping, medians)
    test = test[test['season'] == season].reset_index(drop=True)
    train = train.reset_index(drop=True)
    model = next(m for m in [ip.KMGroup()] + ip.candidates() if m.name == model_name)
    scores, _ = ip.evaluate(train, test, [model], sorted(train['model_group'].unique()))
    return scores.iloc[0], len(train), len(test)


def check_season_backtest(df, today, model_name):
    done = [s for s in sorted(df['season'].unique()) if cal.season_bounds(int(s))[1].date() < today]
    if len(done) < 2:
        return [row('season_backtest', 'ibs_1_60', status='info', detail='needs two completed seasons')], []
    s, prev = int(done[-1]), int(done[-2])
    (cur_sc, n_tr, n_te), (prev_sc, p_tr, p_te) = _backtest(df, s, model_name), _backtest(df, prev, model_name)
    rise = cur_sc['ibs_1_60'] / prev_sc['ibs_1_60'] - 1
    out = [
        row('season_backtest', 'ibs_1_60', cur_sc['ibs_1_60'], prev_sc['ibs_1_60'] * (1 + IBS_RISE),
            'alert' if rise > IBS_RISE else 'ok', n=n_te,
            detail=f'{season_name(s)} {cur_sc["ibs_1_60"]:.4f} vs {season_name(prev)} {prev_sc["ibs_1_60"]:.4f} '
                   f'({rise:+.1%}; alert above +{IBS_RISE:.0%})'),
        row('season_backtest', 'calibration_mae', cur_sc['calibration_mae'], CAL_MAE_MAX,
            'alert' if cur_sc['calibration_mae'] > CAL_MAE_MAX else 'ok', n=n_te,
            detail=f'{season_name(s)} {cur_sc["calibration_mae"]:.3f} (alert above {CAL_MAE_MAX}); '
                   f'{season_name(prev)} {prev_sc["calibration_mae"]:.3f}'),
        row('season_backtest', 'c_index', cur_sc['c_index'], None, 'info', n=n_te,
            detail=f'{season_name(s)} {cur_sc["c_index"]:.3f} vs {season_name(prev)} {prev_sc["c_index"]:.3f}'),
    ]
    evals = []
    for season, sc, ntr, nte in [(s, cur_sc, n_tr, n_te), (prev, prev_sc, p_tr, p_te)]:
        evals.append({'run_date': today, 'source': 'season_backtest', 'model': model_name,
                      'test_seasons': str(season), 'train_seasons': f'<{season}', 'n_train': ntr, 'n_test': nte,
                      'is_champion': 1, **{c: float(sc[c]) for c in ip.EVAL_COLS if c in sc.index}})
    return out, evals


# ---------------------------------------------------------------------------
# 2. Calibration of the published curves on recent episodes
# ---------------------------------------------------------------------------

def check_calibration(df, curves, today):
    recent_from = pd.Timestamp(today - dt.timedelta(days=RECENT_DAYS))
    full, mapping, medians = ip.setup(df)
    rec = full[full['start_date'] >= recent_from].copy()
    published = {g: c.sort_values('days')['probabilities'].astype(float).values for g, c in curves.groupby('injury')}

    def curve_of(g):
        for k in (g, ip.parent(g), 'injury:other', 'unspecified'):
            if k in published:
                return k
        return None
    rec['curve'] = rec['model_group'].map(curve_of)
    rec = rec[rec['curve'].notna()]
    if rec.empty:
        return [row('calibration', 'gap', status='info', detail='no recent episodes')]

    counts = rec['curve'].value_counts()
    big = set(counts[counts >= CAL_MIN_N].index)
    rec['unit'] = np.where(rec['curve'].isin(big), rec['curve'],
                           rec['curve'].str.split(':').str[0] + ':* (pooled)')
    pooled = rec['unit'].value_counts()
    rec.loc[rec['unit'].map(pooled) < CAL_MIN_N, 'unit'] = 'everything else (pooled)'

    out = []
    units = [(u, d) for u, d in rec.groupby('unit') if len(d) >= CAL_MIN_N] + [('ALL', rec)]
    for unit, d in units:
        km = KaplanMeierFitter().fit(d['T'], d['E'])
        ci = km.confidence_interval_survival_function_
        for t in CAL_TIMES:
            at_risk = int((d['T'] >= t).sum())
            if at_risk < CAL_MIN_AT_RISK:
                continue
            obs = float(km.predict(t))
            lo, hi = ci[ci.index <= t].iloc[-1].values
            pred = float(np.mean([published[c][t] for c in d['curve']]))
            gap = obs - pred
            alert = unit != 'ALL' and abs(gap) > CAL_GAP and not (lo <= pred <= hi)
            out.append(row('calibration', f'gap_day{t}', gap, CAL_GAP, 'alert' if alert else
                           ('info' if unit == 'ALL' else 'ok'), n=len(d), unit=unit,
                           detail=f'still out at day {t}: observed {obs:.2f} (95% CI {lo:.2f}-{hi:.2f}) vs curve '
                                  f'{pred:.2f}; {len(d)} episodes, {at_risk} at risk'))
    return out


# ---------------------------------------------------------------------------
# 3. Mix and label monitors
# ---------------------------------------------------------------------------

def psi(recent, ref):
    keys = sorted(set(recent.index) | set(ref.index))
    p = recent.reindex(keys, fill_value=0) + 1e-4
    q = ref.reindex(keys, fill_value=0) + 1e-4
    p, q = p / p.sum(), q / q.sum()
    return float(((p - q) * np.log(p / q)).sum())


def check_mix_labels(df, today):
    done = [s for s in sorted(df['season'].unique()) if cal.season_bounds(int(s))[1].date() < today]
    ref = df[df['season'] == done[-1]] if done else df.iloc[0:0]
    rec = df[df['start_date'] >= pd.Timestamp(today - dt.timedelta(days=MIX_RECENT_DAYS))]
    label = f'last {MIX_RECENT_DAYS} days ({len(rec)} episodes) vs {season_name(done[-1]) if done else "?"} ({len(ref)})'
    if len(rec) < 30 or ref.empty:
        return [row('mix_labels', 'psi_category', status='info', n=len(rec), detail=f'too few episodes: {label}')]
    out = []
    v = psi(rec['category'].value_counts(normalize=True), ref['category'].value_counts(normalize=True))
    out.append(row('mix_labels', 'psi_category', v, PSI_MAX, 'alert' if v > PSI_MAX else 'ok', n=len(rec),
                   detail=f'PSI {v:.3f} (alert above {PSI_MAX}); {label}'))
    top = ref['curve_group'].value_counts().index[:15]
    bucket = lambda s: s.where(s.isin(top), 'other').value_counts(normalize=True)
    v = psi(bucket(rec['curve_group']), bucket(ref['curve_group']))
    out.append(row('mix_labels', 'psi_curve_group', v, PSI_MAX, 'alert' if v > PSI_MAX else 'ok', n=len(rec),
                   detail=f'PSI {v:.3f} over the 15 largest groups + other (alert above {PSI_MAX})'))

    flags = {'out_indefinitely': rec['out_indefinitely'], 'stated_window': rec['stated_days'].notna(),
             'surgery': rec['is_surgery'], 'day_to_day': rec['is_dtd']}
    ref_flags = {'out_indefinitely': ref['out_indefinitely'], 'stated_window': ref['stated_days'].notna(),
                 'surgery': ref['is_surgery'], 'day_to_day': ref['is_dtd']}
    for name, f in flags.items():
        r_now, r_ref = float(pd.Series(f).fillna(0).astype(float).mean()), \
            float(pd.Series(ref_flags[name]).fillna(0).astype(float).mean())
        ratio = r_now / r_ref if r_ref > 0 else np.nan
        enough = pd.Series(f).fillna(0).astype(float).sum() >= 10 or r_ref * len(rec) >= 10
        alert = enough and np.isfinite(ratio) and (ratio > SEV_RATIO or ratio < 1 / SEV_RATIO)
        out.append(row('mix_labels', f'rate_{name}', ratio, SEV_RATIO, 'alert' if alert else 'ok', n=len(rec),
                       detail=f'{r_now:.1%} of recent episodes vs {r_ref:.1%} (x{ratio:.2f}; alert beyond x{SEV_RATIO:g} either way)'))

    cls = query('SELECT note_key, source FROM basketball.injury_note_classification')
    src = rec['note_key'].map(dict(zip(cls['note_key'], cls['source'])))
    llm = float((src == 'llm').mean())
    out.append(row('mix_labels', 'llm_labelled_share', llm, LLM_SHARE_MAX, 'alert' if llm > LLM_SHARE_MAX else 'ok',
                   n=len(rec), detail=f'{llm:.1%} of recent episodes have a note the regex could not read '
                                      f'(alert above {LLM_SHARE_MAX:.0%})'))
    u_now, u_ref = float((rec['curve_group'] == 'unspecified').mean()), float((ref['curve_group'] == 'unspecified').mean())
    out.append(row('mix_labels', 'unspecified_share_change', u_now - u_ref, UNSPEC_PP,
                   'alert' if abs(u_now - u_ref) > UNSPEC_PP else 'ok', n=len(rec),
                   detail=f'unspecified {u_now:.1%} recently vs {u_ref:.1%} (alert beyond {UNSPEC_PP:.0%} points)'))
    return out


# ---------------------------------------------------------------------------
# Store + summary
# ---------------------------------------------------------------------------

def write(rows, today):
    cn = mysql.connect(**config)
    cur = cn.cursor()
    try:
        cur.execute('DELETE FROM basketball.injury_model_monitoring WHERE run_date = %s;', (today,))
        cur.executemany(f'INSERT INTO basketball.injury_model_monitoring ({", ".join(COLS)}) '
                        f'VALUES ({", ".join(["%s"] * len(COLS))});',
                        [tuple(today if c == 'run_date' else r[c] for c in COLS) for r in rows])
        cn.commit()
    except Exception:
        cn.rollback()
        raise
    finally:
        cur.close()
        cn.close()
    print(f'basketball.injury_model_monitoring: {len(rows)} rows for {today}')


def latest_run():
    df = query('SELECT * FROM basketball.injury_model_monitoring WHERE run_date = '
               '(SELECT MAX(run_date) FROM basketball.injury_model_monitoring)')
    return df


def refit_info():
    try:
        r = query("SELECT run_date, model FROM basketball.injury_model_evaluations WHERE source = 'refit' "
                  "ORDER BY run_date DESC LIMIT 1")
        return (r['run_date'].iloc[0], r['model'].iloc[0]) if len(r) else (None, None)
    except mysql.Error:
        return None, None


def summarize(rows, run_date, today):
    """Markdown 'model health' block, plus ::warning:: annotations under GitHub Actions."""
    refit_date, model = refit_info()
    next_due = run_date + dt.timedelta(days=EVERY_DAYS) if run_date else today
    lines = ['### Model health: injury survival curves', '',
             f'Curves: **{model or "?"}**, refit {refit_date or "unknown"} · checks run {run_date} '
             f'(next {next_due})', '', '| Check | Status | Detail |', '|---|---|---|']
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
            status = '✅ ok'
            lead = {'data_quality': 'injury_log_age_days', 'season_backtest': 'ibs_1_60',
                    'calibration': 'gap_day14', 'mix_labels': 'psi_category'}[key]
            first = next((r for r in rs if r['metric'] == lead and r['unit'] in ('', 'ALL')), rs[0])
            n_units = len({r['unit'] for r in rs if r['unit'] not in ('', 'ALL')})
            detail = (f'{n_units} curve groups checked; overall ' if key == 'calibration' else '') + first['detail']
        lines.append(f'| {title} | {status} | {detail.replace("|", "/")} |')
    if alerts:
        lines += ['', '**Alerts**', ''] + [f'- {t} · {r["unit"] + " · " if r["unit"] else ""}{r["metric"]}: '
                                          f'{r["detail"]}' for t, r in alerts]
    md = '\n'.join(lines) + '\n'
    print('\n' + md)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as f:
            f.write(md)
    if os.environ.get('GITHUB_ACTIONS') == 'true':
        esc = lambda s: s.replace('%', '%25').replace('\r', '%0D').replace('\n', '%0A')
        for t, r in alerts[:10]:
            print(f'::warning title=Injury model health ({t})::'
                  + esc(f'{r["unit"] + " · " if r["unit"] else ""}{r["metric"]}: {r["detail"]}'))
        if len(alerts) > 10:
            print(f'::warning title=Injury model health::{len(alerts) - 10} more alerts in the run summary')


def main():
    ap = argparse.ArgumentParser(description='Drift checks for the injury survival curves')
    ap.add_argument('--force', action='store_true', help=f'run the checks even if the last run is < {EVERY_DAYS} days old')
    ap.add_argument('--dry-run', action='store_true', help='run the checks, print them, write nothing')
    ap.add_argument('--summary-only', action='store_true', help='only print the latest stored results')
    args = ap.parse_args()
    today = dt.date.today()

    try:
        last = query('SELECT MAX(run_date) AS d FROM basketball.injury_model_monitoring')['d'].iloc[0]
    except mysql.Error as e:
        print(f'injury_model_monitoring not available ({e}); run '
              'sql_files/migrations/2026-11-20_injury_model_monitoring.sql once.')
        if not args.dry_run:
            return 0
        last = None
    due = last is None or (today - last).days >= EVERY_DAYS
    if not (args.summary_only or (not args.force and not args.dry_run and not due)):
        curves = query('SELECT injury, days, probabilities, model FROM basketball.injury_probabilities')
        if curves.empty:
            print('injury_probabilities is empty; nothing to monitor')
            return 0
        model = curves['model'].dropna().iloc[0]
        df = ip.prepare(ip.load_episodes())
        print(f'{len(df)} fit-eligible episodes; published model {model}; {curves.injury.nunique()} curves')
        rows = check_data_quality(today)
        bt_rows, evals = check_season_backtest(df, today, model)
        rows += bt_rows + check_calibration(df, curves, today) + check_mix_labels(df, today)
        if args.dry_run:
            summarize(rows, today, today)
            print('dry run: nothing written')
            return 0
        write(rows, today)
        ip.record_evaluations(evals, replace_source='season_backtest')
    elif not args.summary_only:
        print(f'checks last ran {last}; next run due {last + dt.timedelta(days=EVERY_DAYS)} (use --force to run now)')

    stored = latest_run()
    if stored.empty:
        print('no monitoring results stored yet')
        return 0
    rows = [{k: (None if isinstance(v, float) and np.isnan(v) else v) for k, v in r.items()}
            for r in stored.to_dict('records')]
    summarize(rows, stored['run_date'].iloc[0], today)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
