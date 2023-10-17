import os
# import requests
import pandas as pd
# import numpy as np
# import datetime as dt
import time
# import matplotlib.pyplot as plt
# from scipy.stats import poisson

import mysql.connector as mysql
from my_basketball_funcs import return_parenthesis_contents, contains_number, coalesce
from mysql.connector import Error
from sksurv.nonparametric import kaplan_meier_estimator



pd.set_option('display.max_columns', None)
pd.set_option('display.max_rows', None)
pd.set_option('display.max_colwidth', None)




sports_db_admin_host=os.environ.get('sports_db_admin_host')
sports_db_admin_db='basketball'
sports_db_admin_user=os.environ.get('sports_db_admin_user')
sports_db_admin_pw=os.environ.get('sports_db_admin_pw')
sports_db_admin_port=os.environ.get('sports_db_admin_port')

# this is temporary
connection=mysql.connect(host=sports_db_admin_host,
                    database=sports_db_admin_db,
                    user=sports_db_admin_user,
                    password=sports_db_admin_pw,
                    port=sports_db_admin_port)

if connection.is_connected():
    cursor=connection.cursor()
    qry="""SELECT * FROM basketball.player_injury_cycles;"""
    cursor.execute(qry)
    inj_df=cursor.fetchall()
    inj_df=pd.DataFrame(inj_df,columns=cursor.column_names)

if connection.is_connected():
	cursor.close()
	connection.close()
	print('MySQL connection is closed')



# index clean up
# inj_df=inj_df.loc[inj_df.player_name != '',:]
# inj_df=inj_df.reset_index()
# inj_df=inj_df.drop('index',axis=1)
inj_df = inj_df.loc[inj_df['player_name'] != ''].reset_index(drop=True)



# flag for player_name contains parenthesis pairs
# conditions=[True if (name.find('(')>=0) & (name.find(')')>=0) else False for name in inj_df['player_name']]
# inj_df.insert(1,"has_parenthesis_pair",conditions)
conditions = [(name.find('(') >= 0) and (name.find(')') >= 0) for name in inj_df['player_name']]
inj_df.insert(1, "has_parenthesis_pair", conditions)



# identify incomplete parenthesis
# inc_parenth=[]
# for idx,row in inj_df.iterrows():
#     if ((row['player_name'].find('(')>=0) & (row['player_name'].find(')')==-1) | (row['player_name'].find(')')>=0) & (row['player_name'].find('(')==-1)):
#         assign=True
#         inc_parenth.append(assign)
#     else:
#         inc_parenth.append(False)
# inj_df.insert(2,'incomplete_parenthesis_flag',inc_parenth)
inc_parenth = [(row['player_name'].find('(') >= 0 and row['player_name'].find(')') == -1)
               or (row['player_name'].find(')') >= 0 and row['player_name'].find('(') == -1)
               for _, row in inj_df.iterrows()]

inj_df['incomplete_parenthesis_flag'] = inc_parenth




# get non parenthesis name - accounting for slash instances
# get string that is NOT inside the parenthesis
# non_parenthesis_name=[s.replace(s[s.find('(')+1:s.find(')')],'').replace('(','').replace(')','').strip() if (s.find('(')>=0) & (s.find(')')>=0) else s for s in inj_df['player_name']]
# inj_df.insert(4,'non_parenthesis_name',non_parenthesis_name)

# track_strings_df=pd.DataFrame(columns=['string1_slash','string2_slash'])
# for i in non_parenthesis_name:
#     present_list=[]
#     if i.find('/')>=0:
#         n1=i.split('/')[0].strip()
#         n2=i.split('/')[1].strip()
#         present_list.append(n1)
#         present_list.append(n2)
#         track_strings_df.loc[len(track_strings_df)]=present_list
#     else:
#         present_list.append(i.strip())
#         present_list.append('')
#         track_strings_df.loc[len(track_strings_df)]=present_list

# col1=track_strings_df['string1_slash']
# inj_df.insert(1,'string1_slash_contents',col1)

# col1=track_strings_df['string2_slash']
# inj_df.insert(2,'string2_slash_contents',col1)
non_parenthesis_name = [s.replace(s[s.find('(')+1:s.find(')')], '').replace('(', '').replace(')', '').strip()
                        if (s.find('(') >= 0) and (s.find(')') >= 0) else s for s in inj_df['player_name']]
inj_df['non_parenthesis_name'] = non_parenthesis_name

track_strings = []

for i in non_parenthesis_name:
    present_list = []
    if '/' in i:
        split_names = list(map(str.strip, i.split('/')))
        if len(split_names)==2:
            n1,n2 = split_names
            present_list.extend([n1, n2])
        else:
            present_list.extend(split_names[:2])
    else:
        present_list.append(i.strip())
        present_list.append('')
    track_strings.append(present_list)
    # present_list = []
    # if '/' in i:
    #     n1, n2 = map(str.strip, i.split('/'))
    #     present_list.extend([n1, n2])
    # else:
    #     present_list.append(i.strip())
    #     present_list.append('')
    # track_strings.append(present_list)

