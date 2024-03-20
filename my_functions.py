import pandas as pd
import requests
from bs4 import BeautifulSoup
import datetime as dt
import time
import os
import numpy as np
import re
# import statsmodels.api as sm
# from statsmodels.graphics.tsaplots import plot_acf, plot_pacf
# import matplotlib.pyplot as plt
# from statsmodels.stats.diagnostic import acorr_ljungbox


'''My functions'''

### Definitions used
def remove_team_string(item):
	output = item.replace('Team(', '')
	output = output.replace(')', '')
	output = output.replace('[', '').replace(']','')
	output.lstrip()
	return output

def remove_matchup_string(item):
	output = item.replace('Matchup(', '')
	output = output.replace(')', '')
	output = output.replace('[', '').replace(']','')
	output.lstrip()
	return output

def remove_activity_string(item):
	output = item.replace('Activity(', '')
	output = output.replace(')', '')
	output = output.replace('[', '').replace(']','')
	output.lstrip()
	return output


def remove_player_string(item):
	output = item.replace('Player(', '')
	output = output.replace(')', '')
	output = output.replace(', points:0', '')
	output = output.replace('[', '').replace(']','')
	output.lstrip()
	return output

def remove_box_string(item):
	output = item.replace('Box Score(', '')
	output = output.replace(')', '')
	output = output.replace('[', '').replace(']','')
	output.lstrip()
	return output

def clean_string(item):
	item=str(item)
	item=remove_team_string(item)
	item=remove_matchup_string(item)
	item=remove_activity_string(item)
	item=remove_player_string(item)
	item=remove_box_string(item)
	return item

def remove_jr(item):
	item=str(item)
	item=item.replace('Jr.','')
	item=item.replace('II','')
	item=item.replace('III','')
	item=item.replace('IV','')
	item=item.replace('Sr.','')
	return item

def remove_name_suffixes(item):
	item=str(item)
	item=item.replace('Jr.','')
	item=item.replace('II','')
	item=item.replace('III','')
	item=item.replace('IV','')
	item=item.replace('Sr.','')
	item=item.replace('Sr.','')
	return item

def convert_game_score_to_points(GS, FG, FGA, FTA, FT, ORB, DRB, STL, AST, BLK, PF, TOV):
	"""
		Obtain a player's points per game by
		inverting John Hollinger's game score measure.
		John Hollinger's Game Score = PTS + 0.4 * FG - 0.7 * FGA - 0.4*(FTA - FT) + 0.7 * ORB + 0.3 * DRB + STL + 0.7 * AST + 0.7 * BLK - 0.4 * PF - TOV. 
	"""
	PTS=GS - 0.4 * FG + 0.7 * FGA + 0.4*(FTA - FT) - 0.7 * ORB - 0.3 * DRB - STL - 0.7 * AST - 0.7 * BLK + 0.4 * PF + TOV
	return PTS







def list_of_pages(dat):
	page_list=[]
	df=dat.find_all('p',class_='bodyCopy')
	for i in df:
		row=i.find_all('a')
		if row:
			x=[y.text.strip() for y in row]
			if x[0]!='Next':
				x.insert(0,'1')
				page_list=x.copy()
	if page_list:
		page_list=[eval(i) for i in page_list]
		page_list=[i*25 for i in page_list]
		page_list.insert(0,0)
	elif not page_list:
		page_list.insert(0,0)

	return page_list

def pagenize_url(my_list, url_input):
	finished_list=[]
	for page in my_list:
		new_url=url_input+f'%22&start={page}'
		finished_list.append(new_url)
	return finished_list

def day_injuries_basketball(day) -> pd.DataFrame():
    original_url=f"https://www.prosportstransactions.com/basketball/Search/SearchResults.php?Player=&Team=&BeginDate={day}&EndDate={day}&ILChkBx=yes&InjuriesChkBx=yes&PersonalChkBx=yes&DisciplinaryChkBx=yes&LegalChkBx=yes&Submit=Search"
    res=requests.get(original_url,timeout=None).content
    data=BeautifulSoup(res,'html.parser')

    pages_iteration=list_of_pages(data)
    url_pagenated_list=pagenize_url(pages_iteration,original_url)
    if len(url_pagenated_list)>1:
    	url_pagenated_list=url_pagenated_list[:-1]
    
    time.sleep(5)
    main_df=pd.DataFrame()
    for url in url_pagenated_list:
    	res=requests.get(url,timeout=None).content
    	data=BeautifulSoup(res,'html.parser')

    	table=data.find('table', class_='datatable center')
    	rows=table.find_all('tr')
    	mylist=[]
    	for row in rows:
    		cols=row.find_all('td')
    		cols=[x.text.strip() for x in cols]
    		mylist.append(cols)
    	df=pd.DataFrame(mylist[1:],columns=['date','team','acquired','relinquished','notes'])
    	clean_r=[x.replace('• ','') for x in df.relinquished]
    	clean_a=[x.replace('• ','') for x in df.acquired]

    	syntax_clean_list_r=[]
    	for name in range(len(clean_r)):
    		c_name=clean_r[name]
    		s=c_name.encode().decode('unicode_escape').encode('raw_unicode_escape')
    		string_uni=s.decode('utf-8')
    		syntax_clean_list_r.append(string_uni)
    	df.relinquished=syntax_clean_list_r

    	syntax_clean_list_a=[]
    	for name in range(len(clean_a)):
    		c_name=clean_a[name]
    		s=c_name.encode().decode('unicode_escape').encode('raw_unicode_escape')
    		string_uni=s.decode('utf-8')
    		syntax_clean_list_a.append(string_uni)
    	df.acquired=syntax_clean_list_a
    	main_df=pd.concat([main_df,df])
    	time.sleep(5)
    return main_df




