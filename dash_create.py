import os
import dash
from dash import dcc
from dash import html
# import plotly.graph_objects as go
import plotly.express as px
from dash.dependencies import Input, Output

import mysql.connector as mysql
import pandas as pd
from mysql.connector import Error
import datetime as dt



# exec(open('/Users/franciscoavalosjr/Desktop/basketball-creds.py').read())


sports_db_admin_host=os.environ.get('basketball_host')
sports_db_admin_db=os.environ.get('basketball_db')
sports_db_admin_user=os.environ.get('basketball_user')
sports_db_admin_pw=os.environ.get('basketball_pw')
sports_db_admin_port=os.environ.get('basketball_port')


connection=mysql.connect(host=sports_db_admin_host,
                        database=sports_db_admin_db,
                        user=sports_db_admin_user,
                        password=sports_db_admin_pw,
                        port=sports_db_admin_port)

# hist_and_current_query="""
# SELECT 
#     EFA.name,
#     EFA.date,
#     EFA.team,
#     EFA.location,
#     EFA.opponent,
#     EFA.outcome,
#     EFA.seconds_played,
#     EFA.made_field_goals,
#     EFA.attempted_field_goals,
#     EFA.made_three_point_field_goals,
#     EFA.attempted_three_point_field_goals,
#     EFA.made_free_throws,
#     EFA.attempted_free_throws,
#     EFA.offensive_rebounds,
#     EFA.defensive_rebounds,
#     EFA.assists,
#     EFA.steals,
#     EFA.blocks,
#     EFA.turnovers,
#     EFA.personal_fouls,
#     EFA.points_scored,
#     EFA.game_score,
#     EFA.name_code
# FROM basketball.live_free_agents EFA
# WHERE EFA.seconds_played!=0
# UNION ALL
# SELECT 
#     HPD.name,
#     HPD.date,
#     HPD.team,
#     HPD.location,
#     HPD.opponent,
#     HPD.outcome,
#     HPD.seconds_played,
#     HPD.made_field_goals,
#     HPD.attempted_field_goals,
#     HPD.made_three_point_field_goals,
#     HPD.attempted_three_point_field_goals,
#     HPD.made_free_throws,
#     HPD.attempted_free_throws,
#     HPD.offensive_rebounds,
#     HPD.defensive_rebounds,
#     HPD.assists,
#     HPD.steals,
#     HPD.blocks,
#     HPD.turnovers,
#     HPD.personal_fouls,
#     HPD.points AS points_scored,
#     HPD.game_score,
#     HPD.slug AS name_code
# FROM basketball.historical_player_data HPD
# JOIN (SELECT DISTINCT name_code FROM basketball.live_free_agents) FA ON HPD.slug = FA.name_code
# WHERE season != '2022-23';"""


# hist_only_query="""
# SELECT 
#     HPD.name,
#     HPD.date,
#     HPD.team,
#     HPD.location,
#     HPD.opponent,
#     HPD.outcome,
#     HPD.seconds_played,
#     HPD.made_field_goals,
#     HPD.attempted_field_goals,
#     HPD.made_three_point_field_goals,
#     HPD.attempted_three_point_field_goals,
#     HPD.made_free_throws,
#     HPD.attempted_free_throws,
#     HPD.offensive_rebounds,
#     HPD.defensive_rebounds,
#     HPD.assists,
#     HPD.steals,
#     HPD.blocks,
#     HPD.turnovers,
#     HPD.personal_fouls,
#     HPD.points AS points_scored,
#     HPD.game_score,
#     HPD.slug AS name_code
# FROM basketball.historical_player_data HPD
# JOIN (SELECT DISTINCT name_code FROM basketball.live_free_agents) FA ON HPD.slug = FA.name_code
# WHERE season != '2022-23';"""


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
    # cursor.execute('SELECT * FROM basketball.live_free_agents WHERE seconds_played!=0;')
    # fa_df=cursor.fetchall()
    # fa_df=pd.DataFrame(fa_df, columns=cursor.column_names)

    cursor.execute(espn_query)
    fa_espn_df=cursor.fetchall()
    fa_espn_df=pd.DataFrame(fa_espn_df,columns=cursor.column_names)

    # cursor.execute(hist_and_current_query)
    # fa_hist_and_current_df=cursor.fetchall()
    # fa_hist_and_current_df=pd.DataFrame(fa_hist_and_current_df,columns=cursor.column_names)

    # cursor.execute(hist_only_query)
    # fa_hist_only_df=cursor.fetchall()
    # fa_hist_only_df=pd.DataFrame(fa_hist_only_df,columns=cursor.column_names)

    cursor.execute(yahoo_query)
    fa_yahoo_df=cursor.fetchall()
    fa_yahoo_df=pd.DataFrame(fa_yahoo_df,columns=cursor.column_names)

    # cursor.execute(yahoo_hist_only_query)
    # fa_yahoo_hist_only_df=cursor.fetchall()
    # fa_yahoo_hist_only_df=pd.DataFrame(fa_yahoo_hist_only_df,columns=cursor.column_names)

    # cursor.execute(yahoo_hist_and_current_query)
    # fa_yahoo_hist_and_current_df=cursor.fetchall()
    # fa_yahoo_hist_and_current_df=pd.DataFrame(fa_yahoo_hist_and_current_df,columns=cursor.column_names)

    # cursor.execute(yahoo_current_only_query)
    # fa_yahoo_current_only_df=cursor.fetchall()
    # fa_yahoo_current_only_df=pd.DataFrame(fa_yahoo_current_only_df,columns=cursor.column_names)


