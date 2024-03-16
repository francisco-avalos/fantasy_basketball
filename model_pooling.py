
# Connection to my DB
import mysql.connector as mysql

# from statsmodels.graphics.tsaplots import plot_acf, plot_pacf
# import statsmodels.api as sm
# # from statsmodels.api import acf, pacf

import pandas as pd
# import numpy as np
import os
# import matplotlib.pyplot as plt

# from my_time_series import stationary_check, difference, optimize_ARMA, optimize_ARIMA
# import my_functions
import my_time_series as mts

# from itertools import product
# import warnings

# import pmdarima as pm
# from statsmodels.tsa.statespace.sarimax import SARIMAX
# from statsmodels.tsa.holtwinters import ExponentialSmoothing
# import tensorflow as tf


import pickle
import datetime

import glob
import re

# warnings.filterwarnings("ignore")


# tf.random.set_seed(42)
# np.random.seed(42)

# pd.set_option('display.max_columns', None)
# pd.set_option('display.max_rows', None)

today=datetime.date.today()
todays_date_string=today.strftime('%Y_%m_%d')


# OBTAIN DATA FROM DATABASE
yh_qry="""
SELECT 
	MT.name, 
    BREF.BBRefID,
    HIST.*
FROM basketball.live_yahoo_players MT
JOIN basketball.basketball_references_players BREF ON MT.name = BREF.BBRefName
JOIN basketball.historical_player_data HIST ON HIST.slug = BREF.BBRefID
;
"""

yh_unique_qry="""
SELECT DISTINCT
	MT.name, 
    BREF.BBRefID
FROM basketball.live_yahoo_players MT
JOIN basketball.basketball_references_players BREF ON MT.name = BREF.BBRefName
;
"""

espn_qry="""
SELECT 
	MT.name, 
    BREF.BBRefID,
    HIST.*
FROM basketball.live_espn_players MT
JOIN basketball.basketball_references_players BREF ON MT.name = BREF.BBRefName
JOIN basketball.historical_player_data HIST ON HIST.slug = BREF.BBRefID
;
"""

espn_unique_qry="""
SELECT DISTINCT
	MT.name, 
    BREF.BBRefID
FROM basketball.live_espn_players MT
JOIN basketball.basketball_references_players BREF ON MT.name = BREF.BBRefName
;
"""


sports_db_admin_host=os.environ.get('sports_db_admin_host')
sports_db_admin_db=os.environ.get('sports_db_admin_db')
sports_db_admin_user=os.environ.get('sports_db_admin_user')
sports_db_admin_pw=os.environ.get('sports_db_admin_pw')
sports_db_admin_port=os.environ.get('sports_db_admin_port')



connection=mysql.connect(host=sports_db_admin_host,
                        database=sports_db_admin_db,
                        user=sports_db_admin_user,
                        password=sports_db_admin_pw,
                        port=sports_db_admin_port)

if connection.is_connected():
    cursor=connection.cursor()
    cursor.execute(yh_qry)
    yahoo_team_df=cursor.fetchall()
    col_names=[name.lower() for name in cursor.column_names]
    yahoo_team_df=pd.DataFrame(yahoo_team_df, columns=col_names)

    cursor.execute(espn_qry)
    espn_team_df=cursor.fetchall()
    col_names=[name.lower() for name in cursor.column_names]
    espn_team_df=pd.DataFrame(espn_team_df, columns=col_names)

    cursor.execute(yh_unique_qry)
    yahoo_myunique_list=cursor.fetchall()
    # col_names=[name.lower() for name in cursor.column_names]
    # yahoo_myunique_list=[yahoo_myunique_df]
    # yahoo_myunique_df=pd.DataFrame(yahoo_myunique_df, columns=col_names)

    cursor.execute(espn_unique_qry)
    espn_myunique_list=cursor.fetchall()
    # col_names=[name.lower() for name in cursor.column_names]
    # espn_myunique_list=[espn_myunique_df]
    # espn_myunique_df=pd.DataFrame(espn_myunique_df, columns=col_names)

if(connection.is_connected()):
    cursor.close()
    connection.close()
    print('MySQL connection is closed')
else:
    print('MySQL already closed')






def date_extract(file_name:str):
	date_pattern=r'\d{4}_\d{2}_\d{2}'
	match=re.search(date_pattern,file_name)
	if match:
		return match.group(0)
	else:
		return None


# PLAYER OUTPUT LOCATION / PARAMETER SCANNING SETTING
yahoo_file_path='/Users/franciscoavalosjr/Desktop/basketball-folder/tmp_data/basketball_yahoo'
espn_file_path='/Users/franciscoavalosjr/Desktop/basketball-folder/tmp_data/basketball_espn'



data_structure={
	'yahoo': {
		'path': yahoo_file_path,
		'players': {}
	},
	'espn': {
		'path': espn_file_path,
		'players': {}
	}
}

for name, bbrefid in yahoo_myunique_list:
	player_data = yahoo_team_df[yahoo_team_df['bbrefid']==bbrefid]
	data_structure['yahoo']['players'][bbrefid] = player_data

for name, bbrefid in espn_myunique_list:
	player_data = espn_team_df[espn_team_df['bbrefid']==bbrefid]
	data_structure['espn']['players'][bbrefid] = player_data



for league,info in data_structure.items():
	file_path=info['path']
	league_player_data=info['players']
	print(league)
	for bbrefid,player_data in league_player_data.items():
		bbrefid_model_file_path=os.path.join(file_path,f'{bbrefid}','models')
		bbrefid_pkl_files=glob.glob(os.path.join(bbrefid_model_file_path,'*.pkl'))
		bbrefid_pkl_files_sorted=sorted(bbrefid_pkl_files,key=lambda x: date_extract(x) or '', reverse=True)

		if bbrefid_pkl_files_sorted:
			most_recent_date=date_extract(bbrefid_pkl_files_sorted[0])
			most_recent_files=[file for file in bbrefid_pkl_files_sorted if date_extract(file)==most_recent_date]
			print(f'Models for {bbrefid}')
			for file in most_recent_files:
				load_model=mts.load_model(file)
				print(load_model.summary())

