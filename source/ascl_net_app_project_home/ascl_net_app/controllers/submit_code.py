#!/usr/bin/python

import flask
import json
from flask import render_template, request, redirect, session, jsonify
from datetime import datetime
from sqlalchemy import text

submit_code_page = flask.Blueprint("submit_code_page", __name__)

# Bot challenge answer (case-insensitive, spaces stripped)
CHALLENGE_ANSWER = "physicsisphun"


def _normalize_name(name_input):
	"""Normalize an author name to 'Last, First M.' format."""
	from nameparser import HumanName

	name = HumanName(name_input)

	parts = []
	last = name.last
	if name.suffix:
		last = f"{last} {name.suffix}"

	if last:
		parts.append(last)

	first_parts = []
	if name.first:
		first_parts.append(name.first)
	if name.middle:
		middle_initials = " ".join(
			m[0] + "." if len(m) > 1 and not m.endswith(".") else m
			for m in name.middle.split()
		)
		first_parts.append(middle_initials)

	if first_parts:
		if parts:
			parts[0] += ","
		parts.extend(first_parts)

	return " ".join(parts) if parts else name_input


def _add_links_for_code(db_session, code_pk, link_type_short_name, urls_text):
	"""Add links for a newly created code."""
	if not urls_text or not urls_text.strip():
		return

	# Get or create link_type_pk
	result = db_session.execute(text(
		"SELECT pk FROM link_type WHERE short_name = :short_name"
	), {"short_name": link_type_short_name}).first()

	if result:
		link_type_pk = result.pk
	else:
		# Create new link type
		db_session.execute(text("""
			INSERT INTO link_type (short_name, name)
			VALUES (:short_name, :name)
		"""), {
			"short_name": link_type_short_name,
			"name": link_type_short_name.replace('-', ' ').title()
		})
		result = db_session.execute(text("SELECT LAST_INSERT_ID()")).scalar()
		link_type_pk = result

	# Insert links
	urls = [url.strip() for url in urls_text.strip().split("\n") if url.strip()]
	for order, url in enumerate(urls):
		db_session.execute(text("""
			INSERT INTO link (code_pk, url, link_type_pk, display_order)
			VALUES (:code_pk, :url, :link_type_pk, :display_order)
		"""), {
			"code_pk": code_pk,
			"url": url,
			"link_type_pk": link_type_pk,
			"display_order": order
		})


def _add_authors_for_code(db_session, code_pk, authors_json):
	"""Insert author rows from JSON array of author objects.

	Each author object: {"name": "...", "orcid": "...", "orcid_provenance": "..."}
	Falls back to semicolon-delimited string for backward compatibility.
	"""
	if not authors_json or not authors_json.strip():
		return

	# Try JSON first, fall back to semicolon-delimited
	try:
		authors = json.loads(authors_json)
		if not isinstance(authors, list):
			raise ValueError
	except (json.JSONDecodeError, ValueError):
		authors = [{"name": t.strip()} for t in authors_json.split(";") if t.strip()]

	if not authors:
		return

	# Look up orcid_provenance PKs (cache)
	prov_cache = {}

	for order, author in enumerate(authors):
		name = author.get("name", "").strip()
		if not name:
			continue

		orcid = author.get("orcid", "").strip() or None
		orcid_prov_short = author.get("orcid_provenance", "").strip() or None
		orcid_prov_pk = None

		if orcid and orcid_prov_short:
			if orcid_prov_short not in prov_cache:
				row = db_session.execute(text(
					"SELECT pk FROM orcid_provenance WHERE short_name = :sn"
				), {"sn": orcid_prov_short}).first()
				prov_cache[orcid_prov_short] = row.pk if row else None
			orcid_prov_pk = prov_cache[orcid_prov_short]

		db_session.execute(text("""
			INSERT INTO author (name, orcid, orcid_provenance_pk)
			VALUES (:name, :orcid, :orcid_prov_pk)
		"""), {
			"name": name,
			"orcid": orcid,
			"orcid_prov_pk": orcid_prov_pk,
		})
		author_pk = db_session.execute(text("SELECT LAST_INSERT_ID()")).scalar()

		db_session.execute(text("""
			INSERT INTO code_to_author (code_pk, author_pk, display_order)
			VALUES (:code_pk, :author_pk, :display_order)
		"""), {
			"code_pk": code_pk,
			"author_pk": author_pk,
			"display_order": order,
		})


