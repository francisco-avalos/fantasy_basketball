import dash
import plotly.graph_objects as go
import plotly.express as px
import mysql.connector as mysql
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import dash_bootstrap_components as dbc
import plotly.figure_factory as ff
import random


from mysql.connector import Error
from dash import dcc, html, Input, Output, dash_table
from espn_api.basketball import League
from my_functions import clean_string, remove_name_suffixes



exec(open('/Users/franciscoavalosjr/Desktop/basketball-creds.py').read())

connection=mysql.connect(host=sports_db_admin_host,
                        database=sports_db_admin_db,
                        user=sports_db_admin_user,
                        password=sports_db_admin_pw,
                        port=sports_db_admin_port)

league=League(league_id=leagueid, 
                year=2023,
                espn_s2=espn_s2,
                swid=swid, 
                debug=False)


if connection.is_connected():
    cursor=connection.cursor()
    cursor.execute("""
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
                    """)
    myteam_df=cursor.fetchall()
    myteam_df=pd.DataFrame(myteam_df, columns=cursor.column_names)

if connection.is_connected():
    cursor=connection.cursor()
    cursor.execute("""SELECT * FROM basketball.injured_player_news ORDER BY exp_return_date ASC;""")
    inj_df=cursor.fetchall()
    inj_df=pd.DataFrame(inj_df, columns=cursor.column_names)


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

my_safe_players=['Jordan Poole', 'Anthony Davis',
                 'Tyrese Haliburton', 'Jrue Holiday',
                 'Jimmy Butler', 'Jarrett Allen'
]



myteam=league.teams[11]
current_players=clean_string(myteam.roster).split(',')
current_players=[remove_name_suffixes(x) for x in current_players]
current_players=[x.strip(' ') for x in current_players]

players_at_risk=list(set(current_players)-set(my_safe_players))
players_at_risk=pd.DataFrame(players_at_risk)
players_at_risk.columns=['Name']


# I picked up bruce brown on November 30 at 10pm, 
# so don't add his scores to my team performance for that day
# same with T.J. McConnell for dec 2
# same with Tim Hardaway for dec 3
myteam_df=myteam_df.drop(235)
myteam_df=myteam_df.drop(249)
myteam_df=myteam_df.drop(255)


connection=mysql.connect(host=sports_db_admin_host,
                        database=sports_db_admin_db,
                        user=sports_db_admin_user,
                        password=sports_db_admin_pw,
                        port=sports_db_admin_port)

myteam=league.teams[11]
my_players=clean_string(myteam.roster).split(',')

main_df=pd.DataFrame()
if connection.is_connected():
    for p in my_players:
        cursor=connection.cursor()
        p=remove_name_suffixes(p)
        p=p.strip()
        qry=f"""
            SELECT
                name,
                team,
                TSCHED.*
            FROM basketball.my_team_stats MTS
            JOIN basketball.high_level_nba_team_schedules TSCHED ON MTS.team = TSCHED.away_team OR MTS.team = TSCHED.home_team
            JOIN basketball.calendar CAL ON DATE(SUBDATE(CAST(TSCHED.start_time AS DATETIME), INTERVAL 8 HOUR)) = CAL.day
            WHERE MTS.name LIKE CONCAT("%", "{p}","%")
                AND CURDATE() BETWEEN CAL.week_starting_monday AND CAL.week_ending_sunday
            GROUP BY MTS.name, TSCHED.start_time;"""
        cursor.execute(qry)
        myteam_df1=cursor.fetchall()
        myteam_df1=pd.DataFrame(myteam_df1, columns=cursor.column_names)
        main_df=pd.concat([main_df, myteam_df1])


aggregate=main_df.groupby(['name']).start_time.nunique()
aggregate=aggregate.reset_index()
aggregate.columns=['name', 'games_this_week']
aggregate=aggregate.sort_values(['games_this_week', 'name'], ascending=False)

if(connection.is_connected()):
    cursor.close()
    connection.close()
    print('Script finished - MySQL connection is closed')
else:
    print('MySQL already closed')



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

# print(myteam_df.dtypes)

app=dash.Dash('francisco app',
            external_stylesheets=[dbc.themes.BOOTSTRAP]
)


# myteam_df=myteam_df.sort_values(by='week_ending_sunday')
xaxis=pd.date_range(min(myteam_df['week_ending_sunday'].unique()),max(myteam_df['week_ending_sunday'].unique()), freq='W')

# myteam_df_x_we=myteam_df.groupby(by=['week_ending_sunday','name'])['points'].sum()

# myteam_df_x_we=myteam_df_x_we.reset_index()

