"""
team_performance.py
-------------------
The Current Team Performance page (page 3, /apps/team-performance): data prep,
figure builders, the tabbed layout and its callbacks.

    Team overview  - player x category value heatmap, position depth (ESPN),
                     minute-weighted production, share of team, weekly trend
    Player detail  - game-by-game spread, small multiples, hot / cold table
    Injuries       - my players currently out (each linked to its survival curve),
                     the curve itself, and key-day probabilities

Data: my game logs come from app.callbacks (already loaded at import there); the
league baseline, injury curves, roster injury status and this season's injury
moves are loaded once here via shared.data_imports.team_performance_data().
Like the rest of the app, nothing refreshes until the dyno restarts.

Group-bys use plain sums (no groupby().apply()) so the frames behave the same on
local pandas 1.3.5 and Heroku's pandas 2.2.3.
"""

import ast
import datetime as dt
import math
import re
import unicodedata

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from dash import dcc, html, Input, Output, ALL, ctx
from dash.exceptions import PreventUpdate

from app.dash_create import app_inst
from app.callbacks import myteam_df, myteam_df_yh, get_connection_from_pool, close_connection
from shared.data_imports import team_performance_data, season_start_str
from shared import season_calendar
from shared.injury_taxonomy import note_key, regex_classify, curve_group, describe_group


####################################################################################################
# 000 - CONSTANTS
####################################################################################################

# label -> (stat column, attempts column or None). The 12 fantasy categories, then extras.
CATS = [
    ('FG%', 'made_field_goals', 'attempted_field_goals'),
    ('FGM', 'made_field_goals', None),
    ('FT%', 'made_free_throws', 'attempted_free_throws'),
    ('FTM', 'made_free_throws', None),
    ('3P%', 'made_three_point_field_goals', 'attempted_three_point_field_goals'),
    ('3PM', 'made_three_point_field_goals', None),
    ('REB', 'total_rebounds', None),
    ('AST', 'assists', None),
    ('STL', 'steals', None),
    ('BLK', 'blocks', None),
    ('PTS', 'points', None),
    ('TO', 'turnovers', None),
]
CAT_LABELS = [c[0] for c in CATS]
CAT = {lab: (m, a) for lab, m, a in CATS + [('MIN', 'minutes_played', None)]}
CAT_NAMES = {
    'FG%': 'Field goal %', 'FGM': 'Field goals made', 'FT%': 'Free throw %', 'FTM': 'Free throws made',
    '3P%': '3-point %', '3PM': '3-pointers made', 'REB': 'Rebounds', 'AST': 'Assists', 'STL': 'Steals',
    'BLK': 'Blocks', 'PTS': 'Points', 'TO': 'Turnovers', 'MIN': 'Minutes',
}
CATEGORY_OPTIONS = [{'label': f'{CAT_NAMES[k]} ({k})', 'value': k} for k in CAT_LABELS + ['MIN']]
STAT_COLS = sorted({c for m, a in CAT.values() for c in (m, a) if c})

WINDOW_OPTIONS = [
    {'label': 'Season to date', 'value': 'season'},
    {'label': 'Last 30 days', 'value': '30'},
    {'label': 'Last 14 days', 'value': '14'},
    {'label': 'Last 7 days', 'value': '7'},
]
LEAGUE_OPTIONS = [{'label': 'ESPN', 'value': 'ESPN'}, {'label': 'Yahoo', 'value': 'Yahoo'}]

# hot / cold: (label, column, change that counts as hot/cold)
HOT_COLD = [('PTS', 'points', 3), ('REB', 'total_rebounds', 1.5), ('AST', 'assists', 1.2),
            ('3PM', 'made_three_point_field_goals', 0.7), ('STL', 'steals', 0.4),
            ('BLK', 'blocks', 0.4), ('MIN', 'minutes_played', 3)]

# league baseline = rotation players: at least this many games and minutes per game
BASELINE_MIN_GP, BASELINE_MIN_MPG = 3, 20

# colours (match assets/custom.css tokens)
TXT, MUTED, FAINT, GRID = '#e2e8f0', '#a0aec0', '#4a5568', '#2a3045'
ACC, RED, AMBER = '#00bc8c', '#e5533d', '#f5a623'
NEUTRAL_CELL = '#2d3446'
Z_SCALE = [[0, '#b8402f'], [0.5, NEUTRAL_CELL], [1, '#00a87e']]
SEQ_SCALE = [[0, '#25313a'], [1, ACC]]
PALETTE = ['#00bc8c', '#3498db', '#f39c12', '#e74c3c', '#9b59b6', '#1abc9c', '#e67e22', '#5dade2',
           '#f1c40f', '#ec7063', '#a569bd', '#48c9b0', '#dc7633', '#85929e', '#52be80', '#af7ac5']
GRAPH_CONFIG = {'displayModeBar': False}  # no 'responsive': it sizes to the (heightless) parent and the cards collapse

# fantasy-platform injury status (ESPN and Yahoo spellings) -> display label
HEALTHY = {'', 'ACTIVE', 'NORMAL', 'NONE'}
STATUS_LABELS = {
    'OUT': 'Out', 'DAY_TO_DAY': 'Day-to-day', 'INJURY_RESERVE': 'Injured reserve', 'SUSPENSION': 'Suspended',
    'O': 'Out', 'GTD': 'Game-time decision', 'DTD': 'Day-to-day', 'INJ': 'Injured', 'IL': 'Injured list',
    'IL+': 'Injured list', 'NA': 'Not active', 'SUSP': 'Suspended',
}


####################################################################################################
# 001 - DATA
####################################################################################################

_conn = get_connection_from_pool()
try:
    _extra = team_performance_data(_conn)
finally:
    close_connection(_conn)


def _prep_games(df):
    """Current-season game logs with float stats, real dates and minutes."""
    cols = ['date', 'name', 'week_ending_sunday'] + STAT_COLS
    if df is None or df.empty:
        return pd.DataFrame(columns=cols)
    out = df.copy()
    out['date'] = pd.to_datetime(out['date'])
    out['week_ending_sunday'] = pd.to_datetime(out['week_ending_sunday'])
    for c in STAT_COLS:
        if c != 'minutes_played':
            out[c] = out[c].astype(float)
    out['minutes_played'] = out['seconds_played'].astype(float) / 60
    out = out[out['date'] >= pd.Timestamp(season_start_str)]
    return out[cols].sort_values('date').reset_index(drop=True)


GAMES = {'ESPN': _prep_games(myteam_df), 'Yahoo': _prep_games(myteam_df_yh)}


