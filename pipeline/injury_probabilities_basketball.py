"""
injury_probabilities_basketball.py
----------------------------------
Fit "how much longer will he be out" curves from basketball.player_injury_cycles
(built by pipeline/injury_mapping.py) and load them into basketball.injury_probabilities.

    player_injury_cycles ──> 4 candidate models, scored on a temporal holdout
                         ──> champion refit on everything ──> one curve per injury group

What is modelled
----------------
Duration  = in-season days from the out date to the return (shared/season_calendar.py).
Event     = 1 when the return was observed. Episodes cut short by a second injury, a gap
            in the box scores, retirement etc. are right-censored (event = 0), so they add
            "was still out after N days" instead of being dropped or counted as a return.
            Episodes open at season end whose player was back within two weeks of the next
            opener (shutdown_suspect) are censored at season end: we can't tell when he
            would have come back if there had been games.
Covariates, all known on day one (nothing learned later in the absence):
  curve group (body region x injury type, illness, non-medical reason, unspecified), with
  groups under MIN_GROUP training episodes pooled into '<region>:other';
  era (2000-05 / 2006-14 / 2015-20 / 2021+, reference 2021+: reporting rules changed);
  out_for_season, out_indefinitely, stated return window, surgery, DTD, concurrent;
  age; prior episodes, same-region episodes and in-season days missed in the last year;
  player frailty: an empirical-Bayes player effect, the shrunken average of how much longer
  (log scale) than his group's median the player's PREVIOUS absences ran.

Candidates
----------
  km_group       Kaplan-Meier per curve group (no covariates): the old approach with censoring
  lognormal_aft  log(T) = Xb + sigma*e, e ~ Normal
  weibull_aft    log(T) = Xb + sigma*e, e ~ Gumbel (Weibull time-to-event)
  spline_ph      proportional hazards, baseline hazard a restricted cubic spline (Royston-Parmar)
Scored on seasons >= TEST_FROM_SEASON after fitting on the earlier seasons: IPCW Brier score
at EVAL_TIMES and integrated over 1..60 days (lower is better), C-index on restricted mean
time (higher is better), and calibration = mean |predicted - Kaplan-Meier| at 7/14/30 days
within each test group. Lowest integrated Brier wins and is refit on every season.

Published curve for a group: the champion's survival curve averaged over that group's
episodes with era set to today's (a population-average curve for the current league),
daily from day 0 to HORIZON in-season days.

Run from the repo root (env: basketball-env-useme-v11052026, which has lifelines):
    python -m pipeline.injury_probabilities_basketball --dry-run          # fit + compare, no DB writes
    python -m pipeline.injury_probabilities_basketball                    # fit + load
    python -m pipeline.injury_probabilities_basketball --from-csv tmp_data/injury_episodes_dryrun.csv --dry-run --plot
"""

import argparse
import os
import warnings

import numpy as np
import pandas as pd
import mysql.connector as mysql
from lifelines import KaplanMeierFitter, LogNormalAFTFitter, WeibullAFTFitter, CoxPHFitter
from lifelines.utils import concordance_index
from sksurv.metrics import brier_score, integrated_brier_score

from shared import season_calendar as cal
from shared.injury_taxonomy import BODY_REGIONS

warnings.filterwarnings('ignore', category=RuntimeWarning)

config = {
    'host': os.environ.get('sports_db_admin_host'),
    'database': 'basketball',
    'user': os.environ.get('sports_db_admin_user'),
    'password': os.environ.get('sports_db_admin_pw'),
    'port': os.environ.get('sports_db_admin_port'),
}

