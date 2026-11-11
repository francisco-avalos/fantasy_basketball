import os
import sys
import chime
import time
import shutil
import urllib.request
import urllib.error
import subprocess
import datetime as dt

# import subprocess
from subprocess import call


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
PROSPORTS_PYTHON = os.path.join(ENVS_DIR, 'basketball-prosports-vclaude-env', 'bin', 'python')
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
		return
	ok, opened_docker, started_unflare = start_unflare()
	try:
		scraped = ok and run_step('historical_basketball_injury_data_updated.py',
		                          [PROSPORTS_PYTHON, '-m', 'pipeline.historical_basketball_injury_data_updated'])
	finally:
		stop_unflare(opened_docker, started_unflare)
	if not scraped:
		print('Injury scrape did not finish; skipping injury_mapping and the probabilities refit.')
		chime.error()
		return
	if not run_step('injury_mapping.py', module_cmd('injury_mapping.py')):
		chime.error()
		return
	if probabilities_due():
		if run_step('injury_probabilities_basketball.py', module_cmd('injury_probabilities_basketball.py')):
			with open(PROBABILITIES_STAMP, 'w') as f:
				f.write(dt.date.today().isoformat())
		else:
			chime.error()
	else:
		print(f'injury_probabilities_basketball.py: last run less than {PROBABILITIES_EVERY_DAYS} days ago, skipped')
	chime.success()


chime.theme('mario')
small_list=['advanced_stats.py','high_level_nba_team_schedules.py',
				'high_level_nba_team_stats.py', 'my_team_stats.py',
				'historicals.py', 
				# 'historical_basketball_injury_data.py', # historical_basketball_injury_data_updated
				# 'injury_probabilities_basketball.py',
				# 'free_agents_yahoo_basketball.py',
				'free_agents_backfill.py']
full_list=['advanced_stats.py','high_level_nba_team_schedules.py',
				'high_level_nba_team_stats.py', 'my_team_stats.py',
				'historicals.py',
				# injury scripts run after the list, in run_injury_chain()
				'free_agents_yahoo_basketball.py',
				'free_agents_backfill.py']

run_fa = input('Execute Free Agents Script?(yes/no) - ')

if run_fa=='yes':
	try:
		print('Begin full list now... \n')
		for script in full_list:
			start_time=time.perf_counter()
			print(f'======= Now running: {script}')
			call(module_cmd(script), cwd=REPO_ROOT)
			end_time=time.perf_counter()
			lapsed_time_min=(end_time-start_time)/60
			print(f'{script} took {lapsed_time_min:.02f} minutes to obtain')
			chime.success()
			print('Finished executing - ', script, '\n')
		chime.theme('zelda')
		chime.success()
	except:
		chime.theme('mario')
		chime.error()
elif run_fa=='no':
	try:
		print('Begin small list now... \n')
		for script in small_list:
			start_time=time.perf_counter()
			print(f'======= Now running: {script}')
			call(module_cmd(script), cwd=REPO_ROOT)
			end_time=time.perf_counter()
			lapsed_time_min=(end_time-start_time)/60
			print(f'{script} took {lapsed_time_min:.02f} minutes to obtain')
			chime.success()
			print('Finished executing - ', script, '\n')
		chime.theme('zelda')
		chime.success()
	except:
		chime.theme('mario')
		chime.error()

if run_fa in ('yes', 'no'):
	run_injury_chain()
