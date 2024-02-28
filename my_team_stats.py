
# ESPN
from espn_api.basketball import League
from espn_api.basketball import Player

# Yahoo
from yahoo_oauth import OAuth2
import yahoo_fantasy_api as yfa

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
from my_functions import clean_string, remove_jr, convert_game_score_to_points

from unidecode import unidecode

from my_functions import clean_string, remove_name_suffixes

## Preliminaries, set ups & initiators 
pd.set_option('display.max_columns', None)
pd.set_option('display.max_rows', None)


sports_db_admin_host=os.environ.get('sports_db_admin_host')
sports_db_admin_db='basketball'
sports_db_admin_user=os.environ.get('sports_db_admin_user')
sports_db_admin_pw=os.environ.get('sports_db_admin_pw')
sports_db_admin_port=os.environ.get('sports_db_admin_port')

leagueid=os.environ.get('leagueid')
espn_s2=os.environ.get('espn_s2')
swid=os.environ.get('swid')

league=League(league_id=leagueid, 
				year=2024,
				espn_s2=espn_s2,
				swid=swid, 
				debug=False)



myteam=league.teams[10]
my_players=clean_string(myteam.roster).split(',')

espn_current_players=[remove_name_suffixes(x) for x in my_players]
espn_current_players=[x.strip(' ') for x in espn_current_players]

espn_current_players=pd.DataFrame(espn_current_players)
espn_current_players.columns=['name']


sc=OAuth2(None,None,from_file='oauth2.json')
gm=yfa.Game(sc, 'nba')
# league_id=gm.league_ids(year=2024)
lg=gm.to_league('428.l.18598')

tm=lg.to_team('428.l.18598.t.4')
my_tm=pd.DataFrame(tm.roster())
my_players_yh=my_tm.name.tolist()




my_players_yh_cp=pd.DataFrame(my_players_yh).copy()
my_players_yh_cp.columns=['name']

connection=mysql.connect(host=sports_db_admin_host,
						database=sports_db_admin_db,
						user=sports_db_admin_user,
						password=sports_db_admin_pw,
						port=sports_db_admin_port,
						allow_local_infile=True)

if connection.is_connected():
	cursor=connection.cursor()
	cursor.execute('TRUNCATE basketball.live_yahoo_players;')
	cursor.execute('TRUNCATE basketball.live_espn_players;')

	file_path='/Users/franciscoavalosjr/Desktop/basketball-folder/tmp_data/live_yh_team.csv'
	my_players_yh_cp.to_csv(file_path,index=False)
	qry=f"LOAD DATA LOCAL INFILE '{file_path}' REPLACE INTO TABLE basketball.live_yahoo_players FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '\"' IGNORE 1 ROWS;"
	cursor.execute(qry)
	connection.commit()
	del my_players_yh_cp
	os.remove(file_path)
	print('live_yahoo_players updated with recent data')

	file_path='/Users/franciscoavalosjr/Desktop/basketball-folder/tmp_data/live_ESPN_team.csv'
	espn_current_players.to_csv(file_path,index=False)
	qry=f"LOAD DATA LOCAL INFILE '{file_path}' REPLACE INTO TABLE basketball.live_espn_players FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '\"' IGNORE 1 ROWS;"
	cursor.execute(qry)
	connection.commit()
	del espn_current_players
	os.remove(file_path)
	print('live_espn_players updated with recent data')

if(connection.is_connected()):
	cursor.close()
	connection.close()