def _roster(status_df, games):
    names = set(games['name']) if not games.empty else set()
    if status_df is not None and 'name' in status_df:
        names |= set(status_df['name'])
    return sorted(names)


STATUS = {'ESPN': _extra['espn_status_df'], 'Yahoo': _extra['yahoo_status_df']}
ROSTER = {lg: _roster(STATUS[lg], GAMES[lg]) for lg in GAMES}
COLORS = {lg: {n: PALETTE[i % len(PALETTE)] for i, n in enumerate(ROSTER[lg])} for lg in GAMES}

# Position depth: lineup slots in my ESPN league (lineupSlotCounts; bench and IR don't count).
POSITIONS = ['PG', 'SG', 'SF', 'PF', 'C', 'UTIL']
SLOTS = {'PG': 1, 'SG': 1, 'SF': 1, 'PF': 1, 'C': 1, 'UTIL': 5}


def _positions(status_df, pos_df):
    """My ESPN roster: name, injured flag, status label and the set of base positions (PG..C)
    each player can play. Every rostered player can play UTIL, even without a positions row.
    Injured = any fantasy status that isn't healthy, so day-to-day counts as injured."""
    if status_df is None or status_df.empty or 'name' not in status_df:
        return pd.DataFrame(columns=['name', 'status', 'injured', 'roles'])
    out = status_df[['name']].copy()
    raw = (status_df['injury_status'] if 'injury_status' in status_df else pd.Series('', index=status_df.index))
    raw = raw.fillna('').astype(str).str.upper()
    out['injured'] = ~raw.isin(HEALTHY)
    out['status'] = [STATUS_LABELS.get(s, s.replace('_', ' ').title()) if s not in HEALTHY else 'Healthy'
                     for s in raw]
    roles = {}
    if pos_df is not None and not pos_df.empty:
        for n, r in zip(pos_df['name'], pos_df['player_roles']):
            try:
                roles[n] = set(ast.literal_eval(r)) & set(POSITIONS)
            except (ValueError, SyntaxError):
                pass
    out['roles'] = out['name'].map(lambda n: roles.get(n))
    return out.sort_values(['injured', 'name']).reset_index(drop=True)


ESPN_POSITIONS = _positions(STATUS['ESPN'], _extra.get('espn_positions_df'))


def player_totals(df):
    """Per-player sums of every stat column plus games played."""
    g = df.groupby('name')
    tot = g[STAT_COLS].sum()
    tot['gp'] = g.size()
    return tot


def category_value(tot, lab):
    """Per-game value of a category (makes / attempts for percentages)."""
    m, a = CAT[lab]
    if a:
        return tot[m] / tot[a].replace(0, np.nan)
    return tot[m] / tot['gp']


# ---- league baseline for z-scores ----
_league = _extra['league_totals_df'].copy()
for _c in _league.columns:
    if _c != 'slug':
        _league[_c] = _league[_c].astype(float)
if not _league.empty:
    _league = _league[(_league['gp'] >= BASELINE_MIN_GP) &
                      (_league['minutes_played'] / _league['gp'] >= BASELINE_MIN_MPG)]
LEAGUE_PCT = {lab: (_league[m].sum() / _league[a].sum() if not _league.empty and _league[a].sum() else np.nan)
              for lab, (m, a) in CAT.items() if a}


def value_metric(tot):
    """Per-game metric each category is ranked on. Percentages use volume-weighted
    impact (makes above league average for the attempts taken), so 50% on 20 shots
    outranks 60% on 3."""
    out = {}
    for lab in CAT_LABELS:
        m, a = CAT[lab]
        out[lab] = (tot[m] - LEAGUE_PCT[lab] * tot[a]) / tot['gp'] if a else tot[m] / tot['gp']
    return pd.DataFrame(out)


if not _league.empty:
    _lg_metric = value_metric(_league.rename(columns={'slug': 'name'}).set_index('name'))
    LEAGUE_MEAN, LEAGUE_STD = _lg_metric.mean(), _lg_metric.std().replace(0, np.nan)
else:
    LEAGUE_MEAN = LEAGUE_STD = None


def zscores(tot):
    """Category z-scores vs the league baseline (TO inverted) plus their TOTAL."""
    if LEAGUE_MEAN is None or tot.empty:
        z = pd.DataFrame(0.0, index=tot.index, columns=CAT_LABELS)
    else:
        z = ((value_metric(tot) - LEAGUE_MEAN) / LEAGUE_STD).fillna(0.0)
    z['TO'] = -z['TO']
    z['TOTAL'] = z[CAT_LABELS].sum(axis=1)
    return z


def window_games(league, window):
    df = GAMES.get(league, GAMES['ESPN'])
    if window and window != 'season':
        start = pd.Timestamp(dt.date.today() - dt.timedelta(days=int(window)))
        df = df[df['date'] >= start]
    return df


def value_order(df):
    """Players sorted by total category value, so every chart lists them the same way."""
    return zscores(player_totals(df))['TOTAL'].sort_values(ascending=False).index.tolist()


def per_game(df, lab):
    """Per-game value series for a category (NaN where a percentage had no attempts)."""
    m, a = CAT[lab]
    return df[m] / df[a].replace(0, np.nan) if a else df[m]


def rolling(df, lab, n=3):
    m, a = CAT[lab]
    if a:
        return df[m].rolling(n, min_periods=1).sum() / df[a].rolling(n, min_periods=1).sum().replace(0, np.nan)
    return df[m].rolling(n, min_periods=1).mean()


def fmt(lab, v):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return '–'
    if lab.endswith('%'):
        return f'{v:.3f}'.lstrip('0') if v < 1 else f'{v:.3f}'
    return f'{v:.1f}'


def no_games_message(league, window):
    if league == 'Yahoo' and GAMES['Yahoo'].empty:
        return 'No Yahoo games this season yet. The Yahoo pipeline is paused until API access is approved.'
    label = next(o['label'] for o in WINDOW_OPTIONS if o['value'] == window).lower()
    return f'No {league} games in the {label} window.'


####################################################################################################
# 002 - FIGURE HELPERS
####################################################################################################

def style_fig(fig, height, margin=None):
    fig.update_layout(
        template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color=TXT, family='Inter, -apple-system, Segoe UI, sans-serif', size=12),
        height=height, margin=margin or dict(l=10, r=10, t=30, b=10),
        hoverlabel=dict(bgcolor='#1a2035', font_color=TXT), showlegend=False,
    )
    fig.update_xaxes(gridcolor=GRID, zerolinecolor=GRID)
    fig.update_yaxes(gridcolor=GRID, zerolinecolor=GRID)
    return fig


