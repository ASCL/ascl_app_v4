#!/usr/bin/python

import flask
from flask import request, render_template, current_app, jsonify
from sqlalchemy import or_
import logging

search_page = flask.Blueprint("search_page", __name__)
logger = logging.getLogger(__name__)


def _normalize_suggest_query(raw_query):
	q = (raw_query or "").strip()
	if q.lower().startswith("ascl:"):
		q = q[5:].strip()
	return q


def _author_query_variants(search_term):
	"""Build a few author-query variants to improve matches across name formats."""
	import re

	raw = (search_term or "").strip()
	words = [w for w in re.split(r"[,\s]+", raw) if w]
	if not words:
		return []

	variants = [raw, " ".join(words)]

	# "Smith, John Kevin" -> "Smith J K"
	if "," in raw and len(words) > 1:
		surname = words[0]
		initials = " ".join(w[0] for w in words[1:] if w)
		if initials:
			variants.append(f"{surname} {initials}")

	# Also try reverse order if user typed "John Smith"
	if len(words) >= 2:
		variants.append(f"{words[-1]} {words[0]}")

	# De-duplicate while preserving order
	seen = set()
	unique = []
	for v in variants:
		key = v.strip().lower()
		if key and key not in seen:
			seen.add(key)
			unique.append(v.strip())
	return unique



def _search_credit_mysql(search_term, limit=100):
	"""Improved MySQL credit search: phrase + token scoring."""
	import re
	from sqlalchemy import case, func
	from ascl_net_app.model.database import Database
	from ascl_core.database.ascldb import ASCLModelClasses as ascldb

	session = Database().Session()
	query_raw = (search_term or "").strip()
	query_lower = query_raw.lower()
	words = [w for w in re.split(r"[,\s.]+", query_raw) if w]
	initials = [w[0].lower() for w in words[1:] if len(w) > 1]
	strong_words = [w for w in words if len(w) >= 2]

	ASCLCode = ascldb.ASCLCode
	credit_col = ASCLCode.credit
	conditions = [credit_col.ilike(f"%{query_raw}%")] if query_raw else []
	for w in strong_words:
		conditions.append(credit_col.ilike(f"%{w}%"))

	# Keep broad recall, then rank by phrase and token quality.
	base_query = session.query(ASCLCode).filter(ASCLCode.published == 1)
	if strong_words:
		# Require at least the first strong token to be present to reduce false positives.
		base_query = base_query.filter(credit_col.ilike(f"%{strong_words[0]}%"))
	if conditions:
		base_query = base_query.filter(or_(*conditions))

	exact_phrase = case((func.lower(credit_col) == query_lower, 1000), else_=0)
	starts_with_phrase = case((func.lower(credit_col).like(f"{query_lower}%"), 500), else_=0)
	contains_phrase = case((func.lower(credit_col).like(f"%{query_lower}%"), 300), else_=0)

	token_score = 0
	for w in words:
		token_score = token_score + case((func.lower(credit_col).like(f"%{w.lower()}%"), 120), else_=0)
	for init in initials:
		token_score = token_score + case((func.lower(credit_col).like(f"%{init}%"), 20), else_=0)

	return (
		base_query
		.order_by((exact_phrase + starts_with_phrase + contains_phrase + token_score).desc(), ASCLCode.time_added.desc())
		.distinct()
		.limit(limit)
		.all()
	)


def _author_suggestions_mysql(query_string, limit=8):
	"""Author name suggestions from MySQL credit strings."""
	from ascl_net_app.model.database import Database
	from ascl_core.database.ascldb.ASCLModelClasses import ASCLCode

	session = Database().Session()
	rows = (
		session.query(ASCLCode.credit)
		.filter(ASCLCode.published == 1)
		.filter(ASCLCode.credit.isnot(None))
		.filter(ASCLCode.credit.ilike(f"%{query_string}%"))
		.limit(300)
		.all()
	)

	q = query_string.lower()
	seen = set()
	out = []
	for (credit,) in rows:
		if not credit:
			continue
		for token in [t.strip() for t in credit.split(";") if t.strip()]:
			k = token.lower()
			if q not in k:
				continue
			if k in seen:
				continue
			seen.add(k)
			out.append(token)
			if len(out) >= limit:
				return out
	return out


