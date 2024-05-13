# Standard
import pandas as pd

# own functions
from my_functions import execute_query_and_fetch_df


####################################################################################################
# 000 - QUERIES
####################################################################################################


espn_query='''
SELECT 
    'history_plus_current' AS all_history,
    A.*
FROM 
    (
        SELECT  
            'current_season_only' AS current_season_vs_historicals,
            ESPN_FA.name,
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
            AND BBREF.date < '2023-10-24'
            AND BBREF.date <= '2024-04-04'
    ) A
;'''

yahoo_query='''
SELECT 
    CASE
        WHEN BBREF.date BETWEEN '2023-10-24' AND '2024-04-14' THEN 'current_season_only'
        WHEN BBREF.date < '2023-10-24' THEN 'historicals_only'
    END current_season_vs_historicals,
    'history_plus_current' AS all_history,
    YP.name,
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
    AND BBREF.date <= '2024-04-04'
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


model_eval_pred_query=f'''
SELECT 
    ME.league,
    ME.slug,
    ME.model_type,
    ME.champion_model,
    P.day,
    ME.evaluation_metric,
    ME.evaluation_metric_value,
    P.p,
    P.d,
    P.q,
    P.alpha,
    P.beta,
    P.predictions
FROM basketball.model_evaluation ME
LEFT JOIN basketball.predictions P ON ME.slug = P.slug
    AND P.league = ME.league
    AND P.model_type = ME.model_type
;'''



next_5_games_opps_qry='''
SELECT *
FROM basketball.myteam_next_5_games
;
'''


inj_prob_qry="""
SELECT *
FROM basketball.injury_probabilities;
"""

historicals_query='''
SELECT 
    HWAD.date,
    HWAD.slug,
    HWAD.name,
    HWAD.team,
    HWAD.opponent,
    HWAD.points,
    HWAD.league
FROM basketball.player_historical_web_app_display HWAD
;'''



####################################################################################################
# 000 - DEFINE AND DB CONNECT
####################################################################################################


my_safe_players=['Jayson Tatum', 'Kyrie Irving','Jaylen Brown']


def add_new_fields(df:pd.DataFrame)->pd.DataFrame:
    new_columns=['total_rebounds','minutes_played']
    df[new_columns[0]]=df['offensive_rebounds']+df['defensive_rebounds']
    df[new_columns[1]]=df['seconds_played']/60
    return df




def optimize_code(connection):
    dfs={}
    if connection.is_connected():
        fa_espn_df=execute_query_and_fetch_df(espn_query,connection)
        fa_yahoo_df=execute_query_and_fetch_df(yahoo_query, connection)
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
        model_eval_pred_df=execute_query_and_fetch_df(query=model_eval_pred_query,connection=connection)
        next_5_players_df=execute_query_and_fetch_df(query=next_5_games_opps_qry,connection=connection)
        dfs['model_eval_pred_df']=model_eval_pred_df
        dfs['next_5_players_df']=next_5_players_df

        injury_probabilities_df = execute_query_and_fetch_df(inj_prob_qry, connection)
        dfs['injury_probabilities_df']=injury_probabilities_df

        historicals_df=execute_query_and_fetch_df(historicals_query,connection)
        dfs['historicals_df']=historicals_df
    return dfs

def optimize_code_layouts(connection):
    dfs={}
    if connection.is_connected():
        fa_espn_df=execute_query_and_fetch_df(espn_query,connection)
        dfs['fa_espn_df']=fa_espn_df
        my_live_espn_df=execute_query_and_fetch_df(my_live_espn_qry,connection)
        
        my_live_yahoo_df=execute_query_and_fetch_df(my_live_yahoo_qry,connection)

        model_eval_pred_df=execute_query_and_fetch_df(query=model_eval_pred_query,connection=connection)
        next_5_players_df=execute_query_and_fetch_df(query=next_5_games_opps_qry,connection=connection)
        dfs['model_eval_pred_df']=model_eval_pred_df
        dfs['next_5_players_df']=next_5_players_df
    return dfs



