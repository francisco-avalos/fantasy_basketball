
# Standard
import pandas as pd
import datetime as dt

# db connections
import mysql.connector as mysql
from mysql.connector import pooling
from config import get_creds

# dash outlay
from dash import dcc, html, Input, Output, dash_table
from dash_create import app


# plot outlay
import plotly.express as px
import plotly.graph_objects as go
import matplotlib.pyplot as plt

# own functions/connections
from callbacks import injury_probabilities,line_plot_preds,create_data_table,heatmap
from callbacks import heatmap_weights,line_plot,bar_plot,boxplot_by_player,boxplot_by_player_weekday_class
from data_imports import add_new_fields, optimize_code_layouts


####################################################################################################
# 000 - FORMATTING INFO
####################################################################################################

####################### Corporate css formatting
corporate_colors={
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

externalgraph_rowstyling={
    'margin-left' : '1px',
    'margin-right' : '1px'
}

externalgraph_colstyling={
    'border-radius' : '10px',
    'border-style' : 'solid',
    'border-width' : '1px',
    # 'border-color' : corporate_colors['superdark-green'],
    # 'background-color' : corporate_colors['superdark-green'],
    # 'box-shadow' : '0px 0px 17px 0px rgba(186, 218, 212, .5)',
    'padding-top' : '5px'
}


navbarcurrentpage={
    'text-decoration' : 'underline',
    'text-decoration-color' : corporate_colors['white'],
    'text-shadow': '0px 0px 1px rgb(251, 251, 252)',
    'color':corporate_colors['white']
}



# recapdiv={
#     'border-radius' : '10px',
#     'border-style' : 'solid',
#     'border-width' : '1px',
#     'border-color' : 'rgb(251, 251, 252, 0.1)',
#     'margin-left' : '15px',
#     'margin-right' : '15px',
#     'margin-top' : '15px',
#     'margin-bottom' : '15px',
#     'padding-top' : '5px',
#     'padding-bottom' : '5px',
#     'background-color' : 'rgb(251, 251, 252, 0.1)'
# }

# recapdiv_text={
#     'text-align' : 'left',
#     'font-weight' : '350',
#     'color' : corporate_colors['white'],
#     'font-size' : '1.5rem',
#     'letter-spacing' : '0.04em'
# }


filterdiv_borderstyling={
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


dbconfig=get_creds()
connection_pool=pooling.MySQLConnectionPool(
    pool_name="sports_db_pool",
    pool_size=5,
    **dbconfig
)

def get_connection_from_pool():
    return connection_pool.get_connection()
def close_connection(connection):
    if connection.is_connected():
        connection.close()
connection=get_connection_from_pool()
try:
    dfs=optimize_code_layouts(connection)
finally:
    close_connection(connection)


fa_espn_df=dfs['fa_espn_df']
model_eval_pred_df=dfs['model_eval_pred_df']
next_5_players_df=dfs['next_5_players_df']

fa_df=fa_espn_df[fa_espn_df['current_season_vs_historicals']=='current_season_only'].copy()
fa_df=add_new_fields(fa_df)


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

short_df=output.iloc[:,0:len(output)]

######


def player_stats():
    fig=px.imshow(short_df, 
        text_auto='.2f')
    fig.update_xaxes(side='top')
    fig.update_layout(height=300, width=100)

    return fig


injury_probabilities_df=injury_probabilities()

model_eval_pred_df_copy=model_eval_pred_df[['day','predictions']].copy()
merged_table_1=pd.merge(model_eval_pred_df,next_5_players_df,on=['slug','day'],how='inner')
merged_table_1=merged_table_1[['day','opponent_location','predictions','league','slug','model_type']]


model_eval_pred_df_table2_copy=model_eval_pred_df[['league','slug','model_type','p','d','q','alpha','beta','evaluation_metric','evaluation_metric_value']].copy()



####################################################################################################
# 000 - DEFINE REUSABLE COMPONENTS AS FUNCTIONS
####################################################################################################

#####################
# Header with logo
def get_header():
    header=html.Div([
                html.Div([], className='col-2'), #Same as img width, allowing to have the title centrally aligned
                html.Div([
                    html.H1(children='Fantasy Basketball Analytics',
                        style={'textAlign' : 'center', 'color':corporate_colors['white']}
                    ),
                    html.H6(children='*Combined data from Basketball-Reference.com, Prosportstransactions.com, ESPN & Yahoo',
                        style={'textAlign':'center','color':corporate_colors['yellow']}
                    )
                    ],className='col-8',style={'padding-top' : '1%'}
                ),
                html.Div([
                    html.Img(src=app.get_asset_url('basketball_hoops.jpg'),
                        height='75 px',
                        width='auto')
                    ],className='col-2',style={'align-items': 'center','padding-top' : '1%','height' : 'auto'}
                )
                ],className='row',style={'height' : '4%','background-color' : corporate_colors['superdark-green']}
            )
    return header


#####################
# Nav bar
def get_navbar(p='page1'):
    navbar_page1=html.Div([
                    html.Div([], className='col-3'),
                    html.Div([
                        dcc.Link(
                            html.H4(children='Predictive Modeling',
                                    style=navbarcurrentpage),
                            href='/apps/fantasy-predictions'
                        )
                    ],className='col-2'),
                    html.Div([
                        dcc.Link(
                            html.H4(children='Free Agent Screening Tool', 
                                style={'color':corporate_colors['white']}),
                            href='/apps/free-agent-screening'
                        )
                    ],className='col-2'),
                    html.Div([
                        dcc.Link(
                            html.H4(children='Current Team Performance', 
                                style={'color':corporate_colors['white']}),
                            href='/apps/team-performance'
                        )
                    ],className='col-2'),
                    html.Div([], className='col-')
                ],className='row',
                style={'background-color' : corporate_colors['dark-green'],
                    'box-shadow': '2px 5px 5px 1px rgba(255, 101, 131, .5)'}
            )

    navbar_page2=html.Div([
                    html.Div([], className='col-3'),
                    html.Div([
                        dcc.Link(
                            html.H4(children='Predictive Modeling', 
                                style={'color':corporate_colors['white']}),
                            href='/apps/fantasy-predictions'
                        )
                    ],className='col-2'),
                    html.Div([
                        dcc.Link(
                            html.H4(children='Free Agent Screening Tool',
                                    style=navbarcurrentpage),
                            href='/apps/free-agent-screening'
                        )
                    ],className='col-2'),
                    html.Div([
                        dcc.Link(
                            html.H4(children='Current Team Performance', 
                                style={'color':corporate_colors['white']}),
                            href='/apps/team-performance'
                        )
                    ],className='col-2'),
                    html.Div([], className='col-3')
                ],className='row',
                style={'background-color' : corporate_colors['dark-green'],
                        'box-shadow': '2px 5px 5px 1px rgba(255, 101, 131, .5)'}
            )

    navbar_page3=html.Div([
                    html.Div([], className='col-3'),
                    html.Div([
                        dcc.Link(
                            html.H4(children='Predictive Modeling', 
                                style={'color':corporate_colors['white']}),
                            href='/apps/fantasy-predictions'
                        )
                    ],className='col-2'),
                    html.Div([
                        dcc.Link(
                            html.H4(children='Free Agent Screening Tool', 
                                style={'color':corporate_colors['white']}),
                            href='/apps/free-agent-screening'
                        )
                    ],className='col-2'),
                    html.Div([
                        dcc.Link(
                            html.H4(children='Current Team Performance',
                                    style=navbarcurrentpage), 
                            href='/apps/team-performance'
                        )
                    ],className='col-2'),
                    html.Div([], className='col-3')
                ],className='row',
                style={'background-color' : corporate_colors['dark-green'],
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
    emptyrow=html.Div([
        html.Div([
            html.Br()
        ], className='col-12')
    ],
    className='row',
    style={'height' : h})
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


id_league_dropdown_options=[
    {'label':'ESPN','value':'ESPN'},
    {'label':'Yahoo','value':'Yahoo'}
]
id_league_default_value='ESPN'


page1=html.Div([

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
                            style={'text-align' : 'left', 'color' : corporate_colors['medium-blue-grey']}
                        ),
                        #Date range picker
                        html.Div([#'Focus Field: ',
                            dcc.Dropdown(id='id-league',
                                    options=id_league_dropdown_options,
                                              value=id_league_default_value
                                ),
                        ], style={'margin-top' : '5px'}
                        )
                    ],
                    style={'margin-top' : '10px',
                            'margin-bottom' : '5px',
                            'text-align' : 'left',
                            'paddingLeft': 5})

                ],
                className='col-4'), # Filter part 1
                ########################################################################################
                # Filter pt 2
                html.Div([
                    html.Div([
                        html.H5(
                            children='Team Players:',
                            style={'text-align' : 'left', 'color' : corporate_colors['medium-blue-grey']}
                        ),
                        html.Div([
                            dcc.Dropdown(
                                id='League-Players'
                            ),
                            html.Div(id='output'),
                        ], style={'margin-top' : '5px'}
                        ),
                    ],
                    style={'margin-top' : '10px',
                            'margin-bottom' : '5px',
                            'text-align' : 'left',
                            'paddingLeft': 5})
                ],className='col-4'), #Filter pt 2

                ########################################################################################

                # Filter pt 3
                html.Div([
                    html.Div([
                        html.H5(
                            children='Model:',
                            style={'text-align' : 'left', 'color' : corporate_colors['medium-blue-grey']}
                        ),
                        html.Div([
                            dcc.Dropdown(
                                id='id-model'
                            ),
                            html.Div(id='model-output'),
                        ], style={'margin-top' : '5px'}
                        ),
                    ],
                    style={'margin-top' : '10px',
                            'margin-bottom' : '5px',
                            'text-align' : 'left',
                            'paddingLeft': 5})
                ],className='col-4'), #Filter pt 3

                ########################################################################################          

                html.Div([
                ],className='col-2') # Blank 2 columns
            ],className='row') # Internal row
        ],className='col-12',
        style=filterdiv_borderstyling) # External 12-column
    ],className='row sticky-top'), # External row

    #####################
    #Row 4
    get_emptyrow(),

    #####################
    #Row 5 : Charts
    html.Div([ # External row
        html.Div([],className='col-1'), # Blank 1 column
        html.Div([
            html.Div([ # Internal row 1
                html.Div([
                    dcc.Graph(id='preds-line',figure=line_plot_preds(),config=config)
                ])
            ]),
        ],className='row'),
        # Injured Players table and title
        html.Div([
            html.H5("Predictions Table",
                style={'color': corporate_colors['white']}),
            html.Div([ 
                    create_data_table(df=merged_table_1,table_id='id-preds-table',columns=merged_table_1.columns)
                ],className='col-6',style={'overflowX':'auto'}),
            html.Div([
                    create_data_table(df=model_eval_pred_df_table2_copy,table_id='id-model-mae',columns=model_eval_pred_df_table2_copy.columns)
                ],className='col-6',style={'overflowX':'auto'})
        ],className='row'),
    ],className='container')
])


