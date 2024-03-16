# fantasy_basketball
**Leveraging Data for better basketball decisions**

## Objective: 
The aim of this captsone project is to build time-series based models and predict player performance. These predictions would improve decisions on player lineups with the intention of outscoring the opponent in the weekly matchups for fantasy basketball. 

## High-level Summary: 
ESPN and Yahoo APIs are leveraged for league data ([ESPN](https://github.com/cwendt94/espn-api), [Yahoo](https://pypi.org/project/yahoo-fantasy-api/)). Daily player data is obtained from the basketball-reference website using the [basketball_reference_web_scraper](https://github.com/jaebradley/basketball_reference_web_scraper) API. Player injury data is scraped from the [Pro Sports Transactions](https://prosportstransactions.com/) website. All data is stored and maintained in a MariaDB database.

A requirements txt file included - pip install /path_to_file/requirements.txt

## Web Application Tool
While the model is underway, a web application has been released. This web app provides fantasy managers with a screening tool that can rank free agent players on a by-minutes-on-the-court category production, a feature not available in ESPN, Yahoo, or other common fantasy basketball websites. This feature is useful in screening free agents in the fantasy manager's ESPN and Yahoo leagues. The web app also includes survival models (using Kaplan Meier estimation) to estimate day duration probabilities of player injuries. A preview and link to the web app shown below:
[Free Agent Analysis Helper Tool](https://fantasy-basketball-team-dash-aef016454ed4.herokuapp.com/)
![Image](https://github.com/francisco-avalos/fantasy_basketball/blob/main/assets/basketball_hoops2.jpg)
