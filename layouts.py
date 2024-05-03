
import os
import mysql.connector as mysql
from mysql.connector import pooling
import pandas as pd
import datetime as dt
from dash import html
from dash import dcc, html, Input, Output, dash_table
import plotly.express as px
import plotly.graph_objects as go
from dash_create import app

# from callbacks import line_plot, bar_plot, heatmap, heatmap_weights, boxplot_by_player, boxplot_by_player_weekday_class, injury_probabilities, line_plot_preds #,predictions_table
# from callbacks import execute_query_and_fetch_df, execute_query_and_fetch_player_df
import callbacks as cbc
import my_functions as mf
# from my_functions import clean_string, remove_name_suffixes

# ESPN 
from espn_api.basketball import League


####################################################################################################
# 000 - FORMATTING INFO
####################################################################################################

####################### Corporate css formatting
corporate_colors = {
    'dark-blue-grey' : 'rgb(62, 64, 76)',
    'medium-blue-grey' : 'rgb(77, 79, 91)',
    'superdark-green' : 'rgb(41, 56, 55)',
    'dark-green' : 'rgb(57, 81, 85)',
    'medium-green' : 'rgb(93, 113, 120)',
    'light-green' : 'rgb(186, 218, 212)',
    'pink-red' : 'rgb(255, 101, 131)',
    'dark-pink-red' : 'rgb(247, 80, 99)',
    'white' : 'rgb(251, 251, 252)',
    'light-grey' : 'rgb(208, 206, 206)',
    'yellow': 'rgb(255,211,67)'
}

externalgraph_rowstyling = {
    'margin-left' : '15px',
    'margin-right' : '15px'
}

externalgraph_colstyling = {
    'border-radius' : '10px',
    'border-style' : 'solid',
    'border-width' : '1px',
    'border-color' : corporate_colors['superdark-green'],
    'background-color' : corporate_colors['superdark-green'],
    'box-shadow' : '0px 0px 17px 0px rgba(186, 218, 212, .5)',
    'padding-top' : '5px'
}


navbarcurrentpage = {
    'text-decoration' : 'underline',
    'text-decoration-color' : corporate_colors['white'],
    'text-shadow': '0px 0px 1px rgb(251, 251, 252)',
    'color':corporate_colors['white']
}



recapdiv = {
    'border-radius' : '10px',
    'border-style' : 'solid',
    'border-width' : '1px',
    'border-color' : 'rgb(251, 251, 252, 0.1)',
    'margin-left' : '15px',
    'margin-right' : '15px',
    'margin-top' : '15px',
    'margin-bottom' : '15px',
    'padding-top' : '5px',
    'padding-bottom' : '5px',
    'background-color' : 'rgb(251, 251, 252, 0.1)'
}

recapdiv_text = {
    'text-align' : 'left',
    'font-weight' : '350',
    'color' : corporate_colors['white'],
    'font-size' : '1.5rem',
    'letter-spacing' : '0.04em'
}


filterdiv_borderstyling = {
    'border-radius' : '0px 0px 10px 10px',
    'border-style' : 'solid',
    'border-width' : '1px',
    'border-color' : corporate_colors['light-green'],
    'background-color' : corporate_colors['light-green'],
    'box-shadow' : '2px 5px 5px 1px rgba(255, 101, 131, .5)'
}



####################################################################################################
# 000 - IMPORT DATA
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

# league_config={
#     "league_id":leagueid,
#     "year":2024,
#     "espn_s2":espn_s2,
#     "swid":swid,
#     "debug":False
# }

# league=League(**league_config)


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
##





# my_live_yahoo_qry='''
# SELECT * 
# FROM basketball.live_yahoo_players
# ;
# '''

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
;
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

# historicals_query='''
# SELECT 
#     HWAD.date,
#     HWAD.slug,
#     HWAD.name,
#     HWAD.team,
#     HWAD.opponent,
#     HWAD.points,
#     HWAD.league
# FROM basketball.player_historical_web_app_display HWAD
# ;
# '''



my_safe_players=['Jayson Tatum', 'Kyrie Irving','Jaylen Brown']



