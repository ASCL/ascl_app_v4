"""Tests that validation errors on insert/update preserve submitted form data.

When a user fills out the admin code form and hits a validation error, the
form should re-render with all previously entered values intact so nothing
is lost.
"""

import json
import pytest
from sqlalchemy import text


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def admin_client(client):
    """Flask test client with admin session pre-set."""
    with client.session_transaction() as sess:
        sess["user_id"] = 1
    return client


@pytest.fixture()
def existing_code_pk(app):
    """Return the pk of a real published code to test the update route."""
    from ascl_core.database.connections import Trillian2DBConnection as db

    try:
        with db.Session() as session:
            row = session.execute(
                text("SELECT pk FROM codes WHERE published = 1 LIMIT 1")
            ).first()
    except Exception:
        pytest.skip("Database not accessible")

    if not row:
        pytest.skip("No published codes in database")
    return row[0]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _insert_form_data(**overrides):
    """Return a complete insert form payload; override individual fields."""
    data = {
        "title": "Preservation Test Code",
        "credit": "Doe, Jane; Roe, Richard",
        "ascl_id": "2499.050",
        "abstract": "An abstract that should survive validation errors.",
        "citation_method": "Preferred citation string",
        "email": "test@example.org",
        "notes": "Some internal notes.",
        "published": "0",
        "doi": "10.0000/test.doi",
        "aliases": "AliasOne\nAliasTwo",
        "keywords": "galaxies\ncosmology",
        "typed_links": json.dumps([
            {"url": "https://github.com/example/repo", "type": "code-site",
             "display_order": 0},
        ]),
        "described_in_urls": "https://arxiv.org/abs/0000.0000",
        "used_in_urls": "https://arxiv.org/abs/1111.1111",
        "see_also": "1234.567",
    }
    data.update(overrides)
    return data


def _assert_form_preserved(html, data):
    """Check that key submitted values appear in the re-rendered HTML."""
    # Fields that should survive a validation round-trip.
    # Each tuple is (form field key, expected substring in HTML).
    checks = [
        ("abstract", data["abstract"]),
        ("email", data["email"]),
        ("doi", data["doi"]),
    ]

    # Title and credit may be blank (they are the required fields we
    # intentionally break), so only check them when they are non-empty.
    if data.get("title"):
        checks.append(("title", data["title"]))
    if data.get("credit"):
        checks.append(("credit", data["credit"]))

    for field, expected in checks:
        assert expected in html, (
            f"Field '{field}' value was lost after validation error. "
            f"Expected '{expected}' in the re-rendered form."
        )


# ===========================================================================
# INSERT — validation preserves form data
# ===========================================================================

class TestInsertValidationPreservesData:
    """POST /admin/insert_code with a validation error should re-render the
    form with all previously entered values intact."""

    def test_missing_title_preserves_other_fields(self, admin_client):
        data = _insert_form_data(title="")
        resp = admin_client.post("/admin/insert_code", data=data,
                                 follow_redirects=True)
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert "Title is required" in html
        _assert_form_preserved(html, data)

    def test_missing_credit_preserves_other_fields(self, admin_client):
        data = _insert_form_data(credit="")
        resp = admin_client.post("/admin/insert_code", data=data,
                                 follow_redirects=True)
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert "Credit is required" in html
        _assert_form_preserved(html, data)

    def test_bad_ascl_id_preserves_other_fields(self, admin_client):
        data = _insert_form_data(ascl_id="short")
        resp = admin_client.post("/admin/insert_code", data=data,
                                 follow_redirects=True)
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert "ASCL ID must be 8 characters" in html
        _assert_form_preserved(html, data)

    def test_empty_ascl_id_preserves_other_fields(self, admin_client):
        data = _insert_form_data(ascl_id="")
        resp = admin_client.post("/admin/insert_code", data=data,
                                 follow_redirects=True)
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert "ASCL ID" in html
        _assert_form_preserved(html, data)

    def test_collision_preserves_other_fields(self, admin_client):
        """An ASCL ID that already exists should re-render with all data."""
        from ascl_core.database.connections import Trillian2DBConnection as db

        try:
            with db.Session() as session:
                row = session.execute(
                    text("SELECT ascl_id FROM codes WHERE published = 1 LIMIT 1")
                ).first()
        except Exception:
            pytest.skip("Database not accessible")

        if not row:
            pytest.skip("No codes in database")

        data = _insert_form_data(ascl_id=row[0])
        resp = admin_client.post("/admin/insert_code", data=data,
                                 follow_redirects=True)
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        _assert_form_preserved(html, data)


# ===========================================================================
# UPDATE — validation preserves form data
# ===========================================================================

class TestUpdateValidationPreservesData:
    """POST /admin/update_code/<pk> with a validation error should re-render
    the form with the user's submitted values, not the stale DB values."""

    def test_missing_title_preserves_edits(self, admin_client, existing_code_pk):
        data = _insert_form_data(title="", credit="Edited Author")
        resp = admin_client.post(
            f"/admin/update_code/{existing_code_pk}",
            data=data, follow_redirects=True,
        )
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert "Title is required" in html
        # The edited credit should still be in the form, not the DB value
        assert "Edited Author" in html
        _assert_form_preserved(html, data)

    def test_missing_credit_preserves_edits(self, admin_client, existing_code_pk):
        data = _insert_form_data(
            credit="",
            title="Edited Title That Should Survive",
        )
        resp = admin_client.post(
            f"/admin/update_code/{existing_code_pk}",
            data=data, follow_redirects=True,
        )
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert "Credit is required" in html
        assert "Edited Title That Should Survive" in html
        _assert_form_preserved(html, data)

    def test_bad_ascl_id_preserves_edits(self, admin_client, existing_code_pk):
        data = _insert_form_data(ascl_id="bad")
        resp = admin_client.post(
            f"/admin/update_code/{existing_code_pk}",
            data=data, follow_redirects=True,
        )
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert "ASCL ID must be 8 characters" in html
        _assert_form_preserved(html, data)
