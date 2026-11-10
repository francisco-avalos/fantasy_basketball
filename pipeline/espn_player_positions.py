"""
ESPN position eligibility for every active NBA player -> basketball.espn_player_positions.

One request: ESPN's pro-players list (the same call espn-api makes to build league.player_map)
already carries each player's eligibleSlots, so there is no per-player lookup and no sleep.
(This used to call league.player_info() once per player with a 4 s sleep: ~30 min for ~450
players, now about 2 s for ~1,100.)

player_name is stored in the live_espn_players spelling (suffixes stripped, as in
pipeline/my_team_stats.py) because the app joins the two tables on name.
player_roles is the eligible-slot list as a Python list literal, e.g. "['PG', 'SG', 'G', 'UT', 'BE', 'IR']";
app/team_performance.py parses it with ast.literal_eval.

Run from the repo root:
    python -m pipeline.espn_player_positions
"""
import os
import sys

import mysql.connector as mysql
from espn_api.basketball import League
from espn_api.basketball.constant import POSITION_MAP

from shared.my_functions import remove_name_suffixes


def live_name(full_name):
    """Same spelling as live_espn_players.name (pipeline/my_team_stats.py)."""
    return remove_name_suffixes(full_name).strip()


def fetch_positions():
    league = League(league_id=os.environ.get('leagueid'), espn_s2=os.environ.get('espn_s2'),
                    swid=os.environ.get('swid'), year=int(os.environ.get('season_year')))
    players = league.espn_request.get_pro_players()
    rows, seen = [], set()
    for p in players:
        name = live_name(p.get('fullName', ''))
        if not name or name in seen:      # primary key is the name; keep the first of any duplicate
            continue
        seen.add(name)
        slots = [POSITION_MAP.get(s, str(s)) for s in p.get('eligibleSlots', [])]
        rows.append((name, str(slots)))
    return rows


def write(rows):
    cn = mysql.connect(host=os.environ.get('sports_db_admin_host'), user=os.environ.get('sports_db_admin_user'),
                       password=os.environ.get('sports_db_admin_pw'), port=os.environ.get('sports_db_admin_port'),
                       database='basketball')
    try:
        cur = cn.cursor()
        # DELETE + INSERT in one transaction (TRUNCATE can't roll back), so a failure keeps the old rows
        cur.execute('DELETE FROM basketball.espn_player_positions;')
        cur.executemany('INSERT INTO basketball.espn_player_positions (player_name, player_roles) VALUES (%s, %s);',
                        rows)
        cn.commit()
        cur.close()
    except mysql.Error:
        cn.rollback()
        raise
    finally:
        cn.close()


if __name__ == '__main__':
    rows = fetch_positions()
    if len(rows) < 300:   # a normal pull is ~1,100 active players; anything tiny means a bad response
        sys.exit(f'ESPN returned only {len(rows)} players; not touching espn_player_positions.')
    write(rows)
    print(f'espn_player_positions: {len(rows)} players written')