####################################################################################################
# 002 - page2 (free agent screening tool)
####################################################################################################


league_id_dropdown_options_filter1=[
    {'label':'ESPN', 'value':'espn'},
    {'label':'Yahoo','value':'yahoo'}
]
league_id_default_value_filter1='yahoo'

history_dropdown_options_filter2=[
    {'label':'History only','value':'ho'},
    {'label':'History + current season ','value':'hcs'},
    {'label':'Current season only','value':'cso'}
]
history_dropdown_default_value_filter2='cso'

calculation_dropdown_options_filter4=[
    {'label':'Total', 'value':'sum'},
    {'label':'Average(non-weighted)', 'value':'mean'},
    {'label':'Weighted Average', 'value':'weights'},
    {'label':'Standard Deviation', 'value':'std'}
]
calculation_default_value_filter4='weights'

dropdown_options_filter5=[
    {'label':'Made Field Goals','value':'made_field_goals'},
    {'label':'Made 3pt Field Goals','value':'made_three_point_field_goals'},
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
    {'label':'Minutes Played','value':'minutes_played'}
]
dropdown_default_value_filter5='points_scored'

fields_to_display_filter6=['made_field_goals', 'made_three_point_field_goals',
                    'made_free_throws','total_rebounds', 'offensive_rebounds', 
                    'defensive_rebounds', 'assists','steals', 'blocks', 
                    'turnovers', 'personal_fouls', 'points_scored', 'minutes_played']

