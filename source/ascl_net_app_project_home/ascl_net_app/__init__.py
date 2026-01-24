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
	from .controllers.browse import browse_page
	from .controllers.search import search_page
	from .controllers.code_detail import code_detail_page
	from .controllers.about import about_page
	from .controllers.news import news_page
	from .controllers.admin import admin_page
	from .controllers.dashboard import dashboard_page
	from .controllers.submit_code import submit_code_page

	app.register_blueprint(index_page)
	app.register_blueprint(browse_page)
	app.register_blueprint(search_page)
	app.register_blueprint(about_page)
	app.register_blueprint(news_page)
	app.register_blueprint(admin_page)
	app.register_blueprint(dashboard_page)
	app.register_blueprint(submit_code_page)
	# Register code_detail_page LAST - it has a catch-all route
	app.register_blueprint(code_detail_page)

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

	# Determine which config file to load based on mode
	# When running with run_ascl_net_app.py --debug, we're in debug mode
	# When running with uvicorn, we're in production mode
	if app.debug:
		#
		# DEBUG MODE: Use default.cfg (already loaded above)
		# Optionally override with hostname-specific config
		#
		hostname = socket.gethostname()
		if "your_host" in hostname:
			server_config_file = _app_setup_utils.getConfigFile("your_host.cfg")
		else:
			# Already loaded default.cfg above, don't reload it
			server_config_file = None

	elif app.testing:
		#
		# TESTING MODE: Use default.cfg (already loaded above)
		#
		server_config_file = None

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
	elif not (app.debug or app.testing):
		# Only warn in production mode if no config file found
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

	# Set up logging for the application and ascl_core module
	from .utilities.logging_config import setup_logging
	setup_logging(app)

	# Change the implementation of "decimal" to a C-based version (much! faster)
	try:
		import cdecimal
		sys.modules["decimal"] = cdecimal
	except ImportError:
		pass # not available

	if app.config["USING_SQLALCHEMY"]:

		# Database connection handled by ascl_core.database.connections.Trillian2DBConnection
		# Controllers import: from ascl_core.database.connections import Trillian2DBConnection as db

		app.logger.info("Database connection: ascl_core.database.connections.Trillian2DBConnection (dm-dbcore)")

		# PostgreSQL-specific setup
		db_type = app.config.get("DB_TYPE", "mysql").lower()
		if app.config.get("USING_POSTGRESQL"):
			db_type = "postgresql"
		elif app.config.get("USING_MYSQL"):
			db_type = "mysql"

		if db_type == "postgresql":
			_app_setup_utils.setupJSONandDecimal()

		@app.teardown_appcontext
		def shutdown_session(exception=None):
			"""
			Remove database sessions at the end of each request or when the app shuts down.
			Trillian2DBConnection uses a scoped_session which needs cleanup per request.
			Ref: http://flask.pocoo.org/docs/patterns/sqlalchemy/
			"""
			from ascl_core.database.connections import Trillian2DBConnection as db
			db.Session.remove()

	# Register all paths (URLs) available.
	register_blueprints(app=app)

	# Register all Jinja filters in the file.
	app.register_blueprint(jinja_filters.blueprint)

	return app


