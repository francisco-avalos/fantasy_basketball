
# Connection to my DB
import mysql.connector as mysql

# from statsmodels.graphics.tsaplots import plot_acf, plot_pacf
# import statsmodels.api as sm
# # from statsmodels.api import acf, pacf

import pandas as pd
import numpy as np
import os
# import matplotlib.pyplot as plt

# from my_time_series import stationary_check, difference, optimize_ARMA, optimize_ARIMA
# import my_functions
import my_time_series as mts
import my_functions as mf

# from itertools import product
import warnings

# import pmdarima as pm
# from statsmodels.tsa.statespace.sarimax import SARIMAX
from statsmodels.tsa.holtwinters import ExponentialSmoothing
# import tensorflow as tf


import pickle
# import datetime

import glob
import re

warnings.filterwarnings("ignore")


# tf.random.set_seed(42)
# np.random.seed(42)

# pd.set_option('display.max_columns', None)
# pd.set_option('display.max_rows', None)

# today=datetime.date.today()
# todays_date_string=today.strftime('%Y_%m_%d')


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

truncate_predictions_table_qry="""
TRUNCATE basketball.predictions;
"""


## CREDENTIALS 
sports_db_admin_host=os.environ.get('sports_db_admin_host')
sports_db_admin_db=os.environ.get('sports_db_admin_db')
sports_db_admin_user=os.environ.get('sports_db_admin_user')
sports_db_admin_pw=os.environ.get('sports_db_admin_pw')
sports_db_admin_port=os.environ.get('sports_db_admin_port')

config={
	'host':sports_db_admin_host,
	'database':sports_db_admin_db,
	'user':sports_db_admin_user,
	'password':sports_db_admin_pw,
	'port':sports_db_admin_port,
	'allow_local_infile':True
}


## DB CONNECTION AND RETRIEVAL
connection=mysql.connect(**config)

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

    cursor.execute(espn_unique_qry)
    espn_myunique_list=cursor.fetchall()

    cursor.execute(truncate_predictions_table_qry)

if(connection.is_connected()):
    cursor.close()
    connection.close()
    print('MySQL connection is closed')
else:
    print('MySQL already closed')



## PLAYER OUTPUT LOCATION / PARAMETER SCANNING SETTING
yahoo_file_path='/Users/franciscoavalosjr/Desktop/basketball-folder/tmp_data/basketball_yahoo'
espn_file_path='/Users/franciscoavalosjr/Desktop/basketball-folder/tmp_data/basketball_espn'
export_import_data_file_path='/Users/franciscoavalosjr/Desktop/basketball-folder/tmp_data/exported_preds.csv'

# SET UP INSERT DB QUERY
load_into_qry=f"LOAD DATA LOCAL INFILE '{export_import_data_file_path}' REPLACE INTO TABLE basketball.predictions \
	FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '\"' IGNORE 1 ROWS;"


## POOL ALL LEAGUES INTO ONE DICTIONARY
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



## PARAM CONFIGS & DATA ENTRY SET UPS
keys = ['df', 'league', 'bid', 'model_type', 'p', 'd', 'q', 'alpha', 'beta', 'ci_lower_bound', 'ci_upper_bound']
kwargs={key:None for key in keys}
d=0
alpha,beta=0,0
conf_lower_bound,conf_upper_bound=0,0


## FORECASTING LENGTH
num_next_games=5



connection=mysql.connect(**config)