# --- Public API endpoints (no login required) ---

@submit_code_page.route("/api/normalize_name", methods=["POST"])
def public_normalize_name():
	"""Normalize an author name to 'Last, First M.' format. Public endpoint."""
	data = request.get_json()
	if not data or "name" not in data:
		return jsonify({"error": "Missing 'name' field"}), 400

	name_input = data["name"].strip()
	if not name_input:
		return jsonify({"error": "Empty name"}), 400

	normalized = _normalize_name(name_input)

	return jsonify({
		"original": name_input,
		"normalized": normalized,
	})


@submit_code_page.route("/api/bibcode_authors/<bibcode>", methods=["GET"])
def public_bibcode_authors(bibcode):
	"""Fetch authors + ORCIDs for a bibcode from ADS. Public endpoint."""
	import re
	import requests as http_requests

	# Basic bibcode validation
	if not re.match(r'^[\w.]+$', bibcode) or len(bibcode) > 25:
		return jsonify({"error": "Invalid bibcode"}), 400

	ads_token = flask.current_app.config.get("ADS_API_TOKEN", "")
	if not ads_token:
		return jsonify({"error": "ADS API not configured"}), 503

	try:
		headers = {"Authorization": f"Bearer {ads_token}"}
		params = {
			"q": f"bibcode:{bibcode}",
			"fl": "title,author,orcid_pub,orcid_user,year,bibcode"
		}
		response = http_requests.get(
			"https://api.adsabs.harvard.edu/v1/search/query",
			headers=headers, params=params, timeout=10
		)

		if response.status_code == 200:
			data = response.json()
			if data.get("response", {}).get("numFound", 0) > 0:
				doc = data["response"]["docs"][0]
				raw_authors = doc.get("author", [])
				orcid_pub = doc.get("orcid_pub", [])
				orcid_user = doc.get("orcid_user", [])

				authors = []
				for i, name in enumerate(raw_authors):
					orcid = None
					orcid_source = None

					# Prefer orcid_pub, fall back to orcid_user
					if i < len(orcid_pub) and orcid_pub[i] and orcid_pub[i] != "-":
						orcid = orcid_pub[i]
						orcid_source = "ads"
					elif i < len(orcid_user) and orcid_user[i] and orcid_user[i] != "-":
						orcid = orcid_user[i]
						orcid_source = "ads"

					normalized = _normalize_name(name)
					authors.append({
						"name": normalized,
						"original": name,
						"orcid": orcid,
						"orcid_provenance": orcid_source,
					})

				return jsonify({
					"bibcode": bibcode,
					"found": True,
					"title": doc.get("title", [""])[0],
					"authors": authors,
				})

		return jsonify({"bibcode": bibcode, "found": False, "error": "Not found"})

	except Exception as e:
		return jsonify({"bibcode": bibcode, "found": False, "error": str(e)})


@submit_code_page.route("/api/orcid_lookup/<path:orcid_id>", methods=["GET"])
def public_orcid_lookup(orcid_id):
	"""Fetch name from ORCID public API. No authentication required."""
	import re
	import requests as http_requests

	# Validate ORCID format: 0000-0000-0000-000X
	if not re.match(r'^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$', orcid_id):
		return jsonify({"error": "Invalid ORCID iD format (expected 0000-0000-0000-000X)"}), 400

	try:
		response = http_requests.get(
			f"https://pub.orcid.org/v3.0/{orcid_id}/record",
			headers={"Accept": "application/json"},
			timeout=10
		)

		if response.status_code == 404:
			return jsonify({"orcid": orcid_id, "found": False, "error": "ORCID not found"})

		if response.status_code != 200:
			return jsonify({"orcid": orcid_id, "found": False, "error": f"ORCID API returned {response.status_code}"})

		data = response.json()

		# Extract name
		person = data.get("person", {})
		name_obj = person.get("name", {})
		given = (name_obj.get("given-names") or {}).get("value", "")
		family = (name_obj.get("family-name") or {}).get("value", "")

		if not family:
			return jsonify({"orcid": orcid_id, "found": False, "error": "No name found for this ORCID"})

		# Normalize to "Family, Given I." format
		normalized = _normalize_name(f"{given} {family}" if given else family)

		return jsonify({
			"orcid": orcid_id,
			"found": True,
			"name": normalized,
			"given": given,
			"family": family,
		})

	except Exception as e:
		return jsonify({"orcid": orcid_id, "found": False, "error": str(e)})


