"""The nightly refresh: every ETL script, then the injury chain, then the points forecast (last: it reads the
day's box scores, rosters, ESPN injury snapshot and injury episodes).

    python -m pipeline.run_scripts                  # asks whether to run the Yahoo free-agent script
    python -m pipeline.run_scripts --list small     # no prompt: skip free_agents_yahoo_basketball
    python -m pipeline.run_scripts --list full      # no prompt: include it

Exits 1 if any step failed, so a scheduler (GitHub Actions: .github/workflows/nightly-pipeline.yml)
marks the run as failed. On Linux / CI it expects Docker and the unflare container to be started by
the caller; PROSPORTS_PYTHON names the interpreter for the injury scrape there.
"""
import os
import sys
import time
import argparse
import platform
import shutil
import urllib.request
import urllib.error
import subprocess
import datetime as dt

CI = os.environ.get('CI') == 'true'
MAC = platform.system() == 'Darwin'


class _Quiet:
	"""Stands in for chime where there's no one to hear it (CI) or chime isn't installed."""
	def theme(self, *a): pass
	def success(self, *a): pass
	def error(self, *a): pass


try:
	import chime
	if CI:
		chime = _Quiet()
except ImportError:
	chime = _Quiet()


# Each script runs as `python -m pipeline.<name>` from the repo root, which is what the
# scripts' `from shared...` imports and relative paths (oauth2.json) need. A bare filename
# resolved against the shell's cwd and failed with "No such file or directory".
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def module_cmd(script):
	return [sys.executable, '-m', 'pipeline.' + script[:-len('.py')]]


# ---------------------------------------------------------------------------
# Injury chain, run after either list (it needs last night's box scores from historicals.py):
#   1. historical_basketball_injury_data_updated  in basketball-prosports-vclaude-env, which
#      needs the Unflare container, which needs Docker Desktop: both are started here if needed
#   2. injury_mapping                              in this env (basketball-env-useme-v11052026)
#   3. injury_probabilities_basketball             in this env, at most once every 30 days
# Docker / Unflare are put back the way they were found (stopped, quit) when the chain ends.
# ---------------------------------------------------------------------------
ENVS_DIR = os.path.dirname(os.path.dirname(os.path.dirname(sys.executable)))   # .../anaconda3/envs
PROSPORTS_PYTHON = (os.environ.get('PROSPORTS_PYTHON')
                    or os.path.join(ENVS_DIR, 'basketball-prosports-vclaude-env', 'bin', 'python'))
DOCKER = shutil.which('docker') or '/usr/local/bin/docker'
UNFLARE_PORT = 5002
PROBABILITIES_EVERY_DAYS = 30
PROBABILITIES_STAMP = os.path.join(REPO_ROOT, 'tmp_data', 'injury_probabilities_last_run.txt')


def docker_up():
	return subprocess.run([DOCKER, 'info'], capture_output=True).returncode == 0


def unflare_ready():
	"""True once the Unflare server itself answers HTTP. An open port isn't enough: Docker accepts
	connections on 5002 as soon as the container starts, ~1 s before the server inside listens, and
	those first requests are reset. pro_sports_transactions logs a reset but returns an empty page,
	which the scrape's pre-flight then reports as 'no rows'."""
	try:
		urllib.request.urlopen(f'http://localhost:{UNFLARE_PORT}/', timeout=3)
		return True
	except urllib.error.HTTPError:          # any HTTP status (e.g. 404 on /) means the server is up
		return True
	except Exception:                       # refused, reset, closed without a response, timeout
		return False


