'''My Functions'''
import pandas as pd
import numpy as np
# import re
import datetime as dt
import requests
from bs4 import BeautifulSoup



def clean_df(df) -> pd.DataFrame():
    df['player_name']=df['player_name'].astype(str)
    df['player_name']=df['player_name'].replace(np.nan, '', regex=True)
    df['pitch_type']=df['pitch_type'].astype(str)
    df['pitch_type']=df['pitch_type'].replace(np.nan, '', regex=True)
    df['events']=df['events'].astype(str)
    df['events']=df['events'].replace(np.nan, '', regex=True)
    df['events']=df['events'].replace('nan', '', regex=True)
    df['bb_type']=df['bb_type'].astype(str)
    df['bb_type']=df['bb_type'].replace(np.nan, '', regex=True)
    df['bb_type']=df['bb_type'].replace('nan', '', regex=True)
    df['sv_id']=df['sv_id'].astype(str)
    df['sv_id']=df['sv_id'].replace(np.nan, '', regex=True)
    df['sv_id']=df['sv_id'].replace('<NA>', '', regex=True)
    df['sv_id']=df['sv_id'].replace('nan', '', regex=True)

    df['pitch_name']=df['pitch_name'].astype(str)
    df['pitch_name']=df['pitch_name'].replace(np.nan, '', regex=True)
    df['pitch_name']=df['pitch_name'].replace('nan', '', regex=True)
    df['if_fielding_alignment']=df['if_fielding_alignment'].astype(str)
    df['if_fielding_alignment']=df['if_fielding_alignment'].replace('<NA>', '', regex=True)
    df['if_fielding_alignment']=df['if_fielding_alignment'].replace('nan', '', regex=True)
    df['of_fielding_alignment']=df['of_fielding_alignment'].astype(str)
    df['of_fielding_alignment']=df['of_fielding_alignment'].replace('<NA>', '', regex=True)
    df['of_fielding_alignment']=df['of_fielding_alignment'].replace('nan', '', regex=True)
    df['description']=df['description'].astype(str)
    df['description']=df['description'].replace(np.nan, '', regex=True)
    df['description']=df['description'].replace('nan', '', regex=True)
    df['game_date']=pd.to_datetime(df['game_date'])
    df['game_date']=df['game_date'].astype(str)

    df['release_speed']=df['release_speed'].astype(float)
    df['release_speed']=df['release_speed'].replace(np.nan, 0)
    df['release_pos_x']=df['release_pos_x'].astype(float)
    df['release_pos_x']=df['release_pos_x'].replace(np.nan, 0)
    df['release_pos_z']=df['release_pos_z'].astype(float)
    df['release_pos_z']=df['release_pos_z'].replace(np.nan, 0)
    df['hit_location']=df['hit_location'].astype(float)
    df['hit_location']=df['hit_location'].replace(np.nan, 0)
    df['pfx_x']=df['pfx_x'].astype(float)
    df['pfx_x']=df['pfx_x'].replace(np.nan, 0)
    df['pfx_z']=df['pfx_z'].astype(float)
    df['pfx_z']=df['pfx_z'].replace(np.nan, 0)
    df['plate_x']=df['plate_x'].astype(float)
    df['plate_x']=df['plate_x'].replace(np.nan, 0)
    df['plate_z']=df['plate_z'].astype(float)
    df['plate_z']=df['plate_z'].replace(np.nan, 0)
    df['on_3b']=df['on_3b'].astype(float)
    df['on_3b']=df['on_3b'].replace(np.nan, 0)
    df['on_2b']=df['on_2b'].astype(float)
    df['on_2b']=df['on_2b'].replace(np.nan, 0)
    df['on_1b']=df['on_1b'].astype(float)
    df['on_1b']=df['on_1b'].replace(np.nan, 0)
    df['hc_x']=df['hc_x'].astype(float)
    df['hc_x']=df['hc_x'].replace(np.nan, 0)
    df['hc_y']=df['hc_y'].astype(float)
    df['hc_y']=df['hc_y'].replace(np.nan, 0)
    df['vx0']=df['vx0'].astype(float)
    df['vx0']=df['vx0'].replace(np.nan, 0)
    df['vy0']=df['vy0'].astype(float)
    df['vy0']=df['vy0'].replace(np.nan, 0)
    df['vz0']=df['vz0'].astype(float)
    df['vz0']=df['vz0'].replace(np.nan, 0)
    df['ax']=df['ax'].astype(float)
    df['ax']=df['ax'].replace(np.nan, 0)
    df['ay']=df['ay'].astype(float)
    df['ay']=df['ay'].replace(np.nan, 0)
    df['az']=df['az'].astype(float)
    df['az']=df['az'].replace(np.nan, 0)
    df['sz_top']=df['sz_top'].astype(float)
    df['sz_top']=df['sz_top'].replace(np.nan, 0)
    df['sz_bot']=df['sz_bot'].astype(float)
    df['sz_bot']=df['sz_bot'].replace(np.nan, 0)
    df['hit_distance_sc']=df['hit_distance_sc'].astype(float)
    df['hit_distance_sc']=df['hit_distance_sc'].replace(np.nan, 0)
    df['launch_speed']=df['launch_speed'].astype(float)
    df['launch_speed']=df['launch_speed'].replace(np.nan, 0)
    df['launch_angle']=df['launch_angle'].astype(float)
    df['launch_angle']=df['launch_angle'].replace(np.nan, 0)
    df['effective_speed']=df['effective_speed'].astype(float)
    df['effective_speed']=df['effective_speed'].replace(np.nan, 0)
    df['release_spin_rate']=df['release_spin_rate'].astype(float)
    df['release_spin_rate']=df['release_spin_rate'].replace(np.nan, 0)
    df['release_extension']=df['release_extension'].astype(float)
    df['release_extension']=df['release_extension'].replace(np.nan, 0)
    df['release_pos_y']=df['release_pos_y'].astype(float)
    df['release_pos_y']=df['release_pos_y'].replace(np.nan, 0)
    df['estimated_ba_using_speedangle']=df['estimated_ba_using_speedangle'].astype(float)
    df['estimated_ba_using_speedangle']=df['estimated_ba_using_speedangle'].replace(np.nan, 0)
    df['estimated_woba_using_speedangle']=df['estimated_woba_using_speedangle'].astype(float)
    df['estimated_woba_using_speedangle']=df['estimated_woba_using_speedangle'].replace(np.nan, 0)
    df['woba_value']=df['woba_value'].astype(float)
    df['woba_value']=df['woba_value'].replace(np.nan, 0)
    df['woba_denom']=df['woba_denom'].astype(float)
    df['woba_denom']=df['woba_denom'].replace(np.nan, 0)
    df['babip_value']=df['babip_value'].astype(float)
    df['babip_value']=df['babip_value'].replace(np.nan, 0)
    df['iso_value']=df['iso_value'].astype(float)
    df['iso_value']=df['iso_value'].replace(np.nan, 0)
    df['launch_speed_angle']=df['launch_speed_angle'].astype(float)
    df['launch_speed_angle']=df['launch_speed_angle'].replace(np.nan, 0)
    df['spin_axis']=df['spin_axis'].astype(float)
    df['spin_axis']=df['spin_axis'].replace(np.nan, 0)
    df['delta_run_exp']=df['delta_run_exp'].astype(float)
    df['delta_run_exp']=df['delta_run_exp'].replace(np.nan, 0)
    df['zone']=df['zone'].astype(float)
    df['zone']=df['zone'].replace(np.nan, 0)

    return df


