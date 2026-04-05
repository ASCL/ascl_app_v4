"""
Fixtures for live-site smoke tests.

Usage:
    pytest tests/ --base-url https://dev.ascl.net
    pytest tests/ --base-url https://ascl.net
    pytest tests/ --base-url http://localhost:5000

Admin tests:
    pytest tests/ --admin-user alice --admin-pass secret
"""

import pytest
import requests


def pytest_addoption(parser):
    parser.addoption(
        "--base-url",
        required=True,
        help="Base URL of the deployed ASCL site to test against (e.g. https://dev.ascl.net)",
    )
    parser.addoption(
        "--admin-user",
        default=None,
        help="Admin username for authenticated tests",
    )
    parser.addoption(
        "--admin-pass",
        default=None,
        help="Admin password for authenticated tests",
    )


@pytest.fixture(scope="session")
def base_url(request):
    url = request.config.getoption("--base-url").rstrip("/")
    return url


@pytest.fixture(scope="session")
def session(base_url):
    """Persistent requests.Session for the whole test run."""
    s = requests.Session()
    s.headers["User-Agent"] = "ascl-smoke-test/1.0"
    # Verify the site is reachable before running the suite
    try:
        r = s.get(base_url, timeout=15)
        r.raise_for_status()
    except requests.RequestException as exc:
        pytest.exit(f"Site unreachable at {base_url}: {exc}")
    return s


@pytest.fixture(scope="session")
def known_ascl_id(session, base_url):
    """Fetch one known published ASCL ID from the JSON export."""
    r = session.get(f"{base_url}/code/json", timeout=30)
    if r.status_code != 200:
        pytest.skip("Could not fetch /code/json to discover a known ASCL ID")
    data = r.json()
    if not data:
        pytest.skip("JSON export returned no codes")
    # Handle both list-of-dicts and dict-keyed-by-id formats
    if isinstance(data, dict):
        entries = list(data.values())
    else:
        entries = data
    for code in entries[:10]:
        aid = code.get("ascl_id") or code.get("ascl_ID") or code.get("id")
        if aid:
            return aid
    pytest.skip("No ASCL ID found in JSON export")


@pytest.fixture(scope="session")
def admin_session(request, base_url):
    """Authenticated admin session. Skips if no credentials provided."""
    username = request.config.getoption("--admin-user")
    password = request.config.getoption("--admin-pass")
    if not username or not password:
        pytest.skip("Admin tests require --admin-user and --admin-pass")

    s = requests.Session()
    s.headers["User-Agent"] = "ascl-smoke-test/1.0"

    # Log in via the admin login form
    r = s.post(
        f"{base_url}/admin/login",
        data={"username": username, "password": password},
        timeout=15,
        allow_redirects=True,
    )
    # After successful login, we should be redirected to admin dashboard
    # or admin home. Verify we're actually logged in by checking a
    # protected page.
    check = s.get(f"{base_url}/admin/unpublished", timeout=15, allow_redirects=False)
    if check.status_code in (301, 302, 401, 403):
        pytest.fail(
            f"Admin login failed for user '{username}' — "
            f"protected page returned {check.status_code}"
        )
    return s


@pytest.fixture(scope="session")
def known_code_pk(admin_session, base_url):
    """Fetch one code PK from the admin unpublished or full table page."""
    # Use the JSON export to get a code, then look up its PK via admin view
    r = admin_session.get(f"{base_url}/code/json", timeout=30)
    if r.status_code != 200:
        pytest.skip("Could not fetch /code/json")
    data = r.json()
    if isinstance(data, dict):
        entries = list(data.values())
    else:
        entries = data
    if not entries:
        pytest.skip("No codes in JSON export")
    # The JSON export includes pk in v4
    for code in entries[:10]:
        pk = code.get("pk") or code.get("id")
        if pk and isinstance(pk, int):
            return pk
    # Fallback: try to extract from admin full table
    r = admin_session.get(f"{base_url}/admin/utility/simple_table", timeout=30)
    if r.status_code == 200:
        import re
        m = re.search(r'/admin/view/(\d+)', r.text)
        if m:
            return int(m.group(1))
    pytest.skip("Could not determine a code PK for admin tests")