def empty_fig(message, height=260):
    fig = go.Figure()
    fig.add_annotation(text=message, showarrow=False, xref='paper', yref='paper', x=0.5, y=0.5,
                       font=dict(color=MUTED, size=14))
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return style_fig(fig, height)


####################################################################################################
# 003 - TEAM OVERVIEW FIGURES
####################################################################################################

def fig_value_heatmap(df, league, window):
    if df.empty:
        return empty_fig(no_games_message(league, window), 300)
    tot = player_totals(df)
    z = zscores(tot)
    rows = z['TOTAL'].sort_values(ascending=False).index.tolist()
    disp = pd.DataFrame({lab: category_value(tot, lab) for lab in CAT_LABELS})
    mpg = (tot['minutes_played'] / tot['gp']).loc[rows]

    fig = make_subplots(rows=1, cols=3, shared_yaxes=True, column_widths=[0.80, 0.07, 0.13],
                        horizontal_spacing=0.008)
    fig.add_trace(go.Heatmap(
        z=z.loc[rows, CAT_LABELS].values, x=CAT_LABELS, y=rows,
        text=[[fmt(lab, disp.loc[r, lab]) for lab in CAT_LABELS] for r in rows], texttemplate='%{text}',
        textfont=dict(color=TXT, size=12), customdata=z.loc[rows, CAT_LABELS].values,
        colorscale=Z_SCALE, zmin=-2, zmax=2, showscale=False, xgap=2, ygap=2,
        hovertemplate='%{y} · %{x}: %{text}<br>vs league: %{customdata:+.2f} SD<extra></extra>'), 1, 1)
    fig.add_trace(go.Heatmap(
        z=z.loc[rows, ['TOTAL']].values, x=['Value'], y=rows,
        text=[[f'{v:+.1f}'] for v in z.loc[rows, 'TOTAL']], texttemplate='<b>%{text}</b>',
        textfont=dict(color=TXT, size=12), colorscale=Z_SCALE, zmin=-8, zmax=8, showscale=False, ygap=2,
        hovertemplate='%{y}<br>Total value: %{text}<extra></extra>'), 1, 2)
    fig.add_trace(go.Bar(
        x=mpg.values, y=rows, orientation='h', marker_color=[COLORS[league].get(r, MUTED) for r in rows],
        text=[f'{v:.1f}' for v in mpg.values], textposition='outside', cliponaxis=False,
        textfont=dict(color=MUTED, size=11), hovertemplate='%{y}: %{x:.1f} MPG<extra></extra>'), 1, 3)

    fig.update_yaxes(autorange='reversed', showgrid=False, ticks='')
    fig.update_xaxes(side='top', showgrid=False, ticks='', tickfont=dict(size=12, color=TXT))
    fig.update_xaxes(row=1, col=3, showticklabels=False, range=[0, float(mpg.max()) * 1.3])
    fig.add_annotation(text='MPG', xref='x3 domain', yref='paper', x=0.5, y=1.0, yanchor='bottom',
                       showarrow=False, font=dict(color=TXT, size=12))
    return style_fig(fig, 36 * len(rows) + 70, dict(l=10, r=30, t=40, b=10))


def fig_position_depth(include_injured):
    """How many of my ESPN players can fill each lineup slot, one block per player.
    A player counts at every position they're eligible for; the tick marks the slots to fill."""
    roster = ESPN_POSITIONS if include_injured else ESPN_POSITIONS[~ESPN_POSITIONS['injured']]
    if roster.empty:
        return empty_fig('No ESPN roster loaded (run pipeline.my_team_stats).', 300)

    def eligible(roles, pos):
        return pos == 'UTIL' or (roles is not None and pos in roles)

    fig = go.Figure()
    for _, r in roster.iterrows():   # one trace per player, in the same order on every row
        ys = [pos for pos in POSITIONS if eligible(r['roles'], pos)]
        fig.add_trace(go.Bar(
            x=[1] * len(ys), y=ys, orientation='h', name=r['name'],
            marker=dict(color=COLORS['ESPN'].get(r['name'], MUTED), line=dict(color='#161b27', width=2),
                        opacity=0.5 if r['injured'] else 0.92,
                        pattern=dict(shape='/' if r['injured'] else '', fgcolor=TXT, fgopacity=1,
                                     size=7, solidity=0.35)),
            text=r['name'].split(' ')[-1], textposition='inside', insidetextanchor='middle',
            textfont=dict(color=TXT if r['injured'] else '#0f1117', size=11), constraintext='inside',
            hovertemplate=f"{r['name']} · {r['status']}<br>%{{y}}<extra></extra>"))
    counts = {pos: sum(eligible(ro, pos) for ro in roster['roles']) for pos in POSITIONS}
    for pos in POSITIONS:
        fig.add_annotation(x=counts[pos], y=pos, text=str(counts[pos]), xanchor='left', xshift=8,
                           showarrow=False, font=dict(color=MUTED, size=12))
        i = POSITIONS.index(pos)   # slot tick, on the category's numeric position
        fig.add_shape(type='line', x0=SLOTS[pos], x1=SLOTS[pos], y0=i - 0.42, y1=i + 0.42,
                      line=dict(color=TXT, width=2), layer='above')
    fig.update_layout(barmode='stack', bargap=0.28)
    fig.update_xaxes(visible=False, range=[0, len(ESPN_POSITIONS) + 1])
    fig.update_yaxes(categoryorder='array', categoryarray=POSITIONS, autorange='reversed', showgrid=False,
                     ticks='', ticksuffix='  ', tickfont=dict(size=13, color=TXT))
    return style_fig(fig, 46 * len(POSITIONS) + 30, dict(l=10, r=10, t=10, b=10))


def position_depth_sub(include_injured):
    r = ESPN_POSITIONS
    n_inj = int(r['injured'].sum())
    parts = ['Each block is one player, in their colour on this page',
             '│ = lineup slots to fill (1 each, UTIL 5)']
    if n_inj:
        names = ', '.join(r.loc[r['injured'], 'name'])
        parts.append(f'hatched = injured ({names})' if include_injured else f'{n_inj} injured excluded ({names})')
    missing = r.loc[r['roles'].isna(), 'name'].tolist()
    if missing:
        parts.append('no ESPN position data for ' + ', '.join(missing) + ' (counted at UTIL only)')
    return ' · '.join(parts)