def remove_double_header_string(text, dic):
    for i,j in dic.items():
        text=text.replace(i,j)
    return text





### start here 

'''
ARI 1998 - 2021
ATL 1990 - 2021
BAL 1990 - 2021
BOS 1990 - 2021
CAL 1990 - 1996 / ANA 1997 - 2004 / LAA 2005 - 2021
CHA 1990 - 1999 / CHW 1990 - 2021 - OK TO JUST USE CHA
CHC 1990 - 2021
CIN 1990 - 2021
CLE 1990 - 2021
COL 1993 - 2021
DET 1990 - 2021
FLA 1993 - 2011 / MIA 2012 - 2021
HOU 1990 - 2021
KCR 1990 - 2021
LAD 1990 - 2021
MIL 1990 - 2021
MIN 1990 - 2021
NYM 1990 - 2021
NYY 1990 - 2021
OAK 1990 - 2021
PHI 1990 - 2021
PIT 1990 - 2021
SDP 1990 - 2021
SEA 1990 - 2021
SFG 1990 - 2021
STL 1990 - 2021
TBD 1998 - 2007 / TBR 2008 - 2021
TEX 1990 - 2021
TOR 1990 - 2021
MON 1990 - 2004 / WSN 2005 - 2021

'''


cd=dt.datetime.now()
year=int(cd.strftime('%Y'))
mybday_year=1990
full_years_list=list(range(mybday_year, year+1))

