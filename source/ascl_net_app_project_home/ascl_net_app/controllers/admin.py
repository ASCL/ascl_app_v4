#!/usr/bin/python

import hashlib
import json
from functools import wraps

import flask
from flask import render_template, request, redirect, url_for, session, flash
import bcrypt

admin_page = flask.Blueprint("admin_page", __name__, url_prefix="/admin")


# ==========================================
# Password Hashing Utilities
# ==========================================

def _hash_password_bcrypt(password):
	"""Hash a password using bcrypt.

	Args:
		password (str): Plain text password

	Returns:
		str: Bcrypt hash (60 characters, $2b$ prefix)
	"""
	return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def _hash_password_sha1(password):
	"""Hash a password using SHA-1 (legacy, for backward compatibility only).

	Args:
		password (str): Plain text password

	Returns:
		str: SHA-1 hash (40 hex characters)
	"""
	return hashlib.sha1(password.encode('utf-8')).hexdigest()


def _verify_password(password, stored_hash):
	"""Verify a password against a stored hash (bcrypt or SHA-1).

	This function supports both bcrypt and legacy SHA-1 hashes for backward compatibility.

	Args:
		password (str): Plain text password to verify
		stored_hash (str): Stored hash (bcrypt or SHA-1 format)

	Returns:
		tuple: (is_valid, is_legacy)
			is_valid (bool): True if password matches
			is_legacy (bool): True if stored_hash is SHA-1 (needs migration)
	"""
	if not password or not stored_hash:
		return (False, False)

	# Check if it's a bcrypt hash (starts with $2a$, $2b$, or $2y$)
	if stored_hash.startswith('$2'):
		try:
			is_valid = bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8'))
			return (is_valid, False)  # Valid bcrypt hash, not legacy
		except Exception:
			return (False, False)

	# Legacy SHA-1 hash (40 hex characters)
	elif len(stored_hash) == 40:
		sha1_hash = _hash_password_sha1(password)
		is_valid = (sha1_hash == stored_hash)
		return (is_valid, True)  # Legacy SHA-1, needs migration

	# Unknown hash format
	return (False, False)


def _migrate_user_password(user, password, db_session):
	"""Migrate a user's password from SHA-1 to bcrypt.

	This function should be called after successful authentication with a legacy SHA-1 hash.
	It upgrades the password to bcrypt automatically without requiring password reset.

	Args:
		user: User object from database
		password (str): Plain text password (from successful login)
		db_session: SQLAlchemy database session
	"""
	new_hash = _hash_password_bcrypt(password)
	user.password = new_hash
	db_session.commit()
	flask.current_app.logger.info(f"Migrated user '{user.username}' from SHA-1 to bcrypt")


# ==========================================
# Session and Authentication
# ==========================================

def _get_db_session():
	from ascl_net_app.model.database import Database
	return Database().Session()


def _get_models():
	import ascl_core.database.ascldb.ASCLModelClasses as ascldb
	return ascldb


def _split_credit_text(credit_text):
	"""Split semicolon-delimited credit string into ordered author tokens."""
	if not credit_text:
		return []
	return [token.strip() for token in credit_text.split(";") if token.strip()]


def _credit_text_from_authors(code):
	"""Build display credit string from related author rows when available."""
	authors = getattr(code, "authors", None)
	if not authors:
		return getattr(code, "credit", "") or ""
	names = []
	for author in authors:
		name = (getattr(author, "display_name", None) or getattr(author, "raw_name", None) or "").strip()
		if name:
			names.append(name)
	return "; ".join(names)


def _sync_authors_from_credit(db_session, ascldb, code_pk, credit_text):
	"""Replace author rows for a code from semicolon-delimited credit text."""
	if not hasattr(ascldb, "Author"):
		return

	db_session.query(ascldb.Author).filter(ascldb.Author.code_pk == code_pk).delete()
	raw_credit_text = credit_text.strip() if credit_text else ""
	for idx, token in enumerate(_split_credit_text(credit_text)):
		author = ascldb.Author()
		author.code_pk = code_pk
		author.display_order = idx
		author.raw_name = token
		author.display_name = token
		author.raw_credit_text = raw_credit_text
		author.orcid_id = None
		author.email = None
		db_session.add(author)


def _current_user(db_session=None):
	ascldb = _get_models()
	user_id = session.get("user_id")
	if not user_id:
		return None
	db_session = db_session or _get_db_session()
	return db_session.query(ascldb.User).filter(ascldb.User.pk == user_id).one_or_none()


def _login_required(view_func):
	@wraps(view_func)
	def wrapper(*args, **kwargs):
		if not session.get("user_id"):
			flash("Please log in to access admin tools.", "error")
			return redirect(url_for("admin_page.admin_home"))
		return view_func(*args, **kwargs)

	return wrapper


@admin_page.route("/", methods=["GET"])
def admin_home():
	db_session = _get_db_session()
	ascldb = _get_models()

	attention_count = 0
	current_usr = _current_user(db_session)

	# Count notes needing attention (only if logged in and tables exist)
	if current_usr:
		try:
			attention_count = (
				db_session.query(ascldb.CodeNote)
				.join(ascldb.NoteType)
				.filter(
					ascldb.NoteType.short_name == 'attention',
					ascldb.CodeNote.hidden == False
				)
				.count()
			)
		except Exception:
			# Tables may not exist yet
			attention_count = 0

	# Count pending corrections
	correction_count = 0
	if current_usr:
		try:
			from sqlalchemy import text as sa_text
			correction_count = db_session.execute(sa_text(
				"SELECT COUNT(*) FROM code_correction WHERE status = 'pending'"
			)).scalar()
		except Exception:
			correction_count = 0

	return render_template(
		"admin/home.html",
		current_user=current_usr,
		attention_count=attention_count,
		correction_count=correction_count,
	)


@admin_page.route("/dashboard", methods=["GET"])
@_login_required
def admin_dashboard():
	"""Dashboard rendered inside the admin layout (with sidebar)."""
	from ascl_net_app.controllers.dashboard import _build_dashboard_context
	ctx = _build_dashboard_context()
	return render_template("admin/dashboard.html", **ctx)


@admin_page.route("/login", methods=["POST"])
def admin_login():
	username = request.form.get("username", "").strip()
	password = request.form.get("password", "")
	if not username or not password:
		flash("Username and password are required.", "error")
		return redirect(url_for("admin_page.admin_home"))

	db_session = _get_db_session()
	ascldb = _get_models()

	user = db_session.query(ascldb.User).filter(ascldb.User.username == username).one_or_none()

	if not user:
		flash("Invalid username.", "error")
		return redirect(url_for("admin_page.admin_home"))

	# lockout after 10 attempts
	if getattr(user, "login_attempts", 0) >= 9:
		user.login_attempts = getattr(user, "login_attempts", 0) + 1
		db_session.commit()
		flash("Number of login attempts exceeded. Please contact an administrator.", "error")
		return redirect(url_for("admin_page.admin_home"))

	# Verify password (supports both bcrypt and legacy SHA-1)
	is_valid, is_legacy = _verify_password(password, user.password)

	if not is_valid:
		user.login_attempts = getattr(user, "login_attempts", 0) + 1
		db_session.commit()
		flash("Invalid password.", "error")
		return redirect(url_for("admin_page.admin_home"))

	# Success: reset attempts and store session info
	user.login_attempts = 0
	db_session.commit()

	# Automatically migrate legacy SHA-1 passwords to bcrypt
	if is_legacy:
		_migrate_user_password(user, password, db_session)
		flask.current_app.logger.info(f"User '{username}' password automatically upgraded to bcrypt")

	session["user_id"] = getattr(user, "id", None) or getattr(user, "pk", None)
	session["username"] = user.username
	flash("Login success.", "success")

	return redirect(url_for("admin_page.admin_home"))


@admin_page.route("/user_cp", methods=["GET"])
@_login_required
def user_cp():
	db_session = _get_db_session()
	current_usr = _current_user(db_session)
	return render_template(
		"admin/user_cp.html",
		current_user=current_usr,
	)


@admin_page.route("/update_user", methods=["POST"])
@_login_required
def update_user():
	db_session = _get_db_session()
	current_usr = _current_user(db_session)

	real_name = request.form.get("real_name", "").strip()
	if not real_name:
		flash("Real name is required.", "error")
	else:
		current_usr.real_name = real_name
		db_session.commit()
		flash("User info updated.", "success")

	return redirect(url_for("admin_page.user_cp"))