def fig_minute_weighted(df, league, window, lab):
    if df.empty:
        return empty_fig(no_games_message(league, window), 300)
    tot = player_totals(df)
    m, a = CAT[lab]
    if a:
        val, val_label = tot[m] / tot[a].replace(0, np.nan), f'{lab} (makes ÷ attempts)'
    elif lab == 'MIN':
        val, val_label = tot['minutes_played'] / tot['gp'], 'Minutes / game'
    else:
        weighted = (df[m] * df['minutes_played']).groupby(df['name']).sum()
        val, val_label = weighted / tot['minutes_played'].replace(0, np.nan), f'Minute-weighted {lab} / game'
    rows = val.sort_values(ascending=False).index.tolist()
    mins = tot['minutes_played'].loc[rows]

    fig = make_subplots(rows=1, cols=2, shared_yaxes=True, horizontal_spacing=0.03)
    for col, (series, label, f) in enumerate([(val.loc[rows], val_label, lambda v: fmt(lab, v)),
                                               (mins, 'Total minutes', lambda v: f'{v:.0f}')], start=1):
        fig.add_trace(go.Heatmap(
            z=series.values[:, None], x=[label], y=rows, text=[[f(v)] for v in series.values],
            texttemplate='<b>%{text}</b>', textfont=dict(color=TXT, size=12), colorscale=SEQ_SCALE,
            showscale=False, ygap=3, hovertemplate=f'%{{y}}<br>{label}: %{{text}}<extra></extra>'), 1, col)
    fig.update_yaxes(autorange='reversed', showgrid=False, ticks='')
    fig.update_xaxes(side='top', showgrid=False, ticks='', tickfont=dict(size=12, color=TXT))
    return style_fig(fig, 32 * len(rows) + 60, dict(l=10, r=10, t=36, b=10))


def fig_share(df, league, window, lab):
    """Share of the team's total for the latest week in the window. Returns (fig, subtitle)."""
    if df.empty:
        return empty_fig(no_games_message(league, window), 300), ''
    week = df['week_ending_sunday'].max()
    m, a = CAT[lab]
    s = df[df['week_ending_sunday'] == week].groupby('name')[m].sum()
    sub = f'Week ending {week:%b %d}' + (f' · % has no share, so this shows {CAT_NAMES[lab].replace(" %", "")} makes'
                                         if a else '') + ' · sorted'
    if s.sum() == 0:
        return empty_fig(f'No {lab} recorded this week yet.', 300), sub
    share = (s / s.sum()).sort_values()
    fig = go.Figure(go.Bar(
        x=share.values, y=share.index, orientation='h',
        marker_color=[COLORS[league].get(n, MUTED) for n in share.index],
        text=[f'{v:.1%}' for v in share.values], textposition='outside', cliponaxis=False,
        textfont=dict(color=MUTED, size=11), customdata=s.loc[share.index].values,
        hovertemplate='%{y}: %{x:.1%} (%{customdata:.0f})<extra></extra>'))
    fig.update_xaxes(visible=False, range=[0, float(share.max()) * 1.2])
    fig.update_yaxes(showgrid=False, ticks='')
    return style_fig(fig, 30 * len(share) + 50, dict(l=10, r=10, t=10, b=10)), sub


def fig_weekly(df, league, window, lab):
    if df.empty:
        return empty_fig(no_games_message(league, window), 320)
    m, a = CAT[lab]
    g = df.groupby(['week_ending_sunday', 'name'])
    wk = (g[m].sum() / g[a].sum().replace(0, np.nan)).unstack() if a else g[m].sum().unstack().fillna(0)
    top5 = df.groupby('name')[m].sum().sort_values(ascending=False).index[:5]
    fig = go.Figure()
    for n in [c for c in wk.columns if c not in top5] + list(top5):
        hi = n in top5
        fig.add_trace(go.Scatter(
            x=wk.index, y=wk[n], name=n, mode='lines+markers', showlegend=hi,
            line=dict(color=COLORS[league].get(n, MUTED) if hi else '#4f5668', width=3 if hi else 1.3),
            marker=dict(size=7 if hi else 4),
            hovertemplate=f'{n}<br>Week ending %{{x|%b %d}}: %{{y:{".3f" if a else ".0f"}}}<extra></extra>'))
    fig.update_xaxes(tickvals=wk.index, ticktext=[f'Wk ending {d:%b %d}' for d in wk.index], showgrid=False)
    fig.update_yaxes(title_text=f'{lab} ({"week %" if a else "week total"})')
    style_fig(fig, 380, dict(l=10, r=10, t=10, b=10))
    fig.update_layout(showlegend=True, legend=dict(orientation='v', x=1.01, y=1, font=dict(size=11),
                                                   title=dict(text='Top 5', font=dict(color=MUTED))))
    return fig


####################################################################################################
# 004 - PLAYER DETAIL FIGURES
####################################################################################################

def fig_game_by_game(df, league, window, lab):
    if df.empty:
        return empty_fig(no_games_message(league, window), 380)
    vals = df.assign(v=per_game(df, lab)).dropna(subset=['v'])
    if vals.empty:
        return empty_fig(f'No {lab} attempts in this window.', 380)
    order = vals.groupby('name')['v'].median().sort_values(ascending=False).index.tolist()
    fig = go.Figure()
    for i, n in enumerate(order):
        d = vals[vals['name'] == n].sort_values('date')
        jit = np.linspace(-0.15, 0.15, len(d)) if len(d) > 1 else np.zeros(1)
        last5 = np.arange(len(d)) >= len(d) - 5
        fig.add_trace(go.Box(x=[i] * len(d), y=d['v'], width=0.55, boxpoints=False, fillcolor=NEUTRAL_CELL,
                             line=dict(color='#5a6478', width=1), hoverinfo='skip'))
        for mask, color, size in [(~last5, '#8a8f9c', 6), (last5, COLORS[league].get(n, ACC), 9)]:
            if mask.any():
                fig.add_trace(go.Scatter(
                    x=i + jit[mask], y=d['v'][mask], mode='markers', marker=dict(color=color, size=size),
                    customdata=d['date'][mask].dt.strftime('%b %d'),
                    hovertemplate=f'{n}<br>%{{customdata}}: %{{y:{".3f" if CAT[lab][1] else ".0f"}}}<extra></extra>'))
    fig.update_xaxes(tickvals=list(range(len(order))), ticktext=order, tickangle=-30, showgrid=False, zeroline=False)
    fig.update_yaxes(title_text=CAT_NAMES[lab])
    return style_fig(fig, 430, dict(l=10, r=10, t=10, b=10))


