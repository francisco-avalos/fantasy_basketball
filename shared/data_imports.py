# Standard
import pandas as pd

# own functions
from shared.my_functions import execute_query_and_fetch_df
from shared.config import get_season_dates
from datetime import datetime

####################################################################################################
# 000 - QUERIES
####################################################################################################

season_start_str,season_end_str=get_season_dates()

# season_start_str = season_start.strftime('%Y-%m-%d')
# season_end_str = season_end.strftime('%Y-%m-%d')
# season_start_str = datetime.strptime(season_start,'%Y-%m-%d')
# season_end_str = datetime.strptime(season_end,'%Y-%m-%d')

espn_query='''
SELECT 
    'history_plus_current' AS all_history,
    A.*
FROM 
    (
        SELECT  
            'current_season_only' AS current_season_vs_historicals,
            ESPN_FA.name,
            ESPN_FA.name_code AS slug,
            ESPN_FA.date,
            ESPN_FA.team,
            ESPN_FA.location,
            ESPN_FA.opponent,
            ESPN_FA.outcome,
            ESPN_FA.seconds_played,
            ESPN_FA.made_field_goals,
            ESPN_FA.attempted_field_goals,
            ESPN_FA.made_three_point_field_goals,
            ESPN_FA.attempted_three_point_field_goals,
            ESPN_FA.made_free_throws,
            ESPN_FA.attempted_free_throws,
            ESPN_FA.offensive_rebounds,
            ESPN_FA.defensive_rebounds,
            ESPN_FA.assists,
            ESPN_FA.steals,
            ESPN_FA.blocks,
            ESPN_FA.turnovers,
            ESPN_FA.personal_fouls,
            ESPN_FA.points_scored,
            ESPN_FA.game_score
        FROM basketball.live_free_agents ESPN_FA
        UNION ALL
        SELECT 
            'historicals_only' AS current_season_vs_historicals,
            BBREF.name,
            BBREF.slug,
            BBREF.date,
            BBREF.team,
            BBREF.location,
            BBREF.opponent,
            BBREF.outcome,
            BBREF.seconds_played,
            BBREF.made_field_goals,
            BBREF.attempted_field_goals,
            BBREF.made_three_point_field_goals,
            BBREF.attempted_three_point_field_goals,
            BBREF.made_free_throws,
            BBREF.attempted_free_throws,
            BBREF.offensive_rebounds,
            BBREF.defensive_rebounds,
            BBREF.assists,
            BBREF.steals,
            BBREF.blocks,
            BBREF.turnovers,
            BBREF.personal_fouls,
            BBREF.points AS points_scored,
            BBREF.game_score
        FROM basketball.historical_player_data BBREF
        WHERE BBREF.slug IN (SELECT DISTINCT name_code FROM basketball.live_free_agents)
            AND BBREF.date NOT BETWEEN LAST_DAY(DATE_FORMAT(BBREF.date, '%Y-04-%d')) AND LAST_DAY(DATE_FORMAT(BBREF.date, '%Y-09-%d'))
            AND BBREF.date < %s #'2024-10-22'
    ) A
;'''

