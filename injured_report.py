import requests
import pandas as pd
import time
import mysql.connector as mysql

from bs4 import BeautifulSoup
from datetime import datetime
from datetime import timedelta
from mysql.connector import Error


exec(open('/Users/franciscoavalosjr/Desktop/basketball-creds.py').read())

out_players=[
# 'https://www.rotowire.com/basketball/player/dangelo-russell-3708'
# 'https://www.rotowire.com/basketball/player/tyrese-haliburton-5114',
# # 'https://www.rotowire.com/basketball/player/jarrett-allen-4122',
'https://www.rotowire.com/basketball/player/norman-powell-3726',
# 'https://www.rotowire.com/basketball/player/deandre-hunter-4776',
# 'https://www.rotowire.com/basketball/player/tj-mcconnell-3760',
# 'https://www.rotowire.com/basketball/player/jimmy-butler-3231',
'https://www.rotowire.com/basketball/player/gary-trent-4433',
'https://www.rotowire.com/basketball/player/anthony-davis-3297'
# 'https://www.rotowire.com/basketball/player/jrue-holiday-3029'
]


report_run_date=datetime.now()-timedelta(days=0)
report_run_date=report_run_date.strftime('%Y-%m-%d')

df=pd.DataFrame(columns=['name', 'injury', 'exp_return_date'])
idx=0

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

cols="`,`".join([str(i) for i in df.columns.tolist()])


df['name']=df['name'].astype(str)
df['injury']=df['injury'].astype(str)
df['exp_return_date']=df['exp_return_date'].astype(str)
df['date_report_ran']=df['date_report_ran'].astype(str)


# print(df)

try:
	connection=mysql.connect(host=sports_db_admin_host,
							database=sports_db_admin_db,
							user=sports_db_admin_user,
							password=sports_db_admin_pw,
							port=sports_db_admin_port)
	cursor=connection.cursor()
	
	if connection.is_connected():
		cursor=connection.cursor()
		cursor.execute('TRUNCATE basketball.injured_player_news;')

	if connection.is_connected():
		for i,row in df.iterrows():
			sql='REPLACE INTO `injured_player_news` (`'+cols+'`) VALUES ('+'%s,'*(len(row)-1)+'%s)'
			cursor.execute(sql, tuple(row))
			connection.commit()
except Error as e:
	print('Error while connecting to MySQL', e)

finally:
	print('injured_player_news table update, as of - ', report_run_date)
	if(connection.is_connected()):
		cursor.close()
		connection.close()
		print('MySQL connection is closed')












