"""Tests for public page rendering (index, browse, code detail, news, about)."""

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text

from ascl_core.database.connections import Trillian2DBConnection as db
from ascl_core.database.connections import WordpressDBConnection as wp_db


def test_index_ok(client):
	resp = client.get("/")
	assert resp.status_code == 200


def test_browse_ok(client):
	resp = client.get("/code/all?limit=1")
	assert resp.status_code == 200


def test_code_detail_ok(client):
	# Grab one code ID from the database to avoid hardcoding
	try:
		with db.Session() as session:
			code = session.execute(text("SELECT ascl_id FROM codes WHERE published=1 LIMIT 1")).first()
	except SQLAlchemyError:
		pytest.skip("Codes table not accessible; skipping code detail test")

	if not code:
		pytest.skip("No codes found to test code detail")

	ascl_id = code[0]
	resp = client.get(f"/{ascl_id}")
	assert resp.status_code == 200


def test_news_endpoints_ok(client):
	# Fetch one published post slug from WordPress; skip if not available
	try:
		with wp_db.engine.connect() as conn:
			row = conn.execute(
				text(
					"SELECT post_name FROM 0hjpDo4yM_posts "
					"WHERE post_type='post' AND post_status='publish' "
					"ORDER BY post_date DESC LIMIT 1"
				)
			).first()
	except Exception:
		pytest.skip("WordPress database not accessible; skipping news tests")

	if not row:
		pytest.skip("No published news posts found")

	slug = row[0]

	resp_list = client.get("/news")
	assert resp_list.status_code == 200

	resp_detail = client.get(f"/news/{slug}")
	assert resp_detail.status_code == 200


def test_about_from_wordpress(client):
	# Ensure /about pulls the published WordPress page (ID=2)
	try:
		with wp_db.engine.connect() as conn:
			row = conn.execute(
				text(
					"SELECT post_title FROM 0hjpDo4yM_posts "
					"WHERE ID = 2 AND post_type='page' AND post_status='publish' "
					"LIMIT 1"
				)
			).first()
	except Exception:
		pytest.skip("WordPress database not accessible; skipping about page test")

	if not row:
		pytest.skip("About page not present in WordPress; skipping about page test")

	post_title = row[0]

	resp = client.get("/about")
	assert resp.status_code == 200
	assert post_title in resp.get_data(as_text=True)


def test_submissions_renders_wp_page_not_redirect(client, monkeypatch):
	from ascl_net_app.controllers import about as about_controller

	called = {}

	def fake_render_wp_page(page_id: int, back: str = None):
		called["page_id"] = page_id
		called["back"] = back
		return "submissions page"

	monkeypatch.setattr(about_controller, "_render_wp_page", fake_render_wp_page)

	resp = client.get("/submissions", follow_redirects=False)
	assert resp.status_code == 200
	assert resp.headers.get("Location") is None
	assert resp.get_data(as_text=True) == "submissions page"
	assert called["page_id"] == about_controller._SUBMISSIONS_PAGE_ID
	assert called["back"] is None
