'''
ModelClasses file for schema "ascldb".
'''

import os
import sys
import pickle
import warnings

import sqlalchemy
from sqlalchemy import Column, Integer, PrimaryKeyConstraint, orm
from sqlalchemy import func # for aggregate, other functions

from sqlalchemy.schema import Table, MetaData
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import mapper, relationship, exc, column_property, validates
from sqlalchemy.orm.session import Session
from sqlalchemy.orm import registry

from ..DatabaseConnection import DatabaseConnection, DBTYPE_POSTGRESQL

dbc = DatabaseConnection()

# -----------------------------------------
# Suppress harmless warnings, e.g.
# 	"SAWarning: Skipped unsupported reflection of expression-based index image_bounding_circle_q3c_idx"
#
warnings.filterwarnings(action="ignore", message="Skipped unsupported reflection")

metadata_pickle_filename = "ModelClasses_ascl.pickle"

# ------------------------------------------
# # Load the cached metadata if it's available
# # ------------------------------------------
# # NOTE: delete the cached file if the database schema changes!!
# cache_path = os.path.join(os.path.expanduser("~"), ".sqlalchemy_cache")
# cached_metadata = None
# if os.path.exists(cache_path):
# 	try:
# 		with open(os.path.join(cache_path, metadata_pickle_filename), 'rb') as cache_file:
# 			cached_metadata = pickle.load(file=cache_file)
# 	except IOError:
# 		# cache file not found - no problem
# 		pass
# # ------------------------------------------

# check first (any) entry defined in this file
# Note: For PostgreSQL, tables are in schema 'ascldb'
# For MySQL, tables are directly in the database (no schema prefix needed)
table_key = 'ascldb.codes' if dbc.database_type == 'postgresql' else 'codes'

if table_key in dbc.metadata.tables:
	need_to_update_metadata_cache = False
else:
	# Reflect tables from database
	# PostgreSQL: reflect from 'ascldb' schema
	# MySQL: reflect from current database (no schema parameter)
	if dbc.database_type == 'postgresql':
		dbc.metadata.reflect(dbc.engine, schema=db_schema)
	else:
		dbc.metadata.reflect(dbc.engine)
	need_to_update_metadata_cache = True

# See DatabaseConnection file for central location to set up any needed adapters.

# ========================
# Define database classes
# ========================
#
# Set schema based on database type
# PostgreSQL: tables are in 'ascldb' schema
# MySQL: tables are in current database (no schema)
db_schema = 'ascldb' if dbc.database_type == 'postgresql' else None

#mapper_registry = dbc.mapper_registry

#Base = dbc.Base

class Base(DeclarativeBase):
    pass

#if dbc.metadataCache:
#	cached_metadata = dbc.metadataCache.metadata
#else:
#	cached_metadata = None
#if cached_metadata:
#	cached_metadata.bind = dbc.engine
#	Base.metadata = cached_metadata

# Note on metadata, reflection, and autoload.
# -------------------------------------------
# The "Base" class contains the Metadata object, specifically "Base.metadata".
# During the Table() calls below, SQLAlchemy first checks Base.metadata
# for the information on the table. If found, it returns it. If not,
# it will autoload from the database and add it to the Base.metadata object.
#

need_to_update_metadata = False

# @mapper_registry.mapped
# class ASCLForZenodoMatching2(Base):
	# __table__ = Table('ascl_for_zenodo_matching2', dbc.metadata,
	# 				  schema=db_schema, autoload_with=dbc.engine)
#
# @mapper_registry.mapped
# class ASCLForZenodoMatchingTwo(Base):
	# __table__ = Table('ascl_for_zenodo_matching_two', dbc.metadata,
	# 				  schema=db_schema, autoload_with=dbc.engine)
#
# @mapper_registry.mapped
# class ASCLForZenodoMatching(Base):
	# __table__ = Table('ascl_for_zenodo_matching', dbc.metadata,
	# 				  schema=db_schema, autoload_with=dbc.engine)

#@mapper_registry.mapped
class Change(Base):
	__table__ = Table('change', Base.metadata,
				      schema=db_schema, autoload_with=dbc.engine)

#@mapper_registry.mapped
class LinkNew(Base):
	__table__ = Table('links_new', dbc.metadata,
					  schema=db_schema, autoload_with=dbc.engine)

#@mapper_registry.mapped
class Link(Base):
	__table__ = Table('links', dbc.metadata,
					  schema=db_schema, autoload_with=dbc.engine)

#@mapper_registry.mapped
class ADSEntryNew(Base):
	__table__ = Table('ads_entries_new', dbc.metadata,
					  schema=db_schema, autoload_with=dbc.engine)

