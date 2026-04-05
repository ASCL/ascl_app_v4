"""Tests for admin page access control and authenticated page rendering."""

import pytest


# ---------------------------------------------------------------------------
# Helper to simulate a logged-in admin session
# ---------------------------------------------------------------------------

@pytest.fixture()
def admin_client(client):
	"""Flask test client with admin session pre-set."""
	with client.session_transaction() as sess:
		sess["user_id"] = 1
	return client


# ---------------------------------------------------------------------------
# Unauthenticated access should redirect
# ---------------------------------------------------------------------------

PROTECTED_ROUTES = [
	"/admin/dashboard",
	"/admin/unpublished",
	"/admin/archived",
	"/admin/insert_code",
	"/admin/corrections",
]


@pytest.mark.parametrize("path", PROTECTED_ROUTES)
def test_admin_routes_redirect_when_not_logged_in(client, path):
	"""Admin routes should redirect unauthenticated users, not 500."""
	resp = client.get(path, follow_redirects=False)
	assert resp.status_code in (301, 302), \
		f"{path} returned {resp.status_code} for unauthenticated user"


# ---------------------------------------------------------------------------
# Authenticated admin pages
# ---------------------------------------------------------------------------

def test_admin_home_renders_when_logged_in(admin_client):
	resp = admin_client.get("/admin/")
	assert resp.status_code == 200


def test_admin_insert_code_form_renders(admin_client):
	resp = admin_client.get("/admin/insert_code")
	assert resp.status_code == 200
	html = resp.get_data(as_text=True)
	assert "title" in html.lower()


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
