import os
# import mysql.connector as mysql
# from mysql.connector import pooling



####################################################################################################
# 000 - CREDENTIALS 
####################################################################################################

# prod env 
sports_db_admin_host=os.environ.get('basketball_host')
sports_db_admin_db=os.environ.get('basketball_db')
sports_db_admin_user=os.environ.get('basketball_user')
sports_db_admin_pw=os.environ.get('basketball_pw')
sports_db_admin_port=os.environ.get('basketball_port')


# # dev env
# sports_db_admin_host=os.environ.get('sports_db_admin_host')
# sports_db_admin_db='basketball'
# sports_db_admin_user=os.environ.get('sports_db_admin_user')
# sports_db_admin_pw=os.environ.get('sports_db_admin_pw')
# sports_db_admin_port=os.environ.get('sports_db_admin_port')


dbconfig = {
    "host":sports_db_admin_host,
    "database":sports_db_admin_db,
    "user":sports_db_admin_user,
    "password":sports_db_admin_pw,
    "port":sports_db_admin_port
}

def get_creds():
	return dbconfig