ROOT = '/Users/franciscoavalosjr/Desktop/basketball-folder/'
TMP = ROOT + 'tmp_data/'
TEST_FROM_SEASON = 2023
MIN_GROUP = 30             # episodes for a curve group to get its own effect and its own published curve
CURRENT_ERA = '2021+'
ERAS = ['2000-05', '2006-14', '2015-20', '2021+']
HORIZON = 150              # in-season days published per curve
EVAL_TIMES = [3, 7, 14, 30, 60]
IBS_TIMES = np.arange(1, 61)
SHRINK_K = 3               # frailty shrinkage: k pseudo-episodes at the group median
PENALIZER = 0.01
MAX_AVG_EPISODES = 1500    # episodes averaged per published curve


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

def load_episodes(from_csv=None):
    if from_csv:
        return pd.read_csv(from_csv, parse_dates=['start_date', 'end_date'])
    connection = mysql.connect(**config)
    try:
        cur = connection.cursor()
        cur.execute('SELECT * FROM basketball.player_injury_cycles WHERE fit_eligible = 1')
        df = pd.DataFrame(cur.fetchall(), columns=cur.column_names)
        cur.close()
    finally:
        connection.close()
    for c in ['start_date', 'end_date']:
        df[c] = pd.to_datetime(df[c])
    num = ['inseason_days', 'stated_days', 'age_at_start', 'prior_episodes', 'prior_same_region_365',
           'prior_inseason_days_365', 'event', 'season']
    df[num] = df[num].apply(pd.to_numeric, errors='coerce')        # DECIMAL -> float
    return df


def prepare(df):
    df = df[df['fit_eligible'] == 1].copy()
    df['E'] = df['event'].astype(int)
    df['T'] = df['inseason_days'].astype(float)
    shut = df['shutdown_suspect'] == 1
    if shut.any():
        ends = df.loc[shut, 'season'].map(lambda s: cal.season_bounds(int(s))[1])
        df.loc[shut, 'T'] = cal.clock(ends.values) - cal.clock(df.loc[shut, 'start_date'].values)
        df.loc[shut, 'E'] = 0
    df['T'] = df['T'].clip(lower=0.5)                 # parametric fits need T > 0; same-day returns = half a day
    df['slug'] = df['slug'].fillna(df['player_key'])
    return df.sort_values(['slug', 'start_date']).reset_index(drop=True)


def parent(group):
    head = group.split(':')[0]
    return 'injury:other' if head in BODY_REGIONS else f'{head}:other' if ':' in group else group


def group_map(groups):
    """curve_group -> model group. Small groups pool into '<region>:other', then 'injury:other'."""
    counts = groups.value_counts()
    keep = set(counts[counts >= MIN_GROUP].index)
    out = {}
    for g in counts.index:
        if g in keep:
            out[g] = g
            continue
        region_other = g.split(':')[0] + ':other' if ':' in g else g
        pooled = counts[[k for k in counts.index if k not in keep and
                         (k.split(':')[0] + ':other' if ':' in k else k) == region_other]].sum()
        out[g] = region_other if pooled >= MIN_GROUP else parent(g)
    return out


def frailty(df, medians):
    """Shrunken mean of log((T+1)/(group median+1)) over the player's earlier observed
    returns. 0 for a player with no history; uses nothing from the current episode."""
    z = np.where(df['E'] == 1, np.log1p(df['T']) - np.log1p(df['model_group'].map(medians).fillna(df['T'].median())), np.nan)
    z = pd.Series(z, index=df.index)
    prev_sum = z.fillna(0).groupby(df['slug']).cumsum() - z.fillna(0)
    prev_n = z.notna().astype(int).groupby(df['slug']).cumsum() - z.notna().astype(int)
    return prev_sum / (prev_n + SHRINK_K)


