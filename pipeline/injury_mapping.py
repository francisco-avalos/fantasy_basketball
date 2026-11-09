"""
injury_mapping.py
-----------------
Build injury episodes from basketball.hist_player_inj and load them into
basketball.player_injury_cycles. Replaces the SQL procedure
basketball.health_cycle_backfill_proc (archived/sql_files/Injury_table_setup_backfill.sql).

    hist_player_inj ──┐
    historical_player_data (box scores) ──┼──> episodes ──> player_injury_cycles
    injury_note_classification ───────────┘
                      ▲
          regex (shared/injury_taxonomy.py), then Claude for the rest

What an episode is
------------------
An episode opens on an "out" row (relinquished: placed on IL, ruled out, DTD,
personal reasons, suspension ...) when the player isn't already out. It closes at
the earliest of:
  * an activation row ("activated from IL", "returned to lineup", "reinstated
    from suspension")                                      -> event, 'activation'
  * the player's first game with minutes after the out date, from box scores.
    The transaction log often never records the return; a box score is proof he
    was back                                              -> event, 'box_score'
A second out row while the episode is open (no game in between):
  * same body region, a vaguer note, or an update ("sprained ankle (DTD)" ->
    "placed on IL with sprained ankle")                   -> same episode
  * a different body region / illness / non-medical reason -> the open episode
    is censored that day ('concurrent_injury': we can no longer see when that
    injury alone would have healed) and a new episode opens, flagged concurrent
  * if league box scores are missing for part of the gap, we can't tell whether
    he played: the open episode is censored at the start of the hole ('data_gap')
Never closed: censored at the end of the data ('open'). Any episode still open
after the end of the season following the one it started in is censored there
('max_follow_up'), so a retirement or a move overseas isn't read as an injury.
A generic first note ("placed on IL") takes the label of a detailed note that
arrives within LABEL_GRACE_DAYS.

Clock: in-season days from season_dates.csv (shared/season_calendar.py). Labels
come from the FIRST note, because that is all you know on day one.

Classification: every out note is normalized to a note_key and looked up in
basketball.injury_note_classification. New keys are classified by regex; keys
the regex can't read unambiguously go to Claude (LLM_MODEL) with a strict JSON
schema. LLM answers are cached in LLM_CACHE so a dry run never pays twice.

Run from the repo root (env: basketball-env-useme-v11052026, which has anthropic):
    python -m pipeline.injury_mapping --dry-run      # build + CSVs in tmp_data/, no DB writes
    python -m pipeline.injury_mapping                # build + load
    python -m pipeline.injury_mapping --no-llm       # regex only; unreadable keys stay 'pending'
    python -m pipeline.injury_mapping --audit 200    # also have Claude label 200 regex keys and report agreement
"""

import argparse
import datetime as dt
import json
import os
import re

import numpy as np
import pandas as pd
import mysql.connector as mysql
from unidecode import unidecode

from shared import season_calendar as cal
from shared.injury_taxonomy import (TAXONOMY_VERSION, CATEGORIES, BODY_REGIONS, INJURY_TYPES,
                                    NON_MEDICAL_REASONS, note_key, note_flags, regex_classify,
                                    severity_tier, curve_group)

config = {
    'host': os.environ.get('sports_db_admin_host'),
    'database': 'basketball',
    'user': os.environ.get('sports_db_admin_user'),
    'password': os.environ.get('sports_db_admin_pw'),
    'port': os.environ.get('sports_db_admin_port'),
}

TMP = '/Users/franciscoavalosjr/Desktop/basketball-folder/tmp_data/'
LLM_CACHE = TMP + 'injury_note_llm_cache.json'
LLM_MODEL = 'claude-opus-5-5'
LLM_BATCH = 40
LABEL_GRACE_DAYS = 3
SHUTDOWN_WINDOW_DAYS = 14
HOLE_MIN_DAYS = 8            # league-wide in-season run with no box scores (All-Star break is shorter)
CLS_FIELDS = ['category', 'body_region', 'body_part', 'injury_type', 'non_medical_reason', 'is_surgery']

