"""
injury_taxonomy.py
------------------
One fixed vocabulary for prosportstransactions injury notes, shared by the
pipeline (pipeline/injury_mapping.py, pipeline/injury_probabilities_basketball.py)
and the app (app/team_performance.py) so a note is classified the same way
everywhere.

    note_key(raw)        normalized note: lowercase, side words and admin tags
                         ("placed on IL with", "(DTD)", "(out for season)", ...)
                         removed. Key of basketball.injury_note_classification.
    note_flags(raw)      what the raw note says beyond the injury itself: side,
                         DTD, out for season, out indefinitely, a stated timeline
    regex_classify(key)  deterministic classification for the common patterns;
                         returns (fields, confident). Not-confident keys go to the
                         LLM in pipeline/injury_mapping.py.
    severity_tier(...)   1 minor / 2 moderate / 3 major, from type + flags
    curve_group(fields)  the group a survival curve is fitted for, e.g.
                         'knee:sprain', 'illness:illness', 'non_medical:rest'

Classification fields: category, body_region, body_part, injury_type,
non_medical_reason, is_surgery. Severity flags come from the raw note, never
from the lookup table, so "(out for season)" on one row can't leak to another.
Side is recorded but not used for grouping: left and right heal the same
(identical medians for ankle, knee, hamstring and calf).

Pure Python (re only), so it runs on Heroku.
"""

import re

TAXONOMY_VERSION = 'v1'

CATEGORIES = ['injury', 'illness', 'non_medical', 'unspecified', 'not_absence']
BODY_REGIONS = ['head', 'neck', 'shoulder', 'arm', 'hand_wrist', 'back', 'torso', 'hip_groin',
                'thigh', 'knee', 'lower_leg', 'ankle', 'foot']
INJURY_TYPES = ['surgery', 'tear', 'fracture', 'dislocation', 'concussion', 'sprain', 'strain',
                'bruise', 'inflammation', 'soreness', 'laceration', 'unspecified',
                'illness', 'covid_protocol']
REGION_LABELS = {'head': 'Head / face', 'neck': 'Neck', 'shoulder': 'Shoulder', 'arm': 'Arm / elbow',
                 'hand_wrist': 'Hand / wrist', 'back': 'Back', 'torso': 'Torso / ribs', 'hip_groin': 'Hip / groin',
                 'thigh': 'Thigh (hamstring, quad)', 'knee': 'Knee', 'lower_leg': 'Lower leg (calf, Achilles)',
                 'ankle': 'Ankle', 'foot': 'Foot / toe', 'unknown': 'Unknown body part'}
NON_MEDICAL_REASONS = ['rest', 'personal', 'suspension', 'team_decision', 'legal', 'other']