reg_full_years_list=list(range(mybday_year, year+1))
team_names=['ATL', 'BAL', 'BOS', 'CHA', 'CHC', 
            'CIN', 'CLE', 'DET', 'HOU', 'KCR', 
            'LAD', 'MIL', 'MIN', 'NYM', 'NYY', 
            'OAK', 'PHI', 'PIT', 'SDP', 'SEA', 
            'SFG', 'STL', 'TEX', 'TOR']
size=len(reg_full_years_list)
unchanged_tm_initial_names=team_names * size
full_years_list=reg_full_years_list * len(team_names)
full_years_list.sort()

df1=pd.DataFrame({'year':full_years_list, 'team':unchanged_tm_initial_names})

main_franken=pd.DataFrame()



p1_years=filter(lambda y: 1998<=y, reg_full_years_list)
p1_years=list(p1_years)
p1_name=['ARI'] * len(p1_years)
name_list=p1_name
y_list=p1_years
df_test=pd.DataFrame({'year':y_list, 'team':name_list})

main_franken=pd.concat([main_franken, df_test])


p1_years=filter(lambda y: 1993<=y, reg_full_years_list)
p1_years=list(p1_years)
p1_name=['COL'] * len(p1_years)
name_list=p1_name
y_list=p1_years
df_test=pd.DataFrame({'year':y_list, 'team':name_list})

main_franken=pd.concat([main_franken, df_test])


p1_years=filter(lambda y: 1990<=y<=1996, reg_full_years_list)
p1_years=list(p1_years)
p2_years=filter(lambda y: 1997<=y<=2004, reg_full_years_list)
p2_years=list(p2_years)
p3_years=filter(lambda y: 2005<=y, reg_full_years_list)
p3_years=list(p3_years)
p1_name=['CAL'] * len(p1_years)
p2_name=['ANA'] * len(p2_years)
p3_name=['LAA'] * len(p3_years)
name_list=p1_name+p2_name+p3_name
y_list=p1_years+p2_years+p3_years
df_test=pd.DataFrame({'year':y_list, 'team':name_list})

main_franken=pd.concat([main_franken,df_test])


p1_years=filter(lambda y: 1990<=y<=2011, reg_full_years_list)
p1_years=list(p1_years)
p2_years=filter(lambda y: 2012<=y, reg_full_years_list)
p2_years=list(p2_years)
p1_name=['FLA'] * len(p1_years)
p2_name=['MIA'] * len(p2_years)
name_list=p1_name+p2_name
y_list=p1_years+p2_years
df_test=pd.DataFrame({'year':y_list, 'team':name_list})

main_franken=pd.concat([main_franken,df_test])


p1_years=filter(lambda y: 1998<=y<=2007, reg_full_years_list)
p1_years=list(p1_years)
p2_years=filter(lambda y: 2008<=y, reg_full_years_list)
p2_years=list(p2_years)
p1_name=['TBD'] * len(p1_years)
p2_name=['TBR'] * len(p2_years)
name_list=p1_name+p2_name
y_list=p1_years+p2_years
df_test=pd.DataFrame({'year':y_list, 'team':name_list})

main_franken=pd.concat([main_franken,df_test])


p1_years=filter(lambda y: 1990<=y<=2004, reg_full_years_list)
p1_years=list(p1_years)
p2_years=filter(lambda y: 2005<=y, reg_full_years_list)
p2_years=list(p2_years)
p1_name=['MON'] * len(p1_years)
p2_name=['WSN'] * len(p2_years)
name_list=p1_name+p2_name
y_list=p1_years+p2_years
df_test=pd.DataFrame({'year':y_list, 'team':name_list})

main_franken=pd.concat([main_franken,df_test])


df1=pd.concat([df1, main_franken])
df1=df1.sort_values(['year', 'team'])
df1=df1.reset_index(drop=True)
### end here 

def get_mlb_team_name_designations():
    return df1







def return_parenthesis_contents(string):
    stack = 0
    startIndex = None
    results = []

    for i, c in enumerate(string):
        if c == '(':
            if stack == 0:
                startIndex = i + 1 # string to extract starts one index later
            # push to stack
            stack += 1
        elif c == ')':
            # pop stack
            stack -= 1
            if stack == 0:
                results.append(string[startIndex:i])
    return results

def contains_number(x):
    return any(char.isdigit() for char in x)

def coalesce(*values):
    """Return the first non-None value or None if all values are None"""
    return next((v for v in values if v is not None), None)