CYCLE_COLUMNS = [
    'player_key', 'start_date', 'seq', 'slug', 'player_name', 'end_date', 'start_team', 'end_team',
    'event', 'end_reason', 'calendar_days', 'inseason_days', 'first_note', 'note_key', 'all_notes', 'n_notes',
    'category', 'body_region', 'body_part', 'injury_type', 'non_medical_reason', 'side', 'is_surgery',
    'is_dtd', 'out_for_season', 'out_indefinitely', 'stated_days', 'later_surgery', 'later_out_for_season',
    'severity_tier', 'curve_group', 'concurrent', 'start_offseason', 'crossed_offseason', 'shutdown_suspect',
    'season', 'era', 'age_at_start', 'prior_episodes', 'prior_same_region_365', 'prior_inseason_days_365',
    'days_since_prior_return', 'fit_eligible', 'built_at',
]
CLS_COLUMNS = ['note_key', 'example_note', 'n_rows'] + CLS_FIELDS + [
    'source', 'model_version', 'confidence', 'llm_regex_agree', 'reviewed', 'classified_at']

ACTIVATION = re.compile(r'activated|returned to lineup|reinstated', re.I)
SKIP_OUT = re.compile(r'\bDNP\b|fined|head coach|assistant coach', re.I)   # DNP = single game sat, not an absence


def era_of(season):
    return '2000-05' if season <= 2005 else '2006-14' if season <= 2014 else '2015-20' if season <= 2020 else '2021+'


# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------

def fetch(cursor, query):
    cursor.execute(query)
    return pd.DataFrame(cursor.fetchall(), columns=cursor.column_names)


def load(connection):
    cur = connection.cursor()
    hist = fetch(cur, 'SELECT day, team, acquired, relinquished, notes FROM basketball.hist_player_inj')
    games = fetch(cur, 'SELECT slug, name, date FROM basketball.historical_player_data WHERE seconds_played > 0')
    births = fetch(cur, 'SELECT bbrefid AS slug, bday FROM basketball.master_names_list_temp')
    births2 = fetch(cur, 'SELECT BBRefID AS slug, BBRefBirthDate AS bday FROM basketball.basketball_references_players')
    try:
        cls = fetch(cur, 'SELECT * FROM basketball.injury_note_classification')
    except mysql.errors.ProgrammingError:
        print('injury_note_classification does not exist yet (run the 2026-11-08 migration); starting empty')
        cls = pd.DataFrame(columns=CLS_COLUMNS)
    cur.close()

    hist['day'] = pd.to_datetime(hist['day'], errors='coerce')
    hist = hist.dropna(subset=['day'])
    first_season = min(s for s, _ in cal._calendar()[4].values())
    early = hist['day'] < first_season       # 1999-00 rows: no season dates, no box scores to confirm returns
    if early.any():
        print(f'dropping {int(early.sum())} transaction rows before {first_season.date()} (first season in season_dates.csv)')
    hist = hist[~early].copy()
    for c in ['team', 'acquired', 'relinquished', 'notes']:
        hist[c] = hist[c].fillna('').astype(str).str.strip().str.strip('"').str.strip()
    games['date'] = pd.to_datetime(games['date'])
    b = pd.concat([births, births2]).dropna()
    b['bday'] = pd.to_datetime(b['bday'], errors='coerce')
    b = b.dropna().drop_duplicates('slug')
    return hist, games, dict(zip(b['slug'], b['bday'])), cls


# ---------------------------------------------------------------------------
# Player identity: prosportstransactions name -> bbref slug
# ---------------------------------------------------------------------------

def name_key(s):
    s = unidecode(str(s)).lower()
    s = re.sub(r"[.'`,]", '', s).replace('-', ' ')
    return ' '.join(t for t in s.split() if t not in {'jr', 'sr', 'ii', 'iii', 'iv'})


def name_variants(raw):
    """'Nene / Nene Hilario' -> both; '(William) Tony Parker' -> 'tony parker' and
    'william tony parker'. Parentheses holding a birth date or Jr./Sr. are dropped
    for matching (they only disambiguate) and used to break ties instead."""
    out = []
    for part in raw.split('/'):
        p = part.strip(' •')
        base = re.sub(r'\(.*?\)', '', p).strip()
        out.append(name_key(base))
        for inside in re.findall(r'\((.*?)\)', p):
            if not re.search(r'\d|jr|sr', inside.lower()):
                out.append(name_key(inside + ' ' + base))
    return [v for v in dict.fromkeys(out) if v]


