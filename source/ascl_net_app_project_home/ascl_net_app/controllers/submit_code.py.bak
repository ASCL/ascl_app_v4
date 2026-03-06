#!/usr/bin/python

import flask
from flask import render_template, request, redirect, session
from datetime import datetime

submit_code_page = flask.Blueprint("submit_code_page", __name__)

# Bot challenge answer (case-insensitive, spaces stripped)
CHALLENGE_ANSWER = "physicsisphun"


def _prep_list_for_db(text):
	"""Convert newline-separated URLs to PHP-serialized format for database storage.

	Matches PHP function: prep_list_for_db()
	"""
	if not text:
		return None

	lines = [line.strip() for line in text.strip().split('\n') if line.strip()]
	if not lines:
		return None

	# PHP serialize format: a:N:{i:0;s:LEN:"value";...}
	parts = []
	for i, line in enumerate(lines):
		parts.append(f'i:{i};s:{len(line)}:"{line}";')

	return f'a:{len(lines)}:{{{" ".join(parts).replace("; ", ";")}}}'


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
			'site_list': request.form.get('site_list', '').strip(),
			'ref_list': request.form.get('ref_list', '').strip(),
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
		if not form_data['site_list']:
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
				new_code.site_list = _prep_list_for_db(form_data['site_list'])
				new_code.ref_list = _prep_list_for_db(form_data['ref_list'])
				new_code.citation_method = form_data['citation_method'] if form_data['citation_method'] else None
				new_code.email = form_data['email']
				new_code.notes = notes
				new_code.time_added = datetime.now()
				new_code.ascl_id = '0000.000'  # User-submitted codes get placeholder ID
				new_code.published = 0  # Not published until reviewed
				new_code.views = 0

				db_session.add(new_code)
				db_session.commit()

				code_pk = new_code.pk

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
