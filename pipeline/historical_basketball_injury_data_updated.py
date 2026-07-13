"""
historical_basketball_injury_data.py

Pulls injury / discipline / legal transactions per day from prosportstransactions.com
(via the pro_sports_transactions library + a local Unflare container) and loads them
into basketball.hist_player_inj.

REQUIREMENT EACH RUN: the Unflare container must be running.
    docker start unflare      # before you run this
    docker stop  unflare      # after (optional)

Resume behavior: each day is committed individually, so a re-run picks up from
MAX(day) already in the table. A real fetch failure HALTS the run (rather than
silently marking days empty); fix Unflare and re-run to resume with no gaps.
"""

import os
import csv
import time
import warnings
import datetime as dt

import pandas as pd
import mysql.connector as mysql

from shared.injury_pipeline import day_injuries_basketball

# The library calls pandas.read_html internally; pandas emits a harmless
# FutureWarning from inside it. Silence just that one so logs stay readable.
warnings.filterwarnings("ignore", category=FutureWarning, module="pro_sports_transactions")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
config = {
    "host":     os.environ.get("sports_db_admin_host"),
    "database": "basketball",
    "user":     os.environ.get("sports_db_admin_user"),
    "password": os.environ.get("sports_db_admin_pw"),
    "port":     os.environ.get("sports_db_admin_port"),
    "allow_local_infile": True,
}

START_DATE = "2000-01-01"
TMP_DIR    = "/Users/franciscoavalosjr/Desktop/basketball-folder/tmp_data"
FAILED_LOG = "/Users/franciscoavalosjr/Desktop/basketball-folder/failed_days.log"

# Seconds between days. ~12 requests/min is polite and well within limits.
# You can lower toward 2-3 to speed a big backfill, but watch for 403/429.
REQUEST_DELAY = 5

# If this many days fail back-to-back, it's a systemic outage (Unflare down /
# IP blocked), so we stop instead of grinding through thousands of failures.
MAX_CONSECUTIVE_FAILURES = 10

CURRENT_DAY = dt.datetime.now().strftime("%Y-%m-%d")

pd.set_option("display.max_columns", None)
pd.set_option("display.max_rows", None)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def insert_day(data: pd.DataFrame, day: str) -> None:
    """Write one day's rows to a temp CSV and LOAD them into the table.

    Target columns are named explicitly so the load never silently depends on
    header text or column order, utf8mb4 keeps accented names intact, and
    OPTIONALLY ENCLOSED BY '"' means commas inside `notes` (e.g. "fined $25,000")
    don't shift the columns.
    """
    file_path = os.path.join(TMP_DIR, f"inj_players_{day}.csv")
    data.to_csv(file_path, index=False, quoting=csv.QUOTE_MINIMAL, lineterminator="\n")

    connection = mysql.connect(**config)
    try:
        cursor = connection.cursor()
        cursor.execute(
            f"LOAD DATA LOCAL INFILE '{file_path}' "
            f"REPLACE INTO TABLE basketball.hist_player_inj "
            f"CHARACTER SET utf8mb4 "
            f"FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '\"' "
            f"LINES TERMINATED BY '\\n' "
            f"IGNORE 1 ROWS "
            f"(day, team, acquired, relinquished, notes);"
        )
        connection.commit()
        cursor.close()
    finally:
        if connection.is_connected():
            connection.close()
    os.remove(file_path)


def log_failure(day: str, err) -> None:
    """Record a failed day so isolated failures aren't lost (re-run them later)."""
    with open(FAILED_LOG, "a") as fh:
        fh.write(f"{day}\t{err}\n")


# ---------------------------------------------------------------------------
# Pre-flight: prove the whole chain works before looping over thousands of days
# ---------------------------------------------------------------------------
if not os.path.isdir(TMP_DIR):
    raise SystemExit(f"temp dir does not exist: {TMP_DIR}")

print("pre-flight: testing scrape + parse on a known-good date (2022-12-07)...")
try:
    _probe = day_injuries_basketball("2022-12-07")   # also warms the cookie cache
except Exception as e:
    raise SystemExit(
        f"pre-flight FAILED: {e}\n"
        f"Is the Unflare container running?   docker start unflare"
    )
if _probe is None or _probe.empty:
    raise SystemExit("pre-flight returned no rows for a known-good date — check Unflare / the function.")
print(f"pre-flight ok: {len(_probe)} rows. Cookie cache is warm.\n")
del _probe


# ---------------------------------------------------------------------------
# Decide where to resume (MAX(day) already in the table)
# ---------------------------------------------------------------------------
connection = mysql.connect(**config)
cursor = connection.cursor()
cursor.execute("SELECT MAX(day) AS recent_date FROM basketball.hist_player_inj;")
(recent_inj_date,) = cursor.fetchone()
cursor.close()
connection.close()
print("MySQL connection is closed")

if recent_inj_date is None:
    date_range = pd.date_range(start=START_DATE, end=CURRENT_DAY)
    print(f"no existing data -- backfilling from {START_DATE}")
else:
    # re-pull MAX(day) inclusive so late-arriving updates to that day are refreshed
    date_range = pd.date_range(start=recent_inj_date, end=CURRENT_DAY)
    print(f"pick up from {recent_inj_date}")


# ---------------------------------------------------------------------------
# Main loop
#   empty frame -> genuine no-transaction day (skip, no DB write)
#   exception   -> real fetch failure: log it; halt if it keeps happening
# ---------------------------------------------------------------------------
consecutive_failures = 0

for ts in date_range:
    day = str(ts).split()[0]

    try:
        data = day_injuries_basketball(day)
    except Exception as e:
        consecutive_failures += 1
        log_failure(day, e)
        print(f"FETCH FAILED for {day} ({consecutive_failures} in a row): {e}")
        if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
            raise SystemExit(
                f"\n{consecutive_failures} consecutive failures -- Unflare is likely down "
                f"or the IP is blocked.\n"
                f"Check: docker ps / docker logs unflare, fix it, then re-run "
                f"(resumes from MAX(day)).\n"
                f"Failed days were logged to {FAILED_LOG}."
            )
        time.sleep(REQUEST_DELAY)
        continue

    consecutive_failures = 0
    if data is None or data.empty:
        print(f"no transactions for {day}")
    else:
        insert_day(data, day)
        del data
        print(f"inserted data for {day}")

    time.sleep(REQUEST_DELAY)

print("done")
