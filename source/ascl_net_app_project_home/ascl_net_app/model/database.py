#!/usr/bin/python

''' This file handles a database connection.

	Supports both MySQL and PostgreSQL databases. The database type is
	determined by the DB_TYPE configuration parameter.
'''

import logging
from flask import current_app as app, g
from sqlalchemy.orm import sessionmaker, scoped_session

from dm_dbcore import DatabaseConnection
from ..designpatterns import singleton

logger = logging.getLogger(__name__)

@singleton
class Database(object):

	def __init__(self):
		self.pool = None
		self.database_connection_string = None # can be set manually
		self._Session = None
		self.db_config = {}
		self.db = None # set in method "connect" below
		self.db_type = None

	def connect(self, flask_app):
		''' Connect to database using connection parameters in flask_app.config. '''

		# create database connection string
		#
		if self.database_connection_string is None:
			# read details from configuration
			try:
				self.db_config["host"]     = flask_app.config["DB_HOST"]
				self.db_config["database"] = flask_app.config["DB_DATABASE"]
				self.db_config["user"]     = flask_app.config["DB_USER"]
				self.db_config["password"] = flask_app.config.get("DB_PASSWORD", '')
				self.db_config["port"]     = flask_app.config["DB_PORT"]

				# Determine database type
				self.db_type = flask_app.config.get("DB_TYPE", "mysql").lower()

				# For backwards compatibility, check legacy flags
				if flask_app.config.get("USING_POSTGRESQL"):
					self.db_type = "postgresql"
				elif flask_app.config.get("USING_MYSQL"):
					self.db_type = "mysql"

			except KeyError as e:
				logger.error(f"Missing database configuration key: {e}")
				flask_app.logger.error(f"ERROR: Missing database configuration key: {e}")
				raise

			# Build connection string based on database type
			if self.db_type == "mysql":
				# MySQL connection string
				# Format: mysql://user:password@host:port/database
				# For mysqlclient driver, use 'mysql' prefix
				# For PyMySQL driver, use 'mysql+pymysql' prefix
				# When password is empty, omit it so mysqlclient falls back to ~/.my.cnf
				if self.db_config['password']:
					self.database_connection_string = 'mysql://{user}:{password}@{host}:{port}/{database}'.format(**self.db_config)
				else:
					self.database_connection_string = 'mysql://{user}@{host}:{port}/{database}'.format(**self.db_config)
				logger.info(f"Built MySQL connection string for {self.db_config['database']}")
				logger.debug(f"Connection params: user={self.db_config['user']}, host={self.db_config['host']}, port={self.db_config['port']}, database={self.db_config['database']}, password={'***' if self.db_config['password'] else 'EMPTY (will use ~/.my.cnf)'}")

			elif self.db_type == "postgresql":
				# PostgreSQL connection string
				# Format: postgresql://user:password@host:port/database
				# When password is empty, omit it so libpq falls back to ~/.pgpass
				if self.db_config['password']:
					self.database_connection_string = 'postgresql://{user}:{password}@{host}:{port}/{database}'.format(**self.db_config)
				else:
					self.database_connection_string = 'postgresql://{user}@{host}:{port}/{database}'.format(**self.db_config)
				logger.info(f"Built PostgreSQL connection string for {self.db_config['database']}")

			else:
				raise ValueError(f"Unsupported database type: {self.db_type}. Use 'mysql' or 'postgresql'")

			logger.info(f"Connecting to {self.db_type.upper()} database at {self.db_config['host']}:{self.db_config['port']}/{self.db_config['database']}")
			flask_app.logger.info(f"Connecting to {self.db_type.upper()} database at {self.db_config['host']}:{self.db_config['port']}/{self.db_config['database']}")

		# connect to database:
		logger.debug("Creating DatabaseConnection instance")
		self.db = DatabaseConnection(database_connection_string=self.database_connection_string)
		logger.info("Database connection established successfully")

	def pool(self, release):
		# NOTE: NOT IMPLEMENTED YET
		''' Return the pool of database connections for the database connected. '''
	
		# -----------------------------------
		# Database connection setup & methods
		# -----------------------------------
		# Ref: http://initd.org/psycopg/docs/module.html
		# Ref: http://packages.python.org/psycopg2/pool.html#module-psycopg2.pool
		# dsn = data source name
		
		if self.pool is None:
			
			db_info = {}
			#for key in self.config.options(""):
			#	db_info[key] = config.
		
		return self.pool
		
	def Session(self):
		''' Returns the SQLAlchemy Session base class. '''
		if self._Session is None:
			self._Session = scoped_session(sessionmaker(bind=self.db.engine, autocommit=False, autoflush=True))
		return self._Session
	
	def get_session(self):
		''' Place a new Session instance on the thread local global context "g". '''
		g.my_session = self.Session()
		return g.my_session

	
	### etc. ###
	
	## TODO: create a sample db file for PostgreSQL, SQLite, and SQLAlchemy