with connection_pool.get_connection() as connection:
    if connection.is_connected():
        fa_espn_df = mf.execute_query_and_fetch_df(espn_query, connection)
        fa_yahoo_df = mf.execute_query_and_fetch_df(yahoo_query, connection)
        
        myteam_df = mf.execute_query_and_fetch_df(my_espn_team_qry, connection)
        myteam_df['total_rebounds']=myteam_df['offensive_rebounds']+myteam_df['defensive_rebounds']
        myteam_df['minutes_played']=myteam_df['seconds_played']/60

        myteam_df_yh = mf.execute_query_and_fetch_df(my_yahoo_team_qry, connection)
        myteam_df_yh['total_rebounds']=myteam_df_yh['offensive_rebounds']+myteam_df_yh['defensive_rebounds']
        myteam_df_yh['minutes_played']=myteam_df_yh['seconds_played']/60

        live_yahoo_players_df = mf.execute_query_and_fetch_df(my_live_yahoo_qry, connection)
        inj_df = mf.execute_query_and_fetch_df(my_injured_espn_team_qry, connection)
        inj_df_yf = mf.execute_query_and_fetch_df(my_injured_yahoo_team_qry, connection)

        #### NEW SECTION

        my_live_espn_df=mf.execute_query_and_fetch_df(my_live_espn_qry,connection)
        my_live_yahoo_df=mf.execute_query_and_fetch_df(my_live_yahoo_qry,connection)
        #### NEW SECTION

        ####################### REWRITE SECTION
        # myteam=league.teams[10] #come back
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
            df_for_agg_list.append(mf.execute_query_and_fetch_player_df(query=my_espn_players_sched_query,connection=connection,p=p))
        df_for_agg=pd.concat(df_for_agg_list, ignore_index=True)
        # df_for_agg = pd.concat([execute_query_and_fetch_df(my_espn_players_sched_query, connection) for p in current_players])

        # df_yh_for_agg = pd.concat([fetch_players_sched_query(my_yahoo_players_sched_query, connection, p) for p in current_players_yh])
        ##
        current_players_yh=live_yahoo_players_df.name.tolist()

        current_players_yh=mf.clean_string(current_players_yh).split(',')
        current_players_yh=[mf.remove_name_suffixes(x) for x in current_players_yh]
        current_players_yh=[x.replace("'","") for x in current_players_yh]
        current_players_yh=[x.replace("'","").strip() for x in current_players_yh]

        current_players_yh_at_risk_df=pd.DataFrame(current_players_yh)
        current_players_yh_at_risk_df.columns=['Name']

        df_yh_for_agg_list=[]
        for p in current_players_yh:
            df_yh_for_agg_list.append(mf.execute_query_and_fetch_player_df(query=my_yahoo_players_sched_query,connection=connection,p=p))
        df_yh_for_agg=pd.concat(df_yh_for_agg_list,ignore_index=True)
        # df_yh_for_agg = pd.concat([execute_query_and_fetch_df(my_yahoo_players_sched_query, connection) for p in current_players_yh])
        ####################### REWRITE SECTION

        current_espn_slugs=my_live_espn_df['slug'].values.tolist()
        current_yahoo_slugs=my_live_yahoo_df['slug'].values.tolist()
        unique_current_players=set(current_espn_slugs + current_yahoo_slugs)
        unique_current_players=list(unique_current_players)

        # attempt - 1
        # historicals_df_list=[]
        # for p in unique_current_players:
        #     historicals_df_list.append(execute_query_and_fetch_player_df(query=historicals_query,connection=connection,p=p))
        # historicals_df=pd.concat(historicals_df_list,ignore_index=True)
        # historicals_df=pd.concat([execute_query_and_fetch_df(historicals_query,connection) for p in unique_current_players])

        # attempt - 2
        # historicals_df=execute_query_and_fetch_df(historicals_query,connection)

        # attempt - 3
        # historicals_df=execute_query_and_fetch_df(historicals_query,connection)

        predictions_df=mf.execute_query_and_fetch_df(predictions_query,connection)
        model_eval_df=mf.execute_query_and_fetch_df(model_eval_query,connection)

        model_eval_pred_df_list=[]
        for p in unique_current_players:
            model_eval_pred_df_list.append(mf.execute_query_and_fetch_player_df(query=model_eval_pred_query,connection=connection,p=p))
        model_eval_pred_df=pd.concat(model_eval_pred_df_list,ignore_index=True)
        # model_eval_pred_df=execute_query_and_fetch_df(model_eval_pred_query,connection)

# if connection.is_connected():
#     cursor=connection.cursor()

#     cursor.execute(espn_query)
#     fa_espn_df=cursor.fetchall()
#     fa_espn_df=pd.DataFrame(fa_espn_df,columns=cursor.column_names)


#     cursor.execute(yahoo_query)
#     fa_yahoo_df=cursor.fetchall()
#     fa_yahoo_df=pd.DataFrame(fa_yahoo_df,columns=cursor.column_names)


# if(connection.is_connected()):
#     cursor.close()
#     connection.close()
#     print('MySQL connection is closed')
# else:
#     print('MySQL already closed')


# pd.set_option('display.max_columns', None)
# pd.set_option('display.max_rows', None)


fa_df=fa_espn_df[fa_espn_df['current_season_vs_historicals']=='current_season_only'].copy()
fa_df['total_rebounds']=fa_df['offensive_rebounds']+fa_df['defensive_rebounds']
fa_df['minutes_played']=fa_df['seconds_played']/60


fa_yahoo_df['total_rebounds']=fa_yahoo_df['offensive_rebounds']+fa_yahoo_df['defensive_rebounds']
fa_yahoo_df['minutes_played']=fa_yahoo_df['seconds_played']/60



######
# myteam_df.head()
cols=['made_field_goals', 'made_three_point_field_goals','made_free_throws', 
      'total_rebounds', 'offensive_rebounds', 'defensive_rebounds', 'assists', 
      'steals', 'blocks', 'turnovers', 'personal_fouls', 'points_scored', 'minutes_played'
     ]

focus_value='made_field_goals'
calc='mean'
player_sample=20
days_ago=700

today=dt.date.today()
days_back=today-dt.timedelta(days=days_ago)


df_query=fa_df.query("date >= @days_back")

output=df_query.groupby(['name'])[cols].agg(calc).reset_index().sort_values(by=[focus_value],ascending=False).head(player_sample)

output.set_index(['name'], inplace=True, drop=True, append=False)
output.reset_index(inplace=False)


short_df = output.iloc[:,0:len(output)]

######


def player_stats():
    fig=px.imshow(short_df, 
        text_auto=True)
    # fig=go.Figure(data=go.Heatmap(short_df))

    fig.update_xaxes(side='top')
    fig.layout.height=750
    fig.layout.width=900

    return fig






# my team performance data



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



# my_safe_players=['Jayson Tatum', 'Kyrie Irving','Jaylen Brown'
# ]



# myteam=league.teams[10]
# current_players=clean_string(myteam.roster).split(',')
# current_players=[remove_name_suffixes(x) for x in current_players]
# current_players=[x.strip(' ') for x in current_players]


# players_at_risk=list(set(current_players)-set(my_safe_players))
# players_at_risk=pd.DataFrame(players_at_risk)
# players_at_risk.columns=['Name']



