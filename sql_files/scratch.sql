

DROP TABLE IF EXISTS basketball.player_injury_cycles;
CREATE TABLE basketball.player_injury_cycles
(
  `player_name` VARCHAR(50),
  `start_health_cycle_team` VARCHAR(50),
  `end_health_cycle_team` VARCHAR(50),
  `unhealthy1` date DEFAULT NULL,
  `first_unhealthy_day_notes` varchar(150) DEFAULT NULL,
  `unhealthy2` date DEFAULT NULL,
  `second_unhealthy_day_notes` varchar(150) DEFAULT NULL,
  `unhealthy3` date DEFAULT NULL,
  `third_unhealthy_day_notes` varchar(150) DEFAULT NULL,
  `unhealthy4` date DEFAULT NULL,
  `fourth_unhealthy_day_notes` varchar(150) DEFAULT NULL,
  `unhealthy5` date DEFAULT NULL,
  `fifth_unhealthy_day_notes` varchar(150) DEFAULT NULL,
  `healthy` date,
  `healthy_notes` varchar(150) DEFAULT NULL,
  `days_to_recovery` int DEFAULT NULL,
  
  `injury_details_1` VARCHAR(150),
--   `tommy_john_injury_flag_1` INT(1),
  `suspension_details_1` VARCHAR(150),
--   `paternity_leave_1` VARCHAR(100),
--   `paternity_flag_1` INT(1),
--   `bereavement_leave_1` VARCHAR(100),
--   `bereavement_flag_1` INT(1),
--   `restricted_details_1` VARCHAR(100),
  `surgery_details_1` VARCHAR(150),
--   `personal_details_1` VARCHAR(150),

  `injury_details_2` VARCHAR(150),
--   `tommy_john_injury_flag_2` INT(1),
  `suspension_details_2` VARCHAR(150),
--   `paternity_leave_2` VARCHAR(100),
--   `paternity_flag_2` INT(1),
--   `bereavement_leave_2` VARCHAR(100),
--   `bereavement_flag_2` INT(1),
--   `restricted_details_2` VARCHAR(100),
  `surgery_details_2` VARCHAR(150),
--   `personal_details_2` VARCHAR(150),

  `injury_details_3` VARCHAR(150),
--   `tommy_john_injury_flag_3` INT(1),
  `suspension_details_3` VARCHAR(150),
--   `paternity_leave_3` VARCHAR(100),
--   `paternity_flag_3` INT(1),
--   `bereavement_leave_3` VARCHAR(100),
--   `bereavement_flag_3` INT(1),
--   `restricted_details_3` VARCHAR(100),
  `surgery_details_3` VARCHAR(150),
--   `personal_details_3` VARCHAR(150),
  
  PRIMARY KEY (player_name, healthy),
  INDEX (start_health_cycle_team, end_health_cycle_team, unhealthy1, unhealthy2, unhealthy3, unhealthy4, unhealthy5)
);

-- TRUNCATE basketball.player_inj_cycles_prefinal;
-- SELECT COUNT(*) FROM basketball.player_inj_cycles_prefinal; # 22,884
-- SELECT * FROM basketball.player_inj_cycles_prefinal LIMIT 10; # 22,884
-- 140,663


DROP PROCEDURE IF EXISTS basketball.health_cycle_backfill_proc;
DELIMITER $$

CREATE PROCEDURE basketball.health_cycle_backfill_proc()
BEGIN

	DROP TABLE IF EXISTS basketball.player_inj_cycles_prefinal;
	CREATE TABLE basketball.player_inj_cycles_prefinal
	(
	  `player_name` VARCHAR(50),
	  `start_health_cycle_team` VARCHAR(50),
	  `end_health_cycle_team` VARCHAR(50),
	  `unhealthy1` date DEFAULT NULL,
	  `first_unhealthy_day_notes` varchar(150) DEFAULT NULL,
	  `unhealthy2` date DEFAULT NULL,
	  `second_unhealthy_day_notes` varchar(150) DEFAULT NULL,
	  `unhealthy3` date DEFAULT NULL,
	  `third_unhealthy_day_notes` varchar(150) DEFAULT NULL,
	  `unhealthy4` date DEFAULT NULL,
	  `fourth_unhealthy_day_notes` varchar(150) DEFAULT NULL,
	  `unhealthy5` date DEFAULT NULL,
	  `fifth_unhealthy_day_notes` varchar(150) DEFAULT NULL,
	  `healthy` date,
	  `healthy_notes` varchar(150) DEFAULT NULL,
	  `days_to_recovery` int DEFAULT NULL,
	  PRIMARY KEY (player_name, healthy),
	  INDEX (start_health_cycle_team, end_health_cycle_team, unhealthy1, unhealthy2, unhealthy3, unhealthy4, unhealthy5)
	);

	DROP TEMPORARY TABLE IF EXISTS basketball.players_cycler;
    CREATE TEMPORARY TABLE basketball.players_cycler
    (	
    	p_name VARCHAR(150), 
   		PRIMARY KEY (p_name)
   	);
    REPLACE INTO basketball.players_cycler
	SELECT DISTINCT p_name
	FROM 
		(
			SELECT 
				acquired AS p_name
			FROM basketball.hist_player_inj
			WHERE acquired!=''
				AND acquired = 'Dwight Howard'
			GROUP BY p_name
			UNION ALL
			SELECT 
				relinquished AS p_name
			FROM basketball.hist_player_inj
			WHERE relinquished!=''
				AND relinquished = 'Dwight Howard'
			GROUP BY p_name
		) X
	WHERE p_name NOT IN (' and to complete 5 days of a work program run by the sheriff''s office"',
						'11/25/2019',
                        '76ers',
                        'left knee injury (DTD)',
                        'left wrist injury (DTD)',
                        'NBA health and safety protocols (DTD)',
                        'placed on IL with bruised right hip',
                        'placed on IL with left knee injury',
                        'placed on IL with right Achilles tendon injury',
                        'placed on IL with sprained right thumb',
                        'placed on IL with surgery on right knee',
                        'placed on IL with torn labrum in right hip',
                        'strained left quadriceps (DTD)',
                        'v')
	ORDER BY p_name;
    SET @name = (SELECT MIN(p_name) FROM basketball.players_cycler);
--     SET @name := 'Aaron Boone';
	
    ########### DNP ANALYSIS START
	DROP TABLE IF EXISTS basketball.unhealthy_date_only_DNP_expanded;
	CREATE TABLE basketball.unhealthy_date_only_DNP_expanded
	(
		`DAY` date NOT NULL,
		`name` varchar(150),
		`dnp_day1` date DEFAULT NULL,
		`notes1` varchar(300) DEFAULT NULL,
		`dnp_day2` date DEFAULT NULL,
		`notes2` varchar(300) DEFAULT NULL,
		`classification` varchar(13) DEFAULT '',
		`classification2` varchar(13) DEFAULT '',
		PRIMARY KEY (DAY, name)
	);
    
    WHILE @name IS NOT NULL DO
		DROP TEMPORARY TABLE IF EXISTS basketball.unhealthy_date_only_DNP;
		CREATE TEMPORARY TABLE basketball.unhealthy_date_only_DNP
		(`DAY` date, PRIMARY KEY (DAY));
        
        REPLACE INTO basketball.unhealthy_date_only_DNP
		SELECT DISTINCT DAY
		FROM basketball.hist_player_inj
		WHERE relinquished IN (@name)
			AND TRIM(BOTH '"' FROM notes) NOT LIKE 'fined %'
			AND TRIM(BOTH '"' FROM notes) NOT LIKE '% fined %'
			AND TRIM(BOTH '"' FROM notes) NOT LIKE '%suspen%'
            AND (TRIM(BOTH '"' FROM notes) LIKE '%DNP%' OR TRIM(BOTH '"' FROM notes) = 'DNP')
            AND day NOT BETWEEN LAST_DAY(DATE_FORMAT(day, '%Y-04-%d')) AND LAST_DAY(DATE_FORMAT(day, '%Y-09-%d')) # in season only
        ;
        DROP TEMPORARY TABLE IF EXISTS basketball.unhealthy_date_only_DNP_COPY;
        CREATE TEMPORARY TABLE basketball.unhealthy_date_only_DNP_COPY LIKE basketball.unhealthy_date_only_DNP;
        REPLACE INTO basketball.unhealthy_date_only_DNP_COPY SELECT * FROM basketball.unhealthy_date_only_DNP;
        
        SET @dnp_day1 := (SELECT MIN(day) FROM basketball.unhealthy_date_only_DNP);
        SET @dnp_day2 := (SELECT MIN(day) FROM basketball.unhealthy_date_only_DNP WHERE day NOT IN (@dnp_day1));
        SET @prev_group := NULL;
        SET @group_num := 0;
		
        WHILE @dnp_day1 IS NOT NULL AND @dnp_day2 IS NOT NULL DO
			SET @prev_case := (SELECT SUBSTRING_INDEX(GROUP_CONCAT(notes1 ORDER BY day DESC SEPARATOR ';'), ';', 1) AS prev_notes FROM basketball.unhealthy_date_only_DNP_expanded WHERE name = @name);
            SET @prev_case_day := (SELECT SUBSTRING_INDEX(GROUP_CONCAT(day ORDER BY day DESC SEPARATOR ';'), ';', 1) AS prev_notes FROM basketball.unhealthy_date_only_DNP_expanded WHERE name = @name);
			
            REPLACE INTO basketball.unhealthy_date_only_DNP_expanded
			SELECT 
				AA.*, 
                DNP.*
            FROM basketball.unhealthy_date_only_DNP AA
            JOIN 
				(
					SELECT 
						A.relinquished AS name,
						A.day AS dnp_day1,
                        TRIM(BOTH '"' FROM A.notes) AS notes1,
						B.day AS dnp_day2,
                        TRIM(BOTH '"' FROM B.notes) AS notes2,
						CASE
							WHEN B.day BETWEEN A.day AND ADDDATE(A.day, INTERVAL 5 DAY) AND TRIM(BOTH '"' FROM A.notes) = TRIM(BOTH '"' FROM B.notes) THEN 'bucket'
							ELSE 'do not bucket'
						END AS classification,
						CASE
                            WHEN @prev_group IS NULL THEN CONCAT('group - ', @group_num := @group_num)
                            WHEN A.day BETWEEN @prev_case_day AND ADDDATE(@prev_case_day, INTERVAL 5 DAY)
								AND @prev_case = TRIM(BOTH '"' FROM A.notes) THEN CONCAT('group - ', @group_num := @group_num)
							ELSE CONCAT('group - ', @group_num := @group_num+1)
						END AS classification2
					FROM basketball.hist_player_inj A
					LEFT JOIN basketball.hist_player_inj B ON A.relinquished = B.relinquished
						AND B.day = @dnp_day2
					WHERE A.relinquished = @name
						AND A.day = @dnp_day1
                ) DNP ON AA.day = DNP.dnp_day1
			;
            DELETE FROM basketball.unhealthy_date_only_DNP_COPY WHERE day = @dnp_day1;
			SET @dnp_day1 := (SELECT MIN(day) FROM basketball.unhealthy_date_only_DNP_COPY);
			SET @dnp_day2 := (SELECT MIN(day) FROM basketball.unhealthy_date_only_DNP_COPY WHERE day NOT IN (@dnp_day1));
            SET @prev_group := @group_num;
		END WHILE;
        DROP TABLES IF EXISTS basketball.unhealthy_date_only_DNP_COPY, basketball.unhealthy_date_only_DNP;
        


        ########### REGULAR HEALTH CYCLE START
		DROP TEMPORARY TABLE IF EXISTS basketball.healthy_date_cycles_excl_DNP;
		CREATE TEMPORARY TABLE basketball.healthy_date_cycles_excl_DNP
		(`DAY` DATE,PRIMARY KEY (DAY));
        
        REPLACE INTO basketball.healthy_date_cycles_excl_DNP
		SELECT DISTINCT A.DAY
		FROM basketball.hist_player_inj A
        WHERE A.acquired IN (@name)
			AND TRIM(BOTH '"' FROM notes) NOT LIKE 'fined %'
			AND TRIM(BOTH '"' FROM notes) NOT LIKE '% fined %'
			AND TRIM(BOTH '"' FROM notes) NOT LIKE '%suspen%'
			AND TRIM(BOTH '"' FROM notes) NOT LIKE '%DNP%'
			AND A.day NOT BETWEEN LAST_DAY(DATE_FORMAT(A.day, '%Y-04-%d')) AND LAST_DAY(DATE_FORMAT(A.day, '%Y-09-%d')) # in season only
		;
		DROP TEMPORARY TABLE IF EXISTS basketball.unhealthy_date_cycles_excl_DNP;
		CREATE TEMPORARY TABLE basketball.unhealthy_date_cycles_excl_DNP
		(`DAY` date, PRIMARY KEY (DAY));
        
        REPLACE INTO basketball.unhealthy_date_cycles_excl_DNP
		SELECT DISTINCT DAY
		FROM basketball.hist_player_inj A
		WHERE relinquished IN (@name)
			AND TRIM(BOTH '"' FROM notes) NOT LIKE 'fined %'
			AND TRIM(BOTH '"' FROM notes) NOT LIKE '% fined %'
			AND TRIM(BOTH '"' FROM notes) NOT LIKE '%suspen%'
            AND TRIM(BOTH '"' FROM notes) NOT LIKE '%DNP%'
            AND TRIM(BOTH '"' FROM notes) NOT LIKE 'suspended % game%'
            AND A.day NOT BETWEEN LAST_DAY(DATE_FORMAT(A.day, '%Y-04-%d')) AND LAST_DAY(DATE_FORMAT(A.day, '%Y-09-%d')) # in season only
        ;

        SET @first_healthy_date := (SELECT MIN(day) FROM basketball.healthy_date_cycles_excl_DNP);
        SET @first_unhealthy_date := (SELECT MIN(day) FROM basketball.unhealthy_date_cycles_excl_DNP);
