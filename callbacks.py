
import os
import dash
from dash.dependencies import Input, Output

import mysql.connector as mysql
from mysql.connector import pooling

import pandas as pd
import datetime as dt
from dash_create import app
import plotly.express as px
import plotly.graph_objects as go

import logging
import random
from my_functions import clean_string, remove_name_suffixes,execute_query_and_fetch_df,execute_query_and_fetch_player_df,convert_fields_to_float

from dash import dash_table

from data_imports import optimize_code,add_new_fields


####################################################################################################
# 000 - IMPORT DATA FROM DB - FREE AGENT SCREEN TOOL
####################################################################################################

## NEEDED
# injury_probabilities_df = execute_query_and_fetch_df(inj_prob_qry, connection)

dfs = optimize_code()

fa_espn_df = dfs['fa_espn_df']
fa_yahoo_df = dfs['fa_yahoo_df']
myteam_df = dfs['myteam_df']
myteam_df_yh = dfs['myteam_df_yh']
live_yahoo_players_df = dfs['live_yahoo_players_df']
inj_df = dfs['inj_df']
inj_df_yf = dfs['inj_df_yf']

my_live_espn_df = dfs['my_live_espn_df']
my_live_yahoo_df = dfs['my_live_yahoo_df']

current_players = dfs['current_players']
players_at_risk_df = dfs['players_at_risk_df']
players_at_risk = dfs['players_at_risk']

current_players_yh_at_risk_df = dfs['current_players_yh_at_risk_df']
df_for_agg = dfs['df_for_agg']
df_yh_for_agg = dfs['df_yh_for_agg']

model_eval_pred_df = dfs['model_eval_pred_df']
next_5_players_df = dfs['next_5_players_df']

injury_probabilities_df = dfs['injury_probabilities_df']
historicals_df = dfs['historicals_df']



merged_table_1=pd.merge(model_eval_pred_df,next_5_players_df,on=['slug','day'],how='inner')
merged_table_1=merged_table_1[['day','opponent_location','predictions','league','slug','model_type']]



pd.set_option('display.max_columns', None)
pd.set_option('display.max_rows', None)


fa_espn_df=add_new_fields(fa_espn_df)
fa_yahoo_df=add_new_fields(fa_yahoo_df)

fa_df=fa_espn_df[fa_espn_df['current_season_vs_historicals']=='current_season_only'].copy()


model_eval_pred_df_table2_copy=model_eval_pred_df[['league','slug','model_type','p','d','q','alpha','beta','evaluation_metric','evaluation_metric_value']].copy()



def create_data_table(df,table_id,columns):
    return dash_table.DataTable(
            id=table_id,
            data=df.to_dict('records'),
            columns=[{'name':col,'id':col} for col in columns],
            style_cell=dict(textAlign='center'),
            style_header=dict(backgroundColor='paleturquoise'),
            style_table={'overflowX':'auto','width':'100%'}
        )



####################################################################################################
# 000 - FREE AGENT SCREEN TOOL
####################################################################################################


def players_shown_at_once(top_n_value:int)->int:
    default_number_of_players_shown=5
    if top_n_value is None:
        player_sample=default_number_of_players_shown
    else:
        player_sample=int(top_n_value)
    return player_sample

def filter_players_deselected(data_df:pd.DataFrame,player_list:list)->pd.DataFrame:
    if len(player_list)!=len(data_df['name'].unique()):
        output_df=data_df[data_df['name'].isin(player_list)]
    else:
        output_df=data_df
    return output_df


def apply_calculation(calculation_type:str,
                    df:pd.DataFrame,
                    imps:list,
                    display_field:str,
                    focus_field:str,
                    player_sample:int,
                    cols:list)->pd.DataFrame:
    if calculation_type=='weights':
        output_df=df.groupby(['name']).apply(lambda x: pd.Series([sum(x[v]*x.minutes_played)/sum(x.minutes_played) if sum(x.minutes_played) != 0 else 0 for v in imps]))
        output_df.columns=imps
        output_df=output_df[display_field]
        output_df=output_df.sort_values(by=[focus_field],ascending=False).head(player_sample)
    else:
        output_df=df.groupby(['name'])[cols].agg(calculation_type).reset_index().sort_values(by=[focus_field],ascending=False).head(player_sample)
        output_df.set_index(['name'],inplace=True,drop=True,append=False)
        output_df.reset_index(inplace=False)
    return output_df


