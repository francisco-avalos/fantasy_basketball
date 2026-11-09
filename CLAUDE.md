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
| `my_team_stats.py` | ESPN + Yahoo rosters, bbref per-player season game logs | `live_espn_players`, `live_yahoo_players`, then `my_team_stats`, `my_team_stats_yahoo` (Yahoo half behind `YAHOO_ENABLED`) |
| `free_agents_yahoo_basketball.py` | Yahoo free agents + waivers | `live_free_agents_yahoo` |
| `free_agents_backfill.py` | ESPN FA history | `live_free_agents` |
| `espn_player_positions.py` | ESPN | `espn_player_positions` |
| `high_level_nba_team_stats.py` / `_schedules.py` | bbref | `high_level_nba_team_stats`, `high_level_nba_team_schedules` |
| `injured_report.py` | requests + BeautifulSoup | `injured_player_news`, `injured_player_news_yh` |
| `historical_basketball_injury_data_updated.py` | prosportstransactions via Unflare | `hist_player_inj` |
| `injury_mapping.py` | `hist_player_inj` + box scores → episodes; notes → taxonomy (regex, then Claude) | `player_injury_cycles`, `injury_note_classification` |
| `injury_probabilities_basketball.py` | `player_injury_cycles` → survival models, champion on a holdout | `injury_probabilities` |
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
exactly one script — `advanced_stats.py`. Add new helpers to `shared/`.

### The injury chain

```
hist_player_inj ─┐
historical_player_data (box scores) ─┼─ pipeline/injury_mapping.py ─> player_injury_cycles ─┐
injury_note_classification ──────────┘        (+ injury_note_classification)                 │
                          pipeline/injury_probabilities_basketball.py <──────────────────────┘
                                         └─> injury_probabilities ─> app (Injuries tab)
```

Both scripts need **`basketball-env-useme-v11052026`** (lifelines, anthropic,
scikit-survival). The old SQL procedure `health_cycle_backfill_proc` is retired:
its file is in `archived/sql_files/` (gitignored) and the `CALL` in
`sql_files/scratch.sql` is commented out. Don't revive it. The procedure still
exists in the database (both `basketball` and `baseball` schemas), but nothing calls it.

**`injury_mapping.py`** builds one row per **injury episode**:
- An episode **opens** on an "out" row. `(DNP)` single-game rows, fines and coach
  rows are skipped.
- It **closes** at the earlier of an activation row or the player's **first box-score
  game** after the out date. The transaction log often never records the return.
- A second out row while the episode is open:
  - same body region, or a vaguer or updated note: the same episode;
  - different region, illness or non-medical: the open episode is **censored**
    (`concurrent_injury`) and a new one opens with `concurrent=1`;
  - a league-wide box-score hole in between: censored (`data_gap`).
- Episodes are also censored when never closed (`open`), and past the end of the
  following season (`max_follow_up`).
- Duration is **in-season days** from `season_dates.csv` via
  `shared/season_calendar.py`. Every day between a season's start and end counts,
  game or not. The offseason doesn't.
- Labels come from the **first** note (or a detailed note within 3 days of a
  generic one).
- Names map to bbref slugs by name variants plus career overlap (~99% of rows).
- Rows before 2000-10-31 (no season dates, no box scores) are dropped.

The note taxonomy is fixed, in `shared/injury_taxonomy.py`: category, body region,
injury type and non-medical reason; a curve group is e.g. `knee:sprain`. Regex labels
~96% of rows. The rest go to Claude (`LLM_MODEL`, JSON schema, cached in
`tmp_data/injury_note_llm_cache.json`). Labels persist in
`injury_note_classification`; set `reviewed=1` or `source='manual'` there to
pin a correction, since the pipeline never overwrites those rows.
`--dry-run` / `--no-llm` / `--audit N` are the flags.

**`injury_probabilities_basketball.py`**:
- Fits four candidates on seasons before 2023 and scores them on 2023+:
  KM per group, log-normal AFT, Weibull AFT, and spline PH (Royston-Parmar).
- Metrics: IPCW Brier and integrated Brier, C-index, and calibration against KM.
- Covariates: group, era, out-for-season / out-indefinitely / stated window,
  surgery, DTD, concurrent, age, injury history, and an empirical-Bayes player
  frailty.
- Refits the lowest-IBS model on everything (log-normal AFT as of 2026-11-08).
- Writes one population-average curve per group at the current era, days 0–150,
  with `DELETE` + `INSERT` in one transaction.
- `injury` now holds a curve group (`knee:sprain`, `injury:other`,
  `unspecified`), with `n_episodes` and `model` columns. The app reads it as
  `injury_curves_qry` (numeric) and `inj_prob_qry` (percent text, for the AI
  context).

⚠️ **Both scripts need `sql_files/migrations/2026-11-08_injury_episodes.sql` run
once first.** It renames the old table to `player_injury_cycles_legacy`, creates
the new `player_injury_cycles` and `injury_note_classification`, and adds two
columns to `injury_probabilities`. Before that, `--dry-run` works and a real
run exits without changing anything.

