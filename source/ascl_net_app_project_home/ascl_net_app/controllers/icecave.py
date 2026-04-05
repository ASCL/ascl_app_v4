#!/usr/bin/python

"""
Icecave admin page — displays archive status from the Icecave VPS API.

The page fetches data from the Icecave API server (configured via
ICECAVE_API_URL and ICECAVE_API_KEY in Flask config) and renders a
dashboard showing archive status, sync history, and curator actions.
"""

import json
import logging
import urllib.request
from functools import wraps
from urllib.error import URLError

import flask
from flask import render_template, request, session, flash, redirect, url_for, current_app, jsonify

logger = logging.getLogger(__name__)

icecave_page = flask.Blueprint("icecave_page", __name__, url_prefix="/admin/icecave")


# ==========================================
# Authentication (reuse admin session)
# ==========================================

def _login_required(view_func):
	@wraps(view_func)
	def wrapper(*args, **kwargs):
		if not session.get("user_id"):
			flash("Please log in to access admin tools.", "error")
			return redirect(url_for("admin_page.admin_home"))
		return view_func(*args, **kwargs)
	return wrapper


# ==========================================
# Icecave API client
# ==========================================

def _icecave_request(path, method='GET', data=None, timeout=10):
	"""Make an authenticated request to the Icecave API.

	Returns (response_dict, error_string). On success error is None.
	On failure response_dict is None.
	"""
	base_url = current_app.config.get('ICECAVE_API_URL', 'http://127.0.0.1:5001')
	api_key = current_app.config.get('ICECAVE_API_KEY', '')

	url = f"{base_url.rstrip('/')}{path}"

	req = urllib.request.Request(url, method=method)
	req.add_header('Accept', 'application/json')
	if api_key:
		req.add_header('Authorization', f'Bearer {api_key}')
	if data is not None:
		req.add_header('Content-Type', 'application/json')
		req.data = json.dumps(data).encode('utf-8')

	try:
		with urllib.request.urlopen(req, timeout=timeout) as resp:
			return json.loads(resp.read()), None
	except URLError as e:
		logger.error(f"Icecave API error ({path}): {e}")
		return None, f"Cannot reach Icecave API: {e.reason}"
	except Exception as e:
		logger.error(f"Icecave API error ({path}): {e}")
		return None, str(e)


# ==========================================
# Routes
# ==========================================

@icecave_page.route("/", methods=["GET"])
@_login_required
def icecave_home():
	"""Main icecave dashboard page."""

	# Fetch all data — filtering/sorting/pagination is done client-side
	health, health_err = _icecave_request('/api/health', timeout=15)
	status, status_err = _icecave_request('/api/status?per_page=5000', timeout=30)
	sync_log, sync_err = _icecave_request('/api/sync/log?limit=5')

	error = health_err or status_err or sync_err

	return render_template("admin/icecave.html",
		health=health,
		status=status,
		sync_log=sync_log,
		api_error=error,
	)


@icecave_page.route("/code/<ascl_id>", methods=["GET"])
@_login_required
def icecave_code_detail(ascl_id):
	"""Detail view for a single code's archive status."""
	data, error = _icecave_request(f'/api/status/{ascl_id}')

	if error:
		flash(f"Icecave API error: {error}", "error")
		return redirect(url_for("icecave_page.icecave_home"))

	if data and data.get('error'):
		flash(f"Code {ascl_id} not found in archive.", "error")
		return redirect(url_for("icecave_page.icecave_home"))

	return render_template("admin/icecave_detail.html", code=data)


@icecave_page.route("/sync/<ascl_id>", methods=["POST"])
@_login_required
def icecave_trigger_sync_single(ascl_id):
	"""Trigger sync for a single code."""
	data, error = _icecave_request(f'/api/sync/{ascl_id}', method='POST')
	if error:
		flash(f"Failed to trigger sync for {ascl_id}: {error}", "error")
	else:
		flash(f"Sync started for {ascl_id}.", "success")
	return redirect(url_for("icecave_page.icecave_code_detail", ascl_id=ascl_id))


@icecave_page.route("/wayback/<ascl_id>", methods=["POST"])
@_login_required
def icecave_wayback_capture(ascl_id):
	"""Submit a code's URL to the Wayback Machine."""
	data, error = _icecave_request(f'/api/wayback/{ascl_id}', method='POST')
	if error:
		flash(f"Wayback capture failed: {error}", "error")
	else:
		flash(f"Wayback capture submitted for {ascl_id}.", "success")
	return redirect(url_for("icecave_page.icecave_code_detail", ascl_id=ascl_id))


@icecave_page.route("/wayback/<ascl_id>/check", methods=["POST"])
@_login_required
def icecave_wayback_check(ascl_id):
	"""Check latest Wayback capture for a code."""
	data, error = _icecave_request(f'/api/wayback/{ascl_id}')
	if error:
		flash(f"Wayback check failed: {error}", "error")
	elif data and data.get('last_wayback'):
		flash(f"Last Wayback capture: {data['last_wayback']}", "success")
	else:
		flash(f"No Wayback capture found for {ascl_id}.", "info")
	return redirect(url_for("icecave_page.icecave_code_detail", ascl_id=ascl_id))
