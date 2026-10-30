# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## What this project is

A fantasy basketball decision system for **ESPN and Yahoo NBA leagues** — the
capstone described in `README.md`. Four features, all built on one MySQL/MariaDB
schema named `basketball`:

1. **Points prediction** per player for the next five games (time-series, ML, and
   naive baselines, with a champion model picked per player).
2. **Minute-weighted free-agent screener** — the headline feature; ranks free
   agents by production per minute played, which neither ESPN nor Yahoo offers.
3. **Current team performance** — weekly roster performance plus Kaplan-Meier
   survival estimates for "how many more days is this injury likely to last".
4. **AI assistant** — a Claude-powered chatbox answering questions against the
   live dashboards' own DataFrames.

Three layers:

```
pipeline/   ETL + model fitting  →  MySQL `basketball` schema  →  app/  (Dash on Heroku)
```

The app **only reads**. Every table it queries is populated by `pipeline/`
scripts run manually from this machine. Nothing in `pipeline/` runs on Heroku,
and `requirements.txt` deliberately omits the sports-API and modeling packages
for that reason (see **Two requirements files**).

---

## Environment

Several conda envs exist with similar names. The ones that matter:

| env | python | use |
|---|---|---|
| `basketball-env-useme` | 3.9.18 | **the default** — app + all `pipeline/` ETL (dash, mysql-connector, espn-api, yahoo-fantasy-api, basketball-reference-web-scraper, sksurv, statsmodels, chime) |
| `basketball-env-useme-parallel-TF` | 3.9.18 | adds **TensorFlow 2.15** — needed by `base_model.py`, `machine_learning_models.py`, `my_time_series.py` |
| `basketball-prosports-vclaude-env` | 3.11.15 | the prosportstransactions injury scrape (`pro_sports_transactions` + Unflare) |
| `basketball-vclaude-useme` | 3.11.9 | matches `runtime.txt`; has `anthropic` only |

```bash
conda activate basketball-env-useme
```

⚠️ **No single env runs everything.** `basketball-env-useme` has no `anthropic`,
so the AI assistant page fails locally there but works on Heroku, where
`requirements.txt` installs it. TensorFlow lives only in the `-parallel-TF` envs.
Check for the package before assuming an env is wrong.

⚠️ **Local pandas is 1.3.5; `requirements.txt` pins 2.2.3.** Local and Heroku are
not the same pandas major. `groupby().apply()` — used by the minute-weighted
calculation in `callbacks.apply_calculation()` and by `ai_chatbox.build_context()`
— changed behaviour between those versions. A frame shape that works locally is
not proof it works live.

### Always run from the repo root

**Nothing in this repo bootstraps `sys.path`.** Scripts import as
`from shared.my_functions import ...` and `from pipeline.my_time_series import ...`,
which only resolve with the repo root on the path. `python pipeline/historicals.py`
puts `pipeline/` on the path, not the root, and fails on import. Use:

```bash
python -m pipeline.historicals
```

Scripts reading `oauth2.json` do so by **relative** path (`my_team_stats.py`,
`free_agents_yahoo_basketball.py`), which is a second reason the root must be cwd.

### Database and env vars

MySQL/MariaDB, schema `basketball`. **The same credentials are read under two
different names depending on the layer** — and unlike the baseball repo, there is
**no fallback**:

| | names it reads |
|---|---|
| `pipeline/*` (every script, each building its own `config` dict) | `sports_db_admin_host` / `_user` / `_pw` / `_port`, database literal `'basketball'` |
| `shared/config.py` → `app/*` | `basketball_host` / `basketball_user` / `basketball_pw` / `basketball_port` / `basketball_db` |

`shared/config.py` reads **only** the Heroku names; the dev block is commented
out. So **running the app locally needs the `basketball_*` names set locally too**,
even though every pipeline script wants the `sports_db_admin_*` ones. Both sets
must exist on this machine.

Other env vars: `season_start` / `season_end` (consumed by `shared/data_imports.py`
to split current season from history), `season_year`, `leagueid` / `espn_s2` /
`swid` (ESPN auth), `ANTHROPIC_API_KEY`.

---

## Commands

```bash
# the app, locally — mirrors the Procfile
gunicorn app.index:server -t 120 --preload

# one pipeline script
python -m pipeline.historicals

# deploy
git push heroku main
```

