-- DROP TABLE IF EXISTS basketball.calendar;
-- CREATE TABLE basketball.calendar
-- (
--   `day` date NOT NULL,
--   PRIMARY KEY (day)
-- );

-- DROP PROCEDURE IF EXISTS basketball.calendar_proc;
-- DELIMITER $$
-- CREATE PROCEDURE basketball.calendar_proc()
-- BEGIN 
-- 	SET @start_date='2021-01-01';
--     SET @end_date='2050-12-31';
--     WHILE @start_date <= @end_date DO
-- 		REPLACE INTO basketball.calendar
--         SELECT @start_date;
--         SET @start_date:=(ADDDATE(@start_date, INTERVAL 1 DAY));
-- 	END WHILE;
-- END 
-- $$
-- DELIMITER ;

-- CALL basketball.calendar_proc();

-- DROP TEMPORARY TABLE IF EXISTS basketball.calendar_temp;
-- CREATE TEMPORARY TABLE basketball.calendar_temp
-- SELECT 
-- 	CAL.*, 
--     IF(DATE_FORMAT(day, '%w')=1, CAL.day, NULL) AS week_starting_monday,
--     IF(DATE_FORMAT(day, '%w')=0, CAL.day, NULL) AS week_ending_sunday
-- FROM basketball.calendar CAL;

-- ALTER TABLE basketball.calendar
-- ADD COLUMN week_starting_monday DATE,
-- ADD COLUMN week_ending_sunday DATE;

-- UPDATE basketball.calendar A
-- JOIN basketball.calendar_temp B ON A.day BETWEEN B.week_starting_monday AND ADDDATE(B.week_starting_monday, INTERVAL 6 DAY)
-- SET A.week_starting_monday = B.week_starting_monday;

-- UPDATE basketball.calendar A
-- JOIN basketball.calendar_temp B ON A.day BETWEEN SUBDATE(B.week_ending_sunday, INTERVAL 6 DAY) AND B.week_ending_sunday
-- SET A.week_ending_sunday = B.week_ending_sunday;

-- DROP TEMPORARY TABLE basketball.calendar_temp;

-- ALTER TABLE basketball.calendar
-- ADD INDEX(week_starting_monday, week_ending_sunday);

-- ALTER TABLE basketball.calendar
-- ADD COLUMN month DATE;

-- UPDATE basketball.calendar A
-- SET A.month=DATE_FORMAT(A.day, '%Y-%m-01');

########################################################################################################################
########################################################################################################################

-- DROP TABLE IF EXISTS basketball.my_team_stats;
-- CREATE TABLE basketball.my_team_stats
-- (
-- 	date DATE NOT NULL,
-- 	slug VARCHAR(50) NOT NULL,
-- 	name VARCHAR(100) NOT NULL,
-- 	team VARCHAR(100) NOT NULL,
-- 	location VARCHAR(100) NOT NULL,
-- 	opponent VARCHAR(100) NOT NULL,
-- 	outcome VARCHAR(100) NOT NULL,
-- 	seconds_played INT,
-- 	made_field_goals INT,
-- 	attempted_field_goals INT,
-- 	made_three_point_field_goals INT,
-- 	attempted_three_point_field_goals INT,
-- 	made_free_throws INT,
-- 	attempted_free_throws INT,
-- 	offensive_rebounds INT,
-- 	defensive_rebounds INT,
-- 	assists INT,
-- 	steals INT,
-- 	blocks INT,
-- 	turnovers INT,
-- 	personal_fouls INT,
-- 	game_score DECIMAL(10,2),
--     points INT DEFAULT NULL,
--     PRIMARY KEY(date, slug)
-- );

########################################################################################################################
########################################################################################################################

-- DROP TABLE IF EXISTS basketball.basketball_references_players;
-- CREATE TABLE basketball.basketball_references_players
-- (
-- 	BBRefName VARCHAR(50),
--     BBRefLink VARCHAR(1000),
--     BBRefID VARCHAR(50),
--     BBRefBirthDate DATE,
--     PRIMARY KEY (BBRefID)
-- );

########################################################################################################################
########################################################################################################################


-- DROP TABLE IF EXISTS basketball.espn_players;
-- CREATE TABLE basketball.espn_players
-- (
-- 	espn_link VARCHAR(1000),
--     espn_name VARCHAR(50),
--     espn_birthdate DATE,
--     PRIMARY KEY (espn_name, espn_birthdate)
-- );


