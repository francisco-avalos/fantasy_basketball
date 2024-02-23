
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
from my_functions import clean_string, remove_name_suffixes, remove_player_string
# from tqdm import tqdm_notebook
from tqdm import tqdm


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

season_end_year=2024
league=League(league_id=leagueid, 
				year=season_end_year,
				espn_s2=espn_s2,
				swid=swid, 
				debug=False)

# myteam=league.teams[11]
# my_players=clean_string(myteam.roster).split(',')



fa_size=10
non_shows=[]
file_path='/Users/franciscoavalosjr/Desktop/basketball-folder/tmp_data/espn_fa_players_roles.csv'


player_position_df=pd.DataFrame(columns=['Player_Name','Player_Roles'])
# for fa in league.free_agents(size=fa_size):
#     fa=str(fa)
#     fa=remove_player_string(fa)
#     pi=league.player_info(fa)
#     new_row={'Player_Name':fa,'Player_Roles':pi.eligibleSlots}
#     player_position_df=player_position_df.append(new_row,ignore_index=True)
#     time.sleep(4)
# # print(player_position_df)



try:

	FA=league.free_agents(size=fa_size)

	# player_position_df=pd.DataFrame(columns=['Player_Name','Player_Roles'])
	# FA=clean_string(FA).split(',')
	# row=0

	print('begin process')

	for fa in tqdm(FA):
		# fa=fa.lstrip().rstrip()
		fa=str(fa)
		fa=remove_player_string(fa)
		pi=league.player_info(fa)
		new_row={'Player_Name':fa,'Player_Roles':pi.eligibleSlots}
		player_position_df=player_position_df.append(new_row,ignore_index=True)
		# print(new_row)
		time.sleep(4)
	player_position_df['Player_Name']=player_position_df['Player_Name'].astype(str)
	print('Obtained FA positions')


	connection=mysql.connect(host=sports_db_admin_host,
							database=sports_db_admin_db,
							user=sports_db_admin_user,
							password=sports_db_admin_pw,
							port=sports_db_admin_port,
							allow_local_infile=True)

	if connection.is_connected():
		cursor=connection.cursor()
		cursor.execute('TRUNCATE basketball.espn_player_positions;')
		player_position_df.to_csv(file_path,index=False)
		qry=f"LOAD DATA LOCAL INFILE '{file_path}' REPLACE INTO TABLE basketball.espn_player_positions FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '\"' IGNORE 1 ROWS;"
		cursor.execute(qry)
		connection.commit()
		# del player_position_df
		# os.remove(file_path)

	# if(connection.is_connected()):
	# 	cursor.close()
	# 	connection.close()


	# for fa in FA:
	# 	fa=fa.lstrip().rstrip()
	# 	if fa not in list(master_names_list_df.full_name):
	# 		for i in master_names_list_df.index:
	# 			full_name=unidecode.unidecode(master_names_list_df.loc[i, 'full_name'])
	# 			first_name=unidecode.unidecode(master_names_list_df.loc[i, 'first_name'])
	# 			last_name=unidecode.unidecode(master_names_list_df.loc[i, 'last_name'])
	# 			name_code=master_names_list_df.loc[i, 'bbrefid']
	# 			if (fa in full_name) & (name_code is not None):
	# 			# if (fa in full_name) & (name_code not in keep_out) & (name_code is not None):
	# 				try:
	# 					fa_output=client.regular_season_player_box_scores(player_identifier=name_code, 
	# 																	season_end_year=season_end_year)
	# 					df=pd.DataFrame(fa_output)
	# 					df.insert(0, 'name', fa)
	# 					name_code_list=[name_code] * df.shape[0]
	# 					df['name_code']=name_code_list
	# 					if not df.empty:
	# 						df['active']=df['active'].astype(bool)
	# 						main_free_agents_df=pd.concat([main_free_agents_df, df])
	# 				except:
	# 					non_shows.append(name_code)
	# 	elif fa in list(master_names_list_df.full_name):
	# 		for i in master_names_list_df.index:
	# 			full_name=master_names_list_df.loc[i, 'full_name']
	# 			name_code=master_names_list_df.loc[i, 'bbrefid']
	# 			if (fa in full_name) & (name_code is not None):
	# 			# if (fa in full_name) & (name_code not in keep_out) & (name_code is not None):
	# 				try:
	# 					fa_output=client.regular_season_player_box_scores(player_identifier=name_code,
	# 																	season_end_year=season_end_year)
	# 					df=pd.DataFrame(fa_output)
	# 					df.insert(0, 'name', fa)
	# 					name_code_list=[name_code] * df.shape[0]
	# 					df['name_code']=name_code_list
	# 					if not df.empty:
	# 						df['active']=df['active'].astype(bool)
	# 						main_free_agents_df=pd.concat([main_free_agents_df, df])
	# 				except:
	# 					non_shows.append(name_code)
	# 	time.sleep(4)
	# 	row+=1
	# 	completion_tracker=row/len(FA)
	# 	print("Progress {:.2%}".format(completion_tracker), end='\r')
	# main_free_agents_df['name']=main_free_agents_df['name'].astype(str)
	# main_free_agents_df['team']=main_free_agents_df['team'].astype(str)
	# main_free_agents_df['location']=main_free_agents_df['location'].astype(str)
	# main_free_agents_df['opponent']=main_free_agents_df['opponent'].astype(str)
	# main_free_agents_df['outcome']=main_free_agents_df['outcome'].astype(str)

	# print('Obtained FA stats')
	# print('Preparing to insert into db')

	# connection=mysql.connect(host=sports_db_admin_host,
	# 						database=sports_db_admin_db,
	# 						user=sports_db_admin_user,
	# 						password=sports_db_admin_pw,
	# 						port=sports_db_admin_port,
	# 						allow_local_infile=True)

	# if connection.is_connected():
	# 	cursor=connection.cursor()
	# 	cursor.execute('TRUNCATE basketball.live_free_agents;')
	# 	file_path='/Users/franciscoavalosjr/Desktop/basketball-folder/tmp_data/espn_fa_players.csv'
	# 	main_free_agents_df.to_csv(file_path,index=False)
	# 	qry=f"LOAD DATA LOCAL INFILE '{file_path}' REPLACE INTO TABLE basketball.live_free_agents FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '\"' IGNORE 1 ROWS;"
	# 	cursor.execute(qry)
	# 	connection.commit()
	# 	del main_free_agents_df
	# 	os.remove(file_path)

	# print('live_free_agents table ready to analyze')
	
	# export_non_shows_file=os.path.join(non_shows_path, 'non_shows_list.csv')
	# non_shows=pd.DataFrame(non_shows, columns=['slug'])
	# non_shows.to_csv(export_non_shows_file, index=False)
	# print('Non-shows exported to csv')

except Error as e:
	print("Error while connecting to MySQL", e)

# finally:
# 	if(connection.is_connected()):
# 		cursor.close()
# 		connection.close()
# 		print('Script finished - MySQL connection is closed')