yahoo_query='''
SELECT 
    CASE
        WHEN BBREF.date BETWEEN %s AND %s THEN 'current_season_only'
        WHEN BBREF.date < %s THEN 'historicals_only'
    END current_season_vs_historicals,
    -- CASE
    --     WHEN BBREF.date BETWEEN '2024-10-22' AND '2025-04-13' THEN 'current_season_only'
    --     WHEN BBREF.date < '2024-10-22' THEN 'historicals_only'
    -- END current_season_vs_historicals,
    'history_plus_current' AS all_history,
    YP.name,
    BBREF.slug,
    BBREF.date,
    BBREF.team,
    BBREF.location,
    BBREF.opponent,
    BBREF.outcome,
    BBREF.seconds_played,
    BBREF.made_field_goals,
    BBREF.attempted_field_goals,
    BBREF.made_three_point_field_goals,
    BBREF.attempted_three_point_field_goals,
    BBREF.made_free_throws,
    BBREF.attempted_free_throws,
    BBREF.offensive_rebounds,
    BBREF.defensive_rebounds,
    BBREF.assists,
    BBREF.steals,
    BBREF.blocks,
    BBREF.turnovers,
    BBREF.personal_fouls,
    BBREF.points AS points_scored,
    BBREF.game_score
FROM basketball.live_free_agents_yahoo YP
JOIN basketball.master_names_list_temp MNL ON SUBSTRING_INDEX(YP.name, ' ',1) = MNL.first_name
    AND (CASE WHEN LENGTH(YP.name)-LENGTH(REPLACE(YP.name, ' ', ''))+1 > 2 THEN SUBSTRING_INDEX(SUBSTRING_INDEX(YP.name, ' ',-2), ' ', 1) ELSE SUBSTRING_INDEX(YP.name, ' ',-1) END) = MNL.last_name
    AND (CASE WHEN LENGTH(YP.name)-LENGTH(REPLACE(YP.name, ' ', ''))+1 > 2 THEN SUBSTRING_INDEX(SUBSTRING_INDEX(YP.name, ' ',-2), ' ', -1) ELSE '' END) = MNL.suffix
JOIN basketball.historical_player_data BBREF ON MNL.bbrefid = BBREF.slug
WHERE BBREF.date NOT BETWEEN LAST_DAY(DATE_FORMAT(BBREF.date, '%Y-04-%d')) AND LAST_DAY(DATE_FORMAT(BBREF.date, '%Y-09-%d'))
    AND BBREF.date <= %s
;'''


my_espn_team_qry='''
SELECT 
    MTS.*, 
    DATE_FORMAT(MTS.date, '%W') AS day_of_week,
    CASE
        WHEN DATE_FORMAT(MTS.date, '%W') IN ('Saturday', 'Sunday') THEN 'week_end'
        ELSE 'week_day'
    END AS day_of_week_class,
    C.week_starting_monday, 
    C.week_ending_sunday 
FROM basketball.my_team_stats MTS 
JOIN basketball.calendar C ON MTS.date=C.day;
'''

my_yahoo_team_qry='''
SELECT 
    MTS.*, 
    DATE_FORMAT(MTS.date, '%W') AS day_of_week,
    CASE
        WHEN DATE_FORMAT(MTS.date, '%W') IN ('Saturday', 'Sunday') THEN 'week_end'
        ELSE 'week_day'
    END AS day_of_week_class,
    C.week_starting_monday, 
    C.week_ending_sunday 
FROM basketball.my_team_stats_yahoo MTS
JOIN basketball.calendar C ON MTS.date=C.day
WHERE name IN (SELECT DISTINCT name FROM basketball.live_yahoo_players);
'''


my_live_espn_qry='''
SELECT 
    LEP.name,
    BRP.BBRefID AS slug
FROM basketball.live_espn_players LEP
JOIN basketball.basketball_references_players BRP ON LEP.name = BBRefName
;'''

my_live_yahoo_qry='''
SELECT 
    LYP.name,
    BRP.BBRefID AS slug
FROM basketball.live_yahoo_players LYP
JOIN basketball.basketball_references_players BRP ON LYP.name = BBRefName
;'''


inj_prob_qry="""
SELECT
    injury,
    days,
    CONCAT(ROUND(probabilities * 100,2),'%') AS probabilities
FROM basketball.injury_probabilities;
"""


# ---- Fantasy Predictions page (app/predictions.py), written by pipeline/points_forecast.py ----
# Tables from sql_files/migrations/2026-11-11_points_forecasts.sql. The page reads the latest run.

forecast_roster_qry='''
SELECT league, name, slug, positions, team, injury_status, run_date
FROM basketball.forecast_roster
;'''