########################################################################################################################
########################################################################################################################

-- DROP TABLE IF EXISTS basketball.live_free_agents;
-- CREATE TABLE basketball.live_free_agents
-- (
--   `name` varchar(100) NOT NULL,
--   `date` date NOT NULL,
--   `team` varchar(100) NOT NULL,
--   `location` varchar(100) NOT NULL,
--   `opponent` varchar(100) NOT NULL,
--   `outcome` varchar(100) NOT NULL, 
--   `active` varchar(50) NOT NULL,
--   `seconds_played` int DEFAULT NULL,
--   `made_field_goals` int DEFAULT NULL,
--   `attempted_field_goals` int DEFAULT NULL,
--   `made_three_point_field_goals` int DEFAULT NULL,
--   `attempted_three_point_field_goals` int DEFAULT NULL,
--   `made_free_throws` int DEFAULT NULL,
--   `attempted_free_throws` int DEFAULT NULL,
--   `offensive_rebounds` int DEFAULT NULL,
--   `defensive_rebounds` int DEFAULT NULL,
--   `assists` int DEFAULT NULL,
--   `steals` int DEFAULT NULL,
--   `blocks` int DEFAULT NULL,
--   `turnovers` int DEFAULT NULL,
--   `personal_fouls` int DEFAULT NULL,
--   `points_scored` int DEFAULT NULL,
--   `game_score` decimal(10,2) DEFAULT NULL,
--   `plus_minus` int signed DEFAULT NULL,
--   PRIMARY KEY (`name`, `date`)
-- );


########################################################################################################################
########################################################################################################################

-- SELECT * FROM basketball.basketball_references_players LIMIT 10;
-- SELECT * FROM basketball.espn_players LIMIT 10;

DROP TABLE IF EXISTS basketball.master_names_list_temp;
CREATE TABLE basketball.master_names_list_temp
(
  `full_name` varchar(50) DEFAULT NULL,
  `first_name` varchar(50) DEFAULT NULL,
  `last_name` varchar(50) DEFAULT NULL COLLATE utf8_unicode_ci,
  `suffix` varchar(50) DEFAULT NULL,
  `bbrefid` varchar(50) DEFAULT NULL,
  `bday` date DEFAULT NULL,
  `age` INT
);
REPLACE INTO basketball.master_names_list_temp
SELECT 
	X.*,
    TIMESTAMPDIFF(YEAR, bday, CURDATE()) AS years_old
FROM 
	(
		SELECT 
			A.bbrefname AS full_name, 
			SUBSTRING_INDEX(A.bbrefname, ' ',1) AS first_name, 
			CASE
				WHEN LENGTH(A.bbrefname)-LENGTH(REPLACE(A.bbrefname, ' ', ''))+1 > 2 THEN SUBSTRING_INDEX(SUBSTRING_INDEX(A.bbrefname, ' ',-2), ' ', 1)
				ELSE SUBSTRING_INDEX(A.bbrefname, ' ',-1)
			END AS last_name,
			CASE
				WHEN LENGTH(A.bbrefname)-LENGTH(REPLACE(A.bbrefname, ' ', ''))+1 > 2 THEN SUBSTRING_INDEX(SUBSTRING_INDEX(A.bbrefname, ' ',-2), ' ', -1)
				ELSE ''
			END AS suffix,
			A.bbrefid,
			A.bbrefbirthdate AS bday
		FROM basketball.basketball_references_players A
		UNION ALL
		SELECT 
			B.espn_name,
			SUBSTRING_INDEX(B.espn_name, ' ', 1) AS first_name,
			CASE
				WHEN LENGTH(espn_name)-LENGTH(REPLACE(espn_name, ' ', ''))+1 > 2 THEN SUBSTRING_INDEX(SUBSTRING_INDEX(B.espn_name, ' ',-2), ' ', 1)
				ELSE SUBSTRING_INDEX(B.espn_name, ' ',-1)
			END AS last_name,
			CASE
				WHEN LENGTH(espn_name)-LENGTH(REPLACE(espn_name, ' ', ''))+1 > 2 THEN SUBSTRING_INDEX(SUBSTRING_INDEX(B.espn_name, ' ',-2), ' ', -1)
				ELSE ''
			END AS suffix,
			NULL AS bbrefid,
			B.espn_birthdate AS bday
		FROM basketball.espn_players B
    ) X
GROUP BY X.first_name, X.last_name, X.bday;