--         SELECT @first_unhealthy_date;

        DELETE FROM basketball.healthy_date_cycles_excl_DNP
        WHERE DAY = CASE WHEN @first_healthy_date < @first_unhealthy_date THEN @first_healthy_date ELSE NULL END;
		
		SET @next_day := (SELECT MIN(day) FROM basketball.healthy_date_cycles_excl_DNP);
--         SET @first_season_half := ();
--         SET @second_season_half := ();
        SET @first_unhealthy_date_of_season := (
													SELECT 
														MIN(day) AS in_season_out 
													FROM basketball.unhealthy_date_cycles_excl_DNP
                                                    WHERE day BETWEEN DATE_FORMAT(@next_day-INTERVAL 1 YEAR, '%Y-10-01') AND @next_day
--                                                     WHERE day < @next_day
-- 														AND day >= DATE_FORMAT(@next_day-INTERVAL 1 YEAR, '%Y-10-01')
												);
-- 		SET @prev_day := DATE_FORMAT(@next_day, '%Y-01-01');
-- 		SET @prev_day := CONCAT(YEAR(@next_day)-1, '-10-15');
--         SET @prev_day := (CASE 
-- 							WHEN MONTH(@next_day) IN (10,11,12) THEN CONCAT(YEAR(@next_day), '-10-15')
--                             WHEN MONTH(@next_day) IN (1,2,3,4) THEN CONCAT(YEAR(@next_day)-1, '-10-15')
-- 						END);
		SET @prev_day := @first_unhealthy_date_of_season;
		# im here - ensure @name data pulled doesn't start off with a 'acquired' entry. if so, delete it.
--         SELECT @next_day;
--         SELECT @prev_day;

		WHILE @next_day IS NOT NULL DO
			REPLACE INTO basketball.player_inj_cycles_prefinal
			SELECT
				player_name,
				MAIN.start_health_cycle_team,
				IFNULL(MAIN.end_health_cycle_team,MAIN.start_health_cycle_team) AS end_health_cycle_team,
				MAIN.first_unhealthy_day AS unhealthy1,
				TRIM(TRIM(BOTH '"' FROM MAIN.first_unhealthy_day_notes)) AS first_unhealthy_day_notes,
				GREATEST(MAIN.first_unhealthy_day,MAIN.second_unhealthy_day) AS unhealthy2,
				TRIM(TRIM(BOTH '"' FROM MAIN.second_unhealthy_day_notes)) AS second_unhealthy_day_notes,
				GREATEST(MAIN.first_unhealthy_day,MAIN.second_unhealthy_day,MAIN.third_unhealthy_day) AS unhealthy3,
				TRIM(TRIM(BOTH '"' FROM MAIN.third_unhealthy_day_notes)) AS third_unhealthy_day_notes,
				GREATEST(MAIN.first_unhealthy_day,MAIN.second_unhealthy_day,MAIN.third_unhealthy_day,MAIN.fourth_unhealthy_day) AS unhealthy4,
				TRIM(TRIM(BOTH '"' FROM MAIN.fourth_unhealthy_day_notes)) AS fourth_unhealthy_day_notes,
				GREATEST(MAIN.first_unhealthy_day,MAIN.second_unhealthy_day,MAIN.third_unhealthy_day,MAIN.fourth_unhealthy_day,MAIN.fifth_unhealthy_day) AS unhealthy5,
				TRIM(TRIM(BOTH '"' FROM MAIN.fifth_unhealthy_day_notes)) AS fifth_unhealthy_day_notes,
                
				IFNULL(MAIN.first_healthy_day,@next_day) AS healthy,
				TRIM(TRIM(BOTH '"' FROM MAIN.first_healthy_day_notes)) AS healthy_notes,
				DATEDIFF(IFNULL(MAIN.first_healthy_day,@next_day),MAIN.first_unhealthy_day) AS days_to_recovery
			FROM 
				(
					SELECT
						GREATEST(X.acquired,X.relinquished) AS player_name,
						SUBSTRING_INDEX(GROUP_CONCAT(DISTINCT IF(X.action_type='healthy', X.team, NULL) ORDER BY X.day ASC SEPARATOR '; '), ';',1) AS end_health_cycle_team,
						SUBSTRING_INDEX(GROUP_CONCAT(DISTINCT IF(X.action_type='unhealthy', X.team, NULL) ORDER BY X.day ASC SEPARATOR '; '), ';',1) AS start_health_cycle_team,
						CAST(SUBSTRING_INDEX(GROUP_CONCAT(DISTINCT IF(X.action_type='healthy', X.day, NULL) ORDER BY X.day ASC SEPARATOR '; '), ';',1) AS DATE) AS first_healthy_day,
						GROUP_CONCAT(DISTINCT IF(X.action_type='unhealthy', X.day, NULL) ORDER BY X.day ASC SEPARATOR '; ') AS unhealthy_days,
						CAST(SUBSTRING_INDEX(GROUP_CONCAT(DISTINCT IF(X.action_type='unhealthy', X.day, NULL) ORDER BY X.day ASC SEPARATOR '; '), ';', 1) AS DATE) AS first_unhealthy_day,
						CASE
							WHEN SUBSTRING_INDEX(SUBSTRING_INDEX(GROUP_CONCAT(DISTINCT IF(X.action_type='unhealthy', X.day, NULL) ORDER BY X.day ASC SEPARATOR '; '), ';', 2), ';', -1) = 
									SUBSTRING_INDEX(GROUP_CONCAT(DISTINCT IF(X.action_type='unhealthy', X.day, NULL) ORDER BY X.day ASC SEPARATOR '; '), ';', 1)
								THEN NULL
							ELSE CAST(SUBSTRING_INDEX(SUBSTRING_INDEX(GROUP_CONCAT(DISTINCT IF(X.action_type='unhealthy', X.day, NULL) ORDER BY X.day ASC SEPARATOR '; '), ';', 2), ';', -1) AS DATE)
						END AS second_unhealthy_day,
						CASE
							WHEN SUBSTRING_INDEX(SUBSTRING_INDEX(GROUP_CONCAT(DISTINCT IF(X.action_type='unhealthy', X.day, NULL) ORDER BY X.day ASC SEPARATOR '; '), ';', 3), ';', -1) = 
									SUBSTRING_INDEX(SUBSTRING_INDEX(GROUP_CONCAT(DISTINCT IF(X.action_type='unhealthy', X.day, NULL) ORDER BY X.day ASC SEPARATOR '; '), ';', 2), ';', -1)
								THEN NULL
							ELSE CAST(SUBSTRING_INDEX(SUBSTRING_INDEX(GROUP_CONCAT(DISTINCT IF(X.action_type='unhealthy', X.day, NULL) ORDER BY X.day ASC SEPARATOR '; '), ';', 3), ';', -1) AS DATE)
						END AS third_unhealthy_day,
						CASE
							WHEN SUBSTRING_INDEX(SUBSTRING_INDEX(GROUP_CONCAT(DISTINCT IF(X.action_type='unhealthy', X.day, NULL) ORDER BY X.day ASC SEPARATOR '; '), ';', 4), ';', -1) = 
									SUBSTRING_INDEX(SUBSTRING_INDEX(GROUP_CONCAT(DISTINCT IF(X.action_type='unhealthy', X.day, NULL) ORDER BY X.day ASC SEPARATOR '; '), ';', 3), ';', -1)
								THEN NULL
							ELSE CAST(SUBSTRING_INDEX(SUBSTRING_INDEX(GROUP_CONCAT(DISTINCT IF(X.action_type='unhealthy', X.day, NULL) ORDER BY X.day ASC SEPARATOR '; '), ';', 4), ';', -1) AS DATE)
						END AS fourth_unhealthy_day,
						CASE
							WHEN SUBSTRING_INDEX(SUBSTRING_INDEX(GROUP_CONCAT(DISTINCT IF(X.action_type='unhealthy', X.day, NULL) ORDER BY X.day ASC SEPARATOR '; '), ';', 5), ';', -1) = 
									SUBSTRING_INDEX(SUBSTRING_INDEX(GROUP_CONCAT(DISTINCT IF(X.action_type='unhealthy', X.day, NULL) ORDER BY X.day ASC SEPARATOR '; '), ';', 4), ';', -1)
								THEN NULL
							ELSE CAST(SUBSTRING_INDEX(SUBSTRING_INDEX(GROUP_CONCAT(DISTINCT IF(X.action_type='unhealthy', X.day, NULL) ORDER BY X.day ASC SEPARATOR '; '), ';', 5), ';', -1) AS DATE)
						END AS fifth_unhealthy_day,

						SUBSTRING_INDEX(GROUP_CONCAT(DISTINCT IF(X.action_type='healthy', X.notes, NULL) ORDER BY X.day ASC SEPARATOR '; '), ';',1) AS first_healthy_day_notes,
						
						SUBSTRING_INDEX(GROUP_CONCAT(DISTINCT IF(X.action_type='unhealthy', X.notes, NULL) ORDER BY X.day ASC SEPARATOR '; '), ';', 1) AS first_unhealthy_day_notes,
						CASE
							WHEN SUBSTRING_INDEX(SUBSTRING_INDEX(GROUP_CONCAT(DISTINCT IF(X.action_type='unhealthy', X.day, NULL) ORDER BY X.day ASC SEPARATOR '; '), ';', 2), ';', -1) = 
									SUBSTRING_INDEX(GROUP_CONCAT(DISTINCT IF(X.action_type='unhealthy', X.day, NULL) ORDER BY X.day ASC SEPARATOR '; '), ';', 1)
								THEN NULL
							ELSE SUBSTRING_INDEX(SUBSTRING_INDEX(GROUP_CONCAT(DISTINCT IF(X.action_type='unhealthy', X.notes, NULL) ORDER BY X.day ASC SEPARATOR '; '), ';', 2), ';', -1)
						END AS second_unhealthy_day_notes,
						CASE
							WHEN SUBSTRING_INDEX(SUBSTRING_INDEX(GROUP_CONCAT(DISTINCT IF(X.action_type='unhealthy', X.day, NULL) ORDER BY X.day ASC SEPARATOR '; '), ';', 3), ';', -1) = 
									SUBSTRING_INDEX(SUBSTRING_INDEX(GROUP_CONCAT(DISTINCT IF(X.action_type='unhealthy', X.day, NULL) ORDER BY X.day ASC SEPARATOR '; '), ';', 2), ';', -1)
								THEN NULL
							ELSE SUBSTRING_INDEX(SUBSTRING_INDEX(GROUP_CONCAT(DISTINCT IF(X.action_type='unhealthy', X.notes, NULL) ORDER BY X.day ASC SEPARATOR '; '), ';', 3), ';', -1)
						END AS third_unhealthy_day_notes,
						CASE
							WHEN SUBSTRING_INDEX(SUBSTRING_INDEX(GROUP_CONCAT(DISTINCT IF(X.action_type='unhealthy', X.day, NULL) ORDER BY X.day ASC SEPARATOR '; '), ';', 4), ';', -1) = 
									SUBSTRING_INDEX(SUBSTRING_INDEX(GROUP_CONCAT(DISTINCT IF(X.action_type='unhealthy', X.day, NULL) ORDER BY X.day ASC SEPARATOR '; '), ';', 3), ';', -1)
								THEN NULL
							ELSE SUBSTRING_INDEX(SUBSTRING_INDEX(GROUP_CONCAT(DISTINCT IF(X.action_type='unhealthy', X.notes, NULL) ORDER BY X.day ASC SEPARATOR '; '), ';', 4), ';', -1)
						END AS fourth_unhealthy_day_notes,
						CASE
							WHEN SUBSTRING_INDEX(SUBSTRING_INDEX(GROUP_CONCAT(DISTINCT IF(X.action_type='unhealthy', X.day, NULL) ORDER BY X.day ASC SEPARATOR '; '), ';', 5), ';', -1) = 
									SUBSTRING_INDEX(SUBSTRING_INDEX(GROUP_CONCAT(DISTINCT IF(X.action_type='unhealthy', X.day, NULL) ORDER BY X.day ASC SEPARATOR '; '), ';', 4), ';', -1)
								THEN NULL
							ELSE SUBSTRING_INDEX(SUBSTRING_INDEX(GROUP_CONCAT(DISTINCT IF(X.action_type='unhealthy', X.notes, NULL) ORDER BY X.day ASC SEPARATOR '; '), ';', 5), ';', -1)
						END AS fifth_unhealthy_day_notes
					FROM
						(
							SELECT
								'unhealthy' AS action_type,
								CAST(A.day AS DATE) AS day,
								A.team,
								A.acquired,
								A.relinquished,
								A.notes
							FROM basketball.hist_player_inj A
							WHERE relinquished=@name
-- 								AND day > @prev_day 
-- 								AND day <= @next_day
                                AND day BETWEEN @prev_day AND @next_day
--                                 AND YEAR(A.day) = YEAR(@next_day)
								AND TRIM(BOTH '"' FROM A.notes) NOT LIKE 'fined %'
								AND TRIM(BOTH '"' FROM A.notes) NOT LIKE '% fined %'
								AND TRIM(BOTH '"' FROM A.notes) NOT LIKE '%suspen%'
								AND TRIM(BOTH '"' FROM A.notes) NOT LIKE '%DNP%'
								AND day NOT BETWEEN LAST_DAY(DATE_FORMAT(A.day, '%Y-04-%d')) AND LAST_DAY(DATE_FORMAT(A.day, '%Y-09-%d')) # in season only
							UNION ALL
							SELECT 
								'healthy' AS action_type,
								CAST(B.day AS DATE) AS day,
								B.team,
								B.acquired,
								B.relinquished,
								B.notes
							FROM basketball.hist_player_inj B
							WHERE acquired=@name
-- 								AND day > @prev_day 
-- 								AND day <= @next_day
								AND day BETWEEN @prev_day AND @next_day
--                                 AND YEAR(B.day) = YEAR(@next_day)
								AND TRIM(BOTH '"' FROM B.notes) NOT LIKE 'fined %'
								AND TRIM(BOTH '"' FROM B.notes) NOT LIKE '% fined %'
								AND TRIM(BOTH '"' FROM B.notes) NOT LIKE '%suspen%'
								AND TRIM(BOTH '"' FROM B.notes) NOT LIKE '%DNP%'
								AND day NOT BETWEEN LAST_DAY(DATE_FORMAT(B.day, '%Y-04-%d')) AND LAST_DAY(DATE_FORMAT(B.day, '%Y-09-%d')) # in season only
							ORDER BY day
						) X
				) MAIN
			;