try:
	connection=mysql.connect(host=sports_db_admin_host,
							database=sports_db_admin_db,
							user=sports_db_admin_user,
							password=sports_db_admin_pw,
							port=sports_db_admin_port)

	if connection.is_connected():
		cursor=connection.cursor()
		sql='SELECT MAX(date) AS most_recent_data_date FROM basketball.my_team_stats;'
		cursor.execute(sql)
		output=cursor.fetchone()

		sql='SELECT MAX(date) AS most_recent_data_date FROM basketball.my_team_stats_yahoo;'
		cursor.execute(sql)
		output_yh=cursor.fetchone()

		# if(connection.is_connected()):
		# 	cursor.close()
		# 	connection.close()

		if output[0] is None:
			season_begin='2023-10-24'
			last_data_date=datetime.strptime(season_begin, '%Y-%m-%d')
			today=datetime.now()-timedelta(days=1)
			today=today.strftime('%Y-%m-%d')

			if last_data_date!=today:

				main_df=pd.DataFrame()
				
				day_range=pd.date_range(start=last_data_date, end=today)
				for day in day_range:
					year=int(datetime.strftime(day.date(), '%Y'))
					month=int(datetime.strftime(day.date(), '%m'))
					date=int(datetime.strftime(day.date(), '%d'))

					try:
						p=client.player_box_scores(day=date,month=month,year=year)
						df=pd.DataFrame(p)
						df_name_list=df.name.tolist()
						name_list=[unidecode(name) for name in df_name_list]
						df['name']=name_list
						date=f'{year}-{month}-{date}'
						if not df.empty:
							df.insert(0, 'date', date)
							for p in my_players:
								p=unidecode(p)
								p=remove_jr(p)
								p=p.lstrip().rstrip()
								insert_df=df[df['name']==p]
								GS=insert_df['game_score']
								FG=insert_df['made_field_goals']
								FGA=insert_df['attempted_field_goals']
								FTA=insert_df['attempted_free_throws']
								FT=insert_df['made_free_throws']
								ORB=insert_df['offensive_rebounds']
								DRB=insert_df['defensive_rebounds']
								STL=insert_df['steals']
								AST=insert_df['assists']
								BLK=insert_df['blocks']
								PF=insert_df['personal_fouls']
								TOV=insert_df['turnovers']						
								points=convert_game_score_to_points(GS=GS, FG=FG, FGA=FGA, FTA=FTA, FT=FT, ORB=ORB, DRB=DRB, STL=STL, AST=AST, BLK=BLK, PF=PF, TOV=TOV)
								copy=insert_df.copy()
								copy.loc[copy['date']==date, 'points']=points
								main_df=pd.concat([main_df, copy])
					except:
						print('Player not found')
					time.sleep(4)
				main_df['slug']=main_df['slug'].astype(str)
				main_df['name']=main_df['name'].astype(str)
				main_df['team']=main_df['team'].astype(str)
				main_df['location']=main_df['location'].astype(str)
				main_df['opponent']=main_df['opponent'].astype(str)
				main_df['outcome']=main_df['outcome'].astype(str)

				connection=mysql.connect(host=sports_db_admin_host,
										database=sports_db_admin_db,
										user=sports_db_admin_user,
										password=sports_db_admin_pw,
										port=sports_db_admin_port,
										allow_local_infile=True)
				cursor=connection.cursor()

				file_path='/Users/franciscoavalosjr/Desktop/basketball-folder/tmp_data/my_team_stats_extract.csv'
				main_df.to_csv(file_path,index=False)
				qry=f"LOAD DATA LOCAL INFILE '{file_path}' REPLACE INTO TABLE basketball.my_team_stats FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '\"' IGNORE 1 ROWS;"
				cursor.execute(qry)
				connection.commit()
				del main_df
				os.remove(file_path)


				# cols="`,`".join([str(i) for i in main_df.columns.tolist()])
				# for i,row in main_df.iterrows():
				# 	sql='REPLACE INTO `my_team_stats` (`'+cols+'`) VALUES ('+'%s,'*(len(row)-1)+'%s)'
				# 	cursor.execute(sql, tuple(row))
				# 	connection.commit()

				print('Backfill to basketball.my_team_stats table complete!')
		else:
			print(f'basketball.my_team_stats, data through {output[0]}')
			last_data_date=output[0].strftime('%Y-%m-%d')
			today=datetime.now()-timedelta(days=1)
			today=today.strftime('%Y-%m-%d')

			last_data_day=output[0].strftime('%d')
			last_data_month=output[0].strftime('%m')
			last_data_year=output[0].strftime('%Y')

			yesterday=datetime.now()-timedelta(days=1)
			yesterday_day=yesterday.strftime('%d')
			yesterday_month=yesterday.strftime('%m')
			yesterday_year=yesterday.now().strftime('%Y')
			yesterday=yesterday.strftime('%Y-%m-%d')

			if last_data_date!=yesterday:
				print('New data! Preparing to add data!')
				main_df=pd.DataFrame()
				last_data_date=datetime.strptime(last_data_date, '%Y-%m-%d')
				
				day_range=pd.date_range(start=last_data_date, end=yesterday)
				for day in day_range:
					year=int(datetime.strftime(day.date(), '%Y'))
					month=int(datetime.strftime(day.date(), '%m'))
					date=int(datetime.strftime(day.date(), '%d'))

					try:
						p=client.player_box_scores(day=date,month=month,year=year)
						df=pd.DataFrame(p)
						df_name_list=df.name.tolist()
						name_list=[unidecode(name) for name in df_name_list]
						df['name']=name_list
						date=f'{year}-{month}-{date}'
						if not df.empty:
							df.insert(0, 'date', date)
							for p in my_players:
								p=unidecode(p)
								p=remove_jr(p)
								p=p.lstrip().rstrip()
								insert_df=df[df['name']==p]
								GS=insert_df['game_score']
								FG=insert_df['made_field_goals']
								FGA=insert_df['attempted_field_goals']
								FTA=insert_df['attempted_free_throws']
								FT=insert_df['made_free_throws']
								ORB=insert_df['offensive_rebounds']
								DRB=insert_df['defensive_rebounds']
								STL=insert_df['steals']
								AST=insert_df['assists']
								BLK=insert_df['blocks']
								PF=insert_df['personal_fouls']
								TOV=insert_df['turnovers']						
								points=convert_game_score_to_points(GS=GS, FG=FG, FGA=FGA, FTA=FTA, FT=FT, ORB=ORB, DRB=DRB, STL=STL, AST=AST, BLK=BLK, PF=PF, TOV=TOV)
								copy=insert_df.copy()
								copy.loc[copy['date']==date, 'points']=points
								main_df=pd.concat([main_df, copy])
					except:
						print('Player not found')
					time.sleep(4)

				main_df['slug']=main_df['slug'].astype(str)
				main_df['name']=main_df['name'].astype(str)
				main_df['team']=main_df['team'].astype(str)
				main_df['location']=main_df['location'].astype(str)
				main_df['opponent']=main_df['opponent'].astype(str)
				main_df['outcome']=main_df['outcome'].astype(str)

				connection=mysql.connect(host=sports_db_admin_host,
										database=sports_db_admin_db,
										user=sports_db_admin_user,
										password=sports_db_admin_pw,
										port=sports_db_admin_port,
										allow_local_infile=True)
				cursor=connection.cursor()
				file_path='/Users/franciscoavalosjr/Desktop/basketball-folder/tmp_data/my_team_stats_extract.csv'
				main_df.to_csv(file_path,index=False)
				qry=f"LOAD DATA LOCAL INFILE '{file_path}' REPLACE INTO TABLE basketball.my_team_stats FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '\"' IGNORE 1 ROWS;"
				cursor.execute(qry)
				connection.commit()
				del main_df
				os.remove(file_path)
				
				# cols="`,`".join([str(i) for i in main_df.columns.tolist()])
				
				# for i,row in main_df.iterrows():
				# 	sql='REPLACE INTO `my_team_stats` (`'+cols+'`) VALUES ('+'%s,'*(len(row)-1)+'%s)'
				# 	cursor.execute(sql, tuple(row))
				# 	connection.commit()
				
				cursor=connection.cursor()
				sql='SELECT MAX(date) AS most_recent_data_date FROM basketball.my_team_stats;'
				cursor.execute(sql)
				output=cursor.fetchone()
				last_data_date=output[0].strftime('%Y-%m-%d')
				print(f'Data now updated through {last_data_date}')
			else:
				print('New data not available yet')
		# for my yahoo league
		if output_yh[0] is None:
			season_begin='2023-10-24'
			last_data_date=datetime.strptime(season_begin, '%Y-%m-%d')
			today=datetime.now()-timedelta(days=1)
			today=today.strftime('%Y-%m-%d')

			if last_data_date!=today:

				main_df=pd.DataFrame()
				
				day_range=pd.date_range(start=last_data_date, end=today)
				for day in day_range:
					year=int(datetime.strftime(day.date(), '%Y'))
					month=int(datetime.strftime(day.date(), '%m'))
					date=int(datetime.strftime(day.date(), '%d'))

					try:
						p=client.player_box_scores(day=date,month=month,year=year)
						df=pd.DataFrame(p)
						df_name_list=df.name.tolist()
						name_list=[unidecode(name) for name in df_name_list]
						df['name']=name_list
						date=f'{year}-{month}-{date}'
						if not df.empty:
							df.insert(0, 'date', date)
							for p in my_players_yh:
								p=unidecode(p)
								p=remove_jr(p)
								p=p.lstrip().rstrip()
								insert_df=df[df['name']==p]
								GS=insert_df['game_score']
								FG=insert_df['made_field_goals']
								FGA=insert_df['attempted_field_goals']
								FTA=insert_df['attempted_free_throws']
								FT=insert_df['made_free_throws']
								ORB=insert_df['offensive_rebounds']
								DRB=insert_df['defensive_rebounds']
								STL=insert_df['steals']
								AST=insert_df['assists']
								BLK=insert_df['blocks']
								PF=insert_df['personal_fouls']
								TOV=insert_df['turnovers']						
								points=convert_game_score_to_points(GS=GS, FG=FG, FGA=FGA, FTA=FTA, FT=FT, ORB=ORB, DRB=DRB, STL=STL, AST=AST, BLK=BLK, PF=PF, TOV=TOV)
								copy=insert_df.copy()
								copy.loc[copy['date']==date, 'points']=points
								main_df=pd.concat([main_df, copy])
					except:
						print('Player not found')
					time.sleep(4)
				main_df['slug']=main_df['slug'].astype(str)
				main_df['name']=main_df['name'].astype(str)
				main_df['team']=main_df['team'].astype(str)
				main_df['location']=main_df['location'].astype(str)
				main_df['opponent']=main_df['opponent'].astype(str)
				main_df['outcome']=main_df['outcome'].astype(str)

				connection=mysql.connect(host=sports_db_admin_host,
										database=sports_db_admin_db,
										user=sports_db_admin_user,
										password=sports_db_admin_pw,
										port=sports_db_admin_port,
										allow_local_infile=True)
				cursor=connection.cursor()

				file_path='/Users/franciscoavalosjr/Desktop/basketball-folder/tmp_data/my_team_stats_extract_yh.csv'
				main_df.to_csv(file_path,index=False)
				qry=f"LOAD DATA LOCAL INFILE '{file_path}' REPLACE INTO TABLE basketball.my_team_stats_yahoo FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '\"' IGNORE 1 ROWS;"
				cursor.execute(qry)
				connection.commit()
				del main_df
				os.remove(file_path)

				# cols="`,`".join([str(i) for i in main_df.columns.tolist()])
				# for i,row in main_df.iterrows():
				# 	sql='REPLACE INTO `my_team_stats` (`'+cols+'`) VALUES ('+'%s,'*(len(row)-1)+'%s)'
				# 	cursor.execute(sql, tuple(row))
				# 	connection.commit()

				print('Backfill to basketball.my_team_stats_yahoo table complete!')
		else:
			print(f'basketball.my_team_stats_yahoo, data through {output_yh[0]}')
			last_data_date=output_yh[0].strftime('%Y-%m-%d')
			today=datetime.now()-timedelta(days=1)
			today=today.strftime('%Y-%m-%d')

			last_data_day=output_yh[0].strftime('%d')
			last_data_month=output_yh[0].strftime('%m')
			last_data_year=output_yh[0].strftime('%Y')

			yesterday=datetime.now()-timedelta(days=1)
			yesterday_day=yesterday.strftime('%d')
			yesterday_month=yesterday.strftime('%m')
			yesterday_year=yesterday.now().strftime('%Y')
			yesterday=yesterday.strftime('%Y-%m-%d')

			if last_data_date!=yesterday:
				print('New data! Preparing to add data!')
				main_df=pd.DataFrame()
				last_data_date=datetime.strptime(last_data_date, '%Y-%m-%d')
				
				day_range=pd.date_range(start=last_data_date, end=yesterday)
				for day in day_range:
					year=int(datetime.strftime(day.date(), '%Y'))
					month=int(datetime.strftime(day.date(), '%m'))
					date=int(datetime.strftime(day.date(), '%d'))

					try:
						p=client.player_box_scores(day=date,month=month,year=year)
						df=pd.DataFrame(p)
						df_name_list=df.name.tolist()
						name_list=[unidecode(name) for name in df_name_list]
						df['name']=name_list
						date=f'{year}-{month}-{date}'
						if not df.empty:
							df.insert(0, 'date', date)
							for p in my_players_yh:
								p=unidecode(p)
								p=remove_jr(p)
								p=p.lstrip().rstrip()
								insert_df=df[df['name']==p]
								GS=insert_df['game_score']
								FG=insert_df['made_field_goals']
								FGA=insert_df['attempted_field_goals']
								FTA=insert_df['attempted_free_throws']
								FT=insert_df['made_free_throws']
								ORB=insert_df['offensive_rebounds']
								DRB=insert_df['defensive_rebounds']
								STL=insert_df['steals']
								AST=insert_df['assists']
								BLK=insert_df['blocks']
								PF=insert_df['personal_fouls']
								TOV=insert_df['turnovers']						
								points=convert_game_score_to_points(GS=GS, FG=FG, FGA=FGA, FTA=FTA, FT=FT, ORB=ORB, DRB=DRB, STL=STL, AST=AST, BLK=BLK, PF=PF, TOV=TOV)
								copy=insert_df.copy()
								copy.loc[copy['date']==date, 'points']=points
								main_df=pd.concat([main_df, copy])
					except:
						print('Player not found')
					time.sleep(4)

				main_df['slug']=main_df['slug'].astype(str)
				main_df['name']=main_df['name'].astype(str)
				main_df['team']=main_df['team'].astype(str)
				main_df['location']=main_df['location'].astype(str)
				main_df['opponent']=main_df['opponent'].astype(str)
				main_df['outcome']=main_df['outcome'].astype(str)

				connection=mysql.connect(host=sports_db_admin_host,
										database=sports_db_admin_db,
										user=sports_db_admin_user,
										password=sports_db_admin_pw,
										port=sports_db_admin_port,
										allow_local_infile=True)
				cursor=connection.cursor()

				file_path='/Users/franciscoavalosjr/Desktop/basketball-folder/tmp_data/my_team_stats_extract_yh.csv'
				main_df.to_csv(file_path,index=False)
				qry=f"LOAD DATA LOCAL INFILE '{file_path}' REPLACE INTO TABLE basketball.my_team_stats_yahoo FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '\"' IGNORE 1 ROWS;"
				cursor.execute(qry)
				connection.commit()
				del main_df
				os.remove(file_path)

				# cols="`,`".join([str(i) for i in main_df.columns.tolist()])
				
				# for i,row in main_df.iterrows():
				# 	sql='REPLACE INTO `my_team_stats` (`'+cols+'`) VALUES ('+'%s,'*(len(row)-1)+'%s)'
				# 	cursor.execute(sql, tuple(row))
				# 	connection.commit()
				
				cursor=connection.cursor()
				sql='SELECT MAX(date) AS most_recent_data_date FROM basketball.my_team_stats_yahoo;'
				cursor.execute(sql)
				output_yh=cursor.fetchone()
				last_data_date=output_yh[0].strftime('%Y-%m-%d')
				print(f'Data now updated through {last_data_date} for my yahoo players')
			else:
				print('New data not available yet for yahoo players')
except Error as e:
	print("Error while connecting to MySQL", e)


finally:
	if(connection.is_connected()):
		cursor.close()
		connection.close()
		print('MySQL connection is closed')





