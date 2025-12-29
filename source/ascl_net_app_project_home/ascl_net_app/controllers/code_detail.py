#!/usr/bin/python

import flask
from flask import render_template, abort
import re
from sqlalchemy import text

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

	def _parse_php_serialized_list(value):
		"""Return a list of strings from a PHP-serialized array or simple string."""
		if not value:
			return []
		if isinstance(value, bytes):
			value = value.decode(errors="ignore")

		# Common case: PHP-serialized array of strings such as a:2:{i:0;s:53:"http://...";i:1;s:...;}
		if isinstance(value, str) and value.strip().startswith("a:"):
			matches = re.findall(r'"([^"]+)"', value)
			if matches:
				return matches

		# Fallback: split on whitespace/commas/semicolons to catch simple multi-value strings
		if isinstance(value, str):
			parts = re.split(r"[\\s,;]+", value.strip())
			return [p for p in parts if p]

		return []

	# Increment view count and reflect updated total for display; failure shouldn't break page rendering.
	view_count = code.views or 0
	try:
		with db.engine.begin() as conn:
			conn.execute(text("UPDATE codes SET views = views + 1 WHERE pk = :pk"), {"pk": code.pk})
		view_count = view_count + 1
	except Exception:
		view_count = code.views or 0

	# Get related data (keywords, links, etc.)
	# keywords = code.keywords if hasattr(code, 'keywords') else []
	site_links = _parse_php_serialized_list(getattr(code, "site_list", None))
	described_in_links = _parse_php_serialized_list(getattr(code, "described_in", None))
	used_in_links = _parse_php_serialized_list(getattr(code, "used_in", None))

	templateDict = {
		'code': code,
		'site_links': site_links,
		'described_in_links': described_in_links,
		'used_in_links': used_in_links,
		'view_count': view_count,
	}

	return render_template("code_detail.html", **templateDict)
