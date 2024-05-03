
import os
import dash
from dash.dependencies import Input, Output

import mysql.connector as mysql
from mysql.connector import pooling
import pandas as pd
import datetime as dt
from dash_create import app
import plotly.express as px
import plotly.graph_objects as go

import logging

import random

# ESPN 
from espn_api.basketball import League

from my_functions import clean_string, remove_name_suffixes,execute_query_and_fetch_df,execute_query_and_fetch_player_df



####################################################################################################
# 000 - IMPORT DATA FROM DB - FREE AGENT SCREEN TOOL
####################################################################################################


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

# leagueid=os.environ.get('leagueid')
# espn_s2=os.environ.get('espn_s2')
# swid=os.environ.get('swid')


# # espn connect
# league=League(league_id=leagueid, 
#                 year=2024,
#                 espn_s2=espn_s2,
#                 swid=swid, 
#                 debug=False)

# connection=mysql.connect(host=sports_db_admin_host,
#                         database=sports_db_admin_db,
#                         user=sports_db_admin_user,
#                         password=sports_db_admin_pw,
#                         port=sports_db_admin_port)


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

inj_prob_qry="""
SELECT *
FROM basketball.injury_probabilities;
"""

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

my_live_yahoo_qry='''
SELECT * 
FROM basketball.live_yahoo_players
;
'''

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


# SELECT
#     DATE(SUBDATE(TSCHED.start_time,INTERVAL 8 HOUR)) AS start_time_pst,
#     REPLACE(REPLACE(TSCHED.away_team,'Team.',''),'_',' ') AS away_team,
#     REPLACE(REPLACE(TSCHED.home_team,'Team.',''),'_',' ') AS home_team,
#     TSCHED.away_team_score,
#     TSCHED.home_team_score,
#     CASE
#         WHEN TSCHED.away_team = HPD.team AND (TSCHED.away_team_score - TSCHED.home_team_score) > 0 THEN 'WIN'
#         WHEN TSCHED.home_team = HPD.team AND (TSCHED.away_team_score - TSCHED.home_team_score) > 0 THEN 'WIN'
#         WHEN TSCHED.away_team = HPD.team AND (TSCHED.away_team_score - TSCHED.home_team_score) < 0 THEN 'LOST'
#         WHEN TSCHED.home_team = HPD.team AND (TSCHED.away_team_score - TSCHED.home_team_score) < 0 THEN 'LOST'
#     END AS players_team_game_outcome,
#     HPD.slug,
#     REPLACE(REPLACE(HPD.team,'Team.',''),'_',' ') AS team,
#     REPLACE(HPD.location,'Location.','') AS location,
#     REPLACE(REPLACE(HPD.opponent,'Team.',''),'_',' ') AS opponent,
#     HPD.points,
#     REPLACE(REPLACE(CT.current_team,'Team.',''),'_',' ') AS players_current_team,
#     IF(REPLACE(REPLACE(CT.current_team,'Team.',''),'_',' ') = REPLACE(REPLACE(TSCHED.away_team,'Team.',''),'_',' '), REPLACE(REPLACE(TSCHED.home_team,'Team.',''),'_',' '),REPLACE(REPLACE(TSCHED.away_team,'Team.',''),'_',' ')) AS opponent_team,
#     CASE
#         WHEN ESPN.name IS NOT NULL THEN 'espn'
#         WHEN Yahoo.name IS NOT NULL THEN 'yahoo'
#     END AS league
# FROM basketball.high_level_nba_team_schedules TSCHED
# LEFT JOIN basketball.historical_player_data HPD ON (HPD.team = TSCHED.away_team OR HPD.team = TSCHED.home_team)
#     AND DATE(SUBDATE(TSCHED.start_time, INTERVAL 8 HOUR)) = HPD.date
#     AND HPD.slug = '{p}'
# LEFT JOIN (SELECT SUBSTRING_INDEX(GROUP_CONCAT(DISTINCT team ORDER BY DATE DESC SEPARATOR '; '), '; ',1) AS current_team FROM basketball.historical_player_data WHERE slug = '{p}') CT ON 1=1
# LEFT JOIN basketball.live_espn_players ESPN ON HPD.name = ESPN.name
# LEFT JOIN basketball.live_yahoo_players Yahoo ON HPD.name = Yahoo.name
# WHERE TSCHED.away_team IN (SELECT
#                         SUBSTRING_INDEX(GROUP_CONCAT(DISTINCT team ORDER BY DATE DESC SEPARATOR '; '), '; ',1) AS current_team
#                     FROM basketball.historical_player_data
#                     WHERE slug = '{p}')
#     OR TSCHED.home_team IN (SELECT 
#                         SUBSTRING_INDEX(GROUP_CONCAT(DISTINCT team ORDER BY DATE DESC SEPARATOR '; '), '; ',1) AS current_team
#                     FROM basketball.historical_player_data
#                     WHERE slug = '{p}')
# ORDER BY TSCHED.start_time DESC
# ;


predictions_query='''
SELECT *
FROM basketball.predictions
WHERE slug = 'wagnemo01'
;
'''

model_eval_query='''
SELECT *
FROM basketball.model_evaluation
WHERE slug = 'wagnemo01'
'''

## 
my_live_espn_qry='''
SELECT 
    LEP.name,
    BRP.BBRefID AS slug
FROM basketball.live_espn_players LEP
JOIN basketball.basketball_references_players BRP ON LEP.name = BRP.BBRefName
;
'''

my_live_yahoo_qry='''
SELECT 
    LYP.name,
    BRP.BBRefID AS slug
FROM basketball.live_yahoo_players LYP
JOIN basketball.basketball_references_players BRP ON LYP.name = BRP.BBRefName
;
'''


model_eval_pred_query='''
SELECT 
    ME.league,
    ME.slug,
    ME.model_type,
    ME.champion_model,
    ME.evaluation_metric,
    ME.evaluation_metric_value,
    P.day,
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
WHERE ME.slug = '{p}'
;
'''
## 


my_safe_players=['Jayson Tatum', 'Kyrie Irving','Jaylen Brown']