--             SELECT @next_day; # current healthy ending date
--             SELECT @prev_day; # current unhealthy starting date / previous health cycle ending date
--             SELECT @next_inj_day; # unhealthy starting datez
--             SELECT @in_season_comp_day; # unhealthy starting date
            
			SET @prev_day := @next_day;
			DELETE FROM basketball.healthy_date_cycles_excl_DNP WHERE day = @next_day; # THE FOLLOWING CODE IS SPECIFIC TO BASEBALL: OR day < (CASE WHEN @next_day = DATE_FORMAT(@next_day, '%Y-12-31') THEN @next_day ELSE '1990-06-11' END);

			SET @next_day := (SELECT MIN(day) FROM basketball.healthy_date_cycles_excl_DNP); # first basketball-trial
--             SET @in_season_comp_day:= DATE_FORMAT(@next_day-INTERVAL 1 YEAR, '%Y-10-15');
            SET @in_season_comp_day:= (CASE 
											WHEN MONTH(@next_day) IN (1,2,3,4) THEN DATE_FORMAT(@next_day-INTERVAL 1 YEAR, '%Y-10-15')
											WHEN MONTH(@next_day) IN (10,11,12) THEN DATE_FORMAT(@next_day, '%Y-10-15')
										END);

            
            # check below for end of season injuries
            DELETE FROM basketball.unhealthy_date_cycles_excl_DNP WHERE day < @prev_day;
            SET @next_inj_day := (SELECT MIN(day) FROM basketball.unhealthy_date_cycles_excl_DNP WHERE DAY >= @in_season_comp_day);
            SET @next_healthy_day := (SELECT MIN(day) FROM basketball.healthy_date_cycles_excl_DNP WHERE day != @next_day);
--             SET @next_next_inj_day := (SELECT MIN(day) FROM basketball.unhealthy_date_cycles_excl_DNP WHERE day > @next_inj_day);
            
--             AND A.day NOT BETWEEN LAST_DAY(DATE_FORMAT(A.day, '%Y-04-%d')) AND LAST_DAY(DATE_FORMAT(A.day, '%Y-09-%d')) # in season only 
            
            SET @prev_day := (SELECT CASE 
										WHEN @prev_day IS NULL THEN NULL                                         
--                                         # activated with no apparent relinquish
--                                         WHEN YEAR(@prev_day) = YEAR(@next_inj_day) AND @next_day BETWEEN @next_inj_day AND @next_next_inj_day THEN @next_next_day

                                        # end of season 
--                                         WHEN YEAR(@next_inj_day) < YEAR(@next_day) THEN DATE_FORMAT(@next_inj_day, '%Y-12-31')
--                                         WHEN YEAR(@next_inj_day) != YEAR(@next_day) THEN DATE_FORMAT(@prev_day, '%Y-12-31')
										## New logic for basketball
                                        WHEN @next_inj_day > @prev_day 
											AND @next_inj_day BETWEEN @in_season_comp_day AND @next_day THEN @next_inj_day
										WHEN @next_inj_day > @next_day THEN @next_healthy_day
										## New logic for basketball
--                                         WHEN @next_inj_day BETWEEN @prev_day AND @next_day AND YEAR(@next_inj_day) = YEAR(@next_day) THEN @next_day
--                                         WHEN @next_inj_day BETWEEN @prev_day AND @next_day AND YEAR(@next_inj_day) != YEAR(@next_day) THEN DATE_FORMAT(@next_inj_day, '%Y-12-31')
                                        ELSE @prev_day 
									END);
		END WHILE;
        DELETE FROM basketball.players_cycler WHERE p_name = @name;
        SET @name = (SELECT MIN(p_name) FROM basketball.players_cycler);
        ########### REGULAR HEALTH CYCLE END (BEFORE INSERTING INTO FINAL TABLE)
        
        REPLACE INTO basketball.player_injury_cycles
        SELECT
			A.*,
############
			CASE
				WHEN TRIM(BOTH '"' FROM A.first_unhealthy_day_notes) LIKE '%(DNP)%' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.first_unhealthy_day_notes), '(DNP)', 1)
				WHEN TRIM(BOTH '"' FROM A.first_unhealthy_day_notes) LIKE '%(DTD)%' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.first_unhealthy_day_notes), '(DTD)', 1)
				WHEN TRIM(BOTH '"' FROM A.first_unhealthy_day_notes) LIKE '%placed on IL with%' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.first_unhealthy_day_notes), 'placed on IL with ', -1)            
				WHEN TRIM(BOTH '"' FROM A.first_unhealthy_day_notes) LIKE 'placed on IL for %' 
					AND TRIM(BOTH '"' FROM A.first_unhealthy_day_notes) NOT LIKE 'placed on IL for %(out for season)' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.first_unhealthy_day_notes), ' for ', -1)
				WHEN TRIM(BOTH '"' FROM A.first_unhealthy_day_notes) LIKE 'placed on IL for %(out for season)' THEN SUBSTRING_INDEX(SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.first_unhealthy_day_notes), '(out for season)', 1), ' for ', -1)
				WHEN TRIM(BOTH '"' FROM A.first_unhealthy_day_notes) LIKE 'placed on IL recovering from %' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.first_unhealthy_day_notes), 'placed on IL ', -1)
				WHEN TRIM(BOTH '"' FROM A.first_unhealthy_day_notes) LIKE 'placed on IR recovering from %' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.first_unhealthy_day_notes), 'placed on IR ', -1)
				WHEN TRIM(BOTH '"' FROM A.first_unhealthy_day_notes) = 'placed on IL (out for season)' THEN 'placed on IL (out for season)'
				WHEN TRIM(BOTH '"' FROM A.first_unhealthy_day_notes) = 'placed on IL ineligible' THEN 'ineligible'

				WHEN TRIM(BOTH '"' FROM A.first_unhealthy_day_notes) LIKE '%(out for season)' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.first_unhealthy_day_notes), '(out for season)', 1)
				WHEN TRIM(BOTH '"' FROM A.first_unhealthy_day_notes) LIKE '%(out indefinitely)' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.first_unhealthy_day_notes), '(out indefinitely)', 1)
				WHEN TRIM(BOTH '"' FROM A.first_unhealthy_day_notes) LIKE 'placed on IR with %' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.first_unhealthy_day_notes), 'placed on IR with ', -1)
				WHEN TRIM(BOTH '"' FROM A.first_unhealthy_day_notes) LIKE 'placed on IR for %' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.first_unhealthy_day_notes), 'placed on IR for ', -1)
				WHEN TRIM(BOTH '"' FROM A.first_unhealthy_day_notes) LIKE '%(out % weeks)' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.first_unhealthy_day_notes), ' (out ', 1)
				WHEN TRIM(BOTH '"' FROM A.first_unhealthy_day_notes) LIKE '%(out % weeks)%' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.first_unhealthy_day_notes), ' (out ', 1)
				WHEN TRIM(BOTH '"' FROM A.first_unhealthy_day_notes) LIKE '%(out % months)' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.first_unhealthy_day_notes), ' (out ', 1)
				WHEN TRIM(BOTH '"' FROM A.first_unhealthy_day_notes) LIKE '%(out % month)' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.first_unhealthy_day_notes), ' (out ', 1)
				WHEN TRIM(BOTH '"' FROM A.first_unhealthy_day_notes) LIKE '%(out indefinitely)%' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.first_unhealthy_day_notes), '(out indefinitely)', 1)
				WHEN TRIM(BOTH '"' FROM A.first_unhealthy_day_notes) LIKE '%(out indefinteily)%' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.first_unhealthy_day_notes), '(out indefinteily)', 1)
				WHEN TRIM(BOTH '"' FROM A.first_unhealthy_day_notes) LIKE '%(date approximate)%' THEN REPLACE(SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.first_unhealthy_day_notes), '(date approximate)', 1), '(out for season)', '')
				WHEN TRIM(BOTH '"' FROM A.first_unhealthy_day_notes) LIKE '%(out for season) (date approximate)%' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.first_unhealthy_day_notes), '(out for season) (date approximate)', 1)
				WHEN TRIM(BOTH '"' FROM A.first_unhealthy_day_notes) LIKE '%(out % week)' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.first_unhealthy_day_notes), '(out ', 1)

				WHEN TRIM(BOTH '"' FROM A.first_unhealthy_day_notes) LIKE 'broken %' OR TRIM(BOTH '"' FROM A.first_unhealthy_day_notes) LIKE 'bruised %' THEN TRIM(BOTH '"' FROM A.first_unhealthy_day_notes)
				WHEN TRIM(BOTH '"' FROM A.first_unhealthy_day_notes) LIKE 'diagnosed with %' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.first_unhealthy_day_notes), 'diagnosed with ', -1)
				WHEN TRIM(BOTH '"' FROM A.first_unhealthy_day_notes) LIKE 'dislocated %' THEN TRIM(BOTH '"' FROM A.first_unhealthy_day_notes)
				WHEN TRIM(BOTH '"' FROM A.first_unhealthy_day_notes) LIKE 'fractured %' THEN TRIM(BOTH '"' FROM A.first_unhealthy_day_notes)
				WHEN TRIM(BOTH '"' FROM A.first_unhealthy_day_notes) LIKE 'torn %' THEN TRIM(BOTH '"' FROM A.first_unhealthy_day_notes)
				WHEN TRIM(BOTH '"' FROM A.first_unhealthy_day_notes) LIKE 'strained %' THEN TRIM(BOTH '"' FROM A.first_unhealthy_day_notes)
				WHEN TRIM(BOTH '"' FROM A.first_unhealthy_day_notes) LIKE 'sprained %' THEN TRIM(BOTH '"' FROM A.first_unhealthy_day_notes)
				WHEN TRIM(BOTH '"' FROM A.first_unhealthy_day_notes) LIKE 'COVID%' THEN TRIM(BOTH '"' FROM A.first_unhealthy_day_notes)
				
				WHEN TRIM(BOTH '"' FROM A.first_unhealthy_day_notes) LIKE 'left %' OR TRIM(BOTH '"' FROM A.first_unhealthy_day_notes) LIKE 'right %' THEN TRIM(BOTH '"' FROM A.first_unhealthy_day_notes)
				WHEN TRIM(BOTH '"' FROM A.first_unhealthy_day_notes) LIKE 'stress %' THEN TRIM(BOTH '"' FROM A.first_unhealthy_day_notes)
			END AS injury_details_1,