@admin_page.route("/update_password", methods=["POST"])
@_login_required
def update_password():
	db_session = _get_db_session()
	current_usr = _current_user(db_session)

	current_password = request.form.get("password", "")
	new_password = request.form.get("new_password", "")
	new_password_confirm = request.form.get("new_password_confirm", "")

	if not current_password or not new_password or not new_password_confirm:
		flash("All password fields are required.", "error")
		return redirect(url_for("admin_page.user_cp"))

	if len(new_password) < 8:
		flash("New password must be at least 8 characters.", "error")
		return redirect(url_for("admin_page.user_cp"))

	if new_password != new_password_confirm:
		flash("New passwords do not match.", "error")
		return redirect(url_for("admin_page.user_cp"))

	# Check lockout
	if getattr(current_usr, "login_attempts", 0) >= 9:
		session.clear()
		flash("Too many failed attempts. You have been logged out.", "error")
		return redirect(url_for("admin_page.admin_home"))

	# Verify current password
	is_valid, _ = _verify_password(current_password, current_usr.password)
	if not is_valid:
		current_usr.login_attempts = getattr(current_usr, "login_attempts", 0) + 1
		db_session.commit()
		flash("Current password is incorrect.", "error")
		return redirect(url_for("admin_page.user_cp"))

	# Update password
	current_usr.password = _hash_password_bcrypt(new_password)
	current_usr.login_attempts = 0
	db_session.commit()
	flash("Password updated.", "success")

	return redirect(url_for("admin_page.user_cp"))


@admin_page.route("/logout", methods=["GET"])
def admin_logout():
	session.clear()
	flash("Logged out.", "info")
	return redirect(url_for("admin_page.admin_home"))


@admin_page.route("/unpublished", methods=["GET"])
@_login_required
def unpublished_codes():
	from sqlalchemy.orm import selectinload

	db_session = _get_db_session()
	ascldb = _get_models()

	# Pagination parameters (per_page=0 means show all)
	page = int(request.args.get("page", 1))
	per_page = int(request.args.get("per_page", 50))

	load_options = [selectinload(ascldb.ASCLCode.keywords)]
	if hasattr(ascldb.ASCLCode, "authors"):
		load_options.append(selectinload(ascldb.ASCLCode.authors))

	base_query = (
		db_session.query(ascldb.ASCLCode)
		.options(*load_options)
		.filter(ascldb.ASCLCode.published == 0, ascldb.ASCLCode.archived == 0)
	)

	total_count = base_query.count()

	if per_page == 0:
		# Show all results
		codes = (
			base_query
			.order_by(ascldb.ASCLCode.pk.desc())
			.all()
		)
		total_pages = 1
	else:
		codes = (
			base_query
			.order_by(ascldb.ASCLCode.pk.desc())
			.offset((page - 1) * per_page)
			.limit(per_page)
			.all()
		)
		import math
		total_pages = math.ceil(total_count / per_page) if per_page > 0 else 1

	# Build credit text for card view
	codes_credit = {code.pk: _credit_text_from_authors(code) for code in codes}

	return render_template(
		"admin/unpublished.html",
		page_title="Unpublished Codes",
		codes=codes,
		codes_credit=codes_credit,
		current_user=_current_user(db_session),
		page=page,
		per_page=per_page,
		total_count=total_count,
		total_pages=total_pages,
	)


@admin_page.route("/archived", methods=["GET"])
@_login_required
def archived_codes():
	from sqlalchemy.orm import selectinload

	db_session = _get_db_session()
	ascldb = _get_models()

	# Pagination parameters (per_page=0 means show all)
	page = int(request.args.get("page", 1))
	per_page = int(request.args.get("per_page", 50))

	base_query = (
		db_session.query(ascldb.ASCLCode)
		.options(selectinload(ascldb.ASCLCode.keywords))
		.filter(ascldb.ASCLCode.archived == 1)
	)

	total_count = base_query.count()

	if per_page == 0:
		# Show all results
		codes = (
			base_query
			.order_by(ascldb.ASCLCode.time_added.desc(), ascldb.ASCLCode.pk.desc())
			.all()
		)
		total_pages = 1
	else:
		codes = (
			base_query
			.order_by(ascldb.ASCLCode.time_added.desc(), ascldb.ASCLCode.pk.desc())
			.offset((page - 1) * per_page)
			.limit(per_page)
			.all()
		)
		import math
		total_pages = math.ceil(total_count / per_page) if per_page > 0 else 1

	return render_template(
		"admin/codes_list.html",
		page_title="Archived Codes",
		codes=codes,
		current_user=_current_user(db_session),
		page=page,
		per_page=per_page,
		total_count=total_count,
		total_pages=total_pages,
		list_type="archived",
	)


@admin_page.route("/notes/attention", methods=["GET"])
@_login_required
def notes_attention():
	"""List all notes that need attention."""
	db_session = _get_db_session()
	ascldb = _get_models()

	try:
		notes = (
			db_session.query(ascldb.CodeNote)
			.join(ascldb.NoteType)
			.join(ascldb.ASCLCode)
			.filter(
				ascldb.NoteType.short_name == 'attention',
				ascldb.CodeNote.hidden == False
			)
			.order_by(ascldb.CodeNote.is_pinned.desc(), ascldb.CodeNote.created_at.desc())
			.all()
		)
	except Exception as e:
		flash(f"Error loading notes: {e}", "error")
		notes = []

	return render_template(
		"admin/notes_attention.html",
		notes=notes,
		current_user=_current_user(db_session),
	)


# ==========================================
# Code Management Routes
# ==========================================

@admin_page.route("/view/<int:pk>", methods=["GET"])
@_login_required
def view_code(pk):
	"""View a code's details (admin view with all fields)."""
	db_session = _get_db_session()
	ascldb = _get_models()

	code = db_session.query(ascldb.ASCLCode).filter(ascldb.ASCLCode.pk == pk).one_or_none()
	if not code:
		flash("Code not found.", "error")
		return redirect(url_for("admin_page.admin_home"))

	# Get aliases as space-separated string
	aliases_str = " ".join([a.alias for a in code.aliases]) if code.aliases else ""

	# Get keywords as space-separated string
	keywords_str = " ".join([k.label for k in code.keywords]) if code.keywords else ""

	# Get links from link table
	site_urls = _get_links_for_code(db_session, ascldb, pk, 'code-site')
	reference_urls = _get_links_for_code(db_session, ascldb, pk, 'refereed')
	described_in_urls = _get_links_for_code(db_session, ascldb, pk, 'described-in')
	used_in_urls = _get_links_for_code(db_session, ascldb, pk, 'used-in')

	# Get see_also as space-separated ASCL IDs
	see_also_str = _get_see_also_for_code(db_session, pk)

	return render_template(
		"admin/view_code.html",
		code=code,
		aliases_str=aliases_str,
		keywords_str=keywords_str,
		site_urls=site_urls,
		reference_urls=reference_urls,
		described_in_urls=described_in_urls,
		used_in_urls=used_in_urls,
		see_also_str=see_also_str,
		current_user=_current_user(db_session),
	)


@admin_page.route("/update_code/<int:pk>", methods=["GET", "POST"])
@_login_required
def update_code(pk):
	"""Edit an existing code."""
	db_session = _get_db_session()
	ascldb = _get_models()

	code = db_session.query(ascldb.ASCLCode).filter(ascldb.ASCLCode.pk == pk).one_or_none()
	if not code:
		flash("Code not found.", "error")
		return redirect(url_for("admin_page.admin_home"))

	if request.method == "POST":
		# Validate required fields
		title = request.form.get("title", "").strip()
		credit = request.form.get("credit", "").strip()
		ascl_id = request.form.get("ascl_id", "").strip()

		if not title:
			flash("Title is required.", "error")
		elif not credit:
			flash("Credit is required.", "error")
		elif not ascl_id or len(ascl_id) != 8:
			flash("ASCL ID must be 8 characters (e.g., 2401.001).", "error")
		else:
			# Check ASCL ID uniqueness (unless it's 0000.000 or unchanged)
			if ascl_id != "0000.000" and ascl_id != code.ascl_id:
				existing = db_session.query(ascldb.ASCLCode).filter(
					ascldb.ASCLCode.ascl_id == ascl_id,
					ascldb.ASCLCode.pk != pk
				).first()
				if existing:
					flash(f"ASCL ID {ascl_id} is already in use.", "error")
					return render_template(
						"admin/edit_code.html",
						code=code,
						mode="update",
						current_user=_current_user(db_session),
					)

			# Track if we're publishing for the first time
			was_unpublished = code.published == 0
			new_published = int(request.form.get("published", 0))

			# Update code fields
			code.ascl_id = ascl_id
			code.title = title
			code.credit = credit
			_sync_authors_from_credit(db_session, ascldb, pk, credit)
			code.abstract = request.form.get("abstract", "").strip()
			code.citation_method = request.form.get("citation_method", "").strip()
			code.email = request.form.get("email", "").strip()
			code.notes = request.form.get("notes", "").strip()
			code.published = new_published
			code.doi = request.form.get("doi", "").strip()

			# Update time_added if first-time publish
			from datetime import datetime
			if was_unpublished and new_published == 1:
				code.time_added = datetime.now()

			code.time_updated = datetime.now()

			# Generate bibcode if publishing
			if new_published == 1 and ascl_id != "0000.000":
				century = getattr(code, "century", "20")
				if not century:
					century = "20"
				code.bibcode = f"{century}{ascl_id[:2]}ascl.soft{ascl_id[2:4]}{ascl_id[5:8]}{credit[0].upper()}"

			# Update aliases
			_update_aliases(db_session, ascldb, pk, request.form.get("aliases", ""))

			# Update keywords
			_update_keywords(db_session, ascldb, pk, request.form.get("keywords", ""))

			# Update links (stored in link table, not codes table)
			_update_all_typed_links(db_session, ascldb, pk, request.form.get("typed_links", ""))
			_update_links_for_code(db_session, ascldb, pk, 'described-in', request.form.get("described_in_urls", ""))
			_update_links_for_code(db_session, ascldb, pk, 'used-in', request.form.get("used_in_urls", ""))

			# Update see_also relationships
			_update_see_also_for_code(db_session, ascldb, pk, request.form.get("see_also", ""))

			db_session.commit()
			flash(f"Code updated successfully. <a href='/{code.ascl_id}'>View it here</a>.", "success")
			return redirect(url_for("admin_page.view_code", pk=pk))

	# GET request - load current data
	# Get aliases as space-separated string
	aliases_str = " ".join([a.alias for a in code.aliases]) if code.aliases else ""
	credits_str = _credit_text_from_authors(code)

	# Get keywords as space-separated string (quote keywords with spaces)
	keywords_list = []
	for k in code.keywords:
		if " " in k.label:
			keywords_list.append(f'"{k.label}"')
		else:
			keywords_list.append(k.label)
	keywords_str = " ".join(keywords_list)

	# Get links from link table
	import json
	url_link_types = _get_url_link_types(db_session)
	typed_links = _get_all_typed_links_for_code(db_session, pk)
	described_in_urls = _get_links_for_code(db_session, ascldb, pk, 'described-in')
	used_in_urls = _get_links_for_code(db_session, ascldb, pk, 'used-in')

	# Get see_also as space-separated ASCL IDs
	see_also_str = _get_see_also_for_code(db_session, pk)

	return render_template(
		"admin/edit_code.html",
		code=code,
		mode="update",
		credits_str=credits_str,
		aliases_str=aliases_str,
		keywords_str=keywords_str,
		url_link_types=url_link_types,
		typed_links_json=json.dumps(typed_links),
		described_in_urls=described_in_urls,
		used_in_urls=used_in_urls,
		see_also_str=see_also_str,
		all_keywords_json=json.dumps(_get_all_keyword_labels(db_session)),
		current_user=_current_user(db_session),
	)


