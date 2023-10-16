
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
import unidecode
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

league=League(league_id=leagueid, 
				year=2024,
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

def remove_name_suffixes(item):
	item=str(item)
	item=item.replace('Jr.','')
	item=item.replace('II','')
	item=item.replace('III','')
	item=item.replace('IV','')
	item=item.replace('Sr.','')
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


# myteam=league.teams[11]
# my_players=clean_string(myteam.roster).split(',')


keep_out=['anthoca01', 'whiteha01', 
		  'aldrila01', 'walkeke02',
		  'couside01', 'howardw01',
		  'fallta01', 'bledser01', 
		  'rondora01', 'thomptr01', 
		  'thomais02', 'hoardja01']
season_end_year=2023
fa_size=1000
non_shows=[]


try:
	connection=mysql.connect(host=sports_db_admin_host,
							database=sports_db_admin_db,
							user=sports_db_admin_user,
							password=sports_db_admin_pw,
							port=sports_db_admin_port)
	if connection.is_connected():
		cursor=connection.cursor()
		cursor.execute('TRUNCATE basketball.advanced_stats;')

	if connection.is_connected():
		cursor=connection.cursor()
		cursor.execute('SELECT * FROM basketball.master_names_list_temp;')
		master_names_list_df=cursor.fetchall()
		master_names_list_df=pd.DataFrame(master_names_list_df, columns=cursor.column_names)

	if(connection.is_connected()):
		cursor.close()
		connection.close()

	FA=league.free_agents(size=fa_size)

	main_free_agents_df=pd.DataFrame()
	FA=clean_string(FA).split(',')

	advanced_df=pd.DataFrame(client.players_advanced_season_totals(season_end_year=season_end_year))

	for fa in FA:
		fa=remove_name_suffixes(fa)
		fa=fa.lstrip().rstrip()
		if fa not in list(master_names_list_df.full_name):
			for i in master_names_list_df.index:
				full_name=unidecode.unidecode(master_names_list_df.loc[i, 'full_name'])
				first_name=unidecode.unidecode(master_names_list_df.loc[i, 'first_name'])
				last_name=unidecode.unidecode(master_names_list_df.loc[i, 'last_name'])
				name_code=master_names_list_df.loc[i, 'bbrefid']
				if (fa in full_name) & (name_code not in keep_out):
					df=advanced_df[advanced_df['slug']==name_code]
					if not df.empty:
						main_free_agents_df=pd.concat([main_free_agents_df, df])
		elif fa in list(master_names_list_df.full_name):
			for i in master_names_list_df.index:
				full_name=master_names_list_df.loc[i, 'full_name']
				name_code=master_names_list_df.loc[i, 'bbrefid']
				if (fa in full_name) & (name_code not in keep_out):
					df=advanced_df[advanced_df['slug']==name_code]
					if not df.empty:
						main_free_agents_df=pd.concat([main_free_agents_df, df])
		# time.sleep(5)

	main_free_agents_df['slug']=main_free_agents_df['slug'].astype(str)
	main_free_agents_df['name']=main_free_agents_df['name'].astype(str)
	main_free_agents_df['positions']=main_free_agents_df['positions'].astype(str)
	main_free_agents_df['team']=main_free_agents_df['team'].astype(str)
	main_free_agents_df['is_combined_totals']=main_free_agents_df['is_combined_totals'].astype(str)

	print('Obtained advanced FA stats')
	print('Preparing to insert into db')

	connection=mysql.connect(host=sports_db_admin_host,
							database=sports_db_admin_db,
							user=sports_db_admin_user,
							password=sports_db_admin_pw,
							port=sports_db_admin_port)

	if connection.is_connected():
		cursor=connection.cursor()
		cols="`,`".join([str(i) for i in main_free_agents_df.columns.tolist()])
		for i,row in main_free_agents_df.iterrows():
			sql='REPLACE INTO `advanced_stats` (`'+cols+'`) VALUES ('+'%s,'*(len(row)-1)+'%s)'
			cursor.execute(sql, tuple(row))
			connection.commit()
	print('advanced_stats table ready to analyze')

except Error as e:
	print("Error while connecting to MySQL", e)


finally:
	if(connection.is_connected()):
		cursor.close()
		connection.close()
		print('Script finished - MySQL connection is closed')





