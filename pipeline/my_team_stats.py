"""
Refresh my fantasy rosters and their current-season game logs.

Four tables, two per league:

    live_espn_players   -> my_team_stats          (ESPN)
    live_yahoo_players  -> my_team_stats_yahoo    (Yahoo, off until YAHOO_ENABLED=True)

Every run, per league:
  1. Live table:  pull my current roster from the fantasy API and replace the
                  live table with exactly those names and their injury status.
  2. Stats table: for every player in the live table, pull this season's
                  regular-season game log from basketball-reference, then
                  replace the stats table with exactly those rows.

Rebuilding the stats table from the live table each run means:
  * a player I dropped disappears from the stats table,
  * a player I just added gets his whole season, not only games since the last run,
  * the first run of a new season (new `season_year`) wipes last season's rows and
    backfills the new one. There is no separate "start of season" mode.

Nothing is written until everything for that table has been fetched. If ESPN,
Yahoo or basketball-reference fails partway, the run stops and the table keeps
its previous contents. Each table is replaced inside one transaction.

Run from the repo root:
    python -m pipeline.my_team_stats
"""

import os
import time

import pandas as pd
import requests
import mysql.connector as mysql
from unidecode import unidecode

from espn_api.basketball import League
from basketball_reference_web_scraper import client
from basketball_reference_web_scraper.errors import InvalidPlayerAndSeason

from shared.my_functions import remove_name_suffixes


# Flip to True once the Yahoo NBA API approval comes through.
YAHOO_ENABLED = False

# basketball-reference starts blocking around 20 requests/min; don't lower this.
BBREF_SLEEP_SECONDS = 4

season_year = int(os.environ.get('season_year'))  # season END year, e.g. 2027 for 2026-27

config = {
	'host': os.environ.get('sports_db_admin_host'),
	'database': 'basketball',
	'user': os.environ.get('sports_db_admin_user'),
	'password': os.environ.get('sports_db_admin_pw'),
	'port': os.environ.get('sports_db_admin_port'),
}

# Column order of basketball.my_team_stats / my_team_stats_yahoo.
STATS_COLUMNS = [
	'date', 'slug', 'name', 'team', 'location', 'opponent', 'outcome',
	'seconds_played', 'made_field_goals', 'attempted_field_goals',
	'made_three_point_field_goals', 'attempted_three_point_field_goals',
	'made_free_throws', 'attempted_free_throws', 'offensive_rebounds',
	'defensive_rebounds', 'assists', 'steals', 'blocks', 'turnovers',
	'personal_fouls', 'game_score', 'points',
]
ENUM_COLUMNS = ['team', 'location', 'opponent', 'outcome']  # stored as e.g. 'Team.MIAMI_HEAT'


# ---------------------------------------------------------------------------
# Rosters (live tables)
# ---------------------------------------------------------------------------

def get_espn_roster():
	"""(name, injury_status) for my ESPN team, found by matching my SWID to the
	team owner, so it no longer depends on the team's position in league.teams.
	injury_status is ESPN's own flag: ACTIVE, OUT, DAY_TO_DAY, ..."""
	swid = os.environ.get('swid')
	league = League(league_id=os.environ.get('leagueid'), year=season_year,
					espn_s2=os.environ.get('espn_s2'), swid=swid, debug=False)

	my_id = swid.strip('{}').lower()
	mine = [t for t in league.teams
			if any(str(o.get('id', '')).strip('{}').lower() == my_id for o in (t.owners or []))]
	if len(mine) != 1:
		teams = ', '.join(f'[{i}] {t.team_name}' for i, t in enumerate(league.teams))
		raise SystemExit(f'Expected exactly one ESPN team owned by my SWID, found {len(mine)}. Teams: {teams}')

	team = mine[0]
	# Same name shape as before (suffixes stripped) so the model scripts' join on
	# basketball_references_players.BBRefName keeps working.
	players = [(remove_name_suffixes(p.name).strip(), p.injuryStatus or 'ACTIVE') for p in team.roster]
	print(f'ESPN team: {team.team_name} ({len(players)} players)')
	return players


def get_yahoo_roster():
	"""(name, injury_status) for my Yahoo team, via the logged-in user's team key in
	this season's league. Yahoo's status is '' when healthy, else e.g. 'O', 'GTD', 'INJ'."""
	from yahoo_oauth import OAuth2
	import yahoo_fantasy_api as yfa

	sc = OAuth2(None, None, from_file='oauth2.json')
	gm = yfa.Game(sc, 'nba')
	# Yahoo labels an NBA season by the year it STARTS (2024 = 2024-25); season_year is the end year.
	league_keys = gm.league_ids(year=season_year - 1)
	if not league_keys:
		raise SystemExit(f'No Yahoo NBA league found for the {season_year - 1}-{season_year % 100:02d} season.')
	lg = gm.to_league(league_keys[-1])
	tm = lg.to_team(lg.team_key())

	players = [(p['name'], p.get('status') or 'ACTIVE') for p in tm.roster()]
	print(f'Yahoo league {league_keys[-1]}, team {lg.team_key()} ({len(players)} players)')
	return players


# ---------------------------------------------------------------------------
# Game logs (stats tables)
# ---------------------------------------------------------------------------

