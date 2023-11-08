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
import os

from mysql.connector import Error
from dash import dcc, html, Input, Output, dash_table

from my_functions import clean_string, remove_name_suffixes

# Yahoo
from yahoo_oauth import OAuth2
import yahoo_fantasy_api as yfa

# ESPN 
from espn_api.basketball import League



sports_db_admin_host=os.environ.get('basketball_host')
sports_db_admin_db=os.environ.get('basketball_db')
sports_db_admin_user=os.environ.get('basketball_user')
sports_db_admin_pw=os.environ.get('basketball_pw')
sports_db_admin_port=os.environ.get('basketball_port')

# sports_db_admin_host=os.environ.get('sports_db_admin_host')
# sports_db_admin_db='basketball'
# sports_db_admin_user=os.environ.get('sports_db_admin_user')
# sports_db_admin_pw=os.environ.get('sports_db_admin_pw')
# sports_db_admin_port=os.environ.get('sports_db_admin_port')


leagueid=os.environ.get('leagueid')
espn_s2=os.environ.get('espn_s2')
swid=os.environ.get('swid')




# espn connect
league=League(league_id=leagueid, 
                year=2024,
                espn_s2=espn_s2,
                swid=swid, 
                debug=False)


# # yahoo connect
# sc=OAuth2(None,None,from_file='oauth2.json')
# gm=yfa.Game(sc, 'nba')
# league_id=gm.league_ids(year=2024)
# lg=gm.to_league('428.l.18598')




