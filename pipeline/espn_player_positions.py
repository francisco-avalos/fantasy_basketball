"""
ESPN position eligibility and injury status for every active NBA player:
    -> basketball.espn_player_positions   (replaced every run)
    -> basketball.nba_injury_status        (one snapshot per day, kept: the injury-status history)

One request: ESPN's fantasy player list (view kona_player_info, all ~1,100 players on a team, free agents
and waivers) carries each player's eligibleSlots, pro team and injuryStatus, so there is no per-player
lookup and no sleep. (The plain pro-players list used before has no injury status. Positions used to
come from league.player_info() once per player with a 4 s sleep: ~30 min, now about 2 s.)

player_name is stored in the live_espn_players spelling (suffixes stripped, as in
pipeline/my_team_stats.py) because the app joins the two tables on name.
player_roles is the eligible-slot list as a Python list literal, e.g. "['PG', 'SG', 'G', 'UT', 'BE', 'IR']";
app/team_performance.py parses it with ast.literal_eval.

nba_injury_status (sql_files/migrations/2026-11-21_forecast_inputs.sql) is the only league-wide injury
status we have: pipeline/points_forecast.py reads today's rows for teammate absences and for the chance a
rostered player plays. slug comes from the same name matching as free_agents_backfill (this and last
season's box-score names first); team is in the box-score spelling ('Team.BOSTON_CELTICS'), NULL for a
free agent. A day's snapshot is replaced if the script runs twice that day.

Run from the repo root:
    python -m pipeline.espn_player_positions
"""
import datetime as dt
import json
import os
import sys

import mysql.connector as mysql
from espn_api.basketball import League
from espn_api.basketball.constant import POSITION_MAP, PRO_TEAM_MAP

from shared import season_calendar
from shared.my_functions import remove_name_suffixes

# ESPN pro-team abbreviation -> basketball-reference team (historical_player_data.team spelling)
ESPN_TEAM = {'ATL': 'ATLANTA_HAWKS', 'BOS': 'BOSTON_CELTICS', 'NOP': 'NEW_ORLEANS_PELICANS', 'CHI': 'CHICAGO_BULLS',
             'CLE': 'CLEVELAND_CAVALIERS', 'DAL': 'DALLAS_MAVERICKS', 'DEN': 'DENVER_NUGGETS', 'DET': 'DETROIT_PISTONS',
             'GSW': 'GOLDEN_STATE_WARRIORS', 'HOU': 'HOUSTON_ROCKETS', 'IND': 'INDIANA_PACERS',
             'LAC': 'LOS_ANGELES_CLIPPERS', 'LAL': 'LOS_ANGELES_LAKERS', 'MIA': 'MIAMI_HEAT', 'MIL': 'MILWAUKEE_BUCKS',
             'MIN': 'MINNESOTA_TIMBERWOLVES', 'BKN': 'BROOKLYN_NETS', 'NYK': 'NEW_YORK_KNICKS', 'ORL': 'ORLANDO_MAGIC',
             'PHL': 'PHILADELPHIA_76ERS', 'PHO': 'PHOENIX_SUNS', 'POR': 'PORTLAND_TRAIL_BLAZERS',
             'SAC': 'SACRAMENTO_KINGS', 'SAS': 'SAN_ANTONIO_SPURS', 'OKC': 'OKLAHOMA_CITY_THUNDER', 'UTA': 'UTAH_JAZZ',
             'WAS': 'WASHINGTON_WIZARDS', 'TOR': 'TORONTO_RAPTORS', 'MEM': 'MEMPHIS_GRIZZLIES',
             'CHA': 'CHARLOTTE_HORNETS'}


def live_name(full_name):
    """Same spelling as live_espn_players.name (pipeline/my_team_stats.py)."""
    return remove_name_suffixes(full_name).strip()


def connect():
    return mysql.connect(host=os.environ.get('sports_db_admin_host'), user=os.environ.get('sports_db_admin_user'),
                         password=os.environ.get('sports_db_admin_pw'), port=os.environ.get('sports_db_admin_port'),
                         database='basketball')


def fetch_players():
    """ESPN's fantasy player list: every NBA player with slots, pro team and injury status."""
    league = League(league_id=os.environ.get('leagueid'), espn_s2=os.environ.get('espn_s2'),
                    swid=os.environ.get('swid'), year=int(os.environ.get('season_year')))
    filters = {'players': {'filterStatus': {'value': ['FREEAGENT', 'WAIVERS', 'ONTEAM']}, 'limit': 3000,
                           'sortPercOwned': {'sortPriority': 1, 'sortAsc': False}}}
    data = league.espn_request.league_get(params={'view': 'kona_player_info', 'scoringPeriodId': league.scoringPeriodId},
                                          headers={'x-fantasy-filter': json.dumps(filters)})
    return [p['player'] for p in data.get('players', []) if p.get('player')]