def map_players(hist, games, births):
    """raw name -> slug, using name variants plus overlap between the player's
    transaction dates and his box-score career. Ambiguous or unmatched -> None."""
    careers = games.groupby(['slug', 'name'])['date'].agg(['min', 'max']).reset_index()
    careers['k'] = careers['name'].map(name_key)
    by_key = {k: g for k, g in careers.groupby('k')}
    people = pd.concat([hist.loc[hist.relinquished != '', ['relinquished', 'day']].rename(columns={'relinquished': 'raw'}),
                        hist.loc[hist.acquired != '', ['acquired', 'day']].rename(columns={'acquired': 'raw'})])
    spans = people.groupby('raw')['day'].agg(['min', 'max'])
    pad = pd.Timedelta(days=400)
    mapping = {}
    for raw, (mn, mx) in spans.iterrows():
        cands = [by_key[v] for v in name_variants(raw) if v in by_key]
        if not cands:
            mapping[raw] = None
            continue
        c = pd.concat(cands)
        c = c[(c['min'] <= mx + pad) & (c['max'] >= mn - pad)]
        slugs = c['slug'].unique()
        if len(slugs) > 1:                           # tie-break on a birth date in the name
            m = re.search(r'b\.\s*(\d{4}-\d{2}-\d{2})', raw)
            if m:
                slugs = [s for s in slugs if str(births.get(s, ''))[:10] == m.group(1)] or slugs
        mapping[raw] = slugs[0] if len(slugs) == 1 else None
    return mapping


def box_score_holes(games):
    """In-season dates inside runs of >= HOLE_MIN_DAYS with no box scores at all."""
    have = set(games['date'].dt.normalize())
    days = pd.date_range(games['date'].min(), games['date'].max(), freq='D')
    in_season = cal.is_in_season(days)
    missing = [d for d, s in zip(days, in_season) if s and d not in have]
    holes, run = set(), []
    for d in missing:
        if run and (d - run[-1]).days > 1:
            if len(run) >= HOLE_MIN_DAYS:
                holes.update(run)
            run = []
        run.append(d)
    if len(run) >= HOLE_MIN_DAYS:
        holes.update(run)
    return holes


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

LLM_SYSTEM = f"""You classify NBA injury-report notes from prosportstransactions.com into a fixed taxonomy.
Each note explains why a player was ruled out, placed on the injured list, or otherwise unavailable.
Notes are lowercased and have side words (left/right) and admin tags removed.

Return one label per input id, using only these values:
- category: one of {CATEGORIES}
    injury = musculoskeletal or trauma; illness = sickness, infection, internal condition, or
    covid / health-and-safety protocols; non_medical = rest, personal/family, suspension,
    team decision, legal; unspecified = no reason given ("undisclosed", "various injuries", "(f)");
    not_absence = not about a player being unavailable (coaches, front office, draft picks, fines).
- body_region: one of {BODY_REGIONS} or "none" (use "none" unless category is injury).
    thigh = hamstring/quadriceps/thigh; lower_leg = calf/achilles/shin; hip_groin = hip, groin,
    adductor, sports hernia, hip pointer; torso = ribs, oblique, abdominal, chest; head = head/face/eye/teeth.
- body_part: short lowercase name of the specific part (e.g. "acl", "meniscus", "hamstring", "big toe"), or "none".
- injury_type: one of {INJURY_TYPES} or "none".
    For injuries pick by severity order: surgery > tear > fracture > dislocation (incl. separated) >
    concussion > sprain > strain > bruise > inflammation (tendinitis, bursitis, fasciitis, swelling) >
    laceration > soreness (sore, spasms, tightness) > unspecified. Illness uses "illness", covid /
    health-and-safety protocols use "covid_protocol". Non-medical uses "none".
- non_medical_reason: one of {NON_MEDICAL_REASONS} or "none" (only for non_medical).
- is_surgery: true if the note mentions surgery or a procedure (including appendectomy, scope).
- confidence: high / medium / low - how sure you are of the category, region and type.
If a note lists several injuries, label the most severe one. Fix obvious typos ("kene" = knee).
"""