########### OLD FUNCTION BELOW


# def day_injuries_basketball(start_day, end_day) -> pd.DataFrame():
# def day_injuries_basketball(day) -> pd.DataFrame():
#     url=f"https://www.prosportstransactions.com/basketball/Search/SearchResults.php?Player=&Team=&BeginDate={day}&EndDate={day}&ILChkBx=yes&InjuriesChkBx=yes&PersonalChkBx=yes&DisciplinaryChkBx=yes&LegalChkBx=yes&Submit=Search"
#     res=requests.get(url,timeout=None).content
#     data=BeautifulSoup(res,'html.parser')
#     table=data.find('table', class_='datatable center')
#     rows=table.find_all('tr')
#     mylist=[]
#     for row in rows:
#         cols=row.find_all('td')
#         cols=[x.text.strip() for x in cols]
#         mylist.append(cols)
#     df=pd.DataFrame(mylist[1:],columns=['date','team','acquired','relinquished','notes'])
#     clean_r=[x.replace('• ','') for x in df.relinquished]
#     clean_a=[x.replace('• ','') for x in df.acquired]

#     syntax_clean_list_r=[]
#     for name in range(len(clean_r)):
#         c_name=clean_r[name]
#         s=c_name.encode().decode('unicode_escape').encode('raw_unicode_escape')
#         string_uni=s.decode('utf-8')
#         syntax_clean_list_r.append(string_uni)
#     df.relinquished=syntax_clean_list_r

#     syntax_clean_list_a=[]
#     for name in range(len(clean_a)):
#         c_name=clean_a[name]
#         s=c_name.encode().decode('unicode_escape').encode('raw_unicode_escape')
#         string_uni=s.decode('utf-8')
#         syntax_clean_list_a.append(string_uni)
#     df.acquired=syntax_clean_list_a

#     return df




def create_player_folder(bid:str,file_path:str):
	bid_directory=os.path.join(file_path,bid)
	if not os.path.exists(bid_directory):
		os.makedirs(bid_directory)
	return bid_directory


def create_model_folder(bid:str,file_path:str):
	models_directory=os.path.join(file_path,bid,'models')
	if not os.path.exists(models_directory):
		os.makedirs(models_directory)
	return models_directory


keyword_to_model_type = {
    '_AR': 'AR',
    '_MA': 'MA',
    '_ARMA': 'ARMA',
    '_ARIMA': 'ARIMA',
    '_SGL_EXP': 'SGL_EXP',
    '_DBL_EXP': 'DBL_EXP'
}


def is_statistical_model(file_name:str):
	keywords=['_AR', '_MA','_ARMA','_ARIMA','_SGL_EXP','_DBL_EXP']
	model_bool=False
	model_type=None
	for keyword in keywords:
		if re.search(keyword,file_name):
			model_bool=True
			model_type=keyword_to_model_type.get(keyword)
	return model_bool,model_type



def prepare_predictions_table(
	df:pd.DataFrame,
	league:str,
	bid:str,
	model_type:str,
	p:int,
	d:int,
	q:int,
	alpha:float,
	beta:float,
	ci_lower_bound:float,
	ci_upper_bound:float,**kwargs)->pd.DataFrame:
	df.insert(0,'league',league)
	df.insert(1,'slug',bid)
	df.insert(2,'model_type',model_type)
	df.insert(4,'p',p)
	df.insert(5,'d',d)
	df.insert(6,'q',q)
	df.insert(7,'alpha',alpha)
	df.insert(8,'beta',beta)
	df.insert(10,'confidence_interval_lower_bound',ci_lower_bound)
	df.insert(11,'confidence_interval_upper_bound',ci_upper_bound)
	return df


def date_extract(file_name:str):
	date_pattern=r'\d{4}_\d{2}_\d{2}'
	match=re.search(date_pattern,file_name)
	if match:
		return match.group(0)
	else:
		return None


