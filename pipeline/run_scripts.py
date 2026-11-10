import os
import sys
import chime
import time

# import subprocess
from subprocess import call


# Each script runs as `python -m pipeline.<name>` from the repo root, which is what the
# scripts' `from shared...` imports and relative paths (oauth2.json) need. A bare filename
# resolved against the shell's cwd and failed with "No such file or directory".
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def module_cmd(script):
	return [sys.executable, '-m', 'pipeline.' + script[:-len('.py')]]


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
				'historical_basketball_injury_data_updated.py',
				'injury_probabilities_basketball.py',
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

