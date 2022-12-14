
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
from datetime import datetime
from datetime import date
from datetime import timedelta
from my_functions import clean_string, remove_jr, convert_game_score_to_points



## Preliminaries, set ups & initiators 
pd.set_option('display.max_columns', None)
pd.set_option('display.max_rows', None)


exec(open('/Users/franciscoavalosjr/Desktop/basketball-creds.py').read())

league=League(league_id=leagueid, 
				year=2023,
				espn_s2=espn_s2,
				swid=swid, 
				debug=False)



myteam=league.teams[11]
my_players=clean_string(myteam.roster).split(',')


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

		if(connection.is_connected()):
			cursor.close()
			connection.close()

		if output[0] is None:
			season_begin='2022-10-18'
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

					p=client.player_box_scores(day=date,month=month,year=year)
					df=pd.DataFrame(p)
					date=f'{year}-{month}-{date}'
					if not df.empty:
						df.insert(0, 'date', date)
						for p in my_players:
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

				main_df['slug']=main_df['slug'].astype(str)
				main_df['name']=main_df['name'].astype(str)
				main_df['team']=main_df['team'].astype(str)
				main_df['location']=main_df['location'].astype(str)
				main_df['opponent']=main_df['opponent'].astype(str)
				main_df['outcome']=main_df['outcome'].astype(str)

				cols="`,`".join([str(i) for i in main_df.columns.tolist()])

				connection=mysql.connect(host=sports_db_admin_host,
										database=sports_db_admin_db,
										user=sports_db_admin_user,
										password=sports_db_admin_pw,
										port=sports_db_admin_port)
				cursor=connection.cursor()

				for i,row in main_df.iterrows():
					sql='REPLACE INTO `my_team_stats` (`'+cols+'`) VALUES ('+'%s,'*(len(row)-1)+'%s)'
					cursor.execute(sql, tuple(row))
					connection.commit()
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

					p=client.player_box_scores(day=date,month=month,year=year)
					df=pd.DataFrame(p)
					date=f'{year}-{month}-{date}'
					if not df.empty:
						df.insert(0, 'date', date)
						for p in my_players:
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

				main_df['slug']=main_df['slug'].astype(str)
				main_df['name']=main_df['name'].astype(str)
				main_df['team']=main_df['team'].astype(str)
				main_df['location']=main_df['location'].astype(str)
				main_df['opponent']=main_df['opponent'].astype(str)
				main_df['outcome']=main_df['outcome'].astype(str)

				cols="`,`".join([str(i) for i in main_df.columns.tolist()])
				
				for i,row in main_df.iterrows():
					sql='REPLACE INTO `my_team_stats` (`'+cols+'`) VALUES ('+'%s,'*(len(row)-1)+'%s)'
					cursor.execute(sql, tuple(row))
					connection.commit()
				
				cursor=connection.cursor()
				sql='SELECT MAX(date) AS most_recent_data_date FROM basketball.my_team_stats;'
				cursor.execute(sql)
				output=cursor.fetchone()
				last_data_date=output[0].strftime('%Y-%m-%d')
				print(f'Data now updated through {last_data_date}')
			else:
				print('New data not available yet')
except Error as e:
	print("Error while connecting to MySQL", e)


finally:
	if(connection.is_connected()):
		cursor.close()
		connection.close()
		print('MySQL connection is closed')