def design(df, groups, eras=ERAS):
    X = pd.DataFrame(index=df.index)
    for c in ['out_for_season', 'out_indefinitely', 'is_surgery', 'is_dtd', 'concurrent']:
        X[c] = df[c].fillna(0).astype(float)
    X['has_stated_window'] = df['stated_days'].notna().astype(float)
    X['log_stated_days'] = np.log1p(df['stated_days'].fillna(0))
    X['age_missing'] = df['age_at_start'].isna().astype(float)
    X['age_c'] = (df['age_at_start'] - 27).fillna(0) / 5
    X['log_prior_episodes'] = np.log1p(df['prior_episodes'].fillna(0))
    X['prior_same_region_365'] = df['prior_same_region_365'].fillna(0).clip(upper=5)
    X['log_prior_days_365'] = np.log1p(df['prior_inseason_days_365'].fillna(0))
    X['frailty'] = df['frailty']
    for e in eras:
        if e != CURRENT_ERA:
            X[f'era_{e}'] = (df['era'] == e).astype(float)
    for g in groups:
        if g != 'unspecified':
            X[f'g_{g}'] = (df['model_group'] == g).astype(float)
    return X


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class KMGroup:
    """Kaplan-Meier per model group; unseen groups get the pooled curve."""
    name = 'km_group'

    def fit(self, df):
        self.curves = {g: KaplanMeierFitter().fit(d['T'], d['E']) for g, d in df.groupby('model_group')}
        self.pooled = KaplanMeierFitter().fit(df['T'], df['E'])
        return self

    def survival(self, df, X, times):
        out = np.empty((len(df), len(times)))
        for g, idx in df.groupby('model_group').indices.items():
            km = self.curves.get(g, self.pooled)
            out[idx] = km.survival_function_at_times(times).values
        return out


class Lifelines:
    """shift: fit on T + shift and read the curve back at t + shift. lifelines' spline
    baseline is built on log(T) and goes non-monotone when T < 1 (same-day returns)."""
    def __init__(self, name, make, shift=0.0):
        self.name, self.make, self.shift = name, make, shift

    def fit(self, df, X):
        self.cols = [c for c in X.columns if X[c].std() > 0]
        d = X[self.cols].assign(T=df['T'].values + self.shift, E=df['E'].values)
        self.model = self.make().fit(d, 'T', 'E')
        return self

    def survival(self, df, X, times):
        sf = self.model.predict_survival_function(X[self.cols], times=np.asarray(times) + self.shift)
        return sf.T.values


def candidates():
    return [
        Lifelines('lognormal_aft', lambda: LogNormalAFTFitter(penalizer=PENALIZER)),
        Lifelines('weibull_aft', lambda: WeibullAFTFitter(penalizer=PENALIZER)),
        Lifelines('spline_ph', lambda: CoxPHFitter(baseline_estimation_method='spline', n_baseline_knots=4),
                  shift=1.0),
    ]


def setup(df, mapping=None, medians=None):
    """Attach model groups and frailty; mapping/medians come from training data when scoring."""
    df = df.copy()
    mapping = mapping or group_map(df['curve_group'])
    df['model_group'] = df['curve_group'].map(mapping).fillna(df['curve_group'].map(parent))
    if medians is None:
        medians = df[df['E'] == 1].groupby('model_group')['T'].median()
    df['frailty'] = frailty(df, medians)
    return df, mapping, medians


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

def surv_array(df):
    return np.array(list(zip(df['E'].astype(bool), df['T'])), dtype=[('E', bool), ('T', float)])


