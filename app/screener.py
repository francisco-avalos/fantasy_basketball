"""
screener.py
-----------
The Free Agent Screener page (page 2, /apps/free-agent-screening): data prep, the ranked
table, the player drawer, the "My needs" view and their callbacks.

    filter bar   league, window, stat type, view (Ranked / My needs), injured filter,
                 a Columns menu (columns + rows) and a searchable "Hide players"
    table        one row per free agent; each stat column coloured by its percentile among
                 free agents with enough games in the window, so every column reads on its
                 own scale (one shared colour scale made points the only bright column)
    drawer       the clicked player: last 10 games, best categories, and a category-by-category
                 comparison with the weakest player on my roster at a position he can play
    My needs     re-ranks by mean percentile over the ticked categories; pre-ticked with my
                 roster's three weakest categories vs league rotation players

Data: the free-agent game rows come from app.callbacks (loaded once at import there); my roster,
the league baseline and the free-agent injury curves come from app.team_performance. Positions
and the latest ESPN injury snapshot are loaded here via shared.data_imports.screener_data().
Like the rest of the app, nothing refreshes until the dyno restarts.

Players are grouped by bbref slug, not name: the history rows carry basketball-reference's
spelling, which can differ from the live free-agent name. Group-bys use plain sums / agg (no
groupby().apply()), so the frames behave the same on local pandas 1.3.5 and Heroku's 2.2.3.
"""

import ast
import datetime as dt
import math

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from dash import dcc, html, Input, Output, State, ALL, ctx
from dash.exceptions import PreventUpdate

from app.dash_create import app_inst
from app.callbacks import fa_espn_df, fa_yahoo_df, get_connection_from_pool, close_connection
from app import team_performance as tp
from shared.data_imports import screener_data
from shared.my_functions import name_key


####################################################################################################
# 000 - CONSTANTS
####################################################################################################

WINDOWS = [('7', '7 d'), ('14', '14 d'), ('30', '30 d'), ('season', 'Season'),
           ('prior', 'Prior seasons'), ('all', 'All seasons')]
WINDOW_TEXT = {'7': 'last 7 days', '14': 'last 14 days', '30': 'last 30 days', 'season': 'season to date',
               'prior': 'prior seasons', 'all': 'all seasons'}
CURRENT_WINDOWS = {'7', '14', '30', 'season'}

CALCS = [
    ('weights', 'Per game · minute-weighted',
     'Per-game stats, with each game weighted by the minutes he played: sum(stat × minutes) ÷ sum(minutes). '
     'A 30-minute game counts three times as much as a 10-minute one.'),
    ('mean', 'Per game', 'Plain per-game averages: every game counts the same.'),
    ('sum', 'Totals', 'Totals over the window. Players with more games rank higher.'),
    ('std', 'Consistency', 'Standard deviation of his per-game values: lower is steadier. Not coloured.'),
]

# label -> (made / count column, attempts column or None)
COLS = {
    'PTS': ('points_scored', None), 'REB': ('total_rebounds', None), 'AST': ('assists', None),
    '3PM': ('made_three_point_field_goals', None), 'STL': ('steals', None), 'BLK': ('blocks', None),
    'TO': ('turnovers', None), 'FGM': ('made_field_goals', None),
    'FG%': ('made_field_goals', 'attempted_field_goals'), 'FTM': ('made_free_throws', None),
    'FT%': ('made_free_throws', 'attempted_free_throws'),
    '3P%': ('made_three_point_field_goals', 'attempted_three_point_field_goals'),
    'OREB': ('offensive_rebounds', None), 'DREB': ('defensive_rebounds', None), 'PF': ('personal_fouls', None),
}
LEAGUE_CATS = tp.CAT_LABELS                       # the 12 categories my leagues score
DEFAULT_COLS = ['PTS', 'REB', 'AST', '3PM', 'STL', 'BLK', 'TO', 'FGM', 'FG%', 'FTM', 'FT%', '3P%']
INVERT = {'TO', 'PF'}                             # lower is better
NAMES = dict(tp.CAT_NAMES, OREB='Offensive rebounds', DREB='Defensive rebounds', PF='Personal fouls')
RAW = ['seconds_played', 'made_field_goals', 'attempted_field_goals', 'made_three_point_field_goals',
       'attempted_three_point_field_goals', 'made_free_throws', 'attempted_free_throws', 'offensive_rebounds',
       'defensive_rebounds', 'assists', 'steals', 'blocks', 'turnovers', 'personal_fouls', 'points_scored']
