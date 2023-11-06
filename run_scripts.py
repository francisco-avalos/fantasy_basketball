import sys
import chime
import time

# import subprocess
from subprocess import call


chime.theme('mario')
small_list=['high_level_nba_team_schedules.py',
				'high_level_nba_team_stats.py', 'my_team_stats.py',
				'historicals.py', 'historical_basketball_injury_data.py',
				'injury_probabilities_basketball.py',
				'free_agents_yahoo_basketball.py']
full_list=['advanced_stats.py', 'high_level_nba_team_schedules.py',
				'high_level_nba_team_stats.py', 'my_team_stats.py',
				'historicals.py',
				'historical_basketball_injury_data.py',
				'injury_probabilities_basketball.py',
				'free_agents_yahoo_basketball.py',
				'free_agents_backfill.py']	

run_fa = input('Execute Free Agents Script?(yes/no) - ')

if run_fa=='yes':
	try:
		print('Begin full list now... \n')
		for script in full_list:
			start_time=time.perf_counter()
			call(['python', script])
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
			call(['python', script])
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