- **Live:** https://fantasy-basketball-team-dash-aef016454ed4.herokuapp.com/
- **Procfile:** `web: gunicorn app.index:server -t 120 --preload`; `runtime.txt` is
  python-3.11.9. Remotes: `origin` (GitHub `francisco-avalos/fantasy_basketball`)
  and `heroku` (`fantasy-basketball-team-dash`). Heroku serves the last **pushed**
  commit — local edits change nothing until committed and pushed.
- There are **no tests** and no linter config in this repo. Don't invent a test
  command; verify by running the script or the app.

⚠️ **`python -m app.index` does not work.** The `__main__` block calls
`app.run_server(debug=True)`, but `app` is the *package* (bound by
`import app.callbacks`), not the Dash instance — which is `app_inst`. It raises
`AttributeError`. Use gunicorn, or fix the block to `app_inst.run_server(...)`.

⚠️ **`pipeline/run_scripts.py` is stale and does not run.** It calls
`call(['python', script])` with **bare filenames** (`'advanced_stats.py'`), which
resolves from neither the root nor `pipeline/`, and it names
`historical_basketball_injury_data.py` — a file that no longer exists (it is now
`historical_basketball_injury_data_updated.py`). It also wraps the loop in a bare
`except:` that only plays a `chime` sound, so a failure is inaudible in the log.
Run scripts individually with `-m` until it is rewritten.

---

## The pipeline

Every ingest script follows the same shape: pull from an API or scrape, write a
CSV into `tmp_data/`, then `LOAD DATA LOCAL INFILE ... REPLACE INTO TABLE`,
then `os.remove()` the CSV. `allow_local_infile=True` is required in the
connection config for this to work.

| script | source | writes |
|---|---|---|
| `advanced_stats.py` | ESPN FA list × bbref advanced season totals | `advanced_stats` |
| `historicals.py` | basketball-reference box scores | `historical_player_data` |
| `my_team_stats.py` | ESPN + Yahoo rosters, bbref box scores | `my_team_stats`, `my_team_stats_yahoo`, `live_espn_players`, `live_yahoo_players` |
| `free_agents_yahoo_basketball.py` | Yahoo free agents + waivers | `live_free_agents_yahoo` |
| `free_agents_backfill.py` | ESPN FA history | `live_free_agents` |
| `espn_player_positions.py` | ESPN | `espn_player_positions` |
| `high_level_nba_team_stats.py` / `_schedules.py` | bbref | `high_level_nba_team_stats`, `high_level_nba_team_schedules` |
| `injured_report.py` | requests + BeautifulSoup | `injured_player_news`, `injured_player_news_yh` |
| `historical_basketball_injury_data_updated.py` | prosportstransactions via Unflare | `hist_player_inj` |
| `injury_probabilities_basketball.py` | `player_injury_cycles` → Kaplan-Meier | `injury_probabilities` |
| `base_model.py`, `machine_learning_models.py`, `model_pooling.py` | model fitting | `predictions`, `model_evaluation` |

`basketball-work.py` (1264 lines, hyphen in the name so it cannot be imported)
and `my_team_performance_dash.py` (965 lines, its own standalone matplotlib/Dash)
are **predecessors kept for reference**, not part of the live flow.

### Name mapping is the hard part

ESPN, Yahoo, and basketball-reference do not share player identifiers. The join
key everything funnels into is the **bbref slug** (`bbrefid` / `slug`, e.g.
`tatumja01`), and `basketball.master_names_list_temp` is the crosswalk.

- **ESPN → bbref** goes through `basketball_references_players.BBRefName` on an
  exact name match, plus `unidecode` + suffix-stripping helpers.
- **Yahoo → bbref** has no id to join on at all. `shared/data_imports.yahoo_query`
  splits the Yahoo display name in SQL with nested `SUBSTRING_INDEX` calls to
  derive first / last / suffix and matches those three against
  `master_names_list_temp`. It is fragile by construction — a new player whose
  name shape the splitter mishandles silently produces **no rows**, not an error.
- `shared/my_functions.py` holds the cleaners (`clean_string`,
  `remove_name_suffixes`, `remove_jr`, …). `sql_files/FA_Stats_Mapping_Overview.sql`
  documents which fields each source actually exposes — read it before inventing
  a new join.

