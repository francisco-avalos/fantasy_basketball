"""
Fantasy Predictions page (page1): next-5-games points forecasts, Draft A.

    filter bar     league · player · models (multi) · history window
    chart          last N games + the next 5 on the team's schedule, opponent on every future tick,
                   champion with its 80% range, any other selected models dashed
    next 5 games   date, opponent, rest / back-to-back, opponent defence rank, champion forecast + range
    scoreboard     backtest MAE, skill vs naive, MAE by horizon, live MAE of logged forecasts
    parameters     one card per selected model (fitted parameters, AICc, Ljung-Box, champion reason)

Data comes from pipeline/points_forecast.py (forecast_roster, model_runs, points_forecasts), loaded once
at import like the other pages. Nothing here fits a model.
"""
import datetime as dt
import json

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from dash import dcc, html, Input, Output
from dash.exceptions import PreventUpdate

from app.dash_create import app_inst
from app.callbacks import get_connection_from_pool, close_connection
from app.team_performance import style_fig, empty_fig, _card, _section, GRAPH_CONFIG, TXT, MUTED, FAINT, ACC, \
    RED, AMBER
from shared.data_imports import forecast_page_data
from shared import season_calendar

####################################################################################################
# 001 - DATA
####################################################################################################

_conn = get_connection_from_pool()
try:
    _d = forecast_page_data(_conn)
finally:
    close_connection(_conn)

NUM_RUN = ['mae', 'mae_h1', 'mae_h2', 'mae_h3', 'mae_h4', 'mae_h5', 'skill', 'aicc', 'ljung_box_p']
ROSTER = _d['roster_df']
RUNS = _d['runs_df'].copy()
for c in NUM_RUN:
    if c in RUNS:
        RUNS[c] = pd.to_numeric(RUNS[c], errors='coerce')
FC = _d['forecasts_df'].copy()
for c in ['prediction', 'lo80', 'hi80']:
    if c in FC:
        FC[c] = pd.to_numeric(FC[c], errors='coerce')
if not FC.empty:
    FC['game_date'] = pd.to_datetime(FC['game_date'])
LIVE = _d['live_df'].copy()
for c in ['live_mae', 'live_coverage']:
    if c in LIVE:
        LIVE[c] = pd.to_numeric(LIVE[c], errors='coerce')
HIST = _d['history_df'].copy()
if not HIST.empty:
    HIST['date'] = pd.to_datetime(HIST['date'])
    HIST['points'] = pd.to_numeric(HIST['points'], errors='coerce')
    HIST['minutes'] = pd.to_numeric(HIST['minutes'], errors='coerce')
READY = not (ROSTER.empty or RUNS.empty or FC.empty)
RUN_DATE = str(RUNS['run_date'].iloc[0]) if not RUNS.empty else None

ABBR = {'ATLANTA_HAWKS': 'ATL', 'BOSTON_CELTICS': 'BOS', 'BROOKLYN_NETS': 'BKN', 'CHARLOTTE_HORNETS': 'CHA',
        'CHICAGO_BULLS': 'CHI', 'CLEVELAND_CAVALIERS': 'CLE', 'DALLAS_MAVERICKS': 'DAL', 'DENVER_NUGGETS': 'DEN',
        'DETROIT_PISTONS': 'DET', 'GOLDEN_STATE_WARRIORS': 'GSW', 'HOUSTON_ROCKETS': 'HOU', 'INDIANA_PACERS': 'IND',
        'LOS_ANGELES_CLIPPERS': 'LAC', 'LOS_ANGELES_LAKERS': 'LAL', 'MEMPHIS_GRIZZLIES': 'MEM', 'MIAMI_HEAT': 'MIA',
        'MILWAUKEE_BUCKS': 'MIL', 'MINNESOTA_TIMBERWOLVES': 'MIN', 'NEW_ORLEANS_PELICANS': 'NOP',
        'NEW_YORK_KNICKS': 'NYK', 'OKLAHOMA_CITY_THUNDER': 'OKC', 'ORLANDO_MAGIC': 'ORL', 'PHILADELPHIA_76ERS': 'PHI',
        'PHOENIX_SUNS': 'PHX', 'PORTLAND_TRAIL_BLAZERS': 'POR', 'SACRAMENTO_KINGS': 'SAC', 'SAN_ANTONIO_SPURS': 'SAS',
        'TORONTO_RAPTORS': 'TOR', 'UTAH_JAZZ': 'UTA', 'WASHINGTON_WIZARDS': 'WAS'}
