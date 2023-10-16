import os
import requests
import pandas as pd
import numpy as np
import datetime as dt
import time

import mysql.connector as mysql
from mysql.connector import Error

from bs4 import BeautifulSoup
from my_functions import day_injuries_basketball
from datetime import datetime


sports_db_admin_host=os.environ.get('sports_db_admin_host')
sports_db_admin_db='basketball'
sports_db_admin_user=os.environ.get('sports_db_admin_user')
sports_db_admin_pw=os.environ.get('sports_db_admin_pw')
sports_db_admin_port=os.environ.get('sports_db_admin_port')

pd.set_option('display.max_columns', None)
pd.set_option('display.max_rows', None)


start_date='2000-01-01'
cd=dt.datetime.now()
current_day=cd.strftime('%Y-%m-%d')

# dt_object=datetime.strptime(start_date,'%Y-%m-%d')
# dt_object=dt_object.replace(day=1)
# dt_object=str(dt_object).split()[0]
# print(dt_object)

# print(start_date)
# print(current_day)


# day_inj=day_injuries_basketball('2022-10-11')
# print(day_inj)



connection=mysql.connect(host=sports_db_admin_host,
                    database=sports_db_admin_db,
                    user=sports_db_admin_user,
                    password=sports_db_admin_pw,
                    port=sports_db_admin_port)

if connection.is_connected():
	cursor=connection.cursor()
	qry="""SELECT MAX(day) AS recent_date FROM basketball.hist_player_inj;"""
	cursor.execute(qry)
	recent_inj_date=cursor.fetchone()
	(recent_inj_date,)=recent_inj_date

if connection.is_connected():
	cursor.close()
	connection.close()
	print('MySQL connection is closed')


# print(recent_inj_date)
# recent_inj_date='2020-06-11'



if recent_inj_date is None:

	# month_range_start=pd.date_range(start=start_date, end=current_day, freq='MS')
	# month_range_end=pd.date_range(start=start_date, end=current_day, freq='M')
	# month_range_start=month_range_start.astype(str).tolist()
	# month_range_end=month_range_end.astype(str).tolist()
	# month_range_end.append(current_day)
	# print('going to backfill')
	# df=pd.DataFrame({'month_start':month_range_start,'month_end':month_range_end})
	# for idx,row in df.iterrows():
	# 	data=day_injuries_basketball(start_day=row['month_start'],end_day=row['month_end'])
	# 	print(data)
	# 	print(data.shape)
	# 	time.sleep(5)
	date_range=pd.date_range(start=start_date,end=current_day)
	# print(date_range)
	for day in date_range:
		day=str(day).split()[0]
		try:
			data=day_injuries_basketball(day)
			connection=mysql.connect(host=sports_db_admin_host,
                                 database=sports_db_admin_db,
                                 user=sports_db_admin_user,
                                 password=sports_db_admin_pw,
                                 port=sports_db_admin_port,
                                 allow_local_infile=True)
			cursor=connection.cursor()
			file_path=f'/Users/franciscoavalosjr/Desktop/basketball-folder/tmp_data/inj_players_{day}.csv'
			data.to_csv(file_path,index=False)
			qry=f"LOAD DATA LOCAL INFILE '{file_path}' REPLACE INTO TABLE basketball.hist_player_inj FIELDS TERMINATED BY ',' IGNORE 1 ROWS;"
			cursor.execute(qry)
			connection.commit()
			del data
			os.remove(file_path)
			if connection.is_connected():
				cursor.close()
				connection.close()
				print('Closed MySQL connection')
			print(f'inserted data for {day}')
		except Exception as e:
			print(f'No data for {day}')
		time.sleep(5)

else:
	date_range=pd.date_range(start=recent_inj_date,end=current_day)
	print(f'pick up from {recent_inj_date}')

	# dt_object=datetime.strptime(recent_inj_date,'%Y-%m-%d')
	# dt_object=dt_object.replace(day=1)
	# dt_object=str(dt_object).split()[0]
	# print(f'pick up from {dt_object}')


	# month_range_start=pd.date_range(start=dt_object, end=current_day, freq='MS')
	# month_range_end=pd.date_range(start=recent_inj_date, end=current_day, freq='M')
	# month_range_start=month_range_start.astype(str).tolist()
	# month_range_end=month_range_end.astype(str).tolist()
	# month_range_end.append(current_day)
	# df=pd.DataFrame({'month_start':month_range_start,'month_end':month_range_end})
	# # print(df)

	for day in date_range:
		day=str(day).split()[0]
		try:
			data=day_injuries_basketball(day)
			connection=mysql.connect(host=sports_db_admin_host,
                                 database=sports_db_admin_db,
                                 user=sports_db_admin_user,
                                 password=sports_db_admin_pw,
                                 port=sports_db_admin_port,
                                 allow_local_infile=True)
			cursor=connection.cursor()
			file_path=f'/Users/franciscoavalosjr/Desktop/basketball-folder/tmp_data/inj_players_{day}.csv'
			data.to_csv(file_path,index=False)
			qry=f"LOAD DATA LOCAL INFILE '{file_path}' REPLACE INTO TABLE basketball.hist_player_inj FIELDS TERMINATED BY ',' IGNORE 1 ROWS;"
			cursor.execute(qry)
			connection.commit()
			del data
			os.remove(file_path)
			if connection.is_connected():
				cursor.close()
				connection.close()
				print('Closed MySQL connection')
			print(f'inserted data for {day}')
		except Exception as e:
			print(f'No data for {day}')
		time.sleep(5)

 