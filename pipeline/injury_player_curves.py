"""
Per-player injury curves -> basketball.injury_player_curves, every night after pipeline.injury_mapping.

The monthly refit (pipeline/injury_probabilities_basketball.py) publishes one population-average curve
per injury group. Its model already knows each absence's own inputs (out for season, a stated return
window, surgery, DTD, age, injury history, player frailty, pre-injury minutes), so this script refits that
same model type on every episode (a few seconds) and predicts one curve for each player currently out:
an episode with no return logged and no game since its out date, started within a year
(injury_probabilities_basketball.current_episodes). Rostered players and free agents alike.

The model type is the latest published champion (injury_model_evaluations, source='refit'; lognormal_aft
if that table is missing). Refitting nightly instead of loading a saved model means no state to carry
between GitHub runs, and the curves always use the latest episodes. The app's Injuries tab and the
free-agent screener read the table; pipeline/points_forecast.py uses it for the chance a player is back
for each upcoming game.

Run from the repo root (env: basketball-env-useme-v11052026):
    python -m pipeline.injury_player_curves             # fit + write
    python -m pipeline.injury_player_curves --dry-run   # fit + print
"""
import argparse
import datetime as dt
import time

import mysql.connector as mysql

from pipeline import injury_probabilities_basketball as ip


def published_champion():
    try:
        cn = mysql.connect(**ip.config)
        cur = cn.cursor()
        cur.execute("SELECT model FROM basketball.injury_model_evaluations WHERE source = 'refit' "
                    "ORDER BY run_date DESC LIMIT 1;")
        row = cur.fetchone()
        cn.close()
        return row[0] if row else 'lognormal_aft'
    except mysql.Error:
        return 'lognormal_aft'


def main():
    ap = argparse.ArgumentParser(description='Per-player injury curves -> basketball.injury_player_curves')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()
    t0 = time.time()
    today = dt.date.today()
    champion = published_champion()
    df = ip.prepare(ip.load_episodes())
    model, full, groups = ip.fit_champion(df, champion)
    rows = ip.player_curves(full, model, groups, today)
    if rows.empty:
        print('no players currently out')
    else:
        s = rows.pivot(index='slug', columns='days', values='probabilities')
        summ = rows.drop_duplicates('slug').set_index('slug')[['player_name', 'curve_group', 'days_out']]
        summ['still_out_d14'] = s[14]
        summ['median_days'] = s.apply(lambda r: int((r <= 0.5).idxmax()) if (r <= 0.5).any() else None, axis=1)
        print(summ.sort_values('days_out', ascending=False).to_string())
    print(f'{champion}: {rows["slug"].nunique() if len(rows) else 0} players currently out, {time.time() - t0:.0f}s')
    if not args.dry_run:
        ip.write_player_curves(rows)


if __name__ == '__main__':
    main()
