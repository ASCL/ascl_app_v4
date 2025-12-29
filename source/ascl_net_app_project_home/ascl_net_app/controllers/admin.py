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

	codes = (
		db_session.query(ascldb.ASCLCode)
		.filter(ascldb.ASCLCode.published == 0, ascldb.ASCLCode.archived == 0)
		.order_by(ascldb.ASCLCode.time_added.desc(), ascldb.ASCLCode.pk.desc())
		.all()
	)

	return render_template(
		"admin/codes_list.html",
		page_title="Unpublished Codes",
		codes=codes,
		current_user=_current_user(db_session),
	)


@admin_page.route("/archived", methods=["GET"])
@_login_required
def archived_codes():
	db_session = _get_db_session()
	ascldb = _get_models()

	codes = (
		db_session.query(ascldb.ASCLCode)
		.filter(ascldb.ASCLCode.archived == 1)
		.order_by(ascldb.ASCLCode.time_added.desc(), ascldb.ASCLCode.pk.desc())
		.all()
	)

	return render_template(
		"admin/codes_list.html",
		page_title="Archived Codes",
		codes=codes,
		current_user=_current_user(db_session),
	)