def update_fig_with_calculation(df:pd.DataFrame,
                display_field:str,
                calculation_value:str)->go.Figure:
    if calculation_value=='sum':
        fig=px.imshow(df[display_field],text_auto=True)
    else:
        fig=px.imshow(df[display_field],text_auto='.2f')
    fig.update_xaxes(side='top')
    fig.layout.height=750
    fig.layout.width=750
    return fig


@app.callback(Output(component_id='player_stats', component_property='figure'),
             Input(component_id='my_input', component_property='value'),
             Input(component_id='dropdown', component_property='value'),
             Input(component_id='calculation', component_property='value'),
             Input(component_id='displayed_fields', component_property='value'),
             Input(component_id='top_n', component_property='value'),
             Input(component_id="history_id", component_property='value'),
             Input(component_id="league_id", component_property='value'),
             Input(component_id='player_list', component_property='value')
            )



def graph_update(input_value:str,
                focus_field_value:str,
                calc_value:str,
                display_field:str,
                top_n_val:int,
                history_id:str,
                league_id:str,
                player_list:list)->go.Figure:
    cols=['made_field_goals', 'made_three_point_field_goals','made_free_throws', 
    'total_rebounds', 'offensive_rebounds', 'defensive_rebounds', 'assists', 
    'steals', 'blocks', 'turnovers', 'personal_fouls', 'points_scored', 'minutes_played']

    days_ago=int(input_value)
    today=dt.date.today()
    days_back=today-dt.timedelta(days=days_ago)

    imps=['made_field_goals','made_three_point_field_goals','made_free_throws','offensive_rebounds',
     'defensive_rebounds','assists','steals','blocks','turnovers','personal_fouls','points_scored',
     'total_rebounds','minutes_played']
    player_sample=players_shown_at_once(top_n_value=top_n_val)
    if league_id=='espn':
        if history_id=='cso':
            fa_df1=filter_players_deselected(data_df=fa_df,player_list=player_list)
            df_query1=fa_df1.query("date >= @days_back")
            output=apply_calculation(calculation_type=calc_value,df=df_query1,imps=imps,
                                display_field=display_field,focus_field=focus_field_value,
                                player_sample=player_sample,cols=cols)
            fig=update_fig_with_calculation(df=output,display_field=display_field,calculation_value=calc_value)

            return fig
        elif history_id=='ho':
            fa_hist_only_df=fa_espn_df[fa_espn_df['current_season_vs_historicals']=='historicals_only']
            fa_hist_only_df1=filter_players_deselected(data_df=fa_hist_only_df,player_list=player_list)
            output=apply_calculation(calculation_type=calc_value,df=fa_hist_only_df1,imps=imps,
                                display_field=display_field,focus_field=focus_field_value,
                                player_sample=player_sample,cols=cols)
            fig=update_fig_with_calculation(df=output,display_field=display_field,calculation_value=calc_value)

            return fig
        elif history_id=='hcs':
            fa_hist_and_current_df=fa_espn_df[fa_espn_df['all_history']=='history_plus_current']
            fa_hist_and_current_df1=filter_players_deselected(data_df=fa_hist_and_current_df,player_list=player_list)
            output=apply_calculation(calculation_type=calc_value,df=fa_hist_and_current_df1,imps=imps,
                                display_field=display_field,focus_field=focus_field_value,
                                player_sample=player_sample,cols=cols)
            fig=update_fig_with_calculation(df=output,display_field=display_field,calculation_value=calc_value)

            return fig
    elif league_id=='yahoo':
        if history_id=='cso':
            fa_yahoo_df1 = fa_yahoo_df[fa_yahoo_df['all_history']=='history_plus_current']
            fa_yahoo_current_only_df1=filter_players_deselected(data_df=fa_yahoo_df1,player_list=player_list)
            fa_yahoo_current_only_df1=fa_yahoo_current_only_df1.query("date >= @days_back")

            output=apply_calculation(calculation_type=calc_value,df=fa_yahoo_current_only_df1,imps=imps,
                                display_field=display_field,focus_field=focus_field_value,
                                player_sample=player_sample,cols=cols)
            fig=update_fig_with_calculation(df=output,display_field=display_field,calculation_value=calc_value)

            return fig
        elif history_id=='ho':
            fa_yahoo_hist_only_df = fa_yahoo_df[fa_yahoo_df['current_season_vs_historicals']=='historicals_only']
            fa_yahoo_hist_only_df1=filter_players_deselected(data_df=fa_yahoo_hist_only_df,player_list=player_list)
            output=apply_calculation(calculation_type=calc_value,df=fa_yahoo_hist_only_df1,imps=imps,
                                display_field=display_field,focus_field=focus_field_value,
                                player_sample=player_sample,cols=cols)
            fig=update_fig_with_calculation(df=output,display_field=display_field,calculation_value=calc_value)

            return fig
        elif history_id=='hcs':
            fa_yahoo_hist_and_current_df = fa_yahoo_df[fa_yahoo_df['current_season_vs_historicals']=='current_season_only']
            fa_yahoo_hist_and_current_df1=filter_players_deselected(data_df=fa_yahoo_hist_and_current_df,player_list=player_list)
            output=apply_calculation(calculation_type=calc_value,df=fa_yahoo_hist_and_current_df1,imps=imps,
                                display_field=display_field,focus_field=focus_field_value,
                                player_sample=player_sample,cols=cols)
            fig=update_fig_with_calculation(df=output,display_field=display_field,calculation_value=calc_value)

            return fig



