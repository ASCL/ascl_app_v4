"""Tests for user-facing submission forms.

Covers:
  - POST /code/submit  (new code submission)
  - POST /<ascl_id>/suggest-edit  (corrections to existing codes)
"""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from ascl_core.database.connections import Trillian2DBConnection as db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

CHALLENGE_ANSWER = "physicsisphun"


def _valid_submit_form():
	"""Return a dict with all required fields for /code/submit."""
	return {
		"title": "Test Submission Code",
		"credit": "Smith, Alice; Jones, Bob",
		"authors_json": "",
		"abstract": "A test code for automated testing.",
		"site_urls": "https://example.com/test-code",
		"described_in_urls": "",
		"used_in_urls": "",
		"citation_method": "",
		"name": "Test User",
		"email": "test@example.com",
		"notes": "",
		"challenge": CHALLENGE_ANSWER,
	}


def _known_published_ascl_id():
	"""Fetch a published ASCL ID from the database (or skip)."""
	try:
		with db.Session() as session:
			row = session.execute(
				text("SELECT ascl_id FROM codes WHERE published=1 LIMIT 1")
			).first()
	except SQLAlchemyError:
		pytest.skip("Database not accessible")
	if not row:
		pytest.skip("No published codes found")
	return row[0]


# ===========================================================================
# /code/submit — GET
# ===========================================================================

def test_submit_form_renders(client):
	resp = client.get("/code/submit")
	assert resp.status_code == 200
	html = resp.get_data(as_text=True).lower()
	assert "title" in html
	assert "submit" in html


# ===========================================================================
# /code/submit — validation
# ===========================================================================

def test_submit_rejects_missing_title(client):
	data = _valid_submit_form()
	data["title"] = ""
	resp = client.post("/code/submit", data=data)
	assert resp.status_code == 200
	assert b"Title is required" in resp.data


def test_submit_rejects_missing_credit(client):
	data = _valid_submit_form()
	data["credit"] = ""
	resp = client.post("/code/submit", data=data)
	assert resp.status_code == 200
	assert b"Credit" in resp.data


def test_submit_rejects_missing_abstract(client):
	data = _valid_submit_form()
	data["abstract"] = ""
	resp = client.post("/code/submit", data=data)
	assert resp.status_code == 200
	assert b"Abstract is required" in resp.data


def test_submit_rejects_missing_site_url(client):
	data = _valid_submit_form()
	data["site_urls"] = ""
	resp = client.post("/code/submit", data=data)
	assert resp.status_code == 200
	assert b"code site URL" in resp.data


def test_submit_rejects_missing_name(client):
	data = _valid_submit_form()
	data["name"] = ""
	resp = client.post("/code/submit", data=data)
	assert resp.status_code == 200
	assert b"Your name is required" in resp.data


def test_submit_rejects_missing_email(client):
	data = _valid_submit_form()
	data["email"] = ""
	resp = client.post("/code/submit", data=data)
	assert resp.status_code == 200
	assert b"Email" in resp.data


def test_submit_rejects_invalid_email(client):
	data = _valid_submit_form()
	data["email"] = "not-an-email"
	resp = client.post("/code/submit", data=data)
	assert resp.status_code == 200
	assert b"valid email" in resp.data


def test_submit_rejects_wrong_challenge(client):
	data = _valid_submit_form()
	data["challenge"] = "wronganswer"
	resp = client.post("/code/submit", data=data)
	assert resp.status_code == 200
	assert b"challenge" in resp.data.lower()


def test_submit_rejects_empty_challenge(client):
	data = _valid_submit_form()
	data["challenge"] = ""
	resp = client.post("/code/submit", data=data)
	assert resp.status_code == 200
	assert b"challenge" in resp.data.lower()


def test_submit_challenge_is_case_insensitive(client, monkeypatch):
	"""The bot challenge should accept any case and spacing."""
	data = _valid_submit_form()
	data["challenge"] = "Physics Is Phun"

	# Monkeypatch Database at the source module so the local import picks it up
	inserted = {}

	class FakeSession:
		def add(self, obj):
			inserted["title"] = obj.title
		def flush(self):
			pass
		def execute(self, *a, **kw):
			from unittest.mock import MagicMock
			return MagicMock(scalar=lambda: 1, first=lambda: MagicMock(pk=1))
		def commit(self):
			pass
		def close(self):
			pass

	class FakeDB:
		def Session(self):
			return FakeSession()

	monkeypatch.setattr(
		"ascl_net_app.model.database.Database",
		lambda: FakeDB(),
	)

	resp = client.post("/code/submit", data=data)
	assert resp.status_code == 200
	# If we reached the DB insert, the challenge passed validation
	assert inserted.get("title") == "Test Submission Code"