-- 			IF(TRIM(BOTH '"' from A.first_unhealthy_day_notes) LIKE '%tommy john%', 1, 0) AS tommy_john_injury_flag_1,
			CASE
				WHEN TRIM(BOTH '"' FROM A.first_unhealthy_day_notes) LIKE 'fined%' 
					AND TRIM(BOTH '"' FROM A.first_unhealthy_day_notes) LIKE '% for %' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.first_unhealthy_day_notes), ' for ', -1)
			
				WHEN TRIM(BOTH '"' FROM A.first_unhealthy_day_notes) LIKE 'arrested and charged with%' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.first_unhealthy_day_notes), 'arrested and charged with ', -1)
				WHEN TRIM(BOTH '"' FROM A.first_unhealthy_day_notes) LIKE 'arrested for %' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.first_unhealthy_day_notes), 'arrested for ', -1)
				WHEN TRIM(BOTH '"' FROM A.first_unhealthy_day_notes) LIKE 'arrested on %' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.first_unhealthy_day_notes), 'arrested on ', -1)
				WHEN TRIM(BOTH '"' FROM A.first_unhealthy_day_notes) LIKE 'charged with %' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.first_unhealthy_day_notes), 'charged with ', -1)

				WHEN TRIM(BOTH '"' FROM A.first_unhealthy_day_notes) LIKE 'player began serving suspension %game for %' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.first_unhealthy_day_notes), 'game for ', -1)
				WHEN TRIM(BOTH '"' FROM A.first_unhealthy_day_notes) LIKE 'player began serving suspension %games for %' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.first_unhealthy_day_notes), 'games for ', -1)
				WHEN TRIM(BOTH '"' FROM A.first_unhealthy_day_notes) LIKE 'suspended by NBA for % game %' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.first_unhealthy_day_notes), ' game for ', -1)
				WHEN TRIM(BOTH '"' FROM A.first_unhealthy_day_notes) LIKE 'suspended by NBA for % games for %' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.first_unhealthy_day_notes), ' games for ', -1)
				WHEN TRIM(BOTH '"' FROM A.first_unhealthy_day_notes) LIKE 'suspended by team indefinitely for %' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.first_unhealthy_day_notes), ' team indefinitely for ', -1)
				WHEN TRIM(BOTH '"' FROM A.first_unhealthy_day_notes) LIKE 'suspended by team for %' 
					AND (TRIM(BOTH '"' FROM A.first_unhealthy_day_notes) NOT LIKE '% game%' AND TRIM(BOTH '"' FROM A.first_unhealthy_day_notes) NOT LIKE '% day%') THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.first_unhealthy_day_notes), 'suspended by team for ', -1)
				WHEN TRIM(BOTH '"' FROM A.first_unhealthy_day_notes) LIKE 'suspended by team for %' 
					AND (TRIM(BOTH '"' FROM A.first_unhealthy_day_notes) LIKE '% _ game %' OR TRIM(BOTH '"' FROM A.first_unhealthy_day_notes) LIKE '% __ game %') THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.first_unhealthy_day_notes), ' game for ', -1)
				WHEN TRIM(BOTH '"' FROM A.first_unhealthy_day_notes) LIKE 'suspended by team for %' 
					AND (TRIM(BOTH '"' FROM A.first_unhealthy_day_notes) LIKE '% _ games %' OR TRIM(BOTH '"' FROM A.first_unhealthy_day_notes) LIKE '% __ games %') THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.first_unhealthy_day_notes), ' games for ', -1)

				WHEN TRIM(BOTH '"' FROM A.first_unhealthy_day_notes) LIKE 'pleaded guilty to %' THEN TRIM(BOTH '"' FROM A.first_unhealthy_day_notes)

				WHEN TRIM(BOTH '"' FROM A.first_unhealthy_day_notes) LIKE 'pleaded %' THEN TRIM(BOTH '"' FROM A.first_unhealthy_day_notes)
				WHEN TRIM(BOTH '"' FROM A.first_unhealthy_day_notes) LIKE 'sentenced to %' THEN TRIM(BOTH '"' FROM A.first_unhealthy_day_notes)
			END AS suspension_details_1,
-- 			CASE
-- 				WHEN TRIM(BOTH '"' from A.first_unhealthy_day_notes) = 'placed on paternity leave list'
-- 					OR TRIM(BOTH '"' from A.first_unhealthy_day_notes) = 'placed on paternity leave'
-- 					OR TRIM(BOTH '"' from A.first_unhealthy_day_notes) LIKE 'placed on paternity leave list%'
-- 					OR TRIM(BOTH '"' from A.first_unhealthy_day_notes) LIKE '%placed on paternity leave list%'
-- 					OR TRIM(BOTH '"' from A.first_unhealthy_day_notes) LIKE '%placed on paternity leave list' THEN 'paternity leave'
-- 				ELSE ''
-- 			END AS paternity_leave_1,
-- 			CASE
-- 				WHEN TRIM(BOTH '"' from A.first_unhealthy_day_notes) = 'placed on paternity leave list'
-- 					OR TRIM(BOTH '"' from A.first_unhealthy_day_notes) = 'placed on paternity leave'
-- 					OR TRIM(BOTH '"' from A.first_unhealthy_day_notes) LIKE 'placed on paternity leave list%'
-- 					OR TRIM(BOTH '"' from A.first_unhealthy_day_notes) LIKE '%placed on paternity leave list%'
-- 					OR TRIM(BOTH '"' from A.first_unhealthy_day_notes) LIKE '%placed on paternity leave list' THEN 1
-- 				ELSE 0
-- 			END AS paternity_flag_1,


-- 			CASE
-- 				WHEN TRIM(BOTH '"' from A.first_unhealthy_day_notes) = 'placed on bereavement list'
-- 					OR TRIM(BOTH '"' from A.first_unhealthy_day_notes) LIKE 'placed on bereavement%'
-- 					OR TRIM(BOTH '"' from A.first_unhealthy_day_notes) LIKE '%placed on bereavement%'
-- 					OR TRIM(BOTH '"' from A.first_unhealthy_day_notes) LIKE '%placed on bereavement' THEN 'bereavement list'
-- 				WHEN TRIM(BOTH '"' from A.first_unhealthy_day_notes) LIKE '%bereavement%' THEN 'bereavement list'
-- 				ELSE ''
-- 			END AS bereavement_leave_1,
-- 			CASE
-- 				WHEN TRIM(BOTH '"' from A.first_unhealthy_day_notes) = 'placed on bereavement list'
-- 					OR TRIM(BOTH '"' from A.first_unhealthy_day_notes) LIKE 'placed on bereavement%'
-- 					OR TRIM(BOTH '"' from A.first_unhealthy_day_notes) LIKE '%placed on bereavement%'
-- 					OR TRIM(BOTH '"' from A.first_unhealthy_day_notes) LIKE '%placed on bereavement' THEN 1
-- 				WHEN TRIM(BOTH '"' from A.first_unhealthy_day_notes) LIKE '%bereavement%' THEN 1
-- 				ELSE 0
-- 			END AS bereavement_flag_1,
-- 			CASE 
-- 				WHEN TRIM(BOTH '"' from A.first_unhealthy_day_notes) IN ('placed on restricted list', 
-- 													'placed on restricted list during suspension',
-- 													'placed on restricted list serving suspension', 
-- 													'placed on restricted list by MLB') THEN 'none_given'
-- 				WHEN TRIM(BOTH '"' from A.first_unhealthy_day_notes) LIKE 'placed on restricted list for %' THEN SUBSTRING_INDEX(TRIM(BOTH '"' from A.first_unhealthy_day_notes), ' for ',-1)
-- 				WHEN TRIM(BOTH '"' from A.first_unhealthy_day_notes) LIKE 'placed on restricted list with %' THEN SUBSTRING_INDEX(TRIM(BOTH '"' from A.first_unhealthy_day_notes), ' with ',-1)
-- 				WHEN TRIM(BOTH '"' from A.first_unhealthy_day_notes) LIKE 'placed on restricted list due %' THEN SUBSTRING_INDEX(TRIM(BOTH '"' from A.first_unhealthy_day_notes), ' due to ',-1)
-- 				WHEN TRIM(BOTH '"' from A.first_unhealthy_day_notes) LIKE 'placed on restricted list while serving %' THEN SUBSTRING_INDEX(TRIM(BOTH '"' from A.first_unhealthy_day_notes), ' while serving ',-1)
-- 				WHEN TRIM(BOTH '"' from A.first_unhealthy_day_notes) LIKE '%(%)'
-- 					AND TRIM(BOTH '"' from A.first_unhealthy_day_notes) NOT LIKE '%(date approximate)'
-- 					AND TRIM(BOTH '"' from A.first_unhealthy_day_notes) NOT LIKE 'COVID-19%' THEN SUBSTRING_INDEX(SUBSTRING_INDEX(TRIM(BOTH '"' from A.first_unhealthy_day_notes), ')', 1), '(', -1)
-- 				ELSE ''
-- 			END AS restricted_details_1,
			CASE
				WHEN TRIM(BOTH '"' FROM A.first_unhealthy_day_notes) LIKE 'will undergo %' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.first_unhealthy_day_notes), ' undergo ', -1)
				WHEN TRIM(BOTH '"' FROM A.first_unhealthy_day_notes) LIKE 'surgery %' OR TRIM(BOTH '"' FROM A.first_unhealthy_day_notes) LIKE '% surgery %' THEN TRIM(BOTH '"' FROM A.first_unhealthy_day_notes)
				WHEN TRIM(BOTH '"' FROM A.first_unhealthy_day_notes) LIKE 'surgery on %' THEN TRIM(BOTH '"' FROM A.first_unhealthy_day_notes)
				WHEN TRIM(BOTH '"' FROM A.first_unhealthy_day_notes) LIKE 'surgery to %' THEN TRIM(BOTH '"' FROM A.first_unhealthy_day_notes)
				WHEN TRIM(BOTH '"' FROM A.first_unhealthy_day_notes) LIKE 'arthroscopic surgery%' THEN TRIM(BOTH '"' FROM A.first_unhealthy_day_notes)
			END AS surgery_details_1,
