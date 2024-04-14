import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

from statsmodels.tsa.stattools import adfuller
from statsmodels.graphics.tsaplots import plot_acf, plot_pacf

from sklearn.metrics import mean_squared_error, mean_absolute_error

# import matplotlib.dates as mdates

from statsmodels.tsa.statespace.sarimax import SARIMAX

# from statsmodels.tsa.arima_process import ArmaProcess

from itertools import product
from typing import Union
# from tqdm import tqdm_notebook
import tqdm
from statsmodels.graphics.gofplots import qqplot
from statsmodels.stats.diagnostic import acorr_ljungbox

# from statsmodels.tsa.seasonal import STL
import statsmodels.api as sm

from statsmodels.tsa.statespace.varmax import VARMAX
from statsmodels.tsa.stattools import grangercausalitytests

from tensorflow.keras import Model, Sequential

from tensorflow.keras.optimizers import Adam
from tensorflow.keras.callbacks import EarlyStopping
from tensorflow.keras.losses import MeanSquaredError
from tensorflow.keras.metrics import MeanAbsoluteError
from sklearn.preprocessing import MinMaxScaler

from tensorflow.keras.layers import Dense, Conv1D, LSTM, Lambda, Reshape, RNN, LSTMCell

import tensorflow as tf

from statsmodels.tsa.holtwinters import ExponentialSmoothing

from my_functions import create_player_folder, create_model_folder, create_model_scaler_folder
import os
import pickle



def mape(y_true, y_pred):
  return np.mean(np.abs((y_true - y_pred) / y_true)) * 100

def MAE(y_true,y_pred):
    if len(y_true) != len(y_pred):
        raise ValueError("Lengths of y_true and y_pred must be the same.")
    absolute_errors = [abs(true - pred) for true, pred in zip(y_true,y_pred)]
    mean_absolute_error = sum(absolute_errors) / len(absolute_errors)
    return mean_absolute_error


def stationary_check(field_values) -> bool:
  adf_result=adfuller(field_values)
  if adf_result[1] < 0.05:
    return True
  else:
    return False

def difference(field_values,n_diff=1) -> bool:
  field_diff = np.diff(field_values,n=n_diff)
  adf_result = adfuller(field_diff)

  if adf_result[1] < 0.05:
    return True
  else:
    return False

##########################################################################################
##########################################################################################






def optimize_ARMA(
  endog: Union[pd.Series, list], 
  orderList:list
) -> pd.DataFrame:
  results = []
  for order in tqdm.tqdm(orderList):
    try:
      model = SARIMAX(
                endog, order=(order[0], 0, order[1]), 
                simple_differencing=False
              ).fit(disp=False)
    except:
      continue
    aic = model.aic
    results.append([order,aic])
  result_df = pd.DataFrame(results)
  result_df.columns = ['(p,q)', 'AIC']
  result_df = result_df.sort_values(by='AIC', ascending=True).reset_index(drop=True)

  return result_df




def optimize_ARIMA(
  endog: Union[pd.Series, list], 
  orderList: list, 
  d: int
) -> pd.DataFrame:
  results = []
  for order in tqdm.tqdm(orderList):
    try:
      model = SARIMAX(
                endog, 
                order=(order[0], d, order[1]),
                simple_differencing=False
              ).fit(disp=False)
    except:
      continue
    aic = model.aic
    results.append([order, aic])
  
  result_df = pd.DataFrame(results)
  result_df.columns = ['(p,q)', 'AIC']
  #Sort in ascending order, lower AIC is better
  result_df = result_df.sort_values(by='AIC', ascending=True).reset_index(drop=True)
  return result_df



    


def optimize_SARIMA(
  endog:Union[pd.Series,list],
  orderList:list,
  d:int,
  D:int,
  s:int
) -> pd.DataFrame:
  results=[]
  for order in tqdm.tqdm(orderList):
    try:
      model=SARIMAX(endog,
                    order=(order[0],d,order[1]),
                    seasonal_order=(order[2],D,order[3],s),
                    simple_differencing=False
            ).fit(disp=False)
    except:
      continue
    aic=model.aic
    results.append([order,aic])
  results_df=pd.DataFrame(results)
  results_df.columns=['(p,q,P,Q)','AIC']

  results_df=results_df.sort_values(by='AIC',ascending=True).reset_index(drop=True)

  return results_df


def optimize_SARIMAX(
  endog: Union[pd.Series,list], 
  exog:Union[pd.Series,list], 
  orderList:list, 
  d:int, 
  D:int, 
  s:int
) -> pd.DataFrame:
  results=[]
  for order in tqdm.tqdm(orderList):
    try:
      model=SARIMAX(
              endog,
              exog,
              order = (order[0], d, order[1]),
              seasonal_order = (order[2], D, order[3], s),
              simple_differencing=False
            ).fit(disp=False)
    except:
      continue
    aic=model.aic
    results.append([order,aic])

  result_df=pd.DataFrame(results)
  result_df.columns=['(p,q,P,Q)','AIC']

  result_df=result_df.sort_values(by='AIC',ascending=True).reset_index(drop=True)
  
  return result_df


def optimize_VAR(endog: Union[pd.Series,list], rangeNum:int) -> pd.DataFrame:
  results = []
  for i in tqdm.tqdm(range(rangeNum)):
    try:
      model = VARMAX(endog, order=(i,0)).fit(disp=False)
    except:
      continue
    aic = model.aic
    results.append([i,aic])
  results_df = pd.DataFrame(results)
  results_df.columns = ['p','AIC']
  results_df = results_df.sort_values(by='AIC', ascending=True).reset_index(drop=True)
  return results_df


