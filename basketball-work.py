
# ESPN
from espn_api.basketball import League
from espn_api.basketball import Player

# basketball-reference
from basketball_reference_web_scraper import client
from basketball_reference_web_scraper.data import Team

# Connection to my DB
import mysql.connector as mysql
from mysql.connector import Error


import pandas as pd
import os
import unidecode
import time
from datetime import datetime
from datetime import date
from datetime import timedelta
from my_functions import remove_team_string, remove_matchup_string, remove_activity_string, remove_player_string, remove_box_string, clean_string, remove_name_suffixes, convert_game_score_to_points

import my_functions as mf


## Preliminaries, set ups & initiators 
pd.set_option('display.max_columns', None)
pd.set_option('display.max_rows', None)


exec(open('/Users/franciscoavalosjr/Desktop/basketball-creds.py').read())

league=League(league_id=leagueid, 
				year=2023,
				espn_s2=espn_s2,
				swid=swid, 
				debug=False)


### Definitions used
# def remove_team_string(item):
# 	output = item.replace('Team(', '')
# 	output = output.replace(')', '')
# 	output = output.replace('[', '').replace(']','')
# 	output.lstrip()
# 	return output

# def remove_matchup_string(item):
# 	output = item.replace('Matchup(', '')
# 	output = output.replace(')', '')
# 	output = output.replace('[', '').replace(']','')
# 	output.lstrip()
# 	return output

# def remove_activity_string(item):
# 	output = item.replace('Activity(', '')
# 	output = output.replace(')', '')
# 	output = output.replace('[', '').replace(']','')
# 	output.lstrip()
# 	return output


# def remove_player_string(item):
# 	output = item.replace('Player(', '')
# 	output = output.replace(')', '')
# 	output = output.replace(', points:0', '')
# 	output = output.replace('[', '').replace(']','')
# 	output.lstrip()
# 	return output

# def remove_box_string(item):
# 	output = item.replace('Box Score(', '')
# 	output = output.replace(')', '')
# 	output = output.replace('[', '').replace(']','')
# 	output.lstrip()
# 	return output

# def clean_string(item):
# 	item=str(item)
# 	item=remove_team_string(item)
# 	item=remove_matchup_string(item)
# 	item=remove_activity_string(item)
# 	item=remove_player_string(item)
# 	item=remove_box_string(item)
# 	# item.replace('[', '').replace(']','')
# 	return item

# def remove_name_suffixes(item):
# 	item=str(item)
# 	item=item.replace('Jr.','')
# 	item=item.replace('II','')
# 	item=item.replace('III','')
# 	item=item.replace('IV','')
# 	item=item.replace('Sr.','')
# 	item=item.replace('Sr.','')
# 	return item

# def convert_game_score_to_points(GS, FG, FGA, FTA, FT, ORB, DRB, STL, AST, BLK, PF, TOV):
# 	"""
# 		Obtain a player's points per game by
# 		inverting John Hollinger's game score measure.
# 		John Hollinger's Game Score = PTS + 0.4 * FG - 0.7 * FGA - 0.4*(FTA - FT) + 0.7 * ORB + 0.3 * DRB + STL + 0.7 * AST + 0.7 * BLK - 0.4 * PF - TOV. 
# 	"""
# 	PTS=GS - 0.4 * FG + 0.7 * FGA + 0.4*(FTA - FT) - 0.7 * ORB - 0.3 * DRB - STL - 0.7 * AST - 0.7 * BLK + 0.4 * PF + TOV
# 	return PTS


# for team in league.teams:
# 	team=str(team)
# 	team=remove_team_string(team)
# 	print(team)


# print(league.scoreboard())


# for score_results in league.scoreboard(1):
# 	score_results=str(score_results)
# 	score_results=remove_team_string(score_results)
# 	score_results=remove_matchup_string(score_results)
# 	print(score_results)



print(league.recent_activity(size=10))
act=league.recent_activity(size=10)
for activity in act:
	activity=str(activity)
	activity=remove_team_string(activity)
	activity=remove_matchup_string(activity)
	activity=clean_string(activity)
	print(activity)



# print(league.free_agents(size=5))


# for fa in league.free_agents(size=20):
# 	fa=str(fa)
# 	fa=remove_player_string(fa)
# 	print(fa)





