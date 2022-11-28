import sys
import subprocess


small_list=['advanced_stats.py', 'high_level_nba_team_schedules.py',
				'high_level_nba_team_stats.py', 'my_team_stats.py']
full_list=['advanced_stats.py', 'high_level_nba_team_schedules.py',
				'high_level_nba_team_stats.py', 'my_team_stats.py',
				'free_agents_backfill.py']
# free_agents_alone='free_agents_backfill.py'


run_fa = input('Execute Free Agents Scrtipt?(yes/no) - ')

if run_fa=='yes':
	print('Begin full list now... \n')
	for script in full_list:
		subprocess.call(['python', script])
		print('Finished executing - ', script)
elif run_fa=='no':
	print('Begin small list now... \n')
	for script in small_list:
		subprocess.call(['python', script])
		print('Finished executing - ', script)