########################################################################################################################
########################################################################################################################


-- DROP TABLE IF EXISTS basketball.advanced_stats;
-- CREATE TABLE basketball.advanced_stats
-- (
--   `slug` VARCHAR(50) NOT NULL,
--   `name` varchar(100) NOT NULL,
--   `positions` varchar(100) NOT NULL,
--   `age` INT NOT NULL,
--   `team` varchar(100) NOT NULL,
--   `games_played` INT,
--   `minutes_played` INT,
--   `player_efficiency_rating` DECIMAL(5,3),
--   `true_shooting_percentage` DECIMAL(5,3),
--   `three_point_attempt_rate` DECIMAL(5,3),
--   `free_throw_attempt_rate` DECIMAL(5,3),
--   `offensive_rebound_percentage` DECIMAL(5,3),
--   `defensive_rebound_percentage` DECIMAL(5,3),
--   `total_rebound_percentage` DECIMAL(5,3),
--   `assist_percentage` DECIMAL(5,3),
--   `steal_percentage` DECIMAL(5,3),
--   `block_percentage` DECIMAL(5,3),
--   `turnover_percentage` DECIMAL(5,3),
--   `usage_percentage` DECIMAL(5,3),
--   `offensive_win_shares` DECIMAL(5,3),
--   `defensive_win_shares` DECIMAL(5,3),
--   `win_shares` DECIMAL(5,3),
--   `win_shares_per_48_minutes` DECIMAL(5,3),
--   `offensive_box_plus_minus` DECIMAL(5,3) SIGNED,
--   `defensive_box_plus_minus` DECIMAL(5,3) SIGNED,
--   `box_plus_minus` DECIMAL(5,3) SIGNED,
--   `value_over_replacement_player` DECIMAL(5,3) SIGNED,
--   `is_combined_totals` VARCHAR(10),
--   PRIMARY KEY (`slug`, `name`)
-- );


########################################################################################################################
########################################################################################################################

-- DROP TABLE IF EXISTS basketball.high_level_nba_team_stats;
-- CREATE TABLE basketball.high_level_nba_team_stats
-- (
--   `team` varchar(100) NOT NULL,
--   `outcome` VARCHAR(100) NOT NULL,
--   `minutes_played` INT,
--   `made_field_goals` int DEFAULT NULL,
--   `attempted_field_goals` int DEFAULT NULL,
--   `made_three_point_field_goals` int DEFAULT NULL,
--   `attempted_three_point_field_goals` int DEFAULT NULL,
--   `made_free_throws` int DEFAULT NULL,
--   `attempted_free_throws` int DEFAULT NULL,
--   `offensive_rebounds` int DEFAULT NULL,
--   `defensive_rebounds` int DEFAULT NULL,
--   `assists` int DEFAULT NULL,
--   `steals` int DEFAULT NULL,
--   `blocks` int DEFAULT NULL,
--   `turnovers` int DEFAULT NULL,
--   `personal_fouls` int DEFAULT NULL,
--   `points` int DEFAULT NULL,
--   `date` DATE,
--   PRIMARY KEY (`team`, `date`)
-- );


########################################################################################################################
########################################################################################################################


-- DROP TABLE IF EXISTS basketball.high_level_nba_team_schedules;
-- CREATE TABLE basketball.high_level_nba_team_schedules
-- (
--   `start_time` varchar(100) NOT NULL,
--   `away_team` varchar(100) NOT NULL,
--   `home_team` varchar(100) NOT NULL,
--   `away_team_score` int DEFAULT NULL,
--   `home_team_score` int DEFAULT NULL,
--   PRIMARY KEY (`start_time`, `away_team`, `home_team`)
-- );


########################################################################################################################
########################################################################################################################


select *
from basketball.my_team_stats
;



SELECT *
FROM basketball.master_names_list_temp
;

SELECT *
FROM basketball.calendar
LIMIT 10;



SELECT *
FROM basketball.live_free_agents
WHERE name='Aaron Holiday'
ORDER BY date DESC;







select * from basketball.espn_players;
select * from basketball.basketball_references_players;






SELECT *
FROM basketball.advanced_stats
WHERE name = 'Tyus Jones'
LIMIT 100
;

SELECT *
FROM basketball.live_free_agents
WHERE name = 'Tyus Jones'
;


SHOW TABLE STATUS FROM basketball WHERE name LIKE '%live_free_agents%';