# myteam=league.teams[11]
# my_players=clean_string(myteam.roster).split(',')
# # print(type(my_players))
# # print(my_players)
# for p in my_players:
# 	print(p.lstrip())

# for p in myteam.roster:
# 	pid=p.playerId
# 	pos=p.position
# 	proT=p.proTeam
# 	elgSl=p.eligibleSlots
# 	acqTy=p.acquisitionType
# 	p=str(p)
# 	p=remove_player_string(p)
# 	print(p, '-', acqTy)


# box=league.box_scores()
# # print(box)

# for b in box:
# 	b=str(b)
# 	b=remove_team_string(b)
# 	b=remove_box_string(b)
# 	print(b)

# print(box[3])
# print(box[3].home_lineup)

# print(box[3].home_lineup[0].points_breakdown)
# print(box[3].home_lineup[1].points_breakdown)
# print(box[3])

# print(remove_team_string(str(league.teams[17])))
# for player in box[3].home_lineup:
# 	p=clean_string(player)
# 	print(p)
# 	for key, val in player.points_breakdown.items():
# 		print(key, '-', val)
# 	print('\n')





# print(league.scoreboard())



# myteam=league.teams[11]
# print('My Team - ', clean_string(myteam))
# # print(clean_string(myteam.roster))
# for player in myteam.roster:
# 	print(clean_string(player))

# # team='LeBrow Javis'
# team='LeBrow Javis'
# box=league.box_scores()
# col_names=['metric', 'value']



# # list out all matches
# # for match in box:
# # 	print(clean_string(match))
# main_df=pd.DataFrame()
# # list out only my match
# for match in box:
# 	if team in clean_string(match):
# 		position=box.index(match)
# 		# print(position)
# 		# print(clean_string(match))
# 		# print(clean_string(box[position].home_team))
# 		# print(clean_string(box[position].away_team))
# 		# print(clean_string(box[position].home_team))
# 		# print(box[position].home_lineup)
# 		for player in box[position].home_lineup:
# 			# if clean_string(player)=='Anthony Davis':

# 			df=pd.DataFrame(player.points_breakdown.items())
# 			df.columns=col_names
# 			df=df.set_index('metric').T
# 			df.insert(0, 'Name', clean_string(player))
# 			df=df.reset_index(drop=True)
# 			main_df=pd.concat([main_df, df])
# 			# print(clean_string(player))
# 			# player_position=player.slot_position
# 			# player_id=player.playerId
# 			# player_team=player.proTeam
# 			# player_ElgSlots=player.eligibleSlots
# 			# ps=player.projected_avg_points
# 			# print(player_position)
# 			# print(player_id)
# 			# print(player_team)
# 			# print(player_ElgSlots)
# 			# print(ps)


# 			# main_df=main_df.append(df)
# 			# print(df.shape)
# 			# print(type(df))
# 			# print(df.T)
# 			# df.columns=col_names
# 			# main_df.append(df, ignore_index=True)
# 		# print('\n')
# 		# print(clean_string(box[position].away_team))
# 		# # print(box[position].away_lineup)
# 		# for player in box[position].away_lineup:
# 		# 	print(clean_string(player.points_breakdown))
# today=date.today()

# print(main_df)
# # main_df.to_csv(f'/Users/franciscoavalosjr/Desktop/player_data-{today}.csv')




# # print(clean_string(box))
# # print(box[3].home_team)
# # print(box[3].home_score)
# # print(box[3].home_lineup)
# # print(box[3].home_lineup[1].points_breakdown)



# ###################################################
# ###################################################
# ###################################################
# ### Basketball Reference
# ###################################################


p=client.player_box_scores(day=21,month=12,year=2022)
# print(type(p))
df=pd.DataFrame(p)
# df=df[df['name']=='Anthony Davis']
print(df.head())




# p=client.season_schedule(season_end_year=2018)
# p=client.players_season_totals(season_end_year=2023)
# p=client.players_season_totals(season_end_year=2018)
# print(p)








# ###################################################
# ###################################################
# ###################################################
# ### Connecting & Storing to my DB
# ###################################################