def evaluate(train, test, models, groups):
    Xtr, Xte = design(train, groups), design(test, groups)
    ytr, yte = surv_array(train), surv_array(test)
    grid = np.arange(1, HORIZON + 1)
    rows, preds = [], {}
    for m in models:
        print(f'  fitting {m.name} ...', flush=True)
        m.fit(train) if isinstance(m, KMGroup) else m.fit(train, Xtr)
        S = np.clip(m.survival(test, Xte, grid), 1e-9, 1)
        preds[m.name] = S
        at = {t: S[:, t - 1] for t in EVAL_TIMES}
        _, bs = brier_score(ytr, yte, np.column_stack([at[t] for t in EVAL_TIMES]), EVAL_TIMES)
        ibs = integrated_brier_score(ytr, yte, S[:, IBS_TIMES - 1], IBS_TIMES)
        cidx = concordance_index(test['T'], S.sum(axis=1), test['E'])
        calib = []
        for g, d in test.groupby('model_group'):
            if len(d) < 30:
                continue
            km = KaplanMeierFitter().fit(d['T'], d['E'])
            for t in (7, 14, 30):
                calib.append((len(d), abs(S[test.index.get_indexer(d.index), t - 1].mean()
                                          - km.survival_function_at_times(t).iloc[0])))
        cal_err = np.average([c[1] for c in calib], weights=[c[0] for c in calib])
        rows.append({'model': m.name, 'ibs_1_60': ibs, **{f'brier_{t}d': b for t, b in zip(EVAL_TIMES, bs)},
                     'c_index': cidx, 'calibration_mae': cal_err})
    return pd.DataFrame(rows).set_index('model'), preds


# ---------------------------------------------------------------------------
# Curves + write
# ---------------------------------------------------------------------------

def publish_curves(df, model, groups):
    """Champion curve per model group: average over the group's episodes, era = today's."""
    days = np.arange(0, HORIZON + 1)
    out = []
    rng = np.random.default_rng(11)
    for g, d in df.groupby('model_group'):
        if len(d) > MAX_AVG_EPISODES:
            d = d.iloc[np.sort(rng.choice(len(d), MAX_AVG_EPISODES, replace=False))]
        d = d.assign(era=CURRENT_ERA)
        S = model.survival(d, design(d, groups), days[1:]).mean(axis=0)
        S = np.minimum.accumulate(np.concatenate([[1.0], S]))       # monotone, starts at 1
        n = int((df['model_group'] == g).sum())
        out.append(pd.DataFrame({'injury': g, 'days': days, 'probabilities': S.round(5),
                                 'n_episodes': n, 'model': model.name}))
    return pd.concat(out, ignore_index=True)


def write(curves):
    connection = mysql.connect(**config)
    cur = connection.cursor()
    try:
        cur.execute('DELETE FROM basketball.injury_probabilities;')
        cur.executemany('INSERT INTO basketball.injury_probabilities (injury, days, probabilities, n_episodes, model) '
                        'VALUES (%s, %s, %s, %s, %s);',
                        [(r.injury, int(r.days), float(r.probabilities), int(r.n_episodes), r.model)
                         for r in curves.itertuples()])
        connection.commit()
    except mysql.errors.ProgrammingError as e:
        connection.rollback()
        if e.errno == 1054:
            raise SystemExit('injury_probabilities has no n_episodes/model columns yet; nothing was changed. '
                             'Run sql_files/migrations/2026-11-08_injury_episodes.sql once, then re-run.')
        raise
    except Exception:
        connection.rollback()
        raise
    finally:
        cur.close()
        connection.close()
    print(f'basketball.injury_probabilities: {len(curves)} rows, {curves.injury.nunique()} curves')


def plot(test, preds, out_path, groups=('ankle:sprain', 'knee:tear', 'thigh:strain', 'illness:covid_protocol')):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    groups = [g for g in groups if (test['model_group'] == g).sum() >= 30]
    fig, axes = plt.subplots(1, len(groups), figsize=(4.2 * len(groups), 3.6), sharey=True)
    grid = np.arange(1, HORIZON + 1)
    colors = {'km_group': '#8a8f98', 'lognormal_aft': '#4c8bf5', 'weibull_aft': '#e8a33d', 'spline_ph': '#3dbb8a'}
    for ax, g in zip(np.atleast_1d(axes), groups):
        d = test[test['model_group'] == g]
        km = KaplanMeierFitter().fit(d['T'], d['E'])
        ax.step(km.timeline, km.survival_function_.values[:, 0], where='post', color='black', lw=1.6,
                label=f'observed (KM, n={len(d)})')
        for name, S in preds.items():
            ax.plot(grid, S[test.index.get_indexer(d.index)].mean(axis=0), color=colors.get(name), lw=1.4, label=name)
        hi = min(HORIZON, max(14, int(d['T'].quantile(.95))))
        ax.set_xlim(0, hi)
        ax.set_title(g, fontsize=10)
        ax.set_xlabel('in-season days out')
        ax.grid(alpha=.25)
    np.atleast_1d(axes)[0].set_ylabel('P(still out)')
    np.atleast_1d(axes)[0].legend(fontsize=7, frameon=False)
    fig.suptitle(f'Holdout seasons {TEST_FROM_SEASON}+ : average predicted curve vs observed', fontsize=11)
    fig.tight_layout()
    fig.savefig(out_path, dpi=130)
    print(f'plot: {out_path}')


