#!/usr/bin/python

import flask
from flask import render_template, request, redirect, session
from datetime import datetime
from sqlalchemy import text

submit_code_page = flask.Blueprint("submit_code_page", __name__)

# Bot challenge answer (case-insensitive, spaces stripped)
CHALLENGE_ANSWER = "physicsisphun"


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


def _add_authors_for_code(db_session, code_pk, credit_text):
	"""Insert author rows from semicolon-delimited credit text."""
	if not credit_text or not credit_text.strip():
		return

	authors = [token.strip() for token in credit_text.split(";") if token.strip()]
	if not authors:
		return

	for order, author in enumerate(authors):
		db_session.execute(text("""
			INSERT INTO author (code_pk, raw_name, display_name, raw_credit_text, display_order)
			VALUES (:code_pk, :raw_name, :display_name, :raw_credit_text, :display_order)
		"""), {
			"code_pk": code_pk,
			"raw_name": author,
			"display_name": author,
			"raw_credit_text": credit_text.strip(),
			"display_order": order
		})


@submit_code_page.route("/code/submit", methods=['GET', 'POST'])
def submit_code():
	"""Code submission form for users to submit new software entries.

	Matches PHP v3: /code/submit
	"""
	from ascl_core.database.connections import Trillian2DBConnection as db
	from ascl_core.database.ascldb.ASCLModelClasses import ASCLCode

	templateDict = {
		'page_title': 'Submit Code',
		'mode': 'insert',
		'err': None,
		'msg': None,
		'hide_form': False,
		'form_data': {}
	}

	if request.method == 'POST':
		# Collect form data
		form_data = {
			'title': request.form.get('title', '').strip(),
			'credit': request.form.get('credit', '').strip(),
			'abstract': request.form.get('abstract', '').strip(),
			'site_urls': request.form.get('site_urls', '').strip(),
			'reference_urls': request.form.get('reference_urls', '').strip(),
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
		if not form_data['site_urls']:
			errors.append("At least one code site URL is required.")
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
				new_code.citation_method = form_data['citation_method'] if form_data['citation_method'] else None
				new_code.email = form_data['email']
				new_code.notes = notes
				new_code.time_added = datetime.now()
				new_code.time_updated = datetime.now()
				new_code.ascl_id = '0000.000'  # User-submitted codes get placeholder ID
				new_code.published = 0  # Not published until reviewed

				db_session.add(new_code)
				db_session.flush()  # Get the PK

				code_pk = new_code.pk

				# Add links to link table
				_add_links_for_code(db_session, code_pk, 'code-site', form_data['site_urls'])
				_add_links_for_code(db_session, code_pk, 'reference', form_data['reference_urls'])
				try:
					_add_authors_for_code(db_session, code_pk, form_data['credit'])
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
				templateDict['err'] = f'<p>An error occurred while submitting your code: {str(e)}</p>'

	return render_template("submit_code.html", **templateDict)