MAKE_ATT = sorted({c for m, a in COLS.values() for c in (m, a) if c})
ROLE_ORDER = ['PG', 'SG', 'SF', 'PF', 'C']

DEFAULT_ROWS = 15
TREND_MIN = 3        # minutes: last 3 games vs window average that counts as a role change
POOL_MIN = 10        # percentiles fall back to every player when fewer qualify


def min_gp(window):
    """Games a player needs in the window to set the percentile scale (and not be dimmed)."""
    return 2 if window == '7' else 3


####################################################################################################
# 001 - DATA
####################################################################################################

_conn = get_connection_from_pool()
try:
    _extra = screener_data(_conn)
finally:
    close_connection(_conn)


def _prep(df):
    """Free-agent game rows with float stats, real dates, minutes and rebounds; games played only."""
    cols = ['slug', 'name', 'date', 'team', 'current'] + RAW + ['total_rebounds', 'minutes_played']
    if df is None or df.empty or 'slug' not in df:
        return pd.DataFrame(columns=cols)
    out = pd.DataFrame({
        'slug': df['slug'].astype(str), 'name': df['name'].astype(str), 'date': pd.to_datetime(df['date']),
        'team': df['team'].astype(str), 'current': df['current_season_vs_historicals'].eq('current_season_only'),
    })
    for c in RAW:
        out[c] = pd.to_numeric(df[c], errors='coerce').fillna(0.0).astype(float)
    out['total_rebounds'] = out['offensive_rebounds'] + out['defensive_rebounds']
    out['minutes_played'] = out['seconds_played'] / 60
    out = out[out['minutes_played'] > 0]
    return out[cols].sort_values(['date', 'slug']).reset_index(drop=True)


FA = {'ESPN': _prep(fa_espn_df), 'Yahoo': _prep(fa_yahoo_df)}


def _display_names(df):
    """slug -> name, preferring the live free-agent spelling (current-season rows) over bbref's."""
    if df.empty:
        return {}
    names = df.groupby('slug')['name'].last()
    cur = df[df['current']]
    if not cur.empty:
        names.update(cur.groupby('slug')['name'].last())
    return names.to_dict()


NAME = {lg: _display_names(FA[lg]) for lg in FA}


def _roles(pos_df):
    """name_key -> eligible base positions (PG..C), from ESPN eligibleSlots."""
    out = {}
    if pos_df is None or pos_df.empty:
        return out
    for n, r in zip(pos_df['name'], pos_df['player_roles']):
        try:
            slots = set(ast.literal_eval(r))
        except (ValueError, SyntaxError):
            continue
        out[name_key(n)] = [p for p in ROLE_ORDER if p in slots]
    return out


ROLES = _roles(_extra.get('positions_df'))

_status = _extra.get('status_df', pd.DataFrame())
STATUS = ({} if _status.empty else
          dict(zip(_status['slug'], _status['injury_status'].fillna('').astype(str).str.upper())))
SNAPSHOT = None if _status.empty else pd.Timestamp(_status['snapshot_date'].max())
ODDS = tp.fa_injury_odds()          # slug -> chance back within 7 / 14 days (ESPN free agents)


def roles_of(name):
    return ROLES.get(name_key(name), [])


def injury_info(slug):
    """(status label, curve odds or None) for an injured free agent, else None. Today's ESPN status wins:
    a player ESPN lists as active is healthy even if the transaction log still has his absence open."""
    raw = STATUS.get(slug)
    if raw is not None and raw in tp.HEALTHY:
        return None
    odds = ODDS.get(slug)
    if raw is None and odds is None:
        return None
    label = tp.STATUS_LABELS.get(raw, raw.replace('_', ' ').title()) if raw else 'Out'
    return label, odds


def team_name(raw):
    """'Team.DENVER_NUGGETS' -> 'Denver Nuggets'."""
    return str(raw).replace('Team.', '').replace('_', ' ').title().replace('76Ers', '76ers')


def window_frame(league, window):
    df = FA.get(league, FA['ESPN'])
    if window == 'prior':
        return df[~df['current']]
    if window == 'all':
        return df
    df = df[df['current']]
    if window not in (None, 'season'):
        df = df[df['date'] >= pd.Timestamp(dt.date.today() - dt.timedelta(days=int(window)))]
    return df