with connection_pool.get_connection() as connection:
    if connection.is_connected():
        fa_espn_df = execute_query_and_fetch_df(espn_query, connection)
        fa_yahoo_df = execute_query_and_fetch_df(yahoo_query, connection)
        injury_probabilities_df = execute_query_and_fetch_df(inj_prob_qry, connection)
        
        myteam_df = execute_query_and_fetch_df(my_espn_team_qry, connection)
        myteam_df['total_rebounds']=myteam_df['offensive_rebounds']+myteam_df['defensive_rebounds']
        myteam_df['minutes_played']=myteam_df['seconds_played']/60

        myteam_df_yh = execute_query_and_fetch_df(my_yahoo_team_qry, connection)
        myteam_df_yh['total_rebounds']=myteam_df_yh['offensive_rebounds']+myteam_df_yh['defensive_rebounds']
        myteam_df_yh['minutes_played']=myteam_df_yh['seconds_played']/60

        live_yahoo_players_df = execute_query_and_fetch_df(my_live_yahoo_qry, connection)
        inj_df = execute_query_and_fetch_df(my_injured_espn_team_qry, connection)
        inj_df_yf = execute_query_and_fetch_df(my_injured_yahoo_team_qry, connection)


        #### NEW SECTION

        my_live_espn_df=execute_query_and_fetch_df(my_live_espn_qry,connection)
        my_live_yahoo_df=execute_query_and_fetch_df(my_live_yahoo_qry,connection)
        #### NEW SECTION

        ####################### REWRITE SECTION
        # myteam=league.teams[10]
        # current_players=clean_string(myteam.roster).split(',')
        # current_players=[remove_name_suffixes(x) for x in current_players]
        # current_players=[x.strip(' ') for x in current_players]
        current_players=my_live_espn_df['name'].values.tolist()

        players_at_risk=list(set(current_players)-set(my_safe_players))
        players_at_risk=pd.DataFrame(players_at_risk)
        players_at_risk.columns=['Name']
        players_at_risk_df = pd.DataFrame(players_at_risk, columns=['Name'])

        df_for_agg_list=[]
        for p in current_players:
            df_for_agg_list.append(execute_query_and_fetch_player_df(query=my_espn_players_sched_query,connection=connection,p=p))
        df_for_agg=pd.concat(df_for_agg_list, ignore_index=True)
        # df_for_agg = pd.concat([execute_query_and_fetch_player_df(my_espn_players_sched_query, connection,p=p) for p in current_players])

        current_players_yh=live_yahoo_players_df.name.tolist()
        current_players_yh=clean_string(current_players_yh).split(',')
        current_players_yh=[remove_name_suffixes(x) for x in current_players_yh]
        current_players_yh=[x.replace("'","") for x in current_players_yh]
        current_players_yh=[x.replace("'","").strip() for x in current_players_yh]
        current_players_yh_at_risk_df=pd.DataFrame(current_players_yh)
        current_players_yh_at_risk_df.columns=['Name']

        df_yh_for_agg_list=[]
        for p in current_players_yh:
            df_yh_for_agg_list.append(execute_query_and_fetch_player_df(query=my_yahoo_players_sched_query,connection=connection,p=p))
        df_yh_for_agg=pd.concat(df_yh_for_agg_list,ignore_index=True)
        # df_yh_for_agg = pd.concat([execute_query_and_fetch_player_df(my_yahoo_players_sched_query, connection,p=p) for p in current_players_yh])

        # historicals_df=execute_query_and_fetch_df(historicals_query,connection)
        current_espn_slugs=my_live_espn_df['slug'].values.tolist()
        current_yahoo_slugs=my_live_yahoo_df['slug'].values.tolist()
        unique_current_players=set(current_espn_slugs + current_yahoo_slugs)
        unique_current_players=list(unique_current_players)

        # attempt - 1
        # historicals_df_list=[]
        # for p in unique_current_players:
        #     historicals_df_list.append(execute_query_and_fetch_player_df(query=historicals_query,connection=connection,p=p))
        # historicals_df=pd.concat(historicals_df_list,ignore_index=True)

        # attempt - 2
        # historicals_df = pd.concat([execute_query_and_fetch_player_df(historicals_query, connection,p=p) for p in unique_current_players])

        # attempt - 3
        historicals_df=execute_query_and_fetch_df(historicals_query,connection)

        predictions_df=execute_query_and_fetch_df(predictions_query,connection)
        model_eval_df=execute_query_and_fetch_df(model_eval_query,connection)

        model_eval_pred_df_list=[]
        for p in unique_current_players:
            model_eval_pred_df_list.append(execute_query_and_fetch_player_df(query=model_eval_pred_query,connection=connection,p=p))
        model_eval_pred_df=pd.concat(model_eval_pred_df_list,ignore_index=True)
        # model_eval_pred_df=pd.concat([execute_query_and_fetch_player_df(model_eval_pred_query,connection,p=p) for p in unique_current_players])


# if connection.is_connected():
#     cursor=connection.cursor()

#     cursor.execute(espn_query)
#     fa_espn_df=cursor.fetchall()
#     fa_espn_df=pd.DataFrame(fa_espn_df,columns=cursor.column_names)


#     cursor.execute(yahoo_query)
#     fa_yahoo_df=cursor.fetchall()
#     fa_yahoo_df=pd.DataFrame(fa_yahoo_df,columns=cursor.column_names)

#     cursor=connection.cursor()
#     cursor.execute(inj_prob_qry)
#     injury_probabilities_df=cursor.fetchall()
#     injury_probabilities_df=pd.DataFrame(injury_probabilities_df,columns=cursor.column_names)


# if(connection.is_connected()):
#     cursor.close()
#     connection.close()
#     print('MySQL connection is closed')
# else:
#     print('MySQL already closed')


pd.set_option('display.max_columns', None)
pd.set_option('display.max_rows', None)


fa_espn_df['minutes_played']=fa_espn_df['seconds_played']/60
fa_espn_df['total_rebounds']=fa_espn_df['offensive_rebounds']+fa_espn_df['defensive_rebounds']

fa_df=fa_espn_df[fa_espn_df['current_season_vs_historicals']=='current_season_only'].copy()
fa_df['total_rebounds']=fa_df['offensive_rebounds']+fa_df['defensive_rebounds']
fa_df['minutes_played']=fa_df['seconds_played']/60


fa_yahoo_df['total_rebounds']=fa_yahoo_df['offensive_rebounds']+fa_yahoo_df['defensive_rebounds']
fa_yahoo_df['minutes_played']=fa_yahoo_df['seconds_played']/60


model_eval_pred_df_table2_copy=model_eval_pred_df[['league','slug','model_type','p','d','q','alpha','beta','evaluation_metric','evaluation_metric_value']].copy()





####################################################################################################
# 000 - FREE AGENT SCREEN TOOL
####################################################################################################


@app.callback(Output(component_id='player_stats', component_property='figure'),
             Input(component_id='my_input', component_property='value'),
             Input(component_id='dropdown', component_property='value'),
             Input(component_id='calculation', component_property='value'),
             Input(component_id='displayed_fields', component_property='value'),
             Input(component_id='top_n', component_property='value'),
             Input(component_id="history_id", component_property='value'),
             Input(component_id="league_id", component_property='value'),
             Input(component_id='player_list', component_property='value')
             )


