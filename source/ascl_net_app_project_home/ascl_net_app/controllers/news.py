#!/usr/bin/python

import math
import re

from flask import Blueprint, render_template, abort, request, redirect, Response
from markupsafe import Markup
from sqlalchemy import text

from ascl_core.database.connections import Trillian2DBConnection as db
from ascl_net_app.utilities.wordpress import wpautop, strip_tags

news_page = Blueprint("news_page", __name__)
_WP_POSTS_TABLE = "ascl_wordpress.0hjpDo4yM_posts"
_WP_USERS_TABLE = "ascl_wordpress.0hjpDo4yM_users"
_WP_TERMS_TABLE = "ascl_wordpress.0hjpDo4yM_terms"
_WP_TERM_TAX_TABLE = "ascl_wordpress.0hjpDo4yM_term_taxonomy"
_WP_TERM_REL_TABLE = "ascl_wordpress.0hjpDo4yM_term_relationships"


def _excerpt(content: str, length: int = 220) -> str:
	plain = strip_tags(content)
	if len(plain) <= length:
		return plain
	return plain[:length].rstrip() + "…"


def _parse_page(page_value: str, default: int = 1) -> int:
	try:
		return max(int(page_value), 1)
	except (TypeError, ValueError):
		return default


def _sanitize_query(query_value: str) -> str:
	query = (query_value or "").strip()
	return query[:120]


def _sanitize_slug(slug_value: str) -> str:
	slug = (slug_value or "").strip().lower()
	return slug if re.fullmatch(r"[a-z0-9-]+", slug) else ""


def _sanitize_archive(archive_value: str) -> str:
	archive = (archive_value or "").strip()
	return archive if re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", archive) else ""


def _build_post_filter_sql(search_query: str = "", category_slug: str = "", archive_month: str = "", author_slug: str = ""):
	joins = []
	where = ["p.post_type = 'post'", "p.post_status = 'publish'"]
	params = {}

	if category_slug:
		joins.append(f"JOIN {_WP_TERM_REL_TABLE} tr ON tr.object_id = p.ID")
		joins.append(f"JOIN {_WP_TERM_TAX_TABLE} tt ON tt.term_taxonomy_id = tr.term_taxonomy_id")
		joins.append(f"JOIN {_WP_TERMS_TABLE} t ON t.term_id = tt.term_id")
		where.append("tt.taxonomy = 'category'")
		where.append("t.slug = :category_slug")
		params["category_slug"] = category_slug

	if archive_month:
		where.append("DATE_FORMAT(p.post_date, '%Y-%m') = :archive_month")
		params["archive_month"] = archive_month

	if author_slug:
		joins.append(f"JOIN {_WP_USERS_TABLE} au ON au.ID = p.post_author")
		where.append("au.user_nicename = :author_slug")
		params["author_slug"] = author_slug

	if search_query:
		where.append("(p.post_title LIKE :search_like OR p.post_content LIKE :search_like OR p.post_excerpt LIKE :search_like)")
		params["search_like"] = f"%{search_query}%"

	return "\n".join(joins), " AND ".join(where), params


def _fetch_posts(limit: int, offset: int = 0, search_query: str = "", category_slug: str = "", archive_month: str = "", author_slug: str = ""):
	join_sql, where_sql, params = _build_post_filter_sql(
		search_query=search_query, category_slug=category_slug, archive_month=archive_month, author_slug=author_slug
	)
	sql = text(
		f"""
		SELECT filtered.*, u.display_name AS author_name, u.user_nicename AS author_slug
		FROM (
			SELECT DISTINCT p.ID, p.post_title, p.post_date, p.post_name AS slug,
				p.post_content, p.post_excerpt, p.post_author
			FROM {_WP_POSTS_TABLE} p
			{join_sql}
			WHERE {where_sql}
		) filtered
		LEFT JOIN {_WP_USERS_TABLE} u ON u.ID = filtered.post_author
		ORDER BY filtered.post_date DESC
		LIMIT :limit OFFSET :offset
		"""
	)
	params.update({"limit": limit, "offset": offset})
	with db.engine.connect() as conn:
		rows = conn.execute(sql, params).mappings().all()
	return rows