SELECT *
FROM basketball.live_free_agents
-- WHERE name LIKE '%fox%'
ORDER BY date DESC;

SELECT MAX(date) AS most_recent_data_date FROM basketball.live_free_agents;


SELECT * 
FROM basketball.master_names_list_temp
LIMIT 10000;



SELECT *, REPLACE(team, 'Team.', '') AS clean_team, REPLACE(outcome, 'Outcome.', '') AS clean_outcome
FROM basketball.high_level_nba_team_stats
ORDER BY date DESC
;


SELECT MAX(date) AS most_recent_data_date FROM basketball.high_level_nba_team_stats;

SELECT 
	*, 
    SUBDATE(CAST(start_time AS DATETIME), INTERVAL 8 HOUR) AS PST_time,
    DATE(SUBDATE(CAST(start_time AS DATETIME), INTERVAL 8 HOUR)) AS PST_date
FROM basketball.high_level_nba_team_schedules
WHERE DATE(SUBDATE(CAST(start_time AS DATETIME), INTERVAL 8 HOUR)) = SUBDATE(CURDATE(), INTERVAL 1 DAY)
-- where away_team_score is not null
;

SELECT * FROM basketball.high_level_nba_team_stats WHERE date = '2022-11-15' LIMIT 100;

select *
from basketball.high_level_nba_team_stats TSTATS
join basketball.high_level_nba_team_schedules TSCHED ON TSTATS.team = TSCHED.home_team
	AND TSTATS.date = DATE(SUBDATE(CAST(TSCHED.start_time AS DATETIME), INTERVAL 8 HOUR))
WHERE DATE(SUBDATE(CAST(TSCHED.start_time AS DATETIME), INTERVAL 8 HOUR)) = SUBDATE(CURDATE(), INTERVAL 2 DAY)
limit 100;




SHOW TABLE STATUS FROM basketball WHERE name LIKE "live_free_agents";
use basketball;

select *
FROM live_free_agents
ORDER BY date DESC
LIMIT 10;

SELECT *
FROM basketball.high_level_nba_team_stats
ORDER BY date DESC
LIMIT 100;

-- 420
SELECT COUNT(*)
FROM basketball.high_level_nba_team_stats
LIMIT 100;




SELECT *
FROM basketball.advanced_stats
-- WHERE slug='hoardja01'
-- WHERE name LIKE '%james%'
LIMIT 1000;


select *
from basketball.my_team_stats
;


SELECT 
	ADS.slug,
	ADS.name, 
	SUBSTRING_INDEX(REPLACE(REPLACE(ADS.positions, '[<Position.', ''), '>]', ''), ':', 1) AS position,
	ADS.age, 
	REPLACE(ADS.team, 'Team.', '') AS team,
	ADS.games_played,
	ADS.minutes_played,
	ADS.player_efficiency_rating,
	ADS.true_shooting_percentage,
	ADS.three_point_attempt_rate,
	ADS.free_throw_attempt_rate,
	ADS.offensive_rebound_percentage,
	ADS.defensive_rebound_percentage,
	ADS.total_rebound_percentage,
	ADS.assist_percentage,
	ADS.steal_percentage,
	ADS.block_percentage,
	ADS.turnover_percentage,
	ADS.usage_percentage,
	ADS.offensive_win_shares,
	ADS.defensive_win_shares,
	ADS.win_shares,
	ADS.win_shares_per_48_minutes,
	ADS.offensive_box_plus_minus,
	ADS.defensive_box_plus_minus,
	ADS.box_plus_minus,
	ADS.value_over_replacement_player,
	ADS.is_combined_totals
FROM basketball.advanced_stats ADS
JOIN basketball.live_free_agents LGA ON LGA.name = ADS.name
GROUP BY ADS.name
;



SELECT *
FROM basketball.my_team_stats
WHERE name LIKE '%jevon carter%'
LIMIT 100;


SELECT *
FROM basketball.live_free_agents
WHERE name LIKE '%jevon carter%'
LIMIT 100;


SELECT *
FROM basketball.advanced_stats
WHERE name LIKE '%anthony davis%'
	OR name LIKE '%jevon carter%'
LIMIT 100;


SELECT DISTINCT name
FROM basketball.advanced_stats;




SELECT 
	DISTINCT MTS.name
FROM basketball.my_team_stats MTS 
JOIN basketball.calendar C ON MTS.date=C.day
WHERE C.day >= SUBDATE(CURDATE(), INTERVAL 4 DAY);