def optimize_VARMA(endog: Union[pd.Series,list], paramsList:list) -> pd.DataFrame:
  results = []
  for param in tqdm.tqdm(paramsList):
    try:
      model = VARMAX(endog, order=param).fit(disp=False)
    except:
      continue
    aic = model.aic
    results.append([param,aic])
  results_df = pd.DataFrame(results)
  results_df.columns = ['(p,q)','AIC']
  results_df = results_df.sort_values(by='AIC', ascending=True).reset_index(drop=True)
  return results_df



def optimize_VARMAX(
    endog: Union[pd.Series,list], 
    exog: Union[pd.Series,list], 
    paramsList:list
) -> pd.DataFrame:
  results = []
  for param in tqdm.tqdm(paramsList):
    try:
      model = VARMAX(endog, exog, order=param).fit(disp=False)
    except:
      continue
    aic = model.aic
    results.append([param,aic])
    
  results_df = pd.DataFrame(results)
  results_df.columns = ['(p,q)','AIC']
  results_df = results_df.sort_values(by='AIC', ascending=True).reset_index(drop=True)
  return results_df



def optimize_exponential(
  endog: Union[pd.Series, list], 
  orderList:list
) -> pd.DataFrame:
  results = []
  for order in tqdm.tqdm(orderList):
    try:
      model = ExponentialSmoothing(endog,trend=None)
      fit_model = model.fit(smoothing_level=order,optimized=True)
    except:
      continue
    aic = fit_model.aic
    results.append([order,aic])
  result_df = pd.DataFrame(results)
  result_df.columns = ['(alpha)', 'AIC']
  result_df = result_df.sort_values(by='AIC', ascending=True).reset_index(drop=True)

  return result_df


def optimize_double_exponential(
  endog: Union[pd.Series, list], 
  orderList:list
) -> pd.DataFrame:
  results = []
  for order in tqdm.tqdm(orderList):
    try:
      model = ExponentialSmoothing(endog,trend=None)
      fit_model = model.fit(smoothing_level=order[0],smoothing_trend=order[1],optimized=True)
    except:
      continue
    aic = fit_model.aic
    results.append([order[0],order[1],aic])
  result_df = pd.DataFrame(results)
  result_df.columns = ['alpha','beta', 'AIC']
  result_df = result_df.sort_values(by='AIC', ascending=True).reset_index(drop=True)

  return result_df


##########################################################################################
##########################################################################################




def rolling_forecast_mean(
	df:Union[pd.DataFrame,list],
	trainLen:int,
	horizon:int,
	window:int,
  **kwargs
) -> list:
	pred_mean = []
	total_len = trainLen + horizon
	for i in range(trainLen, total_len, window):
		mean = np.mean(df[:i].values)
		pred_mean.extend(mean for _ in range(window))
	return pred_mean



def rolling_forecast_last(
	df:pd.DataFrame,
	trainLen:int,
  horizon:int,
	window:int,
  **kwargs
) -> list:
	pred_last_value = []
	total_len = trainLen + horizon
	for i in range(trainLen, total_len, window):
		last_value = df[:i].iloc[-1].values[0]
		pred_last_value.extend(last_value for _ in range(window))
	return pred_last_value



def rolling_forecast_MovingAverage(
  df:pd.DataFrame,
  trainLen:int,
  window:int,
  horizon:int,
  q:int,
  **kwargs
) -> list:
  pred_MA = []
  total_len = trainLen + horizon
  for i in range(trainLen, total_len, window):
    model = SARIMAX(df[:i], order=(0,0,q))
    res = model.fit(disp=False)
    predictions = res.get_prediction(0,i + window - 1)
    oos_pred = predictions.predicted_mean.iloc[-window:]
    pred_MA.extend(oos_pred)
  return pred_MA



def rolling_forecast_AutoRegressive(
	df:pd.DataFrame,
	trainLen:int,
	window:int,
  horizon:int,
	p:int,
  **kwargs
) -> list:
	pred_AR=[]
	total_len = trainLen + horizon
	for i in range(trainLen,total_len,window):
		model=SARIMAX(df[:i],order=(p,0,0))
		res=model.fit(disp=False)
		predictions=res.get_prediction(0,i+window-1)
		oos_pred=predictions.predicted_mean.iloc[-window:]
		pred_AR.extend(oos_pred)
	return pred_AR



def rolling_forecast_ARMA(
	df:pd.DataFrame, 
  trainLen:int, 
  horizon:int, 
  window:int, 
  orderList:list,
  **kwargs
) -> list:
  pred_ARMA=[]
  total_len = trainLen + horizon
  for i in range(trainLen,total_len,window):
    model=SARIMAX(df[:i],order=(orderList[0],0,orderList[1]))
    res=model.fit(disp=False)
    predictions=res.get_prediction(0,i+window-1)
    oos_pred=predictions.predicted_mean.iloc[-window:]
    pred_ARMA.extend(oos_pred)
  return pred_ARMA



def rolling_forecast_ARIMA(
	df:pd.DataFrame, 
    trainLen:int, 
    horizon:int, 
    window:int, 
    orderList:list,
    d:int,
    **kwargs
) -> list:
  pred_ARIMA=[]
  total_len = trainLen + horizon
  for i in range(trainLen,total_len,window):
    model=SARIMAX(df[:i],order=(orderList[0],d,orderList[1]))
    res=model.fit(disp=False)
    predictions=res.get_prediction(0,i+window-1)
    oos_pred=predictions.predicted_mean.iloc[-window:]
    pred_ARIMA.extend(oos_pred)
  return pred_ARIMA



