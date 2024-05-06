
import os
import mysql.connector as mysql
from mysql.connector import pooling
import pandas as pd

import my_functions as mf


# prod env 
sports_db_admin_host=os.environ.get('basketball_host')
sports_db_admin_db=os.environ.get('basketball_db')
sports_db_admin_user=os.environ.get('basketball_user')
sports_db_admin_pw=os.environ.get('basketball_pw')
sports_db_admin_port=os.environ.get('basketball_port')


# # dev env
# sports_db_admin_host=os.environ.get('sports_db_admin_host')
# sports_db_admin_db='basketball'
# sports_db_admin_user=os.environ.get('sports_db_admin_user')
# sports_db_admin_pw=os.environ.get('sports_db_admin_pw')
# sports_db_admin_port=os.environ.get('sports_db_admin_port')

dbconfig = {
    "host":sports_db_admin_host,
    "database":sports_db_admin_db,
    "user":sports_db_admin_user,
    "password":sports_db_admin_pw,
    "port":sports_db_admin_port
}

connection_pool = pooling.MySQLConnectionPool(
    pool_name="sports_db_pool",
    pool_size=5,
    **dbconfig
)


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
    ) A
;
'''

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
;
'''


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


##
my_live_espn_qry='''
SELECT 
    LEP.name,
    BRP.BBRefID AS slug
FROM basketball.live_espn_players LEP
JOIN basketball.basketball_references_players BRP ON LEP.name = BBRefName
;
'''

my_live_yahoo_qry='''
SELECT 
    LYP.name,
    BRP.BBRefID AS slug
FROM basketball.live_yahoo_players LYP
JOIN basketball.basketball_references_players BRP ON LYP.name = BBRefName
;
'''


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
;
'''


next_5_games_opps_qry='''
SELECT
    date,
    @day := @day +1 AS day,
    slug,
    team,
    opponent,
    location,
    CASE
        WHEN SUBSTRING_INDEX(location,'.',-1) = 'HOME' THEN REPLACE(opponent,'Team.','')
        WHEN SUBSTRING_INDEX(location,'.',-1) = 'AWAY' THEN CONCAT('@',REPLACE(opponent,'Team.',''))
    END AS opponent_location,
    points
FROM basketball.historical_player_data, (SELECT @day := 0) AS init
WHERE slug = '{p}'
    AND date > '2024-04-04'
LIMIT 5
;
'''

##







my_injured_espn_team_qry='''
SELECT 
    name,
    injury,
    news_date,
    exp_return_date 
FROM basketball.injured_player_news 
ORDER BY exp_return_date ASC;
'''

my_injured_yahoo_team_qry='''
SELECT 
    name,
    injury,
    news_date,
    exp_return_date 
FROM basketball.injured_player_news_yh 
ORDER BY exp_return_date ASC;
'''



# predictions_query='''
# SELECT *
# FROM basketball.predictions
# WHERE slug = 'wagnemo01'
# ;
# '''

# model_eval_query='''
# SELECT *
# FROM basketball.model_evaluation
# WHERE slug = 'wagnemo01'
# ;
# '''


p = ''
my_espn_players_sched_query='''
SELECT
    name,
    team,
    TSCHED.*
FROM basketball.my_team_stats MTS
JOIN basketball.high_level_nba_team_schedules TSCHED ON MTS.team = TSCHED.away_team OR MTS.team = TSCHED.home_team
JOIN basketball.calendar CAL ON DATE(SUBDATE(CAST(TSCHED.start_time AS DATETIME), INTERVAL 8 HOUR)) = CAL.day
WHERE MTS.name LIKE CONCAT("%", "{p}","%")
    AND CURDATE() BETWEEN CAL.week_starting_monday AND CAL.week_ending_sunday
GROUP BY MTS.name, TSCHED.start_time;
'''

my_yahoo_players_sched_query='''
SELECT
    name,
    team,
    TSCHED.*
FROM basketball.my_team_stats_yahoo MTS
JOIN basketball.high_level_nba_team_schedules TSCHED ON MTS.team = TSCHED.away_team OR MTS.team = TSCHED.home_team
JOIN basketball.calendar CAL ON DATE(SUBDATE(CAST(TSCHED.start_time AS DATETIME), INTERVAL 8 HOUR)) = CAL.day
WHERE MTS.name LIKE CONCAT("%", "{p}","%")
    AND CURDATE() BETWEEN CAL.week_starting_monday AND CAL.week_ending_sunday
    AND name IN (SELECT DISTINCT name FROM basketball.live_yahoo_players)
GROUP BY MTS.name, TSCHED.start_time;
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
;
'''