-- 			CASE
-- 				WHEN TRIM(BOTH '"' from A.first_unhealthy_day_notes) LIKE '%personal%' THEN 'personal'
-- 				ELSE ''
-- 			END as personal_details_1,
			CASE
				WHEN TRIM(BOTH '"' FROM A.second_unhealthy_day_notes) LIKE '%(DNP)%' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.second_unhealthy_day_notes), '(DNP)', 1)
				WHEN TRIM(BOTH '"' FROM A.second_unhealthy_day_notes) LIKE '%(DTD)%' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.second_unhealthy_day_notes), '(DTD)', 1)
				WHEN TRIM(BOTH '"' FROM A.second_unhealthy_day_notes) LIKE '%placed on IL with%' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.second_unhealthy_day_notes), 'placed on IL with ', -1)            
				WHEN TRIM(BOTH '"' FROM A.second_unhealthy_day_notes) LIKE 'placed on IL for %' 
					AND TRIM(BOTH '"' FROM A.second_unhealthy_day_notes) NOT LIKE 'placed on IL for %(out for season)' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.second_unhealthy_day_notes), ' for ', -1)
				WHEN TRIM(BOTH '"' FROM A.second_unhealthy_day_notes) LIKE 'placed on IL for %(out for season)' THEN SUBSTRING_INDEX(SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.second_unhealthy_day_notes), '(out for season)', 1), ' for ', -1)
				WHEN TRIM(BOTH '"' FROM A.second_unhealthy_day_notes) LIKE 'placed on IL recovering from %' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.second_unhealthy_day_notes), 'placed on IL ', -1)
				WHEN TRIM(BOTH '"' FROM A.second_unhealthy_day_notes) LIKE 'placed on IR recovering from %' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.second_unhealthy_day_notes), 'placed on IR ', -1)
				WHEN TRIM(BOTH '"' FROM A.second_unhealthy_day_notes) = 'placed on IL (out for season)' THEN 'placed on IL (out for season)'
				WHEN TRIM(BOTH '"' FROM A.second_unhealthy_day_notes) = 'placed on IL ineligible' THEN 'ineligible'

				WHEN TRIM(BOTH '"' FROM A.second_unhealthy_day_notes) LIKE '%(out for season)' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.second_unhealthy_day_notes), '(out for season)', 1)
				WHEN TRIM(BOTH '"' FROM A.second_unhealthy_day_notes) LIKE '%(out indefinitely)' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.second_unhealthy_day_notes), '(out indefinitely)', 1)
				WHEN TRIM(BOTH '"' FROM A.second_unhealthy_day_notes) LIKE 'placed on IR with %' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.second_unhealthy_day_notes), 'placed on IR with ', -1)
				WHEN TRIM(BOTH '"' FROM A.second_unhealthy_day_notes) LIKE 'placed on IR for %' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.second_unhealthy_day_notes), 'placed on IR for ', -1)
				WHEN TRIM(BOTH '"' FROM A.second_unhealthy_day_notes) LIKE '%(out % weeks)' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.second_unhealthy_day_notes), ' (out ', 1)
				WHEN TRIM(BOTH '"' FROM A.second_unhealthy_day_notes) LIKE '%(out % weeks)%' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.second_unhealthy_day_notes), ' (out ', 1)
				WHEN TRIM(BOTH '"' FROM A.second_unhealthy_day_notes) LIKE '%(out % months)' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.second_unhealthy_day_notes), ' (out ', 1)
				WHEN TRIM(BOTH '"' FROM A.second_unhealthy_day_notes) LIKE '%(out % month)' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.second_unhealthy_day_notes), ' (out ', 1)
				WHEN TRIM(BOTH '"' FROM A.second_unhealthy_day_notes) LIKE '%(out indefinitely)%' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.second_unhealthy_day_notes), '(out indefinitely)', 1)
				WHEN TRIM(BOTH '"' FROM A.second_unhealthy_day_notes) LIKE '%(out indefinteily)%' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.second_unhealthy_day_notes), '(out indefinteily)', 1)
				WHEN TRIM(BOTH '"' FROM A.second_unhealthy_day_notes) LIKE '%(date approximate)%' THEN REPLACE(SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.second_unhealthy_day_notes), '(date approximate)', 1), '(out for season)', '')
				WHEN TRIM(BOTH '"' FROM A.second_unhealthy_day_notes) LIKE '%(out for season) (date approximate)%' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.second_unhealthy_day_notes), '(out for season) (date approximate)', 1)
				WHEN TRIM(BOTH '"' FROM A.second_unhealthy_day_notes) LIKE '%(out % week)' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.second_unhealthy_day_notes), '(out ', 1)

				WHEN TRIM(BOTH '"' FROM A.second_unhealthy_day_notes) LIKE 'broken %' OR TRIM(BOTH '"' FROM A.second_unhealthy_day_notes) LIKE 'bruised %' THEN TRIM(BOTH '"' FROM A.second_unhealthy_day_notes)
				WHEN TRIM(BOTH '"' FROM A.second_unhealthy_day_notes) LIKE 'diagnosed with %' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.second_unhealthy_day_notes), 'diagnosed with ', -1)
				WHEN TRIM(BOTH '"' FROM A.second_unhealthy_day_notes) LIKE 'dislocated %' THEN TRIM(BOTH '"' FROM A.second_unhealthy_day_notes)
				WHEN TRIM(BOTH '"' FROM A.second_unhealthy_day_notes) LIKE 'fractured %' THEN TRIM(BOTH '"' FROM A.second_unhealthy_day_notes)
				WHEN TRIM(BOTH '"' FROM A.second_unhealthy_day_notes) LIKE 'torn %' THEN TRIM(BOTH '"' FROM A.second_unhealthy_day_notes)
				WHEN TRIM(BOTH '"' FROM A.second_unhealthy_day_notes) LIKE 'strained %' THEN TRIM(BOTH '"' FROM A.second_unhealthy_day_notes)
				WHEN TRIM(BOTH '"' FROM A.second_unhealthy_day_notes) LIKE 'sprained %' THEN TRIM(BOTH '"' FROM A.second_unhealthy_day_notes)
				WHEN TRIM(BOTH '"' FROM A.second_unhealthy_day_notes) LIKE 'COVID%' THEN TRIM(BOTH '"' FROM A.second_unhealthy_day_notes)
				
				WHEN TRIM(BOTH '"' FROM A.second_unhealthy_day_notes) LIKE 'left %' OR TRIM(BOTH '"' FROM A.second_unhealthy_day_notes) LIKE 'right %' THEN TRIM(BOTH '"' FROM A.second_unhealthy_day_notes)
				WHEN TRIM(BOTH '"' FROM A.second_unhealthy_day_notes) LIKE 'stress %' THEN TRIM(BOTH '"' FROM A.second_unhealthy_day_notes)
			END AS injury_details_2,
-- 			IF(TRIM(BOTH '"' from A.second_unhealthy_day_notes) LIKE '%tommy john%', 1, 0) AS tommy_john_injury_flag_2,
			CASE
				WHEN TRIM(BOTH '"' FROM A.second_unhealthy_day_notes) LIKE 'fined%' 
					AND TRIM(BOTH '"' FROM A.second_unhealthy_day_notes) LIKE '% for %' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.second_unhealthy_day_notes), ' for ', -1)
			
				WHEN TRIM(BOTH '"' FROM A.second_unhealthy_day_notes) LIKE 'arrested and charged with%' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.second_unhealthy_day_notes), 'arrested and charged with ', -1)
				WHEN TRIM(BOTH '"' FROM A.second_unhealthy_day_notes) LIKE 'arrested for %' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.second_unhealthy_day_notes), 'arrested for ', -1)
				WHEN TRIM(BOTH '"' FROM A.second_unhealthy_day_notes) LIKE 'arrested on %' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.second_unhealthy_day_notes), 'arrested on ', -1)
				WHEN TRIM(BOTH '"' FROM A.second_unhealthy_day_notes) LIKE 'charged with %' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.second_unhealthy_day_notes), 'charged with ', -1)

				WHEN TRIM(BOTH '"' FROM A.second_unhealthy_day_notes) LIKE 'player began serving suspension %game for %' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.second_unhealthy_day_notes), 'game for ', -1)
				WHEN TRIM(BOTH '"' FROM A.second_unhealthy_day_notes) LIKE 'player began serving suspension %games for %' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.second_unhealthy_day_notes), 'games for ', -1)
				WHEN TRIM(BOTH '"' FROM A.second_unhealthy_day_notes) LIKE 'suspended by NBA for % game %' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.second_unhealthy_day_notes), ' game for ', -1)
				WHEN TRIM(BOTH '"' FROM A.second_unhealthy_day_notes) LIKE 'suspended by NBA for % games for %' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.second_unhealthy_day_notes), ' games for ', -1)
				WHEN TRIM(BOTH '"' FROM A.second_unhealthy_day_notes) LIKE 'suspended by team indefinitely for %' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.second_unhealthy_day_notes), ' team indefinitely for ', -1)
				WHEN TRIM(BOTH '"' FROM A.second_unhealthy_day_notes) LIKE 'suspended by team for %' 
					AND (TRIM(BOTH '"' FROM A.second_unhealthy_day_notes) NOT LIKE '% game%' AND TRIM(BOTH '"' FROM A.second_unhealthy_day_notes) NOT LIKE '% day%') THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.second_unhealthy_day_notes), 'suspended by team for ', -1)
				WHEN TRIM(BOTH '"' FROM A.second_unhealthy_day_notes) LIKE 'suspended by team for %' 
					AND (TRIM(BOTH '"' FROM A.second_unhealthy_day_notes) LIKE '% _ game %' OR TRIM(BOTH '"' FROM A.second_unhealthy_day_notes) LIKE '% __ game %') THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.second_unhealthy_day_notes), ' game for ', -1)
				WHEN TRIM(BOTH '"' FROM A.second_unhealthy_day_notes) LIKE 'suspended by team for %' 
					AND (TRIM(BOTH '"' FROM A.second_unhealthy_day_notes) LIKE '% _ games %' OR TRIM(BOTH '"' FROM A.second_unhealthy_day_notes) LIKE '% __ games %') THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.second_unhealthy_day_notes), ' games for ', -1)

				WHEN TRIM(BOTH '"' FROM A.second_unhealthy_day_notes) LIKE 'pleaded guilty to %' THEN TRIM(BOTH '"' FROM A.second_unhealthy_day_notes)

				WHEN TRIM(BOTH '"' FROM A.second_unhealthy_day_notes) LIKE 'pleaded %' THEN TRIM(BOTH '"' FROM A.second_unhealthy_day_notes)
				WHEN TRIM(BOTH '"' FROM A.second_unhealthy_day_notes) LIKE 'sentenced to %' THEN TRIM(BOTH '"' FROM A.second_unhealthy_day_notes)
			END AS suspension_details_2,