# # tm=lg.to_team('428.l.18598.t.4')
# # my_tm=pd.DataFrame(tm.roster(4))
# # current_players_yh=my_tm.name.tolist()

# current_players_yh=live_yahoo_players_df.name.tolist()

# current_players_yh=clean_string(current_players_yh).split(',')
# current_players_yh=[remove_name_suffixes(x) for x in current_players_yh]
# current_players_yh=[x.replace("'","") for x in current_players_yh]
# current_players_yh=[x.replace("'","").strip() for x in current_players_yh]

# current_players_yh_at_risk_df=pd.DataFrame(current_players_yh)
# current_players_yh_at_risk_df.columns=['Name']



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



injury_probabilities_df=cbc.injury_probabilities()


model_eval_pred_df_copy=model_eval_pred_df[['day','predictions']].copy()
model_eval_pred_df_table2_copy=model_eval_pred_df[['league','slug','model_type','p','d','q','alpha','beta','evaluation_metric','evaluation_metric_value']].copy()



####################################################################################################
# 000 - DEFINE REUSABLE COMPONENTS AS FUNCTIONS
####################################################################################################

#####################
# Header with logo
def get_header():

    header = html.Div([

        html.Div([], className = 'col-2'), #Same as img width, allowing to have the title centrally aligned

        html.Div([
            html.H1(children='Fantasy Basketball Analytics',
                    style = {'textAlign' : 'center', 'color':corporate_colors['white']}
            ),
            html.H6(children='*Combined data from Basketball-Reference.com, Prosportstransactions.com, ESPN & Yahoo',
                    style={'textAlign':'center','color':corporate_colors['yellow']})],
            className='col-8',
            style = {'padding-top' : '1%'}
        ),

        html.Div([
            html.Img(
                    src = app.get_asset_url('basketball_hoops.jpg'),
                    height = '75 px',
                    width = 'auto')
            ],
            className = 'col-2',
            style = {
                    'align-items': 'center',
                    'padding-top' : '1%',
                    'height' : 'auto'})

        ],
        className = 'row',
        style = {'height' : '4%',
                'background-color' : corporate_colors['superdark-green']}
        )

    return header


#####################
# Nav bar
def get_navbar(p = 'page1'):

    navbar_page1 = html.Div([

        html.Div([], className = 'col-3'),

        html.Div([
            dcc.Link(
                html.H4(children = 'Predictive Modeling',
                        style = navbarcurrentpage),
                href='/apps/fantasy-predictions'
                )
        ],
        className='col-2'),

        html.Div([
            dcc.Link(
                html.H4(children = 'Free Agent Screening Tool', style={'color':corporate_colors['white']}),
                href='/apps/free-agent-screening'
                )
        ],
        className='col-2'),

        html.Div([
            dcc.Link(
                html.H4(children = 'Current Team Performance', style={'color':corporate_colors['white']}),
                href='/apps/team-performance'
                )
        ],
        className='col-2'),

        html.Div([], className = 'col-')

    ],
    className = 'row',
    style = {'background-color' : corporate_colors['dark-green'],
            'box-shadow': '2px 5px 5px 1px rgba(255, 101, 131, .5)'}
    )

    navbar_page2 = html.Div([

        html.Div([], className = 'col-3'),

        html.Div([
            dcc.Link(
                html.H4(children = 'Predictive Modeling', style={'color':corporate_colors['white']}),
                href='/apps/fantasy-predictions'
                )
        ],
        className='col-2'),

        html.Div([
            dcc.Link(
                html.H4(children = 'Free Agent Screening Tool',
                        style = navbarcurrentpage),
                href='/apps/free-agent-screening'
                )
        ],
        className='col-2'),

        html.Div([
            dcc.Link(
                html.H4(children = 'Current Team Performance', style={'color':corporate_colors['white']}),
                href='/apps/team-performance'
                )
        ],
        className='col-2'),

        html.Div([], className = 'col-3')

    ],
    className = 'row',
    style = {'background-color' : corporate_colors['dark-green'],
            'box-shadow': '2px 5px 5px 1px rgba(255, 101, 131, .5)'}
    )

    navbar_page3 = html.Div([

        html.Div([], className = 'col-3'),

        html.Div([
            dcc.Link(
                html.H4(children = 'Predictive Modeling', style={'color':corporate_colors['white']}),
                href='/apps/fantasy-predictions'
                )
        ],
        className='col-2'),

        html.Div([
            dcc.Link(
                html.H4(children = 'Free Agent Screening Tool', style={'color':corporate_colors['white']}),
                href='/apps/free-agent-screening'
                )
        ],
        className='col-2'),

        html.Div([
            dcc.Link(
                html.H4(children = 'Current Team Performance',
                        style = navbarcurrentpage), 
                href='/apps/team-performance'
                )
        ],
        className='col-2'),

        html.Div([], className = 'col-3')

    ],
    className = 'row',
    style = {'background-color' : corporate_colors['dark-green'],
            'box-shadow': '2px 5px 5px 1px rgba(255, 101, 131, .5)'}
    )

    if p == 'page1':
        return navbar_page1
    elif p == 'page2':
        return navbar_page2
    else:
        return navbar_page3



#####################
# Empty row

def get_emptyrow(h='45px'):
    """This returns an empty row of a defined height"""

    emptyrow = html.Div([
        html.Div([
            html.Br()
        ], className = 'col-12')
    ],
    className = 'row',
    style = {'height' : h})

    return emptyrow

config={
    'displayModeBar': False,
    'displaylogo': False,                                       
    'modeBarButtonsToRemove': ['zoom2d', 'hoverCompareCartesian', 'hoverClosestCartesian', 'toggleSpikelines']
  }

table_title_font_color={
    'color': '#FFFFFF',
    'white-space':'normal'
}




