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
-- CREATE TABLE basketball.live_free_agents (
--  `name` varchar(100) NOT NULL,
--  `date` date NOT NULL,
--  `team` varchar(100) NOT NULL,
--  `location` varchar(100) NOT NULL,
--  `opponent` varchar(100) NOT NULL,
--  `outcome` varchar(100) NOT NULL,
--  `active` varchar(50) NOT NULL,
--  `seconds_played` int DEFAULT NULL,
--  `made_field_goals` int DEFAULT NULL,
--  `attempted_field_goals` int DEFAULT NULL,
--  `made_three_point_field_goals` int DEFAULT NULL,
--  `attempted_three_point_field_goals` int DEFAULT NULL,
--  `made_free_throws` int DEFAULT NULL,
--  `attempted_free_throws` int DEFAULT NULL,
--  `offensive_rebounds` int DEFAULT NULL,
--  `defensive_rebounds` int DEFAULT NULL,
--  `assists` int DEFAULT NULL,
--  `steals` int DEFAULT NULL,
--  `blocks` int DEFAULT NULL,
--  `turnovers` int DEFAULT NULL,
--  `personal_fouls` int DEFAULT NULL,
--  `points_scored` int DEFAULT NULL,
--  `game_score` decimal(10,2) DEFAULT NULL,
--  `plus_minus` int DEFAULT NULL,
--  `name_code` VARCHAR(75),
--  PRIMARY KEY (`name`,`date`,`team`,`name_code`)
-- ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
-- ;


########################################################################################################################
########################################################################################################################

-- SELECT * FROM basketball.basketball_references_players LIMIT 10;
-- SELECT * FROM basketball.espn_players LIMIT 10;

-- DROP TABLE IF EXISTS basketball.master_names_list_temp;
-- CREATE TABLE basketball.master_names_list_temp
-- (
--   `full_name` varchar(50) DEFAULT NULL,
--   `first_name` varchar(50) DEFAULT NULL,
--   `last_name` varchar(50) DEFAULT NULL COLLATE utf8_unicode_ci,
--   `suffix` varchar(50) DEFAULT NULL,
--   `bbrefid` varchar(50) DEFAULT NULL,
--   `bday` date DEFAULT NULL,
--   `age` INT
-- );
-- REPLACE INTO basketball.master_names_list_temp
-- SELECT 
-- 	X.*,
--     TIMESTAMPDIFF(YEAR, bday, CURDATE()) AS years_old
-- FROM 
-- 	(
-- 		SELECT 
-- 			A.bbrefname AS full_name, 
-- 			SUBSTRING_INDEX(A.bbrefname, ' ',1) AS first_name, 
-- 			CASE
-- 				WHEN LENGTH(A.bbrefname)-LENGTH(REPLACE(A.bbrefname, ' ', ''))+1 > 2 THEN SUBSTRING_INDEX(SUBSTRING_INDEX(A.bbrefname, ' ',-2), ' ', 1)
-- 				ELSE SUBSTRING_INDEX(A.bbrefname, ' ',-1)
-- 			END AS last_name,
-- 			CASE
-- 				WHEN LENGTH(A.bbrefname)-LENGTH(REPLACE(A.bbrefname, ' ', ''))+1 > 2 THEN SUBSTRING_INDEX(SUBSTRING_INDEX(A.bbrefname, ' ',-2), ' ', -1)
-- 				ELSE ''
-- 			END AS suffix,
-- 			A.bbrefid,
-- 			A.bbrefbirthdate AS bday
-- 		FROM basketball.basketball_references_players A
-- 		UNION ALL
-- 		SELECT 
-- 			B.espn_name,
-- 			SUBSTRING_INDEX(B.espn_name, ' ', 1) AS first_name,
-- 			CASE
-- 				WHEN LENGTH(espn_name)-LENGTH(REPLACE(espn_name, ' ', ''))+1 > 2 THEN SUBSTRING_INDEX(SUBSTRING_INDEX(B.espn_name, ' ',-2), ' ', 1)
-- 				ELSE SUBSTRING_INDEX(B.espn_name, ' ',-1)
-- 			END AS last_name,
-- 			CASE
-- 				WHEN LENGTH(espn_name)-LENGTH(REPLACE(espn_name, ' ', ''))+1 > 2 THEN SUBSTRING_INDEX(SUBSTRING_INDEX(B.espn_name, ' ',-2), ' ', -1)
-- 				ELSE ''
-- 			END AS suffix,
-- 			NULL AS bbrefid,
-- 			B.espn_birthdate AS bday
-- 		FROM basketball.espn_players B
--     ) X
-- GROUP BY X.first_name, X.last_name, X.bday;


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


-- DROP TABLE IF EXISTS basketball.injured_player_news;
-- CREATE TABLE basketball.injured_player_news
-- (
--   `name` varchar(100) NOT NULL,
--   `injury` varchar(100) NOT NULL,
--   `exp_return_date` DATE,
--   `news_date` DATE,
--   `date_report_ran` DATE,
--   PRIMARY KEY (`name`, `exp_return_date`)
-- );


########################################################################################################################
########################################################################################################################


-- DROP TABLE IF EXISTS basketball.injured_player_news_yh;
-- CREATE TABLE basketball.injured_player_news_yh
-- (
--   `name` varchar(100) NOT NULL,
--   `injury` varchar(100) NOT NULL,
--   `exp_return_date` DATE,
--   `news_date` DATE,
--   `date_report_ran` DATE,
--   PRIMARY KEY (`name`, `exp_return_date`)
-- );


########################################################################################################################
########################################################################################################################

-- CREATE TABLE basketball.historical_player_data LIKE basketball.my_team_stats;
-- ALTER TABLE basketball.historical_player_data
-- ADD COLUMN season VARCHAR(7) NOT NULL;

-- ALTER TABLE basketball.historical_player_data
-- ADD INDEX(slug);

########################################################################################################################
########################################################################################################################


-- DROP TABLE IF EXISTS basketball.player_injury_cycles;
-- CREATE TABLE basketball.player_injury_cycles
-- (
--   `player_name` VARCHAR(50),
--   `start_health_cycle_team` VARCHAR(50),
--   `end_health_cycle_team` VARCHAR(50),
--   `unhealthy1` date DEFAULT NULL,
--   `first_unhealthy_day_notes` varchar(150) DEFAULT NULL,
--   `unhealthy2` date DEFAULT NULL,
--   `second_unhealthy_day_notes` varchar(150) DEFAULT NULL,
--   `unhealthy3` date DEFAULT NULL,
--   `third_unhealthy_day_notes` varchar(150) DEFAULT NULL,
--   `unhealthy4` date DEFAULT NULL,
--   `fourth_unhealthy_day_notes` varchar(150) DEFAULT NULL,
--   `unhealthy5` date DEFAULT NULL,
--   `fifth_unhealthy_day_notes` varchar(150) DEFAULT NULL,
--   `healthy` date,
--   `healthy_notes` varchar(150) DEFAULT NULL,
--   `days_to_recovery` int DEFAULT NULL,
--   `injury_details_1` VARCHAR(150),
--   `surgery_details_1` VARCHAR(150),
--   `injury_details_2` VARCHAR(150),
--   `surgery_details_2` VARCHAR(150),
--   `injury_details_3` VARCHAR(150),
--   `surgery_details_3` VARCHAR(150),
--   
--   PRIMARY KEY (player_name, healthy),
--   INDEX (start_health_cycle_team, end_health_cycle_team, unhealthy1, unhealthy2, unhealthy3, unhealthy4, unhealthy5)
-- );


########################################################################################################################
########################################################################################################################

-- DROP TABLE IF EXISTS basketball.unhealthy_date_only_DNP_expanded;
-- CREATE TABLE basketball.unhealthy_date_only_DNP_expanded
-- (
-- 	`DAY` date NOT NULL,
-- 	`name` varchar(150),
-- 	`dnp_day1` date DEFAULT NULL,
-- 	`notes1` varchar(300) DEFAULT NULL,
-- 	`dnp_day2` date DEFAULT NULL,
-- 	`notes2` varchar(300) DEFAULT NULL,
-- 	`classification` varchar(13) DEFAULT '',
-- 	`classification2` varchar(13) DEFAULT '',
-- 	PRIMARY KEY (DAY, name)
-- );



########################################################################################################################
########################################################################################################################

-- DROP TABLE IF EXISTS basketball.injury_probabilities;
-- CREATE TABLE IF NOT EXISTS basketball.injury_probabilities
-- (
--   `injury` varchar(509) NOT NULL,
--   `days` int NOT NULL,
--   `probabilities` decimal(6,5) DEFAULT NULL,
--   PRIMARY KEY (`injury`,`days`)
-- );





########################################################################################################################
########################################################################################################################

-- DROP TABLE IF EXISTS basketball.live_free_agents_yahoo;
-- CREATE TABLE basketball.live_free_agents_yahoo
-- (
--  `playerid` varchar(100) NOT NULL,
--  `name` varchar(100) NOT NULL,
--  `status` varchar(100) NOT NULL,
--  `position_type` varchar(100) NOT NULL,
--  `eligible_positions` varchar(100) NOT NULL,
--  `percent_owned` INT,
--  PRIMARY KEY (`playerid`,`name`)
-- );



########################################################################################################################
########################################################################################################################
-- CREATE TABLE basketball.my_team_stats_yahoo LIKE basketball.my_team_stats;


-- DROP TABLE IF EXISTS basketball.my_team_stats_yahoo;
-- CREATE TABLE IF NOT EXISTS basketball.my_team_stats_yahoo
-- (
--   `date` date NOT NULL,
--   `slug` varchar(50) NOT NULL,
--   `name` varchar(100) NOT NULL,
--   `team` varchar(100) NOT NULL,
--   `location` varchar(100) NOT NULL,
--   `opponent` varchar(100) NOT NULL,
--   `outcome` varchar(100) NOT NULL,
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
--   `game_score` decimal(10,2) DEFAULT NULL,
--   `points` int DEFAULT NULL,
--   PRIMARY KEY (`date`,`slug`)
-- );


########################################################################################################################
########################################################################################################################

-- DROP TABLE IF EXISTS basketball.live_yahoo_players;
-- CREATE TABLE IF NOT EXISTS basketball.live_yahoo_players
-- (
--   `name` varchar(100) NOT NULL,
--   PRIMARY KEY (`name`)
-- );


########################################################################################################################
########################################################################################################################

-- DROP TABLE IF EXISTS basketball.live_espn_players;
-- CREATE TABLE IF NOT EXISTS basketball.live_espn_players
-- (
--   `name` varchar(100) NOT NULL,
--   PRIMARY KEY (`name`)
-- );


########################################################################################################################
########################################################################################################################

-- DROP TABLE IF EXISTS basketball.espn_player_positions;
-- CREATE TABLE IF NOT EXISTS basketball.espn_player_positions
-- (
--   `player_name` varchar(100) NOT NULL,
--   `player_roles` varchar(200) NOT NULL,
--   PRIMARY KEY (`player_name`)
-- );


########################################################################################################################
########################################################################################################################

-- DROP TABLE IF EXISTS basketball.predictions;
-- CREATE TABLE basketball.predictions
-- (
--   `league` VARCHAR(50),
--   `slug` VARCHAR(50) NOT NULL,
--   `model_type` VARCHAR(20),
--   `day` INT,
--   `p` INT,
--   `d` INT,
--   `q` INT,
--   `alpha` DECIMAL(4,2),
--   `beta` DECIMAL(4,2),
--   `predictions` DECIMAL(5,3),
--   `confidence_interval_lower_bound` DECIMAL(5,3),
--   `confidence_interval_upper_bound` DECIMAL(5,3),
--   PRIMARY KEY (`league`, `slug`,`model_type`,`day`)
-- );


########################################################################################################################
########################################################################################################################

-- DROP TABLE IF EXISTS basketball.model_evaluation;
-- CREATE TABLE basketball.model_evaluation
-- (
--   `league` VARCHAR(50),
--   `slug` VARCHAR(50) NOT NULL,
--   `model_type` VARCHAR(20),
--   `evaluation_metric` VARCHAR(20),
--   `evaluation_metric_value` DECIMAL(5,3),
--   `champion_model` INT, 
--   PRIMARY KEY (`league`, `slug`,`model_type`,`evaluation_metric`)
-- );






DROP PROCEDURE IF EXISTS basketball.player_app_display;
DELIMITER $$
CREATE PROCEDURE basketball.player_app_display()
BEGIN 
	DROP TEMPORARY TABLE IF EXISTS basketball.temp_player_info;
	CREATE TEMPORARY TABLE basketball.temp_player_info
	SELECT DISTINCT X.*
	FROM
		(
			SELECT 
				LEP.name,
				BRP.BBRefID AS slug,
                'espn' AS league
			FROM basketball.live_espn_players LEP
			JOIN basketball.basketball_references_players BRP ON LEP.name = BRP.BBRefName
			UNION ALL
			SELECT 
				LYP.name,
				BRP.BBRefID AS slug,
                'yahoo' AS league
			FROM basketball.live_yahoo_players LYP
			JOIN basketball.basketball_references_players BRP ON LYP.name = BRP.BBRefName
		) X
	;
	DROP TABLE IF EXISTS basketball.player_historical_web_app_display;
	CREATE TABLE basketball.player_historical_web_app_display
	(
	  `date` date NOT NULL,
	  `slug` varchar(50) NOT NULL,
      `name` varchar(150) NOT NULL,
	  `team` varchar(100) NOT NULL DEFAULT '',
	  `opponent` varchar(100) NOT NULL DEFAULT '',
	  `points` int DEFAULT 0,
	  `league` varchar(5) NOT NULL,
	  PRIMARY KEY (date,slug,league)
	);
	DROP TABLE IF EXISTS basketball.myteam_next_5_games;
	CREATE TABLE basketball.myteam_next_5_games
	(
	  `date` date NOT NULL,
	  `day` double DEFAULT NULL,
	  `slug` varchar(50) NOT NULL,
	  `team` varchar(100) NOT NULL,
	  `opponent` varchar(100) NOT NULL,
	  `location` varchar(100) NOT NULL,
	  `opponent_location` varchar(101) DEFAULT NULL,
	  `points` int DEFAULT NULL
	);
    SET @slug := (SELECT MIN(slug) AS slug FROM basketball.temp_player_info LIMIT 1);
    SET @league := (SELECT league FROM basketball.temp_player_info WHERE slug = @slug LIMIT 1);
    WHILE @slug IS NOT NULL DO
		REPLACE INTO basketball.player_historical_web_app_display
		SELECT 
			HPD.date,
			HPD.slug,
            HPD.name,
			REPLACE(REPLACE(HPD.team,'Team.',''),'_',' ') AS team,
			REPLACE(REPLACE(HPD.opponent,'Team.',''),'_',' ') AS opponent,
			HPD.points,
			@league AS league
		FROM basketball.historical_player_data HPD
		WHERE HPD.slug = @slug
		ORDER BY date DESC;

		REPLACE INTO basketball.myteam_next_5_games
		SELECT
			date,
			@day := @day +1 AS day,
			slug,
			team,
			opponent,
			location,
			CASE
				WHEN SUBSTRING_INDEX(location,'.',-1) = 'HOME' THEN REPLACE(opponent,'Team.','')
				WHEN SUBSTRING_INDEX(location,'.',-1) = 'AWAY' THEN CONCAT('@',REPLACE(opponent,'Team.',''))
			END AS opponent_location,
			points
		FROM basketball.historical_player_data, (SELECT @day := 0) AS init
		WHERE slug = @slug
			AND date > '2024-04-04'
		LIMIT 5;
        
        DELETE FROM basketball.temp_player_info WHERE slug = @slug AND league = @league;
        SET @slug := (SELECT MIN(slug) AS slug FROM basketball.temp_player_info LIMIT 1);
        SET @league := (SELECT league FROM basketball.temp_player_info WHERE slug = @slug LIMIT 1);
	END WHILE;
END 
$$
DELIMITER ;

CALL basketball.player_app_display();



########################################################################################################################
########################################################################################################################

DROP TABLE IF EXISTS basketball.espn_player_positions_final;
CREATE TABLE basketball.espn_player_positions_final
SELECT DISTINCT A.*
FROM 
	( 
		SELECT
			player_name,
			TRIM(BOTH "'" FROM SUBSTRING_INDEX(SUBSTRING_INDEX(REPLACE(REPLACE(TRIM(player_roles), '[', ''), ']', ''), ',', 1), ',', -1)) AS position
		FROM basketball.espn_player_positions
		UNION ALL
		SELECT
			player_name,
			TRIM(BOTH "'" FROM TRIM(TRIM(BOTH "'" FROM SUBSTRING_INDEX(SUBSTRING_INDEX(REPLACE(REPLACE(TRIM(player_roles), '[', ''), ']', ''), ',', 2), ',', -1)))) AS position
		FROM basketball.espn_player_positions
		UNION ALL
		SELECT
			player_name,
			TRIM(BOTH "'" FROM TRIM(TRIM(BOTH "'" FROM SUBSTRING_INDEX(SUBSTRING_INDEX(REPLACE(REPLACE(TRIM(player_roles), '[', ''), ']', ''), ',', 3), ',', -1)))) AS position
		FROM basketball.espn_player_positions
		UNION ALL
		SELECT
			player_name,
			TRIM(BOTH "'" FROM TRIM(TRIM(BOTH "'" FROM SUBSTRING_INDEX(SUBSTRING_INDEX(REPLACE(REPLACE(TRIM(player_roles), '[', ''), ']', ''), ',', 4), ',', -1)))) AS position
		FROM basketball.espn_player_positions
		UNION ALL
		SELECT
			player_name,
			TRIM(BOTH "'" FROM TRIM(TRIM(BOTH "'" FROM SUBSTRING_INDEX(SUBSTRING_INDEX(REPLACE(REPLACE(TRIM(player_roles), '[', ''), ']', ''), ',', 5), ',', -1)))) AS position
		FROM basketball.espn_player_positions
		UNION ALL
		SELECT
			player_name,
			TRIM(BOTH "'" FROM TRIM(TRIM(BOTH "'" FROM SUBSTRING_INDEX(SUBSTRING_INDEX(REPLACE(REPLACE(TRIM(player_roles), '[', ''), ']', ''), ',', 6), ',', -1)))) AS position
		FROM basketball.espn_player_positions
		UNION ALL
		SELECT
			player_name,
			TRIM(BOTH "'" FROM TRIM(TRIM(BOTH "'" FROM SUBSTRING_INDEX(SUBSTRING_INDEX(REPLACE(REPLACE(TRIM(player_roles), '[', ''), ']', ''), ',', 7), ',', -1)))) AS position
		FROM basketball.espn_player_positions
		UNION ALL
		SELECT
			player_name,
			TRIM(BOTH "'" FROM TRIM(TRIM(BOTH "'" FROM SUBSTRING_INDEX(SUBSTRING_INDEX(REPLACE(REPLACE(TRIM(player_roles), '[', ''), ']', ''), ',', 8), ',', -1)))) AS position
		FROM basketball.espn_player_positions
		UNION ALL
		SELECT
			player_name,
			TRIM(BOTH "'" FROM TRIM(TRIM(BOTH "'" FROM SUBSTRING_INDEX(SUBSTRING_INDEX(REPLACE(REPLACE(TRIM(player_roles), '[', ''), ']', ''), ',', 9), ',', -1)))) AS position
		FROM basketball.espn_player_positions
		UNION ALL
		SELECT
			player_name,
			TRIM(BOTH "'" FROM TRIM(TRIM(BOTH "'" FROM SUBSTRING_INDEX(SUBSTRING_INDEX(REPLACE(REPLACE(TRIM(player_roles), '[', ''), ']', ''), ',', 10), ',', -1)))) AS position
		FROM basketball.espn_player_positions
		UNION ALL
		SELECT
			player_name,
			TRIM(BOTH "'" FROM TRIM(TRIM(BOTH "'" FROM SUBSTRING_INDEX(SUBSTRING_INDEX(REPLACE(REPLACE(TRIM(player_roles), '[', ''), ']', ''), ',', 11), ',', -1)))) AS position
		FROM basketball.espn_player_positions
    ) A;


