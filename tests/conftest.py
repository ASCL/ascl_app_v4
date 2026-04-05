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
    assert r.status_code == 200, f"/code/json returned {r.status_code}"
    data = r.json()
    assert data, "/code/json returned empty data"

    if isinstance(data, dict):
        entries = list(data.values())
    else:
        entries = data
    aid = entries[0].get("ascl_id") or entries[0].get("ascl_ID") or entries[0].get("id")
    assert aid, f"First entry in /code/json has no ascl_id: {list(entries[0].keys())}"
    return aid


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
    """Fetch one code PK from the JSON export (keys are PKs)."""
    r = admin_session.get(f"{base_url}/code/json", timeout=30)
    assert r.status_code == 200, f"/code/json returned {r.status_code}"
    data = r.json()
    assert data, "/code/json returned empty data"

    if isinstance(data, dict):
        # JSON export is keyed by code PK (as string)
        key = next(iter(data))
        return int(key)
    else:
        # List format — entries must have pk or id
        pk = data[0].get("pk") or data[0].get("id")
        assert pk, f"First entry in /code/json has no pk or id: {list(data[0].keys())}"
        return int(pk)