my_safe_players=['Jayson Tatum', 'Kyrie Irving','Jaylen Brown']


def clean_player_names(player_list:list)->list:
    cleaned_names=[mf.remove_name_suffixes(x.replace("'","").strip()) for x in player_list]
    return cleaned_names

def add_new_fields(df:pd.DataFrame)->pd.DataFrame:
    new_columns=['total_rebounds','minutes_played']
    df[new_columns[0]]=df['offensive_rebounds']+df['defensive_rebounds']
    df[new_columns[1]]=df['seconds_played']/60
    return df

def new_fetch_players_df(query,connection,players):
    df_list=[]
    for p in players:
        df_list.append(mf.execute_query_and_fetch_player_df(query=query,connection=connection,p=p))
    return pd.concat(df_list,ignore_index=True)


def optimize_code():
    with connection_pool.get_connection() as connection:
        dfs={}
        if connection.is_connected():
            fa_espn_df=mf.execute_query_and_fetch_df(espn_query,connection)
            fa_yahoo_df=mf.execute_query_and_fetch_df(yahoo_query, connection)
            dfs['fa_espn_df']=fa_espn_df
            dfs['fa_yahoo_df']=fa_yahoo_df

            myteam_df=mf.execute_query_and_fetch_df(my_espn_team_qry,connection)
            myteam_df=add_new_fields(myteam_df)
            dfs['myteam_df']=myteam_df

            myteam_df_yh=mf.execute_query_and_fetch_df(my_yahoo_team_qry,connection)
            myteam_df_yh=add_new_fields(myteam_df_yh)
            dfs['myteam_df_yh']=myteam_df_yh

            live_yahoo_players_df=mf.execute_query_and_fetch_df(my_live_yahoo_qry,connection)
            inj_df=mf.execute_query_and_fetch_df(my_injured_espn_team_qry,connection)
            inj_df_yf=mf.execute_query_and_fetch_df(my_injured_yahoo_team_qry,connection)
            dfs['live_yahoo_players_df']=live_yahoo_players_df
            dfs['inj_df']=inj_df
            dfs['inj_df_yf']=inj_df_yf

            my_live_espn_df=mf.execute_query_and_fetch_df(my_live_espn_qry,connection)
            my_live_yahoo_df=mf.execute_query_and_fetch_df(my_live_yahoo_qry,connection)
            dfs['my_live_espn_df']=my_live_espn_df
            dfs['my_live_yahoo_df']=my_live_yahoo_df

            current_players=my_live_espn_df['name'].values.tolist()
            players_at_risk=list(set(current_players)-set(my_safe_players))
            players_at_risk_spec=pd.DataFrame({'Name':players_at_risk},index=None)
            players_at_risk_df=pd.DataFrame({'Name':players_at_risk},index=None)
            dfs['players_at_risk']=players_at_risk_spec
            dfs['current_players']=current_players
            dfs['players_at_risk_df']=players_at_risk_df

            current_players_yh=clean_player_names(live_yahoo_players_df['name'].tolist())
            current_players_yh_at_risk_df=pd.DataFrame({'Name':current_players_yh})
            dfs['current_players_yh_at_risk_df']=current_players_yh_at_risk_df

            df_for_agg=new_fetch_players_df(query=my_espn_players_sched_query,connection=connection,players=current_players)
            df_yh_for_agg=new_fetch_players_df(query=my_yahoo_players_sched_query,connection=connection,players=current_players_yh)
            dfs['df_for_agg']=df_for_agg
            dfs['df_yh_for_agg']=df_yh_for_agg

            unique_current_players=set(my_live_espn_df['slug'].tolist() + my_live_yahoo_df['slug'].tolist())
            model_eval_pred_df=new_fetch_players_df(query=model_eval_pred_query,connection=connection,players=unique_current_players)
            next_5_players_df=new_fetch_players_df(query=next_5_games_opps_qry,connection=connection,players=unique_current_players)
            dfs['model_eval_pred_df']=model_eval_pred_df
            dfs['next_5_players_df']=next_5_players_df

            injury_probabilities_df = mf.execute_query_and_fetch_df(inj_prob_qry, connection)
            dfs['injury_probabilities_df']=injury_probabilities_df

            historicals_df=mf.execute_query_and_fetch_df(historicals_query,connection)
            dfs['historicals_df']=historicals_df

        return dfs