default_displayed_fields_filter6=['made_field_goals', 'made_three_point_field_goals',
                    'made_free_throws','total_rebounds', 'offensive_rebounds', 
                    'defensive_rebounds','assists','steals', 'blocks', 
                    'turnovers', 'points_scored']

players_to_display_filter7=fa_df['name'].unique().tolist()


page2=html.Div([

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
                ########################################################################################
                #Filter pt 1
                html.Div([
                    html.Div([
                        html.H5(
                            children='League:',
                            style={'text-align' : 'left', 'color' : corporate_colors['medium-blue-grey']}
                        ),
                        #Date range picker
                        html.Div([#'League: ',
                            dcc.Dropdown(id='league_id',
                                options=league_id_dropdown_options_filter1,
                                value=league_id_default_value_filter1)
                        ], style={'margin-top' : '5px'})
                    ],style={'margin-top' : '10px','margin-bottom' : '5px','text-align' : 'left','paddingLeft': 5})
                ],className='col-4'), # Filter part 1
                ########################################################################################
                #Filter pt 2
                html.Div([
                    html.Div([
                        html.H5(
                            children='Historical Options:',
                            style={'text-align' : 'left', 'color' : corporate_colors['medium-blue-grey']}
                        ),
                        #Date range picker
                        html.Div([#'Historical Options: ',
                            dcc.Dropdown(id='history_id',
                                options=history_dropdown_options_filter2,
                                value=history_dropdown_default_value_filter2)
                        ], style={'margin-top' : '5px'})
                    ],style={'margin-top' : '10px','margin-bottom' : '5px','text-align' : 'left','paddingLeft': 5})
                ],className='col-4'), # Filter part 2
                #######################################################################################
                #Filter pt 3
                html.Div([
                    html.Div([
                        html.H5(
                            children='How many days back?',
                            style={'text-align' : 'left', 'color' : corporate_colors['medium-blue-grey']}
                        ),
                        html.Div(['(Functional for current season only)',
                            dcc.Input(id='my_input',
                                        value=200,
                                        type='number',
                                        style={'font-size': '12px','display': 'inline-block', 'border-radius' : '2px', 'border' : '1px solid #ccc', 'color': '#333', 'border-spacing' : '0', 'border-collapse' :'separate'}
                                )
                        ], style={'margin-top' : '5px'})
                    ],style={'margin-top' : '10px','margin-bottom' : '5px','text-align' : 'left','paddingLeft': 5})
                ],className='col-4'), # Filter part 3
                #######################################################################################
                #Filter pt 4
                html.Div([
                    html.Div([
                        html.H5(
                            children='Calculation Type:',
                            style={'text-align' : 'left', 'color' : corporate_colors['medium-blue-grey']}
                        ),
                        #Date range picker
                        html.Div([#'Calculation Type: ',
                            dcc.Dropdown(id='calculation',
                                options=calculation_dropdown_options_filter4,
                                value=calculation_default_value_filter4)
                        ], style={'margin-top' : '5px'})
                    ],style={'margin-top' : '10px','margin-bottom' : '5px','text-align' : 'left','paddingLeft': 5})
                ],className='col-4'), # Filter part 4
                #######################################################################################
                #Filter pt 5
                html.Div([
                    html.Div([
                        html.H5(
                            children='Focus Field',
                            style={'text-align' : 'left', 'color' : corporate_colors['medium-blue-grey']}
                        ),
                        #Date range picker
                        html.Div(['(Picked field must be checked ON in \"Fields to Display\"): ',
                            dcc.Dropdown(id='dropdown',
                                options=dropdown_options_filter5,
                                value=dropdown_default_value_filter5)
                        ], style={'margin-top' : '5px'})
                    ],style={'margin-top' : '10px','margin-bottom' : '5px','text-align' : 'left','paddingLeft': 5})
                ],className='col-4'), # Filter part 5
                #######################################################################################
                #Filter pt 6
                html.Div([
                    html.Div([
                        html.H5(
                            children='Fields to Display:',
                            style={'text-align' : 'left', 
                            "overflow-y":"scroll", #"height": "50px",
                                'color' : corporate_colors['medium-blue-grey']
                                }
                        ),
                        #Date range picker
                        html.Div([#'Fields to Display: ',
                            dcc.Checklist(id='displayed_fields', 
                                options=[{'label':field,'value':field} for field in fields_to_display_filter6],
                                value=default_displayed_fields_filter6,
                                style={"overflow-y":"scroll", "height": "100px"})
                        ],style={'margin-top' : '5px'})
                    ],style={'margin-top' : '10px','margin-bottom' : '5px','text-align' : 'left','paddingLeft': 5})
                ],className='col-4'), # Filter part 6
                #######################################################################################
                #Filter pt 7
                html.Div([
                    html.Div([
                        html.H5(
                            children='Number of players:',
                            style={'text-align' : 'left', 'color' : corporate_colors['medium-blue-grey']}
                        ),
                        #Date range picker
                        html.Div([#'Number of Players: ',
                            dcc.Input(id='top_n', value=12, type='number')
                        ], style={'margin-top' : '5px'})
                    ],style={'margin-top' : '10px','margin-bottom' : '5px','text-align' : 'left','paddingLeft': 5})
                ],className='col-4'), # Filter part 7

                #######################################################################################
                #Filter pt 8
                html.Div([
                    html.Div([
                        html.H5(
                            children='Player Checklist:',
                            style={'text-align' : 'left', 
                            "overflow-y":"scroll", #"height": "50px",
                                'color' : corporate_colors['medium-blue-grey']
                                }
                        ),
                        #Date range picker
                        html.Div([#'Fields to Display: ',
                            dcc.Checklist(id='player_list', 
                                options=[{'label':field,'value':field} for field in players_to_display_filter7],
                                value=players_to_display_filter7,
                                style={"overflow-y":"scroll", "height": "100px"},inline=True)
                        ],style={'margin-top' : '5px'})
                    ],style={'margin-top' : '10px','margin-bottom' : '5px','text-align' : 'left','paddingLeft': 5})
                ],className='col-4'), # Filter part 7
                # #######################################################################################
            ],className='row') # Internal row
        ],className='col-12',style=filterdiv_borderstyling) # External 12-column
    ],className='row sticky-top'), # External row

    get_emptyrow(),

    html.Div([
        dcc.Graph(id='player_stats',figure=player_stats(),config=config)
    ],className='col-12')
],className='col-12')