for league,info in data_structure.items():
	file_path=info['path']
	league_player_data=info['players']
	print(league)
	for bbrefid,player_data in league_player_data.items():
		bbrefid_model_file_path=os.path.join(file_path,f'{bbrefid}','models')
		bbrefid_pkl_files=glob.glob(os.path.join(bbrefid_model_file_path,'*.pkl'))
		bbrefid_pkl_files_sorted=sorted(bbrefid_pkl_files,key=lambda x: mf.date_extract(x) or '', reverse=True)

		bbrefid_scale_file_path=os.path.join(file_path,f'{bbrefid}','scalers')
		scaler_file=glob.glob(os.path.join(bbrefid_scale_file_path,'*.pkl'))
		loaded_scaler=mts.load_scaler(scaler_file[0])

		if bbrefid_pkl_files_sorted:
			most_recent_date=mf.date_extract(bbrefid_pkl_files_sorted[0])
			most_recent_files=[file for file in bbrefid_pkl_files_sorted if mf.date_extract(file)==most_recent_date]
			print(f'Predictions for {bbrefid}')
			for file in most_recent_files:
				is_stats_model,is_stats_model_type=mf.is_statistical_model(file_name=file)
				loaded_model=mts.load_model(file)
				if is_stats_model and is_stats_model_type in ['AR','MA','ARMA','ARIMA']:
					print(f'Type - {is_stats_model_type}')
					if is_stats_model_type=='ARIMA':
						d=1
					refitted_model=loaded_model.apply(player_data.points,refit=False)
					next_games_predictions=refitted_model.forecast(num_next_games)

					confidence_interval=refitted_model.get_forecast(steps=num_next_games)
					confidence_interval=confidence_interval.conf_int()

					optimized_arima_df=mts.obtain_optimized_arma_parameter_extracts(bid=bbrefid,file_path=file_path)
					p,q=mts.optimized_param_decision(optimized_arima_df)

					next_games_predictions=next_games_predictions.to_frame()
					next_games_predictions.reset_index(inplace=True)
					next_games_predictions.columns=['day','predicted_mean']
					next_games_predictions['day']=next_games_predictions.index+1
					conf_lower_bound,conf_upper_bound=confidence_interval.iloc[:,0].values,confidence_interval.iloc[:,1].values

					kwargs['df'],kwargs['league'],kwargs['bid'],kwargs['model_type'],kwargs['p'],kwargs['d'],kwargs['q'], \
						kwargs['alpha'],kwargs['beta'],kwargs['ci_lower_bound'],kwargs['ci_upper_bound'] = \
						next_games_predictions, league, bbrefid, is_stats_model_type, p, d, q, alpha, beta, conf_lower_bound, conf_upper_bound
					next_games_predictions=mf.prepare_predictions_table(**kwargs)

					if connection.is_connected():
						cursor=connection.cursor()
						next_games_predictions.to_csv(export_import_data_file_path,index=False)
						cursor.execute(load_into_qry)
						connection.commit()
						del next_games_predictions
						os.remove(export_import_data_file_path)
						print(f'Finished inserting predictions for {bbrefid} - {is_stats_model_type}')

				elif is_stats_model and is_stats_model_type in ['SGL_EXP','DBL_EXP']:
					print('Exponential TYPE MODEL')
					conf_lower_bound,conf_upper_bound=0,0
					if is_stats_model_type=='SGL_EXP':
						p,q=0,0
						alpha=loaded_model.params['smoothing_level']
						print(f'Type - {is_stats_model_type}, alpha = {alpha}')
						refitted_model=ExponentialSmoothing(player_data.points,trend=None,).fit(smoothing_level=alpha,optimized=True)
						next_games_predictions=refitted_model.predict(1,num_next_games)
						next_games_predictions=next_games_predictions.to_frame()
						next_games_predictions.reset_index(inplace=True)
						next_games_predictions.columns=['day','predicted_mean']
						next_games_predictions['day']=next_games_predictions.index+1

						kwargs['df'],kwargs['league'],kwargs['bid'],kwargs['model_type'],kwargs['p'],kwargs['d'],kwargs['q'], \
							kwargs['alpha'],kwargs['beta'],kwargs['ci_lower_bound'],kwargs['ci_upper_bound'] = \
							next_games_predictions, league, bbrefid, is_stats_model_type, p, d, q, alpha, beta, conf_lower_bound, conf_upper_bound
						next_games_predictions=mf.prepare_predictions_table(**kwargs)

						if connection.is_connected():
							cursor=connection.cursor()
							next_games_predictions.to_csv(export_import_data_file_path,index=False)
							cursor.execute(load_into_qry)
							connection.commit()
							del next_games_predictions
							print(f'Finished inserting predictions for {bbrefid} - {is_stats_model_type}')
					elif is_stats_model_type=='DBL_EXP':
						p,q=0,0
						alpha=loaded_model.params['smoothing_level']
						beta=loaded_model.params['smoothing_trend']
						print(f'Type - {is_stats_model_type}, alpha = {alpha}, beta = {beta}')
						refitted_model=ExponentialSmoothing(player_data.points,trend=None,).fit(smoothing_level=alpha,smoothing_trend=beta,optimized=True)
						next_games_predictions=refitted_model.predict(1,num_next_games)
						next_games_predictions=next_games_predictions.to_frame()
						next_games_predictions.reset_index(inplace=True)
						next_games_predictions.columns=['day','predicted_mean']
						next_games_predictions['day']=next_games_predictions.index+1
						
						kwargs['df'],kwargs['league'],kwargs['bid'],kwargs['model_type'],kwargs['p'],kwargs['d'],kwargs['q'], \
							kwargs['alpha'],kwargs['beta'],kwargs['ci_lower_bound'],kwargs['ci_upper_bound'] = \
							next_games_predictions, league, bbrefid, is_stats_model_type, p, d, q, alpha, beta, conf_lower_bound, conf_upper_bound
						next_games_predictions=mf.prepare_predictions_table(**kwargs)

						connection=mysql.connect(**config)
						if connection.is_connected():
							cursor=connection.cursor()
							next_games_predictions.to_csv(export_import_data_file_path,index=False)
							cursor.execute(load_into_qry)
							connection.commit()
							del next_games_predictions
							os.remove(export_import_data_file_path)
							print(f'Finished inserting predictions for {bbrefid}')
				elif is_stats_model_type == 'LINEAR':
					next_games_predictions_prep=np.array([[1,2,3,4,5]])
					next_games_predictions_prep=np.transpose(next_games_predictions_prep)
					next_games_predictions=loaded_model.predict(next_games_predictions_prep)

					next_games_predictions_2d = np.squeeze(next_games_predictions)
					next_games_predictions=pd.DataFrame(next_games_predictions_2d)
					next_games_predictions=loaded_scaler.inverse_transform(next_games_predictions)
					next_games_predictions=pd.DataFrame(next_games_predictions)

					next_games_predictions.reset_index(inplace=True)
					next_games_predictions.columns=['day','predicted_mean']
					next_games_predictions['day']=next_games_predictions.index+1

					p,d,q,alpha,beta,conf_lower_bound,conf_upper_bound=0,0,0,0.0,0.0,0.0,0.0
					kwargs['df'],kwargs['league'],kwargs['bid'],kwargs['model_type'],kwargs['p'],kwargs['d'],kwargs['q'], \
						kwargs['alpha'],kwargs['beta'],kwargs['ci_lower_bound'],kwargs['ci_upper_bound'] = \
						next_games_predictions, league, bbrefid, is_stats_model_type, p, d, q, alpha, beta, conf_lower_bound, conf_upper_bound
					next_games_predictions=mf.prepare_predictions_table(**kwargs)

					connection=mysql.connect(**config)
					if connection.is_connected():
						cursor=connection.cursor()
						next_games_predictions.to_csv(export_import_data_file_path,index=False)
						cursor.execute(load_into_qry)
						connection.commit()
						del next_games_predictions,next_games_predictions_prep,next_games_predictions_2d
						os.remove(export_import_data_file_path)
						print(f'Finished inserting predictions for {bbrefid} - {is_stats_model_type}')

				elif is_stats_model_type == 'NEURAL_NETWORK':
					next_games_predictions_prep=np.array([[1,2,3,4,5]])
					next_games_predictions_prep=np.transpose(next_games_predictions_prep)
					next_games_predictions=loaded_model.predict(next_games_predictions_prep)

					next_games_predictions_2d = np.squeeze(next_games_predictions)
					next_games_predictions=pd.DataFrame(next_games_predictions_2d)
					next_games_predictions=loaded_scaler.inverse_transform(next_games_predictions)
					next_games_predictions=pd.DataFrame(next_games_predictions)

					next_games_predictions.reset_index(inplace=True)
					next_games_predictions.columns=['day','predicted_mean']
					next_games_predictions['day']=next_games_predictions.index+1

					p,d,q,alpha,beta,conf_lower_bound,conf_upper_bound=0,0,0,0.0,0.0,0.0,0.0
					kwargs['df'],kwargs['league'],kwargs['bid'],kwargs['model_type'],kwargs['p'],kwargs['d'],kwargs['q'], \
						kwargs['alpha'],kwargs['beta'],kwargs['ci_lower_bound'],kwargs['ci_upper_bound'] = \
						next_games_predictions, league, bbrefid, is_stats_model_type, p, d, q, alpha, beta, conf_lower_bound, conf_upper_bound
					next_games_predictions=mf.prepare_predictions_table(**kwargs)

					connection=mysql.connect(**config)
					if connection.is_connected():
						cursor=connection.cursor()
						next_games_predictions.to_csv(export_import_data_file_path,index=False)
						cursor.execute(load_into_qry)
						connection.commit()
						del next_games_predictions,next_games_predictions_prep,next_games_predictions_2d
						os.remove(export_import_data_file_path)
						print(f'Finished inserting predictions for {bbrefid} - {is_stats_model_type}')

				elif is_stats_model_type == 'LSTM':
					next_games_predictions_prep=np.array([[1,2,3,4,5]])
					next_games_predictions_prep=np.transpose(next_games_predictions_prep)
					next_games_predictions=loaded_model.predict(next_games_predictions_prep)

					next_games_predictions_2d = np.squeeze(next_games_predictions)
					next_games_predictions=pd.DataFrame(next_games_predictions_2d)
					next_games_predictions=loaded_scaler.inverse_transform(next_games_predictions)
					next_games_predictions=pd.DataFrame(next_games_predictions)

					next_games_predictions.reset_index(inplace=True)
					next_games_predictions.columns=['day','predicted_mean']
					next_games_predictions['day']=next_games_predictions.index+1

					p,d,q,alpha,beta,conf_lower_bound,conf_upper_bound=0,0,0,0.0,0.0,0.0,0.0
					kwargs['df'],kwargs['league'],kwargs['bid'],kwargs['model_type'],kwargs['p'],kwargs['d'],kwargs['q'], \
						kwargs['alpha'],kwargs['beta'],kwargs['ci_lower_bound'],kwargs['ci_upper_bound'] = \
						next_games_predictions, league, bbrefid, is_stats_model_type, p, d, q, alpha, beta, conf_lower_bound, conf_upper_bound
					next_games_predictions=mf.prepare_predictions_table(**kwargs)

					connection=mysql.connect(**config)
					if connection.is_connected():
						cursor=connection.cursor()
						next_games_predictions.to_csv(export_import_data_file_path,index=False)
						cursor.execute(load_into_qry)
						connection.commit()
						del next_games_predictions,next_games_predictions_prep,next_games_predictions_2d
						os.remove(export_import_data_file_path)
						print(f'Finished inserting predictions for {bbrefid} - {is_stats_model_type}')



if(connection.is_connected()):
	cursor.close()
	connection.close()
	print('MySQL connection is closed')

