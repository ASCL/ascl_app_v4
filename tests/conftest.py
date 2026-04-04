"""
Fixtures for live-site smoke tests.

Usage:
    pytest tests/ --base-url https://dev.ascl.net
    pytest tests/ --base-url http://localhost:5000
"""

import pytest
import requests


def pytest_addoption(parser):
    parser.addoption(
        "--base-url",
        default="https://dev.ascl.net",
        help="Base URL of the deployed ASCL site to test against",
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