LLM_SCHEMA = {
    'type': 'object',
    'properties': {'labels': {'type': 'array', 'items': {
        'type': 'object',
        'properties': {
            'id': {'type': 'integer'},
            'category': {'type': 'string', 'enum': CATEGORIES},
            'body_region': {'type': 'string', 'enum': BODY_REGIONS + ['none']},
            'body_part': {'type': 'string'},
            'injury_type': {'type': 'string', 'enum': INJURY_TYPES + ['none']},
            'non_medical_reason': {'type': 'string', 'enum': NON_MEDICAL_REASONS + ['none']},
            'is_surgery': {'type': 'boolean'},
            'confidence': {'type': 'string', 'enum': ['high', 'medium', 'low']},
        },
        'required': ['id', 'category', 'body_region', 'body_part', 'injury_type', 'non_medical_reason',
                     'is_surgery', 'confidence'],
        'additionalProperties': False,
    }}},
    'required': ['labels'],
    'additionalProperties': False,
}


def load_llm_cache():
    if os.path.exists(LLM_CACHE):
        with open(LLM_CACHE) as f:
            return json.load(f)
    return {}


def save_llm_cache(cache):
    os.makedirs(TMP, exist_ok=True)
    with open(LLM_CACHE, 'w') as f:
        json.dump(cache, f, indent=0, sort_keys=True)


def llm_classify(keys, examples, cache):
    """Label `keys` with Claude, LLM_BATCH per request; results land in `cache`
    (saved after every batch, so an interrupted run resumes without re-paying)."""
    import anthropic
    client = anthropic.Anthropic()
    todo = [k for k in keys if k not in cache]
    print(f'Claude ({LLM_MODEL}): {len(todo)} notes to label in {-(-len(todo) // LLM_BATCH)} requests')
    for i in range(0, len(todo), LLM_BATCH):
        batch = todo[i:i + LLM_BATCH]
        items = [{'id': j, 'note': k, 'raw_example': examples.get(k, k)} for j, k in enumerate(batch)]
        for attempt in range(2):
            resp = client.beta.messages.create(
                model=LLM_MODEL,
                max_tokens=16000,
                system=LLM_SYSTEM,
                messages=[{'role': 'user', 'content': 'Classify these notes:\n' + json.dumps(items)}],
                output_config={'effort': 'medium', 'format': {'type': 'json_schema', 'schema': LLM_SCHEMA}},
                betas=['server-side-fallback-2026-07-01'],
                fallbacks='default',
            )
            if resp.stop_reason == 'refusal':
                print(f'  batch {i // LLM_BATCH + 1}: refused ({resp.stop_details}); left pending')
                break
            text = next((b.text for b in resp.content if b.type == 'text'), '')
            try:
                labels = {lab['id']: lab for lab in json.loads(text)['labels']}
            except (json.JSONDecodeError, KeyError) as e:
                print(f'  batch {i // LLM_BATCH + 1}: unreadable response ({type(e).__name__}); retrying')
                continue
            for j, k in enumerate(batch):
                if j in labels:
                    lab = labels[j]
                    cache[k] = {f: (None if lab[f] == 'none' else lab[f]) for f in
                                ['category', 'body_region', 'body_part', 'injury_type', 'non_medical_reason']}
                    cache[k]['is_surgery'] = int(lab['is_surgery'])
                    cache[k]['confidence'] = lab['confidence']
                    cache[k]['model_version'] = resp.model
            missing = [k for k in batch if k not in cache]
            if not missing:
                break
            batch = missing
            items = [{'id': j, 'note': k, 'raw_example': examples.get(k, k)} for j, k in enumerate(batch)]
        save_llm_cache(cache)
        print(f'  {min(i + LLM_BATCH, len(todo))}/{len(todo)} done')
    return cache


