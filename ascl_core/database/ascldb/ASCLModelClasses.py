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

from dm_dbcore import DatabaseConnection
from dm_dbcore import DBTYPE_POSTGRESQL, DBTYPE_MYSQL, DBTYPE_SQLITE

dbc = DatabaseConnection()

class Base(DeclarativeBase):
	metadata = dbc.metadata

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
# Note: For PostgreSQL, tables are in schema 'ascldb'.
# For MySQL, tables are directly in the database (no schema prefix needed).
table_key = 'ascldb.codes' if dbc.database_type == DBTYPE_POSTGRESQL else 'codes'
#
# if table_key in dbc.metadata.tables:
	# need_to_update_metadata_cache = False
# else:
	# # Reflect tables from database
	# # PostgreSQL: reflect from 'ascldb' schema
	# # MySQL: reflect from current database (no schema parameter)
	# if dbc.database_type == DBTYPE_POSTGRESQL:
	# 	dbc.metadata.reflect(dbc.engine, schema=db_schema)
	# else:
	# 	dbc.metadata.reflect(dbc.engine)
	# need_to_update_metadata_cache = True

need_to_update_metadata = table_key not in Base.metadata

# See DatabaseConnection file for central location to set up any needed adapters.

# ========================
# Define database classes
# ========================
#
# Set schema based on database type
# PostgreSQL: tables are in 'ascldb' schema
# MySQL: tables are in current database (no schema)
db_schema = 'ascldb' if dbc.database_type == DBTYPE_POSTGRESQL else None

# Note on metadata, reflection, and autoload.
# -------------------------------------------
# The "Base" class contains the Metadata object, specifically "Base.metadata".
# During the Table() calls below, SQLAlchemy first checks Base.metadata
# for the information on the table. If found, it returns it. If not,
# it will autoload from the database and add it to the Base.metadata object.
#

#@mapper_registry.mapped
class Change(Base):
	__table__ = Table('change', Base.metadata,
				      schema=db_schema, autoload_with=dbc.engine)

#@mapper_registry.mapped
class Link(Base):
	__table__ = Table('link', dbc.metadata,
					  schema=db_schema, autoload_with=dbc.engine)

#@mapper_registry.mapped
class ADSEntryNew(Base):
	__table__ = Table('ads_entries_new', dbc.metadata,
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
					  schema=db_schema, autoload_with=dbc.engine)

