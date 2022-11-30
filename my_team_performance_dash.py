import dash
import plotly.graph_objects as go
import plotly.express as px
import mysql.connector as mysql
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import dash_bootstrap_components as dbc


from mysql.connector import Error
from dash import dcc, html, Input, Output, dash_table




exec(open('/Users/franciscoavalosjr/Desktop/basketball-creds.py').read())

connection=mysql.connect(host=sports_db_admin_host,
                        database=sports_db_admin_db,
                        user=sports_db_admin_user,
                        password=sports_db_admin_pw,
                        port=sports_db_admin_port)


if connection.is_connected():
    cursor=connection.cursor()
    cursor.execute("""SELECT MTS.*, C.week_starting_monday, C.week_ending_sunday FROM basketball.my_team_stats MTS JOIN basketball.calendar C ON MTS.date=C.day;""")
    myteam_df=cursor.fetchall()
    myteam_df=pd.DataFrame(myteam_df, columns=cursor.column_names)

if connection.is_connected():
    cursor=connection.cursor()
    cursor.execute("""SELECT 
                        DISTINCT MTS.name
                    FROM basketball.my_team_stats MTS 
                    JOIN basketball.calendar C ON MTS.date=C.day
                    WHERE C.day >= SUBDATE(CURDATE(), INTERVAL 4 DAY);""")
    myteam_df_recent=cursor.fetchall()
    myteam_df_recent=pd.DataFrame(myteam_df_recent, columns=cursor.column_names)


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

current_players = myteam_df_recent.name.unique()
players_at_risk=list(set(current_players)-set(my_safe_players))
players_at_risk=pd.DataFrame(players_at_risk)
players_at_risk.columns=['Name']



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

mycolors=px.colors.qualitative.Light24+px.colors.qualitative.Pastel1


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
        yaxis_tickformat=".2%",
        xaxis=xaxis_formats
    )
    return bar_plot_pct_share

def heatmap():
    heat_map=px.density_heatmap(myteam_df,
                                x='attempted_field_goals',
                                y='name',
                                z='made_field_goals',
                                text_auto=True
    )
    heat_map.update_xaxes(side='top')
    return heat_map


app.layout=dbc.Container(
    [
        dbc.Row(
            html.H1('My team performance', style={'textAlign': 'center'})
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
                                                  {'label':'Minutes Played','value':'minutes_played'}],
                                    value='made_field_goals'
                    )],
                    lg=3
                )
            ]
        ),
        dbc.Row(
            [
                dcc.Graph(id='bar-plot', figure=bar_plot())
            ]
        )
    ]
)


@app.callback(
    Output(component_id='line_plot', component_property='figure'),
    Output(component_id='bar-plot', component_property='figure'),
    Input(component_id='id-dropdown', component_property='value')
)

def update_plots(metric_value):
    fig_line=line_plot(metric_value)
    fig_bar=bar_plot(metric_value)
    return fig_line, fig_bar


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