# # myteam_df_x_we['pct']=myteam_df_x_we.points/myteam_df_x_we.groupby('week_ending_sunday')['points'].sum()
# myteam_df_x_we['pct']=myteam_df_x_we.points/myteam_df_x_we.groupby('week_ending_sunday')['points'].transform('sum')
# myteam_df_x_we['pct']=pd.to_numeric(myteam_df_x_we['pct'])
# myteam_df_x_we['pct']=myteam_df_x_we['pct'].round(4)
# # myteam_df_x_we['pct']=myteam_df_x_we['pct'].apply(lambda x: '{0:1.2}%'.format(x))

# pct_df=myteam_df_x_we.groupby('week_ending_sunday').reset_index()
# myteam_df_x_we.groupby('week_ending_sunday')['points'].sum()
# print(myteam_df_x_we.head())
random.seed(11)
mycolors=px.colors.qualitative.Light24+px.colors.qualitative.Pastel1+px.colors.qualitative.Vivid+px.colors.qualitative.Set1
random.shuffle(mycolors)

# print(myteam_df.head())

def line_plot(metric='points'):
    myteam_df_x_we=myteam_df.groupby(by=['week_ending_sunday','name'])[metric].sum()
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

def bar_plot(metric='points'):
    myteam_df_x_we=myteam_df.groupby(by=['week_ending_sunday','name'])[metric].sum()
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
imps=[metric]
output=myteam_df.groupby(['name']).apply(lambda x: pd.Series([sum(x[v]*x.minutes_played)/sum(x.minutes_played) for v in imps]))
output.columns=imps

mins_agg=myteam_df.groupby(['name'])['minutes_played'].sum()

output=pd.merge(output, mins_agg, how='inner', on='name')

output=output.sort_values(by=metric, ascending=False)
# output=output.sort_values(by=[focus_field_value],ascending=False).head(player_sample)

output=output[output.index.isin(current_players)]
# output=output.reset_index()
# print(output.head())
# print(output.index)






def heatmap(metric='points'):

    imps=[metric]
    output=myteam_df.groupby(['name']).apply(lambda x: pd.Series([sum(x[v]*x.minutes_played)/sum(x.minutes_played) for v in imps]))
    output.columns=imps
    
    # mins_agg=myteam_df.groupby(['name'])['minutes_played'].sum()

    # output=pd.merge(output, mins_agg, how='inner', on='name')

    output=output.sort_values(by=metric, ascending=False)
    # output=output.sort_values(by=[focus_field_value],ascending=False).head(player_sample)

    output=output[output.index.isin(current_players)]
    fig=px.imshow(output, 
                    text_auto='.2f', 
                    color_continuous_scale='RdBu_r',
                    aspect='auto'
    )
    fig.update_xaxes(side='top')
    fig.update_yaxes(title=None)
    fig.update_layout(width=300,height=400)

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

def heatmap_weights():
    metric='minutes_played'

    mins_agg=myteam_df.groupby(['name'])['minutes_played'].sum()
    mins_agg.columns=metric
    mins_agg=pd.DataFrame(mins_agg)
    mins_agg=mins_agg.sort_values(by=metric, ascending=False)
    mins_agg=mins_agg[mins_agg.index.isin(current_players)]
    fig=px.imshow(mins_agg, 
                    text_auto='.2f', 
                    color_continuous_scale='RdBu_r',
                    aspect='auto'
    )
    fig.update_xaxes(side='top')
    fig.update_yaxes(title=None)
    fig.update_layout(width=300,height=400)

    return fig

# print(myteam_df[myteam_df['name'].isin(current_players)].head())
def boxplot_by_player(metric='points'):
    myteam_df_v1=myteam_df[myteam_df['name'].isin(current_players)]
    fig1=px.box(myteam_df_v1, x='name', y=metric)
    fig1.update_traces(quartilemethod='exclusive')
    return fig1

def boxplot_by_player_weekday_class(metric='points'):
    myteam_df_v2=myteam_df[myteam_df['name'].isin(current_players)]
    fig=px.box(myteam_df_v2, x='name', y=metric, 
                facet_row='day_of_week_class'
    )
    fig.update_traces(quartilemethod='exclusive')
    return fig


# metric='made_field_goals'
# names=[name for name in myteam_df.name.unique()]
# data_list=[]
# for name in names:
#     name_values=myteam_df[myteam_df['name']==name][metric].values.tolist()
#     data_list.append(name_values)

# # data_list=pd.Series(data_list)
# # print(type(data_list))
# # print(type(names))
# # print(data_list)
# # print(names)

# # # print(len(data_list))
# # print(names)
# # print(data_list)
# # # # print(unlist(data_list))
# # print(data_list[0:10])
# fig=ff.create_distplot(data_list,
#     names, show_rug=False, colors=mycolors)
# fig.show()