@admin_page.route("/archive_code/<int:pk>", methods=["GET", "POST"])
@_login_required
def archive_code(pk):
	"""Toggle archived status of a code."""
	db_session = _get_db_session()
	ascldb = _get_models()

	code = db_session.query(ascldb.ASCLCode).filter(ascldb.ASCLCode.pk == pk).one_or_none()
	if not code:
		flash("Code not found.", "error")
		return redirect(url_for("admin_page.admin_home"))

	# Toggle archived status
	code.archived = 0 if code.archived == 1 else 1
	db_session.commit()

	action = "archived" if code.archived == 1 else "unarchived"
	flash(f"Code {action}. <a href='/admin/archive_code/{pk}'>Undo</a>", "success")

	# Redirect back to appropriate list
	if code.archived == 1:
		return redirect(url_for("admin_page.archived_codes"))
	else:
		return redirect(url_for("admin_page.unpublished_codes"))


@admin_page.route("/insert_code", methods=["GET", "POST"])
@_login_required
def insert_code():
	"""Add a new code."""
	from datetime import datetime

	db_session = _get_db_session()
	ascldb = _get_models()

	if request.method == "POST":
		# Validate required fields
		title = request.form.get("title", "").strip()
		credit = request.form.get("credit", "").strip()
		ascl_id = request.form.get("ascl_id", "").strip()

		if not title:
			flash("Title is required.", "error")
		elif not credit:
			flash("Credit is required.", "error")
		elif not ascl_id or len(ascl_id) != 8:
			flash("ASCL ID must be 8 characters (e.g., 2401.001).", "error")
		else:
			# Check ASCL ID uniqueness (unless it's 0000.000)
			if ascl_id != "0000.000":
				existing = db_session.query(ascldb.ASCLCode).filter(
					ascldb.ASCLCode.ascl_id == ascl_id
				).first()
				if existing:
					# ASCL ID collision - re-render form with collision notice
					# Recreate a mock code with the submitted data so user doesn't lose work
					class MockCode:
						pass
					mock_code = MockCode()
					mock_code.pk = None
					mock_code.ascl_id = ascl_id
					mock_code.title = title
					mock_code.credit = credit
					mock_code.abstract = request.form.get("abstract", "").strip()
					mock_code.citation_method = request.form.get("citation_method", "").strip()
					mock_code.email = request.form.get("email", "").strip()
					mock_code.notes = request.form.get("notes", "").strip()
					mock_code.published = int(request.form.get("published", 0))
					mock_code.doi = request.form.get("doi", "").strip()
					mock_code.bibcode = request.form.get("bibcode", "").strip()

					return render_template(
						"admin/edit_code.html",
						code=mock_code,
						mode="insert",
						credits_str=credit,
						ascl_id_collision=ascl_id,
						aliases_str=request.form.get("aliases", ""),
						keywords_str=request.form.get("keywords", ""),
						url_link_types=_get_url_link_types(db_session),
						typed_links_json=request.form.get("typed_links", "[]"),
						described_in_urls=request.form.get("described_in_urls", ""),
						used_in_urls=request.form.get("used_in_urls", ""),
						see_also_str=request.form.get("see_also", ""),
						all_keywords_json=json.dumps(_get_all_keyword_labels(db_session)),
						current_user=_current_user(db_session),
					)

			# Create new code
			code = ascldb.ASCLCode()
			code.ascl_id = ascl_id
			code.title = title
			code.credit = credit
			code.abstract = request.form.get("abstract", "").strip()
			code.citation_method = request.form.get("citation_method", "").strip()
			code.email = request.form.get("email", "").strip()
			code.notes = request.form.get("notes", "").strip()
			code.published = int(request.form.get("published", 0))
			code.doi = request.form.get("doi", "").strip()
			code.time_added = datetime.now()
			code.time_updated = datetime.now()
			code.archived = 0

			# Set added_by from current user
			current_user = _current_user(db_session)
			if current_user:
				code.added_by = current_user.pk

			# Generate bibcode if publishing
			if code.published == 1 and ascl_id != "0000.000":
				code.century = "20"  # Default century
				code.bibcode = f"20{ascl_id[:2]}ascl.soft{ascl_id[2:4]}{ascl_id[5:8]}{credit[0].upper()}"

			db_session.add(code)
			db_session.flush()  # Get the PK

			pk = code.pk
			_sync_authors_from_credit(db_session, ascldb, pk, credit)

			# Add aliases
			_update_aliases(db_session, ascldb, pk, request.form.get("aliases", ""))

			# Add keywords
			_update_keywords(db_session, ascldb, pk, request.form.get("keywords", ""))

			# Add links (stored in link table)
			_update_all_typed_links(db_session, ascldb, pk, request.form.get("typed_links", ""))
			_update_links_for_code(db_session, ascldb, pk, 'described-in', request.form.get("described_in_urls", ""))
			_update_links_for_code(db_session, ascldb, pk, 'used-in', request.form.get("used_in_urls", ""))

			# Add see_also relationships
			_update_see_also_for_code(db_session, ascldb, pk, request.form.get("see_also", ""))

			db_session.commit()
			flash(f"Code added successfully. <a href='/{code.ascl_id}'>View it here</a>.", "success")
			return redirect(url_for("admin_page.view_code", pk=pk))

	# GET request - show empty form
	# Create a mock code object for template compatibility
	class MockCode:
		def __init__(self):
			self.pk = None
			self.ascl_id = "0000.000"
			self.title = ""
			self.credit = ""
			self.abstract = ""
			self.citation_method = ""
			self.email = ""
			self.notes = ""
			self.published = 0
			self.doi = ""

	return render_template(
		"admin/edit_code.html",
		code=MockCode(),
		mode="insert",
		credits_str="",
		aliases_str="",
		keywords_str="",
		url_link_types=_get_url_link_types(db_session),
		typed_links_json="[]",
		described_in_urls="",
		used_in_urls="",
		see_also_str="",
		all_keywords_json=json.dumps(_get_all_keyword_labels(db_session)),
		current_user=_current_user(db_session),
	)


@admin_page.route("/delete_code/<int:pk>", methods=["GET", "POST"])
@_login_required
def delete_code(pk):
	"""Delete a code (with confirmation)."""
	db_session = _get_db_session()
	ascldb = _get_models()

	code = db_session.query(ascldb.ASCLCode).filter(ascldb.ASCLCode.pk == pk).one_or_none()
	if not code:
		flash("Code not found.", "error")
		return redirect(url_for("admin_page.admin_home"))

	if request.method == "POST":
		# Delete related records first (due to FK constraints)
		db_session.query(ascldb.ASCLCodeAlias).filter(ascldb.ASCLCodeAlias.code_pk == pk).delete()
		db_session.query(ascldb.ASCLCodeToKeyword).filter(ascldb.ASCLCodeToKeyword.code_pk == pk).delete()

		# Delete the code
		db_session.delete(code)
		db_session.commit()

		flash("Code deleted.", "success")
		return redirect(url_for("admin_page.admin_home"))

	return render_template(
		"admin/delete_code.html",
		code=code,
		current_user=_current_user(db_session),
	)