def fig_small_multiples(df, league, window, lab):
    if df.empty:
        return empty_fig(no_games_message(league, window), 400)
    order = value_order(df)
    ncols = 4
    nrows = math.ceil(len(order) / ncols)
    titles = []
    for n in order:
        d = df[df['name'] == n]
        titles.append(f'{n}  <span style="color:{MUTED}">{fmt(lab, category_value(player_totals(d), lab).iloc[0])}</span>')
    fig = make_subplots(rows=nrows, cols=ncols, shared_yaxes='all', subplot_titles=titles,
                        horizontal_spacing=0.03, vertical_spacing=min(0.12, 0.35 / max(nrows, 1)))
    x_start = df['date'].min() - pd.Timedelta(days=1)
    x_end = df['date'].max() + pd.Timedelta(days=1)
    for i, n in enumerate(order):
        r, c = divmod(i, ncols)
        d = df[df['name'] == n].sort_values('date')
        color = COLORS[league].get(n, ACC)
        fig.add_trace(go.Bar(x=d['date'], y=per_game(d, lab), marker_color='#4a5060',
                             hovertemplate='%{x|%b %d}: %{y}<extra></extra>'), r + 1, c + 1)
        fig.add_trace(go.Scatter(x=d['date'], y=rolling(d, lab), mode='lines', line=dict(color=color, width=2.5),
                                 hovertemplate='3-game avg %{y:.2f}<extra></extra>'), r + 1, c + 1)
        avg = category_value(player_totals(d), lab).iloc[0]
        if not (isinstance(avg, float) and math.isnan(avg)):
            fig.add_hline(y=avg, line=dict(color=MUTED, width=1, dash='dash'), row=r + 1, col=c + 1)
    fig.update_xaxes(showticklabels=False, showgrid=False, range=[x_start, x_end])
    fig.update_yaxes(showgrid=True, tickfont=dict(size=10))
    fig.update_annotations(font=dict(size=12, color=TXT))
    return style_fig(fig, 170 * nrows + 40, dict(l=10, r=10, t=30, b=10))


def hot_cold_table(df, league, window):
    if df.empty:
        return html.Div(no_games_message(league, window), className='tp-empty')
    header = html.Tr([html.Th('Player')] + [html.Th(lab) for lab, _, _ in HOT_COLD])
    body = []
    for n in value_order(df):
        d = df[df['name'] == n].sort_values('date')
        cells = [html.Td(n, className='tp-name')]
        if len(d) <= 5:
            cells.append(html.Td(f'only {len(d)} game{"s" if len(d) != 1 else ""} in this window, no trend yet',
                                 colSpan=len(HOT_COLD), className='tp-flat tp-note'))
        else:
            for lab, col, thr in HOT_COLD:
                delta = d[col].tail(5).mean() - d[col].mean()
                cls, arrow = ('tp-hot', ' ▲') if delta >= thr else ('tp-cold', ' ▼') if delta <= -thr else ('tp-flat', '')
                cells.append(html.Td(f'{delta:+.1f}{arrow}', className=cls))
        body.append(html.Tr(cells))
    return html.Table([html.Thead(header), html.Tbody(body)], className='tp-table')


####################################################################################################
# 005 - INJURIES
####################################################################################################

CURVES = _extra['injury_curves_df'].copy()
if not CURVES.empty:
    CURVES['days'] = CURVES['days'].astype(int)
    CURVES['probabilities'] = CURVES['probabilities'].astype(float)
CURVE_N = CURVES.groupby('injury').size().sort_values(ascending=False) if not CURVES.empty else pd.Series(dtype=int)
INJURY_TYPES = sorted(CURVE_N.index.tolist(), key=str.lower)
# pipeline/injury_probabilities_basketball.py now writes one curve per taxonomy group
# ('knee:sprain', 'illness:illness', 'unspecified', ...) on the in-season-day clock. The old
# table held raw notes on calendar days; until it is rebuilt the legacy matcher below is used.
GROUP_CURVES = 'unspecified' in CURVE_N.index or any(':' in str(i) for i in CURVE_N.index)
if GROUP_CURVES:
    INJURY_TYPES = sorted(CURVE_N.index.tolist(), key=describe_group)
    DEFAULT_CURVE = 'unspecified' if 'unspecified' in CURVE_N.index else INJURY_TYPES[0]
else:
    DEFAULT_CURVE = 'placed on IL' if 'placed on IL' in CURVE_N.index else (CURVE_N.index[0] if len(CURVE_N) else None)
CURVE_OPTIONS = [{'label': describe_group(i) if GROUP_CURVES else i, 'value': i} for i in INJURY_TYPES]

_NOTES = _extra.get('injury_notes_df', pd.DataFrame())
NOTE_LABELS = ({} if _NOTES.empty else
               {r['note_key']: {k: (r[k] if isinstance(r[k], str) else None)
                                for k in ['category', 'body_region', 'injury_type', 'non_medical_reason']}
                for r in _NOTES.to_dict('records')})


def curve_label(injury):
    return describe_group(injury) if GROUP_CURVES and injury else injury


def days_since(since, today):
    """Days out on the curves' clock: in-season days for group curves, calendar days for legacy."""
    if GROUP_CURVES:
        try:
            return int(season_calendar.inseason_days(since, today))
        except ValueError:                       # outside season_dates.csv coverage
            pass
    return int((today - since).days)


def match_group(note):
    """Taxonomy curve for a note: the pipeline's label if it has seen the note, else the regex
    guess; then the most specific curve that exists: group, '<region>:other', 'injury:other',
    'unspecified'."""
    key = note_key(note)
    fields = NOTE_LABELS.get(key) or regex_classify(key)[0]
    group = curve_group(fields) if fields.get('category') else 'unspecified'
    head = group.split(':')[0]
    for g in [group, f'{head}:other', 'injury:other' if fields.get('category') == 'injury' else None, 'unspecified']:
        if g and g in CURVE_N.index:
            return g
    return DEFAULT_CURVE

_STOP = {'placed', 'on', 'il', 'with', 'out', 'indefinitely', 'dtd', 'the', 'to', 'of', 'and', 'a', 'for',
         'in', 'from', 'day', 'dl', 'up', 'activated', 'transferred', 'status', 'return', 'expected', 'game',
         'games', 'season', 'clean', 'debris', 'his', 'by', 'at', 'after'}