⚠️ **There are two copies of the helper module.** `shared/my_functions.py` is
canonical. `pipeline/my_basketball_funcs.py` is an older, larger copy that still
contains baseball leftovers (`get_mlb_team_name_designations`) and is imported by
exactly two scripts — `advanced_stats.py` and `injury_probabilities_basketball.py`
(for `return_parenthesis_contents`, `contains_number`, `coalesce`, which the
canonical module lacks). Add new helpers to `shared/`.

### The injury chain

`hist_player_inj` (raw prosportstransactions rows) is reshaped by SQL in
`sql_files/Injury_table_setup_backfill.sql` through a chain of intermediate
tables — `unhealthy_date_only_*`, `healthy_date_cycles_excl_*`,
`unhealthy_date_cycles_excl_*`, `players_cycler`, `player_inj_cycles_prefinal` —
into **`player_injury_cycles`**, one row per player per health cycle with
`unhealthy1..5` day counts and their notes.

`injury_probabilities_basketball.py` reads `player_injury_cycles`, parses the
injury description out of the notes, and fits
`sksurv.nonparametric.kaplan_meier_estimator` per injury type, landing
`injury_probabilities` (injury, days, probability). The app reads that table
directly and formats the probability as a percentage string **in SQL**
(`inj_prob_qry`), so it arrives as text, not a number.

⚠️ **The prosportstransactions scrape needs a local Unflare container running.**
`shared/injury_pipeline.py` points `UnflareRequestHandler` at
`http://localhost:5002/scrape` and builds the handler **once at import time** so
the Cloudflare clearance cookie is reused. Before running the injury script:
`docker start unflare`. Each day is committed individually, so a re-run resumes
from `MAX(day)`; a real fetch failure **halts** rather than marking days empty, so
gaps don't get baked in silently.

### The model stack

```
base_model.py              statistical / time-series fits per player
machine_learning_models.py LINEAR, NEURAL_NETWORK, LSTM (TensorFlow)
model_pooling.py           adds baselines, picks the champion, loads to MySQL
my_time_series.py          the library all three import (1333 lines)
```

Artifacts are per player, under
`tmp_data/basketball_espn/<bbrefid>/` and `tmp_data/basketball_yahoo/<bbrefid>/`,
split into `models/` (pickles named `<bbrefid>_<YYYY_MM_DD>_<MODEL>.pkl`) and
`scalers/`, with per-player MAE CSVs (`<bbrefid>_ML_MAE.csv`) alongside.
`shared/my_functions.create_player_folder` / `create_model_folder` /
`create_model_scaler_folder` create them; `is_statistical_model()` and
`date_extract()` parse the model type and date back out of a filename.

- **Train/test split is 80/20** (`n=0.8`), chronological, and the evaluation
  metric is **MAE** throughout.
- `model_pooling.py` concatenates the statistical and ML MAE files, appends two
  naive baselines it computes itself — **REPEAT** (tile the last five games) and
  **LAST** (repeat the final value) — sorts ascending by MAE, and sets
  `champion_model = 1` on **the single best row**. Everything else gets 0.
- Forecast horizon is **5 games**, written through
  `shared/my_functions.prepare_predictions_table()`, which inserts the id and
  parameter columns positionally (`df.insert(0..11)`) around the caller's `day`
  and `predictions`. Change that column order and the `LOAD DATA` into
  `basketball.predictions` shifts silently.
- These three scripts are **not** in `run_scripts.py` — fitting is on demand.

⚠️ `model_pooling.py` **TRUNCATEs `predictions` and `model_evaluation` up front**
(line ~138), then loads one player at a time from inside the fitting loop
(line ~205). So an interrupted run leaves a **partially populated** predictions
table — covering whichever players it reached — and the app serves it without
complaint. Same hazard as `advanced_stats.py` below, one step further downstream.

---

## The Dash app

```
app/index.py        routes, gunicorn entry point (app.index:server)
app/dash_create.py  the Dash instance (app_inst) — keep minimal
app/landing.py      page0, the landing page
app/layouts.py      page1–page4 (1295 lines)
app/callbacks.py    every @app_inst.callback + every figure builder (946 lines)
app/ai_chatbox.py   Anthropic client, context builder, system prompt
```

| route | page | content |
|---|---|---|
| `/` (and anything unrecognised) | `page0` | landing |
| `/apps/fantasy-predictions` | `page1` | predictions + model evaluation |
| `/apps/free-agent-screening` | `page2` | minute-weighted screener |
| `/apps/team-performance` | `page3` | weekly team performance + injury survival |
| `/apps/ai-assistant` | `page4` | chatbox |