def positions_rows(players):
    rows, seen = [], set()
    for p in players:
        name = live_name(p.get('fullName', ''))
        if not name or name in seen:      # primary key is the name; keep the first of any duplicate
            continue
        seen.add(name)
        slots = [POSITION_MAP.get(s, str(s)) for s in p.get('eligibleSlots', [])]
        rows.append((name, str(slots)))
    return rows


def resolve_slugs(cn, players):
    """ESPN name -> bbref slug by free_agents_backfill.match_slugs against box-score names since last season.
    A name matching several slugs keeps the one whose latest team is the player's ESPN team, else the one
    who played most recently."""
    from pipeline.free_agents_backfill import match_slugs
    season_year = int(os.environ.get('season_year'))
    since = season_calendar.season_bounds(season_year - 1)[0].date()
    cur = cn.cursor()
    cur.execute('SELECT slug, name, team, MAX(date) FROM basketball.historical_player_data WHERE date >= %s '
                'GROUP BY slug, name, team;', (since,))
    box = cur.fetchall()
    cur.execute('SELECT full_name, bbrefid FROM basketball.master_names_list_temp;')
    cw = cur.fetchall()
    cur.close()
    import pandas as pd
    box = pd.DataFrame(box, columns=['slug', 'name', 'team', 'last']).sort_values('last')
    latest = box.drop_duplicates('slug', keep='last').set_index('slug')
    # match on ESPN's full name: live_name() turns 'Jimmy Butler III' into 'Jimmy Butler I', name_key() handles III
    names = [p.get('fullName', '') for p in players]
    pairs, _, _ = match_slugs(sorted(set(names)), latest.reset_index()[['name', 'slug']],
                              pd.DataFrame(cw, columns=['full_name', 'bbrefid']))
    cands = {}
    for n, s in pairs:
        if s in latest.index:
            cands.setdefault(n, []).append(s)
    out = {}
    for p, n in zip(players, names):
        c = cands.get(n, [])
        team = ESPN_TEAM.get(PRO_TEAM_MAP.get(p.get('proTeamId')))
        same = [s for s in c if latest.loc[s, 'team'] == f'Team.{team}']
        pick = same or c
        out[p['id']] = max(pick, key=lambda s: latest.loc[s, 'last']) if pick else None
    return out


def status_rows(players, slugs, today):
    rows, seen = [], set()
    for p in players:
        if p['id'] in seen:
            continue
        seen.add(p['id'])
        team = ESPN_TEAM.get(PRO_TEAM_MAP.get(p.get('proTeamId')))
        news = p.get('lastNewsDate')
        rows.append((today, int(p['id']), live_name(p.get('fullName', ''))[:150], slugs.get(p['id']),
                     f'Team.{team}' if team else None, p.get('injuryStatus'),
                     dt.datetime.utcfromtimestamp(news / 1000) if news else None))
    return rows


def write(cn, pos_rows, st_rows, today):
    try:
        cur = cn.cursor()
        # DELETE + INSERT in one transaction (TRUNCATE can't roll back), so a failure keeps the old rows
        cur.execute('DELETE FROM basketball.espn_player_positions;')
        cur.executemany('INSERT INTO basketball.espn_player_positions (player_name, player_roles) VALUES (%s, %s);',
                        pos_rows)
        try:
            cur.execute('DELETE FROM basketball.nba_injury_status WHERE snapshot_date = %s;', (today,))
            cur.executemany('INSERT INTO basketball.nba_injury_status (snapshot_date, espn_id, player_name, slug, team, '
                            'injury_status, last_news_date) VALUES (%s, %s, %s, %s, %s, %s, %s);', st_rows)
        except mysql.errors.ProgrammingError as e:
            if e.errno != 1146:          # table missing: positions still get written
                raise
            print('nba_injury_status does not exist yet: run sql_files/migrations/2026-11-21_forecast_inputs.sql')
            st_rows = []
        cn.commit()
        cur.close()
        return len(st_rows)
    except mysql.Error:
        cn.rollback()
        raise


if __name__ == '__main__':
    today = dt.date.today()
    players = fetch_players()
    pos_rows = positions_rows(players)
    if len(pos_rows) < 300:   # a normal pull is ~1,100 active players; anything tiny means a bad response
        sys.exit(f'ESPN returned only {len(pos_rows)} players; not touching espn_player_positions.')
    cn = connect()
    try:
        slugs = resolve_slugs(cn, players)
        st_rows = status_rows(players, slugs, today)
        n_status = write(cn, pos_rows, st_rows, today)
    finally:
        cn.close()
    hurt = sum(1 for r in st_rows if r[5] not in (None, 'ACTIVE'))
    matched = sum(1 for r in st_rows if r[3])
    print(f'espn_player_positions: {len(pos_rows)} players written; nba_injury_status: {n_status} rows for {today} '
          f'({hurt} not ACTIVE, {matched} matched to a slug)')