-- 			CASE
-- 				WHEN TRIM(BOTH '"' from A.second_unhealthy_day_notes) = 'placed on paternity leave list'
-- 					OR TRIM(BOTH '"' from A.second_unhealthy_day_notes) = 'placed on paternity leave'
-- 					OR TRIM(BOTH '"' from A.second_unhealthy_day_notes) LIKE 'placed on paternity leave list%'
-- 					OR TRIM(BOTH '"' from A.second_unhealthy_day_notes) LIKE '%placed on paternity leave list%'
-- 					OR TRIM(BOTH '"' from A.second_unhealthy_day_notes) LIKE '%placed on paternity leave list' THEN 'paternity leave'
-- 				ELSE ''
-- 			END AS paternity_leave_2,
-- 			CASE
-- 				WHEN TRIM(BOTH '"' from A.second_unhealthy_day_notes) = 'placed on paternity leave list'
-- 					OR TRIM(BOTH '"' from A.second_unhealthy_day_notes) = 'placed on paternity leave'
-- 					OR TRIM(BOTH '"' from A.second_unhealthy_day_notes) LIKE 'placed on paternity leave list%'
-- 					OR TRIM(BOTH '"' from A.second_unhealthy_day_notes) LIKE '%placed on paternity leave list%'
-- 					OR TRIM(BOTH '"' from A.second_unhealthy_day_notes) LIKE '%placed on paternity leave list' THEN 1
-- 				ELSE 0
-- 			END AS paternity_flag_2,


-- 			CASE
-- 				WHEN TRIM(BOTH '"' from A.second_unhealthy_day_notes) = 'placed on bereavement list'
-- 					OR TRIM(BOTH '"' from A.second_unhealthy_day_notes) LIKE 'placed on bereavement%'
-- 					OR TRIM(BOTH '"' from A.second_unhealthy_day_notes) LIKE '%placed on bereavement%'
-- 					OR TRIM(BOTH '"' from A.second_unhealthy_day_notes) LIKE '%placed on bereavement' THEN 'bereavement list'
-- 				WHEN TRIM(BOTH '"' from A.second_unhealthy_day_notes) LIKE '%bereavement%' THEN 'bereavement list'
-- 				ELSE ''
-- 			END AS bereavement_leave_2,
-- 			CASE
-- 				WHEN TRIM(BOTH '"' from A.second_unhealthy_day_notes) = 'placed on bereavement list'
-- 					OR TRIM(BOTH '"' from A.second_unhealthy_day_notes) LIKE 'placed on bereavement%'
-- 					OR TRIM(BOTH '"' from A.second_unhealthy_day_notes) LIKE '%placed on bereavement%'
-- 					OR TRIM(BOTH '"' from A.second_unhealthy_day_notes) LIKE '%placed on bereavement' THEN 1
-- 				WHEN TRIM(BOTH '"' from A.second_unhealthy_day_notes) LIKE '%bereavement%' THEN 1
-- 				ELSE 0
-- 			END AS bereavement_flag_2,
-- 			CASE 
-- 				WHEN TRIM(BOTH '"' from A.second_unhealthy_day_notes) IN ('placed on restricted list', 
-- 													'placed on restricted list during suspension',
-- 													'placed on restricted list serving suspension', 
-- 													'placed on restricted list by MLB') THEN 'none_given'
-- 				WHEN TRIM(BOTH '"' from A.second_unhealthy_day_notes) LIKE 'placed on restricted list for %' THEN SUBSTRING_INDEX(TRIM(BOTH '"' from A.second_unhealthy_day_notes), ' for ',-1)
-- 				WHEN TRIM(BOTH '"' from A.second_unhealthy_day_notes) LIKE 'placed on restricted list with %' THEN SUBSTRING_INDEX(TRIM(BOTH '"' from A.second_unhealthy_day_notes), ' with ',-1)
-- 				WHEN TRIM(BOTH '"' from A.second_unhealthy_day_notes) LIKE 'placed on restricted list due %' THEN SUBSTRING_INDEX(TRIM(BOTH '"' from A.second_unhealthy_day_notes), ' due to ',-1)
-- 				WHEN TRIM(BOTH '"' from A.second_unhealthy_day_notes) LIKE 'placed on restricted list while serving %' THEN SUBSTRING_INDEX(TRIM(BOTH '"' from A.second_unhealthy_day_notes), ' while serving ',-1)
-- 				WHEN TRIM(BOTH '"' from A.second_unhealthy_day_notes) LIKE '%(%)'
-- 					AND TRIM(BOTH '"' from A.second_unhealthy_day_notes) NOT LIKE '%(date approximate)'
-- 					AND TRIM(BOTH '"' from A.second_unhealthy_day_notes) NOT LIKE 'COVID-19%' THEN SUBSTRING_INDEX(SUBSTRING_INDEX(TRIM(BOTH '"' from A.second_unhealthy_day_notes), ')', 1), '(', -1)
-- 				ELSE ''
-- 			END AS restricted_details_2,
			CASE
				WHEN TRIM(BOTH '"' FROM A.second_unhealthy_day_notes) LIKE 'will undergo %' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.second_unhealthy_day_notes), ' undergo ', -1)
				WHEN TRIM(BOTH '"' FROM A.second_unhealthy_day_notes) LIKE 'surgery %' OR TRIM(BOTH '"' FROM A.second_unhealthy_day_notes) LIKE '% surgery %' THEN TRIM(BOTH '"' FROM A.second_unhealthy_day_notes)
				WHEN TRIM(BOTH '"' FROM A.second_unhealthy_day_notes) LIKE 'surgery on %' THEN TRIM(BOTH '"' FROM A.second_unhealthy_day_notes)
				WHEN TRIM(BOTH '"' FROM A.second_unhealthy_day_notes) LIKE 'surgery to %' THEN TRIM(BOTH '"' FROM A.second_unhealthy_day_notes)
				WHEN TRIM(BOTH '"' FROM A.second_unhealthy_day_notes) LIKE 'arthroscopic surgery%' THEN TRIM(BOTH '"' FROM A.second_unhealthy_day_notes)
			END AS surgery_details_2,
-- 			CASE
-- 				WHEN TRIM(BOTH '"' from A.second_unhealthy_day_notes) LIKE '%personal%' THEN 'personal'
-- 				ELSE ''
-- 			END as personal_details_2,
			CASE
				WHEN TRIM(BOTH '"' FROM A.third_unhealthy_day_notes) LIKE '%(DNP)%' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.third_unhealthy_day_notes), '(DNP)', 1)
				WHEN TRIM(BOTH '"' FROM A.third_unhealthy_day_notes) LIKE '%(DTD)%' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.third_unhealthy_day_notes), '(DTD)', 1)
				WHEN TRIM(BOTH '"' FROM A.third_unhealthy_day_notes) LIKE '%placed on IL with%' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.third_unhealthy_day_notes), 'placed on IL with ', -1)            
				WHEN TRIM(BOTH '"' FROM A.third_unhealthy_day_notes) LIKE 'placed on IL for %' 
					AND TRIM(BOTH '"' FROM A.third_unhealthy_day_notes) NOT LIKE 'placed on IL for %(out for season)' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.third_unhealthy_day_notes), ' for ', -1)
				WHEN TRIM(BOTH '"' FROM A.third_unhealthy_day_notes) LIKE 'placed on IL for %(out for season)' THEN SUBSTRING_INDEX(SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.third_unhealthy_day_notes), '(out for season)', 1), ' for ', -1)
				WHEN TRIM(BOTH '"' FROM A.third_unhealthy_day_notes) LIKE 'placed on IL recovering from %' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.third_unhealthy_day_notes), 'placed on IL ', -1)
				WHEN TRIM(BOTH '"' FROM A.third_unhealthy_day_notes) LIKE 'placed on IR recovering from %' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.third_unhealthy_day_notes), 'placed on IR ', -1)
				WHEN TRIM(BOTH '"' FROM A.third_unhealthy_day_notes) = 'placed on IL (out for season)' THEN 'placed on IL (out for season)'
				WHEN TRIM(BOTH '"' FROM A.third_unhealthy_day_notes) = 'placed on IL ineligible' THEN 'ineligible'

				WHEN TRIM(BOTH '"' FROM A.third_unhealthy_day_notes) LIKE '%(out for season)' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.third_unhealthy_day_notes), '(out for season)', 1)
				WHEN TRIM(BOTH '"' FROM A.third_unhealthy_day_notes) LIKE '%(out indefinitely)' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.third_unhealthy_day_notes), '(out indefinitely)', 1)
				WHEN TRIM(BOTH '"' FROM A.third_unhealthy_day_notes) LIKE 'placed on IR with %' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.third_unhealthy_day_notes), 'placed on IR with ', -1)
				WHEN TRIM(BOTH '"' FROM A.third_unhealthy_day_notes) LIKE 'placed on IR for %' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.third_unhealthy_day_notes), 'placed on IR for ', -1)
				WHEN TRIM(BOTH '"' FROM A.third_unhealthy_day_notes) LIKE '%(out % weeks)' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.third_unhealthy_day_notes), ' (out ', 1)
				WHEN TRIM(BOTH '"' FROM A.third_unhealthy_day_notes) LIKE '%(out % weeks)%' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.third_unhealthy_day_notes), ' (out ', 1)
				WHEN TRIM(BOTH '"' FROM A.third_unhealthy_day_notes) LIKE '%(out % months)' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.third_unhealthy_day_notes), ' (out ', 1)
				WHEN TRIM(BOTH '"' FROM A.third_unhealthy_day_notes) LIKE '%(out % month)' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.third_unhealthy_day_notes), ' (out ', 1)
				WHEN TRIM(BOTH '"' FROM A.third_unhealthy_day_notes) LIKE '%(out indefinitely)%' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.third_unhealthy_day_notes), '(out indefinitely)', 1)
				WHEN TRIM(BOTH '"' FROM A.third_unhealthy_day_notes) LIKE '%(out indefinteily)%' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.third_unhealthy_day_notes), '(out indefinteily)', 1)
				WHEN TRIM(BOTH '"' FROM A.third_unhealthy_day_notes) LIKE '%(date approximate)%' THEN REPLACE(SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.third_unhealthy_day_notes), '(date approximate)', 1), '(out for season)', '')
				WHEN TRIM(BOTH '"' FROM A.third_unhealthy_day_notes) LIKE '%(out for season) (date approximate)%' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.third_unhealthy_day_notes), '(out for season) (date approximate)', 1)
				WHEN TRIM(BOTH '"' FROM A.third_unhealthy_day_notes) LIKE '%(out % week)' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.third_unhealthy_day_notes), '(out ', 1)

				WHEN TRIM(BOTH '"' FROM A.third_unhealthy_day_notes) LIKE 'broken %' OR TRIM(BOTH '"' FROM A.third_unhealthy_day_notes) LIKE 'bruised %' THEN TRIM(BOTH '"' FROM A.third_unhealthy_day_notes)
				WHEN TRIM(BOTH '"' FROM A.third_unhealthy_day_notes) LIKE 'diagnosed with %' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.third_unhealthy_day_notes), 'diagnosed with ', -1)
				WHEN TRIM(BOTH '"' FROM A.third_unhealthy_day_notes) LIKE 'dislocated %' THEN TRIM(BOTH '"' FROM A.third_unhealthy_day_notes)
				WHEN TRIM(BOTH '"' FROM A.third_unhealthy_day_notes) LIKE 'fractured %' THEN TRIM(BOTH '"' FROM A.third_unhealthy_day_notes)
				WHEN TRIM(BOTH '"' FROM A.third_unhealthy_day_notes) LIKE 'torn %' THEN TRIM(BOTH '"' FROM A.third_unhealthy_day_notes)
				WHEN TRIM(BOTH '"' FROM A.third_unhealthy_day_notes) LIKE 'strained %' THEN TRIM(BOTH '"' FROM A.third_unhealthy_day_notes)
				WHEN TRIM(BOTH '"' FROM A.third_unhealthy_day_notes) LIKE 'sprained %' THEN TRIM(BOTH '"' FROM A.third_unhealthy_day_notes)
				WHEN TRIM(BOTH '"' FROM A.third_unhealthy_day_notes) LIKE 'COVID%' THEN TRIM(BOTH '"' FROM A.third_unhealthy_day_notes)
				
				WHEN TRIM(BOTH '"' FROM A.third_unhealthy_day_notes) LIKE 'left %' OR TRIM(BOTH '"' FROM A.third_unhealthy_day_notes) LIKE 'right %' THEN TRIM(BOTH '"' FROM A.third_unhealthy_day_notes)
				WHEN TRIM(BOTH '"' FROM A.third_unhealthy_day_notes) LIKE 'stress %' THEN TRIM(BOTH '"' FROM A.third_unhealthy_day_notes)
			END AS injury_details_3,
