#!/usr/bin/python

from __future__ import division
from __future__ import print_function

import sys
import socket
import os

from flask import Flask, g

from . import jinja_filters
from . import _app_setup_utils
from .utilities.color_print import print_warning, print_error, print_info, yellow_text, green_text, red_text

# ================================================================================

def register_blueprints(app=None):
	'''
	Register the code associated with each URL paths. Manually add each new
	controller file you create here.
	'''
	from .controllers.index import index_page
	#from .controllers.controller1 import xxx

	app.register_blueprint(index_page)
	#app.register_blueprint(xxx)

# ================================================================================

# place this here so that the app can be universally called (yes, a global)
app = None

def create_app(debug=False): #, conf=dict()):
	
	global app
	app = Flask(__name__) # creates the app instance using the name of the module
	app.debug = debug

	# --------------------------------------------------
	# Read configuration files.
	# -------------------------
	# You can define a different configuration
	# file based on the host the app is running on.
	#
	# Configuration files are located in the "configuration_files" directory.
	# -----------------------------------------------------------------------
	server_config_file = None
	
	# Always load the default configuration - values that need to be overridden
	# should be contained in other configuration files (see logic below).
	default_config_file = _app_setup_utils.getConfigFile("default.cfg") # returns the file path
	app.config.from_pyfile(default_config_file) # reads values into app.config dictionary

	if app.debug:
		#
		# Look for configuration file by host name (for example, can modify to taste).
		#
		hostname = socket.gethostname()		
		if "your_host" in hostname:
			server_config_file = _app_setup_utils.getConfigFile("your_host.cfg")
		else:
			server_config_file = _app_setup_utils.getConfigFile("default.cfg") # default
		
	elif app.testing:
		#
		# Get config file when testing. Can add extra logic here to test multiple configurations,
		# e.g. a testing configuration file.
		#
		server_config_file = _app_setup_utils.getConfigFile("default.cfg") # default
		
	else:
		#
		# Must be in production mode (running under Uvicorn).
		# Load production configuration file.
		#
		# For production-specific configuration, you can:
		# 1. Set environment variable: export FLASK_CONFIG=production.cfg
		# 2. Or specify config file when launching Uvicorn (see README.md)
		#
		config_from_env = os.environ.get('FLASK_CONFIG')
		if config_from_env:
			server_config_file = _app_setup_utils.getConfigFile(config_from_env)
		else:
			# Default to production config if it exists, otherwise use default
			try:
				server_config_file = _app_setup_utils.getConfigFile("production.cfg")
			except:
				server_config_file = _app_setup_utils.getConfigFile("default.cfg")

	if server_config_file:
		print(green_text("Loading config file: "), yellow_text(server_config_file))
		app.config.from_pyfile(server_config_file)
	else:
		print(yellow_text("Warning: No server configuration file found."))

	# Override database credentials from environment variables if set
	if os.environ.get('ASCLDB_USER'):
		app.config['DB_USER'] = os.environ.get('ASCLDB_USER')
		if app.debug:
			print_info(f"Using database user from environment: {app.config['DB_USER']}")

	if os.environ.get('ASCLDB_PASSWORD'):
		app.config['DB_PASSWORD'] = os.environ.get('ASCLDB_PASSWORD')
		if app.debug:
			print_info("Using database password from environment variable")

	# -----------------------------
	# Perform app setup below here.
	# -----------------------------
	
	if app.debug:
		#print("{0}App '{1}' created.{2}".format('\033[92m', __name__, '\033[0m'))
		print_info("Application '{0}' created.".format(__name__))
	else:
		if app.config["USING_SENTRY"]:
			_app_setup_utils.setupSentry(app, dsn=sentryDSN)

	# Change the implementation of "decimal" to a C-based version (much! faster)
	try:
		import cdecimal
		sys.modules["decimal"] = cdecimal
	except ImportError:
		pass # not available

	if app.config["USING_SQLALCHEMY"]:

		# Database-specific setup
		db_type = app.config.get("DB_TYPE", "mysql").lower()

		# For backwards compatibility
		if app.config.get("USING_POSTGRESQL"):
			db_type = "postgresql"
		elif app.config.get("USING_MYSQL"):
			db_type = "mysql"

		if db_type == "postgresql":
			# PostgreSQL-specific setup
			_app_setup_utils.setupJSONandDecimal()

			# This "with" is necessary to prevent exceptions of the form:
			#    RuntimeError: working outside of application context
			#    (i.e. the app object doesn't exist yet - being created here) (?)

			with app.app_context():
				from .model.databasePostgreSQL import db

		elif db_type == "mysql":
			# MySQL-specific setup (if needed)
			# MySQL generally works out of the box with SQLAlchemy
			pass

		# Establish database connection
		#
		from .model.database import Database
		database = Database()
		database.connect(flask_app=app)

		@app.teardown_appcontext
		def shutdown_session(exception=None):
			'''
			Enable Flask to automatically remove database schema at the end of the request.
			Also removes the session at app shutdown.
			Ref: http://flask.pocoo.org/docs/patterns/sqlalchemy/
			'''
			if hasattr(g, 'my_session'): # defined in model.database.py
				g.my_session.remove()

	# Register all paths (URLs) available.
	register_blueprints(app=app)

	# Register all Jinja filters in the file.
	app.register_blueprint(jinja_filters.blueprint)

	return app
	

	
	