# ==========================================
# Helper Functions for Code Management
# ==========================================

def _get_link_type_pk(db_session, ascldb, short_name):
	"""Get or create a link_type pk by short_name."""
	link_type = db_session.query(ascldb.LinkType).filter(
		ascldb.LinkType.short_name == short_name
	).first()
	if link_type:
		return link_type.pk
	# Create if doesn't exist
	new_type = ascldb.LinkType()
	new_type.short_name = short_name
	new_type.name = short_name.replace('-', ' ').title()
	db_session.add(new_type)
	db_session.flush()
	return new_type.pk


def _get_all_keyword_labels(db_session):
	"""Return sorted list of all keyword labels for typeahead."""
	ascldb = _get_models()
	rows = db_session.query(ascldb.Keyword.label).order_by(ascldb.Keyword.label).all()
	return [r.label for r in rows]


def _get_url_link_types(db_session):
	"""Get all link types except described-in and used-in (those have special bibcode UI).
	Returns list of {pk, short_name, name, description}."""
	from sqlalchemy import text
	results = db_session.execute(text("""
		SELECT pk, short_name, name, description FROM link_type
		WHERE short_name NOT IN ('described-in', 'used-in')
		ORDER BY CASE short_name
			WHEN 'code-site' THEN 0
			WHEN 'refereed' THEN 1
			WHEN 'emac' THEN 2
			ELSE 3
		END, pk
	""")).fetchall()
	return [
		{"pk": row.pk, "short_name": row.short_name, "name": row.name, "description": row.description}
		for row in results
	]


def _get_all_typed_links_for_code(db_session, code_pk):
	"""Get all URL-type links for a code (excludes described-in and used-in).
	Returns list of {url, type} ordered by display_order."""
	from sqlalchemy import text
	results = db_session.execute(text("""
		SELECT l.url, lt.short_name as type
		FROM link l
		JOIN link_type lt ON l.link_type_pk = lt.pk
		WHERE l.code_pk = :code_pk AND lt.short_name NOT IN ('described-in', 'used-in')
		ORDER BY l.display_order, l.pk
	"""), {"code_pk": code_pk}).fetchall()
	return [{"url": row.url, "type": row.type} for row in results]


def _update_all_typed_links(db_session, ascldb, code_pk, links_json_str):
	"""Update URL-type links from JSON array of {url, type, display_order}.
	Deletes existing URL-type links (not described-in/used-in), inserts new ones."""
	import json
	from sqlalchemy import text

	# Delete existing URL-type links (not described-in or used-in)
	db_session.execute(text("""
		DELETE l FROM link l
		JOIN link_type lt ON l.link_type_pk = lt.pk
		WHERE l.code_pk = :code_pk AND lt.short_name NOT IN ('described-in', 'used-in')
	"""), {"code_pk": code_pk})

	if not links_json_str or not links_json_str.strip():
		return

	try:
		links = json.loads(links_json_str)
	except (json.JSONDecodeError, TypeError):
		return

	# Build a short_name → pk cache
	type_cache = {}

	for order, link_data in enumerate(links):
		url = (link_data.get("url") or "").strip()
		type_short = (link_data.get("type") or "").strip()
		if not url or not type_short:
			continue

		if type_short not in type_cache:
			type_cache[type_short] = _get_link_type_pk(db_session, ascldb, type_short)

		new_link = ascldb.Link()
		new_link.code_pk = code_pk
		new_link.url = url
		new_link.link_type_pk = type_cache[type_short]
		new_link.display_order = order
		db_session.add(new_link)


def _get_links_for_code(db_session, ascldb, code_pk, link_type_short_name):
	"""Get URLs for a code by link type, as newline-separated string."""
	from sqlalchemy import text
	query = text("""
		SELECT l.url FROM link l
		JOIN link_type lt ON l.link_type_pk = lt.pk
		WHERE l.code_pk = :code_pk AND lt.short_name = :link_type
		ORDER BY l.display_order, l.pk
	""")
	results = db_session.execute(query, {
		"code_pk": code_pk,
		"link_type": link_type_short_name
	}).fetchall()
	return "\n".join(row.url for row in results)


def _update_links_for_code(db_session, ascldb, code_pk, link_type_short_name, urls_text):
	"""Update links for a code by link type from newline-separated URLs."""
	from sqlalchemy import text

	# Get link_type_pk
	link_type_pk = _get_link_type_pk(db_session, ascldb, link_type_short_name)

	# Delete existing links of this type for this code
	db_session.execute(text("""
		DELETE FROM link WHERE code_pk = :code_pk AND link_type_pk = :link_type_pk
	"""), {"code_pk": code_pk, "link_type_pk": link_type_pk})

	if not urls_text or not urls_text.strip():
		return

	# Insert new links
	urls = [url.strip() for url in urls_text.strip().split("\n") if url.strip()]
	for order, url in enumerate(urls):
		new_link = ascldb.Link()
		new_link.code_pk = code_pk
		new_link.url = url
		new_link.link_type_pk = link_type_pk
		new_link.display_order = order
		db_session.add(new_link)


def _get_see_also_for_code(db_session, code_pk):
	"""Get see_also ASCL IDs for a code, as space-separated string."""
	from sqlalchemy import text
	query = text("""
		SELECT c.ascl_id FROM code_see_also csa
		JOIN codes c ON csa.related_code_pk = c.pk
		WHERE csa.code_pk = :code_pk
		ORDER BY csa.display_order, csa.pk
	""")
	results = db_session.execute(query, {"code_pk": code_pk}).fetchall()
	return " ".join(row.ascl_id for row in results)


def _update_see_also_for_code(db_session, ascldb, code_pk, see_also_text):
	"""Update see_also relationships from space/semicolon-separated ASCL IDs."""
	from sqlalchemy import text
	import re

	# Delete existing see_also for this code
	db_session.execute(text("""
		DELETE FROM code_see_also WHERE code_pk = :code_pk
	"""), {"code_pk": code_pk})

	if not see_also_text or not see_also_text.strip():
		return

	# Parse ASCL IDs (space or semicolon separated)
	ascl_ids = re.split(r'[;\s]+', see_also_text.strip())
	ascl_ids = [aid.strip() for aid in ascl_ids if aid.strip()]

	# Build lookup of ascl_id -> pk
	if ascl_ids:
		codes = db_session.query(ascldb.ASCLCode.pk, ascldb.ASCLCode.ascl_id).filter(
			ascldb.ASCLCode.ascl_id.in_(ascl_ids)
		).all()
		ascl_lookup = {c.ascl_id: c.pk for c in codes}

		for order, ascl_id in enumerate(ascl_ids):
			related_pk = ascl_lookup.get(ascl_id)
			if related_pk:
				db_session.execute(text("""
					INSERT INTO code_see_also (code_pk, related_code_pk, display_order)
					VALUES (:code_pk, :related_pk, :display_order)
				"""), {"code_pk": code_pk, "related_pk": related_pk, "display_order": order})


def _update_aliases(db_session, ascldb, code_pk, aliases_text):
	"""Update code aliases from space-separated text."""
	# Clear existing aliases
	db_session.query(ascldb.ASCLCodeAlias).filter(ascldb.ASCLCodeAlias.code_pk == code_pk).delete()

	if not aliases_text or not aliases_text.strip():
		return

	# Add new aliases
	aliases = aliases_text.strip().split()
	seen = set()
	for alias in aliases:
		alias = alias.strip().lower()  # Normalize
		if alias and alias not in seen:
			seen.add(alias)
			new_alias = ascldb.ASCLCodeAlias()
			new_alias.code_pk = code_pk
			new_alias.alias = alias
			db_session.add(new_alias)


def _update_keywords(db_session, ascldb, code_pk, keywords_text):
	"""Update code keywords from space-separated text (handles quoted phrases)."""
	import shlex

	# Clear existing keyword associations
	db_session.query(ascldb.ASCLCodeToKeyword).filter(ascldb.ASCLCodeToKeyword.code_pk == code_pk).delete()

	if not keywords_text or not keywords_text.strip():
		return

	# Parse keywords (handles quoted strings with spaces)
	try:
		keywords = shlex.split(keywords_text.replace(",", " "))
	except ValueError:
		keywords = keywords_text.strip().split()

	for kw in keywords:
		kw = kw.strip()
		if not kw:
			continue

		# Check if keyword exists
		existing = db_session.query(ascldb.Keyword).filter(ascldb.Keyword.label == kw).first()
		if existing:
			kw_pk = existing.pk
		else:
			# Create new keyword
			new_kw = ascldb.Keyword()
			new_kw.label = kw
			new_kw.short_name = kw.lower().replace(' ', '-')
			db_session.add(new_kw)
			db_session.flush()  # Get the PK
			kw_pk = new_kw.pk

		# Create association
		assoc = ascldb.ASCLCodeToKeyword()
		assoc.code_pk = code_pk
		assoc.keyword_pk = kw_pk
		db_session.add(assoc)


# ==========================================
# Utility / Raw Data Routes
# ==========================================