# def rolling_forecast_MLMA_AA(
#     df:pd.DataFrame, 
#     trainLen:int, 
#     horizon:int, 
#     window:int, 
#     method:str, 
#     orderList:list,
#     d:int
# ) -> list:
#   """
#     train_len: # of data points that can be used to fit a model
#     horizon: equal to the length of the test set and represents how many values must be predicted
#     window: specifies how many timesteps are predicted at a time. in our case,
#       because we have a MA(2) process, the window will be equal to 2.
#     method: specifies what model to use. Allows us to generate forecasts from the
#       naive methods and the MA(2) model
#     orderList: list specifying the p and q order terms of the model
#     d: specifies the order of integration for the ARIMA model
#   """
#   total_len = trainLen + horizon
#   if method == 'mean':
#     pred_mean = []
#     for i in range(trainLen, total_len, window):
#       mean = np.mean(df[:i].values)
#       pred_mean.extend(mean for _ in range(window))
#     return pred_mean
#   elif method == 'last':
#     pred_last_value = []
#     for i in range(trainLen, total_len, window):
#       last_value = df[:i].iloc[-1].values[0]
#       pred_last_value.extend(last_value for _ in range(window))
#       # pred_last_value=np.append(pred_last_value,last_value for _ in range(window))
#     return pred_last_value
#   elif method=='MA':
#     pred_MA = []
#     for i in range(trainLen, total_len, window):
#       # model = SARIMAX(df[:i], order=(0,0,4)) # was 0,0,2
#       model = SARIMAX(df[:i], order=(0,0,orderList[1])) # 0,0,1
#       res = model.fit(disp=False)
#       predictions = res.get_prediction(0,i + window - 1)
#       oos_pred = predictions.predicted_mean.iloc[-window:]
#       pred_MA.extend(oos_pred)
#     return pred_MA
#   elif method=='AR':
#     pred_AR=[]
#     for i in range(trainLen,total_len,window):
#       model=SARIMAX(df[:i],order=(orderList[0],0,0)) # 1,0,0
#       res=model.fit(disp=False)
#       predictions=res.get_prediction(0,i+window-1)
#       oos_pred=predictions.predicted_mean.iloc[-window:]
#       pred_AR.extend(oos_pred)
#     return pred_AR
#   elif method=='ARMA':
#     pred_ARMA=[]
#     for i in range(trainLen,total_len,window):
#       model=SARIMAX(df[:i],order=(orderList[0],0,orderList[1])) # 1,0,1
#       res=model.fit(disp=False)
#       predictions=res.get_prediction(0,i+window-1)
#       oos_pred=predictions.predicted_mean.iloc[-window:]
#       pred_ARMA.extend(oos_pred)
#     return pred_ARMA
#   elif method=='ARIMA':
#     pred_ARIMA=[]
#     for i in range(trainLen,total_len,window):
#       model=SARIMAX(df[:i],order=(orderList[0],d,orderList[1])) # 1,1,1
#       res=model.fit(disp=False)
#       predictions=res.get_prediction(0,i+window-1)
#       oos_pred=predictions.predicted_mean.iloc[-window:]
#       pred_ARIMA.extend(oos_pred)
#     return pred_ARIMA





def rolling_forecast_SARIMAX(
    endog:Union[pd.Series,list],
    exog:Union[pd.Series,list],
    trainLen:int,
    horizon:int,
    window:int,
    orderList:list,
    seasonalOrderList:list,
    d:int,
    D:int,
    s:int,
    **kwargs
) -> list:
  """
    endog: endogenous (dependent) variables
    exog: exogenous (independent) variables
    train_len: # of data points that can be used to fit a model
    horizon: equal to the length of the test set and represents how many values must be predicted
    window: specifies how many timesteps are predicted at a time. in our case,
      because we have a MA(2) process, the window will be equal to 2.
    method: specifies what model to use. Allows us to generate forecasts from the
      naive methods and the MA(2) model
    orderList: list specifying the p and q order terms of the model
    seasonalOrderList: list specifying the seaonal p and q order terms of the model
    d: specifies the order of integration for the ARIMA model
    D: specifies the seasonal order of integration
    s: frquency (notably m)
  """
  total_len = trainLen + horizon
  pred_SARIMAX = []
  for i in range(trainLen, total_len, window):
    model = SARIMAX(
              endog[:i],
              exog[:i],
              order=(orderList[0], d, orderList[1]),
              seasonal_order=(seasonalOrderList[0], D, seasonalOrderList[1], s),
              simple_differencing=False
            )
    res=model.fit(disp=False)
    predictions=res.get_prediction(exog=exog)
    oos_pred=predictions.predicted_mean.iloc[-window:]
    pred_SARIMAX.extend(oos_pred)
  return pred_SARIMAX





def rolling_forecast_VAR(
    endog:pd.DataFrame,
    trainLen:int,
    horizon:int,
    window:int,
    orderList:list,
    endog_var1:str,
    endog_var2:str,
    **kwargs
) -> list:
  """
  	endog: endogenous (dependent) variables
    trainLen: # of data points that can be used to fit a model
    horizon: equal to the length of the test set and represents how many values must be predicted
    window: specifies how many timesteps are predicted at a time. in our case,
      because we have a MA(2) process, the window will be equal to 2.
    orderList: list specifying the p and q order terms of the model
    endog_var1: endogenous variable 1
    endog_var1: endogenous variable 2
  """
  total_len = trainLen + horizon
  end_idx = trainLen
  #   if (method == 'VAR') | (method == 'VARMA'):
  var1_pred_VAR = []
  var2_pred_VAR = []
  for i in range(trainLen, total_len, window):
    model = VARMAX(endog[:i], order=(orderList[0],orderList[1]))
    res = model.fit(disp=False)
    predictions = res.get_prediction(0,i+window-1)

    oos_pred_var1 = predictions.predicted_mean.iloc[-window:][endog_var1]
    oos_pred_var2 = predictions.predicted_mean.iloc[-window:][endog_var2]

    var1_pred_VAR.extend(oos_pred_var1)
    var2_pred_VAR.extend(oos_pred_var2)
  return var1_pred_VAR, var2_pred_VAR