Theme is Bootstrap **DARKLY** plus Inter from Google Fonts, patched by
`assets/custom.css`. Dash auto-serves `assets/`, and `dash_create.py` points
`assets_folder` one level up from `app/` to reach it. In-file styling uses the
`corporate_colors` dict at the top of `layouts.py`.

### ⚠️ All data loads at import time, and the app is not a module boundary

`layouts.py` imports its figure builders **from `callbacks.py`**, so importing
layouts executes callbacks first. Each of the two modules independently:

- builds its **own** `pooling.MySQLConnectionPool`, both named `"sports_db_pool"`,
  both `pool_size=5` — 10 connections for one process; and
- runs its own startup query batch at module level
  (`data_imports.optimize_code()` in callbacks, `optimize_code_layouts()` in
  layouts), so the **expensive `espn_query`** — a `UNION ALL` of
  `live_free_agents` with every matching row of `historical_player_data` — runs
  **twice per boot**.

`layouts.py` then does more pandas work at import (a 700-day groupby for the
opening heatmap). This is why the Procfile carries `-t 120 --preload`.

⚠️ **Running ANY pipeline script changes nothing on the live site until the dyno
restarts** (`heroku restart -a fantasy-basketball-team-dash`, or Heroku's own
~daily cycling). The frames are module globals, never refreshed, with no cache
TTL — there is no "reload data" path short of a restart. A fresh table plus a
stale dyno is easy to mistake for a code bug: on 2026-10-30, `live_free_agents`
had 163 players all inside the last 10 days, while the dyno still served a
226-player snapshot from an older load. The free-agent screener's Player
Checklist is the quickest tell, since it is frozen at boot from the same
snapshot — compare its names against the table.

The screener also **500s on an empty window**: `apply_calculation('weights')`
sets 13 column names on the 0×16 frame that `groupby().apply()` returns for no
rows (`ValueError: Length mismatch`), and Dash then keeps whatever figure was
already showing.

`optimize_code_layouts()` also queries `my_live_espn_qry` / `my_live_yahoo_qry`
and never puts the results in its return dict — dead work on every boot.

### The minute-weighted calculation

`callbacks.apply_calculation()` is where feature #2 actually lives. When
`calculation_type == 'weights'` it computes, per player,
`sum(stat × minutes_played) / sum(minutes_played)` (guarding a zero denominator);
anything else falls through to a plain `groupby().agg()`. `minutes_played` and
`total_rebounds` are **derived in pandas, not SQL**, by
`data_imports.add_new_fields()` (`seconds_played / 60`, and offensive + defensive
rebounds) — so any frame fed to the weighted path must be passed through it first.

The history selector (`history_id`) is three-valued and only one branch is
date-filtered: `'cso'` (current season only) applies the `days_ago` window,
while `'ho'` (historicals only) and `'hcs'` (history + current) **ignore it**.

---

## Hard-won gotchas

Each of these costs real time. Do not rediscover them.

- ⚠️ **`myteam=league.teams[9]` — the ESPN roster is picked by LIST INDEX**
  (`my_team_stats.py`). The index has already moved 11 → 10 → 9 across seasons,
  and commented-out older values are still in the files. A wrong index silently
  ingests **another manager's roster** with no error. Verify it against the real
  team name whenever a season rolls over.
- ⚠️ **Yahoo league keys are hard-coded, and the two scripts disagree.**
  `my_team_stats.py` uses `454.l.6397` (2024-25) and `free_agents_yahoo_basketball.py`
  uses `428.l.18598` (2023-24) — pointing at two different seasons. Worse,
  `free_agents_yahoo_basketball.py` calls `gm.league_ids(year=season_year)` and
  then **throws the result away** on the next line. Both keys need updating each
  season; prefer wiring them to `league_ids()` rather than editing literals.
- ⚠️ **`advanced_stats.py` TRUNCATEs before it fetches.** The table is emptied,
  *then* the ESPN FA list and the bbref advanced-totals scrape run. A rate-limit
  or auth failure leaves `advanced_stats` **empty**, and the app shows no error —
  just nothing. (`free_agents_yahoo_basketball.py` has the safe order: fetch
  first, then truncate and load.)