def graph_update(input_value,focus_field_value, calc_value,display_field, top_n_val,history_id,league_id,player_list):
    cols=['made_field_goals', 'made_three_point_field_goals','made_free_throws', 
    'total_rebounds', 'offensive_rebounds', 'defensive_rebounds', 'assists', 
    'steals', 'blocks', 'turnovers', 'personal_fouls', 'points_scored', 'minutes_played']

    days_ago=int(input_value)
    today=dt.date.today()
    days_back=today-dt.timedelta(days=days_ago)

    imps=[
     'made_field_goals',
     'made_three_point_field_goals',
     'made_free_throws',
     'offensive_rebounds',
     'defensive_rebounds',
     'assists',
     'steals',
     'blocks',
     'turnovers',
     'personal_fouls',
     'points_scored',
     'total_rebounds',
     'minutes_played']

    if league_id=='espn':
        if history_id=='cso':
            if top_n_val=='':
                player_sample=5
            else:
                player_sample=int(top_n_val)
            if len(player_list)!=len(fa_df['name'].unique()):
                fa_df1=fa_df[fa_df['name'].isin(player_list)]
            else:
                fa_df1=fa_df

            df_query1=fa_df1.query("date >= @days_back")

            if calc_value=='weights':
                output=df_query1.groupby(['name']).apply(lambda x: pd.Series([sum(x[v]*x.minutes_played)/sum(x.minutes_played) if sum(x.minutes_played) != 0 else 0 for v in imps]))
                output.columns=imps
                output=output[display_field]
                output=output.sort_values(by=[focus_field_value],ascending=False).head(player_sample)
            else:
                output=df_query1.groupby(['name'])[cols].agg(calc_value).reset_index().sort_values(by=[focus_field_value],ascending=False).head(player_sample)
                output.set_index(['name'], inplace=True, drop=True, append=False)
                output.reset_index(inplace=False)


            if calc_value=='sum':
                fig=px.imshow(output[display_field], text_auto=True)
            else:
                fig=px.imshow(output[display_field], text_auto='.2f')

            fig.update_xaxes(side='top')

            fig.layout.height=750
            fig.layout.width=750

            return fig

        elif history_id=='ho':
            fa_hist_only_df=fa_espn_df[fa_espn_df['current_season_vs_historicals']=='historicals_only']
            if top_n_val=='':
                player_sample=5
            else:
                player_sample=int(top_n_val)
            if len(player_list)!=len(fa_hist_only_df['name'].unique()):
                fa_hist_only_df1=fa_hist_only_df[fa_hist_only_df['name'].isin(player_list)]
            else:
                fa_hist_only_df1=fa_hist_only_df

            if calc_value=='weights':
                output=fa_hist_only_df1.groupby(['name']).apply(lambda x: pd.Series([sum(x[v]*x.minutes_played)/sum(x.minutes_played) if sum(x.minutes_played) != 0 else 0 for v in imps]))
                output.columns=imps
                output=output[display_field]
                output=output.sort_values(by=[focus_field_value],ascending=False).head(player_sample)
            else:
                output=fa_hist_only_df1.groupby(['name'])[cols].agg(calc_value).reset_index().sort_values(by=[focus_field_value],ascending=False).head(player_sample)
                output.set_index(['name'], inplace=True, drop=True, append=False)
                output.reset_index(inplace=False)

            if calc_value=='sum':
                fig=px.imshow(output[display_field], text_auto=True)
            else:
                fig=px.imshow(output[display_field], text_auto='.2f')

            fig.update_xaxes(side='top')

            fig.layout.height=750
            fig.layout.width=750

            return fig

        elif history_id=='hcs':
            fa_hist_and_current_df=fa_espn_df[fa_espn_df['all_history']=='history_plus_current']
            if top_n_val=='':
                player_sample=5
            else:
                player_sample=int(top_n_val)
            if len(player_list)!=len(fa_hist_and_current_df['name'].unique()):
                fa_hist_and_current_df1=fa_hist_and_current_df[fa_hist_and_current_df['name'].isin(player_list)]
            else:
                fa_hist_and_current_df1=fa_hist_and_current_df

            if calc_value=='weights':
                output=fa_hist_and_current_df1.groupby(['name']).apply(lambda x: pd.Series([sum(x[v]*x.minutes_played)/sum(x.minutes_played) if sum(x.minutes_played) != 0 else 0 for v in imps]))
                output.columns=imps
                output=output[display_field]
                output=output.sort_values(by=[focus_field_value],ascending=False).head(player_sample)
            else:
                output=fa_hist_and_current_df1.groupby(['name'])[cols].agg(calc_value).reset_index().sort_values(by=[focus_field_value],ascending=False).head(player_sample)
                output.set_index(['name'], inplace=True, drop=True, append=False)
                output.reset_index(inplace=False)

            if calc_value=='sum':
                fig=px.imshow(output[display_field], text_auto=True)
            else:
                fig=px.imshow(output[display_field], text_auto='.2f')

            fig.update_xaxes(side='top')

            fig.layout.height=750
            fig.layout.width=750

            return fig
    elif league_id=='yahoo':
        if history_id=='cso':
            fa_yahoo_df1 = fa_yahoo_df[fa_yahoo_df['all_history']=='history_plus_current']
            if top_n_val=='':
                player_sample=5
            else:
                player_sample=int(top_n_val)
            if len(player_list)!=len(fa_yahoo_df1['name'].unique()):
                fa_yahoo_current_only_df1=fa_yahoo_df1[fa_yahoo_df1['name'].isin(player_list)]
            else:
                fa_yahoo_current_only_df1=fa_yahoo_df1

            fa_yahoo_current_only_df1=fa_yahoo_current_only_df1.query("date >= @days_back")

            if calc_value=='weights':
                output=fa_yahoo_current_only_df1.groupby(['name']).apply(lambda x: pd.Series([sum(x[v]*x.minutes_played)/sum(x.minutes_played) if sum(x.minutes_played) != 0 else 0 for v in imps]))
                output.columns=imps
                output=output[display_field]
                output=output.sort_values(by=[focus_field_value],ascending=False).head(player_sample)
            else:
                output=fa_yahoo_current_only_df1.groupby(['name'])[cols].agg(calc_value).reset_index().sort_values(by=[focus_field_value],ascending=False).head(player_sample)
                output.set_index(['name'], inplace=True, drop=True, append=False)
                output.reset_index(inplace=False)


            if calc_value=='sum':
                fig=px.imshow(output[display_field], text_auto=True)
            else:
                fig=px.imshow(output[display_field], text_auto='.2f')

            fig.update_xaxes(side='top')

            fig.layout.height=750
            fig.layout.width=750

            return fig
        elif history_id=='ho':
            fa_yahoo_hist_only_df = fa_yahoo_df[fa_yahoo_df['current_season_vs_historicals']=='historicals_only']
            if top_n_val=='':
                player_sample=5
            else:
                player_sample=int(top_n_val)
            if len(player_list)!=len(fa_yahoo_hist_only_df['name'].unique()):
                fa_yahoo_hist_only_df1=fa_yahoo_hist_only_df[fa_yahoo_hist_only_df['name'].isin(player_list)]
            else:
                fa_yahoo_hist_only_df1=fa_yahoo_hist_only_df

            if calc_value=='weights':
                output=fa_yahoo_hist_only_df1.groupby(['name']).apply(lambda x: pd.Series([sum(x[v]*x.minutes_played)/sum(x.minutes_played) if sum(x.minutes_played) != 0 else 0 for v in imps]))
                output.columns=imps
                output=output[display_field]
                output=output.sort_values(by=[focus_field_value],ascending=False).head(player_sample)
            else:
                output=fa_yahoo_hist_only_df1.groupby(['name'])[cols].agg(calc_value).reset_index().sort_values(by=[focus_field_value],ascending=False).head(player_sample)
                output.set_index(['name'], inplace=True, drop=True, append=False)
                output.reset_index(inplace=False)

            if calc_value=='sum':
                fig=px.imshow(output[display_field], text_auto=True)
            else:
                fig=px.imshow(output[display_field], text_auto='.2f')

            fig.update_xaxes(side='top')

            fig.layout.height=750
            fig.layout.width=750

            return fig

        elif history_id=='hcs':
            fa_yahoo_hist_and_current_df = fa_yahoo_df[fa_yahoo_df['current_season_vs_historicals']=='current_season_only']
            if top_n_val=='':
                player_sample=5
            else:
                player_sample=int(top_n_val)
            if len(player_list)!=len(fa_yahoo_hist_and_current_df['name'].unique()):
                fa_yahoo_hist_and_current_df1=fa_yahoo_hist_and_current_df[fa_yahoo_hist_and_current_df['name'].isin(player_list)]
            else:
                fa_yahoo_hist_and_current_df1=fa_yahoo_hist_and_current_df

            if calc_value=='weights':
                output=fa_yahoo_hist_and_current_df1.groupby(['name']).apply(lambda x: pd.Series([sum(x[v]*x.minutes_played)/sum(x.minutes_played) if sum(x.minutes_played) != 0 else 0 for v in imps]))
                output.columns=imps
                output=output[display_field]
                output=output.sort_values(by=[focus_field_value],ascending=False).head(player_sample)
            else:
                output=fa_yahoo_hist_and_current_df1.groupby(['name'])[cols].agg(calc_value).reset_index().sort_values(by=[focus_field_value],ascending=False).head(player_sample)
                output.set_index(['name'], inplace=True, drop=True, append=False)
                output.reset_index(inplace=False)

            if calc_value=='sum':
                fig=px.imshow(output[display_field], text_auto=True)
            else:
                fig=px.imshow(output[display_field], text_auto='.2f')

            fig.update_xaxes(side='top')

            fig.layout.height=750
            fig.layout.width=750

            return fig




