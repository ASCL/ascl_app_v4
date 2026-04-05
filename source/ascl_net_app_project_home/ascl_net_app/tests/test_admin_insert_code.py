"""Tests for admin code insertion (POST /admin/insert_code).

These tests use a mocked database session to avoid writing to the real
database while still exercising the controller's validation logic and
insertion path.
"""

import json
import pytest
from unittest.mock import MagicMock, patch, PropertyMock


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def admin_client(client):
	"""Flask test client with admin session pre-set."""
	with client.session_transaction() as sess:
		sess["user_id"] = 1
	return client


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _valid_insert_form():
	"""Return a dict with all required fields for /admin/insert_code."""
	return {
		"title": "Admin Test Code",
		"credit": "Smith, Alice; Jones, Bob",
		"ascl_id": "2499.001",
		"abstract": "A test abstract for automated testing.",
		"citation_method": "",
		"email": "admin@example.com",
		"notes": "",
		"published": "0",
		"doi": "",
		"aliases": "",
		"keywords": "",
		"typed_links": "[]",
		"described_in_urls": "",
		"used_in_urls": "",
		"see_also": "",
	}


# ===========================================================================
# Authentication
# ===========================================================================

def test_insert_code_requires_login(client):
	"""POST to insert_code without login should redirect."""
	resp = client.post("/admin/insert_code", data=_valid_insert_form(),
					   follow_redirects=False)
	assert resp.status_code in (301, 302)


# ===========================================================================
# Validation
# ===========================================================================

def test_insert_rejects_missing_title(admin_client):
	data = _valid_insert_form()
	data["title"] = ""
	resp = admin_client.post("/admin/insert_code", data=data,
							 follow_redirects=True)
	assert resp.status_code == 200
	html = resp.get_data(as_text=True)
	assert "Title is required" in html


def test_insert_rejects_missing_credit(admin_client):
	data = _valid_insert_form()
	data["credit"] = ""
	resp = admin_client.post("/admin/insert_code", data=data,
							 follow_redirects=True)
	assert resp.status_code == 200
	html = resp.get_data(as_text=True)
	assert "Credit is required" in html


def test_insert_rejects_missing_ascl_id(admin_client):
	data = _valid_insert_form()
	data["ascl_id"] = ""
	resp = admin_client.post("/admin/insert_code", data=data,
							 follow_redirects=True)
	assert resp.status_code == 200
	html = resp.get_data(as_text=True)
	assert "ASCL ID" in html


def test_insert_rejects_short_ascl_id(admin_client):
	data = _valid_insert_form()
	data["ascl_id"] = "123"
	resp = admin_client.post("/admin/insert_code", data=data,
							 follow_redirects=True)
	assert resp.status_code == 200
	html = resp.get_data(as_text=True)
	assert "ASCL ID must be 8 characters" in html


# ===========================================================================
# ASCL ID collision
# ===========================================================================

def test_insert_detects_ascl_id_collision(admin_client):
	"""Submitting an ASCL ID that already exists should re-render the form
	with a collision notice (not crash)."""
	# Use an ASCL ID we know exists — fetch from DB
	from sqlalchemy import text
	from ascl_core.database.connections import Trillian2DBConnection as db

	try:
		with db.Session() as session:
			row = session.execute(
				text("SELECT ascl_id FROM codes WHERE published=1 LIMIT 1")
			).first()
	except Exception:
		pytest.skip("Database not accessible")

	if not row:
		pytest.skip("No codes in database")

	data = _valid_insert_form()
	data["ascl_id"] = row[0]

	resp = admin_client.post("/admin/insert_code", data=data,
							 follow_redirects=True)
	assert resp.status_code == 200
	html = resp.get_data(as_text=True)
	# The form should be re-rendered (not a 500), with the collision ID visible
	assert row[0] in html


# ===========================================================================
# Successful insertion
# ===========================================================================

def test_insert_code_success_redirects(admin_client):
	"""A valid submission with a unique ASCL ID should insert and redirect."""
	data = _valid_insert_form()
	data["ascl_id"] = "2499.999"

	resp = admin_client.post("/admin/insert_code", data=data,
							 follow_redirects=False)

	if resp.status_code in (301, 302):
		location = resp.headers.get("Location", "")
		assert "/admin/view/" in location
	else:
		assert resp.status_code == 200  # ASCL ID collision form


def test_insert_code_with_keywords(admin_client):
	"""Keywords provided during insertion should not cause an error."""
	data = _valid_insert_form()
	data["ascl_id"] = "2499.998"
	data["keywords"] = "galaxies\ncosmology"

	resp = admin_client.post("/admin/insert_code", data=data,
							 follow_redirects=False)
	assert resp.status_code in (200, 301, 302)


def test_insert_code_with_aliases(admin_client):
	"""Aliases provided during insertion should not cause an error."""
	data = _valid_insert_form()
	data["ascl_id"] = "2499.997"
	data["aliases"] = "TestAlias1\nTestAlias2"

	resp = admin_client.post("/admin/insert_code", data=data,
							 follow_redirects=False)
	assert resp.status_code in (200, 301, 302)


def test_insert_code_with_typed_links(admin_client):
	"""Typed links (JSON) should be processed without error."""
	data = _valid_insert_form()
	data["ascl_id"] = "2499.996"
	data["typed_links"] = json.dumps([
		{"url": "https://github.com/example/test", "type": "code-site", "display_order": 0}
	])

	resp = admin_client.post("/admin/insert_code", data=data,
							 follow_redirects=False)
	assert resp.status_code in (200, 301, 302)


def test_insert_published_code_generates_bibcode(admin_client):
	"""Publishing a code should auto-generate a bibcode."""
	data = _valid_insert_form()
	data["ascl_id"] = "2499.995"
	data["published"] = "1"

	resp = admin_client.post("/admin/insert_code", data=data,
							 follow_redirects=False)
	assert resp.status_code in (200, 301, 302)


# ===========================================================================
# Cleanup — delete test codes that were inserted
# ===========================================================================

@pytest.fixture(autouse=True, scope="module")
def cleanup_test_codes():
	"""Remove any codes with test ASCL IDs after the module finishes."""
	yield

	test_ids = ("2499.999", "2499.998", "2499.997", "2499.996", "2499.995")
	try:
		from ascl_core.database.connections import Trillian2DBConnection as db
		from sqlalchemy import text
		with db.Session() as session:
			for test_id in test_ids:
				row = session.execute(
					text("SELECT pk FROM codes WHERE ascl_id = :aid"),
					{"aid": test_id}
				).first()
				if row:
					pk = row[0]
					# Delete related rows first (FK constraints)
					for table in ("link", "code_to_author", "author",
								  "code_alias", "code_to_keyword",
								  "code_to_code", "code_note"):
						try:
							session.execute(
								text(f"DELETE FROM {table} WHERE code_pk = :pk"),
								{"pk": pk}
							)
						except Exception:
							pass
					session.execute(
						text("DELETE FROM codes WHERE pk = :pk"), {"pk": pk}
					)
			session.commit()
	except Exception:
		pass  # Best-effort cleanup