####################################################################################################
# 001 - IMPORT DATA FROM DB - CURRENT TEAM PERFORMANCE
####################################################################################################



my_safe_players=['Jayson Tatum', 'Kyrie Irving','Jaylen Brown']



current_players=my_live_espn_df['name'].values.tolist()


players_at_risk=list(set(current_players)-set(my_safe_players))
players_at_risk=pd.DataFrame(players_at_risk)
players_at_risk.columns=['Name']



current_players_yh=live_yahoo_players_df.name.tolist()

current_players_yh=clean_string(current_players_yh).split(',')
current_players_yh=[remove_name_suffixes(x) for x in current_players_yh]
current_players_yh=[x.replace("'","") for x in current_players_yh]
current_players_yh=[x.replace("'","").strip() for x in current_players_yh]

current_players_yh_at_risk_df=pd.DataFrame(current_players_yh)
current_players_yh_at_risk_df.columns=['Name']



aggregate=df_for_agg.groupby(['name']).start_time.nunique()
aggregate=aggregate.reset_index()
aggregate.columns=['name', 'games_this_week']
aggregate=aggregate.sort_values(['games_this_week', 'name'], ascending=False)

aggregate_yh=df_yh_for_agg.groupby(['name']).start_time.nunique()
aggregate_yh=aggregate_yh.reset_index()
aggregate_yh.columns=['name', 'games_this_week']
aggregate_yh=aggregate_yh.sort_values(['games_this_week', 'name'], ascending=False)

del df_for_agg, df_yh_for_agg



convert_to_float_fields=['seconds_played','made_field_goals',
                        'attempted_field_goals','made_three_point_field_goals',
                        'attempted_three_point_field_goals','made_free_throws',
                        'attempted_free_throws','offensive_rebounds',
                        'defensive_rebounds','assists','steals','blocks',
                        'turnovers','personal_fouls','points','total_rebounds','game_score']
myteam_df=convert_fields_to_float(df=myteam_df,fields=convert_to_float_fields)
myteam_df_yh=convert_fields_to_float(df=myteam_df_yh,fields=convert_to_float_fields)


xaxis=pd.date_range(min(myteam_df['week_ending_sunday'].unique()),max(myteam_df['week_ending_sunday'].unique()), freq='W')


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