# try:
# 	connection=mysql.connect(host=sports_db_admin_host,
# 							database=sports_db_admin_db,
# 							user=sports_db_admin_user,
# 							password=sports_db_admin_pw,
# 							port=3306)
# 	if connection.is_connected():
# 		cursor=connection.cursor()
# 		cursor.execute('show databases;')
# 		output=cursor.fetchall()
# 		output=pd.DataFrame(output)
# 		print(output.T)
# except Error as e:
# 	print("Error while connecting to MySQL", e)


# ################# PUTTING IT ALL TOGETHER 



########### below work used for collecting data on my team alone 
# myteam=league.teams[11]
# my_players=clean_string(myteam.roster).split(',')
# # # for p in my_players:
# # # 	p=p.lstrip()


# day1=18
# day2=23

# # p=client.player_box_scores(day=20,month=10,year=2022)
# # # print(type(p))
# # df=pd.DataFrame(p)
# # df=df[df['name']=='Anthony Davis']
# # print(df.head())

# main_df=pd.DataFrame()
# for d in range(day1, day2, 1):
# 	p=client.player_box_scores(day=d,month=10,year=2022)
# 	df=pd.DataFrame(p)
# 	date=f'2022-10-{d}'
# 	df.insert(0, 'date', date)
# 	for p in my_players:
# 		p=p.lstrip()
# 		# print(df)
# 		insert_df=df[df['name']==p]
# 		# print(p)
# 		# print(insert_df)
# 		main_df=pd.concat([main_df, insert_df])

# print(main_df)

# main_df['slug']=main_df['slug'].astype(str)
# main_df['name']=main_df['name'].astype(str)
# main_df['team']=main_df['team'].astype(str)
# main_df['location']=main_df['location'].astype(str)
# main_df['opponent']=main_df['opponent'].astype(str)
# main_df['outcome']=main_df['outcome'].astype(str)



# cols="`,`".join([str(i) for i in main_df.columns.tolist()])

# try:
# 	connection=mysql.connect(host=sports_db_admin_host,
# 							database=sports_db_admin_db,
# 							user=sports_db_admin_user,
# 							password=sports_db_admin_pw,
# 							port=3306)
# 	if connection.is_connected():
# 		cursor=connection.cursor()
# 		for i,row in main_df.iterrows():
# 			sql='REPLACE INTO `my_team_stats` (`'+cols+'`) VALUES ('+'%s,'*(len(row)-1)+'%s)'
# 			cursor.execute(sql, tuple(row))
# 			connection.commit()
# 		# cursor.execute('show databases;')
# 		# output=cursor.fetchall()
# 		# output=pd.DataFrame(output)
# 		print('done')
# except Error as e:
# 	print("Error while connecting to MySQL", e)


# try:
# 	connection=mysql.connect(host=sports_db_admin_host,
# 							database=sports_db_admin_db,
# 							user=sports_db_admin_user,
# 							password=sports_db_admin_pw,
# 							port=3306)
# 	if connection.is_connected():
# 		cursor=connection.cursor()
# 		cursor.execute('SELECT * FROM basketball.my_team_stats;')
# 		df=cursor.fetchall()
# 		df=pd.DataFrame(df, columns=cursor.column_names)



# except Error as e:
# 	print("Error while connecting to MySQL", e)

########### above work used for collecting data on my team alone 




########### below work used for analyzing FA


# try:
# 	connection=mysql.connect(host=sports_db_admin_host,
# 							database=sports_db_admin_db,
# 							user=sports_db_admin_user,
# 							password=sports_db_admin_pw,
# 							port=3306)
# 	if connection.is_connected():
# 		cursor=connection.cursor()
# 		cursor.execute('SELECT * FROM basketball.master_names_list_temp;')
# 		master_names_list_df=cursor.fetchall()
# 		master_names_list_df=pd.DataFrame(master_names_list_df, columns=cursor.column_names)



# except Error as e:
# 	print("Error while connecting to MySQL", e)


# print(master_names_list_df)
# print(type(master_names_list_df.full_name))

# master_names_list_df['full_name']=master_names_list_df['full_name'].to_string()
# master_names_list_df['first_name']=master_names_list_df['first_name'].to_string()
# master_names_list_df['last_name']=master_names_list_df['last_name'].to_string()

# for i in master_names_list_df.index:
# 	full_name=unidecode.unidecode(master_names_list_df.loc[i, 'full_name'])
# 	first_name=unidecode.unidecode(master_names_list_df.loc[i, 'first_name'])
# 	last_name=unidecode.unidecode(master_names_list_df.loc[i, 'last_name'])
# 	name_code=master_names_list_df.loc[i, 'bbrefid']
# 	print(full_name,'-',name_code)



