#!/usr/bin/python

import flask
from flask import render_template, abort, redirect, request, session, jsonify
import re
from sqlalchemy import text, func

code_detail_page = flask.Blueprint("code_detail_page", __name__)

@code_detail_page.route("/alt/<path:ascl_id>", methods=['GET'])
def code_detail_alt(ascl_id):
	"""Modern alternate version of code detail page."""
	import re
	if not re.match(r'^\d{4}\.\d{3}$', ascl_id):
		from flask import abort
		abort(404)

	from ascl_core.database.connections import Trillian2Connection as db
	import ascl_core.database.ascldb.ASCLModelClasses as ascldb

	# Get database session
	session = db.Session()

	code = session.query(ascldb.ASCLCode).filter_by(ascl_id=ascl_id).first()

	if not code:
		abort(404)

	# Get related links from link table
	link_query = text("""
		SELECT l.pk AS lpk, l.url, lt.short_name
		FROM link l
		LEFT JOIN link_type lt ON l.link_type_pk = lt.pk
		WHERE l.code_pk = :code_pk
		ORDER BY lt.pk, l.display_order, l.pk
	""")

	link_results = session.execute(link_query, {"code_pk": code.pk}).mappings().all()

	# Group links by type
	site_links = []
	described_in_links = []
	used_in_links = []
	ref_links = []
	emac_links = []
	untyped_links = []

	for link in link_results:
		url = link["url"]
		link_type = link["short_name"]

		if link_type == 'code-site':
			site_links.append(url)
		elif link_type == 'described-in':
			described_in_links.append(url)
		elif link_type == 'used-in':
			used_in_links.append(url)
		elif link_type == 'reference':
			ref_links.append(url)
		elif link_type == 'emac':
			emac_links.append(url)
		elif link_type is None or link_type == '':
			untyped_links.append({'pk': link["lpk"], 'url': url})

	# Get keywords for this code
	from sqlalchemy import desc
	keywords_query = text("""
		SELECT k.label
		FROM keyword k
		JOIN code_to_keyword ck ON k.pk = ck.keyword_pk
		WHERE ck.code_pk = :code_pk
		ORDER BY k.label ASC
	""")

	keyword_results = session.execute(keywords_query, {"code_pk": code.pk}).fetchall()
	keywords = [row.label for row in keyword_results]

	templateDict = {
		'code': code,
		'site_links': site_links,
		'described_in_links': described_in_links,
		'used_in_links': used_in_links,
		'ref_links': ref_links,
		'emac_links': emac_links,
		'untyped_links': untyped_links,
		'keywords': keywords,
	}

	return render_template("code_detail_alt.html", **templateDict)


@code_detail_page.route("/<path:ascl_id>", methods=['GET'])
def code_detail(ascl_id):
	''' Show detailed information for a specific code, or resolve an alias. '''
	from ascl_core.database.connections import Trillian2Connection as db
	import ascl_core.database.ascldb.ASCLModelClasses as ascldb

	# Get database session
	session = db.Session()

	# Branch: ASCL ID format (YYMM.NNN) vs. potential alias
	if not re.match(r'^\d{4}\.\d{3}$', ascl_id):
		# --- Alias resolution ---
		alias_matches = (
			session.query(ascldb.ASCLCodeAlias)
			.join(ascldb.ASCLCode, ascldb.ASCLCodeAlias.code)
			.filter(func.lower(ascldb.ASCLCodeAlias.alias) == ascl_id.lower())
			.filter(ascldb.ASCLCode.published == 1)
			.all()
		)

		if len(alias_matches) == 0:
			abort(404)
		elif len(alias_matches) == 1:
			return redirect(f"/{alias_matches[0].code.ascl_id}")
		else:
			# Multiple matches — show search results
			codes = [match.code for match in alias_matches]
			return render_template("search.html",
				query=ascl_id,
				results=codes,
				result_count=len(codes),
				page=1,
				per_page=0,
				total_pages=1,
				start_result=1,
				end_result=len(codes),
			)

	# --- Standard ASCL ID lookup ---
	code = session.query(ascldb.ASCLCode).filter_by(ascl_id=ascl_id).first()

	if not code:
		abort(404)

	# Non-admin visitors cannot view unpublished codes (matches PHP production)
	from flask import session as flask_session
	if not flask_session.get("user_id") and not code.published:
		abort(404)

	# Get related links from link table
	link_query = text("""
		SELECT l.pk AS lpk, l.url, lt.short_name
		FROM link l
		LEFT JOIN link_type lt ON l.link_type_pk = lt.pk
		WHERE l.code_pk = :code_pk
		ORDER BY lt.pk, l.display_order, l.pk
	""")

	link_results = session.execute(link_query, {"code_pk": code.pk}).mappings().all()

	# Group links by type
	site_links = []
	described_in_links = []
	used_in_links = []
	ref_links = []
	emac_links = []
	untyped_links = []

	for link in link_results:
		url = link["url"]
		link_type = link["short_name"]

		if link_type == 'code-site':
			site_links.append(url)
		elif link_type == 'described-in':
			described_in_links.append(url)
		elif link_type == 'used-in':
			used_in_links.append(url)
		elif link_type == 'reference':
			ref_links.append(url)
		elif link_type == 'emac':
			emac_links.append(url)
		elif link_type is None or link_type == '':
			untyped_links.append({'pk': link["lpk"], 'url': url})

	templateDict = {
		'code': code,
		'site_links': site_links,
		'described_in_links': described_in_links,
		'used_in_links': used_in_links,
		'ref_links': ref_links,
		'emac_links': emac_links,
		'untyped_links': untyped_links,
	}

	return render_template("code_detail.html", **templateDict)


@code_detail_page.route("/delete_link/<int:link_pk>", methods=['POST'])
def delete_link(link_pk):
	"""Delete an untyped link (admin only)."""
	if not session.get("user_id"):
		abort(403)

	from ascl_core.database.connections import Trillian2Connection as db

	db_session = db.Session()

	# Only allow deleting links with NULL link_type_pk
	row = db_session.execute(
		text("SELECT pk, code_pk, link_type_pk FROM link WHERE pk = :pk"),
		{"pk": link_pk}
	).mappings().first()

	if not row:
		abort(404)
	if row["link_type_pk"] is not None:
		abort(403)

	db_session.execute(text("DELETE FROM link WHERE pk = :pk"), {"pk": link_pk})
	db_session.commit()

	# Redirect back to the referring page
	return redirect(request.referrer or "/")
