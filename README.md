# fantasy_basketball
**Leveraging Data for better basketball decisions**

## Objective: 
This capstone project aims to optimize the performance of my fantasy basketball teams in ESPN and Yahoo leagues. It aims to enhance my roster across 4 areas - 1) points predictions at the player level using various models, including time-series based; 2) provides a minute-weighted screening tool for top players in free agency; 3) weekly performance of my current team for the season; 4) AI chatbox where users can ask questions to a Claude LLM and receive suggestions based on the data.

## High-level Summary: 
ESPN and Yahoo APIs are leveraged for league data ([ESPN](https://github.com/cwendt94/espn-api), [Yahoo](https://pypi.org/project/yahoo-fantasy-api/)). Daily player data is obtained from the basketball-reference website using the [basketball_reference_web_scraper](https://github.com/jaebradley/basketball_reference_web_scraper) API. Player injury data is scraped from the [Pro Sports Transactions](https://prosportstransactions.com/) website. All data is stored and maintained in a MariaDB database.

A requirements txt file included - pip install /path_to_file/requirements.txt

## Web Application Tool

### Predictive Modeling
Points prediction by player for the next five games across the ESPN and Yahoo platforms. Models include: 
1. Standard time-series - Autoregressive Integrated Moving Average, Autoregressive Moving Average, Double Exponential Smoothing, Single Exponential Smoothing, Autoregressive, Moving Average
2. Machine Learning - Long Short-Term Memory, Neural Networks
3. Default base - Last value, repeat values

### Free Agent Screening Tool
This web app provides fantasy managers with a screening tool that can rank free agent players weighted by minutes on the court production, a feature not available in ESPN, Yahoo, or other common fantasy basketball websites. This feature is useful in screening free agents in the fantasy manager's ESPN and Yahoo leagues. 

### Current Team Performance
The web app also includes survival models (using Kaplan Meier estimation) to estimate the probability a player is out x days based on a particular injury. 

### AI Assistant
An AI chatbox powered by Claude LLMs allows users to ask questions and get real response suggestions based on the data

A preview and link to the web app shown below:
[Free Agent Analysis Helper Tool](https://fantasy-basketball-team-dash-aef016454ed4.herokuapp.com/)
![Image](https://github.com/francisco-avalos/fantasy_basketball/blob/main/assets/basketball_hoops2.jpg)