forecast_runs_qry='''
SELECT run_date, slug, model, label, family, params, n_games, n_origins, mae, mae_h1, mae_h2, mae_h3,
       mae_h4, mae_h5, skill, aicc, ljung_box_p, champion, champion_reason
FROM basketball.model_runs
WHERE run_date = (SELECT MAX(run_date) FROM basketball.model_runs)
;'''

forecast_latest_qry='''
SELECT run_date, slug, model, horizon, game_date, team, opponent, home, rest_days, opp_def_rank,
       prediction, lo80, hi80, champion, p_play, expected_points, play_note
FROM basketball.points_forecasts
WHERE run_date = (SELECT MAX(run_date) FROM basketball.points_forecasts)
;'''

# every logged forecast whose game has been played, scored against the box score
forecast_live_qry='''
SELECT F.slug, F.model, COUNT(*) AS n_scored,
       AVG(ABS(F.prediction - H.points)) AS live_mae,
       AVG(CASE WHEN H.points BETWEEN F.lo80 AND F.hi80 THEN 1 ELSE 0 END) AS live_coverage
FROM basketball.points_forecasts F
JOIN basketball.historical_player_data H ON H.slug = F.slug AND H.date = F.game_date
WHERE H.seconds_played > 0
GROUP BY F.slug, F.model
;'''

forecast_history_qry='''
SELECT H.date, H.slug, H.team, H.opponent, H.location, H.points, H.seconds_played / 60 AS minutes
FROM basketball.historical_player_data H
WHERE H.slug IN (SELECT slug FROM basketball.forecast_roster)
  AND H.seconds_played > 0
  AND H.date >= DATE_SUB(CURDATE(), INTERVAL 450 DAY)
ORDER BY H.slug, H.date
;'''

# latest live drift check of the forecasts (pipeline/forecast_drift_monitor.py; empty before
# sql_files/migrations/2026-11-22_forecast_model_monitoring.sql or the first run)
forecast_health_qry='''
SELECT run_date, check_name, unit, metric, value, status, detail
FROM basketball.forecast_model_monitoring
WHERE run_date = (SELECT MAX(run_date) FROM basketball.forecast_model_monitoring);
'''

# champion forecasts for the AI assistant's context
forecast_champion_qry='''
SELECT R.league, R.name, F.slug, F.horizon, F.game_date, F.opponent, F.home, F.prediction, F.lo80, F.hi80, F.model
FROM basketball.points_forecasts F
JOIN basketball.forecast_roster R ON R.slug = F.slug
WHERE F.champion = 1 AND F.run_date = (SELECT MAX(run_date) FROM basketball.points_forecasts)
ORDER BY R.league, R.name, F.horizon
;'''


# ---- Current Team Performance page (app/team_performance.py) ----

# Per-player season totals for every NBA player this season: the league baseline
# the category-value heatmap compares my players against. Aggregated in SQL so the
# app never holds the full box-score table.
league_totals_qry='''
SELECT
    slug,
    COUNT(*)                               AS gp,
    SUM(seconds_played) / 60               AS minutes_played,
    SUM(made_field_goals)                  AS made_field_goals,
    SUM(attempted_field_goals)             AS attempted_field_goals,
    SUM(made_free_throws)                  AS made_free_throws,
    SUM(attempted_free_throws)             AS attempted_free_throws,
    SUM(made_three_point_field_goals)      AS made_three_point_field_goals,
    SUM(attempted_three_point_field_goals) AS attempted_three_point_field_goals,
    SUM(offensive_rebounds + defensive_rebounds) AS total_rebounds,
    SUM(assists)                           AS assists,
    SUM(steals)                            AS steals,
    SUM(blocks)                            AS blocks,
    SUM(points)                            AS points,
    SUM(turnovers)                         AS turnovers
FROM basketball.historical_player_data
WHERE date >= %s
GROUP BY slug;
'''

# Numeric survival curves (inj_prob_qry above formats them as text for the old table).
injury_curves_qry='''
SELECT injury, days, probabilities
FROM basketball.injury_probabilities
ORDER BY injury, days;
'''