def roster_needs(league):
    """My roster's three weakest categories (mean z-score vs league rotation players, season to date)."""
    games = tp.GAMES.get(league, pd.DataFrame())
    if games.empty:
        return []
    z = tp.zscores(tp.player_totals(games))[LEAGUE_CATS].mean()
    return z.nsmallest(3).index.tolist()


NEEDS = {lg: roster_needs(lg) for lg in FA}


####################################################################################################
# 002 - CALCULATION
####################################################################################################

def aggregate(d, calc):
    """Per-slug values for every column under the chosen stat type, plus the metric each column is
    coloured and sorted on. Percentages are coloured on volume-weighted impact (makes above the league
    rate for the attempts taken), so 1-for-1 doesn't top FG%."""
    g = d.groupby('slug')
    out = pd.DataFrame({'gp': g.size(), 'min': g['minutes_played'].sum()})
    out['mpg'] = out['min'] / out['gp']
    if calc == 'weights':
        vals = d[MAKE_ATT].multiply(d['minutes_played'], axis=0).groupby(d['slug']).sum()
        vals = vals.div(out['min'].replace(0, np.nan), axis=0)
    elif calc == 'std':
        vals = g[MAKE_ATT].std(ddof=0)
    else:
        vals = g[MAKE_ATT].agg(calc)
    metric = pd.DataFrame(index=out.index)
    for lab, (m, a) in COLS.items():
        if a is None:
            out[lab] = vals[m]
            metric[lab] = vals[m]
        elif calc == 'std':
            per_game = d[m] / d[a].where(d[a] > 0)
            out[lab] = per_game.groupby(d['slug']).std(ddof=0)
            metric[lab] = out[lab]
        else:
            out[lab] = vals[m] / vals[a].replace(0, np.nan)
            lp = tp.LEAGUE_PCT.get(lab, np.nan)
            metric[lab] = vals[m] - lp * vals[a] if np.isfinite(lp) else out[lab]
    last3 = d.groupby('slug').tail(3).groupby('slug')['minutes_played'].mean()
    out['trend'] = last3 - out['mpg']
    return out, metric


def percentiles(metric, qualified):
    """0-100 percentile of each column against the qualified players (TO / PF inverted)."""
    pool = metric[qualified] if qualified.sum() >= POOL_MIN else metric
    out = {}
    for lab in metric.columns:
        ref = np.sort(pool[lab].dropna().values)
        v = metric[lab].values.astype(float)
        if len(ref) == 0:
            out[lab] = np.full(len(v), np.nan)
            continue
        if lab in INVERT:
            p = 1 - np.searchsorted(ref, v, side='left') / len(ref)
        else:
            p = np.searchsorted(ref, v, side='right') / len(ref)
        out[lab] = np.where(np.isnan(v), np.nan, p * 100)
    return pd.DataFrame(out, index=metric.index)


def screen(league, window, calc, needs, hide, injured):
    """The full screened frame (every free agent in the window, after filters), or a message."""
    d = window_frame(league, window)
    if d.empty:
        if FA.get(league, pd.DataFrame()).empty:
            return None, (f'No {league} free agents loaded. The Yahoo pipeline is paused until API access '
                          'is approved.' if league == 'Yahoo' else f'No {league} free agents loaded.')
        return None, f'No free-agent games in the {WINDOW_TEXT[window]}. Try a longer window.'
    out, metric = aggregate(d, calc)
    out['qualified'] = out['gp'] >= min_gp(window)
    if calc != 'std':
        pct = percentiles(metric, out['qualified'])
        for lab in COLS:
            out[f'p_{lab}'] = pct[lab]
        out['Value'] = pct[LEAGUE_CATS].mean(axis=1)
        out['Fit'] = pct[needs].mean(axis=1) if needs else np.nan
    out['name'] = [NAME[league].get(s, s) for s in out.index]
    out['injury'] = pd.Series([injury_info(s) for s in out.index], index=out.index, dtype=object)
    if hide:
        out = out[~out.index.isin(hide)]
    if injured == 'healthy':
        out = out[out['injury'].isna()]
    elif injured == 'only':
        out = out[out['injury'].notna()]
    if out.empty:
        return None, 'No players left after the filters. Check "Hide players" and the injured filter.'
    return out, None


