"""
ESPN free agents' current-season game logs -> basketball.live_free_agents.

1. league.free_agents(): who is available in my ESPN league right now.
2. Each name -> its bbref slug (match_slugs), first match wins:
   a. the names on this season's box scores, by name_key (accents, case, punctuation, Jr./II
      ignored). These are basketball-reference's own names for the games we load, rookies included;
   b. same last name and one first name a prefix of the other (Ron / Ronald), if exactly one
      player this season fits;
   c. basketball.master_names_list_temp, by the original rule (every row whose full_name contains
      the ESPN name; accents stripped unless the name matches a full_name exactly). Only players
      with no game this season get here, and they add no rows.
3. Their games this season from basketball.historical_player_data (league-wide daily box scores
   loaded by pipeline/historicals.py), in one query.

Step 3 used to call client.regular_season_player_box_scores() once per free agent with a 4 s sleep:
~700 requests, ~50 min. Those rows are already in historical_player_data, so this now takes seconds.
Run pipeline.historicals first so last night's games are in (run_scripts.py already does).
Differences from the old source: a stat basketball-reference corrects after historicals.py loaded
that day isn't picked up, and plus_minus is left empty (historical_player_data doesn't keep it).

Run from the repo root:
    python -m pipeline.free_agents_backfill            # fetch + replace live_free_agents
    python -m pipeline.free_agents_backfill --dry-run  # fetch + summary, no DB writes
"""
import argparse
import os
import sys

import pandas as pd
import mysql.connector as mysql
import unidecode
from espn_api.basketball import League

from shared.my_functions import clean_string, name_key
from shared import season_calendar

FA_SIZE = 700
NON_SHOWS_FILE = '/Users/franciscoavalosjr/Desktop/basketball-folder/tmp_data/non_shows_list.csv'

# live_free_agents columns, in table order (named in the INSERT, so order never shifts data)
FA_COLS = ['name', 'date', 'team', 'location', 'opponent', 'outcome', 'active', 'seconds_played',
           'made_field_goals', 'attempted_field_goals', 'made_three_point_field_goals',
           'attempted_three_point_field_goals', 'made_free_throws', 'attempted_free_throws',
           'offensive_rebounds', 'defensive_rebounds', 'assists', 'steals', 'blocks', 'turnovers',
           'personal_fouls', 'points_scored', 'game_score', 'plus_minus', 'name_code']
HIST_COLS = ['slug', 'date', 'team', 'location', 'opponent', 'outcome', 'seconds_played',
             'made_field_goals', 'attempted_field_goals', 'made_three_point_field_goals',
             'attempted_three_point_field_goals', 'made_free_throws', 'attempted_free_throws',
             'offensive_rebounds', 'defensive_rebounds', 'assists', 'steals', 'blocks', 'turnovers',
             'personal_fouls', 'points', 'game_score']


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


def espn_free_agents(season_year):
    """Names of the players currently available in my ESPN league."""
    league = League(league_id=os.environ.get('leagueid'), year=season_year,
                    espn_s2=os.environ.get('espn_s2'), swid=os.environ.get('swid'), debug=False)
    return [n.strip() for n in clean_string(league.free_agents(size=FA_SIZE)).split(',') if n.strip()]