####################################################################################################
# 001 - IMPORT DATA FROM DB - CURRENT TEAM PERFORMANCE
####################################################################################################









# # my database connect
# connection=mysql.connect(host=sports_db_admin_host,
#                         database=sports_db_admin_db,
#                         user=sports_db_admin_user,
#                         password=sports_db_admin_pw,
#                         port=sports_db_admin_port)

# if connection.is_connected():
#     cursor=connection.cursor()
#     cursor.execute("""
#                     SELECT 
#                         MTS.*, 
#                         DATE_FORMAT(MTS.date, '%W') AS day_of_week,
#                         CASE
#                             WHEN DATE_FORMAT(MTS.date, '%W') IN ('Saturday', 'Sunday') THEN 'week_end'
#                             ELSE 'week_day'
#                         END AS day_of_week_class,
#                         C.week_starting_monday, 
#                         C.week_ending_sunday 
#                     FROM basketball.my_team_stats MTS 
#                     JOIN basketball.calendar C ON MTS.date=C.day;
#                     """)
#     myteam_df=cursor.fetchall()
#     myteam_df=pd.DataFrame(myteam_df, columns=cursor.column_names)

#     cursor.execute("""
#                     SELECT 
#                         MTS.*, 
#                         DATE_FORMAT(MTS.date, '%W') AS day_of_week,
#                         CASE
#                             WHEN DATE_FORMAT(MTS.date, '%W') IN ('Saturday', 'Sunday') THEN 'week_end'
#                             ELSE 'week_day'
#                         END AS day_of_week_class,
#                         C.week_starting_monday, 
#                         C.week_ending_sunday 
#                     FROM basketball.my_team_stats_yahoo MTS 
#                     JOIN basketball.calendar C ON MTS.date=C.day
#                     WHERE name IN (SELECT DISTINCT name FROM basketball.live_yahoo_players);
#                     """)
#     myteam_df_yh=cursor.fetchall()
#     myteam_df_yh=pd.DataFrame(myteam_df_yh, columns=cursor.column_names)

#     cursor.execute("""SELECT * FROM basketball.live_yahoo_players""")
#     live_yahoo_players_df=cursor.fetchall()
#     live_yahoo_players_df=pd.DataFrame(live_yahoo_players_df, columns=cursor.column_names)


# if connection.is_connected():
#     cursor=connection.cursor()
#     cursor.execute("""SELECT name,injury,news_date,exp_return_date FROM basketball.injured_player_news ORDER BY exp_return_date ASC;""")
#     inj_df=cursor.fetchall()
#     inj_df=pd.DataFrame(inj_df, columns=cursor.column_names)

#     cursor.execute("""SELECT name,injury,news_date,exp_return_date FROM basketball.injured_player_news_yh ORDER BY exp_return_date ASC;""")
#     inj_df_yf=cursor.fetchall()
#     inj_df_yf=pd.DataFrame(inj_df_yf, columns=cursor.column_names)


# if(connection.is_connected()):
#     cursor.close()
#     connection.close()
#     print('MySQL connection is closed')
# else:
#     print('MySQL already closed')



# myteam_df['total_rebounds']=myteam_df['offensive_rebounds']+myteam_df['defensive_rebounds']
# myteam_df['minutes_played']=myteam_df['seconds_played']/60

# myteam_df_yh['total_rebounds']=myteam_df_yh['offensive_rebounds']+myteam_df_yh['defensive_rebounds']
# myteam_df_yh['minutes_played']=myteam_df_yh['seconds_played']/60


# my_safe_players=['Jayson Tatum', 'Kyrie Irving','Jaylen Brown']




# myteam=league.teams[10]
# current_players=clean_string(myteam.roster).split(',')
# current_players=[remove_name_suffixes(x) for x in current_players]
# current_players=[x.strip(' ') for x in current_players]
current_players=my_live_espn_df['name'].values.tolist()


players_at_risk=list(set(current_players)-set(my_safe_players))
players_at_risk=pd.DataFrame(players_at_risk)
players_at_risk.columns=['Name']



# tm=lg.to_team('428.l.18598.t.4')
# my_tm=pd.DataFrame(tm.roster(4))
# current_players_yh=my_tm.name.tolist()

current_players_yh=live_yahoo_players_df.name.tolist()

current_players_yh=clean_string(current_players_yh).split(',')
current_players_yh=[remove_name_suffixes(x) for x in current_players_yh]
current_players_yh=[x.replace("'","") for x in current_players_yh]
current_players_yh=[x.replace("'","").strip() for x in current_players_yh]

current_players_yh_at_risk_df=pd.DataFrame(current_players_yh)
current_players_yh_at_risk_df.columns=['Name']



# I picked up bruce brown on November 30 at 10pm, 
# so don't add his scores to my team performance for that day
# same with T.J. McConnell for dec 2
# same with Tim Hardaway for dec 3
# myteam_df=myteam_df.drop(235)
# myteam_df=myteam_df.drop(249)
# myteam_df=myteam_df.drop(255)

# myteam_df=myteam_df.drop(381) # shake milton
# myteam_df=myteam_df.drop(402) # duane washington
# myteam_df=myteam_df.drop(409) # duane washington
# myteam_df=myteam_df.drop(394) # quentin grimes
# myteam_df=myteam_df.drop(401) # moritz wagner
# myteam_df=myteam_df.drop(408) # moritz wagner
# myteam_df=myteam_df.drop(405) # patty mills

# myteam_df=myteam_df.drop(414) # immanuel quickley
# myteam_df=myteam_df.drop(443) # Alec burks
# print(myteam_df.tail(15))

# myteam_df=myteam_df.drop(414)
# myteam_df=myteam_df.drop(426)

# print(myteam_df[myteam_df['name']=='Immanuel Quickley'])
# print(myteam_df.tail(50))