def sort_frame(out, key, calc):
    """Best first, players with enough games ahead of the rest (a 1-game outlier doesn't top the list).
    Stat columns sort on their percentile (raw value under Consistency)."""
    if key in COLS:
        col = f'p_{key}' if calc != 'std' else key
    else:
        col = {'GP': 'gp', 'MPG': 'mpg'}.get(key, key)
    return out.sort_values(['qualified', col, 'mpg'], ascending=[False, False, False], na_position='last')


def default_sort(mode, calc):
    if calc == 'std':
        return 'PTS'
    return 'Fit' if mode == 'needs' else 'Value'


####################################################################################################
# 003 - TABLE
####################################################################################################

def fmt(lab, v, calc):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return '–'
    if lab.endswith('%'):
        return f'{v:.3f}'.lstrip('0') if v < 1 else f'{v:.3f}'
    if calc == 'sum':
        return f'{v:.0f}'
    return f'{v:.1f}' if calc != 'std' else f'{v:.2f}'


def heat(p):
    if p is None or (isinstance(p, float) and math.isnan(p)):
        return ''
    if p >= 80:
        return 'fa-q4'
    if p >= 60:
        return 'fa-q3'
    if p < 20:
        return 'fa-q1'
    return ''


def injury_chip(info):
    if not info:
        return None
    label, odds = info
    text = label + (f" · {odds['back_7']:.0%} in 7 d" if odds else '')
    tip = (f"{tp.curve_label(odds['group'])}, {odds['days_out']} in-season days out · "
           f"{odds['back_14']:.0%} back within 14 days · median "
           f"{odds['median_more'] if odds['median_more'] is not None else '150+'} more days"
           if odds else 'ESPN injury status (no fitted curve for this absence)')
    cls = 'fa-chip fa-chip--dtd' if label in ('Day-to-day', 'Game-time decision') else 'fa-chip'
    return html.Span(text, className=cls, title=tip)


def _th(label, sort_key, active, title=None, numeric=True):
    cls = 'fa-sortable' + (' fa-sorted' if sort_key == active else '') + ('' if numeric else ' fa-left')
    return html.Th([label, html.Span(' ▾' if sort_key == active else '', className='fa-arrow')],
                   id={'type': 'fa-sort', 'index': sort_key}, n_clicks=0, className=cls, title=title)


def table(out, cols, sort_key, selected, mode, calc, window, n_rows):
    current = window in CURRENT_WINDOWS
    show_value = calc != 'std' and mode == 'ranked'
    show_fit = calc != 'std' and mode == 'needs'
    head = [html.Th('#', className='fa-left'), html.Th('Player', className='fa-left'),
            html.Th('Pos', className='fa-left'),
            _th('GP', 'GP', sort_key, 'Games played in the window'),
            _th('MPG', 'MPG', sort_key, 'Minutes per game in the window')]
    head += [_th(lab, lab, sort_key, NAMES.get(lab, lab)) for lab in cols]
    if show_value:
        head.append(_th('Value', 'Value', sort_key, 'Mean percentile across the 12 league categories'))
    if show_fit:
        head += [_th('Fit', 'Fit', sort_key, 'Mean percentile across the ticked categories'), html.Th('')]
    if current:
        head.append(html.Th('Min trend', title=f'Minutes in his last 3 games vs his average in this window '
                                               f'(▲ / ▼ at {TREND_MIN}+ minutes)'))
    body = []
    for i, (slug, r) in enumerate(out.head(n_rows).iterrows(), start=1):
        cells = [html.Td(i, className='fa-left fa-rank'),
                 html.Td([html.Span(r['name'], className='fa-name'), injury_chip(r['injury'])], className='fa-left'),
                 html.Td('/'.join(roles_of(r['name'])) or '–', className='fa-left fa-muted'),
                 html.Td(int(r['gp'])), html.Td(f"{r['mpg']:.1f}")]
        for lab in cols:
            p = r.get(f'p_{lab}', np.nan) if calc != 'std' else np.nan
            cells.append(html.Td(fmt(lab, r[lab], calc), className=heat(p),
                                 title=None if calc == 'std' or pd.isna(p) else f'{p:.0f}th percentile'))
        if show_value:
            cells.append(html.Td(f"{r['Value']:.0f}" if pd.notna(r['Value']) else '–', className='fa-strong'))
        if show_fit:
            fit = r['Fit']
            cells.append(html.Td(f'{fit:.0f}' if pd.notna(fit) else '–', className='fa-strong'))
            cells.append(html.Td(html.Div(html.Div(style={'width': f'{fit if pd.notna(fit) else 0:.0f}%'},
                                                   className='tp-bar-fill'), className='tp-bar fa-fitbar')))
        if current:
            t = r['trend']
            if pd.notna(t) and t >= TREND_MIN:
                cells.append(html.Td(f'▲ {t:+.1f}', className='pr-up'))
            elif pd.notna(t) and t <= -TREND_MIN:
                cells.append(html.Td(f'▼ {t:+.1f}', className='pr-down'))
            else:
                cells.append(html.Td('–', className='fa-muted'))
        cls = ' '.join(c for c in ['fa-row', 'fa-selected' if slug == selected else '',
                                   '' if r['qualified'] else 'fa-dim'] if c)
        body.append(html.Tr(cells, id={'type': 'fa-row', 'index': slug}, n_clicks=0, className=cls))
    return html.Div(html.Table([html.Thead(html.Tr(head)), html.Tbody(body)], className='tp-table fa-table'),
                    className='fa-table-wrap')