def classify_notes(out_notes, existing, use_llm, audit_n):
    """Return (lookup: note_key -> fields, classification rows to write, audit frame)."""
    keys = out_notes.map(note_key)
    counts = keys.value_counts()
    examples = pd.Series(out_notes.values, index=keys.values)
    examples = examples[~examples.index.duplicated()].to_dict()
    now = dt.datetime.now().replace(microsecond=0)

    rows = {}
    for r in existing.to_dict('records'):
        if r['source'] != 'pending':
            rows[r['note_key']] = dict(r)
    cache = load_llm_cache()
    need_llm = []
    for k in counts.index:
        if k in rows:
            continue
        fields, confident = regex_classify(k)
        if confident:
            rows[k] = dict(fields, note_key=k, source='regex', model_version=f'regex-{TAXONOMY_VERSION}',
                           confidence='high', llm_regex_agree=None, reviewed=0, classified_at=now)
        else:
            need_llm.append(k)
    if need_llm and use_llm:
        llm_classify(need_llm, examples, cache)
    for k in need_llm:
        if k in cache:
            c = cache[k]
            rows[k] = dict({f: c.get(f) for f in CLS_FIELDS}, note_key=k, source='llm',
                           model_version=c.get('model_version', LLM_MODEL), confidence=c.get('confidence'),
                           llm_regex_agree=None, reviewed=0, classified_at=now)
        else:                                       # no LLM: best regex guess, revisited next run
            fields, _ = regex_classify(k)
            if fields['category'] is None:
                fields['category'] = 'unspecified'
            rows[k] = dict(fields, note_key=k, source='pending', model_version=f'regex-{TAXONOMY_VERSION}',
                           confidence='low', llm_regex_agree=None, reviewed=0, classified_at=now)

    audit = pd.DataFrame()
    if audit_n:
        pool = [k for k, r in rows.items() if r['source'] == 'regex' and r.get('llm_regex_agree') is None and k in counts]
        rng = np.random.default_rng(7)
        sample = list(rng.choice(pool, size=min(audit_n, len(pool)), replace=False))
        if use_llm:
            llm_classify(sample, examples, cache)
        recs = []
        for k in sample:
            if k not in cache:
                continue
            r, c = rows[k], cache[k]
            same = {f: (r.get(f) or None) == (c.get(f) or None) for f in ['category', 'body_region', 'injury_type', 'non_medical_reason']}
            rows[k]['llm_regex_agree'] = int(all(same.values()))
            recs.append(dict(note_key=k, n_rows=int(counts[k]), **{f'regex_{f}': r.get(f) for f in same},
                             **{f'llm_{f}': c.get(f) for f in same}, **{f'agree_{f}': v for f, v in same.items()}))
        audit = pd.DataFrame(recs)

    for k, r in rows.items():
        r['n_rows'] = int(counts.get(k, r.get('n_rows') or 0))
        r['example_note'] = examples.get(k, r.get('example_note'))
    lookup = {k: {f: r.get(f) for f in CLS_FIELDS} for k, r in rows.items()}
    return lookup, rows, audit


# ---------------------------------------------------------------------------
# Episodes
# ---------------------------------------------------------------------------

def region_of(fields):
    """What 'the same injury' means when a second out row arrives."""
    cat = fields.get('category')
    if cat == 'injury':
        return fields.get('body_region') or 'injury'
    if cat in ('illness', 'non_medical'):
        return cat if cat == 'illness' else f"nm:{fields.get('non_medical_reason')}"
    return None                                    # unspecified / not_absence: compatible with anything