def line_plot_preds(leagueid='espn',player_slug='brownja02',model_type=None):
    if leagueid=='Yahoo':
        leagueid='yahoo'
    elif leagueid=='ESPN':
        leagueid='espn'
    df=historicals_df[(historicals_df['slug']==player_slug) & (historicals_df['league']==leagueid)].copy()

    df.reset_index(drop=True,inplace=True)
    df.reset_index(drop=False,inplace=True) # new

    points_mean=df[~df['points'].isna()]['points'].mean()
    nan_rows=df.index[df.points.isna()][1:]
    df.loc[nan_rows,'points']=points_mean

    points_mean = df.loc[~df['points'].isna(), 'points'].mean()
    df.loc[df['points'].isna(), 'points'] = points_mean

    if df.empty:
        logging.warning(f"DataFrame is empty. No data to plot. {historicals_df.shape}")
        return None

    # sorted_idx=df.sort_values(by='start_time_pst',ascending=False).index
    # sorted_values=df.sort_values(by='start_time_pst',ascending=True)['points'].values

    dups=model_eval_pred_df[model_eval_pred_df.duplicated()]

    model_eval_pred_df_copy=model_eval_pred_df.copy()
    if not dups.empty:
        model_eval_pred_df_copy.drop_duplicates(inplace=True)

    df_pred=model_eval_pred_df_copy[
                            (model_eval_pred_df_copy['slug']==player_slug) & 
                            (model_eval_pred_df_copy['league']==leagueid)
                        ].copy()
    df_pred.reset_index(drop=True,inplace=True)

    line_plot=px.line(df,
        x='index',
        y='points'
    )
    line_plot.update_traces(mode='lines+markers',line_color='blue',name='Historical Points')
    line_plot.update_layout(xaxis_title='Time', yaxis_title='Points', showlegend=True)


    if model_type==None:
        model_trace=px.line(
                        x=df_pred[df_pred.champion_model==1]['day']+len(df),
                        y=df_pred[df_pred.champion_model==1]['predictions'].values
                    )
        model_trace.update_traces(mode='lines+markers',line_color='red',name='Model Predictions')
    elif model_type is not None:
        model_trace=px.line(
                        x=df_pred[df_pred['model_type']==model_type]['day']+len(df),
                        y=df_pred[df_pred['model_type']==model_type]['predictions'].values
                    )
        model_trace.update_traces(mode='lines+markers',line_color='red',name='Model Predictions')

    line_plot.add_trace(model_trace.data[0])

    line_plot.update_layout(
                            title='Historical and Predictions - Points',
                            xaxis_title='Time',
                            yaxis_title='Points'
        )
    line_plot.update_traces(showlegend=True)
    return line_plot


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
imps_temp=[metric]
output=myteam_df.groupby(['name']).apply(lambda x: pd.Series([sum(x[v]*x.minutes_played)/sum(x.minutes_played) for v in imps_temp]))
output.columns=imps_temp

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
                    # labels=dict(x=f'{metric}', y='name')
    )
    fig.update_xaxes(side='top')
    fig.update_yaxes(title=None)
    fig.update_layout(width=300,height=550)

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
    fig.update_layout(width=300,height=550)

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


####################################################################################################
# 001 - CURRENT TEAM PERFORMANCE
####################################################################################################

def injury_probabilities(searched_injury='flu'):
    injury_probabilities_df_temp=injury_probabilities_df[injury_probabilities_df['injury'].str.contains(searched_injury,case=False)]
    return injury_probabilities_df_temp