# print(league.free_agents(size=5))

# for fa in league.free_agents(size=20):
# 	fa=clean_string(fa)
# 	client.player_box_score(day=20,month=10,year=2022)
# 	print(fa)


# ############################ BELOW FINAL USE FOR free_agents.py
# fa_size=2
# FA=league.free_agents(size=fa_size)

# keep_out=['anthoca01', 'whiteha01', 
# 		  'aldrila01', 'walkeke02',
# 		  'couside01', 'howardw01',
# 		  'fallta01', 'bledser01', 
# 		  'rondora01', 'thomptr01']
# main_free_agents_df=pd.DataFrame()
# season_end_year=2023
# FA=clean_string(FA).split(',')
# for fa in FA:
# 	fa=remove_name_suffixes(fa)
# 	fa=fa.lstrip().rstrip()
# 	if fa not in list(master_names_list_df.full_name):
# 		for i in master_names_list_df.index:
# 			full_name=unidecode.unidecode(master_names_list_df.loc[i, 'full_name'])
# 			first_name=unidecode.unidecode(master_names_list_df.loc[i, 'first_name'])
# 			last_name=unidecode.unidecode(master_names_list_df.loc[i, 'last_name'])
# 			name_code=master_names_list_df.loc[i, 'bbrefid']
# 			# if (fa in full_name) & (name_code!='satorto01') & (name_code!='luwawti01'):
# 			if (fa in full_name) & (name_code not in keep_out):
# 				fa_output=client.regular_season_player_box_scores(player_identifier=name_code, 
# 																	season_end_year=season_end_year)
# 				df=pd.DataFrame(fa_output)
# 				df.insert(0, 'name', fa)
# 				if not df.empty:
# 					df['active']=df['active'].astype(bool)
# 					main_free_agents_df=pd.concat([main_free_agents_df, df])
# 				# print("ESPN Name not direct match so had to decode for - ", full_name, '-', name_code)
# 	elif fa in list(master_names_list_df.full_name):
# 		for i in master_names_list_df.index:
# 			full_name=master_names_list_df.loc[i, 'full_name']
# 			name_code=master_names_list_df.loc[i, 'bbrefid']
# 			if (fa in full_name) & (name_code not in keep_out):
# 				fa_output=client.regular_season_player_box_scores(player_identifier=name_code,
# 																	season_end_year=season_end_year)
# 				df=pd.DataFrame(fa_output)
# 				df.insert(0, 'name', fa)
# 				if not df.empty:
# 					df['active']=df['active'].astype(bool)
# 					main_free_agents_df=pd.concat([main_free_agents_df, df])		
# 				# df_copy=df.copy()
# 				# df_copy['active']=df_copy['active'].map({'True':True, 'False':False})
				
# 			# 	# df['name']=fa
# 				# print('second part')
# 			# 	# print('ESPN Name matches master list for - ', fa, '-', name_code)
# 	time.sleep(5)
# print(main_free_agents_df)
# # print(df.dtypes)
# ############################ BELOW FINAL USE FOR free_agents.py




	# 	print('Found ', fa, '-', master_names_list_df.bbrefid)
	# if fa in list(master_names_list_df.full_name):
	# 	print(fa, ' found')
	# first_name=fa.split(' ')[0]
	# last_name=fa.split(' ')[1]
	# if (first_name in list(master_names_list_df.first_name)) & (last_name in list(master_names_list_df.last_name)):
	# 	print('match')
	# else:
	# 	print('no match for ', fa)
		# print('db - ', person for first_name in master_names_list_df.first_name)

# Bogdan Bogdanovic  not found
# Dennis Schroder  not found
# Marcus Morris Sr.  not found
# Goran Dragic  not found
# Chet Holmgren  not found
# T.J. Warren  not found


# print(investigate_fas)

# for player in FA:
# 	print(clean_string(player))
# 	print(player.proTeam)
# 	print(player.injuryStatus)
# 	print(player.injured)
# 	print(player.position)
# 	print(player.acquisitionType)	