- ⚠️ **`execute_query_and_fetch_df()` swallows every exception**, prints it, and
  returns **`None`**. A failed query therefore surfaces far away as
  `TypeError: 'NoneType' is not subscriptable` inside whatever module-level code
  unpacks the dict — not as a database error. When the app dies at import with a
  `None` complaint, look at the printed line above it. The same helper reads
  `cursor.description` **after** the `with` block has closed the cursor; it works
  on mysql-connector 8.1.0 but will break on a connector that clears it.
- ⚠️ **Do NOT escape the `%` in `DATE_FORMAT`.** mysql-connector 8.1.0 substitutes
  parameters with `RE_PY_PARAM = re.compile(b'(%s)')` — a regex sub on `%s` only,
  **not** Python `%`-formatting. So `DATE_FORMAT(date, '%Y-04-%d')` sitting in the
  same query as a `%s` placeholder is correct as written (`espn_query`,
  `yahoo_query`). "Fixing" them to `%%Y` would change the SQL and corrupt the
  date comparison.
- **MySQL `DECIMAL` arrives as `decimal.Decimal` and will not do arithmetic with
  floats.** Frames are built from the cursor
  (`pd.DataFrame(result, columns=[col[0] for col in cursor.description])`) rather
  than `pd.read_sql`, which used to hide this. That is what
  `my_functions.convert_fields_to_float()` exists for — call it on any numeric
  columns you intend to compute with, not just the ones already listed.
- **`LOAD DATA` needs `OPTIONALLY ENCLOSED BY '"'`.** Every loader in this repo
  has it. Injury `notes` contain commas ("fined $25,000"); without the clause the
  row splits and every later column shifts.
  `historical_basketball_injury_data_updated.py` also names its target columns
  explicitly, so the load never depends on CSV column order — follow that.
- **`subprocess.call()` returns an exit code; it does not raise.** A `try/except`
  around it never fires — which is exactly why `run_scripts.py` reports success on
  scripts that failed. Check `returncode`.
- **Bare `except:` hides failures** — `run_scripts.py` and several ETL loops. When
  touching one, print the actual exception. `advanced_stats.py`'s per-player
  handler already does (`f'{fa} not captured — {type(e).__name__}: {e}'`).
- **Basketball-reference rate-limits hard.** Scripts carry `time.sleep(4)` between
  requests; the comments in `advanced_stats.py` record the measured ceiling
  (~20 requests/min is where blocking starts). Don't lower the delays.
- ⚠️ **Hard-coded absolute paths.** Every CSV handoff and model folder is written
  as `/Users/franciscoavalosjr/Desktop/basketball-folder/tmp_data/...`. Moving or
  renaming the repo breaks the whole pipeline. `tmp_data/` is gitignored, so these
  paths exist on this machine only — and nothing on Heroku can read them.

---

## Two requirements files

- `requirements.txt` — **what Heroku installs**: Dash, Plotly, pandas,
  mysql-connector, `anthropic`, `beautifulsoup4`. No sports APIs, no statsmodels,
  no TensorFlow. The app cannot ingest or fit; that is deliberate.
- `requirements-dev.txt` — the local superset: adds espn-api, yahoo-fantasy-api,
  basketball-reference-web-scraper, statsmodels, scikit-survival, prophet,
  matplotlib/seaborn, scipy, sklearn.

⚠️ `Flask==2.2.5` / `Werkzeug==2.2.3` are pinned because **Dash 2.13 breaks on
Flask 2.3+**. Don't bump them without bumping Dash.

---

## Repo layout

```
app/              the Dash app (see above)
pipeline/         ETL + modeling scripts; run as `python -m pipeline.<name>`
shared/           config.py (creds/season dates), data_imports.py (every app
                  query), my_functions.py (canonical helpers),
                  injury_pipeline.py (Unflare / prosportstransactions)
sql_files/        table DDL (commented out in table_creation_definitions.sql),
                  the injury-cycle chain, and scratch/inspection queries
assets/           custom.css + images, auto-served by Dash
data/             BBRefIDs.csv, ESPNIDs.csv
notebooks/        exploration
tmp_data/         CSV handoffs + per-player model artifacts  (gitignored)
archived/         retired scripts  (gitignored)
*.ipynb           large exploration notebooks at the root  (gitignored)
```

`sql_files/table_creation_definitions.sql` holds the `CREATE TABLE` for ~28
tables, **all commented out** — it is the schema reference, not a runnable
script. Read it before guessing at a column.
