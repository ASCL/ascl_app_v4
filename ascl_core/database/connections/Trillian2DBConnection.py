#!/usr/bin/python
# -*- coding: UTF-8 -*-

import os
import logging
from socket import gethostname
from urllib.parse import quote_plus
from configparser import ConfigParser

import sqlalchemy
from sqlalchemy.orm import sessionmaker, scoped_session

from dm_dbcore import DatabaseConnection

logger = logging.getLogger("DatabaseConnection logger")

# ---------------------------------------------------------------------
# Fill in database connection information here.
# The password is read from ~/.my.cnf (MySQL) or ~/.pgpass (PostgreSQL)
# so the source file can be checked into public version control.
# ---------------------------------------------------------------------

def read_mysql_config(group='client_ascl'):
	"""Read MySQL credentials from ~/.my.cnf and return a config dict."""
	config_path = os.path.expanduser('~/.my.cnf')

	config = ConfigParser()
	config.read(config_path)

	if group not in config:
		logger.warning(f"MySQL config section [{group}] not found in {config_path}")
		return {}

	return dict(config[group])

# Read credentials from ~/.my.cnf [client_ascl] section
mysql_config = read_mysql_config('client_ascl')

db_config = {
	'user'     : mysql_config.get('user', 'ascl_db'),
	'password' : mysql_config.get('password', ''),  # Will be URL-encoded below
	'database' : 'ascl_db_v4',  # the name of the database (v4 = upgraded schema with InnoDB+FKs)
	'host'     : mysql_config.get('host', 'localhost'),
	'port'     : int(mysql_config.get('port', 3307))
}

# URL-encode the password to handle special characters
if db_config['password']:
	db_config['password_encoded'] = quote_plus(db_config['password'])
else:
	db_config['password_encoded'] = ''

logger.info(f"Read MySQL credentials from ~/.my.cnf [client_ascl]")
# ---------------------------------------------------------------------

# The default connection is via "localhost". If the local host name is not "...",
# assume we are connecting via port xxxx (the standard SSH tunnel port for the database).

#if gethostname() != "...":
#	db_config["port"] = xxxx

# Finally, provide an means to override any of these values via an environment variable:
#
# $ASCLDB_PORT
# $ASCLDB_USER
# $ASCLDB_HOST
#
if "ASCLDB_PORT" in os.environ:
	db_config['port'] = os.environ["ASCLDB_PORT"]
if "ASCLDB_USER" in os.environ:
	db_config['user'] = os.environ["ASCLDB_USER"]
if "ASCLDB_HOST" in os.environ:
	db_config['host'] = os.environ["ASCLDB_HOST"]
if "ASCLDB_PASSWORD" in os.environ:
	db_config['password'] = os.environ["ASCLDB_PASSWORD"]

# =====================================================================
# No need to modify anything below this line.
# =====================================================================

# Build connection string with URL-encoded password
# This handles special characters in passwords (like {, }, =, ~, etc.)
database_connection_string = 'mysql://{0[user]}:{0[password_encoded]}@{0[host]}:{0[port]}/{0[database]}'.format(db_config)

logger.info(f"Trillian2DBConnection: Configured to connect to {db_config['host']}:{db_config['port']}/{db_config['database']}")
logger.debug(f"Trillian2DBConnection: Connection string: mysql://{db_config['user']}:***@{db_config['host']}:{db_config['port']}/{db_config['database']}")

# This allows the file to be 'import'ed any number of times, but attempts to
# connect to the database only once.
try:
	logger.debug("Trillian2DBConnection: Attempting to get existing DatabaseConnection singleton")
	db = DatabaseConnection() # fails if connection not yet made.
	logger.info("Trillian2DBConnection: Using existing DatabaseConnection singleton")
except:
	logger.info("Trillian2DBConnection: Creating new DatabaseConnection singleton")
	# NOTE: Metadata caching disabled during active development
	db = DatabaseConnection(database_connection_string=database_connection_string, cache_name=None)
	logger.info("Trillian2DBConnection: DatabaseConnection created successfully")

engine = db.engine
metadata = db.metadata
Session = scoped_session(sessionmaker(engine, autocommit=False))