def _count_posts(search_query: str = "", category_slug: str = "", archive_month: str = "", author_slug: str = ""):
	join_sql, where_sql, params = _build_post_filter_sql(
		search_query=search_query, category_slug=category_slug, archive_month=archive_month, author_slug=author_slug
	)
	sql = text(
		f"""
		SELECT COUNT(DISTINCT p.ID) AS cnt
		FROM {_WP_POSTS_TABLE} p
		{join_sql}
		WHERE {where_sql}
		"""
	)
	with db.engine.connect() as conn:
		row = conn.execute(sql, params).first()
	return row[0] if row else 0


def _fetch_post_by_slug(slug: str):
	sql = text(
		f"""
		SELECT p.ID, p.post_title, p.post_date, p.post_name AS slug, p.post_content,
			u.display_name AS author_name, u.user_nicename AS author_slug
		FROM {_WP_POSTS_TABLE} p
		LEFT JOIN {_WP_USERS_TABLE} u ON u.ID = p.post_author
		WHERE p.post_type = 'post' AND p.post_status = 'publish' AND p.post_name = :slug
		LIMIT 1
		"""
	)
	with db.engine.connect() as conn:
		row = conn.execute(sql, {"slug": slug}).mappings().first()
	return row


def _fetch_categories_for_posts(post_ids):
	"""Fetch categories for a list of post IDs. Returns {post_id: [{"name": ..., "slug": ...}, ...]}."""
	if not post_ids:
		return {}
	placeholders = ", ".join(f":id_{i}" for i in range(len(post_ids)))
	sql = text(
		f"""
		SELECT tr.object_id AS post_id, t.name, t.slug
		FROM {_WP_TERM_REL_TABLE} tr
		JOIN {_WP_TERM_TAX_TABLE} tt ON tt.term_taxonomy_id = tr.term_taxonomy_id
		JOIN {_WP_TERMS_TABLE} t ON t.term_id = tt.term_id
		WHERE tt.taxonomy = 'category' AND tr.object_id IN ({placeholders})
		ORDER BY t.name
		"""
	)
	params = {f"id_{i}": pid for i, pid in enumerate(post_ids)}
	with db.engine.connect() as conn:
		rows = conn.execute(sql, params).mappings().all()
	grouped = {}
	for row in rows:
		pid = row["post_id"]
		if pid not in grouped:
			grouped[pid] = []
		grouped[pid].append({"name": row["name"], "slug": row["slug"]})
	return grouped


_WP_COMMENTS_TABLE = _WP_POSTS_TABLE.replace("_posts", "_comments")


def _fetch_comments_for_post(post_id):
	"""Fetch approved comments for a post, returning a threaded tree."""
	sql = text(
		f"""
		SELECT comment_ID, comment_author, comment_author_url, comment_date,
			comment_content, comment_parent
		FROM {_WP_COMMENTS_TABLE}
		WHERE comment_post_ID = :post_id AND comment_approved = '1' AND comment_type IN ('comment', '')
		ORDER BY comment_date ASC
		"""
	)
	with db.engine.connect() as conn:
		rows = conn.execute(sql, {"post_id": post_id}).mappings().all()

	# Build threaded tree
	by_id = {}
	roots = []
	for row in rows:
		node = {
			"id": row["comment_ID"],
			"author": row["comment_author"] or "Anonymous",
			"author_url": row["comment_author_url"] or "",
			"date": row["comment_date"],
			"content": Markup(wpautop(row["comment_content"] or "")),
			"children": [],
		}
		by_id[node["id"]] = node
		parent_id = row["comment_parent"]
		if parent_id and parent_id in by_id:
			by_id[parent_id]["children"].append(node)
		else:
			roots.append(node)
	return roots


def _fetch_recent_posts(limit: int = 8):
	sql = text(
		f"""
		SELECT post_title AS title, post_name AS slug, post_date AS date
		FROM {_WP_POSTS_TABLE}
		WHERE post_type = 'post' AND post_status = 'publish'
		ORDER BY post_date DESC
		LIMIT :limit
		"""
	)
	with db.engine.connect() as conn:
		return conn.execute(sql, {"limit": limit}).mappings().all()


