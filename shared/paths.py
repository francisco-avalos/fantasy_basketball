"""Repo-relative paths, so the pipeline runs from any checkout (this laptop or a GitHub Actions runner).

    REPO_ROOT  the repository root (the folder holding pipeline/, shared/, season_dates.csv)
    TMP_DIR    REPO_ROOT/tmp_data, the CSV handoff folder (gitignored); created on import
"""
import os

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP_DIR = os.path.join(REPO_ROOT, 'tmp_data')
os.makedirs(TMP_DIR, exist_ok=True)