# connection=mysql.connect(host=sports_db_admin_host,
#                         database=sports_db_admin_db,
#                         user=sports_db_admin_user,
#                         password=sports_db_admin_pw,
#                         port=sports_db_admin_port)

# myteam=league.teams[11]
# my_players=clean_string(myteam.roster).split(',')
# my_players=[x.strip() for x in my_players]



# df_for_agg=pd.DataFrame()
# df_yh_for_agg=pd.DataFrame()
# if connection.is_connected():
#     for p in current_players:
#         cursor=connection.cursor()
#         p=remove_name_suffixes(p)
#         p=p.strip()
#         qry=f"""
#             SELECT
#                 name,
#                 team,
#                 TSCHED.*
#             FROM basketball.my_team_stats MTS
#             JOIN basketball.high_level_nba_team_schedules TSCHED ON MTS.team = TSCHED.away_team OR MTS.team = TSCHED.home_team
#             JOIN basketball.calendar CAL ON DATE(SUBDATE(CAST(TSCHED.start_time AS DATETIME), INTERVAL 8 HOUR)) = CAL.day
#             WHERE MTS.name LIKE CONCAT("%", "{p}","%")
#                 AND CURDATE() BETWEEN CAL.week_starting_monday AND CAL.week_ending_sunday
#             GROUP BY MTS.name, TSCHED.start_time;"""
#         cursor.execute(qry)
#         myteam_df1=cursor.fetchall()
#         myteam_df1=pd.DataFrame(myteam_df1, columns=cursor.column_names)
#         df_for_agg=pd.concat([df_for_agg, myteam_df1])
#     for p in current_players_yh:
#         cursor=connection.cursor()
#         p=remove_name_suffixes(p)
#         p=p.strip()
#         qry=f"""
#             SELECT
#                 name,
#                 team,
#                 TSCHED.*
#             FROM basketball.my_team_stats_yahoo MTS
#             JOIN basketball.high_level_nba_team_schedules TSCHED ON MTS.team = TSCHED.away_team OR MTS.team = TSCHED.home_team
#             JOIN basketball.calendar CAL ON DATE(SUBDATE(CAST(TSCHED.start_time AS DATETIME), INTERVAL 8 HOUR)) = CAL.day
#             WHERE MTS.name LIKE CONCAT("%", "{p}","%")
#                 AND CURDATE() BETWEEN CAL.week_starting_monday AND CAL.week_ending_sunday
#             GROUP BY MTS.name, TSCHED.start_time;"""
#         cursor.execute(qry)
#         my_team_df1_yh=cursor.fetchall()
#         my_team_df1_yh=pd.DataFrame(my_team_df1_yh,columns=cursor.column_names)
#         df_yh_for_agg=pd.concat([df_yh_for_agg,my_team_df1_yh])




aggregate=df_for_agg.groupby(['name']).start_time.nunique()
aggregate=aggregate.reset_index()
aggregate.columns=['name', 'games_this_week']
aggregate=aggregate.sort_values(['games_this_week', 'name'], ascending=False)

aggregate_yh=df_yh_for_agg.groupby(['name']).start_time.nunique()
aggregate_yh=aggregate_yh.reset_index()
aggregate_yh.columns=['name', 'games_this_week']
aggregate_yh=aggregate_yh.sort_values(['games_this_week', 'name'], ascending=False)

del df_for_agg, df_yh_for_agg

# if(connection.is_connected()):
#     cursor.close()
#     connection.close()
#     print('MySQL connection is closed')
# else:
#     print('MySQL already closed')



myteam_df['seconds_played']=myteam_df['seconds_played'].astype(float)
myteam_df['made_field_goals']=myteam_df['made_field_goals'].astype(float)
myteam_df['attempted_field_goals']=myteam_df['attempted_field_goals'].astype(float)
myteam_df['made_three_point_field_goals']=myteam_df['made_three_point_field_goals'].astype(float)
myteam_df['attempted_three_point_field_goals']=myteam_df['attempted_three_point_field_goals'].astype(float)
myteam_df['made_free_throws']=myteam_df['made_free_throws'].astype(float)
myteam_df['attempted_free_throws']=myteam_df['attempted_free_throws'].astype(float)
myteam_df['offensive_rebounds']=myteam_df['offensive_rebounds'].astype(float)
myteam_df['defensive_rebounds']=myteam_df['defensive_rebounds'].astype(float)
myteam_df['assists']=myteam_df['assists'].astype(float)
myteam_df['steals']=myteam_df['steals'].astype(float)
myteam_df['blocks']=myteam_df['blocks'].astype(float)
myteam_df['turnovers']=myteam_df['turnovers'].astype(float)
myteam_df['personal_fouls']=myteam_df['personal_fouls'].astype(float)
myteam_df['points']=myteam_df['points'].astype(float)
myteam_df['total_rebounds']=myteam_df['total_rebounds'].astype(float)
myteam_df['game_score']=myteam_df['game_score'].astype(float)


myteam_df_yh['seconds_played']=myteam_df_yh['seconds_played'].astype(float)
myteam_df_yh['made_field_goals']=myteam_df_yh['made_field_goals'].astype(float)
myteam_df_yh['attempted_field_goals']=myteam_df_yh['attempted_field_goals'].astype(float)
myteam_df_yh['made_three_point_field_goals']=myteam_df_yh['made_three_point_field_goals'].astype(float)
myteam_df_yh['attempted_three_point_field_goals']=myteam_df_yh['attempted_three_point_field_goals'].astype(float)
myteam_df_yh['made_free_throws']=myteam_df_yh['made_free_throws'].astype(float)
myteam_df_yh['attempted_free_throws']=myteam_df_yh['attempted_free_throws'].astype(float)
myteam_df_yh['offensive_rebounds']=myteam_df_yh['offensive_rebounds'].astype(float)
myteam_df_yh['defensive_rebounds']=myteam_df_yh['defensive_rebounds'].astype(float)
myteam_df_yh['assists']=myteam_df_yh['assists'].astype(float)
myteam_df_yh['steals']=myteam_df_yh['steals'].astype(float)
myteam_df_yh['blocks']=myteam_df_yh['blocks'].astype(float)
myteam_df_yh['turnovers']=myteam_df_yh['turnovers'].astype(float)
myteam_df_yh['personal_fouls']=myteam_df_yh['personal_fouls'].astype(float)
myteam_df_yh['points']=myteam_df_yh['points'].astype(float)
myteam_df_yh['total_rebounds']=myteam_df_yh['total_rebounds'].astype(float)
myteam_df_yh['game_score']=myteam_df_yh['game_score'].astype(float)


xaxis=pd.date_range(min(myteam_df['week_ending_sunday'].unique()),max(myteam_df['week_ending_sunday'].unique()), freq='W')


random.seed(11)
mycolors=px.colors.qualitative.Light24+px.colors.qualitative.Pastel1+px.colors.qualitative.Vivid+px.colors.qualitative.Set1
random.shuffle(mycolors)

# print(myteam_df.head())

