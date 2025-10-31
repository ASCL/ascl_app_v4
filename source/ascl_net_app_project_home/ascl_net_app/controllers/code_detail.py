#!/usr/bin/python

import flask
from flask import render_template, abort

code_detail_page = flask.Blueprint("code_detail_page", __name__)

@code_detail_page.route("/<path:ascl_id>", methods=['GET'])
def code_detail(ascl_id):
	# Only handle ASCL ID format (YYMM.NNN)
	import re
	if not re.match(r'^\d{4}\.\d{3}$', ascl_id):
		from flask import abort
		abort(404)
	''' Show detailed information for a specific code. '''
	from ascl_core.database.connections import Trillian2Connection as db
	import ascl_core.database.ascldb.ASCLModelClasses as ascldb

	# Get database session
	session = db.Session()

	# The ASCL ID may come in formatted (e.g., "1404.008") or as stored in DB
	# Try both: exact match first, then try querying with the ascl_id as-is
	code = session.query(ascldb.ASCLCode).filter_by(ascl_id=ascl_id).first()

	if not code:
		abort(404)

	# Get related data (keywords, links, etc.)
	# keywords = code.keywords if hasattr(code, 'keywords') else []

	templateDict = {
		'code': code,
	}

	return render_template("code_detail.html", **templateDict)
