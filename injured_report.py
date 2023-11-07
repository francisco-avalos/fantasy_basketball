import requests
import pandas as pd
import time
import mysql.connector as mysql

from bs4 import BeautifulSoup
from datetime import datetime
from datetime import timedelta
from mysql.connector import Error

import os



sports_db_admin_host=os.environ.get('sports_db_admin_host')
sports_db_admin_db='basketball'
sports_db_admin_user=os.environ.get('sports_db_admin_user')
sports_db_admin_pw=os.environ.get('sports_db_admin_pw')
sports_db_admin_port=os.environ.get('sports_db_admin_port')


out_players=[
'https://www.rotowire.com/basketball/player/cameron-johnson-4916'
# 'https://www.rotowire.com/basketball/player/lonnie-walker-4435'
# 'https://www.rotowire.com/basketball/player/kyrie-irving-3186'
# 'https://www.rotowire.com/basketball/player/klay-thompson-3197'
]
out_players_yf=[
'https://www.rotowire.com/basketball/player/markelle-fultz-4100',
'https://www.rotowire.com/basketball/player/nic-claxton-4827',
'https://www.rotowire.com/basketball/player/cj-mccollum-3437',
'https://www.rotowire.com/basketball/player/anthony-davis-3297'
]


report_run_date=datetime.now()-timedelta(days=0)
report_run_date=report_run_date.strftime('%Y-%m-%d')

df=pd.DataFrame(columns=['name', 'injury', 'exp_return_date'])
idx=0

df_yh=pd.DataFrame(columns=['name', 'injury', 'exp_return_date'])
idx_yh=0

for p in out_players:
	soup=BeautifulSoup(requests.get(p).text,"html.parser")
	dat=soup.find_all(class_='p-card__injury-data')
	data=[x.find('b').text for x in dat]
	inj_player_name=[n.find('h1').text for n in soup.find_all('div',attrs={'class':'p-card'})]
	inj_player_name=str(inj_player_name).strip('[]')
	data.insert(0, inj_player_name)
	# print(data)
	df.loc[idx]=data
	idx+=1
	time.sleep(5)


df.exp_return_date=pd.to_datetime(df.exp_return_date)
df['date_report_ran']=report_run_date
df['name']=df['name'].apply(lambda x: x.replace('\'', '').replace('"', ''))



df['name']=df['name'].astype(str)
df['injury']=df['injury'].astype(str)
df['exp_return_date']=df['exp_return_date'].astype(str)
df['date_report_ran']=df['date_report_ran'].astype(str)


for p in out_players_yf:
	soup=BeautifulSoup(requests.get(p).text,"html.parser")
	dat=soup.find_all(class_='p-card__injury-data')
	data=[x.find('b').text for x in dat]
	inj_player_name=[n.find('h1').text for n in soup.find_all('div',attrs={'class':'p-card'})]
	inj_player_name=str(inj_player_name).strip('[]')
	data.insert(0, inj_player_name)
	# print(data)
	df_yh.loc[idx]=data
	idx_yh+=1
	time.sleep(5)

df_yh.exp_return_date=pd.to_datetime(df.exp_return_date)
df_yh['date_report_ran']=report_run_date
df_yh['name']=df_yh['name'].apply(lambda x: x.replace('\'', '').replace('"', ''))

df_yh['name']=df_yh['name'].astype(str)
df_yh['injury']=df_yh['injury'].astype(str)
df_yh['exp_return_date']=df_yh['exp_return_date'].astype(str)
df_yh['date_report_ran']=df_yh['date_report_ran'].astype(str)



# print(df)

try:
	connection=mysql.connect(host=sports_db_admin_host,
							database=sports_db_admin_db,
							user=sports_db_admin_user,
							password=sports_db_admin_pw,
							port=sports_db_admin_port,
							allow_local_infile=True)
	cursor=connection.cursor()
	
	if connection.is_connected():
		cursor=connection.cursor()
		cursor.execute('TRUNCATE basketball.injured_player_news;')
		cursor.execute('TRUNCATE basketball.injured_player_news_yh;')

	if connection.is_connected():
		file_path='/Users/franciscoavalosjr/Desktop/basketball-folder/tmp_data/my_team_inj_report.csv'
		df.to_csv(file_path,index=False)
		qry=f"LOAD DATA LOCAL INFILE '{file_path}' REPLACE INTO TABLE basketball.injured_player_news FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '\"' IGNORE 1 ROWS;"
		cursor.execute(qry)
		connection.commit()
		del df
		os.remove(file_path)

		file_path='/Users/franciscoavalosjr/Desktop/basketball-folder/tmp_data/my_team_inj_report_yh.csv'
		df_yh.to_csv(file_path,index=False)
		qry=f"LOAD DATA LOCAL INFILE '{file_path}' REPLACE INTO TABLE basketball.injured_player_news_yh FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '\"' IGNORE 1 ROWS;"
		cursor.execute(qry)
		connection.commit()
		del df_yh
		os.remove(file_path)

# basketball.injured_player_news_yh

		# for i,row in df.iterrows():
		# 	sql='REPLACE INTO `injured_player_news` (`'+cols+'`) VALUES ('+'%s,'*(len(row)-1)+'%s)'
		# 	cursor.execute(sql, tuple(row))
		# 	connection.commit()
except Error as e:
	print('Error while connecting to MySQL', e)

finally:
	print('injured_player_news table update, as of - ', report_run_date)
	if(connection.is_connected()):
		cursor.close()
		connection.close()
		print('MySQL connection is closed')












