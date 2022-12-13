
# ESPN
from espn_api.basketball import League
from espn_api.basketball import Player

# basketball-reference
from basketball_reference_web_scraper import client

# Connection to my DB
import mysql.connector as mysql
from mysql.connector import Error


import pandas as pd
import numpy as np
import os
import matplotlib.pyplot as plt
import datetime as dt
import matplotlib.ticker as mtick
import seaborn as sn
import time

from datetime import datetime
from datetime import date
from datetime import timedelta
from my_functions import convert_game_score_to_points


## Preliminaries, set ups & initiators 
pd.set_option('display.max_columns', None)
pd.set_option('display.max_rows', None)


exec(open('/Users/franciscoavalosjr/Desktop/basketball-creds.py').read())

basketball_seasons=pd.read_csv('/Users/franciscoavalosjr/Downloads/season_dates.csv')



try:
    connection=mysql.connect(host=sports_db_admin_host,
                            database=sports_db_admin_db,
                            user=sports_db_admin_user,
                            password=sports_db_admin_pw,
                            port=sports_db_admin_port)
    if connection.is_connected():
        cursor=connection.cursor()
        cursor.execute('SELECT MAX(date) FROM basketball.historical_player_data;')
        return_date=cursor.fetchall()
        return_date=pd.DataFrame(return_date, columns=['date'])
    if(connection.is_connected()):
        cursor.close()
        connection.close()
        print('MySQL connection is closed for now.')

        basketball_seasons['start']=pd.to_datetime(basketball_seasons['start'])
        basketball_seasons['end']=pd.to_datetime(basketball_seasons['end'])
        basketball_seasons['special_start']=pd.to_datetime(basketball_seasons['special_start'])
        basketball_seasons['special_end']=pd.to_datetime(basketball_seasons['special_end'])

    if return_date is not None:
        max_date=return_date.iloc[0,0].strftime('%Y-%m-%d')
        print(f'not starting from scratch... starting from after {max_date}')
        season_parsed=basketball_seasons[basketball_seasons['start']>max_date]
        # season_parsed=season_parsed[season_parsed['start']<'2019-10-22'] # doing covid season manually

        #use below 2 lines for runinng covid season
        # del basketball_seasons['start'], basketball_seasons['end']
        # basketball_seasons.dropna(how='all', inplace=True)
        # season_parsed=basketball_seasons.copy(deep=True)

        n=2
        # for i in season_parsed.index:
        for i in season_parsed.index:
            start_time=time.perf_counter()
            df=pd.DataFrame()
            season_year_start=int(datetime.strftime(season_parsed.loc[i,:]['start'],'%Y'))
            season_year_end=int(datetime.strftime(season_parsed.loc[i,:]['end'],'%Y'))
            # season_year_start=int(datetime.strftime(season_parsed.loc[i,:]['special_start'],'%Y'))
            # season_year_end=int(datetime.strftime(season_parsed.loc[i,:]['special_end'],'%Y'))
            length=len(str(season_year_start))
            season='20'+str(season_year_start)[length-n:]+'-'+str(season_year_end)[length-n:]
            day_range=pd.date_range(start=season_parsed.loc[i,'start'], end=season_parsed.loc[i,'end'])
            # day_range=pd.date_range(start=season_parsed.loc[i,'special_start'], end=season_parsed.loc[i,'special_end'])
            for day in day_range:
                year=int(day.year)
                month=int(day.month)
                date=int(day.day)
                try:
                    p=client.player_box_scores(day=date,month=month,year=year)
                    p=pd.DataFrame(p)
                    p.insert(0,'date',day.date())
                    p['points']=convert_game_score_to_points(GS=p['game_score'],FG=p['made_field_goals'],FGA=p['attempted_field_goals'],FT=p['made_free_throws'],FTA=p['attempted_free_throws'],ORB=p['offensive_rebounds'],DRB=p['defensive_rebounds'],STL=p['steals'],AST=p['assists'],BLK=p['blocks'],PF=p['personal_fouls'],TOV=p['turnovers'])
                    p['season']=season
                    df=pd.concat([df, p])
                    print('Completed for ', day)
                except:
                    print('Holiday possibly', day)
                time.sleep(5)
            df['slug']=df['slug'].astype(str)
            df['name']=df['name'].astype(str)
            df['team']=df['team'].astype(str)
            df['location']=df['location'].astype(str)
            df['opponent']=df['opponent'].astype(str)
            df['outcome']=df['outcome'].astype(str)
            cols="`,`".join([str(i) for i in df.columns.tolist()])
            end_time=time.perf_counter()
            connection=mysql.connect(host=sports_db_admin_host,
                                    database=sports_db_admin_db,
                                    user=sports_db_admin_user,
                                    password=sports_db_admin_pw,
                                    port=sports_db_admin_port)
            lapsed_time_min=(end_time-start_time)/60
            print(f'Whole {season} took {lapsed_time_min:.02f} minutes to obtain')
            if connection.is_connected():
                cursor=connection.cursor()
                print('Connection to database established... Begin insertion into historical table.')
                start_time=time.perf_counter()
                for i,row in df.iterrows():
                    sql='REPLACE INTO `historical_player_data` (`'+cols+'`) VALUES ('+'%s,'*(len(row)-1)+'%s)'
                    cursor.execute(sql, tuple(row))
                    connection.commit()
                end_time=time.perf_counter()
                lapsed_time_min=(end_time-start_time)/60
                print(f'Insertion to database took {lapsed_time_min:.02f} minutes')
            if(connection.is_connected()):
                cursor.close()
                connection.close()
                print('MySQL connection is closed for now.')
            print(f'Finished inserting for the {season} season')
    else:
        print('hello full backfill')
        n=2
        for i in basketball_seasons.loc[0:18,:].index:
            df=pd.DataFrame()
            season_year_start=int(datetime.strftime(basketball_seasons.loc[i,:]['start'],'%Y'))
            season_year_end=int(datetime.strftime(basketball_seasons.loc[i,:]['end'],'%Y'))
            length=len(str(season_year_start))
            season='20'+str(season_year_start)[length-n:]+'-'+str(season_year_end)[length-n:]
            day_range=pd.date_range(start=basketball_seasons.loc[i,'start'], end=basketball_seasons.loc[i,'end'])
            for day in day_range:
                year=int(day.year)
                month=int(day.month)
                date=int(day.day)
                try:
                    p=client.player_box_scores(day=date, month=month, year=year)
                    p=pd.DataFrame(p)
                    p.insert(0,'date',day.date())
                    p['points']=convert_game_score_to_points(GS=p['game_score'],FG=p['made_field_goals'],FGA=p['attempted_field_goals'],FT=p['made_free_throws'],FTA=p['attempted_free_throws'],ORB=p['offensive_rebounds'],DRB=p['defensive_rebounds'],STL=p['steals'],AST=p['assists'],BLK=p['blocks'],PF=p['personal_fouls'],TOV=p['turnovers'])
                    p['season']=season
                    df=pd.concat([df, p])
                    print('Completed for ', day)
                except:
                    print('Holiday possibly', day)
                time.sleep(5)
            df['slug']=df['slug'].astype(str)
            df['name']=df['name'].astype(str)
            df['team']=df['team'].astype(str)
            df['location']=df['location'].astype(str)
            df['opponent']=df['opponent'].astype(str)
            df['outcome']=df['outcome'].astype(str)
            cols="`,`".join([str(i) for i in df.columns.tolist()])
            connection=mysql.connect(host=sports_db_admin_host,
                                    database=sports_db_admin_db,
                                    user=sports_db_admin_user,
                                    password=sports_db_admin_pw,
                                    port=sports_db_admin_port)
            if connection.is_connected():
                cursor=connection.cursor()
                print('Connection to database established... Begin insertion into historical table.')
                for i,row in df.iterrows():
                    sql='REPLACE INTO `historical_player_data` (`'+cols+'`) VALUES ('+'%s,'*(len(row)-1)+'%s)'
                    cursor.execute(sql, tuple(row))
                    connection.commit()
            if(connection.is_connected()):
                cursor.close()
                connection.close()
                print('MySQL connection is closed for now.')
            print(f'Finished inserting for the {season} season')
except Error as e:
    print('Error while connecting to MySQL', e)
finally:
    if(connection.is_connected()):
        cursor.close()
        connection.close()
        print('MySQL connection is closed')