# The published curves' last refit (pipeline/injury_probabilities_basketball.py) and the latest weekly drift
# checks (pipeline/injury_drift_monitor.py), for the Injuries tab's model-health badge. Both tables come from
# sql_files/migrations/2026-11-20_injury_model_monitoring.sql; before it, these come back empty.
injury_refit_qry='''
SELECT run_date, model
FROM basketball.injury_model_evaluations
WHERE source = 'refit'
ORDER BY run_date DESC
LIMIT 1;
'''

injury_health_qry='''
SELECT run_date, check_name, unit, metric, status, detail
FROM basketball.injury_model_monitoring
WHERE run_date = (SELECT MAX(run_date) FROM basketball.injury_model_monitoring);
'''

# One survival curve per player currently out, from that absence's own inputs (pipeline/injury_player_curves.py,
# nightly; sql_files/migrations/2026-11-21_forecast_inputs.sql). Empty before the migration.
injury_player_curves_qry='''
SELECT slug, player_name, start_date, days_out, curve_group, model, days, probabilities
FROM basketball.injury_player_curves;
'''

# The same curves for ESPN free agents (live_free_agents.name_code is the bbref slug), for the screener.
fa_injury_curves_qry='''
SELECT F.name, C.slug, C.start_date, C.days_out, C.curve_group, C.days, C.probabilities
FROM basketball.injury_player_curves C
JOIN (SELECT DISTINCT name, name_code FROM basketball.live_free_agents) F ON F.name_code = C.slug;
'''

# Normalized injury note -> taxonomy labels (shared/injury_taxonomy.py), from pipeline/injury_mapping.py.
injury_notes_qry='''
SELECT note_key, category, body_region, injury_type, non_medical_reason
FROM basketball.injury_note_classification;
'''

# ESPN position eligibility for my roster: player_roles is ESPN's eligibleSlots as a Python list literal,
# e.g. "['PG', 'SG', 'G', 'UT', 'BE', 'IR']", written by pipeline/espn_player_positions.py.
espn_positions_qry='''
SELECT p.player_name AS name, p.player_roles
FROM basketball.espn_player_positions p
JOIN basketball.live_espn_players l ON l.name = p.player_name;
'''

# Every active ESPN player's eligibility (names in the live-table spelling, suffixes stripped), for the
# screener's position column; matched to free agents with shared.my_functions.name_key.
all_positions_qry='''
SELECT player_name AS name, player_roles
FROM basketball.espn_player_positions;
'''

# The latest daily ESPN injury snapshot (pipeline/espn_player_positions.py), keyed by bbref slug.
fa_status_qry='''
SELECT slug, injury_status, snapshot_date
FROM basketball.nba_injury_status
WHERE snapshot_date = (SELECT MAX(snapshot_date) FROM basketball.nba_injury_status)
    AND slug IS NOT NULL;
'''

# Fantasy-platform injury status, written by pipeline/my_team_stats.py.
# This season's prosportstransactions moves: relinquished = placed on IL / ruled out,
# acquired = activated. Used to find each injured player's note and days out.
injury_moves_qry='''
SELECT day, team, acquired, relinquished, notes
FROM basketball.hist_player_inj
WHERE day >= %s;
'''


####################################################################################################
# 000 - DEFINE AND DB CONNECT
####################################################################################################


def add_new_fields(df:pd.DataFrame)->pd.DataFrame:
    new_columns=['total_rebounds','minutes_played']
    df[new_columns[0]]=df['offensive_rebounds']+df['defensive_rebounds']
    df[new_columns[1]]=df['seconds_played']/60
    return df



