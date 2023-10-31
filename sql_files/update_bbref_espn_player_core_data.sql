
# Reference this repo as the init for behind the R pull 
# https://github.com/djblechn-su/nba-player-team-ids/tree/master

# 576
SELECT COUNT(*)
FROM basketball.basketball_references_players
LIMIT 100;

# 542
SELECT COUNT(*)
FROM basketball.espn_players
LIMIT 100
;

TRUNCATE basketball.basketball_references_players;
TRUNCATE basketball.espn_players;


LOAD DATA LOCAL INFILE '/Users/franciscoavalosjr/Desktop/basketball_yahoo_player_info/basketball_yahoo_player_info_directory/BBRefIDs.csv'
REPLACE INTO TABLE basketball.basketball_references_players FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '\"' IGNORE 1 ROWS;

LOAD DATA LOCAL INFILE '/Users/franciscoavalosjr/Desktop/basketball_yahoo_player_info/basketball_yahoo_player_info_directory/ESPNIDs.csv'
REPLACE INTO TABLE basketball.espn_players FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '\"' IGNORE 1 ROWS;


SELECT *
FROM basketball.basketball_references_players
LIMIT 100;


SELECT *
FROM basketball.espn_players
LIMIT 100;


SELECT 
	MAX(date) AS most_recent_data_date 
FROM basketball.high_level_nba_team_stats
;


SELECT *
FROM basketball.high_level_nba_team_schedules
ORDER BY start_time DESC 
LIMIT 10000;