def rolling_forecast_VAR_list(
    endog:pd.DataFrame,
    trainLen:int,
    horizon:int,
    window:int,
    orderList:list,
    endog_var_list:list,
    **kwargs
) -> dict:
  """
    endog: endogenous (dependent) variables
    trainLen: # of data points that can be used to fit a model
    horizon: equal to the length of the test set and represents how many values must be predicted
    window: specifies how many timesteps are predicted at a time. in our case,
      because we have a MA(2) process, the window will be equal to 2.
    orderList: list specifying the p and q order terms of the model
    endog_var1: endogenous variable 1
    endog_var1: endogenous variable 2
  """
  total_len = trainLen + horizon
  predictions_dict = {}
  for endog_var in endog_var_list:
    var_pred=[]
    for i in range(trainLen, total_len, window):
      model = VARMAX(endog[:i], order=(orderList[0],orderList[1]))
      res = model.fit(disp=False)
      predictions = res.get_prediction(0,i+window-1)
      oos_pred = predictions.predicted_mean.iloc[-window:][endog_var]
      var_pred.extend(oos_pred)
    predictions_dict[endog_var] = var_pred
  return predictions_dict
  
  # elif method == 'last':
  #   realdpi_pred_last = []
  #   realcons_pred_last = []
  #   for i in range(trainLen, total_len, window):
  #     realdpi_last = endog[:i].iloc[-1]['realdpi']
  #     realcons_last = endog[:i].iloc[-1]['realcons']
  #     realdpi_pred_last.extend(realdpi_last for _ in range(window))
  #     realcons_pred_last.extend(realcons_last for _ in range(window))
  #   return realdpi_pred_last, realcons_pred_last





def rolling_forecast_VARMAX(
    endog:pd.DataFrame,
    trainLen:int,
    horizon:int,
    window:int,
    exog:Union[pd.Series,list],
    orderList:list,
    endog_var1:str,
    endog_var2:str,
    **kwargs
) -> list:
  """
  	endog: endogenous (dependent) variables
    trainLen: # of data points that can be used to fit a model
    horizon: equal to the length of the test set and represents how many values must be predicted
    window: specifies how many timesteps are predicted at a time. in our case,
      because we have a MA(2) process, the window will be equal to 2.
    method: specifies what model to use. Allows us to generate forecasts from the
      naive methods and the MA(2) model
    exog: exogenous (independent) variables
    orderList: list specifying the p and q order terms of the model
    endog_var1: endogenous variable 1
    endog_var1: endogenous variable 2
  """
  total_len = trainLen + horizon

  var1_pred_VARMAX = []
  var2_pred_VARMAX = []
  for i in range(trainLen, total_len, window):
  	model = VARMAX(endog[:i], exog[:i], order=(orderList[0], orderList[1]))
  	res = model.fit(disp=False)
  	predictions = res.get_prediction(0, i + window - 1, exog = exog.iloc[-1])

  	oos_pred_var1 = predictions.predicted_mean.iloc[-window:][endog_var1]
  	oos_pred_var2 = predictions.predicted_mean.iloc[-window:][endog_var2]

  	var1_pred_VARMAX.extend(oos_pred_var1)
  	var2_pred_VARMAX.extend(oos_pred_var2)
  return var1_pred_VARMAX, var2_pred_VARMAX




def rolling_forecast_exponential(
  df:pd.DataFrame, 
  trainLen:int, 
  horizon:int, 
  window:int, 
  orderList:list,
  **kwargs
) -> list:
  pred_DExp=[]
  total_len = trainLen + horizon
  model=ExponentialSmoothing(df.iloc[:total_len],trend=None)
  res=model.fit(smoothing_level=orderList[0],optimized=True)
  for i in range(trainLen,total_len-horizon+1,window):
    predictions=res.forecast(steps=i+window-1)
    pred_DExp.extend(predictions.values)

  return pred_DExp



def rolling_forecast_double_exponential(
  df:pd.DataFrame, 
  trainLen:int, 
  horizon:int, 
  window:int, 
  orderList:list,
  **kwargs
) -> list:
  pred_DExp=[]
  total_len = trainLen + horizon
  model=ExponentialSmoothing(df.iloc[:total_len],trend=None)
  res=model.fit(smoothing_level=orderList[0],smoothing_trend=orderList[1],optimized=True)
  for i in range(trainLen,total_len-horizon+1,window):
    predictions=res.forecast(steps=i+window-1)
    pred_DExp.extend(predictions.values)

  return pred_DExp


##########################################################################################
##########################################################################################


def exponential_smoothing(series, alpha):

    result = [series[0]] # first value is same as series
    for n in range(1, len(series)):
        result.append(alpha * series[n] + (1 - alpha) * result[n-1])
    return result
  
def plot_exponential_smoothing(series, alphas, x_lim=None):
 
    fig, ax = plt.subplots(figsize=(12,6))
    linewidth=2.5
    ax.plot(series.values, "c", label = "Actual", linewidth=linewidth)
    for alpha in alphas:
        ax.plot(exponential_smoothing(series, alpha), label="Alpha {}".format(alpha), linewidth=linewidth)
        
    # Check if x_lim is a list
    if isinstance(x_lim, list):
        ax.set_xlim(x_lim[0],x_lim[1])
    elif isinstance(x_lim,int):
        ax.set_xlim(0,x_lim)
    ax.legend(loc="best")
    ax.set_title("Exponential Smoothing")
    ax.grid(True);


def double_exponential_smoothing(series, alpha, beta):

    result = [series[0]]
    for n in range(1, len(series)+1):
        if n == 1:
            level, trend = series[0], series[1] - series[0]
        if n >= len(series): # forecasting
            value = result[-1]
        else:
            value = series[n]
        last_level, level = level, alpha * value + (1 - alpha) * (level + trend)
        trend = beta * (level - last_level) + (1 - beta) * trend
        result.append(level + trend)
    return result