@submit_code_page.route("/code/submit", methods=['GET', 'POST'])
def submit_code():
	"""Code submission form for users to submit new software entries.

	Matches PHP v3: /code/submit
	"""
	from ascl_net_app.model.database import Database
	db = Database()
	from ascl_core.database.ascldb.ASCLModelClasses import ASCLCode

	templateDict = {
		'page_title': 'Submit a Code',
		'mode': 'insert',
		'err': None,
		'msg': None,
		'hide_form': False,
		'form_data': {}
	}

	if request.method == 'POST':
		# Collect form data
		# credit: semicolon-delimited string for codes.credit column
		# authors_json: JSON array with name/orcid/provenance for author table
		form_data = {
			'title': request.form.get('title', '').strip(),
			'credit': request.form.get('credit', '').strip(),
			'authors_json': request.form.get('authors_json', '').strip(),
			'abstract': request.form.get('abstract', '').strip(),
			'site_urls': request.form.get('site_urls', '').strip(),
			'described_in_urls': request.form.get('described_in_urls', '').strip(),
			'used_in_urls': request.form.get('used_in_urls', '').strip(),
			'citation_method': request.form.get('citation_method', '').strip(),
			'name': request.form.get('name', '').strip(),
			'email': request.form.get('email', '').strip(),
			'notes': request.form.get('notes', '').strip(),
			'challenge': request.form.get('challenge', '').strip()
		}
		templateDict['form_data'] = form_data

		# Validation
		errors = []

		if not form_data['title']:
			errors.append("Title is required.")
		if not form_data['credit']:
			errors.append("Credit (author names) is required.")
		if not form_data['abstract']:
			errors.append("Abstract is required.")

		if not form_data['name']:
			errors.append("Your name is required.")
		if not form_data['email']:
			errors.append("Email address is required.")
		elif '@' not in form_data['email']:
			errors.append("Please enter a valid email address.")

		# Bot challenge validation
		challenge_response = form_data['challenge'].lower().replace(' ', '')
		if not form_data['challenge']:
			errors.append("Bot challenge response is required.")
		elif challenge_response != CHALLENGE_ANSWER:
			errors.append("Bot challenge response was incorrect. Note: Spaces and capitalization do not matter, just spelling.")

		if errors:
			templateDict['err'] = '<p>' + '</p><p>'.join(errors) + '</p>'
		else:
			# Insert the code into the database
			try:
				db_session = db.Session()

				# Prepare notes field with submitter info
				notes = f"Submitted by: {form_data['name']}\n\n{form_data['notes']}"

				# Create new code entry
				new_code = ASCLCode()
				new_code.title = form_data['title']
				new_code.credit = form_data['credit']
				new_code.abstract = form_data['abstract']
				new_code.citation_method = form_data['citation_method'] or None
				new_code.email = form_data['email']
				new_code.notes = notes
				new_code.time_added = datetime.now()
				new_code.time_updated = datetime.now()
				new_code.ascl_id = '0000.000'  # User-submitted codes get placeholder ID
				new_code.published = 1  # Visible immediately; editor reviews later

				db_session.add(new_code)
				db_session.flush()  # Get the PK

				code_pk = new_code.pk

				# Add links to link table
				_add_links_for_code(db_session, code_pk, 'code-site', form_data['site_urls'])
				_add_links_for_code(db_session, code_pk, 'described-in', form_data['described_in_urls'])
				_add_links_for_code(db_session, code_pk, 'used-in', form_data['used_in_urls'])
				try:
					# Use authors_json if available; fall back to credit string
					authors_data = form_data['authors_json'] or form_data['credit']
					_add_authors_for_code(db_session, code_pk, authors_data)
				except Exception:
					# Author table may not exist yet if migration has not run.
					pass

				db_session.commit()

				# Store in session so user can edit their submission
				if 'editable_codes' not in session:
					session['editable_codes'] = []
				session['editable_codes'].append(code_pk)
				session.modified = True

				db_session.close()

				templateDict['msg'] = f'<p>Code added. <a href="/code/v/{code_pk}">View it here</a>.</p>'
				templateDict['hide_form'] = True

			except Exception as e:
				import logging
				logging.getLogger(__name__).exception("Code submission failed")
				db_session.rollback()
				templateDict['err'] = f'<p>An error occurred while submitting your code. Please try again or contact us if the problem persists.</p>'

	return render_template("submit_code.html", **templateDict)