def line_plot(metric='points',leagueid='ESPN'):

    if leagueid=='ESPN':
        myteam_df_x_we=myteam_df.groupby(by=['week_ending_sunday','name'])[metric].sum()
    elif leagueid=='Yahoo':
        myteam_df_x_we=myteam_df_yh.groupby(by=['week_ending_sunday','name'])[metric].sum()

    
    myteam_df_x_we=myteam_df_x_we.reset_index()
    myteam_df_x_we['pct']=myteam_df_x_we[metric]/myteam_df_x_we.groupby('week_ending_sunday')[metric].transform('sum')
    myteam_df_x_we['pct']=pd.to_numeric(myteam_df_x_we['pct'])
    myteam_df_x_we['pct']=myteam_df_x_we['pct'].round(4)
    xaxis_formats={
        'tickvals':xaxis,
        'tickformat':'%Y-%m-%d',
        'tickangle':-45
    }
    legend_formats={
        # orientation='h',
        'title_text':'Player name'
    }
    title_formats={
        'text':'Player contribution by week',
        'x':0.5
    }
    line_data={
        'width':3.75
    }
    labels={
        'week_ending_sunday':'Week Ending Sunday',
        metric:metric
        # 'points':'Point'
    }

    line_plot=px.line(myteam_df_x_we,
                x=myteam_df_x_we['week_ending_sunday'],
                y=myteam_df_x_we[metric],
                color=myteam_df_x_we['name'],
                width=20,
                markers=True,
                labels=labels,
                color_discrete_sequence=mycolors
    )
    line_plot.update_layout(
        # xaxis=dict(
        #     tickvals=xaxis,
        #     tickformat='%Y-%m-%d',
        #     tickangle=-45
        # ),
        xaxis=xaxis_formats,
        legend=legend_formats,
        title=title_formats,
        width=1300,
        height=500
    )
    line_plot.update_traces(
        line=line_data
    )
    return line_plot

# fig1=px.bar(myteam_df_x_we, 
#             x='week_ending_sunday',
#             y='pct',
#             text='pct',
#             color='name',
#             barmode='stack'
# )



# points_mean=historicals_df[~historicals_df.points.isna()]['points'].mean()
# nan_rows=historicals_df.index[historicals_df.points.isna()][1:]
# historicals_df.loc[nan_rows,'points']=points_mean

# sorted_idx=historicals_df.sort_values(by='start_time_pst',ascending=False).index
# sorted_values=historicals_df.sort_values(by='start_time_pst',ascending=True)['points'].values


def line_plot_preds(leagueid='espn',player_slug='brownja02',model_type=None):
    if leagueid=='Yahoo':
        leagueid='yahoo'
    elif leagueid=='ESPN':
        leagueid='espn'
    df=historicals_df[(historicals_df['slug']==player_slug) & (historicals_df['league']==leagueid)].copy()

    df.reset_index(drop=True,inplace=True)
    df.reset_index(drop=False,inplace=True) # new

    points_mean=df[~df['points'].isna()]['points'].mean()
    nan_rows=df.index[df.points.isna()][1:]
    df.loc[nan_rows,'points']=points_mean

    points_mean = df.loc[~df['points'].isna(), 'points'].mean()
    df.loc[df['points'].isna(), 'points'] = points_mean

    if df.empty:
        logging.warning(f"DataFrame is empty. No data to plot. {historicals_df.shape}")
        return None

    # sorted_idx=df.sort_values(by='start_time_pst',ascending=False).index
    # sorted_values=df.sort_values(by='start_time_pst',ascending=True)['points'].values

    dups=model_eval_pred_df[model_eval_pred_df.duplicated()]

    model_eval_pred_df_copy=model_eval_pred_df.copy()
    if not dups.empty:
        model_eval_pred_df_copy.drop_duplicates(inplace=True)

    df_pred=model_eval_pred_df_copy[
                            (model_eval_pred_df_copy['slug']==player_slug) & 
                            (model_eval_pred_df_copy['league']==leagueid)
                        ].copy()
    df_pred.reset_index(drop=True,inplace=True)

    line_plot=px.line(df,
        x='index',
        y='points'
    )
    line_plot.update_traces(mode='lines+markers',line_color='blue',name='Historical Points')
    line_plot.update_layout(xaxis_title='Time', yaxis_title='Points', showlegend=True)


    if model_type==None:
        model_trace=px.line(
                        x=df_pred[df_pred.champion_model==1]['day']+len(df),
                        y=df_pred[df_pred.champion_model==1]['predictions'].values
                    )
        model_trace.update_traces(mode='lines+markers',line_color='red',name='Model Predictions')
    elif model_type is not None:
        model_trace=px.line(
                        x=df_pred[df_pred['model_type']==model_type]['day']+len(df),
                        y=df_pred[df_pred['model_type']==model_type]['predictions'].values
                    )
        model_trace.update_traces(mode='lines+markers',line_color='red',name='Model Predictions')

    line_plot.add_trace(model_trace.data[0])

    line_plot.update_layout(
                            title='Historical and Predictions - Points',
                            xaxis_title='Time',
                            yaxis_title='Points'
        )
    line_plot.update_traces(showlegend=True)
    return line_plot

## original     
    # line_plot=px.line(historicals_df,
    #     x=sorted_idx,
    #     y=sorted_values
    # )
    # line_plot.update_traces(mode='lines+markers',line_color='blue',name='Historical Points')
    # # line_plot.update_traces()
    # model_trace=px.line(
    #                     x=model_eval_pred_df[model_eval_pred_df.champion_model==1]['day']+len(historicals_df),
    #                     y=model_eval_pred_df[model_eval_pred_df.champion_model==1]['predictions'].values
    #     )
    # model_trace.update_traces(mode='lines+markers',line_color='red',name='Model Predictions')
    # # model_trace.update_traces()
    # line_plot.add_trace(model_trace.data[0])
    # line_plot.update_layout(
    #                         title='Historical and Predictions - Points',
    #                         xaxis_title='Time',
    #                         yaxis_title='Points'
    #     )
    # line_plot.update_traces(showlegend=True)
    # return line_plot

def bar_plot(metric='points',leagueid='ESPN'):

    if leagueid=='ESPN':
        myteam_df_x_we=myteam_df.groupby(by=['week_ending_sunday','name'])[metric].sum()
        myteam_df_x_we=myteam_df_x_we.reset_index()
    elif leagueid=='Yahoo':
        myteam_df_x_we=myteam_df_yh.groupby(by=['week_ending_sunday','name'])[metric].sum()
        myteam_df_x_we=myteam_df_x_we.reset_index()

    myteam_df_x_we['pct']=myteam_df_x_we[metric]/myteam_df_x_we.groupby('week_ending_sunday')[metric].transform('sum')
    myteam_df_x_we['pct']=pd.to_numeric(myteam_df_x_we['pct'])
    myteam_df_x_we['pct']=myteam_df_x_we['pct'].round(4)
    hover_data={
        'pct':False,
        metric:True
        # 'points':True
    }
    title_data={
        'text':'Player contribution share by week',
        'x':0.5
    }
    legend_data={
        'title_text':'Player name'
    }
    labels={
        'week_ending_sunday':'Week Ending Sunday',
        'pct':f'{metric} share (%)'
    }
    xaxis_formats={
        'tickvals':xaxis,
        'tickformat':'%Y-%m-%d',
        'tickangle':-45
    }


    bar_plot_pct_share=px.bar(myteam_df_x_we, 
                x='week_ending_sunday',
                y='pct',
                text='pct',
                text_auto='.01%',
                # hover_data='points',
                hover_data=hover_data,
                # hovertemplate="%{percent}",
                # text=dict('pct'),
                color='name',
                labels=labels,
                color_discrete_sequence=mycolors
    )

    bar_plot_pct_share.update_layout(title=title_data,
        # legend=dict(title_text='Player name'),
        legend=legend_data,
        height=800,
        width=1250,
        # height=800,
        # width=1250,
        yaxis_tickformat=".2%",
        xaxis=xaxis_formats
    )
    return bar_plot_pct_share