#@mapper_registry.mapped
class Keyword(Base):
	__table__ = Table('keywords', dbc.metadata,
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
class CISession(Base):
	__table__ = Table('ci_sessions', dbc.metadata,
					  schema=db_schema, autoload_with=dbc.engine)

# =========================
# Define relationships here
# =========================
# Note: If the relationship is not found, don't use the
#       "#@mapper_registry.mapped" decorator; instead go
#       back to subclassing from "Base".

# ---------------------------------------------------------
# 1. ASCLCode.aliases → ASCLCodeAlias (One-to-Many)
# ---------------------------------------------------------
# FK: code_aliases.code_id → codes.pk
# One code has many aliases
# Note: Using string-based primaryjoin because FK may not be reflected from MySQL
ASCLCode.aliases = relationship(
	"ASCLCodeAlias",
	primaryjoin="ASCLCode.pk == foreign(ASCLCodeAlias.code_id)",
	backref="code",
	cascade="save-update, merge",
	lazy="selectin"
)

# ---------------------------------------------------------
# 2. ASCLCode.keywords ↔ Keyword (Many-to-Many)
# ---------------------------------------------------------
# Via code_keywords junction table
# FKs: code_keywords.code_id → codes.pk, code_keywords.keyword_id → keywords.id
ASCLCode.keywords = relationship(
	"Keyword",
	secondary="code_keywords",
	primaryjoin="ASCLCode.pk == code_keywords.c.code_id",
	secondaryjoin="Keyword.id == code_keywords.c.keyword_id",
	backref="ascl_codes",
	lazy="selectin"
)

# ---------------------------------------------------------
# 3. ASCLCode.ads_entries → ADSEntryNew (One-to-Many)
# ---------------------------------------------------------
# FK: ads_entries_new.code_pk → codes.pk
# One code has many ADS entries
# NOTE: Using lambda to delay evaluation until tables are loaded
ASCLCode.ads_entries = relationship(
	"ADSEntryNew",
	primaryjoin=lambda: ASCLCode.__table__.c[list(ASCLCode.__table__.primary_key.columns.keys())[0]] == ADSEntryNew.__table__.c.code_pk,
	foreign_keys=lambda: [ADSEntryNew.__table__.c.code_pk],
	backref="ascl_code",
	cascade="save-update, merge",
	lazy="selectin"
)

# ---------------------------------------------------------
# 4. ASCLCode.links → Link (One-to-Many)
# ---------------------------------------------------------
# FK: link.code_pk → codes.pk
# One code has many links
ASCLCode.links = relationship(
	"Link",
	primaryjoin=lambda: ASCLCode.__table__.c[list(ASCLCode.__table__.primary_key.columns.keys())[0]] == Link.__table__.c.code_pk,
	foreign_keys=lambda: [Link.__table__.c.code_pk],
	backref="ascl_code",
	cascade="save-update, merge",
	lazy="selectin"
)

# ---------------------------------------------------------
# 5. ASCLCode.citefile_metadata → CitefileMetadata (One-to-One or One-to-Many)
# ---------------------------------------------------------
# FK: citefile_metadata.code_pk → codes.pk
# One code has one (or possibly many) citefile metadata record(s)
ASCLCode.citefile_metadata = relationship(
	"CitefileMetadata",
	primaryjoin=lambda: ASCLCode.__table__.c[list(ASCLCode.__table__.primary_key.columns.keys())[0]] == CitefileMetadata.__table__.c.code_pk,
	foreign_keys=lambda: [CitefileMetadata.__table__.c.code_pk],
	backref="ascl_code",
	cascade="save-update, merge",
	lazy="selectin",
	uselist=True  # Set to False if truly one-to-one
)

# ---------------------------------------------------------
# 6. ASCLCode.changes → Change (One-to-Many)
# ---------------------------------------------------------
# FK: change.code_pk → codes.pk
# One code has many change records
ASCLCode.changes = relationship(
	"Change",
	primaryjoin=lambda: ASCLCode.__table__.c[list(ASCLCode.__table__.primary_key.columns.keys())[0]] == Change.__table__.c.code_pk,
	foreign_keys=lambda: [Change.__table__.c.code_pk],
	backref="ascl_code",
	cascade="save-update, merge",
	lazy="selectin"
)

# ---------------------------------------------------------
# 7. ASCLCode.citations → Citation (One-to-Many)
# ---------------------------------------------------------
# FK: citations.code_pk → codes.pk
# NOTE: entry_asclid column was removed in Step 16 of DB_UPGRADE_PLAYBOOK
# All joins now use code_pk (integer FK) instead of ascl_id (varchar)
ASCLCode.citations = relationship(
	"Citation",
	primaryjoin=lambda: ASCLCode.__table__.c[list(ASCLCode.__table__.primary_key.columns.keys())[0]] == Citation.__table__.c.code_pk,
	foreign_keys=lambda: [Citation.__table__.c.code_pk],
	backref="ascl_code",
	cascade="save-update, merge",
	lazy="selectin"
)


# ---------------------------------------------------------
# Test that all relations/mappings are self-consistent.
# ---------------------------------------------------------
#
from sqlalchemy.orm import configure_mappers
try:
	configure_mappers()
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

# Write metadata cache if caching is enabled and cache doesn't exist
# NOTE: Metadata caching disabled during active development
# if dbc.metadataCache is not None and not dbc.metadataCache.cachePath.exists():
# 	assert len(Base.metadata.tables) > 0
# 	dbc.metadataCache.write(metadata=Base.metadata)
