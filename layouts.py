
import os
import mysql.connector as mysql
import pandas as pd
import datetime as dt
from dash import html
from dash import dcc
import plotly.express as px
from dash_create import app

from callbacks import line_plot, bar_plot, heatmap, heatmap_weights, boxplot_by_player, boxplot_by_player_weekday_class



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
    'light-grey' : 'rgb(208, 206, 206)'
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

# sports_db_admin_host=os.environ.get('basketball_host')
# sports_db_admin_db=os.environ.get('basketball_db')
# sports_db_admin_user=os.environ.get('basketball_user')
# sports_db_admin_pw=os.environ.get('basketball_pw')
# sports_db_admin_port=os.environ.get('basketball_port')


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
    fig.update_xaxes(side='top')
    fig.layout.height=750
    fig.layout.width=750
    return fig









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
            )],
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
def get_navbar(p = 'sales'):

    navbar_sales = html.Div([

        html.Div([], className = 'col-3'),

        html.Div([
            dcc.Link(
                html.H4(children = 'Free Agent Screen Tool',
                        style = navbarcurrentpage),
                href='/apps/free-agent-screening'
                )
        ],
        className='col-2'),

        html.Div([
            dcc.Link(
                html.H4(children = 'Current Team Performance', style={'color':corporate_colors['white']}),
                href='/apps/page2'
                )
        ],
        className='col-2'),

        html.Div([
            dcc.Link(
                html.H4(children = 'Predictive Modeling', style={'color':corporate_colors['white']}),
                href='/apps/page3'
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
                html.H4(children = 'Free Agent Screening Tool', style={'color':corporate_colors['white']}),
                href='/apps/free-agent-screening'
                )
        ],
        className='col-2'),

        html.Div([
            dcc.Link(
                html.H4(children = 'Current Team Performance',
                        style = navbarcurrentpage),
                href='/apps/page2'
                )
        ],
        className='col-2'),

        html.Div([
            dcc.Link(
                html.H4(children = 'Predictive Modeling', style={'color':corporate_colors['white']}),
                href='/apps/page3'
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
                html.H4(children = 'Free Agent Screening Tool', style={'color':corporate_colors['white']}),
                href='/apps/free-agent-screening'
                )
        ],
        className='col-2'),

        html.Div([
            dcc.Link(
                html.H4(children = 'Current Team Performance', style={'color':corporate_colors['white']}),
                href='/apps/page2'
                )
        ],
        className='col-2'),

        html.Div([
            dcc.Link(
                html.H4(children = 'Predictive Modeling',
                        style = navbarcurrentpage), 
                href='/apps/page3'
                )
        ],
        className='col-2'),

        html.Div([], className = 'col-3')

    ],
    className = 'row',
    style = {'background-color' : corporate_colors['dark-green'],
            'box-shadow': '2px 5px 5px 1px rgba(255, 101, 131, .5)'}
    )

    if p == 'sales':
        return navbar_sales
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




####################################################################################################
# 001 - SALES
####################################################################################################


# this is my original html code below
# sales = layout=html.Div(children=[html.H1(children='Free Agent Analysis Helper Tool',
#                                         style={'textAlign':'center'}),
#                               html.Div(children='Analysis tool to screen potential star players',
#                                         style={'textAlign':'center', 'color':'red'}), 
#                              dcc.Graph(figure=player_stats(), id='line_plot',config=config),
#                               'How many days back?\n',
#                               dcc.Input(id='my_input', value=7, type='integer'),
#                               'Focus Field\n',
#                              html.Div(dcc.Dropdown(id='dropdown',
#                                          options=[{'label':'Made Field Goals','value':'made_field_goals'},
#                                                   {'label':'Made 3p Field Goals','value':'made_three_point_field_goals'},
#                                                   {'label':'Made Free Throws','value':'made_free_throws'},
#                                                   {'label':'Total Rebounds','value':'total_rebounds'},
#                                                   {'label':'Offensive Rebounds','value':'offensive_rebounds'},
#                                                   {'label':'Defensive Rebounds','value':'defensive_rebounds'},
#                                                   {'label':'Assists','value':'assists'},
#                                                   {'label':'Steals','value':'steals'},
#                                                   {'label':'Blocks','value':'blocks'},
#                                                   {'label':'Turnovers','value':'turnovers'},
#                                                   {'label':'Personal Fouls','value':'personal_fouls'},
#                                                   {'label':'Points','value':'points_scored'},
#                                                   {'label':'Minutes Played','value':'minutes_played'}],
#                                          value='points_scored')),