def optimize_code(connection):
    dfs={}
    if connection.is_connected():
        fa_espn_df=execute_query_and_fetch_df(espn_query,connection,season_start_str)
        fa_yahoo_df=execute_query_and_fetch_df(yahoo_query, connection,season_start_str,season_end_str,season_start_str,season_end_str)
        dfs['fa_espn_df']=fa_espn_df
        dfs['fa_yahoo_df']=fa_yahoo_df

        myteam_df=execute_query_and_fetch_df(my_espn_team_qry,connection)
        myteam_df=add_new_fields(myteam_df)
        dfs['myteam_df']=myteam_df

        myteam_df_yh=execute_query_and_fetch_df(my_yahoo_team_qry,connection)
        myteam_df_yh=add_new_fields(myteam_df_yh)
        dfs['myteam_df_yh']=myteam_df_yh

        my_live_espn_df=execute_query_and_fetch_df(my_live_espn_qry,connection)
        my_live_yahoo_df=execute_query_and_fetch_df(my_live_yahoo_qry,connection)
        dfs['my_live_espn_df']=my_live_espn_df
        dfs['my_live_yahoo_df']=my_live_yahoo_df

        current_players=my_live_espn_df['name'].values.tolist()
        dfs['current_players']=current_players
        forecast_champion_df=execute_query_and_fetch_df(forecast_champion_qry, connection)
        dfs['forecast_champion_df']=forecast_champion_df if forecast_champion_df is not None else pd.DataFrame()

        injury_probabilities_df = execute_query_and_fetch_df(inj_prob_qry, connection)
        dfs['injury_probabilities_df']=injury_probabilities_df
    return dfs

def screener_data(connection):
    """Extra frames for the Free Agent Screener (app/screener.py): every ESPN player's position
    eligibility and the latest ESPN injury snapshot. A failed query comes back empty."""
    def fetch(query):
        df=execute_query_and_fetch_df(query, connection)
        return df if df is not None else pd.DataFrame()
    return {
        'positions_df': fetch(all_positions_qry),
        'status_df':    fetch(fa_status_qry),
    }


def forecast_page_data(connection):
    """Frames for the Fantasy Predictions page. A failed query (tables not migrated yet) comes back
    empty, so the page shows a message instead of failing at import."""
    def fetch(query):
        df=execute_query_and_fetch_df(query, connection)
        return df if df is not None else pd.DataFrame()
    return {
        'roster_df': fetch(forecast_roster_qry),
        'runs_df': fetch(forecast_runs_qry),
        'forecasts_df': fetch(forecast_latest_qry),
        'live_df': fetch(forecast_live_qry),
        'history_df': fetch(forecast_history_qry),
        'health_df': fetch(forecast_health_qry),
    }


def team_performance_data(connection):
    """Extra frames for the Current Team Performance page. Any query that fails
    (e.g. the injury_status column not migrated yet) comes back as an empty frame,
    so the page degrades to a message instead of failing at import."""
    def fetch(query, *params):
        df=execute_query_and_fetch_df(query, connection, *params)
        return df if df is not None else pd.DataFrame()
    def status(table):
        # Before the injury_status migration the column doesn't exist: fall back to names only.
        df=fetch(f'SELECT name, injury_status FROM basketball.{table};')
        return df if not df.empty else fetch(f'SELECT name FROM basketball.{table};')
    return {
        'league_totals_df': fetch(league_totals_qry, season_start_str),
        'injury_curves_df': fetch(injury_curves_qry),
        'espn_status_df':   status('live_espn_players'),
        'yahoo_status_df':  status('live_yahoo_players'),
        'injury_moves_df':  fetch(injury_moves_qry, season_start_str),
        # note -> taxonomy labels written by pipeline/injury_mapping.py (empty before the 2026-11-08 migration)
        'injury_notes_df':  fetch(injury_notes_qry),
        'espn_positions_df': fetch(espn_positions_qry),
        'injury_refit_df':  fetch(injury_refit_qry),
        'injury_health_df': fetch(injury_health_qry),
        'player_curves_df': fetch(injury_player_curves_qry),
        'fa_curves_df':     fetch(fa_injury_curves_qry),
        'forecast_roster_df': fetch(forecast_roster_qry),     # live_* name -> slug, per league
    }