# ===========================================================================
# /code/submit — successful submission (mocked DB)
# ===========================================================================

def test_submit_success_shows_confirmation(client, monkeypatch):
	"""A valid submission should display a success message (DB mocked)."""
	from unittest.mock import MagicMock

	class FakeSession:
		def add(self, obj):
			obj.pk = 999
		def flush(self):
			pass
		def execute(self, *a, **kw):
			m = MagicMock()
			m.scalar.return_value = 1
			m.first.return_value = MagicMock(pk=1)
			return m
		def commit(self):
			pass
		def close(self):
			pass

	class FakeDB:
		def Session(self):
			return FakeSession()

	monkeypatch.setattr(
		"ascl_net_app.model.database.Database",
		lambda: FakeDB(),
	)

	data = _valid_submit_form()
	resp = client.post("/code/submit", data=data)
	assert resp.status_code == 200
	html = resp.get_data(as_text=True)
	assert "Code added" in html or "View it here" in html


# ===========================================================================
# /<ascl_id>/suggest-edit — GET
# ===========================================================================

def test_suggest_edit_form_renders(client):
	ascl_id = _known_published_ascl_id()
	resp = client.get(f"/{ascl_id}/suggest-edit")
	assert resp.status_code == 200
	html = resp.get_data(as_text=True).lower()
	assert "suggest" in html or "edit" in html


def test_suggest_edit_404_for_bad_id(client):
	resp = client.get("/not-valid/suggest-edit")
	assert resp.status_code == 404


def test_suggest_edit_404_for_nonexistent_code(client):
	resp = client.get("/9999.999/suggest-edit")
	assert resp.status_code == 404


# ===========================================================================
# /<ascl_id>/suggest-edit — validation
# ===========================================================================

def test_suggest_edit_rejects_missing_name(client):
	ascl_id = _known_published_ascl_id()
	resp = client.post(f"/{ascl_id}/suggest-edit", data={
		"title": "Changed Title",
		"credit": "Smith, Alice",
		"name": "",
		"email": "test@example.com",
		"challenge": CHALLENGE_ANSWER,
	})
	assert resp.status_code == 200
	assert b"name is required" in resp.data


def test_suggest_edit_rejects_missing_email(client):
	ascl_id = _known_published_ascl_id()
	resp = client.post(f"/{ascl_id}/suggest-edit", data={
		"title": "Changed Title",
		"credit": "Smith, Alice",
		"name": "Test User",
		"email": "",
		"challenge": CHALLENGE_ANSWER,
	})
	assert resp.status_code == 200
	assert b"Email" in resp.data


def test_suggest_edit_rejects_wrong_challenge(client):
	ascl_id = _known_published_ascl_id()
	resp = client.post(f"/{ascl_id}/suggest-edit", data={
		"title": "Changed Title",
		"credit": "Smith, Alice",
		"name": "Test User",
		"email": "test@example.com",
		"challenge": "wrong",
	})
	assert resp.status_code == 200
	assert b"challenge" in resp.data.lower()


def test_suggest_edit_rejects_no_changes(client):
	"""Submitting the same values as the current code should be rejected.

	The controller ignores empty scalar fields (treats them as 'no change')
	and only detects changes when the submitted value differs from the
	current database value. We also need to submit the current link values
	to avoid false link-change detection.
	"""
	ascl_id = _known_published_ascl_id()

	# Fetch current link data so we can echo it back
	try:
		with db.Session() as session:
			code_row = session.execute(
				text("SELECT pk FROM codes WHERE ascl_id = :aid AND published = 1"),
				{"aid": ascl_id}
			).first()
			link_types = session.execute(
				text("SELECT pk FROM link_type ORDER BY pk")
			).all()
			current_links = {}
			if code_row:
				rows = session.execute(
					text("SELECT url, link_type_pk FROM link WHERE code_pk = :pk ORDER BY link_type_pk, display_order"),
					{"pk": code_row[0]}
				).all()
				for url, lt_pk in rows:
					current_links.setdefault(lt_pk, []).append(url)
	except SQLAlchemyError:
		pytest.skip("Database not accessible for suggest-edit test")

	# Build form data that echoes back existing links (no changes)
	form_data = {
		"title": "",
		"credit": "",
		"abstract": "",
		"citation_method": "",
		"name": "Test User",
		"email": "test@example.com",
		"challenge": CHALLENGE_ANSWER,
	}
	for lt_pk, in link_types:
		urls = current_links.get(lt_pk, [])
		form_data[f"links_{lt_pk}"] = urls

	resp = client.post(f"/{ascl_id}/suggest-edit", data=form_data)
	assert resp.status_code == 200
	assert b"No changes detected" in resp.data
