"""Tests for code submission: user submissions are published immediately,
admin-created codes default to unpublished."""

import pytest
from sqlalchemy import text

from ascl_core.database.connections import Trillian2DBConnection as db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def admin_client(client):
    """Flask test client with admin session pre-set."""
    with client.session_transaction() as sess:
        sess["user_id"] = 1
    return client


def _cleanup_code(pk):
    """Remove a test code and its related rows."""
    try:
        with db.Session() as session:
            session.execute(text("DELETE FROM link WHERE code_pk = :pk"), {"pk": pk})
            session.execute(text("DELETE FROM code_to_author WHERE code_pk = :pk"), {"pk": pk})
            session.execute(text("DELETE FROM codes WHERE pk = :pk"), {"pk": pk})
            session.commit()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# User submission via /code/submit
# ---------------------------------------------------------------------------

class TestUserSubmission:

    def test_user_submitted_code_is_published(self, client):
        """A code submitted via /code/submit must have published=1."""
        resp = client.post("/code/submit", data={
            "title": "TestUserSubmit_AutoTest",
            "credit": "Test Author",
            "abstract": "A test abstract for automated testing.",
            "site_urls": "https://example.com/test-repo",
            "described_in_urls": "",
            "used_in_urls": "",
            "citation_method": "",
            "name": "Test Submitter",
            "email": "test@example.com",
            "notes": "",
            "challenge": "physics is phun",
        }, follow_redirects=True)

        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert "Code added" in html or "Code updated" in html

        # Verify database state
        pk = None
        try:
            with db.Session() as session:
                row = session.execute(text(
                    "SELECT pk, published, ascl_id FROM codes "
                    "WHERE title = 'TestUserSubmit_AutoTest' "
                    "ORDER BY pk DESC LIMIT 1"
                )).first()
                assert row is not None, "Submitted code not found in database"
                pk = row.pk
                assert row.published == 1, (
                    f"User-submitted code should be published (1), got {row.published}"
                )
                assert row.ascl_id == "0000.000", (
                    "User-submitted code should have placeholder ASCL ID"
                )
        finally:
            if pk:
                _cleanup_code(pk)

    def test_user_submitted_code_view_link_works(self, client):
        """The /code/v/<pk> link shown after submission must return 200."""
        resp = client.post("/code/submit", data={
            "title": "TestViewLink_AutoTest",
            "credit": "Test Author",
            "abstract": "A test abstract for view link testing.",
            "site_urls": "https://example.com/test-repo",
            "described_in_urls": "",
            "used_in_urls": "",
            "citation_method": "",
            "name": "Test Submitter",
            "email": "test@example.com",
            "notes": "",
            "challenge": "physics is phun",
        }, follow_redirects=True)

        assert resp.status_code == 200

        pk = None
        try:
            with db.Session() as session:
                row = session.execute(text(
                    "SELECT pk FROM codes "
                    "WHERE title = 'TestViewLink_AutoTest' "
                    "ORDER BY pk DESC LIMIT 1"
                )).first()
                assert row is not None, "Submitted code not found in database"
                pk = row.pk

            # The /code/v/<pk> route should return the detail page
            detail_resp = client.get(f"/code/v/{pk}")
            assert detail_resp.status_code == 200, (
                f"/code/v/{pk} returned {detail_resp.status_code}, expected 200"
            )
            detail_html = detail_resp.get_data(as_text=True)
            assert "TestViewLink_AutoTest" in detail_html

            # Submitted codes must show [submitted], not [ascl:0000.000]
            assert "[submitted]" in detail_html, (
                "Detail page for 0000.000 code should display [submitted]"
            )
            assert "ascl:0000.000" not in detail_html, (
                "Detail page should not display ascl:0000.000"
            )
            # Shield badge should be hidden for submitted codes
            assert "img.shields.io/badge/ascl-0000.000" not in detail_html, (
                "Shield badge should not appear for submitted codes"
            )
        finally:
            if pk:
                _cleanup_code(pk)


# ---------------------------------------------------------------------------
# Admin code creation via /admin/insert_code
# ---------------------------------------------------------------------------

class TestAdminInsertCode:

    def test_admin_created_code_defaults_unpublished(self, admin_client):
        """A code created via /admin/insert_code without checking 'published'
        must have published=0."""
        resp = admin_client.post("/admin/insert_code", data={
            "title": "TestAdminInsert_AutoTest",
            "credit": "Admin Author",
            "ascl_id": "0000.000",
            "abstract": "Admin test abstract.",
            "citation_method": "",
            "email": "",
            "notes": "",
            # published is NOT included — should default to 0
            "aliases": "",
            "keywords": "",
            "typed_links": "[]",
            "described_in_urls": "",
            "used_in_urls": "",
            "see_also": "",
        }, follow_redirects=True)

        assert resp.status_code == 200

        pk = None
        try:
            with db.Session() as session:
                row = session.execute(text(
                    "SELECT pk, published FROM codes "
                    "WHERE title = 'TestAdminInsert_AutoTest' "
                    "ORDER BY pk DESC LIMIT 1"
                )).first()
                assert row is not None, "Admin-created code not found in database"
                pk = row.pk
                assert row.published == 0, (
                    f"Admin-created code should default to unpublished (0), got {row.published}"
                )
        finally:
            if pk:
                _cleanup_code(pk)

    def test_admin_can_explicitly_publish(self, admin_client):
        """A code created via /admin/insert_code with published=1 should be published."""
        resp = admin_client.post("/admin/insert_code", data={
            "title": "TestAdminPublish_AutoTest",
            "credit": "Admin Author",
            "ascl_id": "0000.000",
            "abstract": "Admin publish test abstract.",
            "citation_method": "",
            "email": "",
            "notes": "",
            "published": "1",
            "aliases": "",
            "keywords": "",
            "typed_links": "[]",
            "described_in_urls": "",
            "used_in_urls": "",
            "see_also": "",
        }, follow_redirects=True)

        assert resp.status_code == 200

        pk = None
        try:
            with db.Session() as session:
                row = session.execute(text(
                    "SELECT pk, published FROM codes "
                    "WHERE title = 'TestAdminPublish_AutoTest' "
                    "ORDER BY pk DESC LIMIT 1"
                )).first()
                assert row is not None, "Admin-created code not found in database"
                pk = row.pk
                assert row.published == 1, (
                    f"Admin-created code with published=1 should be published, got {row.published}"
                )
        finally:
            if pk:
                _cleanup_code(pk)