metric='points'
imps_temp=[metric]
output=myteam_df.groupby(['name']).apply(lambda x: pd.Series([sum(x[v]*x.minutes_played)/sum(x.minutes_played) for v in imps_temp]))
output.columns=imps_temp

mins_agg=myteam_df.groupby(['name'])['minutes_played'].sum()

output=pd.merge(output, mins_agg, how='inner', on='name')

output=output.sort_values(by=metric, ascending=False)
# output=output.sort_values(by=[focus_field_value],ascending=False).head(player_sample)

output=output[output.index.isin(current_players)]
# output=output.reset_index()
# print(output.head())
# print(output.index)






def heatmap(metric='points',leagueid='ESPN'):

    imps=[metric]
    if leagueid=='ESPN':
        output=myteam_df.groupby(['name']).apply(lambda x: pd.Series([sum(x[v]*x.minutes_played)/sum(x.minutes_played) for v in imps]))
        output.columns=imps
        output=output.sort_values(by=metric, ascending=False)
        output=output[output.index.isin(current_players)]
    elif leagueid=='Yahoo':
        output=myteam_df_yh.groupby(['name']).apply(lambda x: pd.Series([sum(x[v]*x.minutes_played)/sum(x.minutes_played) for v in imps]))
        output.columns=imps
        output=output.sort_values(by=metric, ascending=False)
        output=output[output.index.isin(current_players_yh)]
    # output=myteam_df.groupby(['name']).apply(lambda x: pd.Series([sum(x[v]*x.minutes_played)/sum(x.minutes_played) for v in imps]))
    # output.columns=imps
    
    # mins_agg=myteam_df.groupby(['name'])['minutes_played'].sum()

    # output=pd.merge(output, mins_agg, how='inner', on='name')




    # output=output.sort_values(by=[focus_field_value],ascending=False).head(player_sample)

    
    fig=px.imshow(output, 
                    text_auto='.2f', 
                    color_continuous_scale='RdBu_r',
                    aspect='auto'
                    # labels=dict(x=f'{metric}', y='name')
    )
    fig.update_xaxes(side='top')
    fig.update_yaxes(title=None)
    fig.update_layout(width=300,height=550)

    # output=output.reset_index()
    # fig=px.density_heatmap(output,
    #                             x=metric,
    #                             y='name',
    #                             text_auto=True
    # )
    # fig.update_xaxes(side='top')



    # heat_map=px.density_heatmap(myteam_df,
    #                             x='attempted_field_goals',
    #                             y='name',
    #                             z='made_field_goals',
    #                             text_auto=True
    # )
    # heat_map.update_xaxes(side='top')
    return fig

def heatmap_weights(leagueid='ESPN'):
    metric='minutes_played'

    if leagueid=='ESPN':
        mins_agg=myteam_df.groupby(['name'])['minutes_played'].sum()
        mins_agg.columns=metric
        mins_agg=pd.DataFrame(mins_agg)
        mins_agg=mins_agg.sort_values(by=metric, ascending=False)
        mins_agg=mins_agg[mins_agg.index.isin(current_players)]
    elif leagueid=='Yahoo':
        mins_agg=myteam_df_yh.groupby(['name'])['minutes_played'].sum()
        mins_agg.columns=metric
        mins_agg=pd.DataFrame(mins_agg)
        mins_agg=mins_agg.sort_values(by=metric, ascending=False)
        mins_agg=mins_agg[mins_agg.index.isin(current_players_yh)]

    fig=px.imshow(mins_agg, 
                    text_auto='.2f', 
                    color_continuous_scale='RdBu_r',
                    aspect='auto'
    )
    fig.update_xaxes(side='top')
    fig.update_yaxes(title=None)
    fig.update_layout(width=300,height=550)

    return fig

# print(myteam_df[myteam_df['name'].isin(current_players)].head())
def boxplot_by_player(metric='points',leagueid='ESPN'):
    if leagueid=='ESPN':
        myteam_df_v1=myteam_df[myteam_df['name'].isin(current_players)]
    elif leagueid=='Yahoo':
        myteam_df_v1=myteam_df_yh[myteam_df_yh['name'].isin(current_players_yh)]

    fig1=px.box(myteam_df_v1, x='name', y=metric)
    fig1.update_traces(quartilemethod='exclusive')
    return fig1

def boxplot_by_player_weekday_class(metric='points',leagueid='ESPN'):

    if leagueid=='ESPN':
        myteam_df_v2=myteam_df[myteam_df['name'].isin(current_players)]
    elif leagueid=='Yahoo':
        myteam_df_v2=myteam_df_yh[myteam_df_yh['name'].isin(current_players_yh)]

    fig=px.box(myteam_df_v2, x='name', y=metric, 
                facet_row='day_of_week_class'
    )
    fig.update_traces(quartilemethod='exclusive')
    return fig


####################################################################################################
# 001 - CURRENT TEAM PERFORMANCE
####################################################################################################

def injury_probabilities(searched_injury='flu'):
    injury_probabilities_df_temp=injury_probabilities_df[injury_probabilities_df['injury'].str.contains(searched_injury,case=False)]
    return injury_probabilities_df_temp


@app.callback(
    Output(component_id='line_plot', component_property='figure'),
    Output(component_id='bar-plot', component_property='figure'),
    Output(component_id='heat-map', component_property='figure'),
    Output(component_id='heat-map-weights', component_property='figure'),
    Output(component_id='box-plot', component_property='figure'),
    Output(component_id='box-plot-x-week-class', component_property='figure'),
    # Output(component_id='id-injury-probabilities-table', component_property='string'),
    # Output(component_id='my-table', component_property='data'),
    # Output(component_id='my-table', component_property='figure'),
    Input(component_id='id-dropdown', component_property='value'),
    Input(component_id='id-league',component_property='value')
)

def update_plots(metric_value,league_id):
    fig_line=line_plot(metric_value,league_id)
    fig_bar=bar_plot(metric_value,league_id)
    fig_heat=heatmap(metric_value,league_id)
    fig_heat_wgts=heatmap_weights(league_id)
    fig_box=boxplot_by_player(metric_value,league_id)
    fig_box_x_week=boxplot_by_player_weekday_class(metric_value,league_id)
    return fig_line, fig_bar, fig_heat, fig_heat_wgts, fig_box, fig_box_x_week

@app.callback(
    Output('my-table','data'),
    Output('my-table','columns'),
    Input('id-league','value')
)

def update_table(selected_value):
    if selected_value == 'ESPN':
        data = aggregate.to_dict('records')
        columns = [{"name": i, "id": i} for i in aggregate.columns]
    elif selected_value == 'Yahoo':
        data = aggregate_yh.to_dict('records')
        columns = [{"name": i, "id": i} for i in aggregate_yh.columns]
    return data,columns