def _fetch_categories(limit: int = 20):
	sql = text(
		f"""
		SELECT t.name, t.slug, COUNT(DISTINCT p.ID) AS post_count
		FROM {_WP_TERM_TAX_TABLE} tt
		JOIN {_WP_TERMS_TABLE} t ON t.term_id = tt.term_id
		JOIN {_WP_TERM_REL_TABLE} tr ON tr.term_taxonomy_id = tt.term_taxonomy_id
		JOIN {_WP_POSTS_TABLE} p ON p.ID = tr.object_id
		WHERE tt.taxonomy = 'category'
		  AND p.post_type = 'post'
		  AND p.post_status = 'publish'
		GROUP BY t.term_id, t.name, t.slug
		HAVING post_count > 0
		ORDER BY post_count DESC, t.name ASC
		LIMIT :limit
		"""
	)
	with db.engine.connect() as conn:
		return conn.execute(sql, {"limit": limit}).mappings().all()


def _fetch_archives(limit: int = 24):
	sql = text(
		f"""
		SELECT
			DATE_FORMAT(MIN(post_date), '%Y-%m') AS archive_key,
			DATE_FORMAT(MIN(post_date), '%M %Y') AS archive_label,
			COUNT(*) AS post_count
		FROM {_WP_POSTS_TABLE}
		WHERE post_type = 'post' AND post_status = 'publish'
		GROUP BY YEAR(post_date), MONTH(post_date)
		ORDER BY MIN(post_date) DESC
		LIMIT :limit
		"""
	)
	with db.engine.connect() as conn:
		return conn.execute(sql, {"limit": limit}).mappings().all()


def _fetch_archive_posts_by_month(limit: int = 24):
	"""Fetch post titles/slugs grouped by archive month (for popup previews)."""
	sql = text(
		f"""
		SELECT DATE_FORMAT(post_date, '%Y-%m') AS month_key, post_title, post_name AS slug
		FROM {_WP_POSTS_TABLE}
		WHERE post_type = 'post' AND post_status = 'publish'
		  AND post_date >= (
		    SELECT MIN(post_date) FROM (
		      SELECT MIN(post_date) AS post_date
		      FROM {_WP_POSTS_TABLE}
		      WHERE post_type = 'post' AND post_status = 'publish'
		      GROUP BY YEAR(post_date), MONTH(post_date)
		      ORDER BY post_date DESC
		      LIMIT :limit
		    ) sub
		  )
		ORDER BY post_date DESC
		"""
	)
	with db.engine.connect() as conn:
		rows = conn.execute(sql, {"limit": limit}).mappings().all()
	grouped = {}
	for row in rows:
		key = row["month_key"]
		if key not in grouped:
			grouped[key] = []
		grouped[key].append({"title": row["post_title"], "slug": row["slug"]})
	return grouped


def _fetch_sidebar_data():
	return {
		"recent_posts": _fetch_recent_posts(),
		"categories": _fetch_categories(),
		"archives": _fetch_archives(),
		"archive_posts": _fetch_archive_posts_by_month(),
	}


@news_page.route("/news")
def news_index():
	page = _parse_page(request.args.get("page", "1"))
	search_query = _sanitize_query(request.args.get("q"))
	category_slug = _sanitize_slug(request.args.get("category"))
	archive_month = _sanitize_archive(request.args.get("archive"))
	author_slug_filter = _sanitize_slug(request.args.get("author"))

	page_size = 10
	offset = (page - 1) * page_size

	total = _count_posts(search_query=search_query, category_slug=category_slug, archive_month=archive_month, author_slug=author_slug_filter)
	total_pages = max(1, math.ceil(total / page_size)) if page_size else 1
	page = min(page, total_pages)
	offset = (page - 1) * page_size

	rows = _fetch_posts(
		limit=page_size,
		offset=offset,
		search_query=search_query,
		category_slug=category_slug,
		archive_month=archive_month,
		author_slug=author_slug_filter,
	)

	post_ids = [row["ID"] for row in rows]
	categories_map = _fetch_categories_for_posts(post_ids)

	posts = []
	for row in rows:
		content_html = Markup(wpautop(row["post_content"] or ""))
		posts.append(
			{
				"title": row["post_title"],
				"slug": row["slug"],
				"date": row["post_date"],
				"author": row["author_name"] or "",
				"author_slug": row["author_slug"] or "",
				"content": content_html,
				"categories": categories_map.get(row["ID"], []),
			}
		)

	return render_template(
		"news_list.html",
		posts=posts,
		total=total,
		page=page,
		page_size=page_size,
		total_pages=total_pages,
		q=search_query,
		category=category_slug,
		archive=archive_month,
		author=author_slug_filter,
		sidebar=_fetch_sidebar_data(),
	)