def name_key(name):
	"""Loose key for matching fantasy names to basketball-reference names:
	accents, case, periods, apostrophes, hyphens and Jr./Sr./II/III/IV ignored."""
	s = unidecode(str(name)).lower().replace('.', '').replace("'", '').replace('-', ' ')
	return ' '.join(t for t in s.split() if t not in {'jr', 'sr', 'ii', 'iii', 'iv'})


def build_slug_lookup(cursor):
	"""name_key -> set of bbref slugs. This season's player totals cover everyone who
	has played, rookies included; the crosswalk table covers players who haven't yet."""
	lookup = {}
	totals = client.players_season_totals(season_end_year=season_year)
	for row in totals:
		lookup.setdefault(name_key(row['name']), set()).add(row['slug'])

	cursor.execute('SELECT BBRefName, BBRefID FROM basketball.basketball_references_players;')
	crosswalk = {}
	for bbref_name, slug in cursor.fetchall():
		crosswalk.setdefault(name_key(bbref_name), set()).add(slug)
	return lookup, crosswalk


def resolve_slug(name, lookup, crosswalk):
	key = name_key(name)
	for source in (lookup, crosswalk):
		slugs = source.get(key, set())
		if len(slugs) == 1:
			return next(iter(slugs))
		if len(slugs) > 1:
			print(f'  ! {name}: ambiguous basketball-reference match {sorted(slugs)}, skipped')
			return None
	print(f'  ! {name}: no basketball-reference match, skipped')
	return None


def fetch_season_game_logs(names, cursor):
	"""Current-season regular-season game log for each name, as rows in STATS_COLUMNS order.
	Raises on any HTTP failure so the caller writes nothing."""
	lookup, crosswalk = build_slug_lookup(cursor)

	frames = []
	for name in names:
		slug = resolve_slug(name, lookup, crosswalk)
		if slug is None:
			continue
		time.sleep(BBREF_SLEEP_SECONDS)
		try:
			games = pd.DataFrame(client.regular_season_player_box_scores(
				player_identifier=slug, season_end_year=season_year))
		except InvalidPlayerAndSeason:
			games = pd.DataFrame()  # bbref has no game log for him this season yet

		if 'active' in games:
			games = games[games['active'] == True]
		print(f'  {name} ({slug}): {len(games)} games')
		if games.empty:
			continue

		games = games.rename(columns={'points_scored': 'points'})
		games['slug'] = slug
		games['name'] = name  # store the live-table spelling so name joins stay exact
		for col in ENUM_COLUMNS:
			games[col] = games[col].astype(str)
		frames.append(games[STATS_COLUMNS])

	if not frames:
		return []
	df = pd.concat(frames, ignore_index=True)
	# Native Python values (no numpy ints), NaN -> NULL.
	return df.astype(object).where(pd.notna(df), None).values.tolist()


# ---------------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------------

def replace_table(connection, table, columns, rows):
	"""Make `table` contain exactly `rows`, in one transaction. DELETE rather than
	TRUNCATE because TRUNCATE commits immediately and can't be rolled back."""
	cursor = connection.cursor()
	try:
		cursor.execute(f'DELETE FROM basketball.{table};')
		if rows:
			cols = ', '.join(f'`{c}`' for c in columns)
			marks = ', '.join(['%s'] * len(columns))
			cursor.executemany(f'INSERT INTO basketball.{table} ({cols}) VALUES ({marks});', rows)
		connection.commit()
	except mysql.errors.ProgrammingError as e:
		connection.rollback()
		if e.errno == 1054 and 'injury_status' in str(e):  # unknown column
			raise SystemExit(f'basketball.{table} has no injury_status column yet; nothing was changed. Run '
							 'sql_files/migrations/2026-11-07_live_players_injury_status.sql once, then re-run.')
		raise
	except Exception:
		connection.rollback()
		raise
	finally:
		cursor.close()
	print(f'basketball.{table}: {len(rows)} rows')


def refresh_league(connection, label, get_roster, live_table, stats_table):
	print(f'\n=== {label} ===')

	# 1. Live table (name + the platform's injury status, read by the app's Injuries tab)
	players = sorted(dict(get_roster()).items())
	if not players:
		raise SystemExit(f'{label} roster came back empty; leaving {live_table} untouched.')
	replace_table(connection, live_table, ['name', 'injury_status'], [list(p) for p in players])

	# 2. Stats table, built only from the live table just written
	cursor = connection.cursor()
	cursor.execute(f'SELECT name FROM basketball.{live_table};')
	live_names = [r[0] for r in cursor.fetchall()]
	try:
		rows = fetch_season_game_logs(live_names, cursor)
	except requests.exceptions.RequestException as e:
		raise SystemExit(f'basketball-reference failed ({type(e).__name__}: {e}); '
						 f'{stats_table} left unchanged. Re-run once it is reachable.')
	finally:
		cursor.close()
	replace_table(connection, stats_table, STATS_COLUMNS, rows)


def main():
	connection = mysql.connect(**config)
	try:
		refresh_league(connection, 'ESPN', get_espn_roster,
					   'live_espn_players', 'my_team_stats')
		if YAHOO_ENABLED:
			refresh_league(connection, 'Yahoo', get_yahoo_roster,
						   'live_yahoo_players', 'my_team_stats_yahoo')
		else:
			print('\nYahoo skipped (YAHOO_ENABLED = False); live_yahoo_players and my_team_stats_yahoo untouched.')
	finally:
		connection.close()


if __name__ == '__main__':
	main()