@admin_page.route("/utility/full_table", methods=["GET"])
@_login_required
def utility_full_table():
	"""Full ASCL table with all details."""
	db_session = _get_db_session()
	ascldb = _get_models()

	# Get optional filters
	subtype = request.args.get("filter", "")

	query = (
		db_session.query(ascldb.ASCLCode)
		.filter(ascldb.ASCLCode.ascl_id != "0000.000")
	)

	if subtype == "published":
		query = query.filter(ascldb.ASCLCode.published == 1)
	elif subtype == "unpublished":
		query = query.filter(ascldb.ASCLCode.published == 0)

	codes = query.order_by(ascldb.ASCLCode.title).all()

	return render_template(
		"admin/utility_ascl.html",
		codes=codes,
		current_user=_current_user(db_session),
		filter=subtype,
	)


@admin_page.route("/utility/simple_table", methods=["GET"])
@_login_required
def utility_simple_table():
	"""Simple ASCL table with just ID and title."""
	db_session = _get_db_session()
	ascldb = _get_models()

	subtype = request.args.get("filter", "")

	query = (
		db_session.query(ascldb.ASCLCode)
		.filter(ascldb.ASCLCode.ascl_id != "0000.000")
	)

	if subtype == "published":
		query = query.filter(ascldb.ASCLCode.published == 1)
	elif subtype == "unpublished":
		query = query.filter(ascldb.ASCLCode.published == 0)

	codes = query.order_by(ascldb.ASCLCode.century, ascldb.ASCLCode.ascl_id).all()

	return render_template(
		"admin/utility_ascl2.html",
		codes=codes,
		current_user=_current_user(db_session),
		filter=subtype,
	)


@admin_page.route("/utility/all_links", methods=["GET"])
@_login_required
def utility_all_links():
	"""All links as plain text."""
	db_session = _get_db_session()
	ascldb = _get_models()

	# Query from link table
	links = db_session.query(ascldb.Link.url).all()

	# Build plain text output
	output = "\n".join([link.url for link in links if link.url])

	from flask import Response
	return Response(output, mimetype="text/plain; charset=utf-8")


@admin_page.route("/utility/site_links", methods=["GET"])
@_login_required
def utility_site_links_list():
	"""Site links only as plain text."""
	db_session = _get_db_session()
	ascldb = _get_models()

	# Query from link table where link_type is 'code-site' (pk=2)
	links = (
		db_session.query(ascldb.Link.url)
		.filter(ascldb.Link.link_type_pk == 2)
		.all()
	)

	# Build plain text output
	output = "\n".join([link.url for link in links if link.url])

	from flask import Response
	return Response(output, mimetype="text/plain; charset=utf-8")


@admin_page.route("/api/check_ascl_id/<ascl_id>", methods=["GET"])
@_login_required
def check_ascl_id(ascl_id):
	"""Check if an ASCL ID exists in the database. Returns JSON."""
	from flask import jsonify
	import re

	# Validate format: YYMM.NNN
	if not re.match(r'^\d{4}\.\d{3}$', ascl_id):
		return jsonify({"valid": False, "exists": False, "error": "Invalid format"})

	db_session = _get_db_session()
	ascldb = _get_models()

	code = db_session.query(ascldb.ASCLCode).filter(ascldb.ASCLCode.ascl_id == ascl_id).first()

	return jsonify({
		"valid": True,
		"exists": code is not None,
		"title": code.title if code else None
	})


@admin_page.route("/api/next_ascl_id", methods=["GET"])
@_login_required
def next_ascl_id():
	"""Get the next available ASCL ID for the current month. Returns JSON."""
	from flask import jsonify
	from datetime import datetime

	db_session = _get_db_session()
	ascldb = _get_models()

	current_yymm = datetime.now().strftime("%y%m")

	# Find highest ASCL ID for current month
	latest = (
		db_session.query(ascldb.ASCLCode)
		.filter(ascldb.ASCLCode.ascl_id.like(f"{current_yymm}.%"))
		.order_by(ascldb.ASCLCode.ascl_id.desc())
		.first()
	)

	if latest and latest.ascl_id:
		try:
			last_num = int(latest.ascl_id.split(".")[1])
			next_num = last_num + 1
		except (ValueError, IndexError):
			next_num = 1
	else:
		next_num = 1

	next_id = f"{current_yymm}.{next_num:03d}"

	return jsonify({"next_ascl_id": next_id})


@admin_page.route("/api/keyword_count/<path:keyword>", methods=["GET"])
@_login_required
def keyword_count(keyword):
	"""Get the count of codes using a keyword. Returns JSON."""
	from flask import jsonify
	from sqlalchemy import func

	db_session = _get_db_session()
	ascldb = _get_models()

	# Count codes with this keyword (case-insensitive)
	count = db_session.query(func.count(ascldb.ASCLCodeToKeyword.code_pk)).join(
		ascldb.Keyword,
		ascldb.ASCLCodeToKeyword.keyword_pk == ascldb.Keyword.pk
	).filter(
		func.lower(ascldb.Keyword.label) == keyword.lower()
	).scalar() or 0

	return jsonify({"keyword": keyword, "count": count})


@admin_page.route("/api/check_alias/<alias>", methods=["GET"])
@_login_required
def check_alias(alias):
	"""Check if an alias is already used by another code. Returns JSON."""
	from flask import jsonify

	db_session = _get_db_session()
	ascldb = _get_models()

	# Optional: exclude a specific code_pk when editing
	exclude_pk = request.args.get("exclude_pk", type=int)

	# Check if alias exists (case-insensitive)
	query = db_session.query(ascldb.ASCLCodeAlias).filter(
		ascldb.ASCLCodeAlias.alias == alias.lower()
	)

	if exclude_pk:
		query = query.filter(ascldb.ASCLCodeAlias.code_pk != exclude_pk)

	existing = query.first()

	if existing:
		# Get the code that uses this alias
		code = db_session.query(ascldb.ASCLCode).filter(
			ascldb.ASCLCode.pk == existing.code_pk
		).first()
		return jsonify({
			"available": False,
			"used_by_ascl_id": code.ascl_id if code else None,
			"used_by_title": code.title if code else None
		})

	return jsonify({"available": True})


@admin_page.route("/api/typesense_status", methods=["GET"])
@_login_required
def typesense_status():
	"""Return live Typesense connectivity/auth status for admin debugging."""
	from flask import jsonify
	from ascl_net_app.services.typesense_client import get_typesense_client

	try:
		typesense = get_typesense_client()
		healthy = typesense.is_healthy(force_check=True)
		stats = typesense.get_stats() if healthy else None

		return jsonify({
			"enabled": bool(typesense.enabled),
			"base_url": typesense.base_url,
			"collection": typesense.collection,
			"healthy": bool(healthy),
			"authenticated": stats is not None,
			"fallback_to_mysql": bool(typesense.fallback_to_mysql),
			"num_documents": (stats or {}).get("num_documents"),
		})
	except Exception:
		flask.current_app.logger.exception("Typesense status check failed")
		return jsonify({"error": "Typesense status check failed"}), 500


@admin_page.route("/api/normalize_name", methods=["POST"])
@_login_required
def normalize_name():
	"""Normalize an author name to 'Last, First M.' format. Returns JSON."""
	from flask import jsonify
	from nameparser import HumanName

	data = request.get_json()
	if not data or "name" not in data:
		return jsonify({"error": "Missing 'name' field"}), 400

	name_input = data["name"].strip()
	if not name_input:
		return jsonify({"error": "Empty name"}), 400

	# Parse the name
	name = HumanName(name_input)

	# Build normalized format: "Last, First M."
	parts = []

	# Last name (including suffix like Jr., III, etc.)
	last = name.last
	if name.suffix:
		last = f"{last} {name.suffix}"

	if last:
		parts.append(last)

	# First name and middle initial(s)
	first_parts = []
	if name.first:
		first_parts.append(name.first)
	if name.middle:
		# Convert middle names to initials
		middle_initials = " ".join(
			m[0] + "." if len(m) > 1 and not m.endswith(".") else m
			for m in name.middle.split()
		)
		first_parts.append(middle_initials)

	if first_parts:
		if parts:
			parts[0] += ","
		parts.extend(first_parts)

	normalized = " ".join(parts) if parts else name_input

	return jsonify({
		"original": name_input,
		"normalized": normalized,
		"parsed": {
			"first": name.first,
			"middle": name.middle,
			"last": name.last,
			"suffix": name.suffix,
			"title": name.title
		}
	})


@admin_page.route("/api/check_url", methods=["POST"])
@_login_required
def check_url():
	"""Check if a URL is reachable. Returns JSON with status."""
	from flask import jsonify
	import requests

	data = request.get_json()
	if not data or "url" not in data:
		return jsonify({"error": "Missing 'url' field"}), 400

	url = data["url"].strip()
	if not url:
		return jsonify({"error": "Empty URL"}), 400

	# Ensure URL has a scheme
	if not url.startswith(('http://', 'https://')):
		url = 'https://' + url

	try:
		# Use HEAD request first (faster), fall back to GET if HEAD fails
		response = requests.head(url, timeout=10, allow_redirects=True)
		if response.status_code >= 400:
			# Some servers don't support HEAD, try GET
			response = requests.get(url, timeout=10, allow_redirects=True, stream=True)
			response.close()

		is_live = response.status_code < 400
		return jsonify({
			"url": url,
			"live": is_live,
			"status_code": response.status_code
		})
	except requests.exceptions.Timeout:
		return jsonify({"url": url, "live": False, "error": "Timeout"})
	except requests.exceptions.ConnectionError:
		return jsonify({"url": url, "live": False, "error": "Connection failed"})
	except requests.exceptions.RequestException as e:
		return jsonify({"url": url, "live": False, "error": str(e)})