_BODY = {'ankle', 'knee', 'calf', 'hamstring', 'back', 'foot', 'hip', 'groin', 'shoulder', 'wrist', 'hand',
         'finger', 'thumb', 'achilles', 'concussion', 'illness', 'quad', 'quadriceps', 'thigh', 'toe', 'elbow',
         'abdominal', 'oblique', 'neck', 'rib', 'ribs', 'chest', 'heel', 'shin', 'leg', 'arm', 'eye', 'face',
         'nose', 'jaw', 'covid', 'flu', 'adductor', 'plantar', 'pelvis', 'tailbone', 'spine', 'head', 'personal',
         'protocols', 'meniscus', 'acl', 'mcl', 'fibula', 'tibia', 'forearm', 'patellar'}


def _tokens(s):
    return set(re.findall(r'[a-z]+', str(s).lower())) - _STOP


def match_curve(note):
    """Survival curve for a free-text injury note. Group curves: taxonomy match.
    Legacy curves: exact match, else the curve sharing the same body part with the
    most overlapping words, else the generic 'placed on IL' curve."""
    if not note or DEFAULT_CURVE is None:
        return DEFAULT_CURVE
    if GROUP_CURVES:
        return match_group(note)
    lowered = {i.lower(): i for i in INJURY_TYPES}
    if note.strip().lower() in lowered:
        return lowered[note.strip().lower()]
    t = _tokens(note)
    body = t & _BODY
    if not body:
        return DEFAULT_CURVE
    best, best_score = None, (-1, -1)
    for inj in INJURY_TYPES:
        it = _tokens(inj)
        if not body & it:
            continue
        score = (len(t & it) / len(t | it), int(CURVE_N[inj]))
        if score > best_score:
            best, best_score = inj, score
    return best or DEFAULT_CURVE


def survival(injury, t):
    """Chance the injury still keeps a player out after t days (step function, S(0)=1)."""
    c = CURVES[CURVES['injury'] == injury]
    c = c[c['days'] <= t]
    return 1.0 if c.empty else float(c.sort_values('days')['probabilities'].iloc[-1])


def name_key(name):
    s = unicodedata.normalize('NFKD', str(name)).encode('ascii', 'ignore').decode().lower()
    s = re.sub(r"[.'’,]", '', s).replace('-', ' ')
    return ' '.join(t for t in s.split() if t not in {'jr', 'sr', 'ii', 'iii', 'iv'})


def _move_keys(cell):
    """prosportstransactions packs 'Name / Alias' into one cell and prefixes bullets."""
    if not isinstance(cell, str) or not cell.strip():
        return set()
    return {name_key(p.strip(' •')) for p in cell.split('/') if p.strip(' •')}


MOVES = _extra['injury_moves_df'].copy()
if not MOVES.empty:
    MOVES['day'] = pd.to_datetime(MOVES['day'])
    MOVES['acq_keys'] = MOVES['acquired'].map(_move_keys)
    MOVES['rel_keys'] = MOVES['relinquished'].map(_move_keys)


def current_injury(name):
    """This season's open injury stint for a player from the transaction log:
    {'since', 'note'} if his latest move was being ruled out / placed on IL."""
    if MOVES.empty:
        return None
    key = name_key(name)
    rel = MOVES[MOVES['rel_keys'].map(lambda k: key in k)]
    if rel.empty:
        return None
    acq = MOVES[MOVES['acq_keys'].map(lambda k: key in k)]
    if not acq.empty:
        rel = rel[rel['day'] > acq['day'].max()]
        if rel.empty:
            return None
    rel = rel.sort_values('day')
    return {'since': rel['day'].iloc[0], 'note': rel['notes'].iloc[-1]}


def out_players(league):
    """Players on my roster who are currently out, with injury note, days out and
    matched curve. Status comes from the fantasy platform (pipeline/my_team_stats.py);
    if that column hasn't been populated yet, falls back to the transaction log."""
    st = STATUS.get(league)
    has_status = st is not None and 'injury_status' in st and st['injury_status'].notna().any()
    if has_status:
        source = f'Status from {league} · injury details from prosportstransactions'
        flagged = [(n, str(s).upper()) for n, s in zip(st['name'], st['injury_status'].fillna(''))
                   if str(s).upper() not in HEALTHY]
    else:
        source = ('Status from prosportstransactions moves (run the injury_status migration and '
                  'pipeline.my_team_stats for ESPN / Yahoo status)')
        flagged = [(n, 'OUT') for n in ROSTER.get(league, []) if current_injury(n)]
    today = pd.Timestamp(dt.date.today())
    players = []
    for n, status in flagged:
        inj = current_injury(n)
        days_out = days_since(inj['since'], today) if inj else None
        curve = match_curve(inj['note']) if inj else DEFAULT_CURVE
        back_7 = None
        if inj and curve:
            s_now = survival(curve, days_out)
            back_7 = 1 - survival(curve, days_out + 7) / s_now if s_now > 0 else None
        players.append({'name': n, 'status': STATUS_LABELS.get(status, status.replace('_', ' ').title()),
                        'note': inj['note'] if inj else None, 'since': inj['since'] if inj else None,
                        'days_out': days_out, 'curve': curve, 'back_7': back_7})
    players.sort(key=lambda p: (p['days_out'] is None, -(p['days_out'] or 0)))
    return players, source


def fig_injury_curve(injury, player=None):
    if injury is None or CURVES.empty:
        return empty_fig('No injury curves loaded.', 360)
    c = CURVES[CURVES['injury'] == injury].sort_values('days')
    if c.empty:
        return empty_fig(f'No curve for "{injury}".', 360)
    x = np.r_[0, c['days'].values]
    y = np.r_[1.0, c['probabilities'].values]
    x_max = min(int(c['days'].max()), 60)
    fig = go.Figure(go.Scatter(x=x, y=y, mode='lines', line=dict(color=ACC, width=3, shape='hv'),
                               fill='tozeroy', fillcolor='rgba(0,188,140,0.15)',
                               hovertemplate='After %{x} days: %{y:.0%} still out<extra></extra>'))
    if player and player.get('days_out') is not None and player.get('curve') == injury:
        d = player['days_out']
        x_max = max(x_max, min(d + 21, int(c['days'].max())))
        s = survival(injury, d)
        fig.add_vline(x=d, line=dict(color=AMBER, width=2, dash='dash'))
        fig.add_annotation(x=d, y=s, text=f"{player['name']}: day {d}", showarrow=True, arrowcolor=AMBER,
                           ax=50, ay=-40, font=dict(color=AMBER, size=12), bgcolor='#1a2035')
    fig.update_xaxes(title_text='In-season days since ruled out' if GROUP_CURVES else 'Days since ruled out',
                     range=[0, x_max], showgrid=False)
    fig.update_yaxes(tickformat='.0%', range=[0, 1.03])
    return style_fig(fig, 380, dict(l=10, r=20, t=10, b=10))


