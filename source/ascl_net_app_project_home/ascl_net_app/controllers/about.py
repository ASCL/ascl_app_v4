#!/usr/bin/python

import flask
from flask import render_template, abort, request
from markupsafe import Markup
from sqlalchemy import text

from ascl_net_app.model.database import Database
from ascl_net_app.utilities.wordpress import wpautop

about_page = flask.Blueprint("about_page", __name__)

# WordPress posts table; used to pull static pages like About/Resources.
_WP_POSTS_TABLE = "ascl_wordpress.0hjpDo4yM_posts"
_ABOUT_PAGE_ID = 2
_SUBMISSIONS_PAGE_ID = 29
_RESOURCES_PAGE_ID = 697
_EXPLAIN_PAGE_ID = 1442

# Map WordPress page IDs to named routes (for subpages nav links)
_PAGE_ID_TO_ROUTE = {
	_ABOUT_PAGE_ID: "/about",
	_SUBMISSIONS_PAGE_ID: "/submissions",
	_RESOURCES_PAGE_ID: "/resources",
	_EXPLAIN_PAGE_ID: "/explain",
}


def _fetch_wp_page(page_id: int):
	if page_id <= 0:
		return None
	sql = text(
		f"""
		SELECT ID, post_title, post_content, post_parent
		FROM {_WP_POSTS_TABLE}
		WHERE ID = :id AND post_type = 'page' AND post_status = 'publish'
		LIMIT 1
		"""
	)
	with Database().db.engine.connect() as conn:
		return conn.execute(sql, {"id": page_id}).mappings().first()


def _title_case(s):
	"""Capitalize first letter of each word, but preserve all-uppercase words like ASCL."""
	words = s.split()
	result = []
	for w in words:
		if w.isupper() and len(w) > 1:
			result.append(w)
		elif '/' in w:
			result.append('/'.join(
				p if (p.isupper() and len(p) > 1) else p.capitalize()
				for p in w.split('/')
			))
		else:
			result.append(w.capitalize())
	return ' '.join(result)


def _fetch_subpages(parent_id: int):
	sql = text(
		f"""
		SELECT ID, post_title
		FROM {_WP_POSTS_TABLE}
		WHERE (post_parent = :parent OR ID = :parent) AND post_type = 'page' AND post_status = 'publish'
		ORDER BY
			CASE WHEN ID = :parent THEN -1 ELSE menu_order END ASC,
			menu_order ASC,
			ID ASC
		"""
	)
	with Database().db.engine.connect() as conn:
		return conn.execute(sql, {"parent": parent_id}).mappings().all()


def _render_wp_page(page_id: int, back: str = None):
	page = _fetch_wp_page(page_id)
	if not page:
		abort(404)

	parent_id = page["post_parent"] or page["ID"]
	subpages_raw = _fetch_subpages(parent_id) if parent_id else []
	subpages = [{"ID": sp["ID"], "post_title": _title_case(sp["post_title"])} for sp in subpages_raw]
	content_html = Markup(wpautop(page["post_content"] or ""))
	back_link = (back or "").strip().lstrip("/")

	return render_template(
		"about.html",
		page_title=_title_case(page["post_title"]),
		content=content_html,
		subpages=subpages,
		current_page=page["ID"],
		back=back_link,
		page_routes=_PAGE_ID_TO_ROUTE,
	)


@about_page.route("/about", methods=['GET'])
def about():
	return _render_wp_page(_ABOUT_PAGE_ID)


@about_page.route("/submissions", methods=['GET'])
def submissions():
	"""Render the WordPress-backed submissions information page."""
	return _render_wp_page(_SUBMISSIONS_PAGE_ID)


@about_page.route("/resources", methods=['GET'])
def resources():
	return _render_wp_page(_RESOURCES_PAGE_ID)


@about_page.route("/explain", methods=['GET'])
def explain():
	return _render_wp_page(_EXPLAIN_PAGE_ID, back=request.args.get("back"))


@about_page.route("/getwp/<int:page_id>", methods=['GET'])
@about_page.route("/home/getwp/<int:page_id>", methods=['GET'])
def getwp(page_id: int):
	return _render_wp_page(page_id, back=request.args.get("back"))