def main():
    ap = argparse.ArgumentParser(description='Fit injury-duration curves and load basketball.injury_probabilities')
    ap.add_argument('--dry-run', action='store_true', help='fit and compare; write CSVs to tmp_data/, not the DB')
    ap.add_argument('--from-csv', help='read episodes from a CSV (e.g. injury_mapping --dry-run output)')
    ap.add_argument('--plot', action='store_true', help='save a holdout comparison chart to mockups/')
    ap.add_argument('--champion', help='skip the comparison and use this model')
    args = ap.parse_args()

    df = prepare(load_episodes(args.from_csv))
    print(f'episodes {len(df)}  returns observed {int(df.E.sum())}  censored {int((df.E == 0).sum())}')

    names = ['km_group'] + [m.name for m in candidates()]
    champion = args.champion
    if not champion:
        train_raw, test_raw = df[df['season'] < TEST_FROM_SEASON], df[df['season'] >= TEST_FROM_SEASON]
        train, mapping, medians = setup(train_raw)
        test, _, _ = setup(pd.concat([train_raw, test_raw]), mapping, medians)   # frailty sees earlier seasons
        test = test[test['season'] >= TEST_FROM_SEASON].reset_index(drop=True)
        train = train.reset_index(drop=True)
        groups = sorted(train['model_group'].unique())
        print(f'holdout: train seasons < {TEST_FROM_SEASON} ({len(train)}), test ({len(test)}), {len(groups)} groups')
        scores, preds = evaluate(train, test, [KMGroup()] + candidates(), groups)
        print('\n' + scores.round(4).to_string())
        os.makedirs(TMP, exist_ok=True)
        scores.to_csv(TMP + 'injury_model_comparison.csv')
        if args.plot:
            plot(test, preds, ROOT + 'mockups/survival_model_holdout.png')
        champion = scores['ibs_1_60'].idxmin()
        print(f'\nchampion (lowest integrated Brier): {champion}')

    full, mapping, medians = setup(df)
    groups = sorted(full['model_group'].unique())
    model = next((m for m in [KMGroup()] + candidates() if m.name == champion), None)
    if model is None:
        raise SystemExit(f'unknown model {champion}; choose from {names}')
    model.fit(full) if isinstance(model, KMGroup) else model.fit(full, design(full, groups))
    if isinstance(model, Lifelines):
        summ = model.model.summary
        keep = [i for i in summ.index if not str(i[1] if isinstance(i, tuple) else i).startswith('g_')]
        print('\ncovariate effects (excluding group dummies):')
        print(summ.loc[keep, ['coef', 'exp(coef)', 'p']].round(3).to_string())
    curves = publish_curves(full, model, groups)
    med = curves[curves.probabilities <= .5].groupby('injury')['days'].min()
    print(f'\n{curves.injury.nunique()} curves; median in-season days out, longest first:')
    print(med.sort_values(ascending=False).head(15).to_string())

    if args.dry_run:
        curves.to_csv(TMP + 'injury_probabilities_dryrun.csv', index=False)
        print(f'\ndry run: wrote {TMP}injury_probabilities_dryrun.csv')
    else:
        write(curves)


if __name__ == '__main__':
    main()
