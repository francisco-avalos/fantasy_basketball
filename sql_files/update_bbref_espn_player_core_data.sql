
# Reference this repo as the init for behind the R pull 
# https://github.com/djblechn-su/nba-player-team-ids/tree/master

# 627
SELECT COUNT(*)
FROM basketball.basketball_references_players
LIMIT 100;

# 627
SELECT COUNT(*)
FROM basketball.espn_players
LIMIT 100
;

TRUNCATE basketball.basketball_references_players;
TRUNCATE basketball.espn_players;


-- LOAD DATA LOCAL INFILE '/Users/franciscoavalosjr/Desktop/basketball_yahoo_player_info/basketball_yahoo_player_info_directory/BBRefIDs.csv'
-- LOAD DATA LOCAL INFILE '/Users/franciscoavalosjr/Downloads/nba-player-team-ids-master/BBRefIDs.csv'
LOAD DATA LOCAL INFILE '/Users/franciscoavalosjr/Desktop/basketball-folder/data/BBRefIDs.csv'
REPLACE INTO TABLE basketball.basketball_references_players FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '\"' IGNORE 1 ROWS;

-- LOAD DATA LOCAL INFILE '/Users/franciscoavalosjr/Desktop/basketball_yahoo_player_info/basketball_yahoo_player_info_directory/ESPNIDs.csv'
-- LOAD DATA LOCAL INFILE '/Users/franciscoavalosjr/Downloads/nba-player-team-ids-master/ESPNIDs.csv'
LOAD DATA LOCAL INFILE '/Users/franciscoavalosjr/Desktop/basketball-folder/data/ESPNIDs.csv'
REPLACE INTO TABLE basketball.espn_players FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '\"' IGNORE 1 ROWS;


SELECT *
FROM basketball.basketball_references_players
WHERE bbrefname LIKE '%Tatum%'
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

SELECT *
FROM basketball.high_level_nba_team_stats
ORDER BY date DESC
LIMIT 10;

SELECT MAX(date) AS most_recent_data_date FROM basketball.high_level_nba_team_stats;
SELECT * FROM basketball.high_level_nba_team_stats ORDER BY date DESC LIMIT 100;
SELECT MAX(date) FROM basketball.historical_player_data;

SELECT 
	season, 
	SUBSTRING_INDEX(GROUP_CONCAT(date ORDER BY date ASC SEPARATOR '; '), ';', 1) AS backfill_since_current_season_begins,
	SUBSTRING_INDEX(GROUP_CONCAT(date ORDER BY date DESC SEPARATOR '; '), ';', 1) AS backfill_since_current_season_latest_data_entry
FROM basketball.historical_player_data
GROUP BY season
ORDER BY date DESC
LIMIT 1;

SELECT *
FROM basketball.hist_player_inj
LIMIT 100;


SELECT * FROM basketball.player_injury_cycles
ORDER BY unhealthy1 DESC
LIMIT 100