# 'FA',
# 'ATL',
# 'BOS',
# 'NOP',
# 'CHI',
# 'CLE',
# 'DAL',
# 'DEN',
# 'DET',
# 'GSW',
# 'HOU',
# 'IND',
# 'LAC',
# 'LAL',
# 'MIA',
# 'MIL',
# 'MIN',
# 'BKN',
# 'NYK',
# 'ORL',
# 'PHL',
# 'PHO',
# 'POR',
# 'SAC',
# 'SAS',
# 'OKC',
# 'UTA',
# 'WAS',
# 'TOR',
# 'MEM',
# 'CHA',


# fa_list=league.free_agents(size=5)
# # for p in league.free_agents(size=20):
# # 	print(clean_string(p))
# # 	print(p.injuryStatus)
# # 	print(p.injured)
# # 	print(p.position)
# # 	print(p.acquisitionType)
# # 	print(p.proTeam)
# # 	print(p.eligibleSlots)
# # df=pd.DataFrame(p.stats)
# non_shows=pd.DataFrame(fa_list, columns=['Name'])
# # non_shows['Name']=clean_string(non_shows['Name'])
# for p in fa_list:
# 	print(mf.clean_string(p))
# # print(non_shows.head())



# df1=client.player_box_scores(day=24,month=10,year=2022)
# df2=client.player_box_scores(day=25,month=10,year=2022)
# df3=client.player_box_scores(day=23,month=10,year=2022)
# df4=client.player_box_scores(day=22,month=10,year=2022)
# df5=client.player_box_scores(day=21,month=10,year=2022)
# df6=client.player_box_scores(day=20,month=10,year=2022)
# df7=client.player_box_scores(day=26,month=10,year=2022)
# df8=client.player_box_scores(day=27,month=10,year=2022)

# df1=pd.DataFrame(df1)
# df2=pd.DataFrame(df2)
# df3=pd.DataFrame(df3)
# df4=pd.DataFrame(df4)
# df5=pd.DataFrame(df5)
# df6=pd.DataFrame(df6)
# df7=pd.DataFrame(df7)
# df8=pd.DataFrame(df8)
# df=pd.concat([df1, df2, df3, df4, df5, df6, df7, df8])
# df=pd.DataFrame(df)
# df=df.iloc[:,:2]
# df=df.groupby(['slug', 'name']).count()
# df=pd.DataFrame(df)
# print(len(df))
# print(df['slug'].unique())
# print(df1.head())

# df=client.regular_season_player_box_scores(
# 		player_identifier='westbru01',
# 		season_end_year=2023)
# df=pd.DataFrame(df)
# print(df.head())


# df=client.playoff_player_box_scores(
#     player_identifier="westbru01", 
#     season_end_year=2018)
# df=pd.DataFrame(df)
# print(df.head())


## high level team stats

# season schedule 
# df=client.season_schedule(season_end_year=2023)
# df=pd.DataFrame(df)
# print('schedule \n',df)
# print('schedule \n',df.shape)


# # team box score
# df=client.team_box_scores(day=9,month=11,year=2022)
# df=pd.DataFrame(df)
# print('team box Score \n',df)


# # standings
# df=client.standings(season_end_year=2023)
# df=pd.DataFrame(df)
# print('standings \n',df)



# season_end_year=2023
# df=pd.DataFrame(client.players_advanced_season_totals(season_end_year=season_end_year))
# df=df[df['name']=='Mo Bamba']
# print(df.head())

# print(help(client))
# df=pd.DataFrame(client.season_schedule(2023))
# print(df['away_team'].unique())
# print(help(client.search))

