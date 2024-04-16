
# Connection to my DB
import mysql.connector as mysql

from statsmodels.graphics.tsaplots import plot_acf, plot_pacf
import statsmodels.api as sm
# from statsmodels.api import acf, pacf

import pandas as pd
import numpy as np
import os
import matplotlib.pyplot as plt

from my_time_series import stationary_check, difference, optimize_ARMA, optimize_ARIMA
import my_functions
import my_time_series as mts

from itertools import product
import warnings

import pmdarima as pm
from statsmodels.tsa.statespace.sarimax import SARIMAX
from statsmodels.tsa.holtwinters import ExponentialSmoothing
import tensorflow as tf
from sklearn.preprocessing import MinMaxScaler
from tensorflow.keras import Model, Sequential

from tensorflow.keras.losses import MeanSquaredError
from tensorflow.keras.metrics import MeanAbsoluteError

from tensorflow.keras.layers import Dense,Conv1D,LSTM,Lambda,Reshape,RNN,LSTMCell

import datetime
import my_functions as mf

warnings.filterwarnings("ignore")


tf.random.set_seed(42)
np.random.seed(42)

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

config={
	'host':sports_db_admin_host,
	'database':sports_db_admin_db,
	'user':sports_db_admin_user,
	'password':sports_db_admin_pw,
	'port':sports_db_admin_port,
	'allow_local_infile':True
}

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
    # col_names=[name.lower() for name in cursor.column_names]
    # yahoo_myunique_df=pd.DataFrame(yahoo_myunique_df, columns=col_names)

    cursor.execute(espn_unique_qry)
    espn_myunique_list=cursor.fetchall()
    # col_names=[name.lower() for name in cursor.column_names]
    # espn_myunique_df=pd.DataFrame(espn_myunique_df, columns=col_names)

if(connection.is_connected()):
    cursor.close()
    connection.close()
    print('MySQL connection is closed')
else:
    print('MySQL already closed')



# PLAYER OUTPUT LOCATION / PARAMETER SCANNING SETTING
# store_path='/Users/franciscoavalosjr/Desktop/basketball-folder/tmp_data/basketball_yahoo'
yahoo_file_path='/Users/franciscoavalosjr/Desktop/basketball-folder/tmp_data/basketball_yahoo'
espn_file_path='/Users/franciscoavalosjr/Desktop/basketball-folder/tmp_data/basketball_espn'
# n=0.80
# max_pq_range=9
# ps=range(0,max_pq_range,1)
# qs=range(0,max_pq_range,1)


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


# ma_keys=['df','trainLen','horizon','window','q']
# ar_keys=['df','trainLen','horizon','window','p']
# arma_keys=['df','trainLen','horizon','window','orderList']
# arima_keys=['df','trainLen','horizon','window','orderList','d']
# exp_keys=['df','trainLen','horizon','window','orderList']
# dbl_exp_keys=['df','trainLen','horizon','window','orderList']

# MA_config={key:None for key in ma_keys}
# AR_config={key:None for key in ar_keys}
# ARMA_config={key:None for key in arma_keys}
# ARIMA_config={key:None for key in arima_keys}
# EXP_config={key:None for key in exp_keys}
# DBL_EXP_config={key:None for key in dbl_exp_keys}

# # MA_config={'df':train,'trainLen':TRAIN_LEN,'window':WINDOW,'horizon':HORIZON,'q':param}
# # AR_config={'df':train,'trainLen':TRAIN_LEN,'window':WINDOW,'horizon':HORIZON,'p':param}
# # ARMA_config={'df':train,'trainLen':TRAIN_LEN,'horizon':HORIZON,'window':WINDOW,'orderList':orderList}
# # ARIMA_config={'df':train,'trainLen':TRAIN_LEN,'horizon':HORIZON,'window':WINDOW,'orderList':orderList,'d':d}
# # EXP_config={'df':train,'trainLen':TRAIN_LEN,'horizon':HORIZON,'window':WINDOW,'orderList':orderList}
# # DBL_EXP_config={'df':train,'trainLen':TRAIN_LEN,'horizon':HORIZON,'window':WINDOW,'orderList':orderList}