def key_days(injury, player=None):
    """Key-day probabilities; conditional on days already out when a player is selected."""
    if injury is None or CURVES.empty:
        return html.Div('No injury curves loaded.', className='tp-empty'), ''
    conditional = player and player.get('days_out') is not None and player.get('curve') == injury
    d0 = player['days_out'] if conditional else 0
    s0 = survival(injury, d0) if conditional else 1.0
    rows = []
    for k in [1, 3, 7, 14, 21, 30]:
        p = survival(injury, d0 + k) / s0 if s0 > 0 else 0.0
        rows.append(html.Tr([
            html.Td(f'{k} {"more " if conditional else ""}day{"s" if k > 1 else ""}'),
            html.Td(html.Div(html.Div(style={'width': f'{p * 100:.0f}%'}, className='tp-bar-fill'), className='tp-bar')),
            html.Td(f'{p:.0%}', className='tp-pct'),
        ]))
    sub = (f"Given {player['name']} has been out {d0} days, chance they're still out after…" if conditional
           else 'Chance a player with this injury is still out after…')
    table = html.Table([html.Thead(html.Tr([html.Th('Days'), html.Th(''), html.Th('Still out')])),
                        html.Tbody(rows)], className='tp-table tp-keydays')
    return table, sub


def out_list(league, selected=None):
    players, source = out_players(league)
    if not players:
        return html.Div(f'No one on your {league} roster is listed as out.', className='tp-empty'), source
    items = []
    for p in players:
        meta = []
        if p['since'] is not None:
            meta.append(f"Since {p['since']:%b %d} · {p['days_out']} {'in-season ' if GROUP_CURVES else ''}days out")
        if p['back_7'] is not None:
            meta.append(f"{p['back_7']:.0%} chance back within 7 days")
        items.append(html.Button([
            html.Div([html.Span(p['name'], className='tp-out-name'),
                      html.Span(p['status'], className='tp-badge')], className='tp-out-head'),
            html.Div(p['note'] or 'No injury note found this season · showing the generic curve', className='tp-out-note'),
            html.Div(' · '.join(meta), className='tp-out-meta'),
            html.Div(f"Curve: {curve_label(p['curve'])}", className='tp-out-curve'),
        ], id={'type': 'tp-out-player', 'index': p['name']}, n_clicks=0,
            className='tp-out-item' + (' selected' if p['name'] == selected else '')))
    return html.Div(items, className='tp-out-grid'), source


####################################################################################################
# 006 - LAYOUT
####################################################################################################

def _card(title, body, sub='', accent=False, title_id=None, sub_id=None):
    t_kw = {'id': title_id} if title_id else {}
    s_kw = {'id': sub_id} if sub_id else {}
    return html.Div([html.Div(title, className='tp-card-title', **t_kw),
                     html.Div(sub, className='tp-card-sub', **s_kw), body],
                    className='tp-card' + (' tp-card--accent' if accent else ''))


def _graph(graph_id):
    return dcc.Graph(id=graph_id, config=GRAPH_CONFIG, figure=empty_fig('Loading…'))


def _section(title, sub, control=None):
    return html.Div([
        html.Div([html.H3(title, className='tp-section-title'), html.Div(sub, className='tp-section-sub')]),
        html.Div(control, className='tp-section-control') if control else None,
    ], className='tp-section')


def _control(label, component):
    return html.Div([html.Span(label, className='tp-control-label'), component], className='tp-control')


def _row(*cols):
    return html.Div([html.Div(c, className=cls) for c, cls in cols], className='row')


def filter_bar(style):
    """Page-wide filters: league and time window."""
    def block(label, component):
        return html.Div([html.H5(label, style={'text-align': 'left', 'color': 'rgb(77, 79, 91)'}),
                         html.Div(component, style={'margin-top': '5px'})],
                        className='col-md-3 col-6', style={'margin': '10px 0 5px', 'paddingLeft': 5})
    return html.Div([html.Div([html.Div([
        block('League:', dcc.Dropdown(id='tp-league', options=LEAGUE_OPTIONS, value='ESPN', clearable=False)),
        block('Window:', dcc.Dropdown(id='tp-window', options=WINDOW_OPTIONS, value='season', clearable=False)),
    ], className='row', style={'padding': '0 24px'})], className='col-12', style=style)], className='row sticky-top')


TAB_STYLE = {'backgroundColor': '#161b27', 'color': MUTED, 'border': f'1px solid {GRID}',
             'borderRadius': '8px 8px 0 0', 'padding': '10px 16px', 'fontWeight': 500}
TAB_SELECTED = dict(TAB_STYLE, color=TXT, borderTop=f'3px solid {ACC}', backgroundColor='#1a2035')


def _tab_overview():
    return html.Div([
        _section('Category value', 'All 12 categories at once · colour shows how far above or below '
                 'the league average each player is'),
        _card('Player × category value', _graph('tp-value-heatmap'), accent=True,
              sub='Cell = per-game stat (FG% / FT% / 3P% = makes ÷ attempts). Colour = z-score vs league '
                  f'rotation players ({BASELINE_MIN_MPG}+ MPG, season to date); percentage colours are '
                  'volume-weighted; TO inverted so green is good. Sorted by total value.'),
        _section('Position depth', 'How many of my ESPN players can fill each lineup slot, and who they are',
                 _control('Injured players:', dcc.RadioItems(
                     id='tp-depth-injured', value='exclude', inline=True, className='tp-segmented',
                     options=[{'label': 'Exclude', 'value': 'exclude'}, {'label': 'Include', 'value': 'include'}]))),
        _card('Players eligible by position', _graph('tp-depth'), accent=True, sub_id='tp-depth-sub'),
        _section('Minutes-played weighted production', 'The category picker applies to this section',
                 _control('Category:', dcc.Dropdown(id='tp-category', options=CATEGORY_OPTIONS, value='PTS',
                                                    clearable=False))),
        _row((_card('', _graph('tp-mw'), sub='One chart, one row order', accent=True, title_id='tp-mw-title'),
              'col-lg-6 col-12'),
             (_card('', _graph('tp-share'), title_id='tp-share-title', sub_id='tp-share-sub'), 'col-lg-6 col-12')),
        _card('', _graph('tp-weekly'), sub='Top 5 highlighted, everyone else in grey (hover for names)',
              title_id='tp-weekly-title'),
    ], className='tp-tab-body')