def build_episodes(hist, slug_map, games, holes, data_end, lookup):
    game_days = {s: np.array(sorted(g['date'].dt.normalize().unique()), dtype='datetime64[ns]')
                 for s, g in games.groupby('slug')}
    hole_days = np.array(sorted(holes), dtype='datetime64[ns]')

    outs = hist[(hist.relinquished != '') & ~hist.notes.str.contains(SKIP_OUT)]
    ins = hist[(hist.acquired != '') & hist.notes.str.contains(ACTIVATION)]
    ev = pd.concat([
        outs.assign(raw=outs.relinquished, kind='out')[['raw', 'day', 'team', 'notes', 'kind']],
        ins.assign(raw=ins.acquired, kind='in')[['raw', 'day', 'team', 'notes', 'kind']],
    ])
    ev['slug'] = ev['raw'].map(slug_map)
    ev['player_key'] = ev['slug'].fillna(ev['raw'])
    ev = ev.sort_values(['player_key', 'day'])

    episodes = []

    def first_after(arr, start, end=None, inclusive_end=False):
        if arr is None or len(arr) == 0:
            return None
        i = np.searchsorted(arr, np.datetime64(start), side='right')
        if i >= len(arr):
            return None
        g = pd.Timestamp(arr[i])
        if end is not None and (g > end or (g == end and not inclusive_end)):
            return None
        return g

    def close(ep, end, event, reason, team=None):
        ep.update(end_date=end, event=event, end_reason=reason, end_team=team or ep['start_team'])
        episodes.append(ep)

    def open_episode(pkey, slug, raw, day, team, note, concurrent=0):
        f = lookup.get(note_key(note), {})
        return {'player_key': pkey, 'slug': slug, 'player_name': raw, 'start_date': day, 'start_team': team,
                'first_note': note, 'notes': [note], 'fields': dict(f), 'flags': note_flags(note),
                'later_surgery': 0, 'later_out_for_season': 0, 'concurrent': concurrent}

    for pkey, g in ev.groupby('player_key', sort=False):
        slug = g['slug'].iloc[0] if isinstance(g['slug'].iloc[0], str) else None
        gd = game_days.get(slug)
        cur = None
        for day, dg in g.groupby('day', sort=True):
            # a game since the open date (and before today's rows) proves he came back
            if cur is not None:
                gm = first_after(gd, cur['start_date'], day, inclusive_end=(dg['kind'] == 'out').any())
                if gm is not None and not (gm == day and (dg['kind'] == 'in').any()):
                    close(cur, gm, 1, 'box_score')
                    cur = None
            kinds = ['in', 'out'] if cur is not None else ['out', 'in']
            for kind in kinds:
                for r in dg[dg['kind'] == kind].itertuples():
                    if kind == 'in':
                        if cur is not None:
                            close(cur, day, 1, 'activation', r.team)
                            cur = None
                        continue
                    if cur is None:
                        cur = open_episode(pkey, slug, r.raw, day, r.team, r.notes)
                        continue
                    if cur['start_date'] == day and r.notes in cur['notes']:
                        continue
                    hole = first_after(hole_days, cur['start_date'], day) if slug else None
                    f_new = lookup.get(note_key(r.notes), {})
                    r_cur, r_new = region_of(cur['fields']), region_of(f_new)
                    if hole is not None:
                        close(cur, hole, 0, 'data_gap')
                        cur = open_episode(pkey, slug, r.raw, day, r.team, r.notes)
                    elif r_cur is None and r_new is not None and (day - cur['start_date']).days <= LABEL_GRACE_DAYS:
                        cur['fields'] = dict(f_new)                       # generic first note, detail follows
                        cur['notes'].append(r.notes)
                    elif r_cur is not None and r_new is not None and r_cur != r_new:
                        close(cur, day, 0, 'concurrent_injury')
                        cur = open_episode(pkey, slug, r.raw, day, r.team, r.notes, concurrent=1)
                    else:
                        cur['notes'].append(r.notes)
                        fl = note_flags(r.notes)
                        cur['later_out_for_season'] |= fl['out_for_season']
                        cur['later_surgery'] |= int(bool(re.search(r'surger|arthroscop', r.notes, re.I)))
        if cur is not None:
            gm = first_after(gd, cur['start_date'])
            if gm is not None:
                close(cur, gm, 1, 'box_score')
            else:
                close(cur, data_end, 0, 'open')
    return episodes


