#!/usr/bin/env python

__author__ = "Demitri Muna"

'''
Classes to add support for PostrgeSQL geometric data types that SQLAlchemy doesn't natively support.

USAGE:

* PGPoint and PGPolygon are to be used to map columns in the database of those types.

-----------------------------------------

Example usage, e.g. at the top of a ModelClasses file:

from sqlalchemy.dialects.postgresql import base as pg
from .PGGeometry import PGPoint
pg.ischema_names['point'] = PGPoint

This will assign the PGPoint object type for all fields of type 'point'.

For illustrative purposes in the comments below, assume a column defined as:
CREATE TABLE some_table (
	pt point,
	pg polygon
);
'''

import re
import ast # Abstract Syntax Trees / https://docs.python.org/3.7/library/ast.html
import numpy as np
import sqlalchemy.types as types
from cornish import ASTCircle, ASTPolygon, ASTICRSFrame
#from psycopg2.extensions import register_adapter, AsIs
		
class PGASTCircle(types.UserDefinedType):
	'''
	Class to represent PostgreSQL "circle" datatype.
	
	https://www.postgresql.org/docs/current/datatype-geometric.html#DATATYPE-CIRCLE
	
	'''
	def bind_processor(self, dialect):
		'''
		Return a function that performs the conversion from the
		provided object to a form that PostgreSQL can understand.
		
		To insert a value into a 'circle' field:
			INSERT INTO some_table (pt) VALUES (CIRCLE(POINT(1,2),3));
		'''
		def process(value):
			if value is None:
				return value
			#xy, radius = value.split(",")
			# value is an ASTCircle object
			return "CIRCLE(POINT({0[0]},{0[1]}),{1})".format(value.center, value.radius)
		return process
		
	def result_processor(self, dialect, coltype):
		'''
		Return a function that converts the value that comes from the
		database to a Python object.
		'''
		def process(value):
			if value is None:
				return None
			#
			# value from db will be a string of the form (without the quotes):
			#
			#   "<(82.66287263711133,2.1669098446685364),0.13926999141057494>"
			#
			#point_values = value.split(",") # not sure if there will be surrounding quotes
			#return (float(point_values[0]), float(point_values[1]))
			#return np.array(ast.literal_eval(value)) # https://docs.python.org/3.7/library/ast.html#ast.literal_eval
			for c in "<>()":
				value = value.replace(c, "")
			x,y,radius = [float(x) for x in value.split(",")]
			return ASTCircle(frame=ASTICRSFrame(), center=[x,y], radius=radius)
		return process

class PGASTPolygon(types.UserDefinedType):
	'''
	Class to represent PostgreSQL "circle" datatype.
	
	https://www.postgresql.org/docs/current/datatype-geometric.html#DATATYPE-POLYGON
	
	'''
	def get_col_spec(self):
		return "POLYGON"

	def bind_processor(self, dialect):
		'''
		Return a function that performs the conversion from the
		provided object to a form that PostgreSQL can understand.
		
		To insert a value into a 'polygon' field:
			INSERT INTO some_table (pt) VALUES (POLYGON('((0,0),(0,1),(1,1),(0,1))'));
		'''
		def process(value):
			if value is None:
				return value
			# value is an ASTPolygon object
			#points = list()
			#for p in value.points:
			#	points.append(f"({p[0]},{p[1]})")
			#return f"'({','.join(points)})'::POLYGON"
			return "'{}'::POLYGON".format(str(value.tolist()).replace("[","(").replace("]",")"))
		return process
		
	def result_processor(self, dialect, coltype):
		'''
		Return a function that converts the value that comes from the
		database to a Python object.
		'''
		def process(value):
			if value is None:
				return None
			#
			# value from db will be a string of the form (without the quotes):
			#
			#   "'((0,0),(0,1),(1,1),(1,0))'"
			#
			points = np.array(ast.literal_eval(value))
			return ASTPolygon(frame=ASTICRSFrame(), points=points)
		return process
		
	
	