⚠️ **The spline PH model is fitted on in-season days + 1.** lifelines builds its
spline baseline on log(T), and it goes non-monotone (survival back up to 1) with
same-day returns at T < 1. The fit diverged before the shift. If you change the
time scale, re-check that model's curves.

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
app/layouts.py      page1–page4 shells (page3 is a stub that calls team_performance)
app/callbacks.py    callbacks + figure builders for pages 1, 2, 4
app/team_performance.py  page 3 in full: data prep, figures, tabbed layout, callbacks
app/ai_chatbox.py   Anthropic client, context builder, system prompt
```

| route | page | content |
|---|---|---|
| `/` (and anything unrecognised) | `page0` | landing |
| `/apps/fantasy-predictions` | `page1` | predictions + model evaluation |
| `/apps/free-agent-screening` | `page2` | minute-weighted screener |
| `/apps/team-performance` | `page3` | three `dcc.Tabs`: Team overview, Player detail, Injuries |
| `/apps/ai-assistant` | `page4` | chatbox |

Theme is Bootstrap **DARKLY** plus Inter from Google Fonts, patched by
`assets/custom.css`. Dash auto-serves `assets/`, and `dash_create.py` points
`assets_folder` one level up from `app/` to reach it. In-file styling uses the
`corporate_colors` dict at the top of `layouts.py`.

### ⚠️ All data loads at import time, and the app is not a module boundary

`layouts.py` imports `line_plot_preds` / `create_data_table` **from `callbacks.py`**
and imports `app.team_performance` (which itself imports `callbacks`), so importing
layouts executes callbacks first. Each of the two modules independently:

- builds its **own** `pooling.MySQLConnectionPool`, both named `"sports_db_pool"`,
  both `pool_size=5` — 10 connections for one process; and
- runs its own startup query batch at module level
  (`data_imports.optimize_code()` in callbacks, `optimize_code_layouts()` in
  layouts), so the **expensive `espn_query`** — a `UNION ALL` of
  `live_free_agents` with every matching row of `historical_player_data` — runs
  **twice per boot**.

`team_performance.py` then runs its own batch (`data_imports.team_performance_data()`:
league totals since `season_start`, injury curves, roster status, this season's
`hist_player_inj` moves) on the callbacks pool. Boot is ~30 s locally. This is
why the Procfile carries `-t 120 --preload`.

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

### Current Team Performance (page 3)

`app/team_performance.py` owns the whole page. Its layout is `filter_bar()` (league
ESPN/Yahoo + window season/30/14/7 days, both global) plus `tabs_body()`:

- **Team overview**: a player × 12-category heatmap. Cells show per-game values;
  colour is a z-score against **league rotation players** (≥3 GP, ≥20 MPG this
  season, from `league_totals_qry` over `historical_player_data`). FG%/FT%/3P% are
  ranked on volume-weighted impact (makes − league% × attempts) and TO is
  inverted. Below it, under one category picker: minute-weighted production,
  share of team for the latest week, and the weekly trend.
- **Player detail**: box + strip per player (last 5 games coloured), small
  multiples, and a hot/cold table (last 5 vs window average).
- **Injuries**: the players currently out, each a button that loads the matched
  `injury_probabilities` curve with a "day N" marker, plus key-day odds
  conditional on days already out, S(d+k)/S(d).

Injury **status** comes from `live_*_players.injury_status` (ESPN `injuryStatus` /
Yahoo `status`, written by `my_team_stats.py`). That column is added by
`sql_files/migrations/2026-11-07_live_players_injury_status.sql`. Until the
migration runs, `team_performance_data()` falls back to names only and the page
works out "out" from `hist_player_inj` instead (latest `relinquished` after the
last `acquired`). In that mode it prints `1054 Unknown column 'injury_status'`
twice at boot. Injury **type** and days out always come from `hist_player_inj`.
Once `injury_probabilities` holds group curves, the stint's latest note goes
through `injury_note_classification` (else the regex). It falls back from group to
`<region>:other`, then `injury:other`, then `unspecified`, and days out are counted
in in-season days (`days_since`). While the table still holds the old raw-note
curves, the legacy word-overlap matcher and calendar days are used
(`GROUP_CURVES` picks).

Group-bys there use plain sums/`agg`, never `groupby().apply()`, so the code
behaves the same on pandas 1.3.5 and 2.2.3. Don't put `'responsive': True` in the
graph config: Plotly then sizes each chart to its heightless card, the cards
collapse to 0 px and the charts overlap. Each figure sets its own height instead.

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

- **`my_team_stats.py` rebuilds all four of its tables from scratch every run.**
  Per league it replaces the live table with the current roster, then replaces
  the stats table with this season's regular-season game log
  (`regular_season_player_box_scores`, one bbref request per player) for exactly
  the players in the live table. So dropped players vanish, new pickups get
  their whole season, and the first run with a new `season_year` wipes last
  season. There is no incremental `MAX(date)` loop any more. Everything is fetched
  before anything is written, and each table is replaced with `DELETE` + `INSERT`
  in one transaction (not `TRUNCATE`, which can't roll back), so a bbref failure
  leaves the old contents. The ESPN team is found by matching the `swid` env var
  to `team.owners[*].id`, **not** by list index (it used to be `league.teams[i]`,
  which drifted 11 → 10 → 9 → 4 and silently ingested other managers' rosters).
  Live-table names keep their old shape (ESPN suffixes stripped via
  `remove_name_suffixes`, Yahoo raw) because `base_model.py` /
  `machine_learning_models.py` / `model_pooling.py` join them to
  `basketball_references_players.BBRefName`. Stats rows store the **live-table
  spelling** in `name` (the app's Yahoo query filters on `name IN live_yahoo_players`)
  and resolve slugs via a loose `name_key()` against this season's
  `players_season_totals`, falling back to the crosswalk table.
- ⚠️ **Yahoo league keys are hard-coded in `free_agents_yahoo_basketball.py`**
  (`428.l.18598`, 2023-24). It calls `gm.league_ids(year=season_year)` and then
  **throws the result away** on the next line. `my_team_stats.py` already derives
  both keys: `gm.league_ids(year=season_year - 1)` (Yahoo labels a season by its
  **start** year; `season_year` is the end year) and `lg.team_key()` for the
  logged-in user's team. Do the same here instead of editing literals. Neither has
  run since Yahoo access lapsed, so treat the Yahoo path as untested.
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
- ⚠️ **basketball-reference-web-scraper fails SILENTLY when bbref changes its
  HTML** — a parser that can't find its table returns an empty list, not an
  error. bbref renamed the advanced-totals table `advanced_stats` → `advanced`;
  scraper 4.12.1 (what `basketball-env-useme` had) returns **0 rows for every
  season**, while 4.15.4 (pinned in `requirements-dev.txt`) parses it. In
  `advanced_stats.py` that surfaces as `KeyError: 'slug'` at the
  `main_free_agents_df['slug']` line — the frame is still the empty
  `pd.DataFrame()` because no lookup ever matched. Check the env's installed
  version against `requirements-dev.txt` before debugging the script. Box-score
  calls (`player_box_scores`, `regular_season_player_box_scores`) were unaffected
  as of 2026-11-05. A day with 0 box scores may just be a day with no games
  (e.g. Election Day 2026-11-03).
- ⚠️ **`historical_player_data` has no rows from 2025-02-14 to 2025-04-13** (the end
  of the 2024-25 regular season). `historicals.py` needs a backfill over that window
  with the `last_data_date` override. Until then, `injury_mapping.py` treats it as a
  box-score hole: episodes spanning it are censored (`data_gap`) instead of closed by
  a game.
- **Basketball-reference rate-limits hard.** Scripts carry `time.sleep(4)` between
  requests; the comments in `advanced_stats.py` record the measured ceiling
  (~20 requests/min is where blocking starts). Don't lower the delays.
- ⚠️ **Incremental day-loops resume from `MAX(date) + 1`, so a skipped day is
  skipped forever.** Scripts that walk `pd.date_range(MAX(date)+1, yesterday)` and
  catch every exception per day treat "bbref returned 503" the same as "no games
  that day", move on, and load later days, so `MAX(date)` jumps past the hole. On
  2026-11-05 a Sports Reference outage ("Sports Reference is temporarily offline",
  Cloudflare 503 on every page) left 10 missing October/November days in
  `high_level_nba_team_stats` while 5 days in between loaded.
  `high_level_nba_team_stats.py` now catches `requests.exceptions.RequestException`
  separately and **`break`s**, so it halts at the first HTTP failure and the next run
  resumes there. An empty no-game day still surfaces as `KeyError: 'team'` (empty
  frame) and is skipped, which is correct. (`my_team_stats.py` no longer
  day-loops; it rebuilds per player, see above.) Other day-loops
  (`historicals.py`, `free_agents_backfill.py`, …) have not been checked for the
  same hazard. **To backfill a hole**, uncomment the
  `last_data_date='YYYY-MM-DD'` override in the script's `else` branch and set it
  to the day before the gap. Re-loading days that already loaded is safe wherever
  the table's primary key includes `date` (`high_level_nba_team_stats` is
  `(team, date)`), because `LOAD DATA ... REPLACE` overwrites instead of
  duplicating. Remove the override afterwards.
- ⚠️ **`espn-api` 0.46 needs `year` as an `int`.** Its `EspnFantasyRequests` does
  `if year < 2018`, so passing the raw `os.environ.get('season_year')` string raises
  `TypeError: '<' not supported between instances of 'str' and 'int'`. 0.32 (the
  old `basketball-env-useme`) accepted the string, so this surfaced only after
  moving to `basketball-env-useme-v11052026`. Every live pipeline script that
  builds a `League(...)` now does `season_year=int(season_year)` (only the
  reference-only `basketball-work.py` and `my_team_performance_dash.py` don't);
  keep that in any new one.
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
