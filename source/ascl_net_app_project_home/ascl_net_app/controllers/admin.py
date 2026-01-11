#!/usr/bin/python

import hashlib
from functools import wraps

import flask
from flask import render_template, request, redirect, url_for, session, flash
from sqlalchemy import func
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
	from ascl_core.database.connections import Trillian2Connection as db
	return db.Session()


def _get_models():
	import ascl_core.database.ascldb.ASCLModelClasses as ascldb
	return ascldb


def _current_user(db_session=None):
	ascldb = _get_models()
	user_id = session.get("user_id")
	if not user_id:
		return None
	db_session = db_session or _get_db_session()
	return db_session.query(ascldb.User).filter(ascldb.User.id == user_id).one_or_none()


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

	published_views = (
		db_session.query(func.sum(ascldb.ASCLCode.views))
		.filter(ascldb.ASCLCode.published == 1)
		.scalar()
		or 0
	)
	unpublished_views = (
		db_session.query(func.sum(ascldb.ASCLCode.views))
		.filter(ascldb.ASCLCode.published == 0)
		.scalar()
		or 0
	)

	template_dict = {
		"current_user": _current_user(db_session),
		"published_views": published_views,
		"unpublished_views": unpublished_views,
	}
	return render_template("admin/home.html", **template_dict)


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


@admin_page.route("/logout", methods=["GET"])
def admin_logout():
	session.clear()
	flash("Logged out.", "info")
	return redirect(url_for("admin_page.admin_home"))


@admin_page.route("/unpublished", methods=["GET"])
@_login_required
def unpublished_codes():
	db_session = _get_db_session()
	ascldb = _get_models()

	# Pagination parameters
	page = int(request.args.get("page", 1))
	per_page = int(request.args.get("per_page", 50))

	base_query = (
		db_session.query(ascldb.ASCLCode)
		.filter(ascldb.ASCLCode.published == 0, ascldb.ASCLCode.archived == 0)
	)

	total_count = base_query.count()

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
		page_title="Unpublished Codes",
		codes=codes,
		current_user=_current_user(db_session),
		page=page,
		per_page=per_page,
		total_count=total_count,
		total_pages=total_pages,
		list_type="unpublished",
	)


