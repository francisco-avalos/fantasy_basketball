
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


exec(open('/Users/franciscoavalosjr/Desktop/basketball-creds.py').read())

league=League(league_id=leagueid, 
				year=2023,
				espn_s2=espn_s2,
				swid=swid, 
				debug=False)


### Definitions used
def remove_team_string(item):
	output = item.replace('Team(', '')
	output = output.replace(')', '')
	output = output.replace('[', '').replace(']','')
	output.lstrip()
	return output

def remove_matchup_string(item):
	output = item.replace('Matchup(', '')
	output = output.replace(')', '')
	output = output.replace('[', '').replace(']','')
	output.lstrip()
	return output

def remove_activity_string(item):
	output = item.replace('Activity(', '')
	output = output.replace(')', '')
	output = output.replace('[', '').replace(']','')
	output.lstrip()
	return output


def remove_player_string(item):
	output = item.replace('Player(', '')
	output = output.replace(')', '')
	output = output.replace(', points:0', '')
	output = output.replace('[', '').replace(']','')
	output.lstrip()
	return output

def remove_box_string(item):
	output = item.replace('Box Score(', '')
	output = output.replace(')', '')
	output = output.replace('[', '').replace(']','')
	output.lstrip()
	return output

def clean_string(item):
	item=str(item)
	item=remove_team_string(item)
	item=remove_matchup_string(item)
	item=remove_activity_string(item)
	item=remove_player_string(item)
	item=remove_box_string(item)
	return item

def remove_jr(item):
	item=str(item)
	item=item.replace('Jr.','')
	item=item.replace('II','')
	item=item.replace('III','')
	item=item.replace('IV','')
	item=item.replace('Sr.','')
	return item

def convert_game_score_to_points(GS, FG, FGA, FTA, FT, ORB, DRB, STL, AST, BLK, PF, TOV):
	"""
		Obtain a player's points per game by
		inverting John Hollinger's game score measure.
		John Hollinger's Game Score = PTS + 0.4 * FG - 0.7 * FGA - 0.4*(FTA - FT) + 0.7 * ORB + 0.3 * DRB + STL + 0.7 * AST + 0.7 * BLK - 0.4 * PF - TOV. 
	"""
	PTS=GS - 0.4 * FG + 0.7 * FGA + 0.4*(FTA - FT) - 0.7 * ORB - 0.3 * DRB - STL - 0.7 * AST - 0.7 * BLK + 0.4 * PF + TOV
	return PTS

season_end_year=2023

try:
	connection=mysql.connect(host=sports_db_admin_host,
							database=sports_db_admin_db,
							user=sports_db_admin_user,
							password=sports_db_admin_pw,
							port=sports_db_admin_port)
	if connection.is_connected():
		cursor=connection.cursor()
		sql='TRUNCATE basketball.high_level_nba_team_schedules;'
		cursor.execute(sql)
		output=cursor.fetchone()

	df=client.season_schedule(season_end_year=season_end_year)
	df=pd.DataFrame(df)
	df['start_time']=df['start_time'].astype(str)
	df['away_team']=df['away_team'].astype(str)
	df['home_team']=df['home_team'].astype(str)
	cols="`,`".join([str(i) for i in df.columns.tolist()])
	for i, row in df.iterrows():
		sql='REPLACE INTO `high_level_nba_team_schedules` (`'+cols+'`) VALUES ('+'%s, '*(len(row)-1)+'%s)'
		cursor.execute(sql, tuple(row))
		connection.commit()
	
	print('Finished updating high_level_nba_team_schedules table')

	if(connection.is_connected()):
		cursor.close()
		connection.close()
		print('MySQL connection closed')

except Error as e:
	print("Error while connecting to MySQL", e)

finally:
	if(connection.is_connected()):
		cursor.close()
		connection.close()
		print('MySQL connection is closed')