-- 			IF(TRIM(BOTH '"' from A.third_unhealthy_day_notes) LIKE '%tommy john%', 1, 0) AS tommy_john_injury_flag_3,
			CASE
				WHEN TRIM(BOTH '"' FROM A.third_unhealthy_day_notes) LIKE 'fined%' 
					AND TRIM(BOTH '"' FROM A.third_unhealthy_day_notes) LIKE '% for %' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.third_unhealthy_day_notes), ' for ', -1)
			
				WHEN TRIM(BOTH '"' FROM A.third_unhealthy_day_notes) LIKE 'arrested and charged with%' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.third_unhealthy_day_notes), 'arrested and charged with ', -1)
				WHEN TRIM(BOTH '"' FROM A.third_unhealthy_day_notes) LIKE 'arrested for %' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.third_unhealthy_day_notes), 'arrested for ', -1)
				WHEN TRIM(BOTH '"' FROM A.third_unhealthy_day_notes) LIKE 'arrested on %' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.third_unhealthy_day_notes), 'arrested on ', -1)
				WHEN TRIM(BOTH '"' FROM A.third_unhealthy_day_notes) LIKE 'charged with %' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.third_unhealthy_day_notes), 'charged with ', -1)

				WHEN TRIM(BOTH '"' FROM A.third_unhealthy_day_notes) LIKE 'player began serving suspension %game for %' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.third_unhealthy_day_notes), 'game for ', -1)
				WHEN TRIM(BOTH '"' FROM A.third_unhealthy_day_notes) LIKE 'player began serving suspension %games for %' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.third_unhealthy_day_notes), 'games for ', -1)
				WHEN TRIM(BOTH '"' FROM A.third_unhealthy_day_notes) LIKE 'suspended by NBA for % game %' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.third_unhealthy_day_notes), ' game for ', -1)
				WHEN TRIM(BOTH '"' FROM A.third_unhealthy_day_notes) LIKE 'suspended by NBA for % games for %' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.third_unhealthy_day_notes), ' games for ', -1)
				WHEN TRIM(BOTH '"' FROM A.third_unhealthy_day_notes) LIKE 'suspended by team indefinitely for %' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.third_unhealthy_day_notes), ' team indefinitely for ', -1)
				WHEN TRIM(BOTH '"' FROM A.third_unhealthy_day_notes) LIKE 'suspended by team for %' 
					AND (TRIM(BOTH '"' FROM A.third_unhealthy_day_notes) NOT LIKE '% game%' AND TRIM(BOTH '"' FROM A.third_unhealthy_day_notes) NOT LIKE '% day%') THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.third_unhealthy_day_notes), 'suspended by team for ', -1)
				WHEN TRIM(BOTH '"' FROM A.third_unhealthy_day_notes) LIKE 'suspended by team for %' 
					AND (TRIM(BOTH '"' FROM A.third_unhealthy_day_notes) LIKE '% _ game %' OR TRIM(BOTH '"' FROM A.third_unhealthy_day_notes) LIKE '% __ game %') THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.third_unhealthy_day_notes), ' game for ', -1)
				WHEN TRIM(BOTH '"' FROM A.third_unhealthy_day_notes) LIKE 'suspended by team for %' 
					AND (TRIM(BOTH '"' FROM A.third_unhealthy_day_notes) LIKE '% _ games %' OR TRIM(BOTH '"' FROM A.third_unhealthy_day_notes) LIKE '% __ games %') THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.third_unhealthy_day_notes), ' games for ', -1)

				WHEN TRIM(BOTH '"' FROM A.third_unhealthy_day_notes) LIKE 'pleaded guilty to %' THEN TRIM(BOTH '"' FROM A.third_unhealthy_day_notes)

				WHEN TRIM(BOTH '"' FROM A.third_unhealthy_day_notes) LIKE 'pleaded %' THEN TRIM(BOTH '"' FROM A.third_unhealthy_day_notes)
				WHEN TRIM(BOTH '"' FROM A.third_unhealthy_day_notes) LIKE 'sentenced to %' THEN TRIM(BOTH '"' FROM A.third_unhealthy_day_notes)
			END AS suspension_details_3,
-- 			CASE
-- 				WHEN TRIM(BOTH '"' from A.third_unhealthy_day_notes) = 'placed on paternity leave list'
-- 					OR TRIM(BOTH '"' from A.third_unhealthy_day_notes) = 'placed on paternity leave'
-- 					OR TRIM(BOTH '"' from A.third_unhealthy_day_notes) LIKE 'placed on paternity leave list%'
-- 					OR TRIM(BOTH '"' from A.third_unhealthy_day_notes) LIKE '%placed on paternity leave list%'
-- 					OR TRIM(BOTH '"' from A.third_unhealthy_day_notes) LIKE '%placed on paternity leave list' THEN 'paternity leave'
-- 				ELSE ''
-- 			END AS paternity_leave_3,
-- 			CASE
-- 				WHEN TRIM(BOTH '"' from A.third_unhealthy_day_notes) = 'placed on paternity leave list'
-- 					OR TRIM(BOTH '"' from A.third_unhealthy_day_notes) = 'placed on paternity leave'
-- 					OR TRIM(BOTH '"' from A.third_unhealthy_day_notes) LIKE 'placed on paternity leave list%'
-- 					OR TRIM(BOTH '"' from A.third_unhealthy_day_notes) LIKE '%placed on paternity leave list%'
-- 					OR TRIM(BOTH '"' from A.third_unhealthy_day_notes) LIKE '%placed on paternity leave list' THEN 1
-- 				ELSE 0
-- 			END AS paternity_flag_3,


-- 			CASE
-- 				WHEN TRIM(BOTH '"' from A.third_unhealthy_day_notes) = 'placed on bereavement list'
-- 					OR TRIM(BOTH '"' from A.third_unhealthy_day_notes) LIKE 'placed on bereavement%'
-- 					OR TRIM(BOTH '"' from A.third_unhealthy_day_notes) LIKE '%placed on bereavement%'
-- 					OR TRIM(BOTH '"' from A.third_unhealthy_day_notes) LIKE '%placed on bereavement' THEN 'bereavement list'
-- 				WHEN TRIM(BOTH '"' from A.third_unhealthy_day_notes) LIKE '%bereavement%' THEN 'bereavement list'
-- 				ELSE ''
-- 			END AS bereavement_leave_3,
-- 			CASE
-- 				WHEN TRIM(BOTH '"' from A.third_unhealthy_day_notes) = 'placed on bereavement list'
-- 					OR TRIM(BOTH '"' from A.third_unhealthy_day_notes) LIKE 'placed on bereavement%'
-- 					OR TRIM(BOTH '"' from A.third_unhealthy_day_notes) LIKE '%placed on bereavement%'
-- 					OR TRIM(BOTH '"' from A.third_unhealthy_day_notes) LIKE '%placed on bereavement' THEN 1
-- 				WHEN TRIM(BOTH '"' from A.third_unhealthy_day_notes) LIKE '%bereavement%' THEN 1
-- 				ELSE 0
-- 			END AS bereavement_flag_3,
-- 			CASE 
-- 				WHEN TRIM(BOTH '"' from A.third_unhealthy_day_notes) IN ('placed on restricted list', 
-- 													'placed on restricted list during suspension',
-- 													'placed on restricted list serving suspension', 
-- 													'placed on restricted list by MLB') THEN 'none_given'
-- 				WHEN TRIM(BOTH '"' from A.third_unhealthy_day_notes) LIKE 'placed on restricted list for %' THEN SUBSTRING_INDEX(TRIM(BOTH '"' from A.third_unhealthy_day_notes), ' for ',-1)
-- 				WHEN TRIM(BOTH '"' from A.third_unhealthy_day_notes) LIKE 'placed on restricted list with %' THEN SUBSTRING_INDEX(TRIM(BOTH '"' from A.third_unhealthy_day_notes), ' with ',-1)
-- 				WHEN TRIM(BOTH '"' from A.third_unhealthy_day_notes) LIKE 'placed on restricted list due %' THEN SUBSTRING_INDEX(TRIM(BOTH '"' from A.third_unhealthy_day_notes), ' due to ',-1)
-- 				WHEN TRIM(BOTH '"' from A.third_unhealthy_day_notes) LIKE 'placed on restricted list while serving %' THEN SUBSTRING_INDEX(TRIM(BOTH '"' from A.third_unhealthy_day_notes), ' while serving ',-1)
-- 				WHEN TRIM(BOTH '"' from A.third_unhealthy_day_notes) LIKE '%(%)'
-- 					AND TRIM(BOTH '"' from A.third_unhealthy_day_notes) NOT LIKE '%(date approximate)'
-- 					AND TRIM(BOTH '"' from A.third_unhealthy_day_notes) NOT LIKE 'COVID-19%' THEN SUBSTRING_INDEX(SUBSTRING_INDEX(TRIM(BOTH '"' from A.third_unhealthy_day_notes), ')', 1), '(', -1)
-- 				ELSE ''
-- 			END AS restricted_details_3,
			CASE
				WHEN TRIM(BOTH '"' FROM A.third_unhealthy_day_notes) LIKE 'will undergo %' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.third_unhealthy_day_notes), ' undergo ', -1)
				WHEN TRIM(BOTH '"' FROM A.third_unhealthy_day_notes) LIKE 'surgery %' OR TRIM(BOTH '"' FROM A.third_unhealthy_day_notes) LIKE '% surgery %' THEN TRIM(BOTH '"' FROM A.third_unhealthy_day_notes)
				WHEN TRIM(BOTH '"' FROM A.third_unhealthy_day_notes) LIKE 'surgery on %' THEN TRIM(BOTH '"' FROM A.third_unhealthy_day_notes)
				WHEN TRIM(BOTH '"' FROM A.third_unhealthy_day_notes) LIKE 'surgery to %' THEN TRIM(BOTH '"' FROM A.third_unhealthy_day_notes)
				WHEN TRIM(BOTH '"' FROM A.third_unhealthy_day_notes) LIKE 'arthroscopic surgery%' THEN TRIM(BOTH '"' FROM A.third_unhealthy_day_notes)
			END AS surgery_details_3
-- 			CASEƒ
-- 				WHEN TRIM(BOTH '"' from A.third_unhealthy_day_notes) LIKE '%personal%' THEN 'personal'
-- 				ELSE ''
-- 			END as personal_details_3
############
		FROM basketball.player_inj_cycles_prefinal A;
        TRUNCATE basketball.player_inj_cycles_prefinal;


	END WHILE;
    #DROP TABLES IF EXISTS basketball.healthy_date_cycles_excl_DNP, basketball.players_cycler, basketball.unhealthy_date_cycles_excl_DNP,basketball.player_inj_cycles_prefinal;
END $$
DELIMITER ;

CALL basketball.health_cycle_backfill_proc();


