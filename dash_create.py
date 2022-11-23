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



exec(open('/Users/franciscoavalosjr/Desktop/basketball-creds.py').read())

connection=mysql.connect(host=sports_db_admin_host,
                        database=sports_db_admin_db,
                        user=sports_db_admin_user,
                        password=sports_db_admin_pw,
                        port=sports_db_admin_port)


if connection.is_connected():
    cursor=connection.cursor()
    cursor.execute('SELECT MTS.*, C.week_starting_monday, C.week_ending_sunday FROM basketball.my_team_stats MTS JOIN basketball.calendar C ON MTS.date=C.day;')
    myteam_df=cursor.fetchall()
    myteam_df=pd.DataFrame(myteam_df, columns=cursor.column_names)


if connection.is_connected():
    cursor=connection.cursor()
    cursor.execute('SELECT * FROM basketball.live_free_agents;')
    fa_df=cursor.fetchall()
    fa_df=pd.DataFrame(fa_df, columns=cursor.column_names)

if(connection.is_connected()):
    cursor.close()
    connection.close()
    print('MySQL connection is closed')
else:
    print('MySQL already closed')


pd.set_option('display.max_columns', None)
pd.set_option('display.max_rows', None)


myteam_df['total_rebounds']=myteam_df['offensive_rebounds']+myteam_df['defensive_rebounds']
myteam_df['minutes_played']=myteam_df['seconds_played']/60

fa_df['total_rebounds']=fa_df['offensive_rebounds']+fa_df['defensive_rebounds']
fa_df['minutes_played']=fa_df['seconds_played']/60



######
# myteam_df.head()
cols=['made_field_goals', 'made_three_point_field_goals','made_free_throws', 
      'total_rebounds', 'offensive_rebounds', 'defensive_rebounds', 'assists', 
      'steals', 'blocks', 'turnovers', 'personal_fouls', 'points_scored', 'minutes_played'
     ]

focus_value='made_field_goals'
calc='mean'
player_sample=20
days_ago=7

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

app.layout=html.Div(children=[dcc.Graph(figure=player_stats(), id='line_plot'),
                              'How many days back?',
                              dcc.Input(id='my_input', value=7, type='integer'),
                              'Focus Field\n',
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
                                         value='made_field_goals'),
                              'Calculation type',
                              dcc.Dropdown(id='calculation', 
                                          options=[{'label':'Total', 'value':'sum'},
                                                   {'label':'Average(non-weighted))', 'value':'mean'},
                                                   {'label':'Weighted Average', 'value':'weights'},
                                                   {'label':'Standard Deviation', 'value':'std'}],
                                          value='sum'),
                              'Fields to display',
                             dcc.Checklist(id='displayed_fields', 
                                           options=['made_field_goals', 'made_three_point_field_goals',
                                                    'made_free_throws','total_rebounds', 'offensive_rebounds', 
                                                    'defensive_rebounds', 'assists','steals', 'blocks', 
                                                    'turnovers', 'personal_fouls', 'points_scored', 'minutes_played'],
                                          value=['made_field_goals', 'made_three_point_field_goals',
                                                    'made_free_throws','total_rebounds', 'offensive_rebounds', 
                                                    'defensive_rebounds', 'assists','steals', 'blocks', 
                                                    'turnovers', 'personal_fouls']),
                              'Number of players',
                             dcc.Input(id='top_n', value=5, type='integer'),
                             'player_checklist',
                             dcc.Checklist(id='player_list', options=[name for name in fa_df['name'].unique()], value=[name for name in fa_df['name'].unique()], 
                                style={'height':10000,'width':100})
                             ])


@app.callback(Output(component_id='line_plot', component_property='figure'),
             Input(component_id='my_input', component_property='value'),
             Input(component_id='dropdown', component_property='value'),
             Input(component_id='calculation', component_property='value'),
             Input(component_id='displayed_fields', component_property='value'),
             Input(component_id='top_n', component_property='value'),
             Input(component_id='player_list', component_property='value')
             )


def graph_update(input_value, focus_field_value, calc_value, display_field, top_n_val, player_list):
    cols=['made_field_goals', 'made_three_point_field_goals','made_free_throws', 
    'total_rebounds', 'offensive_rebounds', 'defensive_rebounds', 'assists', 
    'steals', 'blocks', 'turnovers', 'personal_fouls', 'points_scored', 'minutes_played']

    days_ago=int(input_value)
    today=dt.date.today()
    days_back=today-dt.timedelta(days=days_ago)
    
    if top_n_val=='':
        player_sample=5
    else:
        player_sample=int(top_n_val)
    if len(player_list)!=len(fa_df['name'].unique()):
        fa_df1=fa_df[fa_df['name'].isin(player_list)]
    else:
        fa_df1=fa_df

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


if __name__ == '__main__': 
    app.run(port=8005)











