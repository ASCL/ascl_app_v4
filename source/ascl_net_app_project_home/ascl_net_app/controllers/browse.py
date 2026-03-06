#!/usr/bin/python

import flask
from flask import request, render_template, redirect

browse_page = flask.Blueprint("browse_page", __name__)

@browse_page.route("/browse", methods=['GET'])
def browse():
	''' Browse all codes with pagination and sorting. '''
	from ascl_core.database.connections import Trillian2Connection as db
	import ascl_core.database.ascldb.ASCLModelClasses as ascldb

	# Get parameters from URL
	page = request.args.get('page', 1, type=int)
	per_page = request.args.get('per_page', 100, type=int)
	sort_by = request.args.get('sort', 'title')  # 'title' or 'date'
	sort_order = request.args.get('order', 'asc')  # 'asc' or 'desc'
	view_mode = request.args.get('view', 'abstract')  # 'abstract' or 'compact'

	# Get database session
	session = db.Session()

	# Build query — only show published codes (matches production)
	query = session.query(ascldb.ASCLCode).filter(ascldb.ASCLCode.published == 1)

	# Apply sorting
	if sort_by == 'date':
		if sort_order == 'desc':
			query = query.order_by(ascldb.ASCLCode.time_added.desc(), ascldb.ASCLCode.pk.desc())
		else:
			query = query.order_by(ascldb.ASCLCode.time_added.asc(), ascldb.ASCLCode.pk.asc())
	else:  # sort by title
		if sort_order == 'desc':
			query = query.order_by(ascldb.ASCLCode.title.desc())
		else:
			query = query.order_by(ascldb.ASCLCode.title.asc())

	# Get total count
	total_codes = query.count()

	# Apply pagination
	if per_page == -1:  # Show all
		codes = query.all()
		total_pages = 1
	else:
		offset = (page - 1) * per_page
		codes = query.limit(per_page).offset(offset).all()
		total_pages = (total_codes + per_page - 1) // per_page

	templateDict = {
		'codes': codes,
		'page': page,
		'per_page': per_page,
		'total_codes': total_codes,
		'total_pages': total_pages,
		'sort_by': sort_by,
		'sort_order': sort_order,
		'view_mode': view_mode,
		'start_result': (page - 1) * per_page + 1 if codes else 0,
		'end_result': min(page * per_page, total_codes) if per_page != -1 else total_codes
	}

	return render_template("browse.html", **templateDict)


@browse_page.route("/code/random", methods=['GET'])
def random_code():
	''' Redirect to a random published code. '''
	from ascl_core.database.connections import Trillian2Connection as db
	import ascl_core.database.ascldb.ASCLModelClasses as ascldb

	session = db.Session()
	code = ascldb.ASCLCode.random_code(session)
	if code:
		return redirect(f"/{code.ascl_id}")
	return redirect("/browse")