/*

SELECT 
	name,
	classification2,
	notes1,
    SUBSTRING_INDEX(GROUP_CONCAT(DAY ORDER BY DAY SEPARATOR ';'), ';', 1) AS start_day,
	SUBSTRING_INDEX(GROUP_CONCAT(DAY ORDER BY DAY SEPARATOR ';'), ';', -1) AS end_day,
	DATEDIFF(SUBSTRING_INDEX(GROUP_CONCAT(DAY ORDER BY DAY SEPARATOR ';'), ';', -1), SUBSTRING_INDEX(GROUP_CONCAT(DAY ORDER BY DAY SEPARATOR ';'), ';', 1))+1 AS date_diff
	
FROM basketball.unhealthy_date_only_DNP_expanded
WHERE name = 'Vladimir Radmanovic'
GROUP BY classification2,notes1,name
ORDER BY start_day
LIMIT 10000;

SELECT @name;

SELECT *
FROM basketball.player_inj_cycles_prefinal;

SELECT *
FROM basketball.player_injury_cycles
LIMIT 1000;













/*
BELOW initied the basketball classification

SELECT
	TRIM(BOTH '"' FROM A.notes) AS notes,
    CASE
		# injury
        WHEN TRIM(BOTH '"' FROM A.notes) LIKE '%(DNP)%' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.notes), '(DNP)', 1)
        WHEN TRIM(BOTH '"' FROM A.notes) LIKE '%(DTD)%' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.notes), '(DTD)', 1)
        WHEN TRIM(BOTH '"' FROM A.notes) LIKE '%placed on IL with%' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.notes), 'placed on IL with ', -1)            
		WHEN TRIM(BOTH '"' FROM A.notes) LIKE 'placed on IL for %' 
			AND TRIM(BOTH '"' FROM A.notes) NOT LIKE 'placed on IL for %(out for season)' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.notes), ' for ', -1)
		WHEN TRIM(BOTH '"' FROM A.notes) LIKE 'placed on IL for %(out for season)' THEN SUBSTRING_INDEX(SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.notes), '(out for season)', 1), ' for ', -1)
        WHEN TRIM(BOTH '"' FROM A.notes) LIKE 'placed on IL recovering from %' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.notes), 'placed on IL ', -1)
        WHEN TRIM(BOTH '"' FROM A.notes) LIKE 'placed on IR recovering from %' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.notes), 'placed on IR ', -1)
        WHEN TRIM(BOTH '"' FROM A.notes) = 'placed on IL (out for season)' THEN 'placed on IL (out for season)'
        WHEN TRIM(BOTH '"' FROM A.notes) = 'placed on IL ineligible' THEN 'ineligible'

        WHEN TRIM(BOTH '"' FROM A.notes) LIKE '%(out for season)' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.notes), '(out for season)', 1)
        WHEN TRIM(BOTH '"' FROM A.notes) LIKE '%(out indefinitely)' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.notes), '(out indefinitely)', 1)
        WHEN TRIM(BOTH '"' FROM A.notes) LIKE 'placed on IR with %' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.notes), 'placed on IR with ', -1)
        WHEN TRIM(BOTH '"' FROM A.notes) LIKE 'placed on IR for %' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.notes), 'placed on IR for ', -1)
        WHEN TRIM(BOTH '"' FROM A.notes) LIKE '%(out % weeks)' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.notes), ' (out ', 1)
        WHEN TRIM(BOTH '"' FROM A.notes) LIKE '%(out % weeks)%' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.notes), ' (out ', 1)
        WHEN TRIM(BOTH '"' FROM A.notes) LIKE '%(out % months)' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.notes), ' (out ', 1)
        WHEN TRIM(BOTH '"' FROM A.notes) LIKE '%(out % month)' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.notes), ' (out ', 1)
        WHEN TRIM(BOTH '"' FROM A.notes) LIKE '%(out indefinitely)%' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.notes), '(out indefinitely)', 1)
        WHEN TRIM(BOTH '"' FROM A.notes) LIKE '%(out indefinteily)%' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.notes), '(out indefinteily)', 1)
        WHEN TRIM(BOTH '"' FROM A.notes) LIKE '%(date approximate)%' THEN REPLACE(SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.notes), '(date approximate)', 1), '(out for season)', '')
        WHEN TRIM(BOTH '"' FROM A.notes) LIKE '%(out for season) (date approximate)%' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.notes), '(out for season) (date approximate)', 1)
        WHEN TRIM(BOTH '"' FROM A.notes) LIKE '%(out % week)' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.notes), '(out ', 1)

        WHEN TRIM(BOTH '"' FROM A.notes) LIKE 'broken %' OR TRIM(BOTH '"' FROM A.notes) LIKE 'bruised %' THEN TRIM(BOTH '"' FROM A.notes)
        WHEN TRIM(BOTH '"' FROM A.notes) LIKE 'diagnosed with %' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.notes), 'diagnosed with ', -1)
        WHEN TRIM(BOTH '"' FROM A.notes) LIKE 'dislocated %' THEN TRIM(BOTH '"' FROM A.notes)
        WHEN TRIM(BOTH '"' FROM A.notes) LIKE 'fractured %' THEN TRIM(BOTH '"' FROM A.notes)
        WHEN TRIM(BOTH '"' FROM A.notes) LIKE 'torn %' THEN TRIM(BOTH '"' FROM A.notes)
        WHEN TRIM(BOTH '"' FROM A.notes) LIKE 'strained %' THEN TRIM(BOTH '"' FROM A.notes)
        WHEN TRIM(BOTH '"' FROM A.notes) LIKE 'sprained %' THEN TRIM(BOTH '"' FROM A.notes)
        WHEN TRIM(BOTH '"' FROM A.notes) LIKE 'COVID%' THEN TRIM(BOTH '"' FROM A.notes)
        
		WHEN TRIM(BOTH '"' FROM A.notes) LIKE 'left %' OR TRIM(BOTH '"' FROM A.notes) LIKE 'right %' THEN TRIM(BOTH '"' FROM A.notes)
		WHEN TRIM(BOTH '"' FROM A.notes) LIKE 'stress %' THEN TRIM(BOTH '"' FROM A.notes)


        # suspension
		WHEN TRIM(BOTH '"' FROM A.notes) LIKE 'fined%' 
			AND TRIM(BOTH '"' FROM A.notes) LIKE '% for %' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.notes), ' for ', -1)
	
        WHEN TRIM(BOTH '"' FROM A.notes) LIKE 'arrested and charged with%' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.notes), 'arrested and charged with ', -1)
        WHEN TRIM(BOTH '"' FROM A.notes) LIKE 'arrested for %' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.notes), 'arrested for ', -1)
        WHEN TRIM(BOTH '"' FROM A.notes) LIKE 'arrested on %' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.notes), 'arrested on ', -1)
        WHEN TRIM(BOTH '"' FROM A.notes) LIKE 'charged with %' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.notes), 'charged with ', -1)

        WHEN TRIM(BOTH '"' FROM A.notes) LIKE 'player began serving suspension %game for %' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.notes), 'game for ', -1)
        WHEN TRIM(BOTH '"' FROM A.notes) LIKE 'player began serving suspension %games for %' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.notes), 'games for ', -1)
        WHEN TRIM(BOTH '"' FROM A.notes) LIKE 'suspended by NBA for % game %' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.notes), ' game for ', -1)
        WHEN TRIM(BOTH '"' FROM A.notes) LIKE 'suspended by NBA for % games for %' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.notes), ' games for ', -1)
		WHEN TRIM(BOTH '"' FROM A.notes) LIKE 'suspended by team indefinitely for %' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.notes), ' team indefinitely for ', -1)
		WHEN TRIM(BOTH '"' FROM A.notes) LIKE 'suspended by team for %' 
			AND (TRIM(BOTH '"' FROM A.notes) NOT LIKE '% game%' AND TRIM(BOTH '"' FROM A.notes) NOT LIKE '% day%') THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.notes), 'suspended by team for ', -1)
		WHEN TRIM(BOTH '"' FROM A.notes) LIKE 'suspended by team for %' 
			AND (TRIM(BOTH '"' FROM A.notes) LIKE '% _ game %' OR TRIM(BOTH '"' FROM A.notes) LIKE '% __ game %') THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.notes), ' game for ', -1)
		WHEN TRIM(BOTH '"' FROM A.notes) LIKE 'suspended by team for %' 
			AND (TRIM(BOTH '"' FROM A.notes) LIKE '% _ games %' OR TRIM(BOTH '"' FROM A.notes) LIKE '% __ games %') THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.notes), ' games for ', -1)

		WHEN TRIM(BOTH '"' FROM A.notes) LIKE 'pleaded guilty to %' THEN TRIM(BOTH '"' FROM A.notes)

		WHEN TRIM(BOTH '"' FROM A.notes) LIKE 'pleaded %' THEN TRIM(BOTH '"' FROM A.notes)
		WHEN TRIM(BOTH '"' FROM A.notes) LIKE 'sentenced to %' THEN TRIM(BOTH '"' FROM A.notes)
         
		# surgery
		WHEN TRIM(BOTH '"' FROM A.notes) LIKE 'will undergo %' THEN SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.notes), ' undergo ', -1)
		WHEN TRIM(BOTH '"' FROM A.notes) LIKE 'surgery %' OR TRIM(BOTH '"' FROM A.notes) LIKE '% surgery %' THEN TRIM(BOTH '"' FROM A.notes)
        WHEN TRIM(BOTH '"' FROM A.notes) LIKE 'surgery on %' THEN TRIM(BOTH '"' FROM A.notes)
        WHEN TRIM(BOTH '"' FROM A.notes) LIKE 'surgery to %' THEN TRIM(BOTH '"' FROM A.notes)
        WHEN TRIM(BOTH '"' FROM A.notes) LIKE 'arthroscopic surgery%' THEN TRIM(BOTH '"' FROM A.notes)
	END AS details,
	IF(TRIM(BOTH '"' FROM A.notes) LIKE '% (left game)', SUBSTRING_INDEX(TRIM(BOTH '"' FROM A.notes), ' (left game', 1), 0) AS test_flag,
    COUNT(*) AS instances
FROM basketball.hist_player_inj
WHERE relinquished!=''
-- 	AND TRIM(BOTH '"' FROM A.notes) != 'placed on IL'
--     AND A.notes != 'DNP'
-- 	AND A.notes NOT LIKE '%(DNP)%'
-- 	AND A.notes NOT LIKE '%(DTD)%'
--     AND A.notes NOT LIKE '%placed on IL with%'
--     AND (A.notes NOT LIKE '%fined %' AND TRIM(BOTH '"' FROM A.notes) NOT LIKE 'fined $%' AND TRIM(BOTH '"' FROM A.notes) NOT LIKE 'fined as %')
--     AND A.notes NOT LIKE 'placed on IL%'

--     AND A.notes NOT LIKE '%(out for season)'
--     AND A.notes NOT LIKE '%(out indefinitely)'
--     AND A.notes NOT LIKE 'placed on IR with %'
--     AND A.notes NOT LIKE '%(out % weeks)'
--     AND A.notes NOT LIKE '%(out % months)'
--     AND A.notes NOT LIKE '%out indefinitely%'
--     AND A.notes NOT LIKE '%(out indefinteily)%'
--     AND A.notes NOT LIKE '%(date approximate)%' AND A.notes NOT LIKE '%(out % weeks)%'
-- 	AND A.notes NOT LIKE '%(out % weeks)%'
--     AND A.notes NOT LIKE '%(out % week)'
--     AND A.notes NOT LIKE '%manager%' AND A.notes NOT LIKE '%coach%'
--     AND A.notes NOT LIKE 'charged with%'
--     AND A.notes NOT LIKE 'broken %' 
--     AND A.notes NOT LIKE 'bruised %'
--     AND A.notes NOT LIKE 'dislocated %'
--     AND A.notes NOT LIKE 'suspended by NBA%'
--     AND A.notes NOT LIKE 'suspended by team %'
--     AND A.notes NOT LIKE '% (left game)'
--     AND A.notes NOT LIKE 'left %'
--     AND A.notes NOT LIKE 'stress %'
--     AND A.notes NOT LIKE 'will undergo %'
GROUP BY A.notes
-- HAVING details = ''
ORDER BY instances DESC
;

SELECT *
FROM baseball.player_inj_cycles_prefinal
;



