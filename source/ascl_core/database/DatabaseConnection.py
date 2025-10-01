#!/usr/bin/python
#

#from __future__ import annotations

import os
import pickle
import pathlib
import logging
from datetime import datetime
from contextlib import contextmanager

import sqlalchemy
from sqlalchemy import create_engine, MetaData, text
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import registry
from sqlalchemy.event import listens_for
from sqlalchemy.pool import Pool
#from sqlalchemy.ext.automap import automap_base

logger = logging.getLogger("DatabaseConnection logger")

@listens_for(Pool, 'connect')
def clearSearchPathCallback(dbapi_con, connection_record):
    '''
    When creating relationships across schema, SQLAlchemy
    has problems when you explicitly declare the schema in
    ModelClasses and it is found in search_path.

    The solution is to set the search_path to "$user" for
    the life of any connection to the database. Since there
    is no (or shouldn't be!) schema with the same name
    as the user, this effectively makes it blank.

    This callback function is called for every database connection.

    For the full details of this issue, see:
    http://groups.google.com/group/sqlalchemy/browse_thread/thread/88b5cc5c12246220

    dbapi_con - type: psycopg2._psycopg.connection
    connection_record - type: sqlalchemy.pool._ConnectionRecord
    '''
    cursor = dbapi_con.cursor()
    cursor.execute('SET search_path TO theres_no_schema_by_this_name_no_sir')
    dbapi_con.commit()

# ---------------------------------------------------------------------------------
# Database adapters
# =================
# Set up any adapters here, e.g. custom data type handling.
# These should be defined in a central location since they are to be defined once.
#
from .adapters import numpy_postgresql
from .adapters import numpy_sqlite
#from .adapters.pggeometry import PGPoint, PGPolygon

from sqlalchemy.dialects.postgresql import base as pg
#pg.ischema_names['circle'] = PGASTCircle

# -----------------------------------------
# This is to hide the warning:
# /usr/local/anaconda3/lib/python3.4/site-packages/sqlalchemy/dialects/postgresql/base.py:2505: SAWarning: Did not recognize type 'point' of column 'map'
# This defines the class PGPoint for any column of type 'point'.
# -----------------------------------------
from sqlalchemy.dialects.postgresql import base as pg
pg.ischema_names['point'] = PGPoint
pg.ischema_names['polygon'] = PGPolygon
#
# ---------------------------------------------------------------------------------

@contextmanager
def session_scope(db):
	"""Provide a transactional scope around a series of operations."""
	session = db.Session()
	try:
		yield session
		session.commit()
	except:
		session.rollback()
		raise
	finally:
		session.close()

class MetadataCache():
	'''
	This is a custom object used to write/read SQLAlchemy metadata to save time setting up 'autoload'ed tables.

	Each model classes file will define a filename for the cached metadata. If that file is found it will be
	loaded. If a schema.table being defined matches one found in the cache, it will be set to that class which
	will avoid the autoload. Otherwise, the cache will be set to 'None'. At the end of the file if the cache
	was 'None', the metadata will be written.

	Multiple model classes are supported, however, all MUST share the same metadata cache file if there
	are relationships between schemas. The metadata will be overwritten at the end of each file, but it will
	be the cumulative metadata gathered. If multiple files are written for the same database (e.g. one per
	schema), any relationships between schemas will not be properly defined if reloaded individually.

	No true anymore, but needs longer term testing. --> IMPORTANT NOTE!! The metadata is never compared to the database schema. Any time the database schema is updated,
	the caches must be deleted manually.

	A corresponding schema and table are required in the database for the check to see if the cache is stale.
	This is detailed at the bottom of this file.

	:param dbc: the `DatabaseConnection` object
	:param filename: the filename to be used for the cache
	:param path: the location to save the path, defaults to $HOME/.sqlalchemy_cache
	'''
	#def __init__(self, dbc:DatabaseConnection=None, filename:str=None, path=os.path.join(os.path.expanduser("~"),
	def __init__(self, dbc=None, filename:str=None, path=os.path.join(os.path.expanduser("~"), ".sqlalchemy_cache")):
		if filename is None:
			raise Exception("Please specify a filename for the metadata cache.")
		self.filename = filename
		self.cache_directory = path
		self.metadata = None
		self.databaseConnection = dbc

	@property
	def cachePath(self):
		''' Return the full filename and path of the cache. '''
		#return os.path.join(self.cache_directory, self.filename)
		return pathlib.Path(self.cache_directory) / self.filename

	def read(self):
		'''
		Read the cached metadata for this database connection.
		'''
		cache_path = self.cachePath

		if cache_path.exists(): #os.path.exists(cache_path):

			if self.cacheIsStale():
				self.cachePath.unlink
				self.metadata = None
			else:
				try:
					with open(cache_path, 'rb') as cache_file:
						self.metadata = pickle.load(file=cache_file)
						logger.info(f"Metadata cache read: {self.metadata.tables.keys()}")
				except IOError:
					return

	def cacheIsStale(self):
		'''
		Check if the schema has been modified since this cache was made.
		'''
		with self.databaseConnection.engine.connect() as connection:
			results = connection.execute(text("SELECT last_modified FROM metadata.schema_metadata"))
			for row in results:
				schema_last_modified = row[0] # -> datetime object

		# get last modification time of cache file
		file_timestamp = datetime.fromtimestamp(self.cachePath.stat().st_mtime)
		if file_timestamp < schema_last_modified:
			logger.info("Metadata cache is stale.")
		else:
			logger.info("Metadata cache is current.")
		return file_timestamp < schema_last_modified

	def write(self, metadata=None):
		'''
		Write the SQLAlchemy metadata to a pickle file.
		:param metadata:
		'''
		try:
			cache_dir = os.path.join(os.path.expanduser("~"), ".sqlalchemy_cache")
			if not os.path.exists(cache_dir):
				os.makedirs(cache_dir)
			with open(os.path.join(cache_dir, self.filename), 'wb') as cache_file:
				pickle.dump(metadata, cache_file)
			logger.info("Metadata cache written.")
			for t in metadata.tables.keys():
				logger.debug(f"    - {t}")
		except:
			# couldn't write the file for some reason
			pass


