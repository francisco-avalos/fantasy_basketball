
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