@app.callback(
    Output('id-injured','data'),
    Output('id-injured','columns'),
    Input('id-league','value')
)

def update_injured_table(selected_value):
    if selected_value=='ESPN':
        data=inj_df.to_dict('records')
        columns=[{"name":i,"id":i} for i in inj_df.columns]
    elif selected_value=='Yahoo':
        data=inj_df_yf.to_dict('records')
        columns=[{"name":i,"id":i} for i in inj_df_yf.columns]
    return data,columns

@app.callback(
    Output('id-my-team','data'),
    Output('id-my-team','columns'),
    Input('id-league','value')
)

def update_at_risk_table(selected_value):
    if selected_value=='ESPN':
        data=players_at_risk.to_dict('records')
        columns=[{"name":i,"id":i} for i in players_at_risk.columns]
    elif selected_value=='Yahoo':
        data=current_players_yh_at_risk_df.to_dict('records')
        columns=[{"name":i,"id":i} for i in current_players_yh_at_risk_df.columns]
    return data,columns


@app.callback(
    Output('id-inj-prob-table','data'),
    # Output('id-inj-prob-table','columns'),
    Input('id-inj-prob', 'value')
)

def update_probabilities_seach_table(searched_injury):
    searched_injury=str(searched_injury)
    specified_injury_search=injury_probabilities_df[injury_probabilities_df['injury'].str.contains(searched_injury,case=False)]

    # columns=[{"name":i,"id":i} if i != 'probabilities' else {"name":i,"id":i,"type":"numeric","format": {"specifier":'.2%'}} for i in specified_injury_search.columns],
    return specified_injury_search.to_dict('records')#, columns



@app.callback(
    Output(component_id='preds-line',component_property='figure'),
    Input(component_id='id-league',component_property='value'),
    Input(component_id='League-Players',component_property='value'),
    Input(component_id='id-model',component_property='value')
)

def update_pred_plot(leagueid,player_slug,model_type):
    fig_line_pred=line_plot_preds(leagueid,player_slug,model_type)
    return fig_line_pred


@app.callback(
    Output(component_id='id-preds-table',component_property='data'),
    Output(component_id='id-preds-table',component_property='columns'),
    Input(component_id='id-league',component_property='value'),
    Input(component_id='League-Players',component_property='value'),
    Input(component_id='id-model',component_property='value')
)

def update_preds_table(leagueid,player_slug,model_type):
    if leagueid=='Yahoo':
        leagueid='yahoo'
    elif leagueid=='ESPN':
        leagueid='espn'


    dups=model_eval_pred_df[model_eval_pred_df.duplicated()]

    model_eval_pred_df_copy=model_eval_pred_df.copy()
    if not dups.empty:
        model_eval_pred_df_copy.drop_duplicates(inplace=True)

    df_pred=model_eval_pred_df_copy[
                            (model_eval_pred_df_copy['slug']==player_slug) & 
                            (model_eval_pred_df_copy['league']==leagueid)
                        ].copy()
    df_pred.reset_index(drop=True,inplace=True)

    df_pred=df_pred[df_pred['model_type']==model_type]
    df_pred['predictions']=df_pred['predictions'].astype(float).round(1)

    df_pred=df_pred[['day','predictions']]

    data=df_pred.to_dict('records')
    columns=[{"name":i,"id":i} for i in df_pred.columns]

    return data, columns






### NEW

@app.callback(
    [Output('League-Players', 'options'),
     Output('League-Players', 'value')],
    [Input('id-league', 'value')]
)
def update_player_list(selected_value):
    if selected_value == 'ESPN':
        options = [{'label': row['name'], 'value': row['slug']} for idx, row in my_live_espn_df.iterrows()]
        default_val = my_live_espn_df.iloc[0, 1] if not my_live_espn_df.empty else None
    elif selected_value == 'Yahoo':
        options = [{'label': row['name'], 'value': row['slug']} for idx, row in my_live_yahoo_df.iterrows()]
        default_val = my_live_yahoo_df.iloc[0, 1] if not my_live_yahoo_df.empty else None
    else:
        options = []
        default_val = None
    return options, default_val

@app.callback(
    Output('output', 'children'),
    [Input('League-Players', 'value')]
)
def update_player_picked_comment(selected_value):
    if selected_value is not None:
        return f'You have selected {selected_value}'
    else:
        return 'Please select a value'

@app.callback(
    [Output('id-model', 'options'),
     Output('id-model', 'value')],
    [Input('League-Players', 'value'),
     Input('id-league', 'value')]
)
def update_model_list(selected_player, selected_league):
    if selected_player is not None and selected_league is not None:
        if selected_league == 'ESPN':
            df = model_eval_pred_df[model_eval_pred_df['league'] == 'espn'].copy()
        elif selected_league == 'Yahoo':
            df = model_eval_pred_df[model_eval_pred_df['league'] == 'yahoo'].copy()
        else:
            df = pd.DataFrame()  # Empty dataframe if selected_league is neither ESPN nor Yahoo

        if not df.empty:
            player_df = df[df['slug'] == selected_player].copy()
            player_models = player_df['model_type'].unique().tolist()
            model_default = player_models[0] if player_models else None
            return [{'label': model, 'value': model} for model in player_models], model_default

    # Return empty options and default value if no valid data found or when any of the inputs are None
    return [], None
### NEW


@app.callback(
    Output('model-output', 'children'),
    Input('id-model', 'value')
)
def update_model_picked_comment(selected_value):
    if selected_value is not None:
        if selected_value == 'ARIMA':
            return 'Autoregressive Integrated Moving Average'
        elif selected_value == 'ARMA':
            return 'Autoregressive Moving Average'
        elif selected_value == 'DBL_EXP':
            return 'Double Exponential Smoothing'
        elif selected_value == 'SGL_EXP':
            return 'Single Exponential Smoothing'
        elif selected_value == 'LINEAR':
            return 'Simple Linear'
        elif selected_value == 'LSTM':
            return 'Long Short-Term Memory'
        elif selected_value == 'NEURAL_NETWORK':
            return 'Neural Network'
        elif selected_value == 'REPEAT':
            return 'Repeat'
        elif selected_value == 'LAST':
            return 'Last'
        # return f'You have selected {selected_value}'
    else:
        return 'Please select a value'




@app.callback(
    Output(component_id='id-model-mae',component_property='data'),
    Output(component_id='id-model-mae',component_property='columns'),
    Input(component_id='id-league',component_property='value'),
    Input(component_id='League-Players',component_property='value')
)

def update_player_models_table(leagueid,player_slug):
    if leagueid=='Yahoo':
        leagueid='yahoo'
    elif leagueid=='ESPN':
        leagueid='espn'
    df=model_eval_pred_df_table2_copy.copy()
    df=df[(df['league']==leagueid) &
            (df['slug']==player_slug)
    ]
    cols_to_drop=['league','slug']
    df.drop(columns=cols_to_drop,inplace=True)
    df['evaluation_metric_value']=df['evaluation_metric_value'].astype(float).round(2)
    df=df.groupby('model_type').first().reset_index()
    df=df.sort_values(by='evaluation_metric_value',ascending=True)

    data=df.to_dict('records')
    columns=[{"name":i,"id":i} for i in df.columns]

    return data, columns





