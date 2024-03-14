
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
    yahoo_myunique_df=cursor.fetchall()
    col_names=[name.lower() for name in cursor.column_names]
    yahoo_myunique_df=pd.DataFrame(yahoo_myunique_df, columns=col_names)

    cursor.execute(espn_unique_qry)
    espn_myunique_df=cursor.fetchall()
    col_names=[name.lower() for name in cursor.column_names]
    espn_myunique_df=pd.DataFrame(espn_myunique_df, columns=col_names)

if(connection.is_connected()):
    cursor.close()
    connection.close()
    print('MySQL connection is closed')
else:
    print('MySQL already closed')



# PLAYER OUTPUT LOCATION / PARAMETER SCANNING SETTING
store_path='/Users/franciscoavalosjr/Desktop/basketball-folder/tmp_data/basketball_yahoo'
n=0.80
max_pq_range=9
ps=range(0,max_pq_range,1)
qs=range(0,max_pq_range,1)


# # # TESTING WHEN NECESSARY 
# test_ids=['bolbo01','branhma01','claxtni01','davisan02','giddejo01','goberru01','gordoer01','hachiru01','hieldbu01','kennalu01']
# # # yahoo_myunique_df=yahoo_myunique_df.head()
# yahoo_myunique_df=yahoo_myunique_df[-yahoo_myunique_df['bbrefid'].isin(test_ids)]

