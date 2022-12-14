
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
from datetime import date
from datetime import timedelta
from my_functions import clean_string, remove_name_suffixes


## Preliminaries, set ups & initiators 
pd.set_option('display.max_columns', None)
pd.set_option('display.max_rows', None)


exec(open('/Users/franciscoavalosjr/Desktop/basketball-creds.py').read())

season_end_year=2023
league=League(league_id=leagueid, 
				year=season_end_year,
				espn_s2=espn_s2,
				swid=swid, 
				debug=False)

# myteam=league.teams[11]
# my_players=clean_string(myteam.roster).split(',')



fa_size=10000
non_shows=[]
non_shows_path='/Users/franciscoavalosjr/Desktop/basketball-folder/'


try:
	connection=mysql.connect(host=sports_db_admin_host,
							database=sports_db_admin_db,
							user=sports_db_admin_user,
							password=sports_db_admin_pw,
							port=sports_db_admin_port)
	print('empty live_free_agents table')
	if connection.is_connected():
		cursor=connection.cursor()
		cursor.execute('TRUNCATE basketball.live_free_agents;')

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
	row=0

	print('begin process')
	for fa in FA:
		fa=remove_name_suffixes(fa)
		fa=fa.lstrip().rstrip()
		if fa not in list(master_names_list_df.full_name):
			for i in master_names_list_df.index:
				full_name=unidecode.unidecode(master_names_list_df.loc[i, 'full_name'])
				first_name=unidecode.unidecode(master_names_list_df.loc[i, 'first_name'])
				last_name=unidecode.unidecode(master_names_list_df.loc[i, 'last_name'])
				name_code=master_names_list_df.loc[i, 'bbrefid']
				if (fa in full_name) & (name_code is not None):
				# if (fa in full_name) & (name_code not in keep_out) & (name_code is not None):
					try:
						fa_output=client.regular_season_player_box_scores(player_identifier=name_code, 
																		season_end_year=season_end_year)
						df=pd.DataFrame(fa_output)
						df.insert(0, 'name', fa)
						if not df.empty:
							df['active']=df['active'].astype(bool)
							main_free_agents_df=pd.concat([main_free_agents_df, df])
					except:
						non_shows.append(name_code)
		elif fa in list(master_names_list_df.full_name):
			for i in master_names_list_df.index:
				full_name=master_names_list_df.loc[i, 'full_name']
				name_code=master_names_list_df.loc[i, 'bbrefid']
				if (fa in full_name) & (name_code is not None):
				# if (fa in full_name) & (name_code not in keep_out) & (name_code is not None):
					try:
						fa_output=client.regular_season_player_box_scores(player_identifier=name_code,
																		season_end_year=season_end_year)
						df=pd.DataFrame(fa_output)
						df.insert(0, 'name', fa)
						if not df.empty:
							df['active']=df['active'].astype(bool)
							main_free_agents_df=pd.concat([main_free_agents_df, df])
					except:
						non_shows.append(name_code)
		time.sleep(5)
		# print('finished for ', fa)
		row+=1
		completion_tracker=row/len(FA)
		print("Progress {:.2%}".format(completion_tracker), end='\r')
	main_free_agents_df['name']=main_free_agents_df['name'].astype(str)
	main_free_agents_df['team']=main_free_agents_df['team'].astype(str)
	main_free_agents_df['location']=main_free_agents_df['location'].astype(str)
	main_free_agents_df['opponent']=main_free_agents_df['opponent'].astype(str)
	main_free_agents_df['outcome']=main_free_agents_df['outcome'].astype(str)

	print('Obtained FA stats')
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
			sql='REPLACE INTO `live_free_agents` (`'+cols+'`) VALUES ('+'%s,'*(len(row)-1)+'%s)'
			cursor.execute(sql, tuple(row))
			connection.commit()
	print('live_free_agents table ready to analyze')
	
	export_non_shows_file=os.path.join(non_shows_path, 'non_shows_list.csv')
	non_shows=pd.DataFrame(non_shows, columns=['slug'])
	non_shows.to_csv(export_non_shows_file, index=False)
	print('Non-shows exported to csv')

except Error as e:
	print("Error while connecting to MySQL", e)

finally:
	if(connection.is_connected()):
		cursor.close()
		connection.close()
		print('Script finished - MySQL connection is closed')