def caption(calc, window, mode):
    g = min_gp(window)
    if calc == 'std':
        return ('Consistency = standard deviation of per-game values (FG% / FT% / 3P%: of per-game '
                'percentages), so lower is steadier. Not coloured; sorted high to low. Click a header to sort, '
                'a row for detail.')
    parts = [f'Colour = percentile among free agents with {g}+ games in this window, per column (TO and PF '
             'inverted, so green is good). FG% / FT% / 3P% are coloured and sorted by volume-weighted impact.',
             'Value = mean percentile across the 12 league categories.' if mode == 'ranked' else
             'Fit = mean percentile across the ticked categories.',
             f'Fewer than {g} games: dimmed and listed after everyone else. Click a header to sort, a row for '
             'detail.']
    return ' '.join(parts)


####################################################################################################
# 004 - PLAYER DRAWER
####################################################################################################

def _per_game_totals(d):
    """Free-agent rows -> the totals frame team_performance's category helpers expect."""
    tot = d.rename(columns={'points_scored': 'points'}).groupby('slug')[tp.STAT_COLS].sum()
    tot['gp'] = d.groupby('slug').size()
    return tot


def weakest_rostered(league, comp_window, roles):
    """(position, name, z-score total) of my weakest rostered player at one of `roles`, or overall."""
    games = tp.window_games(league, comp_window)
    if games.empty:
        return None
    z = tp.zscores(tp.player_totals(games))['TOTAL']
    best = None
    if league == 'ESPN' and roles and not tp.ESPN_POSITIONS.empty:
        roster_roles = {n: (r or set()) for n, r in zip(tp.ESPN_POSITIONS['name'], tp.ESPN_POSITIONS['roles'])}
        for pos in roles:
            cands = z[[n for n in z.index if pos in roster_roles.get(n, set())]]
            if not cands.empty and (best is None or cands.min() < best[2]):
                best = (pos, cands.idxmin(), float(cands.min()))
    if best is None:
        best = (None, z.idxmin(), float(z.min()))
    return best, games