@admin_page.route("/archived", methods=["GET"])
@_login_required
def archived_codes():
	db_session = _get_db_session()
	ascldb = _get_models()

	# Pagination parameters
	page = int(request.args.get("page", 1))
	per_page = int(request.args.get("per_page", 50))

	base_query = (
		db_session.query(ascldb.ASCLCode)
		.filter(ascldb.ASCLCode.archived == 1)
	)

	total_count = base_query.count()

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
	keywords_str = " ".join([k.keyword for k in code.keywords]) if code.keywords else ""

	return render_template(
		"admin/view_code.html",
		code=code,
		aliases_str=aliases_str,
		keywords_str=keywords_str,
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
			code.abstract = request.form.get("abstract", "").strip()
			code.site_list = _prep_list_for_db(request.form.get("site_list", ""))
			code.ref_list = _prep_list_for_db(request.form.get("ref_list", ""))
			code.described_in = _prep_list_for_db(request.form.get("described_in", ""))
			code.used_in = _prep_list_for_db(request.form.get("used_in", ""))
			code.citation_method = request.form.get("citation_method", "").strip()
			code.see_also = request.form.get("see_also", "").strip()
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

			db_session.commit()
			flash(f"Code updated successfully. <a href='/code/v/{pk}'>View it here</a>.", "success")
			return redirect(url_for("admin_page.view_code", pk=pk))

	# GET request - load current data
	# Get aliases as space-separated string
	aliases_str = " ".join([a.alias for a in code.aliases]) if code.aliases else ""

	# Get keywords as space-separated string (quote keywords with spaces)
	keywords_list = []
	for k in code.keywords:
		if " " in k.keyword:
			keywords_list.append(f'"{k.keyword}"')
		else:
			keywords_list.append(k.keyword)
	keywords_str = " ".join(keywords_list)

	# Prep lists for form display (unserialize PHP arrays)
	site_list_str = _prep_list_for_form(code.site_list)
	ref_list_str = _prep_list_for_form(code.ref_list)
	described_in_str = _prep_list_for_form(code.described_in)
	used_in_str = _prep_list_for_form(code.used_in)

	return render_template(
		"admin/edit_code.html",
		code=code,
		mode="update",
		aliases_str=aliases_str,
		keywords_str=keywords_str,
		site_list_str=site_list_str,
		ref_list_str=ref_list_str,
		described_in_str=described_in_str,
		used_in_str=used_in_str,
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
	db_session = _get_db_session()
	ascldb = _get_models()

	# Calculate next ASCL ID suggestion
	from datetime import datetime
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

	next_ascl_id = f"{current_yymm}.{next_num:03d}"

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
					flash(f"ASCL ID {ascl_id} is already in use.", "error")
					return render_template(
						"admin/edit_code.html",
						code=None,
						mode="insert",
						next_ascl_id=next_ascl_id,
						current_user=_current_user(db_session),
					)

			# Create new code
			code = ascldb.ASCLCode()
			code.ascl_id = ascl_id
			code.title = title
			code.credit = credit
			code.abstract = request.form.get("abstract", "").strip()
			code.site_list = _prep_list_for_db(request.form.get("site_list", ""))
			code.ref_list = _prep_list_for_db(request.form.get("ref_list", ""))
			code.described_in = _prep_list_for_db(request.form.get("described_in", ""))
			code.used_in = _prep_list_for_db(request.form.get("used_in", ""))
			code.citation_method = request.form.get("citation_method", "").strip()
			code.see_also = request.form.get("see_also", "").strip()
			code.email = request.form.get("email", "").strip()
			code.notes = request.form.get("notes", "").strip()
			code.published = int(request.form.get("published", 0))
			code.doi = request.form.get("doi", "").strip()
			code.time_added = datetime.now()
			code.time_updated = datetime.now()
			code.archived = 0
			code.views = 0

			# Set added_by from current user
			current_user = _current_user(db_session)
			if current_user:
				code.added_by = current_user.id

			# Generate bibcode if publishing
			if code.published == 1 and ascl_id != "0000.000":
				code.century = "20"  # Default century
				code.bibcode = f"20{ascl_id[:2]}ascl.soft{ascl_id[2:4]}{ascl_id[5:8]}{credit[0].upper()}"

			db_session.add(code)
			db_session.flush()  # Get the PK

			pk = code.pk

			# Add aliases
			_update_aliases(db_session, ascldb, pk, request.form.get("aliases", ""))

			# Add keywords
			_update_keywords(db_session, ascldb, pk, request.form.get("keywords", ""))

			db_session.commit()
			flash(f"Code added successfully. <a href='/code/v/{pk}'>View it here</a>.", "success")
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
			self.site_list = ""
			self.ref_list = ""
			self.described_in = ""
			self.used_in = ""
			self.citation_method = ""
			self.see_also = ""
			self.email = ""
			self.notes = ""
			self.published = 0
			self.doi = ""

	return render_template(
		"admin/edit_code.html",
		code=MockCode(),
		mode="insert",
		aliases_str="",
		keywords_str="",
		site_list_str="",
		ref_list_str="",
		described_in_str="",
		used_in_str="",
		next_ascl_id=next_ascl_id,
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
		db_session.query(ascldb.ASCLCodeAlias).filter(ascldb.ASCLCodeAlias.code_id == pk).delete()
		db_session.query(ascldb.ASCLCodeToKeyword).filter(ascldb.ASCLCodeToKeyword.code_id == pk).delete()

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

def _prep_list_for_db(text):
	"""Convert newline-separated URLs to PHP serialized array for database storage."""
	if not text or not text.strip():
		return None

	import phpserialize
	lines = [line.strip() for line in text.strip().split("\n") if line.strip()]
	if not lines:
		return None

	# PHP serialize as indexed array
	return phpserialize.dumps(lines).decode("utf-8")


def _prep_list_for_form(serialized):
	"""Convert PHP serialized array to newline-separated text for form display."""
	if not serialized:
		return ""

	try:
		import phpserialize
		data = phpserialize.loads(serialized.encode("utf-8") if isinstance(serialized, str) else serialized)
		if isinstance(data, dict):
			return "\n".join(str(v) for v in data.values())
		elif isinstance(data, (list, tuple)):
			return "\n".join(str(item) for item in data)
		return str(data)
	except Exception:
		# If deserialization fails, return as-is
		return serialized if serialized else ""


def _update_aliases(db_session, ascldb, code_pk, aliases_text):
	"""Update code aliases from space-separated text."""
	# Clear existing aliases
	db_session.query(ascldb.ASCLCodeAlias).filter(ascldb.ASCLCodeAlias.code_id == code_pk).delete()

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
			new_alias.code_id = code_pk
			new_alias.alias = alias
			db_session.add(new_alias)


def _update_keywords(db_session, ascldb, code_pk, keywords_text):
	"""Update code keywords from space-separated text (handles quoted phrases)."""
	import shlex

	# Clear existing keyword associations
	db_session.query(ascldb.ASCLCodeToKeyword).filter(ascldb.ASCLCodeToKeyword.code_id == code_pk).delete()

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
		existing = db_session.query(ascldb.Keyword).filter(ascldb.Keyword.keyword == kw).first()
		if existing:
			kw_id = existing.id
		else:
			# Create new keyword
			new_kw = ascldb.Keyword()
			new_kw.keyword = kw
			db_session.add(new_kw)
			db_session.flush()  # Get the ID
			kw_id = new_kw.id

		# Create association
		assoc = ascldb.ASCLCodeToKeyword()
		assoc.code_id = code_pk
		assoc.keyword_id = kw_id
		db_session.add(assoc)


# ==========================================
# Utility / Raw Data Routes
# ==========================================

@admin_page.route("/utility/ascl", methods=["GET"])
@_login_required
def utility_ascl():
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


@admin_page.route("/utility/ascl2", methods=["GET"])
@_login_required
def utility_ascl2():
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


@admin_page.route("/utility/links", methods=["GET"])
@_login_required
def utility_links():
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
def utility_site_links():
	"""Site links only as plain text."""
	db_session = _get_db_session()
	ascldb = _get_models()

	# Query from link table where link_type is 'Code Site' (pk=1)
	links = (
		db_session.query(ascldb.Link.url)
		.filter(ascldb.Link.link_type_pk == 1)
		.all()
	)

	# Build plain text output
	output = "\n".join([link.url for link in links if link.url])

	from flask import Response
	return Response(output, mimetype="text/plain; charset=utf-8")
