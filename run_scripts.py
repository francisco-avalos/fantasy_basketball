import sys
import chime

# import subprocess
from subprocess import call


chime.theme('mario')
small_list=['advanced_stats.py', 'high_level_nba_team_schedules.py',
				'high_level_nba_team_stats.py', 'my_team_stats.py',
				'historicals.py']
full_list=['advanced_stats.py', 'high_level_nba_team_schedules.py',
				'high_level_nba_team_stats.py', 'my_team_stats.py',
				'historicals.py',
				'free_agents_backfill.py']

run_fa = input('Execute Free Agents Script?(yes/no) - ')

if run_fa=='yes':
	try:
		print('Begin full list now... \n')
		for script in full_list:
			call(['python', script])
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
			call(['python', script])
			chime.success()
			print('Finished executing - ', script, '\n')
		chime.theme('zelda')
		chime.success()
	except:
		chime.theme('mario')
		chime.error()

