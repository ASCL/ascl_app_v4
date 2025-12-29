#!/usr/bin/python

from datetime import datetime
import math
import re

from flask import Blueprint, render_template, abort, request
from markupsafe import Markup
from sqlalchemy import text

from ascl_core.database.connections import Trillian2DBConnection as db

news_page = Blueprint("news_page", __name__)

# Basic wrapper to mimic wpautop behavior for paragraphing.
def _wpautop(content: str) -> str:
	if not content:
		return ""
	# Normalize newlines
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


def _strip_tags(text_value: str) -> str:
	if not text_value:
		return ""
	return re.sub(r"<[^>]+>", "", text_value)


def _excerpt(content: str, length: int = 220) -> str:
	plain = _strip_tags(content)
	if len(plain) <= length:
		return plain
	return plain[:length].rstrip() + "…"


def _fetch_posts(limit: int, offset: int = 0):
	sql = text(
		"""
		SELECT ID, post_title, post_date, post_name AS slug, post_content, post_excerpt
		FROM ascl_wordpress.0hjpDo4yM_posts
		WHERE post_type = 'post' AND post_status = 'publish'
		ORDER BY post_date DESC
		LIMIT :limit OFFSET :offset
		"""
	)
	with db.engine.connect() as conn:
		rows = conn.execute(sql, {"limit": limit, "offset": offset}).mappings().all()
	return rows


def _count_posts():
	sql = text(
		"""
		SELECT COUNT(*) AS cnt
		FROM ascl_wordpress.0hjpDo4yM_posts
		WHERE post_type = 'post' AND post_status = 'publish'
		"""
	)
	with db.engine.connect() as conn:
		row = conn.execute(sql).first()
	return row[0] if row else 0


def _fetch_post_by_slug(slug: str):
	sql = text(
		"""
		SELECT ID, post_title, post_date, post_name AS slug, post_content
		FROM ascl_wordpress.0hjpDo4yM_posts
		WHERE post_type = 'post' AND post_status = 'publish' AND post_name = :slug
		LIMIT 1
		"""
	)
	with db.engine.connect() as conn:
		row = conn.execute(sql, {"slug": slug}).mappings().first()
	return row


@news_page.route("/news")
def news_index():
	page = max(int(request.args.get("page", 1)), 1)
	page_size = 10
	offset = (page - 1) * page_size

	total = _count_posts()
	rows = _fetch_posts(limit=page_size, offset=offset)

	posts = []
	for row in rows:
		content = row["post_excerpt"] or row["post_content"] or ""
		posts.append(
			{
				"title": row["post_title"],
				"slug": row["slug"],
				"date": row["post_date"],
				"excerpt": _excerpt(content),
			}
		)

	total_pages = max(1, math.ceil(total / page_size)) if page_size else 1

	return render_template(
		"news_list.html",
		posts=posts,
		page=page,
		total_pages=total_pages,
	)


@news_page.route("/news/<slug>")
def news_detail(slug):
	row = _fetch_post_by_slug(slug)
	if not row:
		abort(404)

	content_html = Markup(_wpautop(row["post_content"] or ""))

	post = {
		"title": row["post_title"],
		"slug": row["slug"],
		"date": row["post_date"],
		"content": content_html,
	}

	return render_template("news_detail.html", post=post)
