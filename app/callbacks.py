
# Standard
import pandas as pd
import datetime as dt
import random

# db connections
import mysql.connector as mysql
from mysql.connector import pooling
from shared.config import get_creds

# dash outlay
from dash.dependencies import Input, Output
from dash import dash_table, Input, Output, State, html
from app.dash_create import app_inst
# import dash_table.FormatTemplate as FormatTemplate
# from dash.dash_table.Format import FormatTemplate
# from dash.dash_table import FormatTemplate

# plot outlay
import plotly.express as px
import plotly.graph_objects as go

# own functions/connections
from shared.my_functions import clean_string,remove_name_suffixes,convert_fields_to_float
from shared.data_imports import optimize_code,add_new_fields

# ai chat
from app.ai_chatbox import ask_ai, build_context



####################################################################################################
# 000 - IMPORT DATA FROM DB - FREE AGENT SCREEN TOOL
####################################################################################################


dbconfig = get_creds()

connection_pool = pooling.MySQLConnectionPool(
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
    dfs=optimize_code(connection)
finally:
    close_connection(connection)


fa_espn_df = dfs['fa_espn_df']
fa_yahoo_df = dfs['fa_yahoo_df']
myteam_df = dfs['myteam_df']
myteam_df_yh = dfs['myteam_df_yh']
my_live_espn_df = dfs['my_live_espn_df']
my_live_yahoo_df = dfs['my_live_yahoo_df']
current_players = dfs['current_players']
forecast_champion_df = dfs['forecast_champion_df']
injury_probabilities_df = dfs['injury_probabilities_df']





fa_espn_df=add_new_fields(fa_espn_df)
fa_yahoo_df=add_new_fields(fa_yahoo_df)

fa_df=fa_espn_df.copy()




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
        output_df=data_df.copy()
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
        
        # print(f'output_df.shape: {output_df.shape}')
        # print(f'len(imps): {len(imps)}')
        
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
    fig.update_layout(height=1200, width=1600)
    # fig.layout.height=750
    # fig.layout.width=750
    return fig


@app_inst.callback(Output(component_id='player_stats', component_property='figure'),
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
        fa_df_filtered=fa_df.copy()
        if history_id=='ho':
            fa_df_filtered=fa_df_filtered[fa_df_filtered['current_season_vs_historicals']=='historicals_only']
        elif history_id=='hcs':
            fa_df_filtered=fa_df_filtered[fa_df_filtered['all_history']=='history_plus_current']
        elif history_id=='cso':
            fa_df_filtered=fa_df_filtered[fa_df_filtered['current_season_vs_historicals']=='current_season_only']
            fa_df_filtered=fa_df_filtered.query("date >= @days_back")
    elif league_id=='yahoo':
        fa_df_filtered=fa_yahoo_df.copy()
        if history_id=='ho':
            fa_df_filtered=fa_df_filtered[fa_df_filtered['current_season_vs_historicals']=='historicals_only']
        elif history_id=='hcs':
            fa_df_filtered=fa_df_filtered[fa_df_filtered['all_history']=='history_plus_current']
        elif history_id=='cso':
            fa_df_filtered=fa_df_filtered[fa_df_filtered['current_season_vs_historicals']=='current_season_only']
            fa_df_filtered=fa_df_filtered.query("date >= @days_back")

    fa_df_filtered=filter_players_deselected(data_df=fa_df_filtered,player_list=player_list)
    output=apply_calculation(calculation_type=calc_value,
                            df=fa_df_filtered,
                            imps=imps,
                            display_field=display_field,
                            focus_field=focus_field_value,
                            player_sample=player_sample,
                            cols=cols)
    fig=update_fig_with_calculation(df=output,display_field=display_field,calculation_value=calc_value)

    return fig



####################################################################################################
# 001 - IMPORT DATA FROM DB - CURRENT TEAM PERFORMANCE
####################################################################################################






convert_to_float_fields=['seconds_played','made_field_goals',
                        'attempted_field_goals','made_three_point_field_goals',
                        'attempted_three_point_field_goals','made_free_throws',
                        'attempted_free_throws','offensive_rebounds',
                        'defensive_rebounds','assists','steals','blocks',
                        'turnovers','personal_fouls','points','total_rebounds','game_score']
myteam_df=convert_fields_to_float(df=myteam_df,fields=convert_to_float_fields)
myteam_df_yh=convert_fields_to_float(df=myteam_df_yh,fields=convert_to_float_fields)



# Current Team Performance (page 3) figures and callbacks live in app/team_performance.py.


# Fantasy Predictions (page 1) figures and callbacks live in app/predictions.py.


####################################################################################################
# 001 - AI chatbox wiring
####################################################################################################


def _make_bubble(role: str, text: str) -> html.Div:
    """Return a styled chat bubble for a given role."""
    is_user = role == "user"
    return html.Div(
        text,
        style={
            "background-color": "rgb(57, 81, 85)" if is_user else "#2a2a3a",
            "color":            "rgb(251, 251, 252)",
            "border-radius":    "12px 12px 0px 12px" if is_user else "12px 12px 12px 0px",
            "padding":          "10px 14px",
            "margin":           "6px 0px 6px 40px" if is_user else "6px 40px 6px 0px",
            "max-width":        "80%",
            "align-self":       "flex-end" if is_user else "flex-start",
            "word-wrap":        "break-word",
            "white-space":      "pre-wrap",
        },
    )


# ── Callback 1: Send message & call Claude ────────────────────────────────────

@app_inst.callback(
    Output("ai-chat-history",  "data"),
    Output("ai-input",         "value"),
    Output("ai-thinking",      "style"),
    Input("ai-send-btn",       "n_clicks"),
    State("ai-input",          "value"),
    State("ai-chat-history",   "data"),
    State("ai-days-back",      "value"),
    prevent_initial_call=True,
)
def ai_send(n_clicks, user_text, history, days_back):
    """
    On Send click:
      • Build live context from the DataFrames already loaded in callbacks.py
      • Call Claude via ai_chatbox.ask_ai()
      • Append user + assistant turns to history
      • Clear the input box
    """
    hiding   = {"display": "none"}
    showing  = {"color": "rgb(255,211,67)", "font-style": "italic",
                 "margin-bottom": "8px", "display": "block"}

    if not user_text or not user_text.strip():
        return history, "", hiding

    user_text = user_text.strip()
    history   = history or []

    # Build context from live DataFrames (globals in callbacks.py scope)
    # When pasted into callbacks.py these names resolve to the module-level vars.
    try:
        context = build_context(
            fa_espn_df            = fa_espn_df,
            fa_yahoo_df           = fa_yahoo_df,
            myteam_df             = myteam_df,
            my_live_espn_df       = my_live_espn_df,
            my_live_yahoo_df      = my_live_yahoo_df,
            forecast_champion_df  = forecast_champion_df,
            injury_probabilities_df = injury_probabilities_df,
            days_back             = int(days_back or 14),
        )
    except Exception as e:
        context = f"(Context unavailable: {e})"

    # Call Claude — pass prior turns so conversation is multi-turn aware
    try:
        reply = ask_ai(
            user_message  = user_text,
            context       = context,
            chat_history  = history,
        )
    except Exception as e:
        reply = f"⚠️ Error calling AI: {e}"

    # Append both turns to history
    updated_history = history + [
        {"role": "user",      "content": user_text},
        {"role": "assistant", "content": reply},
    ]

    return updated_history, "", hiding


# ── Callback 2: Re-render chat display ───────────────────────────────────────

@app_inst.callback(
    Output("ai-chat-display", "children"),
    Input("ai-chat-history",  "data"),
)
def ai_render(history):
    """Convert stored history list into styled bubble components."""
    if not history:
        return [
            html.P(
                "No messages yet. Ask me something! 🏀",
                style={"color": "rgb(186, 218, 212)", "font-style": "italic"},
            )
        ]
    bubbles = []
    for turn in history:
        role = turn.get("role", "user")
        text = turn.get("content", "")
        bubbles.append(_make_bubble(role, text))
    return bubbles


# ── Callback 3: Clear chat ────────────────────────────────────────────────────

@app_inst.callback(
    Output("ai-chat-history", "data",    allow_duplicate=True),
    Output("ai-chat-display", "children", allow_duplicate=True),
    Input("ai-clear-btn",     "n_clicks"),
    prevent_initial_call=True,
)
def ai_clear(n_clicks):
    """Wipe the chat when the user clicks 'Clear chat'."""
    empty_msg = html.P(
        "Chat cleared. Ask me something! 🏀",
        style={"color": "rgb(186, 218, 212)", "font-style": "italic"},
    )
    return [], [empty_msg]




