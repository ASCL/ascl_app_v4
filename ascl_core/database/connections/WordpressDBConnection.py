#!/usr/bin/python
# -*- coding: UTF-8 -*-

import os
import logging

from sqlalchemy.orm import sessionmaker, scoped_session

from dm_dbcore import DatabaseConnection

logger = logging.getLogger("WordpressDBConnection logger")

# ---------------------------------------------------------------------
# WordPress database connection info.
# Defaults match the dev Docker MySQL instance; password is read from
# ~/.my.cnf when left blank.
# ---------------------------------------------------------------------
db_config = {
	'user'     : os.environ.get("WPDB_USER", "ascl_root"),
	'password' : os.environ.get("WPDB_PASSWORD", ""),  # empty -> read from ~/.my.cnf
	'database' : os.environ.get("WPDB_DATABASE", "ascl_wordpress"),
	'host'     : os.environ.get("WPDB_HOST", "localhost"),
	'port'     : os.environ.get("WPDB_PORT", 3307),
}

database_connection_string = 'mysql://{0[user]}:{0[password]}@{0[host]}:{0[port]}/{0[database]}'.format(db_config)

logger.info(
	f"WordpressDBConnection: {db_config['host']}:{db_config['port']}/{db_config['database']} (user={db_config['user']})"
)

try:
	logger.debug("WordpressDBConnection: Attempting to reuse DatabaseConnection singleton")
	db = DatabaseConnection()  # fails if connection not yet made
	logger.info("WordpressDBConnection: Using existing DatabaseConnection singleton")
except Exception:
	logger.info("WordpressDBConnection: Creating new DatabaseConnection singleton")
	db = DatabaseConnection(database_connection_string=database_connection_string, cache_name="wp_metadata_cache.pickle")
	logger.info("WordpressDBConnection: DatabaseConnection created successfully")

engine = db.engine
metadata = db.metadata
Session = scoped_session(sessionmaker(engine, autocommit=False))