def _search_mysql_suggestions(query_string, limit=8):
	"""Fallback suggestions when Typesense is unavailable or empty."""
	from ascl_net_app.model.database import Database
	from ascl_core.database.ascldb.ASCLModelClasses import ASCLCode
	from sqlalchemy import case, func

	session = Database().Session()
	query_lower = query_string.lower()

	exact_ascl = case((func.lower(ASCLCode.ascl_id) == query_lower, 1000), else_=0)
	prefix_ascl = case((func.lower(ASCLCode.ascl_id).like(f"{query_lower}%"), 500), else_=0)
	prefix_title = case((func.lower(ASCLCode.title).like(f"{query_lower}%"), 300), else_=0)
	contains_title = case((func.lower(ASCLCode.title).like(f"%{query_lower}%"), 100), else_=0)

	results = (
		session.query(ASCLCode)
		.filter(ASCLCode.published == 1)
		.filter(
			or_(
				ASCLCode.ascl_id.ilike(f"%{query_string}%"),
				ASCLCode.title.ilike(f"%{query_string}%"),
				ASCLCode.credit.ilike(f"%{query_string}%"),
			)
		)
		.order_by((exact_ascl + prefix_ascl + prefix_title + contains_title).desc(), ASCLCode.time_added.desc())
		.limit(limit)
		.all()
	)

	return [
		{
			"ascl_id": c.ascl_id,
			"title": c.title,
			"url": f"/code/v/{c.pk}" if c.ascl_id == "0000.000" else f"/{c.ascl_id}",
		}
		for c in results
	]

def search_mysql(query_string, published_only=True, page=1, per_page=20):
	"""
	MySQL search using FULLTEXT index with relevance ranking.

	Uses MATCH...AGAINST for relevance scoring, with boosts for exact
	and prefix title matches. Falls back to LIKE search if FULLTEXT
	index doesn't exist.

	Args:
		query_string: Search query
		published_only: Only return published codes
		page: Page number (1-indexed)
		per_page: Results per page

	Returns:
		tuple: (results list, total_count)
	"""
	from sqlalchemy import text
	from ascl_net_app.model.database import Database
	from ascl_core.database.ascldb.ASCLModelClasses import ASCLCode
	session = Database().Session()

	offset = (page - 1) * per_page
	published_filter = "AND published = 1" if published_only else ""

	# Try FULLTEXT search first
	try:
		# Count query
		count_sql = text(f"""
			SELECT COUNT(*) as cnt
			FROM codes
			WHERE MATCH(title, abstract, credit) AGAINST(:query IN NATURAL LANGUAGE MODE)
			{published_filter}
		""")
		total_count = session.execute(count_sql, {"query": query_string}).scalar()

		# Search query with relevance ranking
		# - Exact title match: +1000
		# - Title starts with query: +500
		# - Title contains query: +100
		# - FULLTEXT relevance score
		# - Views as popularity tiebreaker
		search_sql = text(f"""
			SELECT pk,
				MATCH(title, abstract, credit) AGAINST(:query IN NATURAL LANGUAGE MODE) AS relevance,
				CASE WHEN LOWER(title) = LOWER(:query) THEN 1000 ELSE 0 END AS exact_match,
				CASE WHEN LOWER(title) LIKE CONCAT(LOWER(:query), '%') THEN 500 ELSE 0 END AS prefix_match,
				CASE WHEN LOWER(title) LIKE CONCAT('%', LOWER(:query), '%') THEN 100 ELSE 0 END AS title_match
			FROM codes
			WHERE MATCH(title, abstract, credit) AGAINST(:query IN NATURAL LANGUAGE MODE)
			{published_filter}
			ORDER BY exact_match DESC, prefix_match DESC, title_match DESC, relevance DESC
			LIMIT :limit OFFSET :offset
		""")
		rows = session.execute(
			search_sql,
			{"query": query_string, "limit": per_page, "offset": offset}
		).fetchall()

		# Fetch full code objects in ranked order
		if rows:
			pks = [row.pk for row in rows]
			codes_dict = {code.pk: code for code in session.query(ASCLCode).filter(ASCLCode.pk.in_(pks)).all()}
			results = [codes_dict[pk] for pk in pks if pk in codes_dict]
		else:
			results = []

		return results, total_count

	except Exception as e:
		# FULLTEXT index may not exist - fall back to LIKE search
		logger.warning(f"FULLTEXT search failed, falling back to LIKE: {e}")
		return _search_mysql_like(session, query_string, published_only, page, per_page)