def plot_double_exponential_smoothing(series, alphas, betas, x_lim=None):
     
    fig, ax = plt.subplots(figsize=(17,8))
    linewidth=2.5
    ax.plot(series.values, label = "Actual")
    for alpha in alphas:
        for beta in betas:
            ax.plot(double_exponential_smoothing(series, alpha, beta), label="Alpha {}, beta {}".format(alpha, beta),linewidth=linewidth)
    # Check if x_lim is a list
    if isinstance(x_lim, list):
        ax.set_xlim(x_lim[0],x_lim[1])
    elif isinstance(x_lim,int):
        ax.set_xlim(0,x_lim)
    ax.legend(loc="best")
    ax.set_title("Double Exponential Smoothing")
    ax.grid(True)
    




##########################################################################################
##########################################################################################


train_df=pd.DataFrame()
val_df=pd.DataFrame()
test_df=pd.DataFrame()

class DataWindow():
    def __init__(self, 
                 input_width, 
                 label_width, 
                 shift, 
                 batch_size,
                 train_df=train_df, 
                 val_df=val_df, 
                 test_df=test_df, 
                 label_columns=None):
        
        self.train_df = train_df
        self.val_df = val_df
        self.test_df = test_df
        self.label_columns = label_columns
        self.batch_size = batch_size
        
        if label_columns is not None:
            self.label_columns_indices = {name: i for i, name in enumerate(label_columns)}
        self.column_indices = {name: i for i, name in enumerate(train_df.columns)}
        
        self.input_width = input_width
        self.label_width = label_width
        self.shift = shift
        
        self.total_window_size = input_width + shift
        
        self.input_slice = slice(0, input_width)
        self.input_indices = np.arange(self.total_window_size)[self.input_slice]
        
        self.label_start = self.total_window_size - self.label_width
        self.labels_slice = slice(self.label_start, None)
        self.label_indices = np.arange(self.total_window_size)[self.labels_slice]
    
    def split_to_inputs_labels(self, features):
        inputs = features[:, self.input_slice, :]
        labels = features[:, self.labels_slice, :]
        if self.label_columns is not None:
            labels = tf.stack(
                [labels[:,:,self.column_indices[name]] for name in self.label_columns],
                axis=-1
            )
        inputs.set_shape([None, self.input_width, None])
        labels.set_shape([None, self.label_width, None])
        
        return inputs, labels
    
    def plot(self, model=None, plot_col='traffic_volume', max_subplots=3):
        inputs, labels = self.sample_batch
        
        plt.figure(figsize=(12, 8))
        plot_col_index = self.column_indices[plot_col]
        max_n = min(max_subplots, len(inputs))
        
        for n in range(max_n):
            plt.subplot(3, 1, n+1)
            plt.ylabel(f'{plot_col} [scaled]')
            plt.plot(self.input_indices, inputs[n, :, plot_col_index],
                     label='Inputs', marker='.', zorder=-10)

            if self.label_columns:
              label_col_index = self.label_columns_indices.get(plot_col, None)
            else:
              label_col_index = plot_col_index

            if label_col_index is None:
              continue

            plt.scatter(self.label_indices, labels[n, :, label_col_index],
                        edgecolors='k', marker='s', label='Labels', c='green', s=64)
            if model is not None:
              predictions = model(inputs)
              plt.scatter(self.label_indices, predictions[n, :, label_col_index],
                          marker='X', edgecolors='k', label='Predictions',
                          c='red', s=64)

            if n == 0:
              plt.legend()

        plt.xlabel('Time (h)')
        
    def make_dataset(self, data):
        data = np.array(data, dtype=np.float32)
        ds = tf.keras.preprocessing.timeseries_dataset_from_array(
            data=data,
            targets=None,
            sequence_length=self.total_window_size,
            sequence_stride=1,
            shuffle=True,
            batch_size=self.batch_size
        )
        
        ds = ds.map(self.split_to_inputs_labels)
        return ds
    
    @property
    def train(self):
        return self.make_dataset(self.train_df)
    
    @property
    def val(self):
        return self.make_dataset(self.val_df)
    
    @property
    def test(self):
        return self.make_dataset(self.test_df)  
    
    @property
    def sample_batch(self):
        result = getattr(self, '_sample_batch', None)
        if result is None:
            result = next(iter(self.train))
            self._sample_batch = result
        return result



class Baseline(Model):
  def __init__(self,label_index=None):
    super().__init__()
    self.label_index=label_index
  def call(self,inputs):
    if self.label_index is None:
      return inputs
    elif isinstance(self.label_index,list):
      tensors=[]
      for index in self.label_index:
        result=inputs[:,:,index]
        result=result[:,:,tf.newaxis]
        tensors.append(result)
      return tf.concat(tensors,axis=-1)
    result=inputs[:,:,self.label_index]
    return result[:,:,tf.newaxis]


class MultiStepLastBaseline(Model):
    def __init__(self,label_index=None,steps=5):
        super().__init__()
        self.label_index = label_index
        self.steps = steps
    def call(self,inputs):
        if self.label_index is None:
            return tf.title(inputs[:,-1:,:],[1,self.steps,1])
        return tf.tile(inputs[:,-1:,self.label_index:],[1,self.steps,1])



class RepeatBaseline(Model):
    def __init__(self,label_index=None):
        super().__init__()
        self.label_index=label_index
    def call(self,inputs):
        return inputs[:,:,self.label_index:]



def compile_and_fit(model, window, patience=3, max_epochs=50):
    early_stopping = EarlyStopping(monitor='val_loss',
                                   patience=patience,
                                   mode='min')
    
    model.compile(loss=MeanSquaredError(),
                  optimizer=Adam(),
                  metrics=[MeanAbsoluteError()])
    
    history = model.fit(window.train,
                       epochs=max_epochs,
                       validation_data=window.val,
                       callbacks=[early_stopping])
    
    return history



