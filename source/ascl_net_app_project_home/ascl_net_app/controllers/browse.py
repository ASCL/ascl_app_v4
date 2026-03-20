#!/usr/bin/python

import flask
from flask import request, render_template, redirect
from sqlalchemy import func, text

code_page = flask.Blueprint("code_page", __name__)

@code_page.route("/code/all", methods=['GET'])
def code_all():
	''' Browse all codes with pagination and sorting. Matches PHP: Code::all() '''
	from ascl_net_app.model.database import Database
	db = Database()
	import ascl_core.database.ascldb.ASCLModelClasses as ascldb

	# Get parameters from URL
	page = request.args.get('page', 1, type=int)
	per_page = request.args.get('limit', 100, type=int)
	sort_by = request.args.get('order', 'title')  # 'title' or 'date'
	sort_order = request.args.get('dir', 'asc')  # 'asc' or 'desc'
	view_mode = request.args.get('listmode', 'full')  # 'full' or 'compact'

	# Validate parameters (matches PHP validation)
	if sort_by not in ('title', 'date'):
		sort_by = 'title'
	if view_mode not in ('full', 'compact'):
		view_mode = 'full'
	if sort_order not in ('asc', 'desc'):
		sort_order = 'asc'
	if page < 1:
		page = 1

	session = db.Session()

	# PHP: only filters on published=1, does NOT filter archived
	query = session.query(ascldb.ASCLCode).filter(ascldb.ASCLCode.published == 1)

	# Get total count of published codes
	total_codes = query.count()

	# Get count of submitted (0000.000) codes within published
	total_sub_codes = (session.query(ascldb.ASCLCode)
		.filter(ascldb.ASCLCode.published == 1)
		.filter(ascldb.ASCLCode.ascl_id == '0000.000')
		.count())

	# Apply sorting
	# For title sort, strip HTML tags so e.g. "<i>realfast</i>" sorts as "realfast"
	stripped_title = func.regexp_replace(ascldb.ASCLCode.title, '<[^>]+>', '')
	if sort_by == 'date':
		if sort_order == 'desc':
			query = query.order_by(ascldb.ASCLCode.time_added.desc())
		else:
			query = query.order_by(ascldb.ASCLCode.time_added.asc())
	else:  # sort by title
		if sort_order == 'desc':
			query = query.order_by(stripped_title.desc())
		else:
			query = query.order_by(stripped_title.asc())

	# Apply pagination
	total_pages = max(1, (total_codes + per_page - 1) // per_page) if per_page > 0 else 1
	if page > total_pages:
		page = total_pages

	if per_page > 0:
		offset = (page - 1) * per_page
		codes = query.limit(per_page).offset(offset).all()
	else:
		codes = query.all()
		total_pages = 1

	templateDict = {
		'codes': codes,
		'page': page,
		'per_page': per_page,
		'total_codes': total_codes,
		'total_sub_codes': total_sub_codes,
		'total_pages': total_pages,
		'sort_by': sort_by,
		'sort_order': sort_order,
		'view_mode': view_mode,
		'start_result': (page - 1) * per_page + 1 if (codes and per_page > 0) else (1 if codes else 0),
		'end_result': min(page * per_page, total_codes) if per_page > 0 else total_codes,
	}

	return render_template("code_all.html", **templateDict)


@code_page.route("/code/all_by_id", methods=['GET'])
def code_all_by_id():
	''' List all codes organized by ASCL ID. Matches PHP: Code::all_by_id() '''
	from ascl_net_app.model.database import Database
	db = Database()
	import ascl_core.database.ascldb.ASCLModelClasses as ascldb

	session = db.Session()

	# PHP: only filters on published=1
	codes = (session.query(ascldb.ASCLCode)
		.filter(ascldb.ASCLCode.published == 1)
		.order_by(ascldb.ASCLCode.century.asc(), ascldb.ASCLCode.ascl_id.asc())
		.all())

	# Group codes by YYMM prefix
	codes_by_id = {}
	for code in codes:
		parts = code.ascl_id.split('.')
		if len(parts) == 2:
			yymm = parts[0]
			xxx = parts[1]
			if yymm not in codes_by_id:
				codes_by_id[yymm] = {}
			codes_by_id[yymm][xxx] = code.title

	return render_template("code_all_by_id.html", codes_by_id=codes_by_id)


@code_page.route("/code/keywords", methods=['GET'])
@code_page.route("/code/keywords/<path:keyword>", methods=['GET'])
def code_keywords(keyword=None):
	''' Browse keywords and codes by keyword. Matches PHP: Code::keywords() '''
	from ascl_net_app.model.database import Database
	db = Database()
	import ascl_core.database.ascldb.ASCLModelClasses as ascldb

	session = db.Session()

	codes = []
	result_count = 0

	# If a keyword was selected, get codes for that keyword
	# PHP: filters on published=1 AND archived=0
	if keyword:
		codes = (session.query(ascldb.ASCLCode)
			.join(ascldb.ASCLCodeToKeyword,
				  ascldb.ASCLCodeToKeyword.__table__.c.code_pk == ascldb.ASCLCode.pk)
			.join(ascldb.Keyword,
				  ascldb.Keyword.pk == ascldb.ASCLCodeToKeyword.__table__.c.keyword_pk)
			.filter(ascldb.Keyword.label == keyword)
			.filter(ascldb.ASCLCode.published == 1)
			.filter(ascldb.ASCLCode.archived == 0)
			.all())
		result_count = len(codes)

	# Build keyword list with counts
	# PHP: filters on published=1 AND archived=0, sorted by usage_count DESC, keyword ASC
	keyword_counts_query = (session.query(
			ascldb.Keyword.label,
			func.count().label('usage_count'))
		.join(ascldb.ASCLCodeToKeyword,
			  ascldb.ASCLCodeToKeyword.__table__.c.keyword_pk == ascldb.Keyword.pk)
		.join(ascldb.ASCLCode,
			  ascldb.ASCLCode.pk == ascldb.ASCLCodeToKeyword.__table__.c.code_pk)
		.filter(ascldb.ASCLCode.published == 1)
		.filter(ascldb.ASCLCode.archived == 0)
		.group_by(ascldb.Keyword.label)
		.order_by(func.count().desc(), ascldb.Keyword.label.asc())
		.all())

	# Build ordered dict of keyword -> count
	keywords = {row.label: row.usage_count for row in keyword_counts_query}

	return render_template("code_keywords.html",
		keywords=keywords,
		keyword=keyword or '',
		codes=codes,
		result_count=result_count)


@code_page.route("/code/alias_list", methods=['GET'])
def code_alias_list():
	''' List of code aliases. Matches PHP: Code::alias_list() '''
	from ascl_net_app.model.database import Database
	db = Database()
	import ascl_core.database.ascldb.ASCLModelClasses as ascldb

	session = db.Session()

	# PHP: filters on published=1 AND archived=0, ordered by alias
	aliases = (session.query(
			ascldb.ASCLCode.ascl_id,
			ascldb.ASCLCodeAlias.alias)
		.join(ascldb.ASCLCodeAlias,
			  ascldb.ASCLCodeAlias.__table__.c.code_pk == ascldb.ASCLCode.pk)
		.filter(ascldb.ASCLCode.published == 1)
		.filter(ascldb.ASCLCode.archived == 0)
		.order_by(ascldb.ASCLCodeAlias.alias.asc())
		.all())

	return render_template("code_alias_list.html",
		aliases=aliases,
		result_count=len(aliases))


@code_page.route("/code/random", methods=['GET'])
def random_code():
	''' Redirect to a random published code. '''
	from ascl_net_app.model.database import Database
	db = Database()
	import ascl_core.database.ascldb.ASCLModelClasses as ascldb

	session = db.Session()
	code = ascldb.ASCLCode.random_code(session)
	if code:
		return redirect(f"/{code.ascl_id}")
	return redirect("/code/all")


@code_page.route("/discover/similar/<ascl_id>", methods=['GET'])
def discover_similar(ascl_id):
	''' Redirect to a random published code sharing any keyword with the given code. '''
	from ascl_net_app.model.database import Database
	db = Database()

	session = db.Session()

	row = session.execute(text("""
		SELECT c2.ascl_id FROM codes c1
		JOIN code_to_keyword ck1 ON c1.pk = ck1.code_pk
		JOIN code_to_keyword ck2 ON ck1.keyword_pk = ck2.keyword_pk
		JOIN public_codes c2 ON c2.pk = ck2.code_pk
		WHERE c1.ascl_id = :ascl_id
		  AND c2.ascl_id != :ascl_id
		ORDER BY RAND() LIMIT 1
	"""), {"ascl_id": ascl_id}).first()

	if row:
		return redirect(f"/{row.ascl_id}")
	return redirect(request.referrer or "/code/all")


@code_page.route("/discover/mentioned/<ascl_id>", methods=['GET'])
def discover_mentioned(ascl_id):
	''' Redirect to a random published code that mentions this code's title in its abstract. '''
	from ascl_net_app.model.database import Database
	db = Database()

	session = db.Session()

	# Get the source code's title
	source = session.execute(text("""
		SELECT pk, title FROM codes WHERE ascl_id = :ascl_id
	"""), {"ascl_id": ascl_id}).first()

	if source:
		row = session.execute(text("""
			SELECT ascl_id FROM public_codes
			WHERE MATCH(abstract) AGAINST(:title IN NATURAL LANGUAGE MODE)
			  AND pk != :source_pk
			ORDER BY RAND() LIMIT 1
		"""), {"title": source.title, "source_pk": source.pk}).first()

		if row:
			return redirect(f"/{row.ascl_id}")

	return redirect(request.referrer or "/code/all")


@code_page.route("/discover/domain/<term>", methods=['GET'])
def discover_domain(term):
	''' Redirect to a random published code whose abstract matches a domain term. '''
	from ascl_net_app.model.database import Database
	db = Database()

	session = db.Session()
	exclude_ascl_id = request.args.get('from', '')

	# Short terms (< 3 chars) fall below MySQL fulltext min token size;
	# use REGEXP with word boundaries instead
	if len(term) < 3:
		row = session.execute(text("""
			SELECT ascl_id FROM public_codes
			WHERE abstract REGEXP CONCAT('\\\\b', :term, '\\\\b')
			  AND ascl_id != :exclude_id
			ORDER BY RAND() LIMIT 1
		"""), {"term": term, "exclude_id": exclude_ascl_id}).first()
	else:
		# Wrap multi-word terms in quotes for exact phrase matching
		search_term = f'"{term}"' if ' ' in term else term

		row = session.execute(text("""
			SELECT ascl_id FROM public_codes
			WHERE MATCH(abstract) AGAINST(:term IN BOOLEAN MODE)
			  AND ascl_id != :exclude_id
			ORDER BY RAND() LIMIT 1
		"""), {"term": search_term, "exclude_id": exclude_ascl_id}).first()

	if row:
		return redirect(f"/{row.ascl_id}")
	return redirect(request.referrer or "/code/all")


@code_page.route("/discover/language/<lang>", methods=['GET'])
def discover_language(lang):
	''' Redirect to a random published code written in the given language. '''
	from ascl_net_app.model.database import Database
	db = Database()

	session = db.Session()
	exclude_ascl_id = request.args.get('from', '')

	# C++ can't use fulltext ('+' is an operator) — use LIKE instead
	# Other languages use REGEXP with word boundaries to avoid false positives
	if lang == 'C++':
		row = session.execute(text("""
			SELECT ascl_id FROM public_codes
			WHERE abstract LIKE :pattern
			  AND ascl_id != :exclude_id
			ORDER BY RAND() LIMIT 1
		"""), {"pattern": "%C++%", "exclude_id": exclude_ascl_id}).first()
	else:
		row = session.execute(text("""
			SELECT ascl_id FROM public_codes
			WHERE abstract REGEXP CONCAT('\\\\b', :lang, '\\\\b')
			  AND ascl_id != :exclude_id
			ORDER BY RAND() LIMIT 1
		"""), {"lang": lang, "exclude_id": exclude_ascl_id}).first()

	if row:
		return redirect(f"/{row.ascl_id}")
	return redirect(request.referrer or "/code/all")


@code_page.route("/discover/author/<ascl_id>", methods=['GET'])
def discover_author(ascl_id):
	''' Redirect to a random published code sharing any author with the given code. '''
	from ascl_net_app.model.database import Database
	db = Database()

	session = db.Session()

	row = session.execute(text("""
		SELECT c2.ascl_id FROM codes c1
		JOIN code_to_author ca1 ON c1.pk = ca1.code_pk
		JOIN code_to_author ca2 ON ca1.author_pk = ca2.author_pk
		JOIN public_codes c2 ON c2.pk = ca2.code_pk
		WHERE c1.ascl_id = :ascl_id
		  AND c2.ascl_id != :ascl_id
		ORDER BY RAND() LIMIT 1
	"""), {"ascl_id": ascl_id}).first()

	if row:
		return redirect(f"/{row.ascl_id}")
	return redirect(request.referrer or "/code/all")
