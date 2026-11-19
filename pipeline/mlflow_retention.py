"""
mlflow_retention.py
-------------------
Prune old registered model versions in the local MLflow store (mlflow/mlflow.db + mlflow/artifacts/).

points_forecast.py registers 5 XGBoost versions every run (points_xgb_<POS>, ~1 MB each, ~1.8 GB a year)
and 10 TFT / DeepAR versions on each weekly retrain day. For every registered model named points_*:

    keep   the newest KEEP versions (30 = a month of nightly XGBoost)
    keep   the last version of each ISO week (Mon-Sun, by creation date), for the last WEEKS weeks,
           tagged retention=weekly
    keep   any version that has an alias (set one by hand to pin a version forever)
    prune  everything else: the registered version is deleted, and so is its saved model folder
           (<artifacts>/<run_id>/artifacts/model). The run itself (params, val MAE, feature importance)
           is kept: it is a few KB, so that history stays complete.

Steady state per store: about (KEEP + WEEKS) x 5 XGBoost versions, ~400 MB, instead of unbounded growth.
points_forecast.py calls prune() after logging each run; the GitHub runner's store and this laptop's
are separate (see CLAUDE.md), and each is pruned when it runs.

Run from the repo root (env: basketball-env-useme-v11052026):
    python -m pipeline.mlflow_retention --dry-run           # list what would go, change nothing
    python -m pipeline.mlflow_retention                     # prune
    python -m pipeline.mlflow_retention --keep 3 --dry-run  # try the rule on a small store
"""

import argparse
import datetime as dt
import shutil
from pathlib import Path
from urllib.parse import unquote, urlparse

REPO_ROOT = Path(__file__).resolve().parents[1]
MLFLOW_DIR = REPO_ROOT / 'mlflow'
ARTIFACTS = MLFLOW_DIR / 'artifacts'
PREFIX = 'points_'
KEEP = 30
WEEKS = 52


def _client():
    import logging
    from mlflow.tracking import MlflowClient
    for name in ('sqlalchemy', 'alembic'):
        logging.getLogger(name).setLevel(logging.WARNING)
    return MlflowClient(tracking_uri=f'sqlite:///{MLFLOW_DIR / "mlflow.db"}')


def plan(versions, keep=KEEP, weeks=WEEKS, today=None):
    """versions: [(version:int, created:datetime, has_alias:bool)] for one registered model.
    -> (keep_newest, keep_weekly, prune), sets of version numbers."""
    today = today or dt.date.today()
    newest = {v for v, _, _ in sorted(versions, key=lambda x: -x[0])[:keep]}
    aliased = {v for v, _, a in versions if a}
    oldest_week = today - dt.timedelta(weeks=weeks)
    last_of_week = {}
    for v, created, _ in versions:
        if created.date() < oldest_week:
            continue
        wk = created.isocalendar()[:2]
        if wk not in last_of_week or v > last_of_week[wk]:
            last_of_week[wk] = v
    weekly = set(last_of_week.values())
    prune = {v for v, _, _ in versions} - newest - weekly - aliased
    return newest | aliased, weekly, prune


def _model_dir(mv):
    """The version's saved model folder, only if it is inside this store's artifacts folder.
    The source URI is absolute (the runner's is /home/runner/...), so fall back to <artifacts>/<run_id>/."""
    candidates = []
    if mv.source and mv.source.startswith('file:'):
        candidates.append(Path(unquote(urlparse(mv.source).path)))
    if mv.run_id:
        candidates.append(ARTIFACTS / mv.run_id / 'artifacts' / 'model')
    for p in candidates:
        try:
            p.resolve().relative_to(ARTIFACTS.resolve())
        except ValueError:
            continue                                   # never delete outside mlflow/artifacts
        if p.exists():
            return p
    return None


def _size(p):
    return sum(f.stat().st_size for f in p.rglob('*') if f.is_file()) if p else 0


def prune(keep=KEEP, weeks=WEEKS, dry_run=False, log=print):
    """Apply the rule to every points_* registered model. Returns (versions pruned, bytes freed)."""
    if not (MLFLOW_DIR / 'mlflow.db').exists():
        log(f'MLflow retention: no store at {MLFLOW_DIR}, nothing to do')
        return 0, 0
    client = _client()
    n_pruned, freed = 0, 0
    for rm in client.search_registered_models(filter_string=f"name LIKE '{PREFIX}%'"):
        mvs = client.search_model_versions(f"name = '{rm.name}'")
        aliases = set()
        for a in (getattr(rm, 'aliases', None) or {}).values():
            aliases.add(int(a))
        info = [(int(mv.version), dt.datetime.fromtimestamp(mv.creation_timestamp / 1000), int(mv.version) in aliases)
                for mv in mvs]
        kept, weekly, gone = plan(info, keep, weeks)
        by_v = {int(mv.version): mv for mv in mvs}
        for v in sorted(weekly):
            if (by_v[v].tags or {}).get('retention') != 'weekly' and not dry_run:
                client.set_model_version_tag(rm.name, str(v), 'retention', 'weekly')
        size = 0
        for v in sorted(gone):
            mv = by_v[v]
            folder = _model_dir(mv)
            size += _size(folder)
            if not dry_run:
                client.delete_model_version(rm.name, str(v))
                if folder is not None:
                    shutil.rmtree(folder, ignore_errors=True)
        n_pruned += len(gone)
        freed += size
        if gone:
            log(f'  {rm.name}: {len(mvs)} versions, keep {len(kept | weekly)} '
                f'({len(kept)} newest/aliased, {len(weekly - kept)} more weekly), '
                f'{"would prune" if dry_run else "pruned"} {len(gone)}: {_ranges(sorted(gone))} ({size / 1e6:.1f} MB)')
    log(f'MLflow retention (newest {keep} + weekly for {weeks} weeks): '
        f'{"would prune" if dry_run else "pruned"} {n_pruned} versions, {freed / 1e6:.1f} MB')
    return n_pruned, freed


def _ranges(vs):
    """[1,2,3,7,9,10] -> '1-3, 7, 9-10'"""
    out, start = [], None
    for i, v in enumerate(vs):
        if start is None:
            start = v
        if i == len(vs) - 1 or vs[i + 1] != v + 1:
            out.append(f'{start}-{v}' if v != start else f'{v}')
            start = None
    return ', '.join(out)


def main():
    ap = argparse.ArgumentParser(description='Prune old points_* model versions in the local MLflow store')
    ap.add_argument('--keep', type=int, default=KEEP, help=f'newest versions kept per model (default {KEEP})')
    ap.add_argument('--weeks', type=int, default=WEEKS, help=f'weeks of weekly versions kept (default {WEEKS})')
    ap.add_argument('--dry-run', action='store_true', help='list what would be pruned; change nothing')
    args = ap.parse_args()
    prune(args.keep, args.weeks, args.dry_run)


if __name__ == '__main__':
    main()