ACTUAL, AVG10 = '#5dade2', '#a0aec0'
MODEL_COLORS = ['#3498db', '#9b59b6', '#f39c12', '#e67e22', '#1abc9c', '#ec7063', '#f1c40f', '#85929e']
SPARK = '▁▂▃▄▅▆▇█'
WINDOW_OPTIONS = [{'label': 'Last 20 games', 'value': 20}, {'label': 'Last 30 games', 'value': 30},
                  {'label': 'Last 60 games', 'value': 60}, {'label': 'All loaded (~15 months)', 'value': 0}]
LEAGUE_OPTIONS = [{'label': 'ESPN', 'value': 'espn'}, {'label': 'Yahoo', 'value': 'yahoo'}]
HEALTHY = {'', 'ACTIVE', 'NORMAL', 'NONE'}


def ab(team):
    t = str(team or '').replace('Team.', '')
    return ABBR.get(t, t[:3])


def label_of(slug, model):
    r = RUNS[(RUNS['slug'] == slug) & (RUNS['model'] == model)]
    return r['label'].iloc[0] if len(r) else model


def champion_of(slug):
    r = RUNS[(RUNS['slug'] == slug) & (RUNS['champion'] == 1)]
    return r['model'].iloc[0] if len(r) else None


####################################################################################################
# 002 - FIGURE
####################################################################################################

