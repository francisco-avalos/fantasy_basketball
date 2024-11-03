
# ESPN
from espn_api.basketball import League
from espn_api.basketball import Player

# basketball-reference
from basketball_reference_web_scraper import client

# Connection to my DB
import mysql.connector as mysql
from mysql.connector import Error


import pandas as pd
import os
import time 
from datetime import datetime
from datetime import date
from datetime import timedelta	



## Preliminaries, set ups & initiators 
pd.set_option('display.max_columns', None)
pd.set_option('display.max_rows', None)


sports_db_admin_host=os.environ.get('sports_db_admin_host')
sports_db_admin_db='basketball'
sports_db_admin_user=os.environ.get('sports_db_admin_user')
sports_db_admin_pw=os.environ.get('sports_db_admin_pw')
sports_db_admin_port=os.environ.get('sports_db_admin_port')
season_year=os.environ.get('season_year')

config={
	'host':sports_db_admin_host,
	'database':sports_db_admin_db,
	'user':sports_db_admin_user,
	'password':sports_db_admin_pw,
	'port':sports_db_admin_port,
	'allow_local_infile':True
}


leagueid=os.environ.get('leagueid')
espn_s2=os.environ.get('espn_s2')
swid=os.environ.get('swid')

league=League(league_id=leagueid, 
				year=season_year,
				espn_s2=espn_s2,
				swid=swid, 
				debug=False)


# ### Definitions used
# def remove_team_string(item):
# 	output = item.replace('Team(', '')
# 	output = output.replace(')', '')
# 	output = output.replace('[', '').replace(']','')
# 	output.lstrip()
# 	return output

# def remove_matchup_string(item):
# 	output = item.replace('Matchup(', '')
# 	output = output.replace(')', '')
# 	output = output.replace('[', '').replace(']','')
# 	output.lstrip()
# 	return output

# def remove_activity_string(item):
# 	output = item.replace('Activity(', '')
# 	output = output.replace(')', '')
# 	output = output.replace('[', '').replace(']','')
# 	output.lstrip()
# 	return output


# def remove_player_string(item):
# 	output = item.replace('Player(', '')
# 	output = output.replace(')', '')
# 	output = output.replace(', points:0', '')
# 	output = output.replace('[', '').replace(']','')
# 	output.lstrip()
# 	return output

# def remove_box_string(item):
# 	output = item.replace('Box Score(', '')
# 	output = output.replace(')', '')
# 	output = output.replace('[', '').replace(']','')
# 	output.lstrip()
# 	return output

# def clean_string(item):
# 	item=str(item)
# 	item=remove_team_string(item)
# 	item=remove_matchup_string(item)
# 	item=remove_activity_string(item)
# 	item=remove_player_string(item)
# 	item=remove_box_string(item)
# 	return item

# def remove_jr(item):
# 	item=str(item)
# 	item=item.replace('Jr.','')
# 	item=item.replace('II','')
# 	item=item.replace('III','')
# 	item=item.replace('IV','')
# 	item=item.replace('Sr.','')
# 	return item

# def convert_game_score_to_points(GS, FG, FGA, FTA, FT, ORB, DRB, STL, AST, BLK, PF, TOV):
# 	"""
# 		Obtain a player's points per game by
# 		inverting John Hollinger's game score measure.
# 		John Hollinger's Game Score = PTS + 0.4 * FG - 0.7 * FGA - 0.4*(FTA - FT) + 0.7 * ORB + 0.3 * DRB + STL + 0.7 * AST + 0.7 * BLK - 0.4 * PF - TOV. 
# 	"""
# 	PTS=GS - 0.4 * FG + 0.7 * FGA + 0.4*(FTA - FT) - 0.7 * ORB - 0.3 * DRB - STL - 0.7 * AST - 0.7 * BLK + 0.4 * PF + TOV
# 	return PTS