class AutoRegressive(Model):
    def __init__(self, units, out_steps):
        super().__init__()
        self.out_steps = out_steps
        self.units = units
        self.lstm_cell = LSTMCell(units)
        self.lstm_rnn = RNN(self.lstm_cell, return_state=True)
        self.dense = Dense(train_df.shape[1])
    def warmup(self, inputs):
        x, *state = self.lstm_rnn(inputs)
        prediction = self.dense(x)
        return prediction, state
    def call(self, inputs, training=None):
        predictions = []
        prediction, state = self.warmup(inputs)
        predictions.append(prediction)
        for n in range(1, self.out_steps):
            x = prediction
            x, state = self.lstm_cell(x, states=state, training=training)
            prediction = self.dense(x)
            predictions.append(prediction)
        predictions = tf.stack(predictions)
        predictions = tf.transpose(predictions, [1, 0, 2])
        return predictions





def acf_pacf_df_export(bid:str,file_path:str,field_values:list):
  # bid_directory=os.path.join(file_path,bid)
  bid_directory=create_player_folder(bid,file_path=file_path)

  conf_int=1.96/np.sqrt(len(field_values))

  # Generate acf table and save
  acf_results=sm.tsa.acf(field_values)
  sig_lags=np.where((acf_results>=conf_int)|(acf_results<=-conf_int))[0]
  df_acf_sig_lags=pd.DataFrame({'Lag':sig_lags,'Autocorrelation':acf_results[sig_lags]})
  csv_filename=os.path.join(bid_directory,f'{bid}_acf_sig_lags.csv')
  df_acf_sig_lags.to_csv(csv_filename,index=False)

  # Generate pacf table and save
  pacf_results=sm.tsa.pacf(field_values)
  sig_lags=np.where((pacf_results>=conf_int)|(pacf_results<=-conf_int))[0]
  df_pacf_sig_lags=pd.DataFrame({'Lag':sig_lags,'Partial Autocorrelation':pacf_results[sig_lags]})
  csv_filename=os.path.join(bid_directory,f'{bid}_pacf_sig_lags.csv')
  df_pacf_sig_lags.to_csv(csv_filename,index=False)

  return df_acf_sig_lags, df_pacf_sig_lags

def acf_pacf_plot_export(bid:str,file_path:str,field_values:list):
  bid_directory=create_player_folder(bid,file_path=file_path)
  plt.figure(figsize=(12,6))
  ax1=plt.subplot(121)
  plot_acf(field_values,lags=min(len(field_values)-1,10),ax=ax1)
  plt.title(f'ACF Plot for Player {bid}')
  plt.xlabel('Lag')
  plt.ylabel('Autoccorelation')

  ax2=plt.subplot(122)
  plot_pacf(field_values,lags=min(len(field_values)-1,10),ax=ax2)
  plt.title(f'PACF Plot for Player {bid}')
  plt.xlabel('Lag')
  plt.ylabel('Partial Autocorrelation')

  plot_file_name=os.path.join(bid_directory,f'acf_pacf_plot_{bid}.png')
  plt.savefig(plot_file_name)
  plt.close()


def find_consecutive_end_indices(lags):
    end_indices = []
    for i in range(len(lags) - 1):
        # If the next 'Lag' is not the consecutive number, mark the current as the end
        if lags.iloc[i + 1] != lags.iloc[i] + 1:
            end_indices.append(i)
    # Always add the last item as an end index if there are entries
    if len(lags) > 0:
        end_indices.append(len(lags) - 1)
    return end_indices

# def obtain_parameter_extracts(bid:str,file_path:str):
#   bid_directory=create_player_folder(bid=bid,file_path=file_path)
#   optimized_arima_file=f'{bid}_optimized_arma.csv'
#   auto_arima_file=f'{bid}_autoarima.csv'
#   optimized_arima_file_path=os.path.join(bid_directory,optimized_arima_file)
#   auto_arima_file_path=os.path.join(bid_directory,auto_arima_file)

#   optimized_arima_df=pd.read_csv(optimized_arima_file_path,sep=',')
#   auto_arima_df=pd.read_csv(auto_arima_file_path,sep=',')

#   return optimized_arima_df,auto_arima_df

def obtain_optimized_arma_parameter_extracts(bid:str,file_path:str):
  bid_directory=create_player_folder(bid=bid,file_path=file_path)
  optimized_arima_file=f'{bid}_optimized_arma.csv'
  optimized_arima_file_path=os.path.join(bid_directory,optimized_arima_file)
  optimized_arima_df=pd.read_csv(optimized_arima_file_path,sep=',')

  return optimized_arima_df


def obtain_optimized_exp_parameter_extracts(bid:str,file_path:str,exponential_type:str):
  bid_directory=create_player_folder(bid=bid,file_path=file_path)
  if exponential_type=='single':
    optimized_exp_file=f'{bid}_optimized_sgl_exp.csv'
    optimized_exp_file_path=os.path.join(bid_directory,optimized_exp_file)
    optimized_exp_df=pd.read_csv(optimized_exp_file_path,sep=',')
  elif exponential_type=='double':
    optimized_exp_file=f'{bid}_optimized_dbl_exp.csv'
    optimized_exp_file_path=os.path.join(bid_directory,optimized_exp_file)
    optimized_exp_df=pd.read_csv(optimized_exp_file_path,sep=',')
  return optimized_exp_df



#imhere
# def obtain_optimized_exp_parameter_extracts(bid:str,file_path:str):
#   bid_directory=create_player_folder(bid=bid,file_path=file_path)
#   optimized_arima_file=f'{bid}_optimized_arma.csv'
#   optimized_arima_file_path=os.path.join(bid_directory,optimized_arima_file)
#   optimized_arima_df=pd.read_csv(optimized_arima_file_path,sep=',')

#   return optimized_arima_df