####################################################################################################
# 001 - page1 (forecasting)
####################################################################################################


page1 = html.Div([

    #####################
    #Row 1 : Header
    get_header(),

    #####################
    #Row 2 : Nav bar
    get_navbar('page1'),

    #####################
    #Row 3 : Filters
    html.Div([ # External row

        html.Div([ # External 12-column

            html.Div([ # Internal row

                ######################################################################################## 

                #Filter pt 1
                html.Div([

                    html.Div([
                        html.H5(
                            children='League:',
                            style = {'text-align' : 'left', 'color' : corporate_colors['medium-blue-grey']}
                        ),
                        #Date range picker
                        html.Div([#'Focus Field: ',
                            dcc.Dropdown(id='id-league',
                                    options=[{'label':'ESPN','value':'ESPN'},
                                              {'label':'Yahoo','value':'Yahoo'}],
                                              value='ESPN'
                                ),
                        ], style = {'margin-top' : '5px'}
                        )

                    ],
                    style = {'margin-top' : '10px',
                            'margin-bottom' : '5px',
                            'text-align' : 'left',
                            'paddingLeft': 5})

                ],
                className = 'col-4'), # Filter part 1

                ########################################################################################

                # Filter pt 2
                html.Div([
                    html.Div([
                        html.H5(
                            children='Team Players:',
                            style = {'text-align' : 'left', 'color' : corporate_colors['medium-blue-grey']}
                        ),
                        html.Div([
                            dcc.Dropdown(
                                id='League-Players'
                            ),
                            html.Div(id='output'),
                        ], style = {'margin-top' : '5px'}
                        ),
                    ],
                    style = {'margin-top' : '10px',
                            'margin-bottom' : '5px',
                            'text-align' : 'left',
                            'paddingLeft': 5})
                ],
                className = 'col-4'), #Filter pt 2

                ########################################################################################


                # Filter pt 3
                html.Div([
                    html.Div([
                        html.H5(
                            children='Model:',
                            style = {'text-align' : 'left', 'color' : corporate_colors['medium-blue-grey']}
                        ),
                        html.Div([
                            dcc.Dropdown(
                                id='id-model'
                            ),
                            html.Div(id='model-output'),
                        ], style = {'margin-top' : '5px'}
                        ),
                    ],
                    style = {'margin-top' : '10px',
                            'margin-bottom' : '5px',
                            'text-align' : 'left',
                            'paddingLeft': 5})
                ],
                className = 'col-4'), #Filter pt 3


                ########################################################################################          

                html.Div([
                ],
                className = 'col-2') # Blank 2 columns


            ],
            className = 'row') # Internal row

        ],
        className = 'col-12',
        style = filterdiv_borderstyling) # External 12-column

    ],
    className = 'row sticky-top'), # External row

    #####################
    #Row 4
    get_emptyrow(),

    #####################
    #Row 5 : Charts
    html.Div([ # External row
        
        html.Div([
        ],
        className = 'col-1'), # Blank 1 column

        html.Div([
            html.Div([ # Internal row 1
                html.Div([
                    dcc.Graph(id='preds-line',figure=cbc.line_plot_preds(),config=config)
                ])
            ]),

        ],
        className = 'row'),

        # Injured Players table and title
        html.Div([
            html.H5("Predictions Table",
                style={'color': corporate_colors['white']}),
            html.Div([
                dash_table.DataTable(
                    id='id-preds-table',
                    data=model_eval_pred_df_copy.to_dict('records'),
                    columns=[{'name':i,'id':i} for i in model_eval_pred_df_copy.columns],
                    style_cell=dict(textAlign='center'),
                    style_header=dict(backgroundColor='paleturquoise'),
                    style_table={'overflowX':'auto','width':'100%'}
                ),
            ],className='col-6'),
            html.Div([
                dash_table.DataTable(
                    id='id-model-mae',
                    data=model_eval_pred_df_table2_copy.to_dict('records'),
                    columns=[{'name':i,'id':i} for i in model_eval_pred_df_table2_copy.columns], # imhere
                    style_cell=dict(textAlign='center'),
                    style_header=dict(backgroundColor='paleturquoise'),
                    style_table={'overflowX':'auto','width':'100%'}
                )
            ],className='col-6')

        ],
        className='row'),
    ],className='container')

])


####################################################################################################
# 002 - page2 (free agent screening tool)
####################################################################################################

