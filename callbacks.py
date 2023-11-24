
import os
import dash
from dash.dependencies import Input, Output

import mysql.connector as mysql
import pandas as pd
import datetime as dt
from dash_create import app
import plotly.express as px

import random







####################################################################################################
# 000 - IMPORT DATA FROM DB - FREE AGENT SCREEN TOOL
####################################################################################################


# prod env 
# sports_db_admin_host=os.environ.get('basketball_host')
# sports_db_admin_db=os.environ.get('basketball_db')
# sports_db_admin_user=os.environ.get('basketball_user')
# sports_db_admin_pw=os.environ.get('basketball_pw')
# sports_db_admin_port=os.environ.get('basketball_port')


# dev env
sports_db_admin_host=os.environ.get('sports_db_admin_host')
sports_db_admin_db='basketball'
sports_db_admin_user=os.environ.get('sports_db_admin_user')
sports_db_admin_pw=os.environ.get('sports_db_admin_pw')
sports_db_admin_port=os.environ.get('sports_db_admin_port')


connection=mysql.connect(host=sports_db_admin_host,
                        database=sports_db_admin_db,
                        user=sports_db_admin_user,
                        password=sports_db_admin_pw,
                        port=sports_db_admin_port)



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



if connection.is_connected():
    cursor=connection.cursor()

    cursor.execute(espn_query)
    fa_espn_df=cursor.fetchall()
    fa_espn_df=pd.DataFrame(fa_espn_df,columns=cursor.column_names)


    cursor.execute(yahoo_query)
    fa_yahoo_df=cursor.fetchall()
    fa_yahoo_df=pd.DataFrame(fa_yahoo_df,columns=cursor.column_names)



if(connection.is_connected()):
    cursor.close()
    connection.close()
    print('MySQL connection is closed')
else:
    print('MySQL already closed')


pd.set_option('display.max_columns', None)
pd.set_option('display.max_rows', None)


fa_espn_df['minutes_played']=fa_espn_df['seconds_played']/60
fa_espn_df['total_rebounds']=fa_espn_df['offensive_rebounds']+fa_espn_df['defensive_rebounds']

fa_df=fa_espn_df[fa_espn_df['current_season_vs_historicals']=='current_season_only'].copy()
fa_df['total_rebounds']=fa_df['offensive_rebounds']+fa_df['defensive_rebounds']
fa_df['minutes_played']=fa_df['seconds_played']/60


fa_yahoo_df['total_rebounds']=fa_yahoo_df['offensive_rebounds']+fa_yahoo_df['defensive_rebounds']
fa_yahoo_df['minutes_played']=fa_yahoo_df['seconds_played']/60







####################################################################################################
# 000 - FREE AGENT SCREEN TOOL
####################################################################################################


@app.callback(Output(component_id='line_plot', component_property='figure'),
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


if(connection.is_connected()):
    cursor.close()
    connection.close()
    print('MySQL connection is closed')
else:
    print('MySQL already closed')


####################################################################################################
# 001 - CURRENT TEAM PERFORMANCE
####################################################################################################








































