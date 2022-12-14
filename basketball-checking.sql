

SELECT *
FROM basketball.injured_player_news;

select *
from basketball.my_team_stats
WHERE date = '2022-12-03'
ORDER BY date DESC;


SELECT *#min(date), max(date)
FROM basketball.historical_player_data
WHERE name LIKE '%dorian%'
ORDER BY game_score DESC
LIMIT 100;



SELECT *
FROM basketball.master_names_list_temp
;

SELECT *
FROM basketball.calendar
LIMIT 10;


SELECT *
-- SELECT COUNT(DISTINCT name)
-- SELECT COUNT(*)
FROM basketball.live_free_agents
LIMIT 100;

SHOW TABLE STATUS FROM basketball WHERE name LIKE '%live_free_agents%';

SELECT *
FROM basketball.my_team_stats
-- WHERE name='Aaron Holiday'
ORDER BY date DESC;






SELECT * FROM basketball.historical_player_data LIMIT 100;


select * from basketball.espn_players;
select * from basketball.basketball_references_players;



SELECT MAX(date) FROM basketball.historical_player_data;
SELECT * FROM basketball.historical_player_data ORDER BY date DESC LIMIT 100;

SELECT 
	season, 
	SUBSTRING_INDEX(GROUP_CONCAT(date ORDER BY date ASC SEPARATOR '; '), ';', 1) AS backfill_since_current_season_begins,
	SUBSTRING_INDEX(GROUP_CONCAT(date ORDER BY date DESC SEPARATOR '; '), ';', 1) AS backfill_since_current_season_latest_data_entry
FROM basketball.historical_player_data 
GROUP BY season
ORDER BY backfill_since_current_season_begin DESC 
LIMIT 1;


SELECT *
FROM basketball.historical_player_data
ORDER BY date DESC, game_score DESC
LIMIT 100
;

EXPLAIN basketball.advanced_stats;
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


SELECT *
FROM basketball.my_team_stats
WHERE date = '2022-11-30' AND name = 'Bruce Brown'
ORDER BY date DESC
LIMIT 100;


SELECT 
	MTS.name, 
    SUM(made_field_goals * seconds_played/60) / SUM(seconds_played/60) AS made_field_goals_weighted_by_mins_played
--     seconds_played/60 AS minutes_played
FROM basketball.my_team_stats MTS 
JOIN basketball.calendar C ON MTS.date=C.day
GROUP BY name
;


SELECT 
	MTS.*, 
    DATE_FORMAT(MTS.date, '%W') AS day_of_week,
	C.week_starting_monday, 
	C.week_ending_sunday 
FROM basketball.my_team_stats MTS 
JOIN basketball.calendar C ON MTS.date=C.day;