page2 = html.Div([

    #####################
    #Row 1 : Header
    get_header(),

    #####################
    #Row 2 : Nav bar
    get_navbar('page2'),

    #####################
    #Row 3 : Filters
    html.Div([ # External row

        html.Div([ # External 12-column

            html.Div([ # Internal row

                # #Internal columns
                # html.Div([
                # ],
                # className = 'col-2'), # Blank 2 columns

                ########################################################################################

                #Filter pt 1
                html.Div([

                    html.Div([
                        html.H5(
                            children='How many days back?',
                            style = {'text-align' : 'left', 'color' : corporate_colors['medium-blue-grey']}
                        ),
                        html.Div(['(Functional for current season only)',
                            dcc.Input(id='my_input',
                                        value=200,
                                        type='number',
                                        style = {'font-size': '12px','display': 'inline-block', 'border-radius' : '2px', 'border' : '1px solid #ccc', 'color': '#333', 'border-spacing' : '0', 'border-collapse' :'separate'}
                                )
                            # dcc.DatePickerRange(
                            #     id='date-picker-page1',
                            #     start_date = min_dt_str,
                            #     end_date = max_dt_str,
                            #     min_date_allowed = min_dt,
                            #     max_date_allowed = max_dt,
                            #     start_date_placeholder_text = 'Start date',
                            #     display_format='DD-MMM-YYYY',
                            #     first_day_of_week = 1,
                            #     end_date_placeholder_text = 'End date',
                            #     style = {'font-size': '12px','display': 'inline-block', 'border-radius' : '2px', 'border' : '1px solid #ccc', 'color': '#333', 'border-spacing' : '0', 'border-collapse' :'separate'}
                            # )
                        ], style = {'margin-top' : '5px'}
                        )

                    ],
                    style = {'margin-top' : '10px',
                            'margin-bottom' : '5px',
                            'text-align' : 'left',
                            'paddingLeft': 5})

                ],
                className = 'col-4'), # Filter part 1

                ########################################################################################

                #Filter pt 2
                html.Div([

                    html.Div([
                        html.H5(
                            children='Focus Field',
                            style = {'text-align' : 'left', 'color' : corporate_colors['medium-blue-grey']}
                        ),
                        #Date range picker
                        html.Div(['(Picked field must be checked ON in \"Fields to Display\"): ',
                            dcc.Dropdown(id='dropdown',
                                options=[{'label':'Made Field Goals','value':'made_field_goals'},
                                {'label':'Made 3p Field Goals','value':'made_three_point_field_goals'},
                                {'label':'Made Free Throws','value':'made_free_throws'},
                                {'label':'Total Rebounds','value':'total_rebounds'},
                                {'label':'Offensive Rebounds','value':'offensive_rebounds'},
                                {'label':'Defensive Rebounds','value':'defensive_rebounds'},
                                {'label':'Assists','value':'assists'},
                                {'label':'Steals','value':'steals'},
                                {'label':'Blocks','value':'blocks'},
                                {'label':'Turnovers','value':'turnovers'},
                                {'label':'Personal Fouls','value':'personal_fouls'},
                                {'label':'Points','value':'points_scored'},
                                {'label':'Minutes Played','value':'minutes_played'}],
                                value='points_scored')
                            # dcc.Input(id='my_input',
                            #             value=7,
                            #             type='integer',
                            #             style = {'font-size': '12px','display': 'inline-block', 'border-radius' : '2px', 'border' : '1px solid #ccc', 'color': '#333', 'border-spacing' : '0', 'border-collapse' :'separate'}
                            #     )
                        ], style = {'margin-top' : '5px'}
                        )

                    ],
                    style = {'margin-top' : '10px',
                            'margin-bottom' : '5px',
                            'text-align' : 'left',
                            'paddingLeft': 5})

                ],
                className = 'col-4'), # Filter part 2
                ########################################################################################

                #Filter pt 3
                html.Div([

                    html.Div([
                        html.H5(
                            children='Calculation Type:',
                            style = {'text-align' : 'left', 'color' : corporate_colors['medium-blue-grey']}
                        ),
                        #Date range picker
                        html.Div([#'Calculation Type: ',
                            dcc.Dropdown(id='calculation',
                                options=[{'label':'Total', 'value':'sum'},
                                {'label':'Average(non-weighted)', 'value':'mean'},
                                {'label':'Weighted Average', 'value':'weights'},
                                {'label':'Standard Deviation', 'value':'std'}],
                                value='weights')
                            # dcc.Input(id='my_input',
                            #             value=7,
                            #             type='integer',
                            #             style = {'font-size': '12px','display': 'inline-block', 'border-radius' : '2px', 'border' : '1px solid #ccc', 'color': '#333', 'border-spacing' : '0', 'border-collapse' :'separate'}
                            #     )
                        ], style = {'margin-top' : '5px'}
                        )

                    ],
                    style = {'margin-top' : '10px',
                            'margin-bottom' : '5px',
                            'text-align' : 'left',
                            'paddingLeft': 5})

                ],
                className = 'col-4'), # Filter part 3
                ########################################################################################


                #Filter pt 4
                html.Div([

                    html.Div([
                        html.H5(
                            children='League:',
                            style = {'text-align' : 'left', 'color' : corporate_colors['medium-blue-grey']}
                        ),
                        #Date range picker
                        html.Div([#'League: ',
                            dcc.Dropdown(id='league_id',
                                options=[{'label':'ESPN', 'value':'espn'},
                                {'label':'Yahoo','value':'yahoo'}],
                                value='yahoo')
                            # dcc.Input(id='my_input',
                            #             value=7,
                            #             type='integer',
                            #             style = {'font-size': '12px','display': 'inline-block', 'border-radius' : '2px', 'border' : '1px solid #ccc', 'color': '#333', 'border-spacing' : '0', 'border-collapse' :'separate'}
                            #     )
                        ], style = {'margin-top' : '5px'}
                        )

                    ],
                    style = {'margin-top' : '10px',
                            'margin-bottom' : '5px',
                            'text-align' : 'left',
                            'paddingLeft': 5})

                ],
                className = 'col-4'), # Filter part 4
                ########################################################################################


                #Filter pt 5
                html.Div([

                    html.Div([
                        html.H5(
                            children='Number of players:',
                            style = {'text-align' : 'left', 'color' : corporate_colors['medium-blue-grey']}
                        ),
                        #Date range picker
                        html.Div([#'Number of Players: ',
                            dcc.Input(id='top_n', value=5, type='number')
                            # dcc.Input(id='my_input',
                            #             value=7,
                            #             type='integer',
                            #             style = {'font-size': '12px','display': 'inline-block', 'border-radius' : '2px', 'border' : '1px solid #ccc', 'color': '#333', 'border-spacing' : '0', 'border-collapse' :'separate'}
                            #     )
                        ], style = {'margin-top' : '5px'}
                        )

                    ],
                    style = {'margin-top' : '10px',
                            'margin-bottom' : '5px',
                            'text-align' : 'left',
                            'paddingLeft': 5})

                ],
                className = 'col-4'), # Filter part 5
                ########################################################################################


                #Filter pt 6
                html.Div([

                    html.Div([
                        html.H5(
                            children='Historical Options:',
                            style = {'text-align' : 'left', 'color' : corporate_colors['medium-blue-grey']}
                        ),
                        #Date range picker
                        html.Div([#'Historical Options: ',
                            dcc.Dropdown(id='history_id',
                                options=[{'label':'History only','value':'ho'},
                                {'label':'History + current season ','value':'hcs'},
                                {'label':'Current season only','value':'cso'}],
                                value='cso')
                            # dcc.Input(id='my_input',
                            #             value=7,
                            #             type='integer',
                            #             style = {'font-size': '12px','display': 'inline-block', 'border-radius' : '2px', 'border' : '1px solid #ccc', 'color': '#333', 'border-spacing' : '0', 'border-collapse' :'separate'}
                            #     )
                        ], style = {'margin-top' : '5px'}
                        )

                    ],
                    style = {'margin-top' : '10px',
                            'margin-bottom' : '5px',
                            'text-align' : 'left',
                            'paddingLeft': 5})

                ],
                className = 'col-4'), # Filter part 6
                ########################################################################################


                #Filter pt 7
                html.Div([

                    html.Div([
                        html.H5(
                            children='Fields to Display:',
                            style = {'text-align' : 'left', 
                            "overflow-y":"scroll", #"height": "50px",
                                'color' : corporate_colors['medium-blue-grey']
                                
                                }
                        ),
                        #Date range picker
                        html.Div([#'Fields to Display: ',
                            dcc.Checklist(id='displayed_fields', 
                                options=['made_field_goals', 'made_three_point_field_goals',
                                'made_free_throws','total_rebounds', 'offensive_rebounds', 
                                'defensive_rebounds', 'assists','steals', 'blocks', 
                                'turnovers', 'personal_fouls', 'points_scored', 'minutes_played'],
                                value=['made_field_goals', 'made_three_point_field_goals',
                                'made_free_throws','total_rebounds', 'offensive_rebounds', 
                                'defensive_rebounds','assists','steals', 'blocks', 
                                'turnovers', 'points_scored'],
                                style={"overflow-y":"scroll", "height": "100px"})
                            # dcc.Input(id='my_input',
                            #             value=7,
                            #             type='integer',
                            #             style = {'font-size': '12px','display': 'inline-block', 'border-radius' : '2px', 'border' : '1px solid #ccc', 'color': '#333', 'border-spacing' : '0', 'border-collapse' :'separate'}
                            #     )
                        ], style = {'margin-top' : '5px'}
                        )

                    ],
                    style = {'margin-top' : '10px',
                            'margin-bottom' : '5px',
                            'text-align' : 'left',
                            'paddingLeft': 5})

                ],
                className = 'col-4'), # Filter part 7
                ########################################################################################


                #Filter pt 8
                html.Div([

                    html.Div([
                        html.H5(
                            children='Player Checklist:',
                            style = {'text-align' : 'left', 'color' : corporate_colors['medium-blue-grey']}
                        ),
                        #Date range picker
                        html.Div([#'Player Checklist: ',
                            dcc.Checklist(id='player_list', 
                                options=[name for name in fa_df['name'].unique()], 
                                value=[name for name in fa_df['name'].unique()], 
                                style={"overflow-y":"scroll", "height": "100px"},
                                # style={'height':10000,'width':100}, 
                                inline=True)
                            # dcc.Input(id='my_input',
                            #             value=7,
                            #             type='integer',
                            #             style = {'font-size': '12px','display': 'inline-block', 'border-radius' : '2px', 'border' : '1px solid #ccc', 'color': '#333', 'border-spacing' : '0', 'border-collapse' :'separate'}
                            #     )
                        ], style = {'margin-top' : '5px'}
                        )

                    ],
                    style = {'margin-top' : '10px',
                            'margin-bottom' : '5px',
                            'text-align' : 'left',
                            'paddingLeft': 5})

                ],
                className = 'col-4'), # Filter part 8
                ########################################################################################
                

                html.Div([
                ],
                className = 'col-2') # Blank 2 columns


            ],
            className = 'row') # Internal row

        ],
        className = 'col-12',
        style = filterdiv_borderstyling) # External 12-column

    ],
    className = 'row sticky-top'), # External row

    #####################
    #Row 4
    get_emptyrow(),

    #####################
    #Row 5 : Charts
    html.Div([ # External row

        html.Div([
        ],
        className = 'col-1'), # Blank 1 column

        html.Div([ # External 10-column

            # html.H2(children = "page1 Performances",
            #         style = {'color' : corporate_colors['white']}),

            # html.Div([ # Internal row - RECAPS

            #     # html.Div([],className = 'col-4'), # Empty column

            #     # html.Div([
            #     #     dash_table.DataTable(
            #     #         id='recap-table',
            #     #         style_header = {
            #     #             'backgroundColor': 'transparent',
            #     #             'fontFamily' : corporate_font_family,
            #     #             'font-size' : '1rem',
            #     #             'color' : corporate_colors['light-green'],
            #     #             'border': '0px transparent',
            #     #             'textAlign' : 'center'},
            #     #         style_cell = {
            #     #             'backgroundColor': 'transparent',
            #     #             'fontFamily' : corporate_font_family,
            #     #             'font-size' : '0.85rem',
            #     #             'color' : corporate_colors['white'],
            #     #             'border': '0px transparent',
            #     #             'textAlign' : 'center'},
            #     #         cell_selectable = False,
            #     #         column_selectable = False
            #     #     )
            #     # ],
            #     # className = 'col-4'),

            #     html.Div([],className = 'col-4') # Empty column

            # ],
            # className = 'row',
            # style = recapdiv
            # ), # Internal row - RECAPS

            html.Div([ # Internal row


                ###### OG 
                # Chart Column
                html.Div([
                    dcc.Graph(id='player_stats',
                                figure=player_stats(),
                                config=config)
                ], 
                # style={'margin': 'auto','height': '100vh', 'text-align': 'center'},
                className = 'col-2'),
                ###### OG 


                # # Chart Column
                # html.Div([
                #     dcc.Graph(
                #         id='page1-count-month')
                # ],
                # className = 'col-4'),

                # # Chart Column
                # html.Div([
                #     dcc.Graph(
                #         id='page1-weekly-heatmap')
                # ],
                # className = 'col-4')

            ],
            className = 'row'), # Internal row

            # html.Div([ # Internal row

            #     # Chart Column
            #     html.Div([
            #         dcc.Graph(
            #             id='page1-count-country')
            #     ],
            #     className = 'col-4'),

            #     # Chart Column
            #     html.Div([
            #         dcc.Graph(
            #             id='page1-bubble-county')
            #     ],
            #     className = 'col-4'),

            #     # Chart Column
            #     html.Div([
            #         dcc.Graph(
            #             id='page1-count-city')
            #     ],
            #     className = 'col-4')

            # ],
            # className = 'row') # Internal row


        ],
        className = 'col-10',
        style = externalgraph_colstyling), # External 10-column

        html.Div([
        ],
        className = 'col-1'), # Blank 1 column

    ],
    className = 'row',
    style = externalgraph_rowstyling
    ), # External row

])