def _search_mysql_like(session, query_string, published_only=True, page=1, per_page=20):
	"""
	Fallback LIKE-based search when FULLTEXT index is unavailable.
	Uses CASE-based relevance scoring for better results than date ordering.
	"""
	from sqlalchemy import case, func
	from ascl_core.database.ascldb.ASCLModelClasses import ASCLCode

	search_pattern = f"%{query_string}%"
	query_lower = query_string.lower()

	base_query = session.query(ASCLCode).filter(
		or_(
			ASCLCode.ascl_id.ilike(search_pattern),
			ASCLCode.title.ilike(search_pattern),
			ASCLCode.abstract.ilike(search_pattern),
			ASCLCode.credit.ilike(search_pattern)
		)
	)

	if published_only:
		base_query = base_query.filter(ASCLCode.published == 1)

	# Get total count
	total_count = base_query.count()

	# Score-based ordering: title matches ranked higher
	exact_title = case(
		(func.lower(ASCLCode.title) == query_lower, 1000),
		else_=0
	)
	prefix_title = case(
		(func.lower(ASCLCode.title).like(f"{query_lower}%"), 500),
		else_=0
	)
	contains_title = case(
		(func.lower(ASCLCode.title).like(f"%{query_lower}%"), 100),
		else_=0
	)
	contains_abstract = case(
		(func.lower(ASCLCode.abstract).like(f"%{query_lower}%"), 10),
		else_=0
	)
	prefix_ascl = case(
		(func.lower(ASCLCode.ascl_id).like(f"{query_lower}%"), 800),
		else_=0
	)
	exact_ascl = case(
		(func.lower(ASCLCode.ascl_id) == query_lower, 1200),
		else_=0
	)

	# Apply pagination with relevance ordering
	offset = (page - 1) * per_page
	results = base_query.order_by(
		(exact_ascl + prefix_ascl + exact_title + prefix_title + contains_title + contains_abstract).desc(),
		ASCLCode.time_added.desc()
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
		'typesense_available': False,
		'mysql_fallback_reason': None,  # 'unavailable' or 'no_results'
	}

	if not query_string:
		return render_template("search.html", **templateDict)

	# Try Typesense first
	from ascl_net_app.services.typesense_client import get_typesense_client

	typesense = get_typesense_client()
	typesense_results = None

	typesense_available = typesense.enabled and typesense.is_healthy()
	if typesense_available:
		logger.info(f"Using Typesense for search: '{query_string}'")
		typesense_results = typesense.search(
			query=query_string,
			query_by='ascl_id,title,abstract,credit',
			query_by_weights='10,8,2,1',
			filter_by='published:1',
			per_page=per_page,
			page=page
		)

	# Use Typesense results if available
	if typesense_results and typesense_results.get('found', 0) > 0:
		templateDict['search_method'] = 'typesense'
		templateDict['typesense_available'] = True
		templateDict['result_count'] = typesense_results['found']
		templateDict['search_time_ms'] = typesense_results.get('search_time_ms', 0)

		# Convert Typesense hits to code objects
		# For now, we'll need to fetch from database by pk
		from ascl_net_app.model.database import Database
		from ascl_core.database.ascldb.ASCLModelClasses import ASCLCode
		session = Database().Session()

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

	elif typesense_results and typesense_results.get('found', 0) == 0 and not typesense.fallback_to_mysql:
		# Honor config: keep empty Typesense result set and do not fallback.
		templateDict['search_method'] = 'typesense'
		templateDict['typesense_available'] = True
		templateDict['result_count'] = 0
		templateDict['results'] = []

	else:
		# Fallback to MySQL
		logger.info(f"Using MySQL fallback for search: '{query_string}'")
		templateDict['search_method'] = 'mysql'
		templateDict['typesense_available'] = typesense_available
		templateDict['mysql_fallback_reason'] = 'no_results' if typesense_results and typesense_results.get('found', 0) == 0 else 'unavailable'

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