# (pattern, body_part, body_region) - most specific first
_BODY = [
    (r'\bacl\b|anterior cruciate', 'acl', 'knee'), (r'\bmcl\b|medial collateral', 'mcl', 'knee'),
    (r'\b[lp]cl\b', 'knee ligament', 'knee'), (r'menisc|menuscus', 'meniscus', 'knee'),
    (r'patell|kneecap', 'patellar tendon', 'knee'), (r'\bknees?\b', 'knee', 'knee'),
    (r'achilles', 'achilles', 'lower_leg'), (r'\bcalf|calves', 'calf', 'lower_leg'),
    (r'\bshin|tibia|fibula|lower leg', 'lower leg', 'lower_leg'),
    (r'ankle', 'ankle', 'ankle'),
    (r'plantar', 'plantar fascia', 'foot'), (r'\bheel', 'heel', 'foot'), (r'\btoes?\b', 'toe', 'foot'),
    (r'\bfoot|\bfeet|lisfranc|metatars|navicular|\barch\b', 'foot', 'foot'),
    (r'hamstring', 'hamstring', 'thigh'), (r'quad', 'quadriceps', 'thigh'), (r'thigh', 'thigh', 'thigh'),
    (r'groin|adductor', 'groin', 'hip_groin'), (r'\bhip|glute|pelvi|tailbone|coccyx|sacroil', 'hip', 'hip_groin'),
    (r'\bback\b|spine|spinal|lumbar|\bdisc\b|herniat|sciatic', 'back', 'back'), (r'\bneck|cervical', 'neck', 'neck'),
    (r'\bribs?\b|oblique|abdom|\bchest|sternum|\bcore\b|pectoral|\babs?\b|intercostal', 'torso', 'torso'),
    (r'shoulder|labrum|rotator|clavicle|collarbone|\bac joint', 'shoulder', 'shoulder'),
    (r'\belbow', 'elbow', 'arm'), (r'bicep|tricep|forearm|\barm\b', 'arm', 'arm'),
    (r'wrist', 'wrist', 'hand_wrist'), (r'thumb', 'thumb', 'hand_wrist'),
    (r'finger|pinky|knuckle', 'finger', 'hand_wrist'), (r'\bhand\b', 'hand', 'hand_wrist'),
    (r'concussion|\bhead\b', 'head', 'head'),
    (r'\beyes?\b|eyelid|orbital|\bnose\b|nasal|\bface\b|facial|\bjaw\b|cheek|tooth|teeth|dental|\blip\b|\bear\b',
     'face', 'head'),
    (r'\blegs?\b', 'leg', 'lower_leg'),
]
# (pattern, injury_type) - checked in this order, so "surgery to repair torn acl" is surgery
_TYPES = [
    (r'surger|arthroscop|\bprocedure|operation|\bscope\b', 'surgery'),
    (r'\btorn\b|\btear|ruptur', 'tear'),
    (r'fractur|broken|\bbreak|stress reaction|cracked', 'fracture'),
    (r'disloc|sublux|separat', 'dislocation'),
    (r'concussion', 'concussion'),
    (r'sprain|hyperext', 'sprain'),
    (r'strain|pulled', 'strain'),
    (r'bruis|contusion', 'bruise'),
    (r'tendin|tendon|bursitis|inflam|synovitis|fasciitis|impinge|effusion|swelling|\bspur', 'inflammation'),
    (r'lacerat|\bcut\b|stitches', 'laceration'),
    (r'spasm|tight|stiff|sore', 'soreness'),
    (r'injur|\bpain\b|discomfort|irritation', 'unspecified'),
]
_COVID = r'covid|health and safety|protocol|coronavirus'
_ILLNESS = (r'illness|\bill\b|\bflu\b|influenza|virus|viral|gastro|stomach|\bsick|infect|pneumonia|strep|'
            r'migraine|headache|dehydrat|\bcold\b|fever|food poisoning|\bmono|bronchitis|appendic|'
            r'respiratory|sinus|tonsil|vertigo|nausea|blood clot|kidney|heart|cardiac|asthma|allerg')
_NON_MEDICAL = [
    (r'suspen', 'suspension'),
    (r'\brest\b|load management|maintenance', 'rest'),
    (r'personal|family|paternity|birth of|bereave|death|funeral|wedding|religious', 'personal'),
    (r'not with team|team decision|coach.?s decision|conditioning|g.?league|assignment|inactive|ineligible|'
     r'trade|waive|contract|holdout|left team|sent home|sent back', 'team_decision'),
    (r'visa|immigra|legal|court|arrest|jail|pleaded|charge|guilty', 'legal'),
]
_NOT_ABSENCE = r'draft pick|head coach|assistant coach|\bcoach\b.*surgery|salary cap|forfeit|front office|\bowner\b'

_ADMIN_TAGS = re.compile(
    r'\((?:dtd|dnp|p|cbc|date approximate|out for season|out indefinitely|out indefinteily|'
    r'out [^)]*?(?:week|month|day)s?[^)]*|[^)]*\bgames?\b[^)]*|missed practice)\)', re.I)