if(connection.is_connected()):
    cursor.close()
    connection.close()
    print('MySQL connection is closed')
else:
    print('MySQL already closed')


pd.set_option('display.max_columns', None)
pd.set_option('display.max_rows', None)


fa_df=fa_espn_df[fa_espn_df['current_season_vs_historicals']=='current_season_only']
fa_df['total_rebounds']=fa_df['offensive_rebounds']+fa_df['defensive_rebounds']
fa_df['minutes_played']=fa_df['seconds_played']/60

# fa_hist_and_current_df['total_rebounds']=fa_hist_and_current_df['offensive_rebounds']+fa_hist_and_current_df['defensive_rebounds']
# fa_hist_and_current_df['minutes_played']=fa_hist_and_current_df['seconds_played']/60

# fa_hist_only_df['total_rebounds']=fa_hist_only_df['offensive_rebounds']+fa_hist_only_df['defensive_rebounds']
# fa_hist_only_df['minutes_played']=fa_hist_only_df['seconds_played']/60


fa_yahoo_df['total_rebounds']=fa_yahoo_df['offensive_rebounds']+fa_yahoo_df['defensive_rebounds']
fa_yahoo_df['minutes_played']=fa_yahoo_df['seconds_played']/60

# default_value=0


# fa_yahoo_hist_only_df['offensive_rebounds'].fillna(default_value,inplace=True)
# fa_yahoo_hist_only_df['defensive_rebounds'].fillna(default_value,inplace=True)
# fa_yahoo_hist_only_df['seconds_played'].fillna(default_value,inplace=True)

# fa_yahoo_hist_only_df['total_rebounds']=fa_yahoo_hist_only_df['offensive_rebounds']+fa_yahoo_hist_only_df['defensive_rebounds']
# fa_yahoo_hist_only_df['minutes_played']=fa_yahoo_hist_only_df['seconds_played']/60



# fa_yahoo_hist_and_current_df['offensive_rebounds'].fillna(default_value,inplace=True)
# fa_yahoo_hist_and_current_df['defensive_rebounds'].fillna(default_value,inplace=True)
# fa_yahoo_hist_and_current_df['seconds_played'].fillna(default_value,inplace=True)

# fa_yahoo_hist_and_current_df['total_rebounds']=fa_yahoo_hist_and_current_df['offensive_rebounds']+fa_yahoo_hist_and_current_df['defensive_rebounds']
# fa_yahoo_hist_and_current_df['minutes_played']=fa_yahoo_hist_and_current_df['seconds_played']/60



# fa_yahoo_current_only_df['offensive_rebounds'].fillna(default_value,inplace=True)
# fa_yahoo_current_only_df['defensive_rebounds'].fillna(default_value,inplace=True)
# fa_yahoo_current_only_df['seconds_played'].fillna(default_value,inplace=True)

# fa_yahoo_current_only_df['total_rebounds']=fa_yahoo_current_only_df['offensive_rebounds']+fa_yahoo_current_only_df['defensive_rebounds']
# fa_yahoo_current_only_df['minutes_played']=fa_yahoo_current_only_df['seconds_played']/60



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
# calc_presentation='Standard Deviation' if calc=='std' else 'Average' if calc=='Mean' else 'Total'


# sn.set(rc={'figure.figsize':(15,8)})

df_query=fa_df.query("date >= @days_back")

output=df_query.groupby(['name'])[cols].agg(calc).reset_index().sort_values(by=[focus_value],ascending=False).head(player_sample)

output.set_index(['name'], inplace=True, drop=True, append=False)
output.reset_index(inplace=False)
# cmap='Spectral_r'
# sn.heatmap(output.iloc[:,0:len(output)-1], annot=True, cmap=cmap)

# plt.suptitle(f'Past {days_ago} day(s) - {calc_presentation} Analysis')
# plt.title(f'{focus_value} leading')
# plt.show()

# fig=px.imshow(output, text_auto=True)
# fig.update_xaxes(side='top')
# fig.layout.height=800
# fig.layout.width=800
# fig.show()

short_df = output.iloc[:,0:len(output)]

######