def fig_forecast(slug, models, window):
    hist = HIST[HIST['slug'] == slug].sort_values('date')
    fc = FC[FC['slug'] == slug]
    champ = champion_of(slug)
    if hist.empty or fc.empty:
        return empty_fig('No games or forecasts for this player in the latest run.', 460)
    season = season_calendar.season_of(hist['date'].iloc[-1])
    season_avg = hist.loc[season_calendar.season_of(hist['date']) == season, 'points'].mean()
    hist = hist.assign(avg10=hist['points'].rolling(10, min_periods=3).mean())
    if window:
        hist = hist.tail(window)
    hist = hist.reset_index(drop=True)
    n = len(hist)
    future = fc[fc['model'] == champ].sort_values('horizon') if champ else fc.drop_duplicates('horizon')
    fx = (n - 1) + 2.3 * future['horizon'].values
    x_end = fx[-1] + 1.3
    last_x, last_y = n - 1, float(hist['points'].iloc[-1])

    fig = go.Figure()
    fig.add_vrect(x0=n - 0.5, x1=x_end, fillcolor='#1a2035', line_width=0, layer='below')
    fig.add_annotation(x=n - 0.3, y=1, yref='paper', text='next 5 games', showarrow=False, xanchor='left',
                       yanchor='top', font=dict(color=MUTED, size=11))
    new_season = hist.index[season_calendar.season_of(hist['date']) == season]
    if len(new_season) and new_season[0] > 0:
        b = new_season[0] - 0.5
        fig.add_vline(x=b, line=dict(color=FAINT, dash='dashdot', width=1))
        fig.add_annotation(x=b, y=1, yref='paper', text=f' {season - 1}-{str(season)[-2:]} season', showarrow=False,
                           xanchor='left', yanchor='top', font=dict(color=MUTED, size=11))
    fig.add_hline(y=season_avg, line=dict(color=FAINT, dash='dash', width=1))
    fig.add_annotation(x=-0.6, y=season_avg, text=f'season avg {season_avg:.1f}', showarrow=False, xanchor='left',
                       yanchor='bottom', font=dict(color=MUTED, size=10))

    # champion 80% range, joined to the last actual game
    if champ:
        band = fc[fc['model'] == champ].sort_values('horizon')
        xs = np.r_[last_x, fx]
        fig.add_trace(go.Scatter(x=xs, y=np.r_[last_y, band['hi80']], mode='lines', line=dict(width=0),
                                 hoverinfo='skip', showlegend=False))
        fig.add_trace(go.Scatter(x=xs, y=np.r_[last_y, band['lo80']], mode='lines', line=dict(width=0),
                                 fill='tonexty', fillcolor='rgba(0,188,140,0.16)', hoverinfo='skip',
                                 name='80% range (champion)'))

    opp = hist['opponent'].map(ab)
    where = np.where(hist['location'] == 'Location.HOME', 'vs', '@')
    fig.add_trace(go.Scatter(
        x=list(range(n)), y=hist['points'], mode='lines+markers', name='Actual points',
        line=dict(color=ACTUAL, width=1.6), marker=dict(size=6),
        customdata=np.c_[hist['date'].dt.strftime('%a %b %-d, %Y'), where, opp, hist['minutes'].round(1)],
        hovertemplate='%{customdata[0]}<br>%{customdata[1]} %{customdata[2]}<br>'
                      '<b>%{y} pts</b> in %{customdata[3]} min<extra></extra>'))
    fig.add_trace(go.Scatter(x=list(range(n)), y=hist['avg10'], mode='lines', name='10-game average',
                             line=dict(color=AVG10, width=1, dash='dot'), hoverinfo='skip'))

    others = [m for m in (models or []) if m != champ]
    for i, m in enumerate(([champ] if champ else []) + others):
        f = fc[fc['model'] == m].sort_values('horizon')
        if f.empty:
            continue
        is_c = m == champ
        color = ACC if is_c else MODEL_COLORS[i % len(MODEL_COLORS)]
        cd = np.c_[f['game_date'].dt.strftime('%a %b %-d'), np.where(f['home'] == 1, 'vs', '@'), f['opponent'].map(ab),
                   f['lo80'].round(0), f['hi80'].round(0)]
        fig.add_trace(go.Scatter(
            x=np.r_[last_x, fx], y=np.r_[last_y, f['prediction']], mode='lines+markers' + ('+text' if is_c else ''),
            name=label_of(slug, m) + ('  ★ champion' if is_c else ''),
            line=dict(color=color, width=3 if is_c else 1.5, dash='solid' if is_c else 'dash'),
            marker=dict(size=[0] + [9 if is_c else 5] * len(f)),
            text=[''] + [f'{v:.1f}' for v in f['prediction']] if is_c else None, textposition='top center',
            textfont=dict(color=ACC, size=12),
            customdata=np.r_[[[''] * 5], cd],
            hovertemplate=f'<b>{label_of(slug, m)}</b><br>%{{customdata[0]}} %{{customdata[1]}} %{{customdata[2]}}'
                          '<br>%{y:.1f} pts (80%: %{customdata[3]}–%{customdata[4]})<extra></extra>'))

    step = max(1, n // 8)
    tickvals = list(range(0, n, step)) + list(fx)
    ticktext = [d.strftime('%-m/%-d') for d in hist['date'].iloc[::step]] + [
        f"<b>{r.game_date:%a %-m/%-d}<br>{'vs' if r.home == 1 else '@'} {ab(r.opponent)}</b>"
        for r in future.itertuples()]
    style_fig(fig, 480, margin=dict(l=10, r=10, t=10, b=10))
    top = max(hist['points'].max(), fc['hi80'].max() if champ else 0) * 1.12
    fig.update_layout(showlegend=True, hovermode='closest',
                      legend=dict(orientation='h', y=1.12, x=0, font=dict(size=11), bgcolor='rgba(0,0,0,0)'))
    fig.update_xaxes(tickvals=tickvals, ticktext=ticktext, range=[-0.8, x_end], showgrid=False, zeroline=False,
                     tickangle=0, tickfont=dict(size=10))
    fig.update_yaxes(title_text='Points', range=[0, top], rangemode='tozero')
    return fig


####################################################################################################
# 003 - TABLES AND CARDS
####################################################################################################

def next5_table(slug):
    champ = champion_of(slug)
    f = FC[(FC['slug'] == slug) & (FC['model'] == champ)].sort_values('horizon')
    h = HIST[HIST['slug'] == slug]
    if f.empty:
        return html.Div('No forecast for this player in the latest run.', className='tp-empty')
    season = season_calendar.season_of(h['date'].iloc[-1]) if not h.empty else None
    avg = h.loc[season_calendar.season_of(h['date']) == season, 'points'].mean() if season else np.nan
    head = html.Tr([html.Th(c) for c in ['#', 'Date', 'Opponent', 'Rest', 'Opp D rank', 'Forecast', '80% range']])
    rows = []
    for r in f.itertuples():
        rest = 'B2B' if r.rest_days == 0 else f'{int(r.rest_days)}d' + ('+' if r.rest_days >= 4 else '')
        rank = int(r.opp_def_rank) if pd.notna(r.opp_def_rank) else None
        rank_cls = 'tp-hot' if rank and rank <= 10 else 'tp-cold' if rank and rank >= 21 else ''
        up = pd.notna(avg) and r.prediction >= avg
        rows.append(html.Tr([
            html.Td(int(r.horizon), className='pr-muted'),
            html.Td(f'{r.game_date:%a %-m/%-d}'),
            html.Td(f"{'vs' if r.home == 1 else '@'} {ab(r.opponent)}", className='tp-name'),
            html.Td(rest, className='pr-amber' if rest == 'B2B' else ''),
            html.Td(f'{rank} / 30' if rank else '–', className=rank_cls),
            html.Td([html.B(f'{r.prediction:.1f}'), html.Span(' ▲' if up else ' ▼',
                                                               className='pr-up' if up else 'pr-down')]),
            html.Td(f'{r.lo80:.0f}–{r.hi80:.0f}', className='pr-muted'),
        ]))
    note = html.Div(f'Opp D rank: 1 = allows the most points over its last 15 games (best matchup). '
                    f'▲/▼ vs season average ({avg:.1f}).', className='pr-foot')
    return html.Div([html.Table([html.Thead(head), html.Tbody(rows)], className='tp-table'), note])


def scoreboard(slug):
    r = RUNS[RUNS['slug'] == slug].sort_values('mae', na_position='last')
    if r.empty:
        return html.Div('No backtest for this player.', className='tp-empty')
    live = LIVE[LIVE['slug'] == slug].set_index('model') if not LIVE.empty else pd.DataFrame()
    hcols = [f'mae_h{h}' for h in range(1, 6)]
    lo, hi = np.nanmin(r[hcols].values), np.nanmax(r[hcols].values)

    def spark(row):
        v = row[hcols].values.astype(float)
        if np.isnan(v).all() or hi <= lo:
            return '–'
        return ''.join(SPARK[int(round((x - lo) / (hi - lo) * 7))] if np.isfinite(x) else ' ' for x in v)

    head = html.Tr([html.Th(c) for c in ['Model', 'Backtest MAE', 'Skill', 'MAE 1→5 ahead', 'Live MAE']])
    rows = []
    for _, x in r.iterrows():
        is_c = x['champion'] == 1
        base = x['family'] == 'baseline'
        name = ('★ ' if is_c else '') + x['label'] + (' · baseline' if base else '') + \
            (' · ML' if x['family'] == 'ml' else '')
        lv = live.loc[x['model']] if not live.empty and x['model'] in live.index else None
        live_txt = f"{lv['live_mae']:.2f} ({int(lv['n_scored'])})" if lv is not None else '–'
        skill = x['skill']
        rows.append(html.Tr([
            html.Td(name, className='tp-name' + (' pr-champ-name' if is_c else ' pr-muted' if base else '')),
            html.Td(f"{x['mae']:.2f}" if pd.notna(x['mae']) else '–'),
            html.Td('—' if x['model'] == 'NAIVE' or pd.isna(skill) else f'{skill:+.0%}',
                    className='pr-up' if pd.notna(skill) and skill > 0 else 'pr-down'),
            html.Td(spark(x), className='pr-spark'),
            html.Td(live_txt, className='pr-muted'),
        ], className='pr-champ-row' if is_c else ''))
    n_or = int(r['n_origins'].iloc[0])
    foot = html.Div(f'Backtest: {n_or} rolling origins, every model refit at each, scored in points 1–5 games '
                    f'ahead. Skill = 1 − MAE / naive MAE. Live MAE = logged forecasts scored after the game '
                    f'(count in brackets).', className='pr-foot')
    return html.Div([html.Table([html.Thead(head), html.Tbody(rows)], className='tp-table pr-board'), foot])


PARAM_NAMES = {'alpha': 'alpha (level)', 'beta': 'beta (trend)', 'phi': 'phi (damping)', 'level': 'level',
               'trend': 'trend', 'drift_b0': 'drift (pts/game)', 'theta': 'theta', 'order': '(p, d, q)',
               'intercept': 'constant', 'sigma2': 'sigma²', 'ar.L1': 'AR 1', 'ar.L2': 'AR 2', 'ma.L1': 'MA 1',
               'ma.L2': 'MA 2', 'min_proj': 'per projected minute', 'home': 'home', 'b2b': 'back-to-back',
               'opp_def': 'opponent defence', 'opp_pace': 'opponent pace', 'const': 'constant',
               'log_min': 'log(projected min)', 'alpha_dispersion': 'dispersion', 'sigma2.irregular': 'noise var',
               'sigma2.level': 'level var', 'signal_to_noise': 'signal / noise', 'proj_minutes': 'projected minutes',
               'pts_per_min': 'pts / min used', 'recent_ppm': 'recent pts / min', 'long_run_ppm': 'long-run pts / min',
               'group_ppm': 'position pts / min', 'kappa_minutes': 'prior weight (min)', 'games': 'games this season',
               'window': 'window (games)', 'positions': 'position models'}


def _fmt(v):
    if isinstance(v, float):
        return f'{v:.4f}' if abs(v) < 1 else f'{v:.2f}'
    if isinstance(v, list):
        return '(' + ', '.join(map(str, v)) + ')'
    return str(v)


def param_cards(slug, models):
    champ = champion_of(slug)
    show = ([champ] if champ else []) + [m for m in (models or []) if m != champ]
    cards = []
    for m in show:
        r = RUNS[(RUNS['slug'] == slug) & (RUNS['model'] == m)]
        if r.empty:
            continue
        r = r.iloc[0]
        try:
            prm = json.loads(r['params'] or '{}')
        except ValueError:
            prm = {}
        items = [(PARAM_NAMES.get(k, k.replace('_val_mae', ' model val MAE')), _fmt(v)) for k, v in prm.items()]
        if pd.notna(r['aicc']):
            items.append(('AICc', f"{r['aicc']:.1f}"))
        if pd.notna(r['ljung_box_p']):
            items.append(('Ljung-Box p (lag 10)', f"{r['ljung_box_p']:.2f}"))
        items += [('backtest MAE', f"{r['mae']:.2f}" if pd.notna(r['mae']) else '–'), ('games fitted', int(r['n_games']))]
        body = [html.Div([html.Span(k, className='pr-k'), html.Span(v, className='pr-v')], className='pr-kv')
                for k, v in items]
        if m == champ and r['champion_reason']:
            body.append(html.Div(r['champion_reason'], className='pr-reason'))
        cards.append(html.Div(_card(r['label'] + ('  ★' if m == champ else ''), html.Div(body), sub=r['family'],
                                    accent=m == champ), className='col-lg-3 col-md-6'))
    return html.Div(cards, className='row')


####################################################################################################
# 004 - LAYOUT
####################################################################################################

def filter_bar(style):
    def block(label, component, cls='col-md-3 col-6'):
        return html.Div([html.H5(label, style={'text-align': 'left', 'color': 'rgb(77, 79, 91)'}),
                         html.Div(component, style={'margin-top': '5px'})],
                        className=cls, style={'margin': '10px 0 5px', 'paddingLeft': 5})
    return html.Div([html.Div([html.Div([
        block('League:', dcc.Dropdown(id='pr-league', options=LEAGUE_OPTIONS, value='espn', clearable=False),
              'col-md-2 col-6'),
        block('Player:', dcc.Dropdown(id='pr-player', clearable=False), 'col-md-3 col-6'),
        block('Models:', dcc.Dropdown(id='pr-models', multi=True, placeholder='Champion only'), 'col-md-5 col-12'),
        block('History:', dcc.Dropdown(id='pr-window', options=WINDOW_OPTIONS, value=30, clearable=False),
              'col-md-2 col-6'),
    ], className='row', style={'padding': '0 24px'})], className='col-12', style=style)], className='row sticky-top')


def body():
    if not READY:
        return html.Div(html.Div(
            'No forecasts yet. Run sql_files/migrations/2026-11-11_points_forecasts.sql once, then '
            '`python -m pipeline.points_forecast`, then restart the dyno.', className='tp-empty'),
            className='tp-container')
    return html.Div([
        _card('Historical and predicted points', dcc.Graph(id='pr-chart', config=GRAPH_CONFIG,
                                                           figure=empty_fig('Loading…', 480)),
              sub='', accent=True, sub_id='pr-chart-sub'),
        html.Div([
            html.Div(_card('Next 5 games', html.Div(id='pr-next5'),
                           sub='Champion forecast; matchup context from the schedule'), className='col-lg-6'),
            html.Div(_card('Model scoreboard', html.Div(id='pr-board'),
                           sub='Rolling-origin backtest, lowest MAE first'), className='col-lg-6'),
        ], className='row'),
        _section('Fitted parameters', 'Final fit on all games for the champion and every model selected above'),
        html.Div(id='pr-params'),
        html.Div(f'Latest run {RUN_DATE} · pipeline/points_forecast.py · runs and XGBoost models tracked in MLflow',
                 className='pr-foot', style={'marginTop': '8px'}),
    ], className='tp-container')


####################################################################################################
# 005 - CALLBACKS
####################################################################################################

@app_inst.callback(Output('pr-player', 'options'), Output('pr-player', 'value'), Input('pr-league', 'value'))
def update_players(league):
    r = ROSTER[ROSTER['league'] == league].sort_values('name') if READY else ROSTER
    if r.empty:
        return [], None
    opts = [{'label': f"{x.name} · {x.positions or '?'}" +
                      ('' if str(x.injury_status or '').upper() in HEALTHY else f' · {x.injury_status}'),
             'value': x.slug} for x in r.itertuples()]
    return opts, opts[0]['value']


@app_inst.callback(Output('pr-models', 'options'), Output('pr-models', 'value'), Input('pr-player', 'value'))
def update_models(slug):
    if not slug or not READY:
        return [], []
    r = RUNS[RUNS['slug'] == slug].sort_values('mae', na_position='last')
    champ = champion_of(slug)
    opts = [{'label': x.label + (' ★' if x.model == champ else ''), 'value': x.model} for x in r.itertuples()]
    default = [m for m in r['model'] if m != champ][:2]
    return opts, ([champ] if champ else []) + default


@app_inst.callback(Output('pr-chart', 'figure'), Output('pr-chart-sub', 'children'), Output('pr-next5', 'children'),
                   Output('pr-board', 'children'), Output('pr-params', 'children'),
                   Input('pr-player', 'value'), Input('pr-models', 'value'), Input('pr-window', 'value'))
def update_page(slug, models, window):
    if not slug or not READY:
        raise PreventUpdate
    p = ROSTER[ROSTER['slug'] == slug].iloc[0]
    champ = champion_of(slug)
    status = str(p['injury_status'] or '').upper()
    hurt = '' if status in HEALTHY else f' · ⚠ {status.replace("_", " ").title()}'
    games = HIST[HIST['slug'] == slug]
    last = f" · last game {games['date'].max():%b %-d}" if not games.empty else ''
    sub = (f"{p['name']} · {ab(p['team'])} · {p['positions'] or ''}{hurt}{last} · champion: "
           f"{label_of(slug, champ) if champ else '–'}")
    return fig_forecast(slug, models, window), sub, next5_table(slug), scoreboard(slug), param_cards(slug, models)