# my database connect
connection=mysql.connect(host=sports_db_admin_host,
                        database=sports_db_admin_db,
                        user=sports_db_admin_user,
                        password=sports_db_admin_pw,
                        port=sports_db_admin_port)

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
                    FROM basketball.my_team_stats_yahoo MTS 
                    JOIN basketball.calendar C ON MTS.date=C.day;
                    """)
    myteam_df_yh=cursor.fetchall()
    myteam_df_yh=pd.DataFrame(myteam_df_yh, columns=cursor.column_names)

    cursor.execute("""SELECT * FROM basketball.live_yahoo_players""")
    live_yahoo_players_df=cursor.fetchall()
    live_yahoo_players_df=pd.DataFrame(live_yahoo_players_df, columns=cursor.column_names)


if connection.is_connected():
    cursor=connection.cursor()
    cursor.execute("""SELECT * FROM basketball.injured_player_news ORDER BY exp_return_date ASC;""")
    inj_df=cursor.fetchall()
    inj_df=pd.DataFrame(inj_df, columns=cursor.column_names)

    cursor.execute("""SELECT * FROM basketball.injured_player_news_yh ORDER BY exp_return_date ASC;""")
    inj_df_yf=cursor.fetchall()
    inj_df_yf=pd.DataFrame(inj_df_yf, columns=cursor.column_names)


if(connection.is_connected()):
    cursor.close()
    connection.close()
    print('MySQL connection is closed')
else:
    print('MySQL already closed')


pd.set_option('display.max_columns', None)
pd.set_option('display.max_rows', None)


# print(live_yahoo_players_df)

myteam_df['total_rebounds']=myteam_df['offensive_rebounds']+myteam_df['defensive_rebounds']
myteam_df['minutes_played']=myteam_df['seconds_played']/60

myteam_df_yh['total_rebounds']=myteam_df_yh['offensive_rebounds']+myteam_df_yh['defensive_rebounds']
myteam_df_yh['minutes_played']=myteam_df_yh['seconds_played']/60


my_safe_players=['Jayson Tatum', 'Kyrie Irving','Jaylen Brown'
]




myteam=league.teams[10]
current_players=clean_string(myteam.roster).split(',')
current_players=[remove_name_suffixes(x) for x in current_players]
current_players=[x.strip(' ') for x in current_players]


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


connection=mysql.connect(host=sports_db_admin_host,
                        database=sports_db_admin_db,
                        user=sports_db_admin_user,
                        password=sports_db_admin_pw,
                        port=sports_db_admin_port)

# myteam=league.teams[11]
# my_players=clean_string(myteam.roster).split(',')
# my_players=[x.strip() for x in my_players]



df_for_agg=pd.DataFrame()
df_yh_for_agg=pd.DataFrame()
if connection.is_connected():
    for p in current_players:
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
        df_for_agg=pd.concat([df_for_agg, myteam_df1])
    for p in current_players_yh:
        cursor=connection.cursor()
        p=remove_name_suffixes(p)
        p=p.strip()
        qry=f"""
            SELECT
                name,
                team,
                TSCHED.*
            FROM basketball.my_team_stats_yahoo MTS
            JOIN basketball.high_level_nba_team_schedules TSCHED ON MTS.team = TSCHED.away_team OR MTS.team = TSCHED.home_team
            JOIN basketball.calendar CAL ON DATE(SUBDATE(CAST(TSCHED.start_time AS DATETIME), INTERVAL 8 HOUR)) = CAL.day
            WHERE MTS.name LIKE CONCAT("%", "{p}","%")
                AND CURDATE() BETWEEN CAL.week_starting_monday AND CAL.week_ending_sunday
            GROUP BY MTS.name, TSCHED.start_time;"""
        cursor.execute(qry)
        my_team_df1_yh=cursor.fetchall()
        my_team_df1_yh=pd.DataFrame(my_team_df1_yh,columns=cursor.column_names)
        df_yh_for_agg=pd.concat([df_yh_for_agg,my_team_df1_yh])


aggregate=df_for_agg.groupby(['name']).start_time.nunique()
aggregate=aggregate.reset_index()
aggregate.columns=['name', 'games_this_week']
aggregate=aggregate.sort_values(['games_this_week', 'name'], ascending=False)

aggregate_yh=df_yh_for_agg.groupby(['name']).start_time.nunique()
aggregate_yh=aggregate_yh.reset_index()
aggregate_yh.columns=['name', 'games_this_week']
aggregate_yh=aggregate_yh.sort_values(['games_this_week', 'name'], ascending=False)

del df_for_agg, df_yh_for_agg

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



# at this point

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
    fig.update_layout(width=300,height=400)

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


# def player_schedule(leagueid='ESPN'):

#     if league_id=='ESPN':
#         # return dash_table.DataTable(id='my-table',
#         #                             data=aggregate.to_dict('records'),
#         #                             columns=[{"name":i,"id":i} for i in aggregate.columns],
#         #                             style_cell=dict(textAlign='left'),
#         #                             style_header=dict(backgroundColor="paleturquoise"))
#         return aggregate.to_dict('records')
#     elif league_id=='Yahoo':
#         # return dash_table.DataTable(id='my-table',
#         #                             data=aggregate_yh.to_dict('records'),
#         #                             columns=[{"name":i,"id":i} for i in aggregate_yh.columns],
#         #                             style_cell=dict(textAlign='left'),
#         #                             style_header=dict(backgroundColor="paleturquoise"))
#         return aggregate_yh.to_dict('records')



# def player_schedule_cols(leagueid='Yahoo'):
#     if leagueid=='ESPN':
#         return [{"name": i, "id": i} for i in aggregate.columns]
#     elif leagueid=='Yahoo':
#         return [{"name": i, "id": i} for i in aggregate_yh.columns]


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



app=dash.Dash()

server = app.server


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
                                )
                    ],
                    lg=3
                ),
                dbc.Col(
                    [dcc.Dropdown(id='id-league',
                                    options=[{'label':'ESPN','value':'ESPN'},
                                              {'label':'Yahoo','value':'Yahoo'}],
                                              value='ESPN'
                                )
                    ],
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
                        dash_table.DataTable(id='id-my-team',
                                            data=players_at_risk.to_dict('records'),
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
                        dash_table.DataTable(id='id-injured',
                                            data=inj_df.to_dict('records'),
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
                        dash_table.DataTable(id='my-table',
                                                data=aggregate_yh.to_dict('records'),
                                                # data=player_schedule(),
                                                columns=[{"name": i, "id": i} for i in aggregate_yh.columns],
                                                # columns=player_schedule_cols(),
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
    Output(component_id='heat-map-weights', component_property='figure'),
    Output(component_id='box-plot', component_property='figure'),
    Output(component_id='box-plot-x-week-class', component_property='figure'),
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




# if __name__ == '__main__': 
#     app.run(port=8005)

if __name__ == '__main__': 
    app.run(port=8006)









