"""Tests for search functionality (Typesense, MySQL fallback, author matching)."""

import json
import pytest


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


# ===========================================================================
# 0000.000 codes must link by pk, not by ascl_id
# ===========================================================================

def test_mysql_suggest_0000_links_by_pk(client):
    """MySQL autocomplete suggestions for 0000.000 codes should use /code/v/<pk>."""
    resp = client.get("/search/suggest?q=ascl&limit=20")
    assert resp.status_code == 200
    payload = resp.get_json()

    for s in payload.get("suggestions", []):
        if s["ascl_id"] == "0000.000":
            assert s["url"].startswith("/code/v/"), (
                f"0000.000 code '{s['title']}' links to '{s['url']}' "
                f"instead of /code/v/<pk>"
            )
            break


def test_typesense_suggest_0000_resolves_local_pk(client, monkeypatch):
    """Typesense 0000.000 suggestions should resolve pk from the local DB, not Typesense id."""
    from ascl_net_app.services import typesense_client
    from sqlalchemy import text as sa_text
    from ascl_net_app.model.database import Database

    # Find a real 0000.000 published code in the local DB
    session = Database().Session()
    row = session.execute(
        sa_text("SELECT pk, title FROM codes "
                "WHERE ascl_id = '0000.000' AND published = 1 LIMIT 1")
    ).first()
    if not row:
        pytest.skip("No published 0000.000 code in local database")
    local_pk, local_title = row[0], row[1]

    class FakeTypesenseClient:
        enabled = True
        fallback_to_mysql = True

        def is_healthy(self):
            return True

        def search(self, **kwargs):
            return {
                "found": 2,
                "hits": [
                    # Typesense id deliberately differs from local pk
                    {"document": {"id": "99999", "ascl_id": "0000.000",
                                  "title": local_title},
                     "highlight": {}},
                    {"document": {"id": "88", "ascl_id": "2306.019",
                                  "title": "Normal Code"},
                     "highlight": {}},
                ],
            }

    monkeypatch.setattr(typesense_client, "get_typesense_client", lambda: FakeTypesenseClient())

    resp = client.get("/search/suggest?q=test&limit=5")
    assert resp.status_code == 200
    payload = resp.get_json()

    suggestions = payload["suggestions"]
    assert len(suggestions) == 2

    # 0000.000 code should use the LOCAL pk, not Typesense's id
    assert suggestions[0]["url"] == f"/code/v/{local_pk}"
    # Normal code should link by ascl_id
    assert suggestions[1]["url"] == "/2306.019"


def test_typesense_suggest_0000_unknown_title_falls_back(client, monkeypatch):
    """If a 0000.000 title from Typesense doesn't exist locally, fall back to search."""
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
                    {"document": {"id": "99999", "ascl_id": "0000.000",
                                  "title": "NonexistentCodeXYZ123"},
                     "highlight": {}},
                ],
            }

    monkeypatch.setattr(typesense_client, "get_typesense_client", lambda: FakeTypesenseClient())

    resp = client.get("/search/suggest?q=test&limit=5")
    assert resp.status_code == 200
    payload = resp.get_json()

    suggestions = payload["suggestions"]
    assert len(suggestions) == 1
    # Should fall back to a search URL, not /code/v/ with a wrong pk
    assert suggestions[0]["url"].startswith("/search?")


def test_suggest_0000_never_links_to_slash_0000(client):
    """No autocomplete suggestion should ever link to /0000.000."""
    resp = client.get("/search/suggest?q=ascl&limit=50")
    assert resp.status_code == 200
    payload = resp.get_json()

    for s in payload.get("suggestions", []):
        assert s["url"] != "/0000.000", (
            f"Code '{s['title']}' links to /0000.000 — "
            f"0000.000 codes must use /code/v/<pk>"
        )


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
