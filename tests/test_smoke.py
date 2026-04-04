"""
Smoke tests for the deployed ASCL Flask application.

These tests hit the live site over HTTP — no Flask internals, no database
imports. They verify that every public endpoint returns the expected status
code and basic content markers.

Usage:
    pytest tests/test_smoke.py                                  # default: dev.ascl.net
    pytest tests/test_smoke.py --base-url https://ascl.net      # production
    pytest tests/test_smoke.py --base-url http://localhost:5000  # local dev server
    pytest tests/test_smoke.py -v                                # verbose output
    pytest tests/test_smoke.py -x                                # stop on first failure
"""

import re
import xml.etree.ElementTree as ET

import pytest
import requests


# ───────────────────────────────────────────────────────────────────────────
# Helpers
# ───────────────────────────────────────────────────────────────────────────

TIMEOUT = 20  # seconds; generous for shared hosting


def get(session, base_url, path, **kwargs):
    """GET helper with default timeout."""
    kwargs.setdefault("timeout", TIMEOUT)
    return session.get(f"{base_url}{path}", **kwargs)


# ───────────────────────────────────────────────────────────────────────────
# Public pages
# ───────────────────────────────────────────────────────────────────────────

class TestPublicPages:

    def test_index(self, session, base_url):
        r = get(session, base_url, "/")
        assert r.status_code == 200
        assert "ascl" in r.text.lower()

    def test_about(self, session, base_url):
        r = get(session, base_url, "/about")
        assert r.status_code == 200
        # Should contain actual WordPress content, not an empty page
        assert len(r.text) > 500

    def test_submissions(self, session, base_url):
        r = get(session, base_url, "/submissions")
        assert r.status_code == 200
        assert len(r.text) > 500

    def test_resources(self, session, base_url):
        r = get(session, base_url, "/resources")
        assert r.status_code == 200

    def test_explain(self, session, base_url):
        r = get(session, base_url, "/explain")
        assert r.status_code == 200

    def test_dashboard(self, session, base_url):
        r = get(session, base_url, "/dashboard")
        assert r.status_code == 200
        assert "dashboard" in r.text.lower() or "statistic" in r.text.lower()


# ───────────────────────────────────────────────────────────────────────────
# Code browsing
# ───────────────────────────────────────────────────────────────────────────

class TestCodeBrowsing:

    def test_code_all(self, session, base_url):
        r = get(session, base_url, "/code/all")
        assert r.status_code == 200

    def test_code_all_pagination(self, session, base_url):
        r = get(session, base_url, "/code/all?page=2")
        assert r.status_code == 200

    def test_code_all_page_beyond_range(self, session, base_url):
        """Very high page number should not 500."""
        r = get(session, base_url, "/code/all?page=99999")
        assert r.status_code in (200, 404)

    def test_code_all_by_id(self, session, base_url):
        r = get(session, base_url, "/code/all_by_id")
        assert r.status_code == 200

    def test_code_keywords(self, session, base_url):
        r = get(session, base_url, "/code/keywords")
        assert r.status_code == 200

    def test_code_keyword_filter(self, session, base_url):
        """Pick a keyword likely to exist."""
        r = get(session, base_url, "/code/keywords/galaxies")
        assert r.status_code == 200

    def test_code_alias_list(self, session, base_url):
        r = get(session, base_url, "/code/alias_list")
        assert r.status_code == 200

    def test_code_random(self, session, base_url):
        r = get(session, base_url, "/code/random", allow_redirects=False)
        assert r.status_code in (301, 302)
        location = r.headers.get("Location", "")
        # Should redirect to something that looks like an ASCL ID
        assert re.search(r"\d{4}\.\d{3}", location), \
            f"Random redirect location doesn't look like an ASCL ID: {location}"

    def test_code_submit_form(self, session, base_url):
        r = get(session, base_url, "/code/submit")
        assert r.status_code == 200


# ───────────────────────────────────────────────────────────────────────────
# Code detail
# ───────────────────────────────────────────────────────────────────────────

class TestCodeDetail:

    def test_code_detail_page(self, session, base_url, known_ascl_id):
        r = get(session, base_url, f"/{known_ascl_id}")
        assert r.status_code == 200
        # Page should contain the ASCL ID somewhere
        assert known_ascl_id in r.text

    def test_code_detail_nonexistent(self, session, base_url):
        r = get(session, base_url, "/9999.999")
        assert r.status_code == 404

    def test_code_detail_malformed_id(self, session, base_url):
        r = get(session, base_url, "/not-a-valid-id")
        assert r.status_code == 404

    def test_suggest_edit_form(self, session, base_url, known_ascl_id):
        r = get(session, base_url, f"/{known_ascl_id}/suggest-edit")
        assert r.status_code == 200