#                               'Calculation type',
#                               dcc.Dropdown(id='calculation', 
#                                           options=[{'label':'Total', 'value':'sum'},
#                                                    {'label':'Average(non-weighted))', 'value':'mean'},
#                                                    {'label':'Weighted Average', 'value':'weights'},
#                                                    {'label':'Standard Deviation', 'value':'std'}],
#                                           value='weights'),
#                               'Fields to display',
#                              dcc.Checklist(id='displayed_fields', 
#                                            options=['made_field_goals', 'made_three_point_field_goals',
#                                                     'made_free_throws','total_rebounds', 'offensive_rebounds', 
#                                                     'defensive_rebounds', 'assists','steals', 'blocks', 
#                                                     'turnovers', 'personal_fouls', 'points_scored', 'minutes_played'],
#                                           value=['made_field_goals', 'made_three_point_field_goals',
#                                                     'made_free_throws','total_rebounds', 'offensive_rebounds', 
#                                                     'defensive_rebounds','assists','steals', 'blocks', 
#                                                     'turnovers', 'points_scored']),
#                               'Number of players',
#                              dcc.Input(id='top_n', value=5, type='integer'),
#                              'historicals options',
#                              dcc.Dropdown(id='history_id',
#                                             options=[{'label':'history-only','value':'ho'},
#                                                     {'label':'history + current season ','value':'hcs'},
#                                                     {'label':'current season only','value':'cso'}],
#                                             value='cso'),
#                              'League',
#                              dcc.Dropdown(id='league_id',
#                                             options=[{'label':'ESPN', 'value':'espn'},
#                                                     {'label':'Yahoo','value':'yahoo'}],
#                                             value='yahoo'),
#                              'player_checklist',
#                              dcc.Checklist(id='player_list', options=[name for name in fa_df['name'].unique()], value=[name for name in fa_df['name'].unique()], 
#                                 style={'height':10000,'width':100}, inline=True)
#                              ])


#im here
sales = html.Div([

    #####################
    #Row 1 : Header
    get_header(),

    #####################
    #Row 2 : Nav bar
    get_navbar('sales'),

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
                        html.Div([ #'Enter # of days back: ',
                            dcc.Input(id='my_input',
                                        value=7,
                                        type='integer',
                                        style = {'font-size': '12px','display': 'inline-block', 'border-radius' : '2px', 'border' : '1px solid #ccc', 'color': '#333', 'border-spacing' : '0', 'border-collapse' :'separate'}
                                )
                            # dcc.DatePickerRange(
                            #     id='date-picker-sales',
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
                        html.Div([#'Focus Field: ',
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
                                {'label':'Average(non-weighted))', 'value':'mean'},
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
                            dcc.Input(id='top_n', value=5, type='integer')
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
                                options=[{'label':'history-only','value':'ho'},
                                {'label':'history + current season ','value':'hcs'},
                                {'label':'current season only','value':'cso'}],
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

        # html.Div([
        # ],
        # className = 'col-1'), # Blank 1 column

        html.Div([ # External 10-column

            # html.H2(children = "Sales Performances",
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

                # Chart Column
                html.Div([
                    dcc.Graph(id='line_plot',
                                figure=player_stats(),
                                config=config),
                ],
                className = 'col-4'),

                # # Chart Column
                # html.Div([
                #     dcc.Graph(
                #         id='sales-count-month')
                # ],
                # className = 'col-4'),

                # # Chart Column
                # html.Div([
                #     dcc.Graph(
                #         id='sales-weekly-heatmap')
                # ],
                # className = 'col-4')

            ],
            className = 'row'), # Internal row

            # html.Div([ # Internal row

            #     # Chart Column
            #     html.Div([
            #         dcc.Graph(
            #             id='sales-count-country')
            #     ],
            #     className = 'col-4'),

            #     # Chart Column
            #     html.Div([
            #         dcc.Graph(
            #             id='sales-bubble-county')
            #     ],
            #     className = 'col-4'),

            #     # Chart Column
            #     html.Div([
            #         dcc.Graph(
            #             id='sales-count-city')
            #     ],
            #     className = 'col-4')

            # ],
            # className = 'row') # Internal row


        ],
        className = 'col-10',
        style = externalgraph_colstyling), # External 10-column

        # html.Div([
        # ],
        # className = 'col-1'), # Blank 1 column

    ],
    className = 'row',
    style = externalgraph_rowstyling
    ), # External row

])



####################################################################################################
# 002 - Current Team Performance
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

        html.Br()

    ],
    className = 'row sticky-top'), # External row

    #####################
    #Row 4
    get_emptyrow(),

    #####################
    #Row 5 : Charts
    html.Div([ # External row

        html.Br()

    ])

])



####################################################################################################
# 003 - Predictive Modeling
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

        html.Br()

    ],
    className = 'row sticky-top'), # External row

    #####################
    #Row 4
    get_emptyrow(),

    #####################
    #Row 5 : Charts
    html.Div([ # External row

        html.Br()

    ])

])