####################################################################################################
# 003 - page3 (current team performance)
####################################################################################################

id_dropdown_options=[
    {'label':'Made Field Goals','value':'made_field_goals'},
    {'label':'Made 3pt Field Goals','value':'made_three_point_field_goals'},
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
    {'label':'Game Score','value':'game_score'}
]
id_dropdown_default_value='made_field_goals'

page3=html.Div([

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
                ########################################################################################
                #Filter pt 1
                html.Div([
                    html.Div([
                        html.H5(
                            children='League:',
                            style={'text-align' : 'left', 'color' : corporate_colors['medium-blue-grey']}
                        ),
                        #Date range picker
                        html.Div([#'Focus Field: ',
                            dcc.Dropdown(id='id-league',
                                    options=id_league_dropdown_options,
                                              value=id_league_default_value
                                )
                        ], style={'margin-top' : '5px'}
                        )
                    ],
                    style={'margin-top' : '10px',
                            'margin-bottom' : '5px',
                            'text-align' : 'left',
                            'paddingLeft': 5})
                ],className='col-4'), # Filter part 1
                ########################################################################################
                #Filter pt 2
                html.Div([
                    html.Div([
                        html.H5(
                            children='Focus Field:',
                            style={'text-align' : 'left', 'color' : corporate_colors['medium-blue-grey']}
                        ),
                        html.Div([ #'Enter # of days back: ',
                            dcc.Dropdown(id='id-dropdown',
                                         options=id_dropdown_options,
                                    value=id_dropdown_default_value
                                )
                        ], style={'margin-top' : '5px'}
                        )
                    ],
                    style={'margin-top' : '10px',
                            'margin-bottom' : '5px',
                            'text-align' : 'left',
                            'paddingLeft': 5})
                ],className='col-4'), # Filter part 2
                ########################################################################################                
                #Filter pt 3
                html.Div([
                    html.Div([
                        html.H5(
                            children='Injury Type:',
                            style={'text-align' : 'left', 'color' : corporate_colors['medium-blue-grey']}
                        ),
                        #Date range picker
                        html.Div([#'Focus Field: ',
                            dcc.Input(id='id-inj-prob',
                                        type='text',
                                        value='flu',
                                        placeholder='wildcard search',
                                )
                        ], style={'margin-top' : '5px'}
                        )
                    ],
                    style={'margin-top' : '10px',
                            'margin-bottom' : '5px',
                            'text-align' : 'left',
                            'paddingLeft': 5})
                ],className='col-4'), # Filter part 2
                ########################################################################################                
                html.Div([
                ],className='col-2') # Blank 2 columns
            ],className='row') # Internal row
        ],className='col-12',
        style=filterdiv_borderstyling) # External 12-column
    ],className='row sticky-top'), # External row

    #####################
    #Row 4
    get_emptyrow(),

    #####################
    #Row 5 : Charts
    html.Div([ # External row
        html.Div([
        ],
        className='col-1'), # Blank 1 column
        html.Div([ # External 10-column
            html.H2(children="Minutes-Played Weighted Production",
                style={'color' : corporate_colors['dark-green']}),
            html.Div([ # Internal row 1
                # min-weight focus field prod heatmap
                html.Div([
                    dcc.Graph(id='heat-map', figure=heatmap(), config=config),
                ],
                className='col-6'),
                # min-weights
                html.Div([
                    dcc.Graph(id='heat-map-weights', figure=heatmap_weights(), config=config)
                ],className='col-6'),
            ],className='row'), # Internal row 1

            html.Div([ # Internal row 2

                # Chart Column
                html.Div([
                    dcc.Graph(id='line_plot', figure=line_plot(), config=config)
                ],className='col-4'),
            ],className='row'), # Internal row 2

            html.Div([ # Internal row 3
                # Chart Column
                html.Div([
                    dcc.Graph(id='bar-plot', figure=bar_plot(), config=config)
                ],className='col-4'),
            ],className='row'), # Internal row 3

            html.Div([ # Internal row 4
                # Chart Column
                html.Div([
                    dcc.Graph(id='box-plot', figure=boxplot_by_player(), config=config)
                ],className='col-12'),
            ],className='row'), # Internal row 4

            html.Div([ # Internal row 5
                # Chart Column
                html.Div([
                    dcc.Graph(id='box-plot-x-week-class', figure=boxplot_by_player_weekday_class(), config=config)
                ],className='col-12'),
            ],className='row'), # Internal row 5

            ##### BELOW 3 TABLES DISCONTINUED
            # html.Div([ # Internal row 6

            #     # Players at risk table and title
            #     html.Div([
            #         html.H5("Players at risk of being \n picked up if dropped",
            #             style={'color': corporate_colors['white']}),
            #         dash_table.DataTable(
            #             id='id-my-team',
            #             data=players_at_risk.to_dict('records'),
            #             columns=[{"name": i, "id": i} for i in players_at_risk.columns],
            #             style_cell=dict(textAlign='left'),
            #             style_header=dict(backgroundColor="paleturquoise"),
            #             style_table={'overflowX':'auto','width':'100%'},
            #         )
            #     ],
            #     className='col-md-4 col-sm-12'),

            #     # Injured Players table and title
            #     html.Div([
            #         html.H5("Injured Players",
            #             style={'color': corporate_colors['white']}),
            #         dash_table.DataTable(
            #             id='id-injured',
            #             data=inj_df.to_dict('records'),
            #             columns=[{"name": i, "id": i} for i in inj_df.columns],
            #             style_cell=dict(textAlign='left'),
            #             style_header=dict(backgroundColor="paleturquoise"),
            #             style_table={'overflowX':'auto','width':'100%'},
            #         )
            #     ],
            #     className='col-md-4 col-sm-12'),

            #     # Expected games this week table and title
            #     html.Div([
            #         html.H5("Expected games this week",
            #             style={'color': corporate_colors['white']}),
            #         dash_table.DataTable(
            #             id='my-table',
            #             data=aggregate_yh.to_dict('records'),
            #             columns=[{"name": i, "id": i} for i in aggregate_yh.columns],
            #             style_cell=dict(textAlign='left'),
            #             style_header=dict(backgroundColor="paleturquoise"),
            #             style_table={'overflowX':'auto','width':'100%'},
            #         )
            #     ],
            #     className='col-md-4 col-sm-12'),

            # ],
            # className='row'),  # Internal row 6

            html.Div([ # Internal row 7
                html.H6("Probability of injury duration",
                    style={'color':corporate_colors['white']}),
                # Chart Column
                html.Div([
                    create_data_table(df=injury_probabilities_df,table_id='id-inj-prob-table',columns=injury_probabilities_df.columns)
                ],className='col-12'),
            ],className='row'), # Internal row 7
        ],className='col-10',
        style=externalgraph_colstyling), # External 10-column
        html.Div([],className='col-1'), # Blank 1 column
    ],className='row',
    style=externalgraph_rowstyling
    ), # External row

])