# ───────────────────────────────────────────────────────────────────────────
# Search
# ───────────────────────────────────────────────────────────────────────────

class TestSearch:

    def test_search_empty(self, session, base_url):
        r = get(session, base_url, "/search")
        assert r.status_code == 200

    def test_search_with_query(self, session, base_url):
        r = get(session, base_url, "/search?q=galaxy")
        assert r.status_code == 200

    def test_search_suggest(self, session, base_url):
        r = get(session, base_url, "/search/suggest?q=astr&limit=5")
        assert r.status_code == 200
        data = r.json()
        assert "suggestions" in data

    def test_search_author_suggest(self, session, base_url):
        r = get(session, base_url, "/search/author_suggest?q=Smith")
        assert r.status_code == 200
        data = r.json()
        assert "suggestions" in data

    def test_credit_search(self, session, base_url):
        r = get(session, base_url, "/code/cs/Smith")
        assert r.status_code == 200

    def test_search_adversarial_input(self, session, base_url):
        """Ensure the app doesn't 500 on adversarial input."""
        r = get(session, base_url, "/search?q=%27%20OR%201%3D1--")
        assert r.status_code in (200, 404)  # must not be 500


# ───────────────────────────────────────────────────────────────────────────
# News
# ───────────────────────────────────────────────────────────────────────────

class TestNews:

    def test_news_list(self, session, base_url):
        r = get(session, base_url, "/news")
        assert r.status_code == 200

    def test_news_rss_feed(self, session, base_url):
        r = get(session, base_url, "/news/feed")
        assert r.status_code == 200
        content_type = r.headers.get("Content-Type", "")
        assert "xml" in content_type or "rss" in content_type
        # Validate it parses as XML
        ET.fromstring(r.content)

    def test_wordpress_redirect(self, session, base_url):
        r = get(session, base_url, "/wordpress", allow_redirects=False)
        assert r.status_code == 301
        assert "/news" in r.headers.get("Location", "")


# ───────────────────────────────────────────────────────────────────────────
# Data exports
# ───────────────────────────────────────────────────────────────────────────

class TestDataExports:

    def test_json_export(self, session, base_url):
        r = get(session, base_url, "/code/json", timeout=60)
        assert r.status_code == 200
        data = r.json()
        # May be a dict keyed by string ID or a list
        if isinstance(data, dict):
            entries = list(data.values())
        else:
            entries = data
        assert len(entries) > 100, "JSON export should contain many codes"
        first = entries[0]
        assert "ascl_id" in first
        assert "title" in first

    def test_xml_export(self, session, base_url):
        r = get(session, base_url, "/code/xml", timeout=60)
        assert r.status_code == 200
        ET.fromstring(r.content)  # valid XML

    def test_dci_export(self, session, base_url):
        r = get(session, base_url, "/code/dci", timeout=60)
        assert r.status_code == 200
        ET.fromstring(r.content)

    def test_dci_export_with_date(self, session, base_url):
        r = get(session, base_url, "/code/dci/2024-01-01", timeout=60)
        assert r.status_code == 200

    def test_ole_export_guest_restricted(self, session, base_url):
        """OLE export beyond 1 month returns 403 for unauthenticated guests."""
        r = get(session, base_url, "/code/ole/2024-01-01", timeout=60)
        assert r.status_code == 403

    def test_ole_export_recent_date(self, session, base_url):
        """OLE export within 1 month window should succeed for guests."""
        from datetime import datetime, timedelta
        recent = (datetime.now() - timedelta(days=15)).strftime("%Y-%m-%d")
        r = get(session, base_url, f"/code/ole/{recent}", timeout=60)
        assert r.status_code == 200

    def test_ads_export_guest_restricted(self, session, base_url):
        """ADS export beyond 1 month returns 403 for unauthenticated guests."""
        r = get(session, base_url, "/code/ads/2024-01-01", timeout=60)
        assert r.status_code == 403

    def test_ads_export_recent_date(self, session, base_url):
        """ADS export within 1 month window should succeed for guests."""
        from datetime import datetime, timedelta
        recent = (datetime.now() - timedelta(days=15)).strftime("%Y-%m-%d")
        r = get(session, base_url, f"/code/ads/{recent}", timeout=60)
        assert r.status_code == 200
        # ADS format contains % markers; may have a header line first
        text = r.text.strip()
        assert "%" in text or len(text) == 0


# ───────────────────────────────────────────────────────────────────────────
# CodeMeta & CITATION.cff
# ───────────────────────────────────────────────────────────────────────────

