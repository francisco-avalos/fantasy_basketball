
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


try:
	connection=mysql.connect(**config)
	if connection.is_connected():
		cursor=connection.cursor()
		sql='TRUNCATE basketball.high_level_nba_team_schedules;'
		cursor.execute(sql)
		output=cursor.fetchone()

	df=client.season_schedule(season_end_year=season_year)
	df=pd.DataFrame(df)
	df['start_time']=df['start_time'].astype(str)
	df['away_team']=df['away_team'].astype(str)
	df['home_team']=df['home_team'].astype(str)

	file_path='/Users/franciscoavalosjr/Desktop/basketball-folder/tmp_data/high_level_nba_team_scheds.csv'
	df.to_csv(file_path, index=False)
	qry=f"LOAD DATA LOCAL INFILE '{file_path}' REPLACE INTO TABLE basketball.high_level_nba_team_schedules FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '\"' IGNORE 1 ROWS;"
	cursor.execute(qry)
	connection.commit()
	del df
	os.remove(file_path)

	# cols="`,`".join([str(i) for i in df.columns.tolist()])
	# for i, row in df.iterrows():
	# 	sql='REPLACE INTO `high_level_nba_team_schedules` (`'+cols+'`) VALUES ('+'%s, '*(len(row)-1)+'%s)'
	# 	cursor.execute(sql, tuple(row))
	# 	connection.commit()
	
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