def _tab_player_detail():
    return html.Div([
        _section('Game-by-game and recent form', 'How each player is trending, game by game',
                 _control('Category:', dcc.Dropdown(id='tp-category-2', options=CATEGORY_OPTIONS, value='PTS',
                                                    clearable=False))),
        _card('', _graph('tp-strip'), title_id='tp-strip-title',
              sub='Box = spread · dots = games · last 5 games in the player colour'),
        _row((_card('', _graph('tp-multiples'), title_id='tp-multiples-title',
                    sub='Bars = games · line = 3-game rolling avg · dashed = window avg'), 'col-lg-7 col-12'),
             (_card('Hot / cold', html.Div(id='tp-hotcold'),
                    sub='Last 5 games minus the window average · ▲ hot, ▼ cold'), 'col-lg-5 col-12')),
    ], className='tp-tab-body')


def _tab_injuries():
    return html.Div([
        _section('Players currently out', 'Click a player to load their injury curve'),
        _card('My injured players', html.Div(id='tp-out-list'), sub_id='tp-out-source'),
        _section('Injury outlook', 'Pick any injury to explore its curve',
                 _control('Injury curve:', dcc.Dropdown(id='tp-injury', options=CURVE_OPTIONS, value=DEFAULT_CURVE,
                                                        clearable=False, searchable=True,
                                                        style={'minWidth': '320px'}))),
        _row((_card('Chance still out after N days', _graph('tp-injury-curve'), sub_id='tp-curve-sub'),
              'col-lg-7 col-12'),
             (_card('Key days', html.Div(id='tp-key-days'), sub_id='tp-key-sub'), 'col-lg-5 col-12')),
        dcc.Store(id='tp-selected-player'),
    ], className='tp-tab-body')


def tabs_body():
    return html.Div(dcc.Tabs(id='tp-tabs', value='overview', children=[
        dcc.Tab(label='Team overview', value='overview', style=TAB_STYLE, selected_style=TAB_SELECTED,
                children=_tab_overview()),
        dcc.Tab(label='Player detail', value='player', style=TAB_STYLE, selected_style=TAB_SELECTED,
                children=_tab_player_detail()),
        dcc.Tab(label='Injuries', value='injuries', style=TAB_STYLE, selected_style=TAB_SELECTED,
                children=_tab_injuries()),
    ]), className='tp-container')


####################################################################################################
# 007 - CALLBACKS
####################################################################################################

@app_inst.callback(
    Output('tp-value-heatmap', 'figure'),
    Output('tp-mw', 'figure'), Output('tp-mw-title', 'children'),
    Output('tp-share', 'figure'), Output('tp-share-title', 'children'), Output('tp-share-sub', 'children'),
    Output('tp-weekly', 'figure'), Output('tp-weekly-title', 'children'),
    Input('tp-league', 'value'), Input('tp-window', 'value'), Input('tp-category', 'value'),
)
def update_overview(league, window, lab):
    df = window_games(league, window)
    share, share_sub = fig_share(df, league, window, lab)
    name = CAT_NAMES[lab].lower()
    return (fig_value_heatmap(df, league, window),
            fig_minute_weighted(df, league, window, lab), f'Minute-weighted {name} + minutes',
            share, f'Share of team {name if not CAT[lab][1] else name.replace(" %", "") + " makes"}', share_sub,
            fig_weekly(df, league, window, lab), f'Weekly {name} by player')


@app_inst.callback(
    Output('tp-depth', 'figure'), Output('tp-depth-sub', 'children'),
    Input('tp-depth-injured', 'value'),
)
def update_position_depth(choice):
    # ESPN only for now: the page's league filter doesn't apply (Yahoo has no position data yet)
    include = choice == 'include'
    return fig_position_depth(include), position_depth_sub(include)


@app_inst.callback(
    Output('tp-strip', 'figure'), Output('tp-strip-title', 'children'),
    Output('tp-multiples', 'figure'), Output('tp-multiples-title', 'children'),
    Output('tp-hotcold', 'children'),
    Input('tp-league', 'value'), Input('tp-window', 'value'), Input('tp-category-2', 'value'),
)
def update_player_detail(league, window, lab):
    df = window_games(league, window)
    name = CAT_NAMES[lab]
    return (fig_game_by_game(df, league, window, lab), f'Game-by-game {name.lower()}',
            fig_small_multiples(df, league, window, lab), f'{name} by game · small multiples',
            hot_cold_table(df, league, window))


@app_inst.callback(
    Output('tp-selected-player', 'data'), Output('tp-injury', 'value'),
    Input({'type': 'tp-out-player', 'index': ALL}, 'n_clicks'), Input('tp-league', 'value'),
)
def select_out_player(_clicks, league):
    """League change (or first load) selects the longest-out player; a click selects that player.
    Re-rendered buttons arrive with n_clicks=0 and are ignored."""
    players = {p['name']: p for p in out_players(league)[0]}
    trigger = ctx.triggered_id
    if isinstance(trigger, dict):
        if not ctx.triggered or not ctx.triggered[0]['value']:
            raise PreventUpdate
        name = trigger['index']
    else:
        name = next(iter(players), None)
    p = players.get(name)
    return (name, p['curve'] or DEFAULT_CURVE) if p else (None, DEFAULT_CURVE)


@app_inst.callback(
    Output('tp-out-list', 'children'), Output('tp-out-source', 'children'),
    Input('tp-league', 'value'), Input('tp-selected-player', 'data'),
)
def update_out_list(league, selected):
    return out_list(league, selected)


@app_inst.callback(
    Output('tp-injury-curve', 'figure'), Output('tp-curve-sub', 'children'),
    Output('tp-key-days', 'children'), Output('tp-key-sub', 'children'),
    Input('tp-injury', 'value'), Input('tp-selected-player', 'data'), Input('tp-league', 'value'),
)
def update_injury_curve(injury, selected, league):
    player = next((p for p in out_players(league)[0] if p['name'] == selected), None)
    on_curve = player is not None and player['curve'] == injury and player['days_out'] is not None
    sub = f'"{curve_label(injury)}"' + (f" · dashed line = {player['name']}, day {player['days_out']}" if on_curve else '')
    table, key_sub = key_days(injury, player)
    return fig_injury_curve(injury, player), sub, table, key_sub
