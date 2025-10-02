#!/usr/bin/python
# -*- coding: UTF-8 -*-

import os
from socket import gethostname

import sqlalchemy
from sqlalchemy.orm import sessionmaker, scoped_session

from ..DatabaseConnection import DatabaseConnection
#from ..pgutils import read_password_from_pgpass

# ---------------------------------------------------------------------
# Fill in database connection information here.
# Note!! The password is read from ~/.my.cnf (MySQL) or ~/.pgpass (PostgreSQL)
# 		 so the source file can be checked into public version control.
# ---------------------------------------------------------------------
db_config = {
	'user'     : 'ascl_db',  	    # specify the database username
	'password' : '',     			# the database password for that user -> '' reads from ~/.my.cnf or ~/.pgpass
	'database' : 'ascl_db',			# the name of the database
	'host'     : 'localhost',		# your hostname, "localhost" if on your own machine
	'port'     : 3307				# ASCL MySQL Docker: 3307, PostgreSQL default: 5432
}
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

# Empty password string will cause MySQL to read from ~/.my.cnf
# For PostgreSQL, empty password will read from ~/.pgpass
#
# If password is empty, that's intentional (use credential files)
#
# Note: When connecting to MySQL on a non-standard port, we need to ensure
# TCP/IP connection is used (not Unix socket). The connection string will
# use TCP when a port is specified.

database_connection_string = 'mysql://{0[user]}:{0[password]}@{0[host]}:{0[port]}/{0[database]}?charset=utf8mb4'.format(db_config)

# This allows the file to be 'import'ed any number of times, but attempts to
# connect to the database only once.
try:
	db = DatabaseConnection() # fails if connection not yet made.
except:
	db = DatabaseConnection(database_connection_string=database_connection_string, cache_name="ascldb_metadata_cache.pickle")

engine = db.engine
metadata = db.metadata
Session = scoped_session(sessionmaker(engine, autocommit=False))