def comparison(league, window, slug, name):
    comp_window = window if window in CURRENT_WINDOWS else 'season'
    found = weakest_rostered(league, comp_window, roles_of(name))
    d = window_frame(league, comp_window)
    d = d[d['slug'] == slug]
    if not found or d.empty:
        return html.Div(f'No games for him or your roster in the {WINDOW_TEXT[comp_window]} to compare.',
                        className='fa-muted fa-small')
    (pos, mine, _z), games = found
    fa_tot = _per_game_totals(d).iloc[0]
    my_tot = tp.player_totals(games[games['name'] == mine]).iloc[0]
    rows, wins = [], 0
    for lab in LEAGUE_CATS:
        a = tp.category_value(fa_tot.to_frame().T, lab).iloc[0]
        b = tp.category_value(my_tot.to_frame().T, lab).iloc[0]
        if pd.isna(a) or pd.isna(b):
            diff_cell = html.Span('–', className='fa-muted')
        else:
            diff = a - b
            good = diff < 0 if lab in INVERT else diff > 0
            wins += bool(good)
            txt = (f'{diff:+.3f}'.replace('0.', '.') if lab.endswith('%') else f'{diff:+.1f}')
            diff_cell = html.Span(txt, className='pr-up' if good else ('pr-down' if diff != 0 else 'fa-muted'))
        rows.append(html.Tr([html.Td(lab, className='fa-left fa-muted'), html.Td(tp.fmt(lab, a)),
                             html.Td(tp.fmt(lab, b), className='fa-muted'), html.Td(diff_cell)]))
    title = f"vs. your weakest {pos} ({mine})" if pos else f'vs. your weakest player ({mine})'
    return html.Div([
        html.Div(title, className='fa-drawer-h'),
        html.Div(f'Per game, {WINDOW_TEXT[comp_window]}. Weakest = lowest total category value '
                 f'on your {league} roster.', className='fa-muted fa-small'),
        html.Table([html.Thead(html.Tr([html.Th('', className='fa-left'), html.Th('Him'), html.Th('Yours'),
                                        html.Th('Diff')])), html.Tbody(rows)], className='tp-table fa-compare'),
        html.Div(['Categories he wins: ', html.B(f'{wins} of {len(LEAGUE_CATS)}')], className='fa-wins'),
    ])


def fig_last_games(league, slug):
    d = FA.get(league, FA['ESPN'])
    d = d[d['slug'] == slug]
    cur = d[d['current']]
    d = (cur if not cur.empty else d).tail(10)
    fig = go.Figure()
    x = [f'{t.month}/{t.day}' for t in d['date']]
    fig.add_trace(go.Bar(x=x, y=d['minutes_played'], name='Minutes', marker_color='#2f3b55',
                         hovertemplate='%{x}: %{y:.0f} min<extra></extra>'))
    fig.add_trace(go.Scatter(x=x, y=d['points_scored'], name='Points', mode='lines+markers',
                             line=dict(color=tp.ACC, width=2), marker=dict(size=5),
                             hovertemplate='%{x}: %{y:.0f} pts<extra></extra>'))
    fig = tp.style_fig(fig, 170, dict(l=28, r=6, t=8, b=28))
    fig.update_layout(bargap=0.35)
    fig.update_xaxes(showgrid=False, tickfont=dict(size=10), type='category', tickangle=0)
    fig.update_yaxes(tickfont=dict(size=10), rangemode='tozero')
    return fig


def drawer(league, window, out, slug):
    if out is None or slug not in out.index:
        return html.Div('Click a player in the table to see his last 10 games and how he compares with your roster.',
                        className='tp-empty')
    r = out.loc[slug]
    name = r['name']
    d = FA[league][FA[league]['slug'] == slug]
    team = team_name(d['team'].iloc[-1]) if not d.empty else ''
    info = injury_info(slug)
    status = info[0] if info else 'Healthy'
    meta = ' · '.join(x for x in ['/'.join(roles_of(name)) or None, team or None, status] if x)
    trend = r['trend']
    mpg_line = f"{r['mpg']:.1f} MPG in the {WINDOW_TEXT[window]}" + (
        f" · last 3 games {r['mpg'] + trend:.1f}" if window in CURRENT_WINDOWS and pd.notna(trend) else '')
    parts = [html.Div([html.Span(name, className='fa-drawer-name'), injury_chip(info)], className='fa-drawer-top'),
             html.Div(meta, className='fa-muted fa-small'), html.Div(mpg_line, className='fa-small')]
    if info and info[1]:
        o = info[1]
        parts.append(html.Div(
            f"{tp.curve_label(o['group'])}, day {o['days_out']} · {o['back_7']:.0%} back within 7 days, "
            f"{o['back_14']:.0%} within 14", className='fa-injury-line'))
    parts.append(html.Div('Last 10 games · bars = minutes, line = points', className='fa-drawer-h'))
    parts.append(dcc.Graph(figure=fig_last_games(league, slug), config=tp.GRAPH_CONFIG))
    if 'p_PTS' in out.columns:
        pct = pd.Series({lab: r[f'p_{lab}'] for lab in LEAGUE_CATS}).dropna().sort_values(ascending=False)
        if not pct.empty:
            best = ', '.join(f'{lab} {p:.0f}' for lab, p in pct.head(3).items())
            parts.append(html.Div(['Best categories (percentile): ', html.B(best)], className='fa-small fa-best'))
    parts.append(comparison(league, window, slug, name))
    return html.Div(parts)