track_strings_df = pd.DataFrame(track_strings, columns=['string1_slash', 'string2_slash'])
inj_df[['string1_slash_contents', 'string2_slash_contents']] = track_strings_df[['string1_slash', 'string2_slash']]





# delete error data
# # these data can't be used
delete_player_names=['activated from 10-day DL',
                     'transferred to 60-day IL with right biceps tendini',
                    'transferred to 60-day IL with strained left lower ',
                     'back injury (DTD)']
inj_df=inj_df[~inj_df['player_name'].isin(delete_player_names)]
inj_df=inj_df.reset_index(drop=True)



# obtain contents inside all parenthesis and flag which are DOB
# track_df=pd.DataFrame(columns=['parenthesis_string_1_is_birthday','parenthesis_string_2_is_birthday'])
# track_contents_df=pd.DataFrame(columns=['parenthesis_string1','parenthesis_string2'])

# for i in inj_df.player_name:
#     output=return_parenthesis_contents(i)
#     designation_list=[True if contains_number(x) else False for x in output]
#     present_list=[]
#     if len(designation_list)==2:
#         track_df.loc[len(track_df)]=designation_list
#         track_contents_df.loc[len(track_contents_df)]=output
#     elif (len(designation_list)==1) and (designation_list[0]==False):
#         designation_list.append('')
#         output.append('')
#         track_df.loc[len(track_df)]=designation_list
#         track_contents_df.loc[len(track_contents_df)]=output
#     elif (len(designation_list)==1) and (designation_list[0]==True):
#         designation_list.insert(0,'')
#         output.insert(0,'')
#         track_df.loc[len(track_df)]=designation_list
#         track_contents_df.loc[len(track_contents_df)]=output
#     elif len(designation_list)==0:
#         designation_list.append('')
#         designation_list.append('')
#         track_df.loc[len(track_df)]=designation_list
#         output.append('')
#         output.append('')
#         track_contents_df.loc[len(track_contents_df)]=output

# parenthesis_info_df=pd.concat([track_contents_df,track_df],axis=1)

# col1=parenthesis_info_df['parenthesis_string1']
# inj_df.insert(5,'parenthesis_string1',col1)

# col1=parenthesis_info_df['parenthesis_string2']
# inj_df.insert(6,'parenthesis_string2',col1)

# col1=parenthesis_info_df['parenthesis_string_1_is_birthday']
# inj_df.insert(7,'parenthesis_string_1_is_birthday',col1)

# col1=parenthesis_info_df['parenthesis_string_2_is_birthday']
# inj_df.insert(8,'parenthesis_string_2_is_birthday',col1)

track_df = pd.DataFrame(columns=['parenthesis_string_1_is_birthday', 'parenthesis_string_2_is_birthday'])
track_contents_df = pd.DataFrame(columns=['parenthesis_string1', 'parenthesis_string2'])

for i in inj_df.player_name:
    output = return_parenthesis_contents(i)
    designation_list = [True if contains_number(x) else False for x in output]
    present_list = []

    if len(designation_list) == 2:
        track_df.loc[len(track_df)] = designation_list
        track_contents_df.loc[len(track_contents_df)] = output
    elif len(designation_list) == 1:
        if designation_list[0] == False:
            designation_list.append('')
            output.append('')
        else:
            designation_list.insert(0, '')
            output.insert(0, '')
        track_df.loc[len(track_df)] = designation_list
        track_contents_df.loc[len(track_contents_df)] = output
    else:
        designation_list.extend(['', ''])
        output.extend(['', ''])
        track_df.loc[len(track_df)] = designation_list
        track_contents_df.loc[len(track_contents_df)] = output

parenthesis_info_df = pd.concat([track_contents_df, track_df], axis=1)

inj_df.insert(5, 'parenthesis_string1', parenthesis_info_df['parenthesis_string1'])
inj_df.insert(6, 'parenthesis_string2', parenthesis_info_df['parenthesis_string2'])
inj_df.insert(7, 'parenthesis_string_1_is_birthday', parenthesis_info_df['parenthesis_string_1_is_birthday'])
inj_df.insert(8, 'parenthesis_string_2_is_birthday', parenthesis_info_df['parenthesis_string_2_is_birthday'])






