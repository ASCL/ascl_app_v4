#!/usr/bin/python

import os

import flask
from flask import current_app, render_template, send_from_directory, g

from ascl_net_app.model.database import Database
from ascl_core.database.ascldb.ASCLModelClasses import *

index_page = flask.Blueprint("index_page", __name__)

@index_page.route("/", methods=['GET'])
def index():
	''' Index page - shows recently added codes. '''
	from collections import OrderedDict

	templateDict = {}

	# Get database session
	database = Database()
	session = database.Session()

	# Get the 10 most recently added published codes
	# Matches PHP logic: where("time_added >", "00-00-00") and where("published", 1)
	# Note: Using IS NOT NULL instead of > '0000-00-00' to avoid MySQL strict mode issues
	recent_codes_query = (
		session.query(ASCLCode)
		.filter(ASCLCode.published == 1)                   # Only published codes
		.filter(ASCLCode.time_added.isnot(None))          # Valid dates only (not NULL)
		.order_by(ASCLCode.time_added.desc())
		.limit(10)
		.all()
	)

	# Group by date (YYYY-MM-DD) - matches PHP grouping logic
	records_by_date = OrderedDict()
	for code in recent_codes_query:
		# Extract date from datetime (assumes time_added is datetime or string)
		if isinstance(code.time_added, str):
			date_key = code.time_added[:10]  # First 10 chars: YYYY-MM-DD
		else:
			date_key = code.time_added.strftime('%Y-%m-%d')

		if date_key not in records_by_date:
			records_by_date[date_key] = []

		records_by_date[date_key].append(code)

	templateDict['records_by_date'] = records_by_date

	return render_template("index.html", **templateDict)

# This will provide the favicon for the whole site. Can be overridden for
# a single page with something like this on the page:
#    <link rel="shortcut icon" href="static/images/favicon.ico">
#
@index_page.route('/favicon.ico')
def favicon():
	static_images_dir = directory=os.path.join(current_app.root_path, 'static', 'images')
	return send_from_directory(static_images_dir, 'favicon.ico')

@index_page.route('/robots.txt')
def robots():
	robots_path = os.path.join(current_app.root_path, 'static')
	return send_from_directory(robots_path, "robots.txt")