####################################################################################################
# 005 - LAYOUT
####################################################################################################

def _seg(component_id, options, value):
    return dcc.RadioItems(id=component_id, value=value, inline=True, className='tp-segmented fa-seg',
                          options=[{'label': lab, 'value': val} for val, lab in options])


def _block(label, component):
    return html.Div([html.Span(label, className='fa-bar-label'), component], className='fa-bar-block')


def filter_bar(style):
    calc_options = [{'label': html.Span(lab, title=tip), 'value': val} for val, lab, tip in CALCS]
    columns_menu = html.Details([
        html.Summary('Columns'),
        html.Div([
            dcc.Checklist(id='fa-cols', value=DEFAULT_COLS, className='fa-col-list',
                          options=[{'label': f'{lab} · {NAMES.get(lab, lab)}', 'value': lab} for lab in COLS]),
            html.Div([html.Span('Rows', className='fa-bar-label'),
                      dcc.Input(id='fa-rows', type='number', min=5, max=100, step=5, value=DEFAULT_ROWS,
                                className='fa-rows', debounce=True)], className='fa-rows-line'),
        ], className='fa-menu-panel'),
    ], className='fa-menu')
    return html.Div([html.Div([html.Div([
        _block('League', _seg('fa-league', [('ESPN', 'ESPN'), ('Yahoo', 'Yahoo')], 'ESPN')),
        _block('Window', _seg('fa-window', WINDOWS, '14')),
        _block('Stat', dcc.RadioItems(id='fa-calc', value='weights', inline=True, className='tp-segmented fa-seg',
                                      options=calc_options)),
        _block('View', _seg('fa-mode', [('ranked', 'Ranked'), ('needs', 'My needs')], 'ranked')),
        _block('Injured', _seg('fa-injured', [('all', 'Show'), ('healthy', 'Hide'), ('only', 'Only')], 'all')),
        _block('', columns_menu),
        _block('', dcc.Dropdown(id='fa-hide', multi=True, placeholder='Hide players…', className='fa-hide')),
    ], className='fa-bar')], className='col-12', style=style)], className='row sticky-top fa-sticky')


def body():
    needs_row = html.Div([
        html.Span('Rank by:', className='fa-bar-label'),
        dcc.Checklist(id='fa-needs', options=[{'label': lab, 'value': lab} for lab in LEAGUE_CATS],
                      value=NEEDS['ESPN'], inline=True, className='fa-chips'),
        html.Span(id='fa-needs-sub', className='fa-muted fa-small'),
    ], id='fa-needs-row', className='fa-needs-row', style={'display': 'none'})
    odds_n = len(ODDS)
    return html.Div([
        tp._section('Free agent screener', html.Span(id='fa-meta')),
        html.Div([
            html.Div(tp._card('', html.Div([needs_row, html.Div(id='fa-table')]),
                              sub='', accent=True, title_id='fa-table-title', sub_id='fa-caption'),
                     className='col-xl-9 col-12'),
            html.Div(tp._card('Player detail', html.Div(id='fa-drawer')), className='col-xl-3 col-12 fa-drawer-col'),
        ], className='row'),
        html.Details([
            html.Summary(f'Full injury outlook · {odds_n} injured ESPN free agent{"s" if odds_n != 1 else ""}'),
            tp._card('Injured free agents', tp.injured_free_agents(ODDS),
                     sub='ESPN free agents currently out, from a survival curve fitted to their own injury details. '
                         'Days are in-season days.'),
        ], className='fa-outlook'),
        dcc.Store(id='fa-sort'),
        dcc.Store(id='fa-selected'),
    ], className='tp-container fa-page')


####################################################################################################
# 006 - CALLBACKS
####################################################################################################

@app_inst.callback(
    Output('fa-needs', 'value'), Output('fa-hide', 'options'), Output('fa-hide', 'value'),
    Input('fa-league', 'value'),
)
def on_league(league):
    names = NAME.get(league, {})
    options = [{'label': n, 'value': s} for s, n in sorted(names.items(), key=lambda kv: kv[1].lower())]
    return NEEDS.get(league) or ['PTS', 'REB', 'AST'], options, []


