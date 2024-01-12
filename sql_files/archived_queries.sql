
/*

The intention with the below query was to obtain a player's historical data through the most recent game. Adding to that, the next few games on the player's schedule.

ARCHIVED REASON: The actual date is not necessary when time series modeling. 
** To present the time series data as one continuous time frame without off season gaps, modeling via ordinal sorting the data retains the time order. 

*/
SELECT 
    DATE(SUBDATE(SCHED.start_time, INTERVAL 8 HOUR)) AS pst_game_day, 
    SCHED.away_team,
    SCHED.home_team,
    A.*
FROM basketball.high_level_nba_team_schedules SCHED
LEFT JOIN
    (
        SELECT A.*
        FROM basketball.historical_player_data A
        WHERE A.name IN (SELECT name FROM basketball.live_yahoo_players)
            AND A.slug = '{player_id}'
    ) A ON (A.team = (CASE WHEN A.location LIKE '%HOME%' THEN SCHED.home_team END)
                                                OR A.team = (CASE WHEN A.location LIKE '%AWAY%' THEN SCHED.away_team END))
                                                AND DATE(SUBDATE(SCHED.start_time, INTERVAL 8 HOUR)) = A.date
WHERE SCHED.start_time BETWEEN '2023-10-01' AND ADDDATE(CURDATE(),INTERVAl 3 DAY)
    AND (
            # current team
            SCHED.away_team LIKE (
                                SELECT SUBSTRING_INDEX(GROUP_CONCAT(DISTINCT A.team ORDER BY A.date DESC SEPARATOR ";"), ";", 1) AS team
                                FROM basketball.historical_player_data A
                                WHERE A.name IN (SELECT name FROM basketball.live_yahoo_players)
                                    AND A.slug = '{player_id}'
                                    AND A.date BETWEEN '2023-10-01' AND ADDDATE(CURDATE(), INTERVAL 3 DAY)
                                    )
        OR SCHED.home_team LIKE (
                                SELECT SUBSTRING_INDEX(GROUP_CONCAT(DISTINCT A.team ORDER BY A.date DESC SEPARATOR ";"), ";", 1) AS team
                                FROM basketball.historical_player_data A
                                WHERE A.name IN (SELECT name FROM basketball.live_yahoo_players)
                                    AND A.slug = '{player_id}'
                                    AND A.date BETWEEN '2023-10-01' AND ADDDATE(CURDATE(), INTERVAL 3 DAY)
                                    )
            # former team if changed this season
        OR SCHED.away_team LIKE (
                                SELECT SUBSTRING_INDEX(SUBSTRING_INDEX(GROUP_CONCAT(DISTINCT A.team ORDER BY A.date DESC SEPARATOR ";"), ";", 2), ";", -1) AS team
                                FROM basketball.historical_player_data A
                                WHERE A.name IN (SELECT name FROM basketball.live_yahoo_players)
                                    AND A.slug = '{player_id}'
                                    AND A.date BETWEEN '2023-10-01' AND ADDDATE(CURDATE(), INTERVAL 3 DAY)
                                    )
        OR SCHED.home_team LIKE (
                                SELECT SUBSTRING_INDEX(SUBSTRING_INDEX(GROUP_CONCAT(DISTINCT A.team ORDER BY A.date DESC SEPARATOR ";"), ";", 2), ";", -1) AS team
                                FROM basketball.historical_player_data A
                                WHERE A.name IN (SELECT name FROM basketball.live_yahoo_players)
                                    AND A.slug = '{player_id}'
                                    AND A.date BETWEEN '2023-10-01' AND ADDDATE(CURDATE(), INTERVAL 3 DAY)
                                    )
        )
-- ORDER BY pst_game_day DESC
UNION ALL
SELECT 
    A.date AS pst_game_day,
    CASE WHEN A.location = 'Location.AWAY' THEN A.team ELSE A.opponent END AS away_team,
    CASE WHEN A.location = 'Location.HOME' THEN A.team ELSE A.opponent END AS home_team,
    A.*
FROM basketball.historical_player_data A
WHERE A.name IN (SELECT name FROM basketball.live_yahoo_players)
    AND A.slug = '{player_id}'
    AND A.date <= '2023-10-01'
ORDER BY 1 DESC
;