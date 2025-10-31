#!/usr/bin/python

import flask
from flask import request, render_template
from sqlalchemy import or_

search_page = flask.Blueprint("search_page", __name__)

@search_page.route("/search", methods=['GET'])
def search():
	''' Search codes by name, description, or author. '''
	import ascl_core.database.ascldb.ASCLModelClasses as ascldb

	query_string = request.args.get('q', '').strip()

	templateDict = {
		'query': query_string,
		'results': [],
		'result_count': 0
	}

	if query_string:
		# Get database session
		from ascl_core.database.connections import Trillian2Connection as db
		session = db.Session()

		# Search in title, abstract, and credit (authors)
		search_pattern = f"%{query_string}%"

		results = session.query(ascldb.ASCLCode).filter(
			or_(
				ascldb.ASCLCode.title.like(search_pattern),
				ascldb.ASCLCode.abstract.like(search_pattern),
				ascldb.ASCLCode.credit.like(search_pattern)
			)
		).order_by(ascldb.ASCLCode.ascl_id.desc()).all()

		templateDict['results'] = results
		templateDict['result_count'] = len(results)

	return render_template("search.html", **templateDict)