@news_page.route("/news/feed")
def news_feed():
	rows = _fetch_posts(limit=20)
	items = []
	for row in rows:
		title = row["post_title"] or ""
		slug = row["slug"] or ""
		date = row["post_date"]
		content = wpautop(row["post_content"] or "")
		excerpt = _excerpt(row["post_content"] or "", length=500)
		pub_date = date.strftime("%a, %d %b %Y %H:%M:%S +0000") if date else ""
		items.append({
			"title": title,
			"link": f"https://ascl.net/news/{slug}",
			"pub_date": pub_date,
			"description": excerpt,
			"content": content,
		})

	from xml.sax.saxutils import escape as xml_escape

	xml_items = []
	for item in items:
		xml_items.append(
			f"<item>\n"
			f"<title>{xml_escape(item['title'])}</title>\n"
			f"<link>{xml_escape(item['link'])}</link>\n"
			f"<pubDate>{item['pub_date']}</pubDate>\n"
			f"<description>{xml_escape(item['description'])}</description>\n"
			f"<content:encoded><![CDATA[{item['content']}]]></content:encoded>\n"
			f"</item>"
		)

	xml = (
		'<?xml version="1.0" encoding="UTF-8"?>\n'
		'<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/">\n'
		'<channel>\n'
		'<title>ASCL News</title>\n'
		'<link>https://ascl.net/news</link>\n'
		'<description>Astrophysics Source Code Library News</description>\n'
		'<language>en-US</language>\n'
		+ "\n".join(xml_items) + "\n"
		'</channel>\n'
		'</rss>'
	)
	return Response(xml, mimetype="application/rss+xml")


@news_page.route("/news/<slug>")
def news_detail(slug):
	row = _fetch_post_by_slug(slug)
	if not row:
		abort(404)

	content_html = Markup(wpautop(row["post_content"] or ""))
	categories_map = _fetch_categories_for_posts([row["ID"]])
	comments = _fetch_comments_for_post(row["ID"])

	post = {
		"title": row["post_title"],
		"slug": row["slug"],
		"date": row["post_date"],
		"author": row["author_name"] or "",
		"author_slug": row["author_slug"] or "",
		"content": content_html,
		"categories": categories_map.get(row["ID"], []),
	}

	comment_error = request.args.get("comment_error")
	return render_template("news_detail.html", post=post, comments=comments, comment_error=comment_error, sidebar=_fetch_sidebar_data())


@news_page.route("/news/<slug>/comment", methods=["POST"])
def post_comment(slug):
	row = _fetch_post_by_slug(slug)
	if not row:
		abort(404)

	comment_text = (request.form.get("comment") or "").strip()
	author_name = (request.form.get("author") or "").strip()
	author_email = (request.form.get("email") or "").strip()
	author_url = (request.form.get("url") or "").strip()

	if not comment_text or not author_name or not author_email:
		return redirect(f"/news/{slug}?comment_error=Name%2C+email%2C+and+comment+are+required.#respond")

	# Sanitize: strip HTML tags from comment text
	comment_content = strip_tags(comment_text)

	sql = text(
		f"""
		INSERT INTO {_WP_POSTS_TABLE.replace('_posts', '_comments')}
			(comment_post_ID, comment_author, comment_author_email, comment_author_url,
			 comment_author_IP, comment_date, comment_date_gmt, comment_content,
			 comment_karma, comment_approved, comment_agent, comment_type, comment_parent, user_id)
		VALUES
			(:post_id, :author, :email, :url,
			 :ip, NOW(), UTC_TIMESTAMP(), :content,
			 0, '1', :agent, 'comment', 0, 0)
		"""
	)
	with db.engine.connect() as conn:
		conn.execute(sql, {
			"post_id": row["ID"],
			"author": author_name[:200],
			"email": author_email[:100],
			"url": author_url[:200],
			"ip": request.remote_addr or "",
			"content": comment_content,
			"agent": (request.headers.get("User-Agent") or "")[:255],
		})
		conn.commit()

	return redirect(f"/news/{slug}#comments")


@news_page.route("/wordpress")
def wordpress_redirect():
	return redirect("/news", code=301)