@admin_page.route("/api/bibcode_info/<bibcode>", methods=["GET"])
@_login_required
def bibcode_info(bibcode):
	"""Fetch bibcode info from ADS. Returns JSON with title and authors."""
	from flask import jsonify
	import requests

	# ADS API endpoint
	ads_url = f"https://api.adsabs.harvard.edu/v1/search/query"

	ads_token = flask.current_app.config.get("ADS_API_TOKEN", "")

	try:
		headers = {"Authorization": f"Bearer {ads_token}"}
		params = {
			"q": f"bibcode:{bibcode}",
			"fl": "title,author,year,bibcode"
		}
		response = requests.get(ads_url, headers=headers, params=params, timeout=10)

		if response.status_code == 200:
			data = response.json()
			if data.get("response", {}).get("numFound", 0) > 0:
				doc = data["response"]["docs"][0]
				return jsonify({
					"bibcode": bibcode,
					"found": True,
					"title": doc.get("title", [""])[0],
					"authors": doc.get("author", []),
					"year": doc.get("year")
				})

		return jsonify({"bibcode": bibcode, "found": False, "error": "Not found"})

	except Exception as e:
		return jsonify({"bibcode": bibcode, "found": False, "error": str(e)})


# ==========================================
# Notes API
# ==========================================

@admin_page.route("/api/note_types", methods=["GET"])
@_login_required
def get_note_types():
	"""Get all note types for dropdown."""
	from flask import jsonify

	db_session = _get_db_session()
	ascldb = _get_models()

	try:
		types = (
			db_session.query(ascldb.NoteType)
			.order_by(ascldb.NoteType.display_order)
			.all()
		)
		return jsonify({
			"types": [
				{"pk": t.pk, "short_name": t.short_name, "name": t.name}
				for t in types
				if t.short_name != 'legacy'  # Don't allow creating legacy notes
			]
		})
	except Exception as e:
		return jsonify({"error": str(e)}), 500


@admin_page.route("/api/code/<int:code_pk>/notes", methods=["GET"])
@_login_required
def get_code_notes(code_pk):
	"""Get all notes for a code."""
	from flask import jsonify

	db_session = _get_db_session()
	ascldb = _get_models()

	try:
		notes = (
			db_session.query(ascldb.CodeNote)
			.filter(ascldb.CodeNote.code_pk == code_pk)
			.order_by(ascldb.CodeNote.is_pinned.desc(), ascldb.CodeNote.created_at.desc())
			.all()
		)
		return jsonify({
			"notes": [
				{
					"pk": n.pk,
					"note": n.note,
					"note_type": n.note_type.name if n.note_type else None,
					"note_type_short": n.note_type.short_name if n.note_type else None,
					"user": n.user.username if n.user else None,
					"created_at": n.created_at.isoformat() if n.created_at else None,
					"is_pinned": n.is_pinned,
					"hidden": n.hidden
				}
				for n in notes
			]
		})
	except Exception as e:
		return jsonify({"error": str(e)}), 500


@admin_page.route("/api/code/<int:code_pk>/notes", methods=["POST"])
@_login_required
def add_code_note(code_pk):
	"""Add a new note to a code."""
	from flask import jsonify

	db_session = _get_db_session()
	ascldb = _get_models()

	data = request.get_json()
	if not data:
		return jsonify({"error": "Missing JSON data"}), 400

	note_text = data.get("note", "").strip()
	note_type_pk = data.get("note_type_pk")

	if not note_text:
		return jsonify({"error": "Note text is required"}), 400
	if not note_type_pk:
		return jsonify({"error": "Note type is required"}), 400

	try:
		# Verify code exists
		code = db_session.query(ascldb.ASCLCode).filter(ascldb.ASCLCode.pk == code_pk).first()
		if not code:
			return jsonify({"error": "Code not found"}), 404

		# Get current user
		current_usr = _current_user(db_session)

		# Create note
		note = ascldb.CodeNote()
		note.code_pk = code_pk
		note.user_pk = current_usr.pk if current_usr else None
		note.note_type_pk = int(note_type_pk)
		note.note = note_text
		note.is_pinned = False
		note.hidden = False

		db_session.add(note)
		db_session.commit()

		return jsonify({
			"success": True,
			"note": {
				"pk": note.pk,
				"note": note.note,
				"note_type": note.note_type.name if note.note_type else None,
				"note_type_short": note.note_type.short_name if note.note_type else None,
				"user": current_usr.username if current_usr else None,
				"created_at": note.created_at.isoformat() if note.created_at else None,
				"is_pinned": note.is_pinned,
				"hidden": note.hidden
			}
		})
	except Exception as e:
		db_session.rollback()
		return jsonify({"error": str(e)}), 500


@admin_page.route("/api/note/<int:note_pk>/toggle_pin", methods=["POST"])
@_login_required
def toggle_note_pin(note_pk):
	"""Toggle the pinned status of a note."""
	from flask import jsonify

	db_session = _get_db_session()
	ascldb = _get_models()

	try:
		note = db_session.query(ascldb.CodeNote).filter(ascldb.CodeNote.pk == note_pk).first()
		if not note:
			return jsonify({"error": "Note not found"}), 404

		note.is_pinned = not note.is_pinned
		db_session.commit()

		return jsonify({"success": True, "is_pinned": note.is_pinned})
	except Exception as e:
		db_session.rollback()
		return jsonify({"error": str(e)}), 500


@admin_page.route("/api/note/<int:note_pk>/toggle_hidden", methods=["POST"])
@_login_required
def toggle_note_hidden(note_pk):
	"""Toggle the hidden status of a note."""
	from flask import jsonify

	db_session = _get_db_session()
	ascldb = _get_models()

	try:
		note = db_session.query(ascldb.CodeNote).filter(ascldb.CodeNote.pk == note_pk).first()
		if not note:
			return jsonify({"error": "Note not found"}), 404

		note.hidden = not note.hidden
		db_session.commit()

		return jsonify({"success": True, "hidden": note.hidden})
	except Exception as e:
		db_session.rollback()
		return jsonify({"error": str(e)}), 500


# ==========================================
# Dashboard Admin Stat Detail Pages
# ==========================================

def _paginated_code_list(base_query, page_title, **extra):
	"""Render a paginated codes_list.html from a base SQLAlchemy query."""
	import math
	from sqlalchemy.orm import selectinload

	ascldb = _get_models()
	db_session = base_query.session

	base_query = base_query.options(selectinload(ascldb.ASCLCode.keywords))

	page = int(request.args.get("page", 1))
	per_page = int(request.args.get("per_page", 50))

	total_count = base_query.count()

	ordered = base_query.order_by(ascldb.ASCLCode.time_added.desc(), ascldb.ASCLCode.pk.desc())

	if per_page == 0:
		codes = ordered.all()
		total_pages = 1
	else:
		codes = ordered.offset((page - 1) * per_page).limit(per_page).all()
		total_pages = math.ceil(total_count / per_page) if per_page > 0 else 1

	return render_template(
		"admin/codes_list.html",
		page_title=page_title,
		codes=codes,
		current_user=_current_user(db_session),
		page=page,
		per_page=per_page,
		total_count=total_count,
		total_pages=total_pages,
		**extra,
	)


@admin_page.route("/codes/awaiting-ids", methods=["GET"])
@_login_required
def codes_awaiting_ids():
	"""Codes with ascl_id = '0000.000' (no assigned ID yet)."""
	db_session = _get_db_session()
	ascldb = _get_models()

	query = db_session.query(ascldb.ASCLCode).filter(ascldb.ASCLCode.ascl_id == '0000.000')

	return _paginated_code_list(query, "Codes Awaiting ASCL IDs", hide_keywords=True)


@admin_page.route("/codes/missing-citation-method", methods=["GET"])
@_login_required
def codes_missing_citation_method():
	"""Codes with assigned IDs that have no preferred citation method."""
	db_session = _get_db_session()
	ascldb = _get_models()

	query = (
		db_session.query(ascldb.ASCLCode)
		.filter(ascldb.ASCLCode.ascl_id != '0000.000')
		.filter((ascldb.ASCLCode.citation_method == None) | (ascldb.ASCLCode.citation_method == ''))
	)

	return _paginated_code_list(query, "Codes Missing Preferred Citation Method")