# [<Team.PHILADELPHIA_76ERS: 'PHILADELPHIA 76ERS'>
#  <Team.LOS_ANGELES_LAKERS: 'LOS ANGELES LAKERS'>
#  <Team.ORLANDO_MAGIC: 'ORLANDO MAGIC'>
#  <Team.WASHINGTON_WIZARDS: 'WASHINGTON WIZARDS'>
#  <Team.HOUSTON_ROCKETS: 'HOUSTON ROCKETS'>
#  <Team.NEW_ORLEANS_PELICANS: 'NEW ORLEANS PELICANS'>
#  <Team.NEW_YORK_KNICKS: 'NEW YORK KNICKS'>
#  <Team.CHICAGO_BULLS: 'CHICAGO BULLS'>
#  <Team.CLEVELAND_CAVALIERS: 'CLEVELAND CAVALIERS'>
#  <Team.OKLAHOMA_CITY_THUNDER: 'OKLAHOMA CITY THUNDER'>
#  <Team.CHARLOTTE_HORNETS: 'CHARLOTTE HORNETS'>
#  <Team.DENVER_NUGGETS: 'DENVER NUGGETS'>
#  <Team.DALLAS_MAVERICKS: 'DALLAS MAVERICKS'>
#  <Team.PORTLAND_TRAIL_BLAZERS: 'PORTLAND TRAIL BLAZERS'>
#  <Team.MILWAUKEE_BUCKS: 'MILWAUKEE BUCKS'>
#  <Team.LOS_ANGELES_CLIPPERS: 'LOS ANGELES CLIPPERS'>
#  <Team.SAN_ANTONIO_SPURS: 'SAN ANTONIO SPURS'>
#  <Team.TORONTO_RAPTORS: 'TORONTO RAPTORS'>
#  <Team.BOSTON_CELTICS: 'BOSTON CELTICS'>
#  <Team.DETROIT_PISTONS: 'DETROIT PISTONS'>
#  <Team.MEMPHIS_GRIZZLIES: 'MEMPHIS GRIZZLIES'>
#  <Team.UTAH_JAZZ: 'UTAH JAZZ'> <Team.PHOENIX_SUNS: 'PHOENIX SUNS'>
#  <Team.MINNESOTA_TIMBERWOLVES: 'MINNESOTA TIMBERWOLVES'>
#  <Team.SACRAMENTO_KINGS: 'SACRAMENTO KINGS'>
#  <Team.INDIANA_PACERS: 'INDIANA PACERS'>
#  <Team.BROOKLYN_NETS: 'BROOKLYN NETS'>
#  <Team.GOLDEN_STATE_WARRIORS: 'GOLDEN STATE WARRIORS'>
#  <Team.ATLANTA_HAWKS: 'ATLANTA HAWKS'> 
#  <Team.MIAMI_HEAT: 'MIAMI HEAT'>]
# season_end_year=2023
# player_id='arizatr01'
# weird_list=[]
# print(weird_list)
# try:
# 	output=client.regular_season_player_box_scores(player_identifier=player_id,
# 										season_end_year=season_end_year)
# except:
# 	print('it failed for', player_id)
# 	weird_list.append(player_id)
# print(weird_list)

# keep_out=['anthoca01', 'whiteha01', 
# 		  'aldrila01', 'walkeke02',
# 		  'couside01', 'howardw01',
# 		  'fallta01', 'bledser01', 
# 		  'rondora01', 'thomptr01', 
# 		  'thomais02', 'lambje01',
# 		  'butleja02', 'willilo02',
# 		  'hoardja01', 'bjeline01', 
# 		  'wilsodj01', 'kanteen01', 
# 		  'millspa01', 'weathqu01', 
# 		  'arizatr01']

# keep_out_df=pd.DataFrame(keep_out, columns=['slug'])
# keep_out_df.to_csv('/Users/franciscoavalosjr/Desktop/basketball-folder/weirds_test.csv', index=False)
# print('exported')




# season_begin='2022-10-18'
# season_begin=datetime.strptime(season_begin, '%Y-%m-%d')
# yesterday=datetime.now()-timedelta(days=1)
# yesterday=yesterday.strftime('%Y-%m-%d')


# main_df=pd.DataFrame()
# day_range=pd.date_range(start=season_begin, end=yesterday)
# for day in day_range:
# 	year=int(datetime.strftime(day.date(), '%Y'))
# 	month=int(datetime.strftime(day.date(), '%m'))
# 	date=int(datetime.strftime(day.date(), '%d'))