class DatabaseConnection(object):
	'''This class defines an object that makes a connection to a database.
	   The "DatabaseConnection" object takes as its parameter the SQLAlchemy
	   database connection string.

	   This class is best called from another class that contains the
	   actual connection information (so that it can be reused for different
	   connections).

	   This class implements the singleton design pattern. The first time the
	   object is created, it *requires* a valid database connection string.
	   Every time it is called via:

	   db = DatabaseConnection()

	   the same object is returned and contains the connection information.
	'''
	_singletons = dict()

	def __new__(cls, database_connection_string=None, cache_name=None):
		"""This overrides the object's usual creation mechanism."""

		if not cls in cls._singletons:
			assert database_connection_string is not None, "A database connection string must be specified!"
			cls._singletons[cls] = object.__new__(cls)

			# ------------------------------------------------
			# This is the custom initialization
			# ------------------------------------------------
			me = cls._singletons[cls] # just for convenience (think "self")

			me.database_connection_string = database_connection_string

			# change 'echo' to print each SQL query (for debugging/optimizing/the curious)
			me.engine = create_engine(me.database_connection_string,
									  pool_pre_ping=True,
									  future=True,
									  echo=False)#, echo_pool="debug") # pool_size=??

			me.metadata = MetaData()
			me.mapper_registry = registry()
			me.Base = me.mapper_registry.generate_base()
			me.Session = scoped_session(sessionmaker(me.engine))

			if cache_name:
				me.metadataCache = MetadataCache(dbc=me, filename=cache_name)
				me.metadataCache.read()
				if me.metadataCache.metadata is not None:
					me.metadata = me.metadataCache.metadata
			else:
				me.metadataCache = None

			# ------------------------------------------------

		return cls._singletons[cls]

'''
These metadata cache staleness check depends on a table called "metadata" in a schema with the
same name. This table contains a row that logs the last timestamp when the database schema changed.
The value is written via a trigger that calls a function on any database schema change event.
The code below sets this up.

-- Create the metadata schema/table.
CREATE SCHEMA metadata;
CREATE TABLE metadata.metadata (
   schema_last_modified TIMESTAMP
);
INSERT INTO metadata.metadata (schema_last_modified) VALUES (NOW());

-- Set up the trigger.
CREATE OR REPLACE FUNCTION metadata.notice_event() RETURNS event_trigger AS $$
DECLARE r RECORD;
BEGIN
	FOR r IN SELECT * FROM pg_event_trigger_ddl_commands() LOOP
		RAISE NOTICE 'caught % event on %', r.command_tag, r.object_identity;
	END LOOP;
	UPDATE metadata.metadata SET schema_last_modified=NOW();
END;
$$
LANGUAGE plpgsql;

CREATE EVENT TRIGGER tr_notice_alter_table
  ON ddl_command_end WHEN TAG IN (
	  'ALTER TABLE', 'ALTER FUNCTION', 'ALTER SCHEMA', 'ALTER TYPE', 'ALTER VIEW',
	  'CREATE FOREIGN TABLE', 'CREATE FUNCTION', 'CREATE SCHEMA', 'CREATE TABLE',
	  'CREATE TABLE AS', 'CREATE VIEW', 'DROP FOREIGN TABLE', 'DROP FUNCTION',
	  'DROP SCHEMA', 'DROP TABLE', 'DROP VIEW', 'IMPORT FOREIGN SCHEMA'
	  )
  EXECUTE PROCEDURE metadata.notice_event();

-- Command to delete the trigger.
DROP EVENT TRIGGER tr_notice_alter_table;
'''