def wait_for(check, seconds, what):
	for _ in range(seconds // 2):
		if check():
			return True
		time.sleep(2)
	print(f'{what} not ready after {seconds} s')
	return False


def start_unflare():
	"""Docker Desktop + the unflare container. Returns (ok, opened_docker, started_unflare)."""
	opened_docker = started_unflare = False
	if not docker_up():
		if not MAC:
			print('Docker is not running (start the daemon / the unflare container before this script)')
			return False, opened_docker, started_unflare
		print('Starting Docker Desktop...')
		subprocess.run(['open', '-g', '-a', 'Docker'])
		opened_docker = True
		if not wait_for(docker_up, 180, 'Docker Desktop'):
			return False, opened_docker, started_unflare
	if not unflare_ready():
		print('Starting the unflare container...')
		r = subprocess.run([DOCKER, 'start', 'unflare'], capture_output=True, text=True)
		if r.returncode != 0:
			print(f'docker start unflare failed: {r.stderr.strip()}')
			return False, opened_docker, started_unflare
		started_unflare = True
		if not wait_for(unflare_ready, 60, f'Unflare on port {UNFLARE_PORT}'):
			return False, opened_docker, started_unflare
	return True, opened_docker, started_unflare


def stop_unflare(opened_docker, started_unflare):
	if started_unflare:
		subprocess.run([DOCKER, 'stop', 'unflare'], capture_output=True)
	if opened_docker:
		subprocess.run(['osascript', '-e', 'quit app "Docker"'], capture_output=True)


def run_step(name, cmd):
	"""Run one step, report its time and whether it worked (exit code, not a try/except)."""
	print(f'======= Now running: {name}')
	start_time = time.perf_counter()
	ok = subprocess.run(cmd, cwd=REPO_ROOT).returncode == 0
	print(f'{name} took {(time.perf_counter() - start_time) / 60:.02f} minutes · {"OK" if ok else "FAILED"}\n')
	return ok


def probabilities_due():
	try:
		last = dt.date.fromisoformat(open(PROBABILITIES_STAMP).read().strip())
	except (OSError, ValueError):
		return True
	return (dt.date.today() - last).days >= PROBABILITIES_EVERY_DAYS


def run_injury_chain():
	print('======= Injury data\n')
	if not os.path.exists(PROSPORTS_PYTHON):
		print(f'Skipping injury data: {PROSPORTS_PYTHON} not found')
		return False
	ok, opened_docker, started_unflare = start_unflare()
	try:
		scraped = ok and run_step('historical_basketball_injury_data_updated.py',
		                          [PROSPORTS_PYTHON, '-m', 'pipeline.historical_basketball_injury_data_updated'])
	finally:
		stop_unflare(opened_docker, started_unflare)
	if not scraped:
		print('Injury scrape did not finish; skipping injury_mapping and the probabilities refit.')
		chime.error()
		return False
	if not run_step('injury_mapping.py', module_cmd('injury_mapping.py')):
		chime.error()
		return False
	if probabilities_due():
		if run_step('injury_probabilities_basketball.py', module_cmd('injury_probabilities_basketball.py')):
			with open(PROBABILITIES_STAMP, 'w') as f:
				f.write(dt.date.today().isoformat())
		else:
			chime.error()
			return False
	else:
		print(f'injury_probabilities_basketball.py: last run less than {PROBABILITIES_EVERY_DAYS} days ago, skipped')
	# one survival curve per player out today, from the published champion (refit nightly, ~5 s)
	if not run_step('injury_player_curves.py', module_cmd('injury_player_curves.py')):
		chime.error()
		return False
	chime.success()
	return True


chime.theme('mario')
small_list=['advanced_stats.py','high_level_nba_team_schedules.py',
				'high_level_nba_team_stats.py', 'my_team_stats.py',
				'historicals.py',
				'espn_player_positions.py',  # positions + today's ESPN injury snapshot (slugs from the box scores above)
				# points_forecast.py runs after the injury chain, in main()
				# 'historical_basketball_injury_data.py', # historical_basketball_injury_data_updated
				# 'injury_probabilities_basketball.py',
				# 'free_agents_yahoo_basketball.py',
				'free_agents_backfill.py']
full_list=['advanced_stats.py','high_level_nba_team_schedules.py',
				'high_level_nba_team_stats.py', 'my_team_stats.py',
				'historicals.py',
				'espn_player_positions.py',
				# injury scripts run after the list, in run_injury_chain(); points_forecast.py after those
				'free_agents_yahoo_basketball.py',
				'free_agents_backfill.py']


def main():
	ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
	ap.add_argument('--list', choices=['small', 'full'],
	                help='small = skip the Yahoo free-agent script, full = include it (default: ask)')
	args = ap.parse_args()
	choice = args.list
	if choice is None:
		if not sys.stdin.isatty():
			ap.error('--list small|full is required when not run from a terminal')
		answer = input('Execute Free Agents Script?(yes/no) - ')
		choice = {'yes': 'full', 'no': 'small'}.get(answer)
		if choice is None:
			return 0

	scripts = full_list if choice == 'full' else small_list
	print(f'Begin {choice} list now... \n')
	failed = []
	for script in scripts:
		# run_step checks the exit code; subprocess.call() never raises, so a try/except can't see a failure
		if run_step(script, module_cmd(script)):
			chime.success()
		else:
			failed.append(script)
			chime.error()
	if not run_injury_chain():
		failed.append('injury chain')
	# last: needs the box scores, rosters and ESPN snapshot above, and the injury episodes. Runs even when the
	# injury chain failed (it then uses yesterday's episodes).
	if run_step('points_forecast.py', module_cmd('points_forecast.py')):
		chime.success()
	else:
		failed.append('points_forecast.py')
		chime.error()
	if failed:
		print('FAILED: ' + ', '.join(failed))
		chime.theme('mario')
		chime.error()
		return 1
	print('All steps finished OK')
	chime.theme('zelda')
	chime.success()
	return 0


if __name__ == '__main__':
	sys.exit(main())