def finish(episodes, births, data_end):
    """Durations, flags, history features and fit eligibility."""
    rows = []
    built = dt.datetime.now().replace(microsecond=0)
    for ep in episodes:
        start, end = pd.Timestamp(ep['start_date']), pd.Timestamp(ep['end_date'])
        season = cal.season_of(start)
        max_end = cal.season_bounds(season + 1)[1] if (season + 1) in cal._calendar()[4] else data_end
        if end > max_end:
            end, ep['event'], ep['end_reason'] = max_end, 0, 'max_follow_up'
        f, fl = ep['fields'], ep['flags']
        crossed = int(ep['event'] == 1 and cal.season_of(end) > season)
        nxt = cal.season_bounds(cal.season_of(end))[0] if crossed else None
        bday = births.get(ep['slug'])
        rows.append({
            'player_key': ep['player_key'], 'start_date': start, 'slug': ep['slug'], 'player_name': ep['player_name'],
            'end_date': end, 'start_team': ep['start_team'], 'end_team': ep['end_team'],
            'event': int(ep['event']), 'end_reason': ep['end_reason'],
            'calendar_days': int((end - start).days), 'inseason_days': int(cal.inseason_days(start, end)),
            'first_note': ep['first_note'][:300], 'note_key': note_key(ep['first_note'])[:300],
            'all_notes': ' | '.join(dict.fromkeys(ep['notes'])), 'n_notes': len(ep['notes']),
            **{k: f.get(k) for k in CLS_FIELDS}, 'side': fl['side'],
            'is_dtd': fl['is_dtd'], 'out_for_season': fl['out_for_season'], 'out_indefinitely': fl['out_indefinitely'],
            'stated_days': fl['stated_days'], 'later_surgery': int(ep['later_surgery']),
            'later_out_for_season': int(ep['later_out_for_season']),
            'severity_tier': severity_tier(f, fl), 'curve_group': curve_group(f) if f.get('category') else 'unspecified',
            'concurrent': ep['concurrent'], 'start_offseason': int(not cal.is_in_season(start)),
            'crossed_offseason': crossed,
            'shutdown_suspect': int(bool(crossed and (end - nxt).days <= SHUTDOWN_WINDOW_DAYS)),
            'season': season, 'era': era_of(season),
            'age_at_start': round((start - bday).days / 365.25, 1) if bday is not None else None,
            'built_at': built,
        })
    df = pd.DataFrame(rows).sort_values(['player_key', 'start_date']).reset_index(drop=True)
    df['is_surgery'] = df['is_surgery'].fillna(0).astype(int)
    df['seq'] = df.groupby(['player_key', 'start_date']).cumcount()

    # history known at the start of each episode (no look-ahead)
    medical = df['category'].isin(['injury', 'illness'])
    prior_n, same_reg, prior_days, since = [], [], [], []
    for _, g in df.groupby('player_key', sort=False):
        hist_rows = []
        for r in g.itertuples():
            past = [h for h in hist_rows if h[0] < r.start_date]
            prior_n.append(sum(1 for h in past if h[3]))
            win = [h for h in past if (r.start_date - h[0]).days <= 365]
            same_reg.append(sum(1 for h in win if h[2] == r.body_region and r.body_region is not None))
            prior_days.append(int(sum(h[4] for h in win if h[3])))
            ends = [h[1] for h in past if h[5] == 1 and h[1] <= r.start_date]
            since.append(int((r.start_date - max(ends)).days) if ends else None)
            hist_rows.append((r.start_date, r.end_date, r.body_region, r.category in ('injury', 'illness'),
                              r.inseason_days, r.event))
    df['prior_episodes'], df['prior_same_region_365'] = prior_n, same_reg
    df['prior_inseason_days_365'], df['days_since_prior_return'] = prior_days, since

    df['fit_eligible'] = (df['slug'].notna() & ~df['category'].isin(['not_absence']) &
                          (df['start_offseason'] == 0) & (df['calendar_days'] > 0)).astype(int)
    return df[CYCLE_COLUMNS]


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------

def py(v):
    if v is None or (isinstance(v, float) and np.isnan(v)) or v is pd.NaT:
        return None
    if isinstance(v, pd.Timestamp):
        return v.to_pydatetime()
    if isinstance(v, np.generic):
        return v.item()
    return v


def write(connection, cycles, cls_rows):
    cur = connection.cursor()
    try:
        cols = ', '.join(f'`{c}`' for c in CLS_COLUMNS)
        marks = ', '.join(['%s'] * len(CLS_COLUMNS))
        upd = ', '.join(f'`{c}`=VALUES(`{c}`)' for c in CLS_FIELDS + ['source', 'model_version', 'confidence', 'classified_at'])
        # reviewed / manual rows keep their labels; everyone gets fresh counts and audit results
        cur.executemany(
            f'INSERT INTO basketball.injury_note_classification ({cols}) VALUES ({marks}) '
            f'ON DUPLICATE KEY UPDATE n_rows=VALUES(n_rows), example_note=VALUES(example_note), '
            f'llm_regex_agree=COALESCE(VALUES(llm_regex_agree), llm_regex_agree), '
            + ', '.join(f"`{c}`=IF(reviewed=1 OR source='manual', `{c}`, VALUES(`{c}`))"
                        for c in CLS_FIELDS + ['source', 'model_version', 'confidence', 'classified_at']),
            [[py(r.get(c)) for c in CLS_COLUMNS] for r in cls_rows.values()])
        cur.execute('DELETE FROM basketball.player_injury_cycles;')
        cols = ', '.join(f'`{c}`' for c in CYCLE_COLUMNS)
        marks = ', '.join(['%s'] * len(CYCLE_COLUMNS))
        data = [[py(v) for v in row] for row in cycles.itertuples(index=False, name=None)]
        for i in range(0, len(data), 2000):
            cur.executemany(f'INSERT INTO basketball.player_injury_cycles ({cols}) VALUES ({marks});', data[i:i + 2000])
        connection.commit()
    except mysql.errors.ProgrammingError as e:
        connection.rollback()
        if e.errno in (1054, 1146):       # unknown column / table: migration not run
            raise SystemExit('Tables are not migrated yet; nothing was changed. Run '
                             'sql_files/migrations/2026-11-08_injury_episodes.sql once, then re-run.')
        raise
    except Exception:
        connection.rollback()
        raise
    finally:
        cur.close()
    print(f'basketball.player_injury_cycles: {len(cycles)} rows; injury_note_classification: {len(cls_rows)} keys')


