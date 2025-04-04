
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

from my_basketball_funcs import clean_string, remove_name_suffixes

## Preliminaries, set ups & initiators 
pd.set_option('display.max_columns', None)
pd.set_option('display.max_rows', None)


sports_db_admin_host=os.environ.get('sports_db_admin_host')
sports_db_admin_db='basketball'
sports_db_admin_user=os.environ.get('sports_db_admin_user')
sports_db_admin_pw=os.environ.get('sports_db_admin_pw')
sports_db_admin_port=os.environ.get('sports_db_admin_port')
season_year=os.environ.get('season_year')

leagueid=os.environ.get('leagueid')
espn_s2=os.environ.get('espn_s2')
swid=os.environ.get('swid')


league=League(league_id=leagueid, 
				year=season_year,
				espn_s2=espn_s2,
				swid=swid, 
				debug=False)





# myteam=league.teams[11]
# my_players=clean_string(myteam.roster).split(',')


keep_out=['tatumja01','moranja01','banede01']
fa_size=700
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
	time.sleep(4)

	main_free_agents_df=pd.DataFrame()
	FA=clean_string(FA).split(',')

	advanced_df=pd.DataFrame(client.players_advanced_season_totals(season_end_year=season_year))
	# row=0

	for fa in FA:
		try:
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
			# row+=1
			# completion_tracker=row/len(FA)
			# print()
			# time.sleep(4) # 5 secs gets 12 requests // 4 seconds gets 15 requests // 3 seconds gets 20 requests, which is close to the >20 requests/min block limit 
		except:
			print(f'{fa} not captured')

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
							port=sports_db_admin_port,
							allow_local_infile=True)

	if connection.is_connected():
		cursor=connection.cursor()
		file_path='/Users/franciscoavalosjr/Desktop/basketball-folder/tmp_data/advanced_data_extract.csv'
		main_free_agents_df.to_csv(file_path,index=False)
		qry=f"LOAD DATA LOCAL INFILE '{file_path}' REPLACE INTO TABLE basketball.advanced_stats FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '\"' IGNORE 1 ROWS;"
		cursor.execute(qry)
		connection.commit()
		del main_free_agents_df
		os.remove(file_path)

		# cols="`,`".join([str(i) for i in main_free_agents_df.columns.tolist()])
		# for i,row in main_free_agents_df.iterrows():
		# 	sql='REPLACE INTO `advanced_stats` (`'+cols+'`) VALUES ('+'%s,'*(len(row)-1)+'%s)'
		# 	cursor.execute(sql, tuple(row))
		# 	connection.commit()
	print('advanced_stats table ready to analyze')

except Error as e:
	print("Error while connecting to MySQL", e)


finally:
	if(connection.is_connected()):
		cursor.close()
		connection.close()
		print('Script finished - MySQL connection is closed')