####################################################################################################
# 003 - page3 (current team performance)
####################################################################################################

page3 = html.Div([

    #####################
    #Row 1 : Header
    get_header(),

    #####################
    #Row 2 : Nav bar
    get_navbar('page3'),

    #####################
    #Row 3 : Filters
    html.Div([ # External row

        html.Div([ # External 12-column

            html.Div([ # Internal row

                # #Internal columns
                # html.Div([
                # ],
                # className = 'col-2'), # Blank 2 columns

                ########################################################################################

                #Filter pt 1
                html.Div([

                    html.Div([
                        html.H5(
                            children='Focus Field:',
                            style = {'text-align' : 'left', 'color' : corporate_colors['medium-blue-grey']}
                        ),
                        html.Div([ #'Enter # of days back: ',
                            dcc.Dropdown(id='id-dropdown',
                                         options=[{'label':'Made Field Goals','value':'made_field_goals'},
                                                  {'label':'Made 3p Field Goals','value':'made_three_point_field_goals'},
                                                  {'label':'Made Free Throws','value':'made_free_throws'},
                                                  {'label':'Total Rebounds','value':'total_rebounds'},
                                                  {'label':'Offensive Rebounds','value':'offensive_rebounds'},
                                                  {'label':'Defensive Rebounds','value':'defensive_rebounds'},
                                                  {'label':'Assists','value':'assists'},
                                                  {'label':'Steals','value':'steals'},
                                                  {'label':'Blocks','value':'blocks'},
                                                  {'label':'Turnovers','value':'turnovers'},
                                                  {'label':'Personal Fouls','value':'personal_fouls'},
                                                  {'label':'Points','value':'points'},
                                                  {'label':'Minutes Played','value':'minutes_played'},
                                                  {'label':'Game Score','value':'game_score'}],
                                    value='made_field_goals'
                                )
                        ], style = {'margin-top' : '5px'}
                        )

                    ],
                    style = {'margin-top' : '10px',
                            'margin-bottom' : '5px',
                            'text-align' : 'left',
                            'paddingLeft': 5})

                ],
                className = 'col-4'), # Filter part 1

                ########################################################################################

                #Filter pt 2
                html.Div([

                    html.Div([
                        html.H5(
                            children='League:',
                            style = {'text-align' : 'left', 'color' : corporate_colors['medium-blue-grey']}
                        ),
                        #Date range picker
                        html.Div([#'Focus Field: ',
                            dcc.Dropdown(id='id-league',
                                    options=[{'label':'ESPN','value':'ESPN'},
                                              {'label':'Yahoo','value':'Yahoo'}],
                                              value='ESPN'
                                )

                        ], style = {'margin-top' : '5px'}
                        )

                    ],
                    style = {'margin-top' : '10px',
                            'margin-bottom' : '5px',
                            'text-align' : 'left',
                            'paddingLeft': 5})

                ],
                className = 'col-4'), # Filter part 2
                ########################################################################################                


                #Filter pt 3
                html.Div([

                    html.Div([
                        html.H5(
                            children='Injury Type:',
                            style = {'text-align' : 'left', 'color' : corporate_colors['medium-blue-grey']}
                        ),
                        #Date range picker
                        html.Div([#'Focus Field: ',
                            dcc.Input(id='id-inj-prob',
                                        type='text',
                                        value='flu',
                                        placeholder='wildcard search',
                                )

                        ], style = {'margin-top' : '5px'}
                        )

                    ],
                    style = {'margin-top' : '10px',
                            'margin-bottom' : '5px',
                            'text-align' : 'left',
                            'paddingLeft': 5})

                ],
                className = 'col-4'), # Filter part 2
                ########################################################################################                

                html.Div([
                ],
                className = 'col-2') # Blank 2 columns


            ],
            className = 'row') # Internal row

        ],
        className = 'col-12',
        style = filterdiv_borderstyling) # External 12-column

    ],
    className = 'row sticky-top'), # External row

    #####################
    #Row 4
    get_emptyrow(),

    #####################
    #Row 5 : Charts
    html.Div([ # External row

        html.Div([
        ],
        className = 'col-1'), # Blank 1 column

        html.Div([ # External 10-column
            html.H2(children = "Minutes-Played Weighted Production",
                style = {'color' : corporate_colors['white']}),


            html.Div([ # Internal row 1

                # min-weight focus field prod heatmap
                html.Div([
                    dcc.Graph(id='heat-map', figure=cbc.heatmap(), config=config),
                ],
                className = 'col-6'),
                
                # min-weights
                html.Div([
                    dcc.Graph(id='heat-map-weights', figure=cbc.heatmap_weights(), config=config)
                ],
                className = 'col-6'),

            ],
            className = 'row'), # Internal row 1


            html.Div([ # Internal row 2

                # Chart Column
                html.Div([
                    dcc.Graph(id='line_plot', figure=cbc.line_plot(), config=config)
                ],
                className = 'col-4'),

                # # Chart Column
                # html.Div([
                #     dcc.Graph(
                #         id='page1-bubble-county')
                # ],
                # className = 'col-4'),

                # # Chart Column
                # html.Div([
                #     dcc.Graph(
                #         id='page1-count-city')
                # ],
                # className = 'col-4')

            ],
            className = 'row'), # Internal row 2


            html.Div([ # Internal row 3

                # Chart Column
                html.Div([
                    dcc.Graph(id='bar-plot', figure=cbc.bar_plot(), config=config)
                ],
                className = 'col-4'),

                # # Chart Column
                # html.Div([
                #     dcc.Graph(
                #         id='page1-bubble-county')
                # ],
                # className = 'col-4'),

                # # Chart Column
                # html.Div([
                #     dcc.Graph(
                #         id='page1-count-city')
                # ],
                # className = 'col-4')

            ],
            className = 'row'), # Internal row 3

            html.Div([ # Internal row 4

                # Chart Column
                html.Div([
                    dcc.Graph(id='box-plot', figure=cbc.boxplot_by_player(), config=config)
                ],
                className = 'col-12'),

                # # Chart Column
                # html.Div([
                #     dcc.Graph(
                #         id='page1-bubble-county')
                # ],
                # className = 'col-4'),

                # # Chart Column
                # html.Div([
                #     dcc.Graph(
                #         id='page1-count-city')
                # ],
                # className = 'col-4')

            ],
            className = 'row'), # Internal row 4

            html.Div([ # Internal row 5

                # Chart Column
                html.Div([
                    dcc.Graph(id='box-plot-x-week-class', figure=cbc.boxplot_by_player_weekday_class(), config=config)
                ],
                className = 'col-12'),

                # # Chart Column
                # html.Div([
                #     dcc.Graph(
                #         id='page1-bubble-county')
                # ],
                # className = 'col-4'),

                # # Chart Column
                # html.Div([
                #     dcc.Graph(
                #         id='page1-count-city')
                # ],
                # className = 'col-4')

            ],
            className = 'row'), # Internal row 5

            html.Div([ # Internal row 6

                # Players at risk table and title
                html.Div([
                    html.H5("Players at risk of being \n picked up if dropped",
                        style={'color': corporate_colors['white']}),
                    dash_table.DataTable(
                        id='id-my-team',
                        data=players_at_risk.to_dict('records'),
                        columns=[{"name": i, "id": i} for i in players_at_risk.columns],
                        style_cell=dict(textAlign='left'),
                        style_header=dict(backgroundColor="paleturquoise"),
                        style_table={'overflowX':'auto','width':'100%'},
                    )
                ],
                className='col-md-4 col-sm-12'),

                # Injured Players table and title
                html.Div([
                    html.H5("Injured Players",
                        style={'color': corporate_colors['white']}),
                    dash_table.DataTable(
                        id='id-injured',
                        data=inj_df.to_dict('records'),
                        columns=[{"name": i, "id": i} for i in inj_df.columns],
                        style_cell=dict(textAlign='left'),
                        style_header=dict(backgroundColor="paleturquoise"),
                        style_table={'overflowX':'auto','width':'100%'},
                    )
                ],
                className='col-md-4 col-sm-12'),

                # Expected games this week table and title
                html.Div([
                    html.H5("Expected games this week",
                        style={'color': corporate_colors['white']}),
                    dash_table.DataTable(
                        id='my-table',
                        data=aggregate_yh.to_dict('records'),
                        columns=[{"name": i, "id": i} for i in aggregate_yh.columns],
                        style_cell=dict(textAlign='left'),
                        style_header=dict(backgroundColor="paleturquoise"),
                        style_table={'overflowX':'auto','width':'100%'},
                    )
                ],
                className='col-md-4 col-sm-12'),

            ],
            className='row'),  # Internal row 6

            html.Div([ # Internal row 7

                html.H6("Probability of injury duration",
                    style={'color':corporate_colors['white']}),
                # Chart Column
                html.Div([
                    dash_table.DataTable(id='id-inj-prob-table',
                                        data=injury_probabilities_df.to_dict('records'),
                                        columns=[{"name":i,"id":i} if i != 'probabilities' else {"name":i,"id":i,"type":"numeric","format": {"specifier":'.2%'}} for i in injury_probabilities_df.columns],
                                        style_cell=dict(textAlign='left'),
                                        style_header=dict(backgroundColor="paleturquoise")
                                    )
                ],
                className = 'col-md-4 col-sm-12'),

                # # Chart Column
                # html.Div([
                #     dcc.Graph(
                #         id='page1-bubble-county')
                # ],
                # className = 'col-4'),

                # # Chart Column
                # html.Div([
                #     dcc.Graph(
                #         id='page1-count-city')
                # ],
                # className = 'col-4')

            ],
            className = 'row'), # Internal row 7


        ],
        className = 'col-10',
        style = externalgraph_colstyling), # External 10-column

        html.Div([
        ],
        className = 'col-1'), # Blank 1 column

    ],
    className = 'row',
    style = externalgraph_rowstyling
    ), # External row

])