@app_inst.callback(
    Output('fa-sort', 'data'),
    Input({'type': 'fa-sort', 'index': ALL}, 'n_clicks'), Input('fa-mode', 'value'), Input('fa-calc', 'value'),
    prevent_initial_call=True,
)
def set_sort(_clicks, _mode, _calc):
    """A header click sorts by that column; changing the view or stat type goes back to the default.
    Re-rendered headers arrive with n_clicks=0 and are ignored."""
    trigger = ctx.triggered_id
    if isinstance(trigger, dict):
        if not ctx.triggered or not ctx.triggered[0]['value']:
            raise PreventUpdate
        return trigger['index']
    return None


@app_inst.callback(
    Output('fa-selected', 'data'),
    Input({'type': 'fa-row', 'index': ALL}, 'n_clicks'),
    prevent_initial_call=True,
)
def select_row(_clicks):
    trigger = ctx.triggered_id
    if not isinstance(trigger, dict) or not ctx.triggered or not ctx.triggered[0]['value']:
        raise PreventUpdate
    return trigger['index']


@app_inst.callback(
    Output('fa-table', 'children'), Output('fa-table-title', 'children'), Output('fa-caption', 'children'),
    Output('fa-drawer', 'children'), Output('fa-meta', 'children'),
    Output('fa-needs-row', 'style'), Output('fa-needs-sub', 'children'),
    Input('fa-league', 'value'), Input('fa-window', 'value'), Input('fa-calc', 'value'), Input('fa-mode', 'value'),
    Input('fa-cols', 'value'), Input('fa-rows', 'value'), Input('fa-hide', 'value'), Input('fa-injured', 'value'),
    Input('fa-needs', 'value'), Input('fa-sort', 'data'), Input('fa-selected', 'data'),
)
def update_screener(league, window, calc, mode, cols, n_rows, hide, injured, needs, sort_key, selected):
    needs = [c for c in (needs or []) if c in COLS]
    n_rows = max(1, int(n_rows)) if n_rows else DEFAULT_ROWS
    all_fa = FA.get(league, pd.DataFrame())
    last_box = f"box scores through {tp._fmt_day(all_fa['date'].max())}" if not all_fa.empty else 'no box scores'
    meta = f"{len(NAME.get(league, {}))} {league} free agents · {last_box}" + (
        f" · ESPN injury status as of {tp._fmt_day(SNAPSHOT)}" if SNAPSHOT is not None else '')
    needs_style = {'display': 'flex'} if mode == 'needs' and calc != 'std' else {'display': 'none'}
    my_needs = NEEDS.get(league)
    needs_sub = (f"Pre-ticked: your {league} roster's weakest categories vs league rotation players this season "
                 f"({', '.join(my_needs)})" if my_needs else f'No {league} roster games yet to suggest categories')

    out, message = screen(league, window, calc, needs, hide, injured)
    calc_label = next(lab for val, lab, _ in CALCS if val == calc)
    title = f"{'My needs' if mode == 'needs' and calc != 'std' else 'Ranked free agents'} · {calc_label.lower()}, " \
            f"{WINDOW_TEXT[window]}"
    if out is None:
        return (html.Div(message, className='tp-empty'), title, '', drawer(league, window, None, None), meta,
                needs_style, needs_sub)

    if mode == 'needs' and calc != 'std':
        show_cols = needs or [c for c in DEFAULT_COLS if c in (cols or [])]
    else:
        show_cols = [c for c in COLS if c in (cols or DEFAULT_COLS)]
    valid = set(show_cols) | {'GP', 'MPG'} | ({'Value'} if mode == 'ranked' and calc != 'std' else set()) | \
        ({'Fit'} if mode == 'needs' and calc != 'std' and needs else set())
    key = sort_key if sort_key in valid else default_sort(mode, calc)
    if key == 'Fit' and not needs:
        key = 'Value' if calc != 'std' else 'PTS'
    if key not in valid and key in COLS:
        key = show_cols[0] if show_cols else 'MPG'
    out = sort_frame(out, key, calc)
    if selected not in out.index:
        selected = out.index[0]
    return (table(out, show_cols, key, selected, mode, calc, window, n_rows), title, caption(calc, window, mode),
            drawer(league, window, out, selected), meta, needs_style, needs_sub)