## ML CONFIGS / TRAIN/TEST/VALID
datawindow_keys=['input_width','label_width','shift','batch_size','train_df','val_df','test_df','label_columns']
DataWindow_config={key:None for key in datawindow_keys}
wide_DataWindow_config={key:None for key in datawindow_keys}



# # # TESTING WHEN NECESSARY 
# exclude_bbrefids=['brownja02','greenja05','irvinky01','johnsca02','kennalu01','martica02','richani01','sharpsh01','tatumja01','thompkl01','wagnemo01','westbru01']
# # espn_myunique_list=espn_myunique_list[~espn_myunique_list['bbrefid'].isin(exclude_bbrefids)]
# # espn_myunique_list=[item for item in espn_myunique_list if item['bbrefid'] not in exclude_bbrefids]
# espn_myunique_list=[item for item in espn_myunique_list if item[1] not in exclude_bbrefids]



for league,info in data_structure.items():
	store_path=info['path']
	league_player_data=info['players']
	print('\n')
	print(f'League {league}')
	ms_val_perf={}
	ms_perf={}
	for bbrefid,player_dat in league_player_data.items():

		## train / test / val sizing
		n=len(player_dat)
		train=player_dat[0:int(n*0.7)]
		val=player_dat[int(n*0.7):int(n*0.9)]
		test=player_dat[int(n*0.9):]

		## points specific
		train_points=train[['points']]
		val_points=val[['points']]
		test_points=test[['points']]

		## scaling for computation speed
		scaler_points=MinMaxScaler()
		scaler_points.fit(train_points)

		train_points[train_points.columns]=scaler_points.transform(train_points[train_points.columns])
		val_points[val_points.columns]=scaler_points.transform(val_points[val_points.columns])
		test_points[test_points.columns]=scaler_points.transform(test_points[test_points.columns])

		# unscaled_test_points=pd.DataFrame(scaler_points.inverse_transform(test_points), columns=['points']) # imhere

		mts.save_scaler(fit_model_scaler=scaler_points,file_path=store_path,bid=bbrefid,model_type='ml')

		column_indices={name: i for i, name in enumerate(train_points.columns)}

		# baseline - Last
		length_steps=2
		batch_size=10

		# data shaping
		DataWindow_config['train_df'],DataWindow_config['val_df'], \
			DataWindow_config['test_df'],DataWindow_config['label_columns']=train_points,val_points,test_points,['points']

		# # for visuals (if needed)
		# wide_DataWindow_config['input_width'],wide_DataWindow_config['label_width'], \
		# 	wide_DataWindow_config['shift'],wide_DataWindow_config['batch_size']=length_steps,length_steps,length_steps,batch_size
		# wide_DataWindow_config['train_df'],wide_DataWindow_config['val_df'], \
		# 	wide_DataWindow_config['test_df'],wide_DataWindow_config['label_columns']=train_points,val_points,test_points,['points']

		# Window Sizing baseline - Last
		DataWindow_config['input_width'],DataWindow_config['label_width'], \
			DataWindow_config['shift'],DataWindow_config['batch_size']=length_steps,length_steps,length_steps,batch_size

		multi_window=mts.DataWindow(**DataWindow_config)
		
		ms_baseline_last=mts.MultiStepLastBaseline(label_index=column_indices['points'], steps=length_steps)
		ms_baseline_last.compile(loss=MeanSquaredError(),metrics=[MeanAbsoluteError()])

		ms_val_perf['Baseline - Last']=ms_baseline_last.evaluate(multi_window.val)
		ms_perf['Baseline - Last']=ms_baseline_last.evaluate(multi_window.test,verbose=0)


		# # baseline - Repeat
		# # length_steps=5
		# # batch_size=10

		# # Window Sizing baseline - Repeat
		# DataWindow_config['input_width'],DataWindow_config['label_width'], \
		# 	DataWindow_config['shift'],DataWindow_config['batch_size']=length_steps,length_steps,length_steps,batch_size


		# multi_window=mts.DataWindow(**DataWindow_config)
		ms_baseline_repeat=mts.RepeatBaseline(label_index=column_indices['points'])
		ms_baseline_repeat.compile(loss=MeanSquaredError(),metrics=[MeanAbsoluteError()])

		ms_val_perf['Baseline - Repeat']=ms_baseline_repeat.evaluate(multi_window.val)
		ms_perf['Baseline - Repeat']=ms_baseline_repeat.evaluate(multi_window.test,verbose=0)


		## Baseline - Linear
		ms_linear=Sequential([
			Dense(1,kernel_initializer=tf.initializers.zeros)
		])
		history=mts.compile_and_fit(ms_linear,multi_window)

		ms_val_perf['Linear']=ms_linear.evaluate(multi_window.val)
		ms_perf['Linear']=ms_linear.evaluate(multi_window.test,verbose=0)

		mts.save_model(fit_model=history.model,file_path=store_path,bid=bbrefid,date=todays_date_string,model_type='LINEAR')


		## Baseline - Neural Network
		ms_dense=Sequential([
			Dense(64,activation='relu'),
			Dense(64,activation='relu'),
			Dense(1,kernel_initializer=tf.initializers.zeros),
		])
		history=mts.compile_and_fit(ms_dense,multi_window)

		ms_val_perf['Deep - Dense']=ms_dense.evaluate(multi_window.val)
		ms_perf['Deep - Dense']=ms_dense.evaluate(multi_window.test,verbose=0)

		mts.save_model(fit_model=history.model,file_path=store_path,bid=bbrefid,date=todays_date_string,model_type='NEURAL_NETWORK')

		## Baseline - Long-Short Term Memory
		deep_lstm_model=Sequential([
			LSTM(32,return_sequences=True),
			Dense(units=1)
		])
		history=mts.compile_and_fit(deep_lstm_model,multi_window)
		ms_val_perf['Deep - LSTM']=deep_lstm_model.evaluate(multi_window.val)
		ms_perf['Deep - LSTM']=deep_lstm_model.evaluate(multi_window.test,verbose=0)

		file_name=os.path.join(store_path,f'{bbrefid}',f'{bbrefid}_ML_MAE.csv')
		# ms_perf_df=pd.DataFrame(ms_perf.items(),columns=['Model','MAE'])
		# ms_perf_df=pd.DataFrame(ms_perf,columns=['Model','MAE'])
		ms_perf_df=pd.DataFrame(ms_perf)
		ms_perf_df=ms_perf_df.tail(1)
		ms_perf_df=ms_perf_df.transpose()
		ms_perf_df=ms_perf_df.reset_index()
		ms_perf_df.columns=['Model','MAE']
		ms_perf_df.to_csv(file_name,index=None)

		mts.save_model(fit_model=history.model,file_path=store_path,bid=bbrefid,date=todays_date_string,model_type='LSTM')

		# ## Baseline - CNN
		# # length_steps=4
		# KERNEL_WIDTH=3
		# LABEL_WIDTH=1
		# shift=1
		# batch_size=10
		# # KERNEL_WIDTH,LABEL_WIDTH,shift,batch_size=3,length_steps,1,10
		# # INPUT_WIDTH=LABEL_WIDTH+KERNEL_WIDTH-1
		# DataWindow_config['input_width'],DataWindow_config['label_width'],DataWindow_config['shift'],\
		# 	DataWindow_config['batch_size']=KERNEL_WIDTH,LABEL_WIDTH,shift,batch_size
		# multi_window=mts.DataWindow(**DataWindow_config)

		# cnn_model=Sequential([
		# 	Conv1D(32,activation='relu',kernel_size=(KERNEL_WIDTH)),
		# 	Dense(units=32,activation='relu'),
		# 	Dense(units=1,kernel_initializer=tf.initializers.zeros),
		# ])
		# history=mts.compile_and_fit(cnn_model,multi_window)

		# ms_val_perf['Deep - CNN']=cnn_model.evaluate(multi_window.val)
		# ms_perf['Deep - CNN']=cnn_model.evaluate(multi_window.test,verbose=0)


		# ms_dense=Sequential([
		# 	Dense(64,activation='relu'),
		# 	Dense(64,activation='relu'),
		# 	Dense(1,kernel_initializer=tf.initializers.zeros)
		# ])
		# history=mts.compile_and_fit(ms_dense,multi_window)