# 	p=client.player_box_scores(day=date,month=month,year=year)
# 	df=pd.DataFrame(p)
# 	date=f'{year}-{month}-{date}'
# 	if not df.empty:
# 		df.insert(0, 'date', date)
# 		for p in investigate_fas:
# 			p=remove_name_suffixes(p)
# 			p=p.lstrip().rstrip()
# 			insert_df=df[df['name']==p]
# 			GS=insert_df['game_score']
# 			FG=insert_df['made_field_goals']
# 			FGA=insert_df['attempted_field_goals']
# 			FTA=insert_df['attempted_free_throws']
# 			FT=insert_df['made_free_throws']
# 			ORB=insert_df['offensive_rebounds']
# 			DRB=insert_df['defensive_rebounds']
# 			STL=insert_df['steals']
# 			AST=insert_df['assists']
# 			BLK=insert_df['blocks']
# 			PF=insert_df['personal_fouls']
# 			TOV=insert_df['turnovers']						
# 			points=convert_game_score_to_points(GS=GS, FG=FG, FGA=FGA, FTA=FTA, FT=FT, ORB=ORB, DRB=DRB, STL=STL, AST=AST, BLK=BLK, PF=PF, TOV=TOV)
# 			copy=insert_df.copy()
# 			copy.loc[copy['date']==date, 'points']=points
# 			main_df=pd.concat([main_df, copy])

# main_df['slug']=main_df['slug'].astype(str)
# main_df['name']=main_df['name'].astype(str)
# main_df['team']=main_df['team'].astype(str)
# main_df['location']=main_df['location'].astype(str)
# main_df['opponent']=main_df['opponent'].astype(str)
# main_df['outcome']=main_df['outcome'].astype(str)

# # print(main_df.shape)
# print(main_df)




# try:
# 	connection=mysql.connect(host=sports_db_admin_host,
# 							database=sports_db_admin_db,
# 							user=sports_db_admin_user,
# 							password=sports_db_admin_pw,
# 							port=3306)
# 	if connection.is_connected():
# 		cursor=connection.cursor()
		
# 		cols="`,`".join([str(i) for i in main_df.columns.tolist()])
# 		for i,row in main_df.iterrows():
# 			sql='REPLACE INTO `live_free_agents` (`'+cols+'`) VALUES ('+'%s,'*(len(row)-1)+'%s)'
# 			cursor.execute(sql, tuple(row))
# 			connection.commit()
# 		print('Backfill to basketball.live_free_agents table complete!')


# except Error as e:
# 	print("Error while connecting to MySQL", e)





########### above work used for analyzing FA





# connection=mysql.connect(host=sports_db_admin_host,
#                         database=sports_db_admin_db,
#                         user=sports_db_admin_user,
#                         password=sports_db_admin_pw,
#                         port=3306)

# myteam=league.teams[11]
# my_players=clean_string(myteam.roster).split(',')
# # for p in my_players:
# #     ll=p.lstrip()
# #     ll=remove_name_suffixes(ll)
# #     print(ll)


# # qry=f"""
# #         SELECT MTS.*
# #         FROM basketball.my_team_stats MTS
# #         WHERE name LIKE CONCAT('%', '{ll}','%');
# #         """
# main_df=pd.DataFrame()
# if connection.is_connected():
#     for p in my_players:
#     	cursor=connection.cursor()
#     	p=p.lstrip()
#     	p=remove_name_suffixes(p)
#     	# print(p)
#     	qry=f"""
# 			SELECT
# 				name,
# 			    team,
# 			    TSCHED.*
# 			FROM basketball.my_team_stats MTS
# 			JOIN basketball.high_level_nba_team_schedules TSCHED ON MTS.team = TSCHED.away_team OR MTS.team = TSCHED.home_team
# 			JOIN basketball.calendar CAL ON DATE(SUBDATE(CAST(TSCHED.start_time AS DATETIME), INTERVAL 8 HOUR)) = CAL.day
# 			WHERE MTS.name LIKE CONCAT("%", "{p}","%")
# 				AND CURDATE() BETWEEN CAL.week_starting_monday AND CAL.week_ending_sunday
# 			GROUP BY TSCHED.start_time;"""
#     	cursor.execute(qry)
#     	myteam_df=cursor.fetchall()
#     	myteam_df=pd.DataFrame(myteam_df, columns=cursor.column_names)
#     	main_df=pd.concat([main_df, myteam_df])


# aggregate=main_df.groupby(['name']).start_time.nunique()
# aggregate=aggregate.reset_index()
# aggregate.columns=['name', 'games_this_week']
# aggregate=aggregate.sort_values(['games_this_week', 'name'], ascending=False)
# print(aggregate)
# print(my_players)


# if(connection.is_connected()):
#     cursor.close()
#     connection.close()
#     print('Script finished - MySQL connection is closed')
# else:
#     print('MySQL already closed')


