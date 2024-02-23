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
# import statsmodels.api as sm

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



def mape(y_true, y_pred):
  return np.mean(np.abs((y_true - y_pred) / y_true)) * 100



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







##########################################################################################
##########################################################################################




def rolling_forecast_mean(
	df:Union[pd.DataFrame,list],
	trainLen:int,
	horizon:int,
	window:int
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
	window:int
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
  q:int
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
	p:int
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
  orderList:list
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
    d:int
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
    s:int
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
    endog_var2:str
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
    endog_var_list:list
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
    endog_var2:str
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

















