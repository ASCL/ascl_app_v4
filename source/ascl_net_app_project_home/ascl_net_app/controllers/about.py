#!/usr/bin/python

import re
import flask
from flask import render_template, abort, request
from markupsafe import Markup
from sqlalchemy import text

from ascl_core.database.connections import Trillian2DBConnection as db

about_page = flask.Blueprint("about_page", __name__)

# WordPress posts table; used to pull static pages like About/Resources.
_WP_POSTS_TABLE = "ascl_wordpress.0hjpDo4yM_posts"
_ABOUT_PAGE_ID = 2
_SUBMISSIONS_PAGE_ID = 29
_RESOURCES_PAGE_ID = 697
_EXPLAIN_PAGE_ID = 1442


def _wpautop(content: str) -> str:
	"""Basic wpautop-style formatting to wrap loose text in <p> tags."""
	content = content or ""
	if not content:
		return ""
	content = content.replace("\r\n", "\n").strip()
	parts = re.split(r"\n\s*\n", content)
	paragraphs = []
	for part in parts:
		part = part.strip()
		if not part:
			continue
		if part.startswith("<p") or part.startswith("<div") or part.startswith("<ul") or part.startswith("<ol"):
			paragraphs.append(part)
		else:
			paragraphs.append(f"<p>{part}</p>")
	return "\n".join(paragraphs)


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
	with db.engine.connect() as conn:
		return conn.execute(sql, {"id": page_id}).mappings().first()


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
	with db.engine.connect() as conn:
		return conn.execute(sql, {"parent": parent_id}).mappings().all()


def _render_wp_page(page_id: int, back: str = None):
	page = _fetch_wp_page(page_id)
	if not page:
		abort(404)

	parent_id = page["post_parent"] or page["ID"]
	subpages = _fetch_subpages(parent_id) if parent_id else []
	content_html = Markup(_wpautop(page["post_content"] or ""))
	back_link = (back or "").strip().lstrip("/")

	return render_template(
		"about.html",
		page_title=page["post_title"],
		content=content_html,
		subpages=subpages,
		current_page=page["ID"],
		back=back_link,
	)


@about_page.route("/about", methods=['GET'])
def about():
	return _render_wp_page(_ABOUT_PAGE_ID)


@about_page.route("/submissions", methods=['GET'])
def submissions():
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
