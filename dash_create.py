import os
import dash
from dash import dcc
from dash import html
import plotly.graph_objects as go
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

hist_and_current_query="""
SELECT 
    EFA.name,
    EFA.date,
    EFA.team,
    EFA.location,
    EFA.opponent,
    EFA.outcome,
    EFA.seconds_played,
    EFA.made_field_goals,
    EFA.attempted_field_goals,
    EFA.made_three_point_field_goals,
    EFA.attempted_three_point_field_goals,
    EFA.made_free_throws,
    EFA.attempted_free_throws,
    EFA.offensive_rebounds,
    EFA.defensive_rebounds,
    EFA.assists,
    EFA.steals,
    EFA.blocks,
    EFA.turnovers,
    EFA.personal_fouls,
    EFA.points_scored,
    EFA.game_score,
    EFA.name_code
FROM basketball.live_free_agents EFA
WHERE EFA.seconds_played!=0
UNION ALL
SELECT 
    HPD.name,
    HPD.date,
    HPD.team,
    HPD.location,
    HPD.opponent,
    HPD.outcome,
    HPD.seconds_played,
    HPD.made_field_goals,
    HPD.attempted_field_goals,
    HPD.made_three_point_field_goals,
    HPD.attempted_three_point_field_goals,
    HPD.made_free_throws,
    HPD.attempted_free_throws,
    HPD.offensive_rebounds,
    HPD.defensive_rebounds,
    HPD.assists,
    HPD.steals,
    HPD.blocks,
    HPD.turnovers,
    HPD.personal_fouls,
    HPD.points AS points_scored,
    HPD.game_score,
    HPD.slug AS name_code
FROM basketball.historical_player_data HPD
JOIN (SELECT DISTINCT name_code FROM basketball.live_free_agents) FA ON HPD.slug = FA.name_code
WHERE season != '2022-23';"""


hist_only_query="""
SELECT 
    HPD.name,
    HPD.date,
    HPD.team,
    HPD.location,
    HPD.opponent,
    HPD.outcome,
    HPD.seconds_played,
    HPD.made_field_goals,
    HPD.attempted_field_goals,
    HPD.made_three_point_field_goals,
    HPD.attempted_three_point_field_goals,
    HPD.made_free_throws,
    HPD.attempted_free_throws,
    HPD.offensive_rebounds,
    HPD.defensive_rebounds,
    HPD.assists,
    HPD.steals,
    HPD.blocks,
    HPD.turnovers,
    HPD.personal_fouls,
    HPD.points AS points_scored,
    HPD.game_score,
    HPD.slug AS name_code
FROM basketball.historical_player_data HPD
JOIN (SELECT DISTINCT name_code FROM basketball.live_free_agents) FA ON HPD.slug = FA.name_code
WHERE season != '2022-23';"""


if connection.is_connected():
    cursor=connection.cursor()
    cursor.execute('SELECT * FROM basketball.live_free_agents WHERE seconds_played!=0;')
    fa_df=cursor.fetchall()
    fa_df=pd.DataFrame(fa_df, columns=cursor.column_names)

    cursor.execute(hist_and_current_query)
    fa_hist_and_current_df=cursor.fetchall()
    fa_hist_and_current_df=pd.DataFrame(fa_hist_and_current_df,columns=cursor.column_names)

    cursor.execute(hist_only_query)
    fa_hist_only_df=cursor.fetchall()
    fa_hist_only_df=pd.DataFrame(fa_hist_only_df,columns=cursor.column_names)

if(connection.is_connected()):
    cursor.close()
    connection.close()
    print('MySQL connection is closed')
else:
    print('MySQL already closed')


pd.set_option('display.max_columns', None)
pd.set_option('display.max_rows', None)



fa_df['total_rebounds']=fa_df['offensive_rebounds']+fa_df['defensive_rebounds']
fa_df['minutes_played']=fa_df['seconds_played']/60

fa_hist_and_current_df['total_rebounds']=fa_hist_and_current_df['offensive_rebounds']+fa_hist_and_current_df['defensive_rebounds']
fa_hist_and_current_df['minutes_played']=fa_hist_and_current_df['seconds_played']/60

fa_hist_only_df['total_rebounds']=fa_hist_only_df['offensive_rebounds']+fa_hist_only_df['defensive_rebounds']
fa_hist_only_df['minutes_played']=fa_hist_only_df['seconds_played']/60



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
                                                    'assists','steals', 'blocks', 
                                                    'turnovers', 'points_scored']),
                              'Number of players',
                             dcc.Input(id='top_n', value=5, type='integer'),
                             'historicals options',
                             dcc.Dropdown(id='history_id',
                                            options=[{'label':'history-only','value':'ho'},
                                                    {'label':'history + current season ','value':'hcs'},
                                                    {'label':'current season only','value':'cso'}],
                                            value='cso'),
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
             Input(component_id='player_list', component_property='value')
             )


def graph_update(input_value, focus_field_value, calc_value, display_field, top_n_val,history_id,player_list):
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
    

    if history_id=='cso':
        if top_n_val=='':
            player_sample=5
        else:
            player_sample=int(top_n_val)
        if len(player_list)!=len(fa_df['name'].unique()):
            fa_df1=fa_df[fa_df['name'].isin(player_list)]
        else:
            fa_df1=fa_df

        df_query=fa_df1.query("date >= @days_back")

        if calc_value=='weights':
            output=df_query.groupby(['name']).apply(lambda x: pd.Series([sum(x[v]*x.minutes_played)/sum(x.minutes_played) for v in imps]))
            output.columns=imps
            output=output[display_field]
            output=output.sort_values(by=[focus_field_value],ascending=False).head(player_sample)
        else:
            output=df_query.groupby(['name'])[cols].agg(calc_value).reset_index().sort_values(by=[focus_field_value],ascending=False).head(player_sample)
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

if __name__ == '__main__': 
    app.run(port=8006)