# RUN THROUGH STATISTICAL MODELS
for idx, bid in yahoo_myunique_df['bbrefid'].iteritems():
	player_dat=yahoo_team_df[yahoo_team_df['bbrefid']==bid]

	orderList=list(product(ps,qs))
	alpha=np.arange(0,1,0.02)
	beta=np.arange(0,1,0.02)
	alphas_betas=list(product(alpha,beta))

	if stationary_check(player_dat.points):
		print(f'{bid} is stationary')

		# EXPORT ACF / PACF PLOTS
		mts.acf_pacf_plot_export(bid=bid,file_path=store_path,field_values=player_dat.points)

		# ## Determine p,q via correlation plots
		# bid_acf_df,bid_pacf_df=acf_pacf_df_export(bid=bid,file_path=store_path,field_values=player_dat.points)
		# acf_sig_index=find_consecutive_end_indices(bid_acf_df.Lag)
		# pacf_sig_index=find_consecutive_end_indices(bid_pacf_df.Lag)

		# print('Show acf results',bid_acf_df[bid_acf_df.index.isin(acf_sig_index)])
		# print('Show pacf results',bid_pacf_df[bid_pacf_df.index.isin(pacf_sig_index)])


		# FIND THE BEST (AIC) ARMA MODEL AND EXPORT TOP 5 INTO CSV FILE
		train=player_dat.points[:int(n*len(player_dat.points))]
		test=player_dat.points[int(n*len(player_dat.points)):].to_frame()
		results_df=mts.optimize_ARMA(endog=train.values,orderList=orderList)
		top_5_results=results_df.head()
		file_name=os.path.join(store_path,f'{bid}',f'{bid}_optimized_arma.csv')
		top_5_results.to_csv(file_name,index=False)

		# EXPORT TRAIN / TEST SIZES INTO CSV FILE
		file_name=os.path.join(store_path,f'{bid}',f'{bid}_train_test_sizes.csv')
		num_rows_train = len(train)
		num_rows_test = len(test)
		df_summary = pd.DataFrame({
				'DataFrame':['Train','Test'],
				'Number of rows':[num_rows_train,num_rows_test]
			})
		df_summary.to_csv(file_name,index=False)


		# model=pm.auto_arima(
		# 	train.values,
		# 	start_p=0, max_p=10,
		# 	d=0, max_d=1,
		# 	start_q=0, max_q=10,
		# 	start_P=0, max_P=10,
		# 	D=0, max_D=1,
		# 	start_Q=0, max_Q=10,
		# 	m=7,
		# 	seasonal=False,
		# 	suppress_warnings=True,
		# 	stepwise=True,
		# 	random_state=20,
		# 	n_fits=75
		# 	)
		# p,d,q=model.order
		# auto_arima_df=pd.DataFrame({'p':[p],'d':[d],'q':[q]})
		# file_name=os.path.join(store_path,f'{bid}',f'{bid}_autoarima.csv')
		# auto_arima_df.to_csv(file_name,index=False)


		# OBTAIN ARMA PARAMETERS (FROM EXPORTED CSV) AND SET CONFIGS FOR FORECASTING
		## optimized_arima_df,auto_arima_df=obtain_parameter_extracts(bid=bid,file_path=store_path)
		optimized_arima_df=mts.obtain_optimized_arma_parameter_extracts(bid=bid,file_path=store_path)
		p,q=mts.optimized_param_decision(optimized_arima_df)
		
		# DECIDE ON STATISTICAL MODEL BASED ON AIC
		if mts.is_MA_or_AR_only(p,q):
			print('Either MovAvg or AutoReg')
			ma_or_ar,param=mts.decide_MA_AR(p,q)
			if ma_or_ar=='MA':
				TRAIN_LEN=len(train)
				HORIZON=len(test)
				WINDOW=mts.window_sizing(horizon=HORIZON,p=param,q=param)
				order=(0,param)
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
				file_name=os.path.join(store_path,f'{bid}',f'{bid}_test_results.csv')
				test[f'pred_points_MA_p={param}']=pred_points[:len(test)]
				test.to_csv(file_name,index=False)
				mts.save_arma_residual_diagnostics(model=ma_model_fit,bid=bid,file_path=store_path,orderList=orderList)

				mts.save_model(fit_model=ma_model_fit,file_path=store_path,bid=bid,date=todays_date_string,model_type='MA')
				# # delete any previous base model 
				# model_file_name=os.path.join(store_path,f'{bid}','models',f'{bid}_{date_string}_MA.pkl')
				# with open(model_file_name,'wb') as file:
				# 	pickle.dump(ma_model_fit,file)

				# print(f'AutoRegression with p={param}')
			elif ma_or_ar=='AR':
				# print(f'MovingAverage with q={param}')
				TRAIN_LEN=len(train)
				HORIZON=len(test)
				WINDOW=mts.window_sizing(horizon=HORIZON,p=param,q=param)
				order=(param,0)
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
				file_name=os.path.join(store_path,f'{bid}',f'{bid}_test_results.csv')
				test[f'pred_points_AR_q={param}']=pred_points[:len(test)]
				test.to_csv(file_name,index=False)
				mts.save_arma_residual_diagnostics(model=ar_model_fit,bid=bid,file_path=store_path,orderList=orderList)

				mts.save_model(fit_model=ar_model_fit,file_path=store_path,bid=bid,date=todays_date_string,model_type='AR')
				# model_file_name=os.path.join(store_path,f'{bid}','models',f'{bid}_{date_string}_AR.pkl')
				# with open(model_file_name,'wb') as file:
				# 	pickle.dump(ar_model_fit,file)
		else:
			# print('Not MovAvg or AutoReg alone')
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
			file_name=os.path.join(store_path,f'{bid}',f'{bid}_test_results.csv')
			test['arma_point_preds']=bid_forecasts
			test.to_csv(file_name,index=False)
			mts.save_arma_residual_diagnostics(model=bid_model_fit,bid=bid,file_path=store_path,orderList=orderList)

			mts.save_model(fit_model=bid_model_fit,file_path=store_path,bid=bid,date=todays_date_string,model_type='ARMA')
			# model_file_name=os.path.join(store_path,f'{bid}','models',f'{bid}_{date_string}_ARMA.pkl')
			# with open(model_file_name,'wb') as file:
			# 	pickle.dump(bid_model_fit,file)


	elif difference(player_dat.points,n_diff=1):
		print(f'{bid} is stationary after 1 difference')
		
		# EXPORT ACF / PACF PLOTS
		differenced=np.diff(player_dat.points,n=1)
		mts.acf_pacf_plot_export(bid=bid,file_path=store_path,field_values=differenced)

		# ## Determine p,q via correlation plots
		# bid_acf_df,bid_pacf_df=acf_pacf_df_export(bid=bid,file_path=store_path,field_values=differenced)
		# acf_sig_index=find_consecutive_end_indices(bid_acf_df.Lag)
		# pacf_sig_index=find_consecutive_end_indices(bid_pacf_df.Lag)

		# print('Show acf results',bid_acf_df[bid_acf_df.index.isin(acf_sig_index)])
		# print('Show pacf results',bid_pacf_df[bid_pacf_df.index.isin(pacf_sig_index)])


		# FIND THE BEST (AIC) ARMA MODEL AND EXPORT TOP 5 INTO CSV FILE
		train=player_dat.points[:int(n*len(player_dat.points))]
		test=player_dat.points[int(n*len(player_dat.points)):].to_frame()
		results_df=mts.optimize_ARIMA(endog=train.values,orderList=orderList,d=1)
		top_5_results=results_df.head()
		file_name=os.path.join(store_path,f'{bid}',f'{bid}_optimized_arma.csv')
		top_5_results.to_csv(file_name,index=False)

		# EXPORT TRAIN / TEST SIZES INTO CSV FILE
		file_name=os.path.join(store_path,f'{bid}',f'{bid}_train_test_sizes.csv')
		num_rows_train = len(train)
		num_rows_test = len(test)
		df_summary = pd.DataFrame({
				'DataFrame':['Train','Test'],
				'Number of rows':[num_rows_train,num_rows_test]
			})
		df_summary.to_csv(file_name,index=False)

		# model=pm.auto_arima(
		# 	train.values,
		# 	start_p=0, max_p=10,
		# 	d=1, max_d=2,
		# 	start_q=0, max_q=10,
		# 	start_P=0, max_P=10,
		# 	D=0, max_D=1,
		# 	start_Q=0, max_Q=10,
		# 	m=7,
		# 	seasonal=False,
		# 	suppress_warnings=True,
		# 	stepwise=True,
		# 	random_state=20,
		# 	n_fits=75
		# 	)
		# p,d,q=model.order
		# auto_arima_df=pd.DataFrame({'p':[p],'d':[d],'q':[q]})
		# file_name=os.path.join(store_path,f'{bid}',f'{bid}_autoarima.csv')
		# auto_arima_df.to_csv(file_name,index=False)

		
		# OBTAIN ARMA PARAMETERS (FROM EXPORTED CSV) AND SET CONFIGS FOR FORECASTING
		# optimized_arima_df,auto_arima_df=obtain_parameter_extracts(bid=bid,file_path=store_path)
		optimized_arima_df=mts.obtain_optimized_arma_parameter_extracts(bid=bid,file_path=store_path)
		p,q=mts.optimized_param_decision(optimized_arima_df)

		# DECIDE ON STATISTICAL MODEL BASED ON AIC
		if mts.is_MA_or_AR_only(p,q):
			print('Either MovAvg or AutoReg')
			ma_or_ar,param=mts.decide_MA_AR(p,q)
			if ma_or_ar=='MA':
				# print(f'AutoRegression with p={param}')
				TRAIN_LEN=len(train)
				HORIZON=len(test)
				WINDOW=mts.window_sizing(horizon=HORIZON,p=param,q=param)
				order=(0,param)
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
				file_name=os.path.join(store_path,f'{bid}',f'{bid}_test_results.csv')
				test[f'pred_points_MA_p={param}']=pred_points[:len(test)]
				test.to_csv(file_name,index=False)
				mts.save_arma_residual_diagnostics(model=ma_model_fit,bid=bid,file_path=store_path,orderList=orderList)

				mts.save_model(fit_model=ma_model_fit,file_path=store_path,bid=bid,date=todays_date_string,model_type='MA')
				# model_file_name=os.path.join(store_path,f'{bid}','models',f'{bid}_{date_string}_MA.pkl')
				# with open(model_file_name,'wb') as file:
				# 	pickle.dump(ma_model_fit,file)
			elif ma_or_ar=='AR':
				# print(f'MovingAverage with q={param}')
				TRAIN_LEN=len(train)
				HORIZON=len(test)
				WINDOW=mts.window_sizing(horizon=HORIZON,p=param,q=param)
				order=(param,0)
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
				file_name=os.path.join(store_path,f'{bid}',f'{bid}_test_results.csv')
				test[f'pred_points_AR_q={param}']=pred_points[:len(test)]
				test.to_csv(file_name,index=False)
				mts.save_arma_residual_diagnostics(model=ar_model_fit,bid=bid,file_path=store_path,orderList=orderList)

				mts.save_model(fit_model=ar_model_fit,file_path=store_path,bid=bid,date=todays_date_string,model_type='AR')
				# model_file_name=os.path.join(store_path,f'{bid}','models',f'{bid}_{date_string}_AR.pkl')
				# with open(model_file_name,'wb') as file:
				# 	pickle.dump(ar_model_fit,file)
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
			mts.save_arma_residual_diagnostics(model=bid_model_fit,bid=bid,file_path=store_path,orderList=orderList)

			mts.save_model(fit_model=bid_model_fit,file_path=store_path,bid=bid,date=todays_date_string,model_type='ARIMA')
			# model_file_name=os.path.join(store_path,f'{bid}','models',f'{bid}_{date_string}_ARIMA.pkl')
			# with open(model_file_name,'wb') as file:
			# 	pickle.dump(bid_model_fit,file)

		# FIND THE BEST (AIC) SGL EXP / DBL EXP MODEL AND EXPORT TOP 5 INTO CSV FILE
		sgl_exp_results_df=mts.optimize_exponential(endog=train,orderList=alpha)
		top_5_results_sgl_exp=sgl_exp_results_df.head()
		file_name=os.path.join(store_path,f'{bid}',f'{bid}_optimized_sgl_exp.csv')
		top_5_results_sgl_exp.to_csv(file_name,index=False)


		# OBTAIN SGL EXP / DBL EXP PARAMETERS (FROM EXPORTED CSV) AS SET CONFIG FOR FORECASTING
		sgl_exp_results_df=mts.obtain_optimized_exp_parameter_extracts(bid=bid,file_path=store_path,exponential_type='single')
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
			bid=bid,
			file_path=store_path,
			exponential_type='single',
			orderList=orderList
			)
		mts.save_model(fit_model=fit_bid_sgl_exp_model,file_path=store_path,bid=bid,date=todays_date_string,model_type='SGL EXP')
		# model_file_name=os.path.join(store_path,f'{bid}',f'{bid}_{date_string}_SGL_EXP.pkl')
		# with open(model_file_name,'wb') as file:
		# 	pickle.dump(fit_bid_sgl_exp_model,file)



		# FIND THE BEST (AIC) SGL EXP / DBL EXP MODEL AND EXPORT TOP 5 INTO CSV FILE
		dbl_exp_results_df=mts.optimize_double_exponential(endog=train,orderList=alphas_betas)
		top_5_results_dbl_exp=dbl_exp_results_df.head()
		file_name=os.path.join(store_path,f'{bid}',f'{bid}_optimized_dbl_exp.csv')
		top_5_results_dbl_exp.to_csv(file_name,index=None)

		# OBTAIN SGL EXP / DBL EXP PARAMETERS (FROM EXPORTED CSV) AS SET CONFIG FOR FORECASTING
		dbl_exp_results_df=mts.obtain_optimized_exp_parameter_extracts(bid=bid,file_path=store_path,exponential_type='double')
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
			bid=bid,
			file_path=store_path,
			exponential_type='double',
			orderList=orderList
			)

		mts.save_model(fit_model=fit_bid_dbl_exp_model,file_path=store_path,bid=bid,date=todays_date_string,model_type='DBL EXP')
		# model_file_name=os.path.join(store_path,f'{bid}',f'{bid}_{date_string}_DBL_EXP.pkl')
		# with open(model_file_name,'wb') as file:
		# 	pickle.dump(fit_bid_dbl_exp_model,file)

		file_name=os.path.join(store_path,f'{bid}',f'{bid}_test_results.csv')
		test.to_csv(file_name,index=False)


	elif difference(player_dat.points,n_diff=2):
		print(f'{bid} is stationary after 2 difference')
		differenced=np.diff(player_dat.points,n=2)

		# EXPORT ACF / PACF PLOTS
		mts.acf_pacf_plot_export(bid=bid,file_path=store_path,field_values=differenced)

		# ## Determine p,q via correlation plots
		# bid_acf_df,bid_pacf_df=acf_pacf_df_export(bid=bid,file_path=store_path,field_values=differenced)
		# acf_sig_index=find_consecutive_end_indices(bid_acf_df.Lag)
		# pacf_sig_index=find_consecutive_end_indices(bid_pacf_df.Lag)

		# print('Show acf results',bid_acf_df[bid_acf_df.index.isin(acf_sig_index)])
		# print('Show pacf results',bid_pacf_df[bid_pacf_df.index.isin(pacf_sig_index)])


		# FIND THE BEST (AIC) ARMA MODEL AND EXPORT TOP 5 INTO CSV FILE
		train=player_dat.points[:int(n*len(player_dat.points))]
		test=player_dat.points[int(n*len(player_dat.points)):].to_frame()
		results_df=mts.optimize_ARIMA(endog=train.values,orderList=orderList,d=2)
		top_5_results=results_df.head()
		file_name=os.path.join(store_path,f'{bid}',f'{bid}_optimized_arma.csv')
		top_5_results.to_csv(file_name,index=False)

		# EXPORT TRAIN / TEST SIZES INTO CSV FILE
		file_name=os.path.join(store_path,f'{bid}',f'{bid}_train_test_sizes.csv')
		num_rows_train = len(train)
		num_rows_test = len(test)
		df_summary = pd.DataFrame({
				'DataFrame':['Train','Test'],
				'Number of rows':[num_rows_train,num_rows_test]
			})
		df_summary.to_csv(file_name,index=False)

		# model=pm.auto_arima(
		# 	train.values,
		# 	start_p=0, max_p=10,
		# 	d=2, max_d=3,
		# 	start_q=0, max_q=10,
		# 	start_P=0, max_P=10,
		# 	D=0, max_D=1,
		# 	start_Q=0, max_Q=10,
		# 	m=7,
		# 	seasonal=False,
		# 	suppress_warnings=True,
		# 	stepwise=True,
		# 	random_state=20,
		# 	n_fits=75
		# 	)
		# p,d,q=model.order
		# auto_arima_df=pd.DataFrame({'p':[p],'d':[d],'q':[q]})
		# file_name=os.path.join(store_path,f'{bid}',f'{bid}_autoarima.csv')
		# auto_arima_df.to_csv(file_name,index=False)


		# OBTAIN ARMA PARAMETERS (FROM EXPORTED CSV) AND SET CONFIGS FOR FORECASTING
		# optimized_arima_df,auto_arima_df=obtain_parameter_extracts(bid=bid,file_path=store_path)
		optimized_arima_df=mts.obtain_optimized_arma_parameter_extracts(bid=bid,file_path=store_path)
		p,q=mts.optimized_param_decision(optimized_arima_df)

		# DECIDE ON STATISTICAL MODEL BASED ON AIC
		if mts.is_MA_or_AR_only(p,q):
			print('Either MovAvg or AutoReg')
			ma_or_ar,param=mts.decide_MA_AR(p,q)
			if ma_or_ar=='MA':
				# print(f'AutoRegression with p={param}')
				TRAIN_LEN=len(train)
				HORIZON=len(test)
				WINDOW=mts.window_sizing(horizon=HORIZON,p=param,q=param)
				order=(0,param)
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
				file_name=os.path.join(store_path,f'{bid}',f'{bid}_test_results.csv')
				test[f'pred_points_MA_p={param}']=pred_points[:len(test)]
				test.to_csv(file_name,index=False)
				mts.save_arma_residual_diagnostics(model=ma_model_fit,bid=bid,file_path=store_path,orderList=orderList)

				mts.save_model(fit_model=ma_model_fit,file_path=store_path,bid=bid,date=todays_date_string,model_type='MA')		
				# model_file_name=os.path.join(store_path,f'{bid}','models',f'{bid}_{date_string}_MA.pkl')
				# with open(model_file_name,'wb') as file:
				# 	pickle.dump(ma_model_fit,file)
			elif ma_or_ar=='AR':
				# print(f'MovingAverage with q={param}')
				TRAIN_LEN=len(train)
				HORIZON=len(test)
				WINDOW=mts.window_sizing(horizon=HORIZON,p=param,q=param)
				order=(param,0)
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
				file_name=os.path.join(store_path,f'{bid}',f'{bid}_test_results.csv')
				test[f'pred_points_AR_q={param}']=pred_points[:len(test)]
				test.to_csv(file_name,index=False)
				mts.save_arma_residual_diagnostics(model=ar_model_fit,bid=bid,file_path=store_path,orderList=orderList)

				mts.save_model(fit_model=ar_model_fit,file_path=store_path,bid=bid,date=todays_date_string,model_type='AR')
				# model_file_name=os.path.join(store_path,f'{bid}','models',f'{bid}_{date_string}_AR.pkl')
				# with open(model_file_name,'wb') as file:
				# 	pickle.dump(ar_model_fit,file)
		else:
			# print('Not MovAvg or AutoReg alone')
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
			mts.save_arma_residual_diagnostics(model=bid_model_fit,bid=bid,file_path=store_path,orderList=orderList)

			mts.save_model(fit_model=bid_model_fit,file_path=store_path,bid=bid,date=todays_date_string,model_type='ARIMA')
			# model_file_name=os.path.join(store_path,f'{bid}','models',f'{bid}_{date_string}_ARIMA.pkl')
			# with open(model_file_name,'wb') as file:
			# 	pickle.dump(bid_model_fit,file)


		# TRAIN_LEN=len(train)
		# HORIZON=len(test)
		# WINDOW=mts.window_sizing(horizon=HORIZON,p=p,q=q)
		# d=2
		# orderList=[p,q]
		# bid_model=SARIMAX(train, order=(p,d,q), simple_differencing=False).fit(disp=False)
		# bid_forecasts=mts.rolling_forecast_ARIMA(
		# 	df=train,
		# 	trainLen=TRAIN_LEN,
		# 	horizon=HORIZON,
		# 	window=WINDOW,
		# 	orderList=orderList,
		# 	d=d
		# 	)
		# # test['arima_point_preds']=bid_forecasts
		# # file_name=os.path.join(store_path,f'{bid}',f'{bid}_test_results.csv')
		# test['arma_point_preds']=bid_forecasts
		# # test.to_csv(file_name,index=False)


		# mts.save_arma_residual_diagnostics(model=bid_model,bid=bid,file_path=store_path,orderList=orderList)



		# FIND THE BEST (AIC) SGL EXP / DBL EXP MODEL AND EXPORT TOP 5 INTO CSV FILE
		sgl_exp_results_df=mts.optimize_exponential(endog=train,orderList=alpha)
		top_5_results_sgl_exp=sgl_exp_results_df.head()
		file_name=os.path.join(store_path,f'{bid}',f'{bid}_optimized_sgl_exp.csv')
		top_5_results_sgl_exp.to_csv(file_name,index=False)


		# OBTAIN SGL EXP / DBL EXP PARAMETERS (FROM EXPORTED CSV) AS SET CONFIG FOR FORECASTING
		sgl_exp_results_df=mts.obtain_optimized_exp_parameter_extracts(bid=bid,file_path=store_path,exponential_type='single')
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

		mts.save_exponential_smoothing_residual_summary(model=fit_bid_sgl_exp_model,bid=bid,file_path=store_path,exponential_type='single',orderList=orderList)

		mts.save_model(fit_model=fit_bid_sgl_exp_model,file_path=store_path,bid=bid,date=todays_date_string,model_type='SGL EXP')
		# model_file_name=os.path.join(store_path,f'{bid}',f'{bid}_{date_string}_SGL_EXP.pkl')
		# with open(model_file_name,'wb') as file:
		# 	pickle.dump(fit_bid_sgl_exp_model,file)

		# FIND THE BEST (AIC) SGL EXP / DBL EXP MODEL AND EXPORT TOP 5 INTO CSV FILE
		dbl_exp_results_df=mts.optimize_double_exponential(endog=train,orderList=alphas_betas)
		top_5_results_dbl_exp=dbl_exp_results_df.head()
		file_name=os.path.join(store_path,f'{bid}',f'{bid}_optimized_dbl_exp.csv')
		top_5_results_dbl_exp.to_csv(file_name,index=None)

		# OBTAIN SGL EXP / DBL EXP PARAMETERS (FROM EXPORTED CSV) AS SET CONFIG FOR FORECASTING
		dbl_exp_results_df=mts.obtain_optimized_exp_parameter_extracts(bid=bid,file_path=store_path,exponential_type='double')
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

		mts.save_exponential_smoothing_residual_summary(model=fit_bid_dbl_exp_model,bid=bid,file_path=store_path,exponential_type='double',orderList=orderList)

		mts.save_model(fit_model=fit_bid_dbl_exp_model,file_path=store_path,bid=bid,date=todays_date_string,model_type='DBL EXP')
		# model_file_name=os.path.join(store_path,f'{bid}',f'{bid}_{date_string}_DBL_EXP.pkl')
		# with open(model_file_name,'wb') as file:
		# 	pickle.dump(fit_bid_dbl_exp_model,file)

		file_name=os.path.join(store_path,f'{bid}',f'{bid}_test_results.csv')
		test.to_csv(file_name,index=False)

	else:
		print(f'{bid} is not stationary')