#@mapper_registry.mapped
class ADSEntry(Base):
	__table__ = Table('ads_entries', dbc.metadata,
					  schema=db_schema, autoload_with=dbc.engine)

#@mapper_registry.mapped
class CitefileMetadata(Base):
	__table__ = Table('citefile_metadata', dbc.metadata,
					  schema=db_schema, autoload_with=dbc.engine)

#@mapper_registry.mapped
class ASCLCodeAlias(Base):
	__table__ = Table('code_aliases', dbc.metadata,
					  schema=db_schema, autoload_with=dbc.engine)

#@mapper_registry.mapped
class ASCLCodeToKeyword(Base):
	__table__ = Table('code_keywords', dbc.metadata,
					  PrimaryKeyConstraint("code_id", "keyword_id", name="pk_code_keywords"),

					  # Column("code_id", Integer, primary_key=True),
					  # Column("keyword_id", Integer, primary_key=True),
					  extend_existing=True,
					  schema=db_schema, autoload_with=dbc.engine)

#@mapper_registry.mapped
class Keyword(Base):
	__table__ = Table('keywords', dbc.metadata,
					  schema=db_schema, autoload_with=dbc.engine)

#@mapper_registry.mapped
class CitationNew(Base):
	__table__ = Table('citations_new', dbc.metadata,
					  schema=db_schema, autoload_with=dbc.engine)

#@mapper_registry.mapped
class Citation(Base):
	__table__ = Table('citations', dbc.metadata,
					  schema=db_schema, autoload_with=dbc.engine)

#@mapper_registry.mapped
class ASCLCode(Base):
	__table__ = Table('codes', dbc.metadata,
					  schema=db_schema, autoload_with=dbc.engine)

#@mapper_registry.mapped
class User(Base):
	__table__ = Table('users', dbc.metadata,
					  schema=db_schema, autoload_with=dbc.engine)

#@mapper_registry.mapped
class Temp(Base):
	__table__ = Table('temp', dbc.metadata,
					  schema=db_schema, autoload_with=dbc.engine)

#@mapper_registry.mapped
class ClassicCitation(Base):
	__table__ = Table('classic_citations', dbc.metadata,
					  schema=db_schema, autoload_with=dbc.engine)

#@mapper_registry.mapped
class CISession(Base):
	__table__ = Table('ci_sessions', dbc.metadata,
					  schema=db_schema, autoload_with=dbc.engine)

#@mapper_registry.mapped
class ASCLCodeBackup2(Base):
	__table__ = Table('codes_backup2', dbc.metadata,
					  schema=db_schema, autoload_with=dbc.engine)

# =========================
# Define relationships here
# =========================
# Note: If the relationship is not found, don't use the
#       "#@mapper_registry.mapped" decorator; instead go
#       back to subclassing from "Base".

# Example relationships (uncomment and adjust as needed):
#ASCLCode.codeAliases = relationship(ASCLCodeAlias, backref="code")
ASCLCode.keywords = relationship(Keyword,
								 secondary=ASCLCodeToKeyword.__table__,
								 #foreign_keys=[ASCLCodeToKeyword.code_id, ASCLCodeToKeyword.keyword_id],
								 primaryjoin=ASCLCodeToKeyword.code_id==ASCLCode.ascl_id,
								 secondaryjoin=ASCLCodeToKeyword.keyword_id==Keyword.id,
								 backref="asclCode")
#
# FitsFile.directoryPaths = relationship(DirectoryPath,
									   # secondary=FitsFileToDirectoryPath.__table__,
									   # #foreign_keys=[FitsFileToDirectoryPath.fits_file_pk, FitsFileToDirectoryPath.directory_path_pk],
									   # primaryjoin=FitsFileToDirectoryPath.fits_file_pk==FitsFile.pk,
									   # secondaryjoin=FitsFileToDirectoryPath.directory_path_pk==DirectoryPath.pk,
									   # backref="fitsFile")


# ---------------------------------------------------------
# Test that all relations/mappings are self-consistent.
# ---------------------------------------------------------
#
from sqlalchemy.orm import configure_mappers
try:
	configure_mappers()
#	raise Exception("")
except RuntimeError as error:
	print("""
An error occurred when verifying the relations between the database tables.
Most likely this is an error in the definition of the SQLAlchemy relations -
see the error message below for details.
""")
	print("Error type: %s" % sys.exc_info()[0])
	print("Error value: %s" % sys.exc_info()[1])
	print("Error trace: %s" % sys.exc_info()[2])
	sys.exit(1)

# assert CodesAliases.__table__.c.alias.references(Codes.__table__.c.id)

if dbc.metadataCache is None or need_to_update_metadata:
	assert len(dbc.metadata.tables) > 0
	dbc.metadataCache.write(metadata=dbc.metadata)
