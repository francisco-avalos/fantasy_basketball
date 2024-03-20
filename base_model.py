
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


import datetime

warnings.filterwarnings("ignore")


# tf.random.set_seed(42)
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
n=0.80
max_pq_range=9
ps=range(0,max_pq_range,1)
qs=range(0,max_pq_range,1)


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


# # # TESTING WHEN NECESSARY 
# exclude_bbrefids=['brownja02','greenja05','irvinky01','johnsca02','kennalu01','martica02','richani01','sharpsh01','tatumja01','thompkl01','wagnemo01','westbru01']
# # espn_myunique_list=espn_myunique_list[~espn_myunique_list['bbrefid'].isin(exclude_bbrefids)]
# # espn_myunique_list=[item for item in espn_myunique_list if item['bbrefid'] not in exclude_bbrefids]
# espn_myunique_list=[item for item in espn_myunique_list if item[1] not in exclude_bbrefids]

for league,info in data_structure.items():
	store_path=info['path']
	league_player_data=info['players']
	print(f'League: {league}')
	for bbrefid,player_dat in league_player_data.items():
		orderList=list(product(ps,qs))
		alpha=np.arange(0,1,0.02)
		beta=np.arange(0,1,0.02)
		alphas_betas=list(product(alpha,beta))
		if mts.stationary_check(player_dat.points):
			print(f'{bbrefid} is stationary')
			mts.acf_pacf_plot_export(bid=bbrefid,file_path=store_path,field_values=player_dat.points)

			# FIND THE BEST (AIC) ARMA MODEL AND EXPORT TOP 5 INTO CSV FILE
			train=player_dat.points[:int(n*len(player_dat.points))]
			test=player_dat.points[int(n*len(player_dat.points)):].to_frame()
			results_df=mts.optimize_ARMA(endog=train.values,orderList=orderList)
			top_5_results=results_df.head()
			file_name=os.path.join(store_path,f'{bbrefid}',f'{bbrefid}_optimized_arma.csv')
			top_5_results.to_csv(file_name,index=False)

			# EXPORT TRAIN / TEST SIZES INTO CSV FILE
			mts.track_train_test_sizes(file_path=store_path,bid=bbrefid,train=train,test=test)
			# file_name=os.path.join(store_path,f'{bbrefid}',f'{bbrefid}_train_test_sizes.csv')
			# num_rows_train = len(train)
			# num_rows_test = len(test)
			# df_summary = pd.DataFrame({
			# 	'DataFrame':['Train','Test'],
			# 	'Number of rows':[num_rows_train,num_rows_test]
			# 	})
			# df_summary.to_csv(file_name,index=False)

			# OBTAIN ARMA PARAMETERS (FROM EXPORTED CSV) AND SET CONFIGS FOR FORECASTING
			optimized_arima_df=mts.obtain_optimized_arma_parameter_extracts(bid=bbrefid,file_path=store_path)
			p,q=mts.optimized_param_decision(optimized_arima_df)

			# DECIDE ON STATISTICAL MODEL BASED ON AIC
			if mts.is_MA_or_AR_only(p,q):
				ma_or_ar,param=mts.decide_MA_AR(p,q)
				if ma_or_ar=='MA':
					TRAIN_LEN=len(train)
					HORIZON=len(test)
					WINDOW=mts.window_sizing(horizon=HORIZON,p=param,q=param)
					d=0
					order=(0,d,param)
					orderList=[0,param]
					ma_model=SARIMAX(train,order=order)
					ma_model_fit=ma_model.fit(disp=False)
					pred_points=mts.rolling_forecast_AutoRegressive(
						df=train,
						trainLen=TRAIN_LEN,
						window=WINDOW,
						horizon=HORIZON,
						p=param
					)
					file_name=os.path.join(store_path,f'{bbrefid}',f'{bbrefid}_test_results.csv')
					test[f'pred_points_MA_p={param}']=pred_points[:len(test)]
					test.to_csv(file_name,index=False)
					mts.save_arma_residual_diagnostics(model=ma_model_fit,bid=bbrefid,file_path=store_path,orderList=orderList)
					mts.save_model(fit_model=ma_model_fit,file_path=store_path,bid=bbrefid,date=todays_date_string,model_type='MA')
				elif ma_or_ar=='AR':
					TRAIN_LEN=len(train)
					HORIZON=len(test)
					WINDOW=mts.window_sizing(horizon=HORIZON,p=param,q=param)
					d=0
					order=(param,d,0)
					orderList=[param,0]
					ar_model=SARIMAX(train,order=order)
					ar_model_fit=ar_model.fit(disp=False)
					pred_points=mts.rolling_forecast_MovingAverage(
						df=train,
						trainLen=TRAIN_LEN,
						window=WINDOW,
						horizon=HORIZON,
						q=param
					)
					file_name=os.path.join(store_path,f'{bbrefid}',f'{bbrefid}_test_results.csv')
					test[f'pred_points_AR_q={param}']=pred_points[:len(test)]
					test.to_csv(file_name,index=False)
					mts.save_arma_residual_diagnostics(model=ar_model_fit,bid=bbrefid,file_path=store_path,orderList=orderList)
					mts.save_model(fit_model=ar_model_fit,file_path=store_path,bid=bbrefid,date=todays_date_string,model_type='AR')
			else:
				TRAIN_LEN=len(train)
				HORIZON=len(test)
				WINDOW=mts.window_sizing(horizon=HORIZON,p=p,q=q)
				orderList=[p,q]
				d=0
				bid_model_fit=SARIMAX(train,order=(p,d,q),simple_differencing=False).fit(disp=False)
				bid_forecasts=mts.rolling_forecast_ARMA(
					df=train,
					trainLen=TRAIN_LEN,
					horizon=HORIZON,
					window=WINDOW,
					orderList=orderList
				)
				file_name=os.path.join(store_path,f'{bbrefid}',f'{bbrefid}_test_results.csv')
				test['arma_point_preds']=bid_forecasts
				test.to_csv(file_name,index=False)
				mts.save_arma_residual_diagnostics(model=bid_model_fit,bid=bbrefid,file_path=store_path,orderList=orderList)
				mts.save_model(fit_model=bid_model_fit,file_path=store_path,bid=bbrefid,date=todays_date_string,model_type='ARMA')

		elif mts.difference(player_dat.points,n_diff=1):
			print(f'{bbrefid} is stationary after 1 difference') 

			# EXPORT ACF / PACF PLOTS
			differenced=np.diff(player_dat.points,n=1)
			mts.acf_pacf_plot_export(bid=bbrefid,file_path=store_path,field_values=differenced)

			# FIND THE BEST (AIC) ARMA MODEL AND EXPORT TOP 5 INTO CSV FILE
			train=player_dat.points[:int(n*len(player_dat.points))]
			test=player_dat.points[int(n*len(player_dat.points)):].to_frame()
			results_df=mts.optimize_ARIMA(endog=train.values,orderList=orderList,d=1)
			top_5_results=results_df.head()
			file_name=os.path.join(store_path,f'{bbrefid}',f'{bbrefid}_optimized_arma.csv')
			top_5_results.to_csv(file_name,index=False)

			# EXPORT TRAIN / TEST SIZES INTO CSV FILE
			mts.track_train_test_sizes(file_path=store_path,bid=bbrefid,train=train,test=test)
			# file_name=os.path.join(store_path,f'{bbrefid}',f'{bbrefid}_train_test_sizes.csv')
			# num_rows_train = len(train)
			# num_rows_test = len(test)
			# df_summary = pd.DataFrame({
			# 	'DataFrame':['Train','Test'],
			# 	'Number of rows':[num_rows_train,num_rows_test]
			# })
			# df_summary.to_csv(file_name,index=False)


			# OBTAIN ARMA PARAMETERS (FROM EXPORTED CSV) AND SET CONFIGS FOR FORECASTING
			optimized_arima_df=mts.obtain_optimized_arma_parameter_extracts(bid=bbrefid,file_path=store_path)
			p,q=mts.optimized_param_decision(optimized_arima_df)

			# DECIDE ON STATISTICAL MODEL BASED ON AIC
			if mts.is_MA_or_AR_only(p,q):
				print('Either MovAvg or AutoReg')
				ma_or_ar,param=mts.decide_MA_AR(p,q)
				if ma_or_ar=='MA':
					TRAIN_LEN=len(train)
					HORIZON=len(test)
					WINDOW=mts.window_sizing(horizon=HORIZON,p=param,q=param)
					d=1
					order=(0,d,param)
					orderList=[0,param]
					ma_model_fit=SARIMAX(train,order=order).fit(disp=False)
					pred_points=mts.rolling_forecast_AutoRegressive(
							df=train,
							trainLen=TRAIN_LEN,
							window=WINDOW,
							horizon=HORIZON,
							p=param
						)
					file_name=os.path.join(store_path,f'{bbrefid}',f'{bbrefid}_test_results.csv')
					test[f'pred_points_MA_p={param}']=pred_points[:len(test)]
					test.to_csv(file_name,index=False)
					mts.save_arma_residual_diagnostics(model=ma_model_fit,bid=bbrefid,file_path=store_path,orderList=orderList)

					mts.save_model(fit_model=ma_model_fit,file_path=store_path,bid=bbrefid,date=todays_date_string,model_type='MA')
				elif ma_or_ar=='AR':
					# print(f'MovingAverage with q={param}')
					TRAIN_LEN=len(train)
					HORIZON=len(test)
					WINDOW=mts.window_sizing(horizon=HORIZON,p=param,q=param)
					d=1
					order=(param,d,0)
					orderList=[param,0]
					ar_model_fit=SARIMAX(train,order=order).fit(disp=False)
					pred_points=mts.rolling_forecast_MovingAverage(
						df=train,
						trainLen=TRAIN_LEN,
						window=WINDOW,
						horizon=HORIZON,
						q=param
						)
					file_name=os.path.join(store_path,f'{bbrefid}',f'{bbrefid}_test_results.csv')
					test[f'pred_points_AR_q={param}']=pred_points[:len(test)]
					test.to_csv(file_name,index=False)
					mts.save_arma_residual_diagnostics(model=ar_model_fit,bid=bbrefid,file_path=store_path,orderList=orderList)

					mts.save_model(fit_model=ar_model_fit,file_path=store_path,bid=bbrefid,date=todays_date_string,model_type='AR')
			else:
				# print('Not MovAvg or AutoReg alone')
				TRAIN_LEN=len(train)
				HORIZON=len(test)
				WINDOW=mts.window_sizing(horizon=HORIZON,p=p,q=q)
				d=1
				orderList=[p,q]
				bid_model_fit=SARIMAX(train,order=(p,d,q),simple_differencing=False).fit(disp=False)
				bid_forecasts=mts.rolling_forecast_ARIMA(
					df=train,
					trainLen=TRAIN_LEN,
					horizon=HORIZON,
					window=WINDOW,
					orderList=orderList,
					d=d
					)
				test[f'arima_point_preds_p={p}_q={q}']=bid_forecasts
				mts.save_arma_residual_diagnostics(model=bid_model_fit,bid=bbrefid,file_path=store_path,orderList=orderList)

				mts.save_model(fit_model=bid_model_fit,file_path=store_path,bid=bbrefid,date=todays_date_string,model_type='ARIMA')

			# FIND THE BEST (AIC) SGL EXP / DBL EXP MODEL AND EXPORT TOP 5 INTO CSV FILE
			sgl_exp_results_df=mts.optimize_exponential(endog=train,orderList=alpha)
			top_5_results_sgl_exp=sgl_exp_results_df.head()
			file_name=os.path.join(store_path,f'{bbrefid}',f'{bbrefid}_optimized_sgl_exp.csv')
			top_5_results_sgl_exp.to_csv(file_name,index=False)


			# OBTAIN SGL EXP / DBL EXP PARAMETERS (FROM EXPORTED CSV) AS SET CONFIG FOR FORECASTING
			sgl_exp_results_df=mts.obtain_optimized_exp_parameter_extracts(bid=bbrefid,file_path=store_path,exponential_type='single')
			alpha=mts.optimized_sgl_exp_decision(sgl_exp_results_df)

			TRAIN_LEN=len(train)
			HORIZON=len(test)
			WINDOW=mts.window_sizing(horizon=HORIZON,p=1,q=1)
			orderList=[alpha]
			bid_sgl_exp_model=ExponentialSmoothing(train,trend=None)
			fit_bid_sgl_exp_model=bid_sgl_exp_model.fit(smoothing_level=alpha,optimized=True)

			bid_sgl_exp_forecasts=mts.rolling_forecast_exponential(
					df=train,
					trainLen=TRAIN_LEN,
					horizon=HORIZON,
					window=WINDOW,
					orderList=orderList
				)
			test[f'exp_alpha={alpha}']=bid_sgl_exp_forecasts[:len(test)]

			mts.save_exponential_smoothing_residual_summary(
				residuals=fit_bid_sgl_exp_model.resid,
				bid=bbrefid,
				file_path=store_path,
				exponential_type='single',
				orderList=orderList
				)
			mts.save_model(fit_model=fit_bid_sgl_exp_model,file_path=store_path,bid=bbrefid,date=todays_date_string,model_type='SGL EXP')

			# FIND THE BEST (AIC) SGL EXP / DBL EXP MODEL AND EXPORT TOP 5 INTO CSV FILE
			dbl_exp_results_df=mts.optimize_double_exponential(endog=train,orderList=alphas_betas)
			top_5_results_dbl_exp=dbl_exp_results_df.head()
			file_name=os.path.join(store_path,f'{bbrefid}',f'{bbrefid}_optimized_dbl_exp.csv')
			top_5_results_dbl_exp.to_csv(file_name,index=None)

			# OBTAIN SGL EXP / DBL EXP PARAMETERS (FROM EXPORTED CSV) AS SET CONFIG FOR FORECASTING
			dbl_exp_results_df=mts.obtain_optimized_exp_parameter_extracts(bid=bbrefid,file_path=store_path,exponential_type='double')
			alpha,beta=mts.optimized_dbl_exp_decision(dbl_exp_results_df)

			TRAIN_LEN=len(train)
			HORIZON=len(test)
			WINDOW=mts.window_sizing(horizon=HORIZON,p=1,q=1)
			orderList=[alpha,beta]
			bid_dbl_exp_model=ExponentialSmoothing(train,trend=None)
			fit_bid_dbl_exp_model=bid_dbl_exp_model.fit(smoothing_level=alpha,smoothing_trend=beta,optimized=True)
			bid_dbl_exp_forecasts=mts.rolling_forecast_double_exponential(
					df=train,
					trainLen=TRAIN_LEN,
					horizon=HORIZON,
					window=WINDOW,
					orderList=orderList
				)
			test[f'exp_alpha={alpha}_beta={beta}']=bid_dbl_exp_forecasts[:len(test)]

			mts.save_exponential_smoothing_residual_summary(
				residuals=fit_bid_dbl_exp_model.resid,
				bid=bbrefid,
				file_path=store_path,
				exponential_type='double',
				orderList=orderList
				)

			mts.save_model(fit_model=fit_bid_dbl_exp_model,file_path=store_path,bid=bbrefid,date=todays_date_string,model_type='DBL EXP')

			file_name=os.path.join(store_path,f'{bbrefid}',f'{bbrefid}_test_results.csv')
			test.to_csv(file_name,index=False)

		elif mts.difference(player_dat.points,n_diff=2):
			print(f'{bbrefid} is stationary after 2 difference')

			differenced=np.diff(player_dat.points,n=2)

			# EXPORT ACF / PACF PLOTS
			mts.acf_pacf_plot_export(bid=bbrefid,file_path=store_path,field_values=differenced)


			# FIND THE BEST (AIC) ARMA MODEL AND EXPORT TOP 5 INTO CSV FILE
			train=player_dat.points[:int(n*len(player_dat.points))]
			test=player_dat.points[int(n*len(player_dat.points)):].to_frame()
			results_df=mts.optimize_ARIMA(endog=train.values,orderList=orderList,d=2)
			top_5_results=results_df.head()
			file_name=os.path.join(store_path,f'{bbrefid}',f'{bbrefid}_optimized_arma.csv')
			top_5_results.to_csv(file_name,index=False)

			# EXPORT TRAIN / TEST SIZES INTO CSV FILE
			mts.track_train_test_sizes(file_path=store_path,bid=bbrefid,train=train,test=test)
			# file_name=os.path.join(store_path,f'{bbrefid}',f'{bbrefid}_train_test_sizes.csv')
			# num_rows_train = len(train)
			# num_rows_test = len(test)
			# df_summary = pd.DataFrame({
			# 		'DataFrame':['Train','Test'],
			# 		'Number of rows':[num_rows_train,num_rows_test]
			# 	})
			# df_summary.to_csv(file_name,index=False)

			# OBTAIN ARMA PARAMETERS (FROM EXPORTED CSV) AND SET CONFIGS FOR FORECASTING
			optimized_arima_df=mts.obtain_optimized_arma_parameter_extracts(bid=bbrefid,file_path=store_path)
			p,q=mts.optimized_param_decision(optimized_arima_df)

			# DECIDE ON STATISTICAL MODEL BASED ON AIC
			if mts.is_MA_or_AR_only(p,q):
				print('Either MovAvg or AutoReg')
				ma_or_ar,param=mts.decide_MA_AR(p,q)
				if ma_or_ar=='MA':
					TRAIN_LEN=len(train)
					HORIZON=len(test)
					WINDOW=mts.window_sizing(horizon=HORIZON,p=param,q=param)
					d=2
					order=(0,d,param)
					orderList=[0,param]
					ma_model_fit=SARIMAX(train,order=order).fit(disp=False)
					pred_points=mts.rolling_forecast_AutoRegressive(
							df=train,
							trainLen=TRAIN_LEN,
							window=WINDOW,
							horizon=HORIZON,
							p=param
						)
					file_name=os.path.join(store_path,f'{bbrefid}',f'{bbrefid}_test_results.csv')
					test[f'pred_points_MA_p={param}']=pred_points[:len(test)]
					test.to_csv(file_name,index=False)
					mts.save_arma_residual_diagnostics(model=ma_model_fit,bid=bbrefid,file_path=store_path,orderList=orderList)

					mts.save_model(fit_model=ma_model_fit,file_path=store_path,bid=bbrefid,date=todays_date_string,model_type='MA')		
				elif ma_or_ar=='AR':
					# print(f'MovingAverage with q={param}')
					TRAIN_LEN=len(train)
					HORIZON=len(test)
					WINDOW=mts.window_sizing(horizon=HORIZON,p=param,q=param)
					d=2
					order=(param,d,0)
					orderList=[param,0]
					ar_model_fit=SARIMAX(train,order=order).fit(disp=False)
					pred_points=mts.rolling_forecast_MovingAverage(
						df=train,
						trainLen=TRAIN_LEN,
						window=WINDOW,
						horizon=HORIZON,
						q=param
						)
					file_name=os.path.join(store_path,f'{bbrefid}',f'{bbrefid}_test_results.csv')
					test[f'pred_points_AR_q={param}']=pred_points[:len(test)]
					test.to_csv(file_name,index=False)
					mts.save_arma_residual_diagnostics(model=ar_model_fit,bid=bbrefid,file_path=store_path,orderList=orderList)

					mts.save_model(fit_model=ar_model_fit,file_path=store_path,bid=bbrefid,date=todays_date_string,model_type='AR')
			else:
				TRAIN_LEN=len(train)
				HORIZON=len(test)
				WINDOW=mts.window_sizing(horizon=HORIZON,p=p,q=q)
				d=2
				orderList=[p,q]
				bid_model_fit=SARIMAX(train,order=(p,d,q),simple_differencing=False).fit(disp=False)
				bid_forecasts=mts.rolling_forecast_ARIMA(
					df=train,
					trainLen=TRAIN_LEN,
					window=WINDOW,
					orderList=orderList,
					d=d
					)
				test[f'arima_points_pred_p={p}_q={q}']=bid_forecasts
				mts.save_arma_residual_diagnostics(model=bid_model_fit,bid=bbrefid,file_path=store_path,orderList=orderList)

				mts.save_model(fit_model=bid_model_fit,file_path=store_path,bid=bbrefid,date=todays_date_string,model_type='ARIMA')


			# FIND THE BEST (AIC) SGL EXP / DBL EXP MODEL AND EXPORT TOP 5 INTO CSV FILE
			sgl_exp_results_df=mts.optimize_exponential(endog=train,orderList=alpha)
			top_5_results_sgl_exp=sgl_exp_results_df.head()
			file_name=os.path.join(store_path,f'{bbrefid}',f'{bbrefid}_optimized_sgl_exp.csv')
			top_5_results_sgl_exp.to_csv(file_name,index=False)


			# OBTAIN SGL EXP / DBL EXP PARAMETERS (FROM EXPORTED CSV) AS SET CONFIG FOR FORECASTING
			sgl_exp_results_df=mts.obtain_optimized_exp_parameter_extracts(bid=bbrefid,file_path=store_path,exponential_type='single')
			alpha=mts.optimized_sgl_exp_decision(sgl_exp_results_df)

			TRAIN_LEN=len(train)
			HORIZON=len(test)
			WINDOW=mts.window_sizing(horizon=HORIZON,p=1,q=1)
			orderList=[alpha]
			fit_bid_sgl_exp_model=ExponentialSmoothing(train,trend=None).fit(smoothing_level=alpha,optimized=True)
			bid_sgl_exp_forecasts=mts.rolling_forecast_exponential(
					df=train,
					trainLen=TRAIN_LEN,
					horizon=HORIZON,
					window=WINDOW,
					orderList=orderList
				)
			test[f'exp_alpha={alpha}']=bid_sgl_exp_forecasts[:len(test)]

			mts.save_exponential_smoothing_residual_summary(model=fit_bid_sgl_exp_model,bid=bbrefid,file_path=store_path,exponential_type='single',orderList=orderList)

			mts.save_model(fit_model=fit_bid_sgl_exp_model,file_path=store_path,bid=bbrefid,date=todays_date_string,model_type='SGL EXP')

			# FIND THE BEST (AIC) SGL EXP / DBL EXP MODEL AND EXPORT TOP 5 INTO CSV FILE
			dbl_exp_results_df=mts.optimize_double_exponential(endog=train,orderList=alphas_betas)
			top_5_results_dbl_exp=dbl_exp_results_df.head()
			file_name=os.path.join(store_path,f'{bbrefid}',f'{bbrefid}_optimized_dbl_exp.csv')
			top_5_results_dbl_exp.to_csv(file_name,index=None)

			# OBTAIN SGL EXP / DBL EXP PARAMETERS (FROM EXPORTED CSV) AS SET CONFIG FOR FORECASTING
			dbl_exp_results_df=mts.obtain_optimized_exp_parameter_extracts(bid=bbrefid,file_path=store_path,exponential_type='double')
			alpha,beta=mts.optimized_dbl_exp_decision(dbl_exp_results_df)

			TRAIN_LEN=len(train)
			HORIZON=len(test)
			WINDOW=mts.window_sizing(horizon=HORIZON,p=1,q=1)
			orderList=[alpha,beta]
			fit_bid_dbl_exp_model=ExponentialSmoothing(train,trend=None).fit(smoothing_level=alpha,smoothing_trend=beta,optimized=True)
			bid_dbl_exp_forecasts=mts.rolling_forecast_double_exponential(
					df=train,
					trainLen=TRAIN_LEN,
					horizon=HORIZON,
					window=WINDOW,
					orderList=orderList
				)
			test[f'exp_alpha={alpha}_beta={beta}']=bid_dbl_exp_forecasts[:len(test)]

			mts.save_exponential_smoothing_residual_summary(model=fit_bid_dbl_exp_model,bid=bbrefid,file_path=store_path,exponential_type='double',orderList=orderList)

			mts.save_model(fit_model=fit_bid_dbl_exp_model,file_path=store_path,bid=bbrefid,date=todays_date_string,model_type='DBL EXP')

			file_name=os.path.join(store_path,f'{bbrefid}',f'{bbrefid}_test_results.csv')
			test.to_csv(file_name,index=False)

		else:
			print(f'{bid} is not stationary')