def seperate_pq_column(df:pd.DataFrame):
  pq_extract=df["(p,q)"].str.extract(r'\((?P<p>\d+),\s*(?P<q>\d+)\)')
  pq_extract["p"]=pd.to_numeric(pq_extract["p"])
  pq_extract["q"]=pd.to_numeric(pq_extract["q"])
  df=df.drop("(p,q)",axis=1)
  result_df=pd.concat([df,pq_extract],axis=1)
  return result_df

# def separate_ab_column(df:pd.DataFrame):
#   ab_extract=df["(alpha,beta)"].str.extract(r'\((?P<alpha>\d+),\s*(?P<beta>\d+)\)')
#   ab_extract["alpha"]=pd.to_numeric(ab_extract["alpha"])
#   ab_extract["beta"]=pd.to_numeric(ab_extract["beta"])
#   df=df.drop("(alpha,beta)",axis=1)
#   results_df=pd.concat([df,ab_extract],axis=1)
#   return results_df

def optimized_param_decision(optimized_df1:pd.DataFrame):
  sep_pq_optimized_df1=seperate_pq_column(optimized_df1)
  first_aic = sep_pq_optimized_df1.loc[0,"AIC"]
  second_aic = sep_pq_optimized_df1.loc[1,"AIC"]
  third_aic = sep_pq_optimized_df1.loc[2,"AIC"]

  first_second_delta = second_aic - first_aic
  first_third_delta = third_aic - first_aic

  first_second_delta = first_second_delta * -1
  first_third_delta = first_third_delta * -1

  aic_threshold = 100
  idx=0
  if (first_second_delta >= aic_threshold) and (first_third_delta >= aic_threshold):
    idx=3
  elif (first_second_delta >= aic_threshold) and (first_third_delta <= aic_threshold):
    idx=2
  p=sep_pq_optimized_df1.loc[idx,"p"]
  q=sep_pq_optimized_df1.loc[idx,"q"]

  return p,q


def optimized_sgl_exp_decision(optimized_exp_df:pd.DataFrame):
  # sep_ab_optimized_df=separate_ab_column(optimized_exp_df)
  first_aic = optimized_exp_df.loc[0,"AIC"]
  second_aic = optimized_exp_df.loc[1,"AIC"]
  third_aic = optimized_exp_df.loc[2,"AIC"]

  first_second_delta = second_aic - first_aic
  first_third_delta = third_aic - first_aic

  aic_threshold = 100
  idx=0
  if (first_second_delta >= aic_threshold) and (first_third_delta >= aic_threshold):
    idx=3
  elif (first_second_delta >= aic_threshold) and (first_third_delta <= aic_threshold):
    idx=2
  alpha = optimized_exp_df.loc[idx,"(alpha)"]
  return alpha

def optimized_dbl_exp_decision(optimized_exp_df:pd.DataFrame):
  # sep_ab_optimized_df=separate_ab_column(optimized_exp_df)
  first_aic = optimized_exp_df.loc[0,"AIC"]
  second_aic = optimized_exp_df.loc[1,"AIC"]
  third_aic = optimized_exp_df.loc[2,"AIC"]

  first_second_delta = second_aic - first_aic
  first_third_delta = third_aic - first_aic

  aic_threshold = 100
  idx=0
  if (first_second_delta >= aic_threshold) and (first_third_delta >= aic_threshold):
    idx=3
  elif (first_second_delta >= aic_threshold) and (first_third_delta <= aic_threshold):
    idx=2
  alpha = optimized_exp_df.loc[idx,"alpha"]
  beta = optimized_exp_df.loc[idx,"beta"]
  return alpha,beta


# def final_arima_params()


def save_exponential_smoothing_residual_summary(residuals:list,bid:str,file_path:str,exponential_type:str,orderList:list):
  bid_directory=create_player_folder(bid,file_path=file_path)
  # residuals=model.resid
  # residuals=residuals[-np.isnan(residuals)]

  fig,axs=plt.subplots(3,2,figsize=(14,14))
  axs[0,0].plot(range(0,len(residuals)),residuals)
  axs[0,0].set_title('Residuals')
  axs[0,0].set_xlabel('Time')
  axs[0,0].set_ylabel('Residuals')
  axs[0,0].axhline(y=0,color='r',linestyle='--')

  axs[0,1].hist(residuals,bins=20,density=True)
  axs[0,1].set_title('Histogram of Residuals')
  axs[0,1].set_xlabel('Residuals')
  axs[0,1].set_ylabel('Density')

  sm.qqplot(residuals,line='s',ax=axs[1,0])
  axs[1,0].set_title('Normal Q-Q Plot')

  plot_acf(residuals,lags=20,ax=axs[1,1])
  axs[1,1].set_title('Autocorrelation Function (ACF) Plot')
  axs[1,1].set_xlabel('Lag')
  axs[1,1].set_ylabel('Autocorrelation')

  plot_pacf(residuals,lags=20,ax=axs[2,0])
  axs[2,0].set_title('Partial Autocorrelation Function (PACF) Plot')
  axs[2,0].set_xlabel('Lag')
  axs[2,0].set_ylabel('Autocorrelation')

  if exponential_type=='single':
    plt.suptitle(f'Model Residual Diagnostics (alpha={orderList[0]})')
    plot_file_name=os.path.join(bid_directory,f'sgl_exponential_residuals_plot_{bid}.png')
  elif exponential_type=='double':
    plt.suptitle(f'Model Residuals Diagnostics (alpha={orderList[0]},beta={orderList[1]})')
    plot_file_name=os.path.join(bid_directory,f'dbl_exponential_residuals_plot_{bid}.png')

  plt.tight_layout()
  plt.savefig(plot_file_name)
  plt.close()