try:
	connection=mysql.connect(**config)
	if connection.is_connected():
		cursor=connection.cursor()
		sql='SELECT MAX(date) AS most_recent_data_date FROM basketball.high_level_nba_team_stats;'
		cursor.execute(sql)
		output=cursor.fetchone()
		
	if output[0] is None:

		### new true stuff
		season_begin='2024-10-24'
		last_data_date=datetime.strptime(season_begin, '%Y-%m-%d')
		today=datetime.now()-timedelta(days=1)
		today=today.strftime('%Y-%m-%d')
		day_range=pd.date_range(start=last_data_date, end=today)


		for day in day_range:
			try:
				df=client.team_box_scores(day=day.day, month=day.month, year=day.year)
				df=pd.DataFrame(df)
				date=day.strftime('%Y-%m-%d')
				df['date']=date
				df['team']=df['team'].astype(str)
				df['outcome']=df['outcome'].astype(str)

				connection=mysql.connect(**config)

				if connection.is_connected():
					cursor=connection.cursor()

					file_path='/Users/franciscoavalosjr/Desktop/basketball-folder/tmp_data/high_level_nba_team_stats.csv'
					df.to_csv(file_path,index=False)
					qry=f"LOAD DATA LOCAL INFILE '{file_path}' REPLACE INTO TABLE basketball.high_level_nba_team_stats FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '\"' IGNORE 1 ROWS;"
					cursor.execute(qry)
					connection.commit()
					del df
					os.remove(file_path)

				if(connection.is_connected()):
					cursor.close()
					connection.close()
					print('MySQL connection closed')
			except:
				print(f'No game for {day}')


				# file_path='/Users/franciscoavalosjr/Desktop/basketball-folder/tmp_data/advanced_data_extract.csv'
				# main_free_agents_df.to_csv(file_path,index=False)
				# qry=f"LOAD DATA LOCAL INFILE '{file_path}' REPLACE INTO TABLE basketball.advanced_stats FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '\"' IGNORE 1 ROWS;"
				# cursor.execute(qry)
				# connection.commit()
				# del main_free_agents_df
				# os.remove(file_path)

			# cols="`,`".join([str(i) for i in df.columns.tolist()])
			# for i,row in df.iterrows():
			# 	sql='REPLACE INTO `high_level_nba_team_stats` (`'+cols+'`) VALUES ('+'%s, '*(len(row)-1)+'%s)'
			# 	cursor.execute(sql, tuple(row))
			# 	connection.commit()
			time.sleep(4)
			print(f'finished for {date}')
		### new true stuff
	else:
		last_data_date=output[0]
		# last_data_date='2023-10-23'
		last_data_date=datetime.strptime(str(last_data_date), '%Y-%m-%d')
		next_date_date=last_data_date+timedelta(days=1)
		today=datetime.now()-timedelta(days=1)
		today=today.strftime('%Y-%m-%d')
		day_range=pd.date_range(start=next_date_date, end=today)
		# print(day_range)

		# connection=mysql.connect(host=sports_db_admin_host,
		# 						database=sports_db_admin_db,
		# 						user=sports_db_admin_user,
		# 						password=sports_db_admin_pw,
		# 						port=sports_db_admin_port,
		# 						allow_local_infile=True)

		# if connection.is_connected():
		# 	cursor=connection.cursor()
		for day in day_range:
			try:
				df=client.team_box_scores(day=day.day, month=day.month, year=day.year)
				df=pd.DataFrame(df)
				date=day.strftime('%Y-%m-%d')
				df['date']=date
				df['team']=df['team'].astype(str)
				df['outcome']=df['outcome'].astype(str)
				# print(df.head())
				connection=mysql.connect(**config)
				if connection.is_connected():
					cursor=connection.cursor()
					file_path='/Users/franciscoavalosjr/Desktop/basketball-folder/tmp_data/high_level_nba_team_stats.csv'
					df.to_csv(file_path,index=False)
					qry=f"LOAD DATA LOCAL INFILE '{file_path}' REPLACE INTO TABLE basketball.high_level_nba_team_stats FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '\"' IGNORE 1 ROWS;"
					cursor.execute(qry)
					connection.commit()
					del df
					os.remove(file_path)
				if(connection.is_connected()):
					cursor.close()
					connection.close()				
			except:
				print(f'No game for {day}')

				# print('MySQL connection closed')
			# if not df.empty:
			# 	print(df.shape)
			# 	df['date']=date
			# 	df['team']=df['team'].astype(str)
			# 	df['outcome']=df['outcome'].astype(str)

			# 	file_path='/Users/franciscoavalosjr/Desktop/basketball-folder/tmp_data/high_level_nba_team_stats.csv'
			# 	df.to_csv(file_path,index=False)
			# 	qry=f"LOAD DATA LOCAL INFILE '{file_path}' REPLACE INTO TABLE basketball.high_level_nba_team_stats FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '\"' IGNORE 1 ROWS;"
			# 	cursor.execute(qry)
			# 	connection.commit()
			# 	del df
			# 	os.remove(file_path)

				# cols="`,`".join([str(i) for i in df.columns.tolist()])
				# for i,row in df.iterrows():
				# 	sql='REPLACE INTO `high_level_nba_team_stats` (`'+cols+'`) VALUES ('+'%s, '*(len(row)-1)+'%s)'
				# 	cursor.execute(sql, tuple(row))
				# 	connection.commit()
			print(f'finished for {date}')
			time.sleep(5)
		# if(connection.is_connected()):
		# 	cursor.close()
		# 	connection.close()
		# 	print('MySQL connection closed')

except Error as e:
	print("Error while connecting to MySQL", e)


finally:
	if(connection.is_connected()):
		cursor.close()
		connection.close()
		print('MySQL connection is closed')





