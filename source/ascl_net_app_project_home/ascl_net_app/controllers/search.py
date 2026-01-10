#!/usr/bin/python

import flask
from flask import request, render_template, current_app
from sqlalchemy import or_
import logging

search_page = flask.Blueprint("search_page", __name__)
logger = logging.getLogger(__name__)

def search_mysql(query_string, published_only=True, page=1, per_page=20):
	"""
	Fallback MySQL LIKE search with pagination.

	Args:
		query_string: Search query
		published_only: Only return published codes
		page: Page number (1-indexed)
		per_page: Results per page

	Returns:
		tuple: (results list, total_count)
	"""
	from ascl_core.database.connections import Trillian2DBConnection as db
	from ascl_core.database.ascldb.ASCLModelClasses import ASCLCode
	session = db.Session()

	# Search in title, abstract, and credit (authors)
	search_pattern = f"%{query_string}%"

	base_query = session.query(ASCLCode).filter(
		or_(
			ASCLCode.title.like(search_pattern),
			ASCLCode.abstract.like(search_pattern),
			ASCLCode.credit.like(search_pattern)
		)
	)

	if published_only:
		base_query = base_query.filter(ASCLCode.published == 1)

	# Get total count
	total_count = base_query.count()

	# Apply pagination
	offset = (page - 1) * per_page
	results = base_query.order_by(
		ASCLCode.time_added.desc(),
		ASCLCode.pk.desc()
	).offset(offset).limit(per_page).all()

	return results, total_count

@search_page.route("/search", methods=['GET'])
def search():
	"""
	Search codes by name, description, or author.

	Uses Typesense if available, falls back to MySQL LIKE search.

	Query parameters:
		q: Search query string
		page: Page number (default: 1)
		per_page: Results per page (default: 20)
	"""
	query_string = request.args.get('q', '').strip()
	page = int(request.args.get('page', 1))
	per_page = int(request.args.get('per_page', 20))

	templateDict = {
		'query': query_string,
		'results': [],
		'result_count': 0,
		'page': page,
		'per_page': per_page,
		'search_method': None,  # 'typesense' or 'mysql'
		'search_time_ms': 0,
		'typesense_available': False
	}

	if not query_string:
		return render_template("search.html", **templateDict)

	# Try Typesense first
	from ascl_net_app.services.typesense_client import get_typesense_client

	typesense = get_typesense_client()
	typesense_results = None

	if typesense.enabled and typesense.is_healthy():
		logger.info(f"Using Typesense for search: '{query_string}'")
		typesense_results = typesense.search(
			query=query_string,
			query_by='title,abstract,credit',
			filter_by='published:1',
			per_page=per_page,
			page=page
		)

	# Use Typesense results if available
	if typesense_results:
		templateDict['search_method'] = 'typesense'
		templateDict['typesense_available'] = True
		templateDict['result_count'] = typesense_results['found']
		templateDict['search_time_ms'] = typesense_results.get('search_time_ms', 0)

		# Convert Typesense hits to code objects
		# For now, we'll need to fetch from database by pk
		from ascl_core.database.connections import Trillian2DBConnection as db
		from ascl_core.database.ascldb.ASCLModelClasses import ASCLCode
		session = db.Session()

		# Extract PKs from Typesense results
		pks = [hit['document']['pk'] for hit in typesense_results['hits']]

		if pks:
			# Fetch codes in the order returned by Typesense
			codes_dict = {code.pk: code for code in session.query(ASCLCode).filter(ASCLCode.pk.in_(pks)).all()}
			results = [codes_dict[pk] for pk in pks if pk in codes_dict]
			templateDict['results'] = results
			templateDict['typesense_hits'] = typesense_results['hits']  # For highlighting
		else:
			templateDict['results'] = []

	else:
		# Fallback to MySQL
		logger.info(f"Using MySQL fallback for search: '{query_string}'")
		templateDict['search_method'] = 'mysql'
		templateDict['typesense_available'] = typesense.is_healthy()

		results, total_count = search_mysql(
			query_string,
			published_only=True,
			page=page,
			per_page=per_page
		)
		templateDict['results'] = results
		templateDict['result_count'] = total_count

	# Calculate pagination info
	import math
	total_pages = math.ceil(templateDict['result_count'] / per_page) if per_page > 0 else 1
	templateDict['total_pages'] = total_pages
	templateDict['start_result'] = ((page - 1) * per_page) + 1 if templateDict['result_count'] > 0 else 0
	templateDict['end_result'] = min(page * per_page, templateDict['result_count'])

	return render_template("search.html", **templateDict)

@search_page.route("/code/cs/<path:search_term>", methods=['GET'])
def credit_search(search_term):
	''' Credit search - search for codes by author name.

	Matches PHP v3: /code/cs/{search_term}
	Performs LIKE search on codes.credit field.
	'''
	from urllib.parse import unquote
	from html import unescape

	# Decode URL encoding and HTML entities (matches PHP: html_entity_decode(urldecode($search_term)))
	search_term = unescape(unquote(search_term))

	templateDict = {
		'search_term': search_term,
		'codes': [],
		'result_count': 0
	}

	# Get database session
	from ascl_core.database.connections import Trillian2DBConnection as db
	from ascl_core.database.ascldb.ASCLModelClasses import ASCLCode
	session = db.Session()

	# Search for codes with matching credit (author name)
	# Matches PHP: $this->db->like("credit",$search_term);
	search_pattern = f"%{search_term}%"

	results = (
		session.query(ASCLCode)
		.filter(ASCLCode.credit.like(search_pattern))
		.filter(ASCLCode.published == 1)  # Only published codes
		.order_by(ASCLCode.time_added.desc())
		.limit(100)  # Matches PHP limit
		.all()
	)

	templateDict['codes'] = results
	templateDict['result_count'] = len(results)

	return render_template("credit_search.html", **templateDict)

@search_page.route("/code/cs_submit", methods=['POST'])
def credit_search_submit():
	''' Credit search form submission - redirect to GET route.

	Matches PHP v3: /code/cs_submit
	Accepts form POST and redirects to /code/cs/{search_term}
	'''
	from flask import redirect
	from urllib.parse import quote

	search_term = request.form.get('search', '').strip()

	if not search_term:
		# No search term provided, redirect to browse all
		return redirect('/code/all')

	# Redirect to GET route with URL-encoded search term
	return redirect(f'/code/cs/{quote(search_term)}')
