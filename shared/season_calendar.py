"""
season_calendar.py
------------------
The NBA in-season clock, built from season_dates.csv at the repo root.

Injury durations are measured in **in-season days**: every calendar day between a
season's start and end counts (game days and off days alike, since recovery goes on
either way), and days outside the season do not. A special window (the 2020 bubble
restart, the 2021 play-in) counts as in-season too.

    clock(date)          cumulative in-season days up to and including `date`;
                         a date outside any season maps to the value of the last
                         in-season day before it, so clock(end) - clock(start)
                         is the in-season duration of [start, end].
    inseason_days(a, b)  clock(b) - clock(a)
    season_of(date)      NBA season (end year) a date belongs to; offseason dates
                         belong to the season that just ended
    season_label(date)   the same season as text, e.g. '2024-25' (historical_player_data.season)
    season_bounds(year)  (start, end) Timestamps of that season; end is the later of the
                         regular-season end and the special window's end (2020 bubble)
    is_in_season(date)

Works on scalars or array-likes, and on pandas 1.3.5 (pipeline) and 2.2.3 (Heroku).
"""

import os
from functools import lru_cache

import numpy as np
import pandas as pd

SEASON_DATES_CSV = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'season_dates.csv')


@lru_cache(maxsize=1)
def _calendar():
    sd = pd.read_csv(SEASON_DATES_CSV, dtype=str)
    windows, seasons = [], []
    for _, r in sd.iterrows():
        start, end = pd.to_datetime(r['start']), pd.to_datetime(r['end'])
        label, last_day = end.year, end
        windows.append((start, end))
        if isinstance(r.get('special_start'), str) and r['special_start'].strip():
            windows.append((pd.to_datetime(r['special_start']), pd.to_datetime(r['special_end'])))
            last_day = max(end, pd.to_datetime(r['special_end']))
        seasons.append((label, start, last_day))
    seasons.sort()
    first = min(s for s, _ in windows) - pd.Timedelta(days=1)
    last = max(e for _, e in windows) + pd.Timedelta(days=400)   # room for open episodes
    days = pd.date_range(first, last, freq='D')
    in_season = np.zeros(len(days), dtype=bool)
    for s, e in windows:
        in_season |= (days >= s) & (days <= e)
    cum = np.cumsum(in_season)
    # season label per day: season whose start <= day, carried through the offseason
    starts = np.array([s for _, s, _ in seasons], dtype='datetime64[ns]')
    labels = np.array([y for y, _, _ in seasons])
    idx = np.searchsorted(starts, days.values, side='right') - 1
    season = np.where(idx >= 0, labels[np.clip(idx, 0, None)], labels[0] - 1)
    return days, in_season, cum, season, {y: (s, e) for y, s, e in seasons}


def _index(dates):
    days = _calendar()[0]
    d = pd.to_datetime(pd.Series(dates) if np.ndim(dates) else pd.Series([dates])).dt.normalize()
    i = ((d - days[0]).dt.days).to_numpy()
    if np.isnan(i.astype(float)).any() or (i < 0).any() or (i >= len(days)).any():
        bad = d[(np.isnan(i.astype(float))) | (i < 0) | (i >= len(days))].head(3).tolist()
        raise ValueError(f'dates outside season_dates.csv coverage: {bad}')
    return i.astype(int), np.ndim(dates) == 0


def clock(dates):
    i, scalar = _index(dates)
    out = _calendar()[2][i]
    return int(out[0]) if scalar else out


def inseason_days(start, end):
    return clock(end) - clock(start)


def is_in_season(dates):
    i, scalar = _index(dates)
    out = _calendar()[1][i]
    return bool(out[0]) if scalar else out


def season_of(dates):
    i, scalar = _index(dates)
    out = _calendar()[3][i]
    return int(out[0]) if scalar else out


def season_bounds(season_end_year):
    return _calendar()[4][int(season_end_year)]


def season_label(dates):
    """'2024-25' style label of season_of(dates); the 2020 bubble and 2021 play-in
    windows belong to the season they finished ('2019-20', '2020-21')."""
    end = season_of(dates)
    fmt = lambda e: f'{int(e) - 1}-{str(int(e))[-2:]}'
    return fmt(end) if np.ndim(end) == 0 else np.array([fmt(e) for e in end])