@search_page.route("/search/suggest", methods=['GET'])
def search_suggest():
	"""JSON type-ahead suggestions for code search."""
	query_string = _normalize_suggest_query(request.args.get('q', ''))
	try:
		limit = min(max(int(request.args.get('limit', 8)), 1), 20)
	except ValueError:
		limit = 8

	if len(query_string) < 2:
		return jsonify({
			"query": query_string,
			"suggestions": [],
			"method": None,
		})

	from ascl_net_app.services.typesense_client import get_typesense_client
	typesense = get_typesense_client()
	suggestions = []
	method = "mysql"

	typesense_available = typesense.enabled and typesense.is_healthy()
	if typesense_available:
		results = typesense.search(
			query=query_string,
			query_by='title,ascl_id,credit,abstract',
			query_by_weights='8,10,4,1',
			filter_by='published:1',
			sort_by='_text_match:desc,time_added:desc',
			prefix=True,
			per_page=limit,
			page=1
		)
		if results and results.get("hits"):
			method = "typesense"
			for hit in results["hits"]:
				doc = hit.get("document", {})
				ascl_id = doc.get("ascl_id")
				title = doc.get("title")
				if not ascl_id or not title:
					continue
				# Extract highlight snippet showing why this result matched
				snippet = ""
				hl = hit.get("highlight", {})
				# Prefer a non-title field so the user sees *why* it matched
				for field in ("abstract", "credit"):
					if field in hl and hl[field].get("snippet"):
						snippet = hl[field]["snippet"]
						break
				# Fall back to highlighted title if that's where the match is
				if not snippet and "title" in hl and hl["title"].get("snippet"):
					snippet = hl["title"]["snippet"]
				if ascl_id == "0000.000":
					# Typesense pk may not match the local database;
					# resolve by title against the local DB.
					from ascl_net_app.model.database import Database
					from sqlalchemy import text as sa_text
					local_row = Database().Session().execute(
						sa_text("SELECT pk FROM codes WHERE title = :title "
								"AND ascl_id = '0000.000' AND published = 1 LIMIT 1"),
						{"title": title},
					).first()
					url = f"/code/v/{local_row[0]}" if local_row else f"/search?q={title}"
				else:
					url = f"/{ascl_id}"
				suggestions.append({
					"ascl_id": ascl_id,
					"title": title,
					"url": url,
					"snippet": snippet,
				})

	if not suggestions:
		suggestions = _search_mysql_suggestions(query_string, limit=limit)
		method = "mysql"

	return jsonify({
		"query": query_string,
		"suggestions": suggestions,
		"method": method,
		"typesense_available": typesense_available,
	})


@search_page.route("/search/author_suggest", methods=['GET'])
def author_suggest():
	"""JSON type-ahead suggestions for author credit search."""
	query_string = request.args.get('q', '').strip()
	try:
		limit = min(max(int(request.args.get('limit', 8)), 1), 20)
	except ValueError:
		limit = 8

	if len(query_string) < 2:
		return jsonify({"query": query_string, "suggestions": [], "method": None})

	from ascl_net_app.services.typesense_client import get_typesense_client
	typesense = get_typesense_client()
	typesense_available = typesense.enabled and typesense.is_healthy()
	suggestions = []
	method = "mysql"

	if typesense_available:
		ts = typesense.search(
			query=query_string,
			query_by='credit',
			filter_by='published:1',
			prefix=True,
			num_typos=1,
			per_page=100,
			page=1
		)
		if ts and ts.get("hits"):
			q = query_string.lower()
			seen = set()
			for hit in ts["hits"]:
				credit = (hit.get("document", {}) or {}).get("credit", "") or ""
				for token in [t.strip() for t in credit.split(";") if t.strip()]:
					k = token.lower()
					if q not in k or k in seen:
						continue
					seen.add(k)
					suggestions.append(token)
					if len(suggestions) >= limit:
						break
				if len(suggestions) >= limit:
					break
			if suggestions:
				method = "typesense"

	if not suggestions:
		suggestions = _author_suggestions_mysql(query_string, limit=limit)
		method = "mysql"

	return jsonify({
		"query": query_string,
		"suggestions": suggestions,
		"method": method,
		"typesense_available": typesense_available,
	})

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
		'result_count': 0,
		'search_method': None,
	}

	# Try Typesense first for credit search.
	from ascl_net_app.services.typesense_client import get_typesense_client
	typesense = get_typesense_client()
	typesense_available = typesense.enabled and typesense.is_healthy()

	results = []
	if typesense_available:
		from ascl_net_app.model.database import Database
		from ascl_core.database.ascldb.ASCLModelClasses import ASCLCode

		pks = []
		seen = set()
		for variant in _author_query_variants(search_term):
			ts = typesense.search(
				query=variant,
				query_by='credit',
				filter_by='published:1',
				sort_by='_text_match:desc,time_added:desc',
				prefix=False,
				num_typos=0,
				per_page=100,
				page=1
			)
			if not ts or not ts.get("hits"):
				continue
			for hit in ts["hits"]:
				doc = hit.get("document", {})
				pk = doc.get("pk")
				if pk is None or pk in seen:
					continue
				seen.add(pk)
				pks.append(pk)
			if len(pks) >= 100:
				break

		if pks:
			session = Database().Session()
			codes_dict = {code.pk: code for code in session.query(ASCLCode).filter(ASCLCode.pk.in_(pks[:100])).all()}
			results = [codes_dict[pk] for pk in pks[:100] if pk in codes_dict]
			templateDict['search_method'] = 'typesense'

	if not results:
		results = _search_credit_mysql(search_term, limit=100)
		templateDict['search_method'] = 'mysql'

	# Keep only true person matches (avoid surname-only false positives).
	results = [code for code in results if code.matches_author_query(search_term)]

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