@admin_page.route("/codes/missing-described-used", methods=["GET"])
@_login_required
def codes_missing_described_used():
	"""Codes missing both 'described in' and 'used in' links."""
	from sqlalchemy import distinct

	db_session = _get_db_session()
	ascldb = _get_models()

	codes_with_di_or_ui = (
		db_session.query(distinct(ascldb.Link.code_pk))
		.filter(ascldb.Link.link_type_pk.in_([4, 5]))
		.subquery()
	)

	query = (
		db_session.query(ascldb.ASCLCode)
		.filter(~ascldb.ASCLCode.pk.in_(db_session.query(codes_with_di_or_ui)))
	)

	status = request.args.get("status")
	if status == "published":
		query = query.filter(ascldb.ASCLCode.ascl_id != '0000.000')
		title = 'Published Codes Missing "Described In" and "Used In"'
	else:
		title = 'All Codes Missing "Described In" and "Used In"'

	return _paginated_code_list(query, title)


@admin_page.route("/codes/submitted-by-authors", methods=["GET"])
@_login_required
def codes_submitted_by_authors():
	"""Codes whose notes indicate author submission."""
	db_session = _get_db_session()
	ascldb = _get_models()

	query = (
		db_session.query(ascldb.ASCLCode)
		.filter(ascldb.ASCLCode.notes.like('Submitted by:%'))
	)

	return _paginated_code_list(query, "Codes Submitted by Authors", show_ascl_id_filter=True)


# ==========================================
# Corrections Review Routes
# ==========================================

def _diff_highlight(old_text, new_text):
	"""Return (old_html, new_html) with <mark> tags highlighting differences."""
	import difflib
	from markupsafe import escape

	old_text = old_text or ""
	new_text = new_text or ""

	sm = difflib.SequenceMatcher(None, old_text, new_text)
	old_parts = []
	new_parts = []

	for op, i1, i2, j1, j2 in sm.get_opcodes():
		old_chunk = str(escape(old_text[i1:i2]))
		new_chunk = str(escape(new_text[j1:j2]))

		if op == "equal":
			old_parts.append(old_chunk)
			new_parts.append(new_chunk)
		elif op == "replace":
			old_parts.append(f'<mark class="diff-del">{old_chunk}</mark>')
			new_parts.append(f'<mark class="diff-add">{new_chunk}</mark>')
		elif op == "delete":
			old_parts.append(f'<mark class="diff-del">{old_chunk}</mark>')
		elif op == "insert":
			new_parts.append(f'<mark class="diff-add">{new_chunk}</mark>')

	return "".join(old_parts), "".join(new_parts)


@admin_page.route("/corrections", methods=["GET"])
@_login_required
def corrections():
	"""List user-submitted corrections for review."""
	from sqlalchemy import text as sa_text

	db_session = _get_db_session()
	filter_status = request.args.get("status", "pending")

	where = ""
	join_extra = ""
	params = {}
	if filter_status in ("pending", "applied", "rejected"):
		where = "WHERE cc.status = :status"
		params["status"] = filter_status
	elif filter_status == "noted":
		join_extra = ("JOIN code_note cn ON cn.correction_pk = cc.pk "
		              "JOIN users u_note ON u_note.pk = cn.user_pk AND u_note.username != 'ASCLbot'")
		where = "WHERE cc.status = 'pending'"

	rows = db_session.execute(sa_text(f"""
		SELECT DISTINCT cc.*, c.ascl_id, c.title AS code_title,
		       c.credit AS current_credit, c.abstract AS current_abstract,
		       c.citation_method AS current_citation_method
		FROM code_correction cc
		JOIN codes c ON c.pk = cc.code_pk
		{join_extra}
		{where}
		ORDER BY cc.submitted_at DESC
	"""), params).mappings().all()

	pending_count = db_session.execute(sa_text(
		"SELECT COUNT(*) FROM code_correction WHERE status = 'pending'"
	)).scalar()

	# Fetch link changes for each correction
	corrections_list = []
	for row in rows:
		c = dict(row)
		link_rows = db_session.execute(sa_text("""
			SELECT ccl.urls AS proposed_urls, lt.name AS link_type_name, lt.pk AS link_type_pk
			FROM code_correction_link ccl
			JOIN link_type lt ON lt.pk = ccl.link_type_pk
			WHERE ccl.correction_pk = :correction_pk
		"""), {"correction_pk": c["pk"]}).mappings().all()

		link_changes = []
		for lr in link_rows:
			# Get current URLs for this link type
			current = db_session.execute(sa_text("""
				SELECT l.url FROM link l
				WHERE l.code_pk = :code_pk AND l.link_type_pk = :lt_pk
				ORDER BY l.display_order, l.pk
			"""), {"code_pk": c["code_pk"], "lt_pk": lr["link_type_pk"]}).fetchall()
			current_urls = "\n".join(r[0] for r in current)
			link_changes.append({
				"link_type_name": lr["link_type_name"],
				"link_type_pk": lr["link_type_pk"],
				"current_urls": current_urls,
				"proposed_urls": lr["proposed_urls"],
			})
		c["link_changes"] = link_changes

		# Compute diff-highlighted HTML for each changed scalar field
		for field, current_key in [
			("title", "code_title"),
			("credit", "current_credit"),
			("abstract", "current_abstract"),
			("citation_method", "current_citation_method"),
		]:
			if c[field] is not None:
				old_html, new_html = _diff_highlight(c[current_key] or "", c[field])
				c[f"{field}_diff_current"] = old_html
				c[f"{field}_diff_proposed"] = new_html

		# Compute diff-highlighted HTML for link changes
		for lc in link_changes:
			old_html, new_html = _diff_highlight(
				lc["current_urls"] or "", lc["proposed_urls"] or ""
			)
			lc["diff_current"] = old_html
			lc["diff_proposed"] = new_html

		# Fetch curator notes linked to this correction
		c["curator_notes"] = db_session.execute(sa_text("""
			SELECT cn.note, cn.created_at, u.username AS author
			FROM code_note cn
			LEFT JOIN users u ON u.pk = cn.user_pk
			WHERE cn.correction_pk = :correction_pk
			ORDER BY cn.created_at
		"""), {"correction_pk": c["pk"]}).mappings().all()

		corrections_list.append(c)

	return render_template(
		"admin/corrections.html",
		corrections=corrections_list,
		current_user=_current_user(db_session),
		filter_status=filter_status,
		pending_count=pending_count,
	)


@admin_page.route("/corrections/<int:pk>/apply", methods=["POST"])
@_login_required
def apply_correction(pk):
	"""Apply a correction to the code entry."""
	from datetime import datetime
	from sqlalchemy import text as sa_text

	db_session = _get_db_session()
	ascldb = _get_models()

	correction = db_session.execute(sa_text(
		"SELECT * FROM code_correction WHERE pk = :pk AND status = 'pending'"
	), {"pk": pk}).mappings().first()

	if not correction:
		flash("Correction not found or already processed.", "error")
		return redirect(url_for("admin_page.corrections"))

	code = db_session.query(ascldb.ASCLCode).filter(
		ascldb.ASCLCode.pk == correction["code_pk"]
	).one_or_none()

	if not code:
		flash("Code not found.", "error")
		return redirect(url_for("admin_page.corrections"))

	# Apply scalar field changes (only those selected by curator)
	total_fields = 0
	applied_fields = 0
	if correction["title"] is not None:
		total_fields += 1
		if request.form.get("include_title"):
			code.title = correction["title"]
			applied_fields += 1
	if correction["credit"] is not None:
		total_fields += 1
		if request.form.get("include_credit"):
			code.credit = correction["credit"]
			_sync_authors_from_credit(db_session, ascldb, code.pk, correction["credit"])
			applied_fields += 1
	if correction["abstract"] is not None:
		total_fields += 1
		if request.form.get("include_abstract"):
			code.abstract = correction["abstract"]
			applied_fields += 1
	if correction["citation_method"] is not None:
		total_fields += 1
		if request.form.get("include_citation_method"):
			code.citation_method = correction["citation_method"]
			applied_fields += 1

	code.time_updated = datetime.now()

	# Apply link changes (only those selected by curator)
	link_changes = db_session.execute(sa_text("""
		SELECT link_type_pk, urls FROM code_correction_link
		WHERE correction_pk = :pk
	"""), {"pk": pk}).mappings().all()

	for lc in link_changes:
		total_fields += 1
		if not request.form.get(f"include_link_{lc['link_type_pk']}"):
			continue

		applied_fields += 1

		# Delete existing links of this type for the code
		db_session.execute(sa_text("""
			DELETE FROM link WHERE code_pk = :code_pk AND link_type_pk = :lt_pk
		"""), {"code_pk": code.pk, "lt_pk": lc["link_type_pk"]})

		# Insert new links
		urls = [u.strip() for u in (lc["urls"] or "").splitlines() if u.strip()]
		for order, url in enumerate(urls):
			db_session.execute(sa_text("""
				INSERT INTO link (code_pk, url, link_type_pk, display_order)
				VALUES (:code_pk, :url, :lt_pk, :display_order)
			"""), {
				"code_pk": code.pk,
				"url": url,
				"lt_pk": lc["link_type_pk"],
				"display_order": order,
			})

	if applied_fields == 0:
		flash("No changes were selected to apply.", "error")
		return redirect(url_for("admin_page.corrections"))

	# Mark correction as applied
	db_session.execute(sa_text("""
		UPDATE code_correction
		SET status = 'applied', reviewed_at = :now, reviewed_by = :user_pk
		WHERE pk = :pk
	"""), {"pk": pk, "now": datetime.now(), "user_pk": session.get("user_id")})

	db_session.commit()
	if applied_fields < total_fields:
		flash(f"Correction partially applied ({applied_fields} of {total_fields} changes) to <a href='/{code.ascl_id}'>ascl:{code.ascl_id}</a>.", "success")
	else:
		flash(f"Correction applied to <a href='/{code.ascl_id}'>ascl:{code.ascl_id}</a>.", "success")
	return redirect(url_for("admin_page.corrections"))