# reorder columns
column_order=[
    'player_name', 
    'string1_slash_contents', 
    'string2_slash_contents',
    
    'has_parenthesis_pair', 
    'parenthesis_string1', 
    'parenthesis_string2',
    'parenthesis_string_1_is_birthday', 
    'parenthesis_string_2_is_birthday',
    'incomplete_parenthesis_flag',
    
    'start_health_cycle_team', 
    'end_health_cycle_team', 
    'unhealthy1', 
    'first_unhealthy_day_notes',
    'unhealthy2', 
    'second_unhealthy_day_notes', 
    'unhealthy3',
    'third_unhealthy_day_notes', 
    'unhealthy4', 
    'fourth_unhealthy_day_notes',
    'unhealthy5', 
    'fifth_unhealthy_day_notes', 
    'healthy', 
    'healthy_notes',
    'days_to_recovery', 
    'injury_details_1', 
    # 'tommy_john_injury_flag_1',
    # 'suspension_details_1', 
    # 'paternity_leave_1', 
    # 'paternity_flag_1',
    # 'bereavement_leave_1', 
    # 'bereavement_flag_1', 
    # 'restricted_details_1',
    'surgery_details_1', 
    # 'personal_details_1', 
    'injury_details_2',
    # 'tommy_john_injury_flag_2', 
    # 'suspension_details_2', 
    # 'paternity_leave_2',
    # 'paternity_flag_2', 
    # 'bereavement_leave_2', 
    # 'bereavement_flag_2',
    # 'restricted_details_2', 
    'surgery_details_2', 
    # 'personal_details_2',
    'injury_details_3', 
    # 'tommy_john_injury_flag_3', 
    # 'suspension_details_3',
    # 'paternity_leave_3', 
    # 'paternity_flag_3', 
    # 'bereavement_leave_3',
    # 'bereavement_flag_3', 
    # 'restricted_details_3', 
    'surgery_details_3'
    # 'personal_details_3'
    ]
inj_df=inj_df[column_order]





## begin injury probabilities



inj_type_list=[]
days_to_recovery_list=[]


columns = ['fourth_unhealthy_day_notes', 'third_unhealthy_day_notes', 'second_unhealthy_day_notes', 'first_unhealthy_day_notes']
for _, row in inj_df.iterrows():
    output=coalesce(*(row[col] for col in columns))
    days=row['days_to_recovery']
    inj_type_list.append(output)
    days_to_recovery_list.append(days)

# for idx,row in inj_df.iterrows():
#     output=coalesce(row['fourth_unhealthy_day_notes'],row['third_unhealthy_day_notes'],row['second_unhealthy_day_notes'],row['first_unhealthy_day_notes'])
#     days=row['days_to_recovery']
#     inj_type_list.append(output)
#     days_to_recovery_list.append(days)


# set minimum sample size for each injury type
min_sample_size=50

df=pd.DataFrame({'inj_type_list':inj_type_list,'days_to_recovery_list':days_to_recovery_list})
df1=df.groupby(['inj_type_list']).describe().reset_index()
df1.columns = df1.columns.droplevel(0)
df1.columns=['injury_type', 'count', 'mean', 'std', 'min', '25%', '50%', '75%', 'max']
df1_values=df1.loc[df1['count']>=min_sample_size,:]['injury_type'].values



# Cut data to injuries with the minimum sample size desired
df=df.loc[df['inj_type_list'].isin(df1_values),:]
df['days_to_recovery_list']=df['days_to_recovery_list'].astype(int)







prob_dict={}
main_df=pd.DataFrame(columns=['injury','days','probabilities'])
for i in df['inj_type_list'].unique():
    temp_dict={}
    days=df.loc[df['inj_type_list']==i,'days_to_recovery_list'].copy()
    s=[True]*len(days)
    day_values,survival_prob=kaplan_meier_estimator(s,days)
    temp_dict['days']=day_values
    temp_dict['probabilities']=survival_prob
    temp_dict['injury']=[i]*len(day_values)
    temp_df=pd.DataFrame.from_dict(temp_dict)
    main_df=pd.concat([main_df,temp_df])

del temp_dict,temp_df,days,s,day_values,survival_prob



# print(main_df.shape)
# print(main_df.head())


connection=mysql.connect(host=sports_db_admin_host,
              database=sports_db_admin_db,
              user=sports_db_admin_user,
              password=sports_db_admin_pw,
              port=sports_db_admin_port,
              allow_local_infile=True)

cursor=connection.cursor()

file_path='/Users/franciscoavalosjr/Desktop/basketball-folder/tmp_data/injury_probabilities.csv'

main_df.to_csv(file_path, index=False)

qry=f"LOAD DATA LOCAL INFILE '{file_path}' REPLACE INTO TABLE basketball.injury_probabilities FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '\"' IGNORE 1 ROWS;"


cursor.execute(qry)
connection.commit() 
del main_df
os.remove(file_path)


if connection.is_connected():
       cursor.close()
       connection.close()
       print('Closed MySQL connection')