class TestCodeMetaCFF:

    def test_codemeta_json(self, session, base_url, known_ascl_id):
        r = get(session, base_url, f"/{known_ascl_id}/codemeta.json")
        assert r.status_code == 200
        data = r.json()
        assert data.get("@type") == "SoftwareSourceCode"
        assert "name" in data

    def test_citation_cff(self, session, base_url, known_ascl_id):
        r = get(session, base_url, f"/{known_ascl_id}/CITATION.cff")
        assert r.status_code == 200
        content_type = r.headers.get("Content-Type", "")
        assert "yaml" in content_type or "text" in content_type
        assert "cff-version:" in r.text

    def test_citation_cff_redirect(self, session, base_url, known_ascl_id):
        """Lowercase citation.cff should 301 to CITATION.cff."""
        r = get(session, base_url, f"/{known_ascl_id}/citation.cff",
                allow_redirects=False)
        assert r.status_code == 301
        assert "CITATION.cff" in r.headers.get("Location", "")


# ───────────────────────────────────────────────────────────────────────────
# Error handling
# ───────────────────────────────────────────────────────────────────────────

class TestErrorHandling:

    def test_404_custom_page(self, session, base_url):
        r = get(session, base_url, "/this-page-definitely-does-not-exist-xyz")
        assert r.status_code == 404
        # Should be a styled error page, not a raw server error
        assert "<html" in r.text.lower()

    def test_no_server_error_on_bad_page_param(self, session, base_url):
        r = get(session, base_url, "/code/all?page=abc")
        assert r.status_code in (200, 400, 404)  # anything but 500

    def test_no_server_error_on_empty_keyword(self, session, base_url):
        r = get(session, base_url, "/code/keywords/")
        assert r.status_code in (200, 301, 302, 404)


# ───────────────────────────────────────────────────────────────────────────
# Static assets
# ───────────────────────────────────────────────────────────────────────────

class TestStaticAssets:

    def test_favicon(self, session, base_url):
        r = get(session, base_url, "/favicon.ico")
        assert r.status_code == 200

    def test_robots_txt(self, session, base_url):
        r = get(session, base_url, "/robots.txt")
        assert r.status_code == 200
        assert "user-agent" in r.text.lower() or "User-agent" in r.text


# ───────────────────────────────────────────────────────────────────────────
# Security boundaries
# ───────────────────────────────────────────────────────────────────────────

class TestSecurityBoundaries:

    def test_admin_shows_login_not_content(self, session, base_url):
        """Unauthenticated /admin/ should show login form, not admin content."""
        r = get(session, base_url, "/admin/", allow_redirects=True)
        if r.status_code in (301, 302, 401, 403):
            return  # redirect or denial — fine
        assert r.status_code == 200
        text = r.text.lower()
        # Should contain a login form, not actual admin functionality
        assert "login" in text or "password" in text or "sign in" in text, \
            "Admin page returned 200 but doesn't appear to show a login form"
        # Should NOT expose admin content to unauthenticated users
        assert "unpublished" not in text or "login" in text

    def test_admin_unpublished_requires_auth(self, session, base_url):
        r = get(session, base_url, "/admin/unpublished", allow_redirects=False)
        assert r.status_code in (301, 302, 401, 403)

    def test_admin_api_requires_auth(self, session, base_url):
        r = get(session, base_url, "/admin/api/next_ascl_id",
                allow_redirects=False)
        assert r.status_code in (301, 302, 401, 403)

    def test_no_stack_trace_in_404(self, session, base_url):
        """Ensure debug mode is off — no tracebacks leak to users."""
        r = get(session, base_url, "/9999.999")
        assert "Traceback" not in r.text
        assert "debugger" not in r.text.lower()


# ───────────────────────────────────────────────────────────────────────────
# Response headers
# ───────────────────────────────────────────────────────────────────────────

class TestResponseHeaders:

    def test_json_export_content_type(self, session, base_url):
        r = get(session, base_url, "/code/json", timeout=60)
        assert "json" in r.headers.get("Content-Type", "")

    def test_xml_export_content_type(self, session, base_url):
        r = get(session, base_url, "/code/xml", timeout=60)
        assert "xml" in r.headers.get("Content-Type", "")

    def test_codemeta_content_type(self, session, base_url, known_ascl_id):
        r = get(session, base_url, f"/{known_ascl_id}/codemeta.json")
        assert "json" in r.headers.get("Content-Type", "")

    def test_rss_content_type(self, session, base_url):
        r = get(session, base_url, "/news/feed")
        ct = r.headers.get("Content-Type", "")
        assert "xml" in ct or "rss" in ct