@app.callback(
    Output(component_id='line_plot', component_property='figure'),
    Output(component_id='bar-plot', component_property='figure'),
    Output(component_id='heat-map', component_property='figure'),
    Output(component_id='heat-map-weights', component_property='figure'),
    Output(component_id='box-plot', component_property='figure'),
    Output(component_id='box-plot-x-week-class', component_property='figure'),
    # Output(component_id='id-injury-probabilities-table', component_property='string'),
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


@app.callback(
    Output('id-inj-prob-table','data'),
    # Output('id-inj-prob-table','columns'),
    Input('id-inj-prob', 'value')
)

def update_probabilities_seach_table(searched_injury):
    searched_injury=str(searched_injury)
    specified_injury_search=injury_probabilities_df[injury_probabilities_df['injury'].str.contains(searched_injury,case=False)]

    # columns=[{"name":i,"id":i} if i != 'probabilities' else {"name":i,"id":i,"type":"numeric","format": {"specifier":'.2%'}} for i in specified_injury_search.columns],
    return specified_injury_search.to_dict('records')#, columns



@app.callback(
    Output(component_id='preds-line',component_property='figure'),
    Input(component_id='id-league',component_property='value'),
    Input(component_id='League-Players',component_property='value'),
    Input(component_id='id-model',component_property='value')
)

def update_pred_plot(leagueid,player_slug,model_type):
    fig_line_pred=line_plot_preds(leagueid,player_slug,model_type)
    return fig_line_pred


@app.callback(
    Output(component_id='id-preds-table',component_property='data'),
    Output(component_id='id-preds-table',component_property='columns'),
    Input(component_id='id-league',component_property='value'),
    Input(component_id='League-Players',component_property='value'),
    Input(component_id='id-model',component_property='value')
)

def update_preds_table(leagueid,player_slug,model_type):
    if leagueid=='Yahoo':
        leagueid='yahoo'
    elif leagueid=='ESPN':
        leagueid='espn'


    # dups=model_eval_pred_df[model_eval_pred_df.duplicated()]
    dups=merged_table_1[merged_table_1.duplicated()]

    # model_eval_pred_df_copy=model_eval_pred_df.copy()
    model_eval_pred_df_copy=merged_table_1.copy()
    if not dups.empty:
        model_eval_pred_df_copy.drop_duplicates(inplace=True)

    df_pred=model_eval_pred_df_copy[
                            (model_eval_pred_df_copy['slug']==player_slug) & 
                            (model_eval_pred_df_copy['league']==leagueid)
                        ].copy()
    df_pred.reset_index(drop=True,inplace=True)

    df_pred=df_pred[df_pred['model_type']==model_type]
    df_pred['predictions']=df_pred['predictions'].astype(float).round(1)

    df_pred=df_pred[['day','opponent_location','predictions']]

    data=df_pred.to_dict('records')
    columns=[{"name":i,"id":i} for i in df_pred.columns]

    return data, columns






### NEW

@app.callback(
    [Output('League-Players', 'options'),
     Output('League-Players', 'value')],
    [Input('id-league', 'value')]
)
def update_player_list(selected_value):
    if selected_value == 'ESPN':
        options = [{'label': row['name'], 'value': row['slug']} for idx, row in my_live_espn_df.iterrows()]
        default_val = my_live_espn_df.iloc[0, 1] if not my_live_espn_df.empty else None
    elif selected_value == 'Yahoo':
        options = [{'label': row['name'], 'value': row['slug']} for idx, row in my_live_yahoo_df.iterrows()]
        default_val = my_live_yahoo_df.iloc[0, 1] if not my_live_yahoo_df.empty else None
    else:
        options = []
        default_val = None
    return options, default_val

@app.callback(
    Output('output', 'children'),
    [Input('League-Players', 'value')]
)
def update_player_picked_comment(selected_value):
    if selected_value is not None:
        return f'You have selected {selected_value}'
    else:
        return 'Please select a value'

@app.callback(
    [Output('id-model', 'options'),
     Output('id-model', 'value')],
    [Input('League-Players', 'value'),
     Input('id-league', 'value')]
)
def update_model_list(selected_player, selected_league):
    if selected_player is not None and selected_league is not None:
        if selected_league == 'ESPN':
            df = model_eval_pred_df[model_eval_pred_df['league'] == 'espn'].copy()
        elif selected_league == 'Yahoo':
            df = model_eval_pred_df[model_eval_pred_df['league'] == 'yahoo'].copy()
        else:
            df = pd.DataFrame()  # Empty dataframe if selected_league is neither ESPN nor Yahoo

        if not df.empty:
            player_df = df[df['slug'] == selected_player].copy()
            player_models = player_df['model_type'].unique().tolist()
            model_default = player_models[0] if player_models else None
            return [{'label': model, 'value': model} for model in player_models], model_default

    # Return empty options and default value if no valid data found or when any of the inputs are None
    return [], None
### NEW


@app.callback(
    Output('model-output', 'children'),
    Input('id-model', 'value')
)
def update_model_picked_comment(selected_value):
    if selected_value is not None:
        if selected_value == 'ARIMA':
            return 'Autoregressive Integrated Moving Average'
        elif selected_value == 'ARMA':
            return 'Autoregressive Moving Average'
        elif selected_value == 'DBL_EXP':
            return 'Double Exponential Smoothing'
        elif selected_value == 'SGL_EXP':
            return 'Single Exponential Smoothing'
        elif selected_value == 'LINEAR':
            return 'Simple Linear'
        elif selected_value == 'LSTM':
            return 'Long Short-Term Memory'
        elif selected_value == 'NEURAL_NETWORK':
            return 'Neural Network'
        elif selected_value == 'REPEAT':
            return 'Repeat'
        elif selected_value == 'LAST':
            return 'Last'
        # return f'You have selected {selected_value}'
    else:
        return 'Please select a value'



@app.callback(
    Output(component_id='id-model-mae',component_property='data'),
    Output(component_id='id-model-mae',component_property='columns'),
    Input(component_id='id-league',component_property='value'),
    Input(component_id='League-Players',component_property='value')
)

def update_player_models_table(leagueid,player_slug):
    if leagueid=='Yahoo':
        leagueid='yahoo'
    elif leagueid=='ESPN':
        leagueid='espn'
    df=model_eval_pred_df_table2_copy.copy()
    df=df[(df['league']==leagueid) &
            (df['slug']==player_slug)
    ]
    cols_to_drop=['league','slug']
    df.drop(columns=cols_to_drop,inplace=True)
    df['evaluation_metric_value']=df['evaluation_metric_value'].astype(float).round(2)
    df=df.groupby('model_type').first().reset_index()
    df=df.sort_values(by='evaluation_metric_value',ascending=True)

    data=df.to_dict('records')
    columns=[{"name":i,"id":i} for i in df.columns]

    return data, columns