def note_key(raw):
    """Normalized note used as the classification lookup key."""
    s = str(raw or '').strip().strip('"').lower()
    s = _ADMIN_TAGS.sub(' ', s)
    s = re.sub(r'^\s*placed on (?:the )?i[lr]\b\s*(?:with|for|recovering from|after)?\s*', '', s)
    s = re.sub(r'\b(?:left|right)\b', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip(' .,;:-')
    return s or 'placed on il'


def note_flags(raw):
    s = str(raw or '').lower()
    m = re.search(r'\(out (\d+)(?:\s*-\s*(\d+))?\s*(day|week|month)s?\)', s)
    stated = None
    if m:
        lo = float(m.group(1)); hi = float(m.group(2) or lo)
        stated = int(round((lo + hi) / 2 * {'day': 1, 'week': 7, 'month': 30}[m.group(3)]))
    side = ('both' if re.search(r'\bleft\b', s) and re.search(r'\bright\b', s) else
            'left' if re.search(r'\bleft\b', s) else 'right' if re.search(r'\bright\b', s) else None)
    return {
        'side': side,
        'is_dtd': int('(dtd)' in s),
        'out_for_season': int('out for season' in s),
        'out_indefinitely': int(bool(re.search(r'out indefin', s))),
        'stated_days': stated,
    }


def _empty():
    return {'category': None, 'body_region': None, 'body_part': None, 'injury_type': None,
            'non_medical_reason': None, 'is_surgery': 0}


def regex_classify(key):
    """(fields, confident). Confident means one unambiguous reading, so the LLM is skipped."""
    k = key or 'placed on il'
    f = _empty()
    if k in ('placed on il', 'placed on ir', 'il', 'injured'):
        f['category'] = 'unspecified'
        return f, True
    if re.search(_NOT_ABSENCE, k):
        f['category'] = 'not_absence'
        return f, False                       # let the LLM confirm these
    if re.search(r'suspen', k):              # incident text ("for throwing elbow") is not an injury
        f.update(category='non_medical', non_medical_reason='suspension')
        return f, True
    if re.search(r'arrest|pleaded|\bjail|\bcourt\b|\bcharges?\b|guilty|visa|immigra', k) and not re.search(_ILLNESS, k):
        f.update(category='non_medical', non_medical_reason='legal')
        return f, True
    multi = bool(re.search(r'/| and |&|,', re.sub(r'health and safety', '', k)))
    bodies = []
    for pat, part, region in _BODY:
        if re.search(pat, k) and region not in [r for _, r in bodies]:
            bodies.append((part, region))
    nm = [reason for pat, reason in _NON_MEDICAL if re.search(pat, k)]
    if re.search(_COVID, k) and not bodies:
        f.update(category='illness', injury_type='covid_protocol')
        return f, not multi
    if re.search(_ILLNESS, k) and not bodies:
        f.update(category='illness', injury_type='illness')
        return f, not multi and not nm
    if nm and not bodies:
        f.update(category='non_medical', non_medical_reason=nm[0])
        return f, len(set(nm)) == 1 and not multi
    typ = next((t for pat, t in _TYPES if re.search(pat, k)), None)
    if bodies:
        part, region = bodies[0]
        f.update(category='injury', body_region=region, body_part=part, injury_type=typ or 'unspecified',
                 is_surgery=int(typ == 'surgery' or bool(re.search(r'surger|arthroscop', k))))
        confident = len(bodies) == 1 and not multi and not nm and typ is not None
        return f, confident
    if typ == 'concussion':
        f.update(category='injury', body_region='head', body_part='head', injury_type='concussion')
        return f, not multi
    return f, False                          # nothing recognisable: LLM


def severity_tier(fields, flags=None):
    """1 minor (soreness, bruise, illness), 2 moderate, 3 major (tear, fracture,
    dislocation, surgery, or ruled out for the season). None for non-medical."""
    flags = flags or {}
    cat, typ = fields.get('category'), fields.get('injury_type')
    if cat in ('non_medical', 'not_absence'):
        return None
    if flags.get('out_for_season') or typ in ('tear', 'fracture', 'dislocation', 'surgery') or fields.get('is_surgery'):
        return 3
    if cat == 'illness' or typ in ('soreness', 'bruise', 'laceration'):
        return 1
    return 2


def curve_group(fields):
    cat = fields.get('category')
    if cat == 'injury':
        return f"{fields.get('body_region') or 'unknown'}:{fields.get('injury_type') or 'unspecified'}"
    if cat == 'illness':
        return f"illness:{fields.get('injury_type') or 'illness'}"
    if cat == 'non_medical':
        return f"non_medical:{fields.get('non_medical_reason') or 'other'}"
    return cat or 'unspecified'


def describe_group(group):
    """Human label for a curve group, for the app's dropdown."""
    if group == 'unspecified':
        return 'Unspecified (placed on IL, no detail)'
    a, _, b = group.partition(':')
    if a == 'illness':
        return 'Illness' if b == 'illness' else 'COVID / health & safety protocols'
    if a == 'non_medical':
        return f"Non-medical: {b.replace('_', ' ')}"
    return f"{REGION_LABELS.get(a, a.title())} — {b.replace('_', ' ')}"