def save_arma_residual_diagnostics(model,bid:str,file_path:str,orderList:list):
  bid_directory=create_player_folder(bid,file_path=file_path)
  fig=model.plot_diagnostics(figsize=(10,8))
  plt.suptitle(f'Model Residual Diagnostics (p={orderList[0]},q={orderList[1]})')
  plt.tight_layout()

  resid_diag_name=f'{bid}_residual_diagnostics.png'
  resid_diag_name_file_path=os.path.join(bid_directory,resid_diag_name)

  plt.savefig(resid_diag_name_file_path)
  plt.close(fig)

  resid_ljungbox_name=f'{bid}_Ljiung_Box_diagnostics.csv'
  resid_ljungbox_name_file_path=os.path.join(bid_directory,resid_ljungbox_name)

  resid=model.resid
  acorr_ljungbox_df=acorr_ljungbox(resid,np.arange(1,11,1))
  acorr_ljungbox_df.to_csv(resid_ljungbox_name_file_path,index=False)


def window_sizing(horizon:int,p:int,q:int):
  window=min(p,q)
  if horizon%window != 0:
    window=1
    return window
  else:
    return window



def is_MovingAverage(p:int,q:int)->bool:
  if (p==0) and (q!=0):
    return True
  else:
    return False

def is_AutoRegressive(p:int,q:int)->bool:
  if (p!=0) and (q==0):
    return True
  else:
    return False

def is_MA_or_AR_only(p:int,q:int)->bool:
  ma_bool=is_MovingAverage(p,q)
  ar_bool=is_AutoRegressive(p,q)
  if ma_bool | ar_bool:
    return True
  else:
    return False

def decide_MA_AR(p:int,q:int)->int:
  decision=None
  if (p==0) and (q!=0):
    decision='MA'
    return decision, q
  elif (p!=0) and (q==0):
    decision='AR'
    return decision, p


def save_model(fit_model,file_path:str,bid:str,date:str,model_type:str):
  model_file_path=create_model_folder(bid=bid,file_path=file_path)
  if model_type=='ARMA':
    model_file_name=os.path.join(model_file_path,f'{bid}_{date}_ARMA.pkl')
    with open(model_file_name,'wb') as file:
      pickle.dump(fit_model,file)
  elif model_type=='ARIMA':
    model_file_name=os.path.join(model_file_path,f'{bid}_{date}_ARIMA.pkl')
    with open(model_file_name,'wb') as file:
      pickle.dump(fit_model,file)
  elif model_type=='MA':
    model_file_name=os.path.join(model_file_path,f'{bid}_{date}_MA.pkl')
    with open(model_file_name,'wb') as file:
      pickle.dump(fit_model,file)
  elif model_type=='AR':
    model_file_name=os.path.join(model_file_path,f'{bid}_{date}_AR.pkl')
    with open(model_file_name,'wb') as file:
      pickle.dump(fit_model,file)
  elif model_type=='SGL EXP':
    model_file_name=os.path.join(model_file_path,f'{bid}_{date}_SGL_EXP.pkl')
    with open(model_file_name,'wb') as file:
      pickle.dump(fit_model,file)
  elif model_type=='DBL EXP':
    model_file_name=os.path.join(model_file_path,f'{bid}_{date}_DBL_EXP.pkl')
    with open(model_file_name,'wb') as file:
      pickle.dump(fit_model,file)
  elif model_type=='LINEAR':
    model_file_name=os.path.join(model_file_path,f'{bid}_{date}_LINEAR.pkl')
    with open(model_file_name,'wb') as file:
      pickle.dump(fit_model,file)
  elif model_type=='NEURAL_NETWORK':
    model_file_name=os.path.join(model_file_path,f'{bid}_{date}_NEURAL_NETWORK.pkl')
    with open(model_file_name,'wb') as file:
      pickle.dump(fit_model,file)
  elif model_type=='LSTM':
    model_file_name=os.path.join(model_file_path,f'{bid}_{date}_LSTM.pkl')
    with open(model_file_name,'wb') as file:
      pickle.dump(fit_model,file)

def save_scaler(fit_model_scaler,file_path:str,bid:str,model_type:str):
  model_scale_file_path=create_model_scaler_folder(bid=bid,file_path=file_path)
  if model_type=='stat':
    model_scaler_file_name=os.path.join(model_scale_file_path,f'{bid}_STAT_scaler.pkl')
  elif model_type=='ml':
    model_scaler_file_name=os.path.join(model_scale_file_path,f'{bid}_ML_scaler.pkl')
  with open(model_scaler_file_name,'wb') as file:
    pickle.dump(fit_model_scaler,file)

  # if model_type=='LINEAR':
  #   model_scaler_file_name=os.path.join(model_scale_file_path,f'{bid}_{date}_LINEAR.pkl')
  #   with open(model_scaler_file_name,'wb') as file:
  #     pickle.dump(fit_model_scaler,file)
  # elif model_type=='LSTM':
  #   model_scaler_file_name=os.path.join(model_scale_file_path,f'{bid}_{date}_LSTM.pkl')
  #   with open(model_scaler_file_name,'wb') as file:
  #     pickle.dump(fit_model_scaler,file)
  # elif model_type=='NEURAL_NETWORK':
  #   model_scaler_file_name=os.path.join(model_scale_file_path,f'{bid}_{date}_NEURAL_NETWORK.pkl')
  #   with open(model_scaler_file_name,'wb') as file:
  #     pickle.dump(fit_model_scaler,file)


def load_model(file:str):
  with open(file,'rb') as file:
    loaded_model=pickle.load(file)
  return loaded_model

def load_scaler(file:str):
  with open(file,'rb') as file:
    loaded_scaler=pickle.load(file)
  return loaded_scaler


def track_train_test_sizes(file_path:str,bid:str,train:pd.DataFrame,test:pd.DataFrame):
  file_name=os.path.join(file_path,f'{bid}',f'{bid}_train_test_sizes.csv')
  num_rows_train=len(train)
  num_rows_test=len(test)
  df_summary=pd.DataFrame({
      'DataFrame':['train','test'],
      'Number of rows':[num_rows_train,num_rows_test]
  })
  df_summary.to_csv(file_name,index=False)


