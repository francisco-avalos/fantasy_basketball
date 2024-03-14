
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
import unidecode
import time
from datetime import date
from datetime import timedelta
from my_functions import clean_string, remove_name_suffixes


## Preliminaries, set ups & initiators 
pd.set_option('display.max_columns', None)
pd.set_option('display.max_rows', None)


sports_db_admin_host=os.environ.get('sports_db_admin_host')
sports_db_admin_db='basketball'
sports_db_admin_user=os.environ.get('sports_db_admin_user')
sports_db_admin_pw=os.environ.get('sports_db_admin_pw')
sports_db_admin_port=os.environ.get('sports_db_admin_port')


sc=OAuth2(None,None,from_file='oauth2.json')
gm=yfa.Game(sc, 'nba')
league_id=gm.league_ids(year=2024)
lg=gm.to_league('428.l.18598')
# lg=gm.to_league('402.l.18598') # tried to use as fix with bug


tk=lg.free_agents('P')
tk=pd.DataFrame(tk)

tk_df=lg.waivers()
tk_df=pd.DataFrame(tk_df)

tk_df=pd.concat([tk, tk_df])
cols_rearranged=['player_id','name','status','position_type','eligible_positions','percent_owned']
tk_df=tk_df[cols_rearranged]

connection=mysql.connect(host=sports_db_admin_host,
						database=sports_db_admin_db,
						user=sports_db_admin_user,
						password=sports_db_admin_pw,
						port=sports_db_admin_port,
						allow_local_infile=True)

if connection.is_connected():
	cursor=connection.cursor()
	cursor.execute('TRUNCATE basketball.live_free_agents_yahoo;')

	file_path='/Users/franciscoavalosjr/Desktop/basketball-folder/tmp_data/yahoo_fa_players.csv'
	tk_df.to_csv(file_path,index=False)
	qry=f"LOAD DATA LOCAL INFILE '{file_path}' REPLACE INTO TABLE basketball.live_free_agents_yahoo FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '\"' IGNORE 1 ROWS;"
	cursor.execute(qry)
	connection.commit()
	del tk_df, tk
	os.remove(file_path)

if connection.is_connected():
       cursor.close()
       connection.close()
       print('MySQL connection is closed')


# SELECT 
# 	YP.playerid AS yahoo_id,
#     YP.name AS yahoo_name,
#     YP.status,
#     MNL.full_name AS source_full_name,
#     MNL.first_name AS source_first_name,
#     MNL.last_name AS source_last_name,
#     MNL.bbrefid,
#     MNL.bday,
#     MNL.age
# FROM basketball.live_free_agents_yahoo YP
# JOIN basketball.master_names_list_temp MNL ON SUBSTRING_INDEX(YP.name, ' ',1) = MNL.first_name
# 	AND (CASE WHEN LENGTH(YP.name)-LENGTH(REPLACE(YP.name, ' ', ''))+1 > 2 THEN SUBSTRING_INDEX(SUBSTRING_INDEX(YP.name, ' ',-2), ' ', 1) ELSE SUBSTRING_INDEX(YP.name, ' ',-1) END) = MNL.last_name
#     AND (CASE WHEN LENGTH(YP.name)-LENGTH(REPLACE(YP.name, ' ', ''))+1 > 2 THEN SUBSTRING_INDEX(SUBSTRING_INDEX(YP.name, ' ',-2), ' ', -1) ELSE '' END) = MNL.suffix
# ;