def match_slugs(free_agents, season_names, crosswalk):
    """[(espn_name, slug)], the names that matched nothing, and a count per method.
    season_names: this season's box-score (name, slug); crosswalk: master_names_list_temp."""
    by_key, by_last = {}, {}
    for n, s in zip(season_names['name'], season_names['slug']):
        k = name_key(n).split()
        if not k:
            continue
        by_key.setdefault(' '.join(k), set()).add(s)
        by_last.setdefault(k[-1], set()).add((k[0], s))
    cw = crosswalk[crosswalk['bbrefid'].notna()]
    raw = list(zip(cw['full_name'], cw['bbrefid']))
    plain = [(unidecode.unidecode(f), s) for f, s in raw]
    exact = set(cw['full_name'])

    pairs, unmatched, how = [], [], {'box_score': 0, 'nickname': 0, 'crosswalk': 0}
    for fa in free_agents:
        k = name_key(fa).split()
        hits, method = [], None
        if k and ' '.join(k) in by_key:
            hits, method = sorted(by_key[' '.join(k)]), 'box_score'
        elif len(k) >= 2:
            first = k[0]
            fits = {s for f, s in by_last.get(k[-1], ()) if min(len(f), len(first)) >= 3
                    and (f.startswith(first) or first.startswith(f))}
            if len(fits) == 1:
                hits, method = sorted(fits), 'nickname'
        if not hits:
            hits = [s for f, s in (raw if fa in exact else plain) if fa in f]
            method = 'crosswalk'
        if hits:
            how[method] += 1
            pairs += [(fa, s) for s in hits]
        else:
            unmatched.append(fa)
    return pairs, unmatched, how


def build(cn, season_year):
    """The rows for live_free_agents, plus the unmatched names."""
    season_start = season_calendar.season_bounds(season_year)[0].date()
    crosswalk = query(cn, 'SELECT full_name, bbrefid FROM basketball.master_names_list_temp;')
    season_names = query(cn, 'SELECT DISTINCT name, slug FROM basketball.historical_player_data '
                             'WHERE date >= %s AND seconds_played > 0;', (season_start,))
    latest = query(cn, 'SELECT MAX(date) AS d FROM basketball.historical_player_data;')['d'].iloc[0]
    free_agents = espn_free_agents(season_year)
    pairs, unmatched, how = match_slugs(free_agents, season_names, crosswalk)
    print(f'{len(free_agents)} ESPN free agents · matched by box-score name {how["box_score"]}, '
          f'nickname {how["nickname"]}, crosswalk {how["crosswalk"]} · {len(unmatched)} unmatched')
    if not pairs:
        sys.exit('No free agent matched a slug; not touching live_free_agents.')

    slugs = sorted({s for _, s in pairs})
    marks = ', '.join(['%s'] * len(slugs))
    games = query(cn, f"SELECT {', '.join(HIST_COLS)} FROM basketball.historical_player_data "
                      f"WHERE date >= %s AND seconds_played > 0 AND slug IN ({marks});",
                  (season_start, *slugs))
    rows = pd.DataFrame(pairs, columns=['name', 'slug']).merge(games, on='slug')
    rows = rows.rename(columns={'slug': 'name_code', 'points': 'points_scored'})
    rows['active'] = 'True'
    rows['plus_minus'] = None
    rows = rows[FA_COLS].drop_duplicates(['name', 'date', 'team', 'name_code'])   # the table's primary key
    print(f'{len(rows)} games for {rows["name_code"].nunique()} players since {season_start} '
          f'(box scores loaded through {latest})')
    return rows, unmatched


def write(cn, rows):
    """Replace live_free_agents in one transaction (TRUNCATE can't roll back), so a failure keeps the old rows."""
    values = [tuple(None if pd.isna(v) else v for v in r) for r in rows.itertuples(index=False)]
    try:
        cur = cn.cursor()
        cur.execute('DELETE FROM basketball.live_free_agents;')
        cur.executemany(f"INSERT INTO basketball.live_free_agents ({', '.join(FA_COLS)}) "
                        f"VALUES ({', '.join(['%s'] * len(FA_COLS))});", values)
        cn.commit()
        cur.close()
    except mysql.Error:
        cn.rollback()
        raise


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true', help='build the rows and print a summary; no DB writes')
    args = ap.parse_args()

    cn = connect()
    try:
        rows, unmatched = build(cn, int(os.environ.get('season_year')))
        if args.dry_run:
            print('dry run: live_free_agents not changed')
            return
        write(cn, rows)
    finally:
        cn.close()
    pd.DataFrame(unmatched, columns=['name']).to_csv(NON_SHOWS_FILE, index=False)
    print(f'live_free_agents ready · unmatched ESPN names in {NON_SHOWS_FILE}')


if __name__ == '__main__':
    main()