# print(myteam_df.head())


app.layout=dbc.Container(
    [
        dbc.Row(
            html.H1('My team performance', style={'textAlign': 'center'})
        ),
        dbc.Row(
            [
                dbc.Col(
                    [
                        html.H3('Minutes-Played Weighted Production'),
                        dcc.Graph(id='heat-map', figure=heatmap())
                    ], 
                    width=6, 
                    align='start'
                ),
                dbc.Col(
                    [
                        dcc.Graph(id='heat-map-weights', figure=heatmap_weights())
                    ],
                    width=6,
                    align='end'
                )
            ]
        ),
        dbc.Row(
            [
                dbc.Col(
                    [dcc.Graph(id='line_plot', figure=line_plot())],
                    md=4
                    # align='start',
                    # offset=0
                    # width={'md':4, 'offset':0, 'order':'start'}
                )
            ], align='center'
        ),
        dbc.Row(
            [
                dbc.Col(
                    [dcc.Dropdown(id='id-dropdown',
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
                    )],
                    lg=3
                )
            ]
        ),
        dbc.Row(
            [
                dbc.Col(
                    [dcc.Graph(id='bar-plot', figure=bar_plot())],
                    width=8,
                    align='end'
                )
            ]
        ),
        dbc.Row(
            [
                dbc.Col(
                    [dcc.Graph(id='box-plot', figure=boxplot_by_player())]
                )
            ]
        ),
        dbc.Row(
            [
                dbc.Col(
                    [dcc.Graph(id='box-plot-x-week-class', figure=boxplot_by_player_weekday_class())]
                )
            ]
        ),
        dbc.Row(
            [
                dbc.Col(
                    [
                        html.H2('Players at risk if dropped'),
                        dash_table.DataTable(data=players_at_risk.to_dict('records'),
                                                    columns=[{"name": i, "id": i} for i in players_at_risk.columns],
                                                    style_cell=dict(textAlign='left'),
                                                    style_header=dict(backgroundColor="paleturquoise")    
                        )
                    ],
                    md=4
                    # align='center'
                    # width={'size':1, 'order':'last'}
                ),
                dbc.Col(
                    [
                        html.H3('Injured players report'),
                        dash_table.DataTable(data=inj_df.to_dict('records'),
                                                    columns=[{"name": i, "id": i} for i in inj_df.columns],
                                                    style_cell=dict(textAlign='left'),
                                                    style_header=dict(backgroundColor="paleturquoise")    
                        )
                    ],
                    md=4
                    # align='center'
                    # width={'size':1, 'order':'last'}
                )

            ]
        ),
        dbc.Row(
            [
                dbc.Col(
                    [
                        html.H2('Games expected this week by players'),
                        dash_table.DataTable(data=aggregate.to_dict('records'),
                                                    columns=[{"name": i, "id": i} for i in aggregate.columns],
                                                    style_cell=dict(textAlign='left'),
                                                    style_header=dict(backgroundColor="paleturquoise")
                        )
                    ],
                    md=4
                )
            ]
        )
    ]
)


@app.callback(
    Output(component_id='line_plot', component_property='figure'),
    Output(component_id='bar-plot', component_property='figure'),
    Output(component_id='heat-map', component_property='figure'),
    Output(component_id='box-plot', component_property='figure'),
    Output(component_id='box-plot-x-week-class', component_property='figure'),
    Input(component_id='id-dropdown', component_property='value')
)

def update_plots(metric_value):
    fig_line=line_plot(metric_value)
    fig_bar=bar_plot(metric_value)
    fig_heat=heatmap(metric_value)
    fig_box=boxplot_by_player(metric_value)
    fig_box_x_week=boxplot_by_player_weekday_class(metric_value)
    return fig_line, fig_bar, fig_heat, fig_box, fig_box_x_week


# app.layout=html.Div(children=[
#                             html.H1('My team performance',
#                                     style={'textAlign':'center'}
#                             ),
#                             dcc.Graph(id='line-plot',
#                                      figure=line_plot()
#                             ),
#                             dcc.Graph(id='bar-plot',
#                                      figure=bar_plot()
#                             ),
#                             dcc.Graph(id='heat-map',
#                                     figure=heatmap()
#                             ),
#                             html.Label("Players at risk if dropped"
#                             ),
#                             dash_table.DataTable(data=players_at_risk.to_dict('records'),
#                                                 columns=[{"name": i, "id": i} for i in players_at_risk.columns],
#                                                 style_cell=dict(textAlign='left'),
#                                                 style_header=dict(backgroundColor="paleturquoise")
#                             )
# ])




if __name__ == '__main__': 
    app.run(port=8005)