def summarize(cycles):
    fit = cycles[cycles.fit_eligible == 1]
    print(f'\nepisodes {len(cycles)}  fit-eligible {len(fit)}  events {int(fit.event.sum())}  censored {int((fit.event == 0).sum())}')
    print('end reasons:', cycles.end_reason.value_counts().to_dict())
    print('categories :', fit.category.value_counts(dropna=False).to_dict())
    print('in-season days (fit, events):',
          fit.loc[fit.event == 1, 'inseason_days'].describe(percentiles=[.5, .75, .9, .99]).round(0).to_dict())
    print('largest curve groups:', fit.curve_group.value_counts().head(12).to_dict())


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    ap.add_argument('--dry-run', action='store_true', help='build and write CSVs to tmp_data/; no DB writes')
    ap.add_argument('--no-llm', action='store_true', help='regex only; keys it cannot read stay pending')
    ap.add_argument('--audit', type=int, default=0, help='Claude labels N regex-classified keys; agreement reported')
    args = ap.parse_args()

    connection = mysql.connect(**config)
    try:
        hist, games, births, existing = load(connection)
        data_end = min(hist['day'].max(), games['date'].max())
        slug_map = map_players(hist, games, births)
        mapped = hist['relinquished'].map(slug_map).notna() | hist['acquired'].map(slug_map).notna()
        print(f'player names mapped to a bbref slug: {sum(v is not None for v in slug_map.values())}/{len(slug_map)} '
              f'({mapped.mean():.1%} of transaction rows)')
        holes = box_score_holes(games)
        if holes:
            print(f'box-score holes (league-wide, >= {HOLE_MIN_DAYS} in-season days): '
                  f'{len(holes)} days, e.g. {min(holes).date()} .. {max(holes).date()}')

        outs = hist.loc[(hist.relinquished != '') & ~hist.notes.str.contains(SKIP_OUT), 'notes']
        lookup, cls_rows, audit = classify_notes(outs, existing, use_llm=not args.no_llm, audit_n=args.audit)
        src = pd.Series([r['source'] for r in cls_rows.values()]).value_counts().to_dict()
        print(f'note keys: {len(cls_rows)} by source {src}')
        if len(audit):
            agree = audit[[c for c in audit if c.startswith('agree_')]].mean().round(3).to_dict()
            print(f'audit of {len(audit)} regex keys vs Claude, agreement by field: {agree}')
            print(f'  weighted by rows: {np.average(audit[[c for c in audit if c.startswith("agree_")]].all(axis=1), weights=audit.n_rows):.1%}')
            os.makedirs(TMP, exist_ok=True)
            audit.to_csv(TMP + 'injury_regex_audit.csv', index=False)
            print(f'  full comparison: {TMP}injury_regex_audit.csv')

        episodes = build_episodes(hist, slug_map, games, holes, data_end, lookup)
        cycles = finish(episodes, births, data_end)
        summarize(cycles)

        if args.dry_run:
            os.makedirs(TMP, exist_ok=True)
            cycles.to_csv(TMP + 'injury_episodes_dryrun.csv', index=False)
            pd.DataFrame(list(cls_rows.values()))[CLS_COLUMNS].to_csv(TMP + 'injury_note_classification_dryrun.csv', index=False)
            print(f'\ndry run: wrote {TMP}injury_episodes_dryrun.csv and injury_note_classification_dryrun.csv')
        else:
            write(connection, cycles, cls_rows)
    finally:
        connection.close()


if __name__ == '__main__':
    main()
