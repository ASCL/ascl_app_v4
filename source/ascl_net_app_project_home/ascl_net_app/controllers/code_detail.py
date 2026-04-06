#!/usr/bin/python

import flask
from flask import render_template, abort, redirect, request, session, jsonify
import re
import random
from sqlalchemy import text, func

code_detail_page = flask.Blueprint("code_detail_page", __name__)

@code_detail_page.route("/alt/<path:ascl_id>", methods=['GET'])
def code_detail_alt(ascl_id):
	"""Modern alternate version of code detail page."""
	import re
	if not re.match(r'^\d{4}\.\d{3}$', ascl_id):
		from flask import abort
		abort(404)

	from ascl_net_app.model.database import Database
	db = Database()
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
		elif link_type == 'refereed':
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


@code_detail_page.route("/code/v/<int:pk>", methods=['GET'])
def code_detail_by_pk(pk):
	'''View a code by its database primary key (used for newly submitted codes).'''
	from ascl_net_app.model.database import Database
	db = Database()
	import ascl_core.database.ascldb.ASCLModelClasses as ascldb

	session = db.Session()
	code = session.query(ascldb.ASCLCode).filter_by(pk=pk).first()

	if not code:
		abort(404)

	# Non-admin visitors cannot view unpublished codes
	from flask import session as flask_session
	if not flask_session.get("user_id") and not code.published:
		abort(404)

	# If the code has a real ASCL ID, redirect to the canonical URL
	if code.ascl_id and code.ascl_id != '0000.000':
		return redirect(f"/{code.ascl_id}")

	return _render_code_detail(session, code)


@code_detail_page.route("/<path:ascl_id>", methods=['GET'])
def code_detail(ascl_id):
	''' Show detailed information for a specific code, or resolve an alias. '''
	from ascl_net_app.model.database import Database
	db = Database()
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

	return _render_code_detail(session, code)