@admin_page.route("/corrections/<int:pk>/reject", methods=["POST"])
@_login_required
def reject_correction(pk):
	"""Reject a correction."""
	from datetime import datetime
	from sqlalchemy import text as sa_text

	db_session = _get_db_session()

	correction = db_session.execute(sa_text(
		"SELECT pk FROM code_correction WHERE pk = :pk AND status = 'pending'"
	), {"pk": pk}).mappings().first()

	if not correction:
		flash("Correction not found or already processed.", "error")
		return redirect(url_for("admin_page.corrections"))

	reviewer_notes = request.form.get("reviewer_notes", "").strip() or None

	db_session.execute(sa_text("""
		UPDATE code_correction
		SET status = 'rejected', reviewed_at = :now, reviewed_by = :user_pk,
		    reviewer_notes = :notes
		WHERE pk = :pk
	"""), {
		"pk": pk,
		"now": datetime.now(),
		"user_pk": session.get("user_id"),
		"notes": reviewer_notes,
	})

	db_session.commit()
	flash("Correction rejected.", "info")
	return redirect(url_for("admin_page.corrections"))


@admin_page.route("/corrections/<int:pk>/note", methods=["POST"])
@_login_required
def save_curator_note(pk):
	"""Add a curator note to a correction via the code_note table."""
	from sqlalchemy import text as sa_text

	db_session = _get_db_session()

	correction = db_session.execute(sa_text(
		"SELECT pk, code_pk FROM code_correction WHERE pk = :pk"
	), {"pk": pk}).mappings().first()

	if not correction:
		flash("Correction not found.", "error")
		return redirect(url_for("admin_page.corrections"))

	note_text = request.form.get("curator_note", "").strip()
	if not note_text:
		flash("Note is empty.", "error")
		return redirect(url_for("admin_page.corrections"))

	db_session.execute(sa_text("""
		INSERT INTO code_note (code_pk, correction_pk, user_pk, note_type_pk, note)
		VALUES (:code_pk, :correction_pk, :user_pk, 3, :note)
	"""), {
		"code_pk": correction["code_pk"],
		"correction_pk": pk,
		"user_pk": session.get("user_id"),
		"note": note_text,
	})

	db_session.commit()
	flash("Curator note added.", "info")
	return redirect(url_for("admin_page.corrections"))


# ==========================================
# Broken Links
# ==========================================

@admin_page.route("/broken-links", methods=["GET"])
@_login_required
def broken_links():
	"""Link check results page — shows all checked links with status filters."""
	from sqlalchemy import text

	db_session = _get_db_session()

	# Deduplicate by URL: same URL may be linked from multiple codes.
	# Group ASCL IDs per unique URL, keep one representative link_check row.
	raw_rows = db_session.execute(text("""
		SELECT c.ascl_id, c.title AS code_title,
		       l.url,
		       lc.http_status, lc.message, lc.is_working,
		       lc.page_title, lc.title_ok,
		       lc.final_url, lc.final_url_ok,
		       lc.domain_changed, lc.fail_count,
		       lc.last_working, lc.checked_at, lc.note
		FROM link_check lc
		JOIN link l ON l.pk = lc.link_pk
		JOIN codes c ON c.pk = l.code_pk
		ORDER BY lc.is_working ASC, lc.fail_count DESC, lc.checked_at DESC
	""")).fetchall()

	seen_urls = {}
	rows = []
	for row in raw_rows:
		if row.url in seen_urls:
			# Add this ASCL ID to the existing entry
			seen_urls[row.url]["ascl_ids"].append(row.ascl_id)
		else:
			entry = {col: getattr(row, col) for col in row._fields}
			entry["ascl_ids"] = [row.ascl_id]
			seen_urls[row.url] = entry
			rows.append(entry)

	# Academic/department domain suffixes
	_ACADEMIC_SUFFIXES = (
		'.edu', '.ac.uk', '.ac.il', '.ac.jp', '.ac.kr', '.ac.za', '.ac.nz',
		'.ac.in', '.ac.at', '.ac.be', '.ac.cn', '.ac.ir', '.ac.th',
		'.edu.au', '.edu.cn', '.edu.tw', '.edu.br', '.edu.mx',
		'.uni-', '.u-', '.univ-',
	)
	_GITHUB_DOMAINS = ('github.com', 'github.io', 'raw.githubusercontent.com')

	def _classify_domain(url):
		"""Return domain tags for a URL: 'github', 'academic', or empty."""
		from urllib.parse import urlparse
		try:
			host = urlparse(url).netloc.lower()
		except Exception:
			return ""
		tags = []
		if any(host.endswith(d) or host == d for d in _GITHUB_DOMAINS):
			tags.append("github")
		if any(s in host for s in _ACADEMIC_SUFFIXES):
			tags.append("academic")
		return " ".join(tags)

	# Classify domains, detect changes, and compute counts
	counts = {"all": 0, "broken": 0, "timeout": 0, "ssl": 0, "ok": 0, "noted": 0}
	domain_counts = {"academic": 0, "not-github": 0, "github": 0}
	signal_counts = {"title-changed": 0, "domain-changed": 0}
	for row in rows:
		row["domain_tags"] = _classify_domain(row["url"])

		# Detect title/domain changes
		row["title_changed"] = bool(
			row["title_ok"] and row["page_title"]
			and row["title_ok"] != row["page_title"]
		)
		# domain_changed is already in the DB row

		counts["all"] += 1
		if "academic" in row["domain_tags"]:
			domain_counts["academic"] += 1
		if "github" not in row["domain_tags"]:
			domain_counts["not-github"] += 1
		else:
			domain_counts["github"] += 1
		if row["title_changed"]:
			signal_counts["title-changed"] += 1
		if row["domain_changed"]:
			signal_counts["domain-changed"] += 1
		if row["is_working"]:
			counts["ok"] += 1
			if row["note"]:
				counts["noted"] += 1
		elif row["http_status"] == 0:
			counts["timeout"] += 1
			counts["broken"] += 1
		elif row["http_status"] == -1:
			counts["ssl"] += 1
			counts["broken"] += 1
		else:
			counts["broken"] += 1

	# Summary stats
	summary = db_session.execute(text("""
		SELECT COUNT(*) AS total_checked,
		       SUM(lc.is_working) AS working,
		       MAX(lc.checked_at) AS last_checked
		FROM link_check lc
		JOIN link l ON l.pk = lc.link_pk
		WHERE l.link_type_pk = 2
	""")).one()

	db_session.close()

	return render_template("admin/broken_links.html",
		link_checks=rows,
		counts=counts,
		domain_counts=domain_counts,
		signal_counts=signal_counts,
		summary=summary,
	)


@admin_page.route("/check-link", methods=["POST"])
@_login_required
def check_single_link():
	"""Re-check a single URL and return the updated result as JSON."""
	import asyncio
	import json as _json
	import sys
	import os
	from flask import jsonify
	from sqlalchemy import text

	url = request.form.get("url", "").strip()
	if not url:
		return jsonify({"error": "No URL provided"}), 400

	# Import the checker module
	bin_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
		os.path.abspath(__file__)))), '..', '..', 'bin')
	sys.path.insert(0, os.path.abspath(bin_dir))
	from ascl_link_checker import (
		check_url, write_result, read_db_config, get_connection,
		MAX_PER_DOMAIN, USER_AGENT,
	)
	import httpx

	# Find all link_pks for this URL
	db_session = _get_db_session()
	rows = db_session.execute(text(
		"SELECT pk FROM link WHERE url = :url"
	), {"url": url}).fetchall()
	db_session.close()

	if not rows:
		return jsonify({"error": "URL not found in link table"}), 404

	link_pks = [r.pk for r in rows]

	# Run the check
	async def _check():
		sem = asyncio.Semaphore(1)
		domain_sems = {}
		domain_last_request = {}
		timeout = httpx.Timeout(connect=10, read=20, write=10, pool=10)
		async with httpx.AsyncClient(
			timeout=timeout,
			headers={"User-Agent": USER_AGENT},
			follow_redirects=True,
		) as client:
			return await check_url(
				client, sem, domain_sems, domain_last_request,
				{"url": url, "link_pks": link_pks},
			)

	result = asyncio.run(_check())

	# Write to DB
	db_cfg = read_db_config()
	connection = get_connection(db_cfg, flask.current_app.config.get("DB_DATABASE", "ascl_db_v4"))
	write_result(connection, result)
	connection.commit()
	connection.close()

	return jsonify({
		"url": result["url"],
		"http_status": result["http_status"],
		"is_working": result["is_working"],
		"page_title": result.get("page_title"),
		"note": result.get("note"),
		"message": result["message"],
	})
