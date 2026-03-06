import pytest
import json
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


def test_search_typesense_no_results_falls_back_to_mysql(client, monkeypatch):
	from ascl_net_app.controllers import search as search_controller
	from ascl_net_app.services import typesense_client

	class FakeTypesenseClient:
		enabled = True
		fallback_to_mysql = True

		def is_healthy(self):
			return True

		def search(self, **kwargs):
			return {"found": 0, "hits": [], "search_time_ms": 2}

	def fake_search_mysql(query_string, published_only=True, page=1, per_page=20):
		return [], 0

	def fake_render_template(template_name, **context):
		return json.dumps({
			"search_method": context.get("search_method"),
			"mysql_fallback_reason": context.get("mysql_fallback_reason"),
			"result_count": context.get("result_count"),
		})

	monkeypatch.setattr(typesense_client, "get_typesense_client", lambda: FakeTypesenseClient())
	monkeypatch.setattr(search_controller, "search_mysql", fake_search_mysql)
	monkeypatch.setattr(search_controller, "render_template", fake_render_template)

	resp = client.get("/search?q=definitely-not-in-typesense")
	assert resp.status_code == 200

	payload = json.loads(resp.get_data(as_text=True))
	assert payload["search_method"] == "mysql"
	assert payload["mysql_fallback_reason"] == "no_results"
	assert payload["result_count"] == 0


def test_search_suggest_uses_typesense(client, monkeypatch):
	from ascl_net_app.services import typesense_client

	class FakeTypesenseClient:
		enabled = True
		fallback_to_mysql = True

		def is_healthy(self):
			return True

		def search(self, **kwargs):
			return {
				"found": 1,
				"hits": [
					{"document": {"ascl_id": "2306.019", "title": "Test Code"}}
				],
			}

	monkeypatch.setattr(typesense_client, "get_typesense_client", lambda: FakeTypesenseClient())

	resp = client.get("/search/suggest?q=test&limit=5")
	assert resp.status_code == 200
	payload = resp.get_json()
	assert payload["method"] == "typesense"
	assert len(payload["suggestions"]) == 1
	assert payload["suggestions"][0]["ascl_id"] == "2306.019"


def test_author_query_variants_include_initial_form():
	from ascl_net_app.controllers.search import _author_query_variants
	variants = _author_query_variants("Smith, John Kevin")
	assert "Smith J K" in variants


def test_author_name_matches_avoids_surname_only_false_positive():
	from ascl_net_app.controllers.search import _author_name_matches
	assert _author_name_matches("Baker, Tessa", "Baker, Tessa")
	assert _author_name_matches("Baker, T.", "Baker, Tessa")
	assert not _author_name_matches("Baker, Fergus", "Baker, Tessa")
	assert not _author_name_matches("Baker, Tessa", "Baker, Paul T")
	assert _author_name_matches("Baker, Paul T.", "Baker, Paul T")


def test_author_suggest_uses_typesense(client, monkeypatch):
	from ascl_net_app.services import typesense_client

	class FakeTypesenseClient:
		enabled = True
		fallback_to_mysql = True

		def is_healthy(self):
			return True

		def search(self, **kwargs):
			return {
				"found": 1,
				"hits": [
					{"document": {"credit": "Pietrow, Alexander G. M.; Someone Else"}}
				],
			}

	monkeypatch.setattr(typesense_client, "get_typesense_client", lambda: FakeTypesenseClient())
	resp = client.get("/search/author_suggest?q=Pietrow")
	assert resp.status_code == 200
	payload = resp.get_json()
	assert payload["method"] == "typesense"
	assert "Pietrow, Alexander G. M." in payload["suggestions"]


def test_admin_typesense_status_endpoint(client, monkeypatch):
	from ascl_net_app.services import typesense_client

	class FakeTypesenseClient:
		enabled = True
		base_url = "http://127.0.0.1:8108"
		collection = "codes"
		fallback_to_mysql = True

		def is_healthy(self, force_check=False):
			return True

		def get_stats(self):
			return {"num_documents": 1234}

	with client.session_transaction() as sess:
		sess["user_id"] = 1

	monkeypatch.setattr(typesense_client, "get_typesense_client", lambda: FakeTypesenseClient())

	resp = client.get("/admin/api/typesense_status")
	assert resp.status_code == 200
	payload = resp.get_json()
	assert payload["enabled"] is True
	assert payload["healthy"] is True
	assert payload["authenticated"] is True
	assert payload["num_documents"] == 1234


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