def _render_code_detail(session, code):
	"""Render the code detail page for a given code object and DB session."""
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
		elif link_type == 'refereed':
			ref_links.append(url)
		elif link_type == 'emac':
			emac_links.append(url)
		elif link_type is None or link_type == '':
			untyped_links.append({'pk': link["lpk"], 'url': url})

	# Discovery bar: check if another code shares a keyword (for "similar" pill)
	has_keywords = session.execute(text("""
		SELECT 1 FROM code_to_keyword ck1
		JOIN code_to_keyword ck2 ON ck1.keyword_pk = ck2.keyword_pk
		JOIN public_codes c2 ON c2.pk = ck2.code_pk
		WHERE ck1.code_pk = :code_pk
		  AND ck2.code_pk != :code_pk
		LIMIT 1
	"""), {"code_pk": code.pk}).first() is not None

	# Discovery bar: author count + whether another code shares any author
	author_count = session.execute(
		text("SELECT COUNT(*) FROM code_to_author WHERE code_pk = :code_pk"),
		{"code_pk": code.pk}
	).scalar()

	# Only show "By same author(s)" if at least one author wrote another published code
	author_has_other_codes = False
	if author_count > 0:
		author_has_other_codes = session.execute(text("""
			SELECT 1 FROM code_to_author ca1
			JOIN code_to_author ca2 ON ca1.author_pk = ca2.author_pk
			JOIN public_codes c2 ON c2.pk = ca2.code_pk
			WHERE ca1.code_pk = :code_pk
			  AND ca2.code_pk != :code_pk
			LIMIT 1
		"""), {"code_pk": code.pk}).first() is not None

	# Discovery bar: match domain terms in abstract
	# Ordered by specificity (niche terms first, broad terms last)
	DOMAIN_TERMS = [
		('machine learning', 'machine learning'),
		('TensorFlow', 'machine learning'),
		('Keras', 'machine learning'),
		('PyTorch', 'machine learning'),
		('monte carlo', 'Monte Carlo'),
		('time series', 'time series'),
		('pulsar', 'pulsar'),
		('exoplanet', 'exoplanet'),
		('AGN', 'AGN'),
		('CMB', 'CMB'),
		('N body', 'N-body'),
		('hydrodynamic*', 'hydrodynamics'),
		('star form*', 'star formation'),
		('stellar', 'stellar'),
		('galactic', 'galactic'),
		('cosmological', 'cosmology'),
		('gravitational', 'gravitational'),
		('spectral', 'spectral'),
		('photometric', 'photometry'),
		('planet*', 'planetary'),
		('solar', 'solar'),
		('continuum', 'continuum'),
		('SED', 'SED'),
		('neutrino', 'neutrino'),
		('synchrotron', 'synchrotron'),
		('dust', 'dust'),
		('plasma', 'plasma'),
		('magnetic', 'magnetic'),
		('cosmic ray', 'cosmic ray'),
		('radio', 'radio'),
		('CCD', 'CCD'),
		('RFI', 'RFI'),
		('PSF', 'PSF'),
		('coronagraph*', 'coronagraphy'),
		('interferomet*', 'interferometry'),
		('Virtual Observatory', 'VO'),
		('VO', 'VO'),
		('FITS', 'FITS'),
		('X ray', 'X-ray'),
		('UV', 'UV'),
		('3D', '3D'),
		('simulat*', 'simulations'),
		('noise', 'noise'),
		('Stokes', 'Stokes'),
		('FFT', 'FFT'),
		('dark matter', 'dark matter'),
		('black hole', 'black hole'),
		('merger*', 'mergers'),
		('lens*', 'lensing'),
		('cluster*', 'clusters'),
		('dwarf', 'dwarf'),
		('halo', 'halo'),
	]

	abstract_text_domain = (code.abstract or '').replace('-', ' ')

	def has_other_match_domain(term):
		"""Check if at least one other published code matches this domain term."""
		clean = term.rstrip('*')
		if len(clean) < 3:
			return session.execute(text("""
				SELECT 1 FROM public_codes
				WHERE abstract REGEXP CONCAT('\\\\b', :term, '\\\\b')
				  AND pk != :code_pk LIMIT 1
			"""), {"term": clean, "code_pk": code.pk}).first() is not None
		search = f'"{clean}"' if ' ' in clean else clean
		return session.execute(text("""
			SELECT 1 FROM public_codes
			WHERE MATCH(abstract) AGAINST(:term IN BOOLEAN MODE)
			  AND pk != :code_pk LIMIT 1
		"""), {"term": search, "code_pk": code.pk}).first() is not None

	domain_matches = []
	seen_labels = set()
	for term, label in DOMAIN_TERMS:
		# Terms ending with '*' match as prefix (no trailing word boundary)
		if term.endswith('*'):
			pattern = r'\b' + re.escape(term[:-1])
		else:
			pattern = r'\b' + re.escape(term) + r'\b'
		if re.search(pattern, abstract_text_domain, re.IGNORECASE) and label not in seen_labels:
			if has_other_match_domain(term):
				domain_matches.append({'term': term.rstrip('*'), 'label': label})
				seen_labels.add(label)
	random.shuffle(domain_matches)

	# Discovery bar: mission/survey pill
	# Primary source: code's keywords (curated in DB)
	# Fallback: scan abstract for well-known mission/survey names
	# Discovery bar: mission/survey pills
	# Primary source: code's keywords (curated in DB)
	# Fallback: scan abstract for well-known mission/survey names
	mission_matches = []
	keyword_rows = session.execute(text("""
		SELECT k.label, k.short_name FROM keyword k
		JOIN code_to_keyword ck ON k.pk = ck.keyword_pk
		WHERE ck.code_pk = :code_pk
		ORDER BY k.label ASC
	"""), {"code_pk": code.pk}).fetchall()
	if keyword_rows:
		for row in keyword_rows:
			paren_match = re.search(r'\(([^)]+)\)', row.label)
			display = paren_match.group(1) if paren_match else row.label
			if has_other_match_domain(display):
				mission_matches.append({'keyword': display, 'search': display})
	else:
		# Fallback: detect missions/surveys from abstract (case-sensitive)
		# Tuples: (match_string, display_label) — plain strings use same for both
		MISSION_FALLBACKS = [
			'JWST', 'Kepler', 'TESS', 'Gaia', 'SDSS', '2MASS', 'Planck',
			('Hubble', 'Hubble'), ('HST', 'Hubble'), 'LSST', 'Spitzer', 'Fermi', 'ALMA', 'Swift',
			'Chandra', 'LIGO', 'WMAP', 'MeerKAT', 'SKA', 'XMM', 'Euclid',
			'Parkes', 'LOFAR', ('Jodrell', 'Jodrell Bank'), 'CARMA',
			('PanSTARRS', 'PanSTARRS'), ('Pan-STARRS', 'PanSTARRS'),
			'Roman', 'GALEX', 'WISE', 'DESI', 'APOGEE', 'Herschel',
			('Canada-France', 'CFHT'), 'CFHT',
		]
		abstract_text_check = code.abstract or ''
		seen_displays = set()
		for mission in MISSION_FALLBACKS:
			if isinstance(mission, tuple):
				match_str, display = mission
			else:
				match_str, display = mission, mission
			if match_str in abstract_text_check and display not in seen_displays:
				if has_other_match_domain(display):
					mission_matches.append({'keyword': display, 'search': display})
					seen_displays.add(display)
	random.shuffle(mission_matches)

	# Discovery bar: programming language pill
	# Matched with word boundaries to avoid false positives (e.g. "Rust" in "robust")
	# C++ uses plain string check since '+' is a regex metacharacter
	LANGUAGE_TERMS = [
		'Python', 'Fortran', 'IDL', 'C++', 'Julia', 'Java', 'MATLAB',
		'CUDA', 'Mathematica', 'Cython', 'Perl', 'Rust', 'yt',
		'JavaScript', 'MPI', 'GPU', 'OpenMP', 'OpenCL', 'IRAF', 'PGPLOT', 'AIPS',
		'Starlink', 'HDF5',
	]
	def has_other_match_language(lang):
		"""Check if at least one other published code matches this language."""
		if lang == 'C++':
			return session.execute(text("""
				SELECT 1 FROM public_codes
				WHERE abstract LIKE :pattern AND pk != :code_pk LIMIT 1
			"""), {"pattern": "%C++%", "code_pk": code.pk}).first() is not None
		return session.execute(text("""
			SELECT 1 FROM public_codes
			WHERE abstract REGEXP CONCAT('\\\\b', :lang, '\\\\b')
			  AND pk != :code_pk LIMIT 1
		"""), {"lang": lang, "code_pk": code.pk}).first() is not None

	abstract_text = code.abstract or ''
	code_languages = []
	for lang in LANGUAGE_TERMS:
		# C++ needs plain string check ('+' is a regex metacharacter)
		if lang == 'C++':
			if 'C++' in abstract_text and has_other_match_language(lang):
				code_languages.append(lang)
		elif lang == 'Fortran':
			# Match "Fortran", "Fortran 77", "Fortran77", "FORTRAN" etc.
			if re.search(r'\bFortran\b', abstract_text, re.IGNORECASE) and has_other_match_language(lang):
				code_languages.append(lang)
		elif re.search(r'\b' + lang + r'\b', abstract_text, re.IGNORECASE) and has_other_match_language(lang):
			code_languages.append(lang)

	random.shuffle(code_languages)

	keywords = [row.label for row in keyword_rows]

	# Discovery bar: check if "Referenced by" pill should appear
	from ascl_net_app.controllers.browse import has_referenced_by
	show_referenced_by = has_referenced_by(session, code.ascl_id, code.pk, code.title)

	templateDict = {
		'code': code,
		'site_links': site_links,
		'described_in_links': described_in_links,
		'used_in_links': used_in_links,
		'ref_links': ref_links,
		'emac_links': emac_links,
		'untyped_links': untyped_links,
		'keywords': keywords,
		'has_keywords': has_keywords,
		'show_referenced_by': show_referenced_by,
		'author_count': author_count,
		'author_has_other_codes': author_has_other_codes,
		'domain_matches': domain_matches,
		'mission_matches': mission_matches,
		'code_languages': code_languages,
	}

	return render_template("code_detail.html", **templateDict)


@code_detail_page.route("/delete_link/<int:link_pk>", methods=['POST'])
def delete_link(link_pk):
	"""Delete an untyped link (admin only)."""
	if not session.get("user_id"):
		abort(403)

	from ascl_net_app.model.database import Database
	db = Database()

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
