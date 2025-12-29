import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text

from ascl_core.database.connections import Trillian2DBConnection as db
from ascl_core.database.connections import WordpressDBConnection as wp_db


def test_index_ok(client):
	resp = client.get("/")
	assert resp.status_code == 200


def test_browse_ok(client):
	resp = client.get("/browse?per_page=1")
	assert resp.status_code == 200


def test_search_ok(client):
	# Empty query should still render successfully
	resp = client.get("/search")
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