def player_stats():
    fig=px.imshow(short_df, text_auto=True)
    fig.update_xaxes(side='top')
    fig.layout.height=750
    fig.layout.width=750
    return fig



app=dash.Dash()

server = app.server

app.layout=html.Div(children=[html.H1(children='Free Agent Analysis Helper Tool',
                                        style={'textAlign':'center'}),
                              html.Div(children='Analysis tool to screen potential star players',
                                        style={'textAlign':'center', 'color':'red'}), 
                             dcc.Graph(figure=player_stats(), id='line_plot'),
                              'How many days back?\n',
                              dcc.Input(id='my_input', value=365, type='integer'),
                              'Focus Field\n',
                             html.Div(dcc.Dropdown(id='dropdown',
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
                                         value='points_scored')),

                             # dcc.Dropdown(id='dropdown',
                             #             options=[{'label':'Made Field Goals','value':'made_field_goals'},
                             #                      {'label':'Made 3p Field Goals','value':'made_three_point_field_goals'},
                             #                      {'label':'Made Free Throws','value':'made_free_throws'},
                             #                      {'label':'Total Rebounds','value':'total_rebounds'},
                             #                      {'label':'Offensive Rebounds','value':'offensive_rebounds'},
                             #                      {'label':'Defensive Rebounds','value':'defensive_rebounds'},
                             #                      {'label':'Assists','value':'assists'},
                             #                      {'label':'Steals','value':'steals'},
                             #                      {'label':'Blocks','value':'blocks'},
                             #                      {'label':'Turnovers','value':'turnovers'},
                             #                      {'label':'Personal Fouls','value':'personal_fouls'},
                             #                      {'label':'Points','value':'points_scored'},
                             #                      {'label':'Minutes Played','value':'minutes_played'}],
                             #             value='made_field_goals'),
                              'Calculation type',
                              dcc.Dropdown(id='calculation', 
                                          options=[{'label':'Total', 'value':'sum'},
                                                   {'label':'Average(non-weighted))', 'value':'mean'},
                                                   {'label':'Weighted Average', 'value':'weights'},
                                                   {'label':'Standard Deviation', 'value':'std'}],
                                          value='weights'),
                              'Fields to display',
                             dcc.Checklist(id='displayed_fields', 
                                           options=['made_field_goals', 'made_three_point_field_goals',
                                                    'made_free_throws','total_rebounds', 'offensive_rebounds', 
                                                    'defensive_rebounds', 'assists','steals', 'blocks', 
                                                    'turnovers', 'personal_fouls', 'points_scored', 'minutes_played'],
                                          value=['made_field_goals', 'made_three_point_field_goals',
                                                    'made_free_throws','total_rebounds', 'offensive_rebounds', 
                                                    'defensive_rebounds','assists','steals', 'blocks', 
                                                    'turnovers', 'points_scored']),
                              'Number of players',
                             dcc.Input(id='top_n', value=5, type='integer'),
                             'historicals options',
                             dcc.Dropdown(id='history_id',
                                            options=[{'label':'history-only','value':'ho'},
                                                    {'label':'history + current season ','value':'hcs'},
                                                    {'label':'current season only','value':'cso'}],
                                            value='ho'),
                             'League',
                             dcc.Dropdown(id='league_id',
                                            options=[{'label':'ESPN', 'value':'espn'},
                                                    {'label':'Yahoo','value':'yahoo'}],
                                            value='espn'),
                             'player_checklist',
                             dcc.Checklist(id='player_list', options=[name for name in fa_df['name'].unique()], value=[name for name in fa_df['name'].unique()], 
                                style={'height':10000,'width':100}, inline=True)
                             ])


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
     'total_rebounds']

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
                output=df_query1.groupby(['name']).apply(lambda x: pd.Series([sum(x[v]*x.minutes_played)/sum(x.minutes_played) for v in imps]))
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
                output=fa_hist_only_df1.groupby(['name']).apply(lambda x: pd.Series([sum(x[v]*x.minutes_played)/sum(x.minutes_played) for v in imps]))
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
                output=fa_hist_and_current_df1.groupby(['name']).apply(lambda x: pd.Series([sum(x[v]*x.minutes_played)/sum(x.minutes_played) for v in imps]))
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
                output=fa_yahoo_current_only_df1.groupby(['name']).apply(lambda x: pd.Series([sum(x[v]*x.minutes_played)/sum(x.minutes_played) for v in imps]))
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
                output=fa_yahoo_hist_only_df1.groupby(['name']).apply(lambda x: pd.Series([sum(x[v]*x.minutes_played)/sum(x.minutes_played) for v in imps]))
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
                output=fa_yahoo_hist_and_current_df1.groupby(['name']).apply(lambda x: pd.Series([sum(x[v]*x.minutes_played)/sum(x.minutes_played) for v in imps]))
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



if __name__ == '__main__': 
    app.run(port=8006)











