#!/usr/bin/env python3
"""
ascl_link_checker — Async link checker for the ASCL v4 database.

Checks URLs in the `link` table for availability using concurrent HTTP requests
and writes detailed results to the `link_check` table.

Captures page title, final URL after redirects, domain changes, and
pattern-matched notes (e.g. "GitHub: repository not found") to help
human curators review broken or changed links.

Usage:
    python3 ascl_link_checker.py                          # check code-site links
    python3 ascl_link_checker.py --link-type all           # check all link types
    python3 ascl_link_checker.py --dry-run -v              # check, skip DB writes
    python3 ascl_link_checker.py --concurrency 10 -p       # limit concurrency

Requires: Python 3.11+, httpx, pymysql.

History:
  2026-04-02 Initial creation (v4-native, based on link_checker_async.py).
"""

import argparse
import asyncio
import collections
import configparser
import datetime
import logging
import os
import re
import sys
import time
from urllib.parse import urlparse

import httpx
import pymysql

# ---------------------------------------------------------------------------
# Tunable constants (overridable via CLI args)
# ---------------------------------------------------------------------------
MAX_CONCURRENT = 50
MAX_PER_DOMAIN = 2
CONNECT_TIMEOUT = 10   # seconds
READ_TIMEOUT = 20      # seconds
# Use a browser-like User-Agent — many servers (universities, personal pages)
# return 403 Forbidden for non-browser User-Agents.
USER_AGENT = ("Mozilla/5.0 (compatible; ASCL-LinkChecker/3.0; +https://ascl.net) "
              "AppleWebKit/537.36 (KHTML, like Gecko)")
MAX_RETRIES = 3        # retries on 429/5xx
DOMAIN_DELAY = 0.5     # seconds between requests to same domain

WORKING_CODES = {200, 202}
# Codes that indicate the server is there but blocking/redirecting us —
# not truly broken, mark as working with a note.
PROBABLY_WORKING_CODES = {401, 403, 405, 406, 429}

# Max bytes to read for title extraction (avoid downloading huge pages)
TITLE_READ_LIMIT = 8192

log = logging.getLogger("ascl_link_checker")

# ---------------------------------------------------------------------------
# Database helpers (same pattern as existing link_checker_async.py)
# ---------------------------------------------------------------------------

def read_db_config() -> dict:
    """Read MySQL credentials from ~/.my.cnf.

    Prefers [client_ascl_root], falls back to [client_ascl], then [client].
    """
    cnf_path = os.path.expanduser("~/.my.cnf")
    if not os.path.exists(cnf_path):
        sys.exit(f"Error: {cnf_path} not found. Create it with a [client_ascl_root] section.")

    config = configparser.ConfigParser()
    config.read(cnf_path)

    for section in ("client_ascl", "client_ascl_root", "client"):
        if config.has_section(section):
            break
    else:
        sys.exit(f"Error: No usable client section in {cnf_path}")

    cfg = {
        "host":     config.get(section, "host", fallback="127.0.0.1"),
        "user":     config.get(section, "user"),
        "password": config.get(section, "password"),
        "port":     config.getint(section, "port", fallback=3307),
    }

    socket = config.get(section, "socket", fallback=None)
    if socket:
        cfg["unix_socket"] = socket

    return cfg


def get_connection(db_cfg: dict, database: str) -> pymysql.Connection:
    """Open a pymysql connection."""
    kwargs = {
        "user":     db_cfg["user"],
        "password": db_cfg["password"],
        "database": database,
        "charset":  "utf8mb4",
        "cursorclass": pymysql.cursors.DictCursor,
    }

    if "unix_socket" in db_cfg:
        kwargs["unix_socket"] = db_cfg["unix_socket"]
    else:
        kwargs["host"] = db_cfg["host"]
        kwargs["port"] = db_cfg["port"]

    return pymysql.connect(**kwargs)


# ---------------------------------------------------------------------------
# URL extraction from v4 link table
# ---------------------------------------------------------------------------

def fetch_links(connection: pymysql.Connection, link_type: str,
                retry_failed: bool = False) -> list[dict]:
    """Read links to check from the link table, deduplicated by URL.

    Returns list of dicts with keys: link_pks (list), url.
    Multiple link rows sharing the same URL are grouped so the URL
    is only checked once; the result is applied to all link_pks.
    Filters to published codes with assigned ASCL IDs.
    If retry_failed=True, only returns links that previously failed.
    """
    sql = """
        SELECT l.pk AS link_pk, l.url, l.code_pk
        FROM link l
        JOIN codes c ON c.pk = l.code_pk
    """

    if retry_failed:
        sql += " JOIN link_check lc ON lc.link_pk = l.pk AND lc.is_working = 0\n"

    sql += """
        WHERE c.published = 1
          AND c.ascl_id != '0000.000'
    """
    params = []

    if link_type != "all":
        sql += " AND l.link_type_pk = (SELECT pk FROM link_type WHERE short_name = %s)"
        params.append(link_type)

    with connection.cursor() as cursor:
        cursor.execute(sql, params)
        rows = cursor.fetchall()

    # Group by URL — check each unique URL once
    url_map: dict[str, list[int]] = {}
    for row in rows:
        url_map.setdefault(row["url"], []).append(row["link_pk"])

    links = [{"url": url, "link_pks": pks} for url, pks in url_map.items()]

    label = f"link_type={link_type}"
    if retry_failed:
        label += ", retry-failed only"
    dupes = len(rows) - len(links)
    log.info("Loaded %d links (%d unique URLs, %d duplicates) (%s)",
             len(rows), len(links), dupes, label)
    return links


# ---------------------------------------------------------------------------
# Page title extraction
# ---------------------------------------------------------------------------

_TITLE_RE = re.compile(r'<title[^>]*>(.*?)</title>', re.IGNORECASE | re.DOTALL)


def extract_title(html: str) -> str | None:
    """Extract the <title> from an HTML string (first 8KB)."""
    m = _TITLE_RE.search(html[:TITLE_READ_LIMIT])
    if m:
        # Collapse whitespace and trim
        title = re.sub(r'\s+', ' ', m.group(1)).strip()
        return title[:512] if title else None
    return None


# ---------------------------------------------------------------------------
# Pattern-matched notes
# ---------------------------------------------------------------------------

_NOTE_PATTERNS = [
    # Bot/human verification challenges (return 200 but not the real page)
    (re.compile(r'Just a moment\.\.\.', re.IGNORECASE),
     "Cloudflare challenge (probably working)"),
    (re.compile(r'not a bot', re.IGNORECASE),
     "Bot check (probably working)"),
    (re.compile(r'verify you are human', re.IGNORECASE),
     "Bot check (probably working)"),
    (re.compile(r'checking your browser', re.IGNORECASE),
     "Bot check (probably working)"),
    # GitHub
    (re.compile(r'Page not found · GitHub', re.IGNORECASE),
     "GitHub: repository not found"),
    (re.compile(r'This repository has been archived', re.IGNORECASE),
     "GitHub: repository archived"),
    (re.compile(r'Repository .+ was renamed', re.IGNORECASE),
     "GitHub: repository renamed"),
    # GitLab
    (re.compile(r'The repository for this project is empty', re.IGNORECASE),
     "GitLab: empty repository"),
    (re.compile(r'This project was archived', re.IGNORECASE),
     "GitLab: project archived"),
    # Bitbucket
    (re.compile(r'Repository not found', re.IGNORECASE),
     "Bitbucket: repository not found"),
    # Generic parked domain indicators
    (re.compile(r'(domain|this site) is for sale', re.IGNORECASE),
     "Possible parked domain"),
    (re.compile(r'buy this domain', re.IGNORECASE),
     "Possible parked domain"),
    (re.compile(r'parked (free|by|domain)', re.IGNORECASE),
     "Possible parked domain"),
]


def detect_note(html: str, title: str | None) -> str | None:
    """Pattern-match response content for known signals."""
    text = (title or "") + " " + html[:TITLE_READ_LIMIT]
    for pattern, note in _NOTE_PATTERNS:
        if pattern.search(text):
            return note
    return None


# ---------------------------------------------------------------------------
# Domain comparison
# ---------------------------------------------------------------------------

def domains_differ(original_url: str, final_url: str | None) -> bool:
    """Check if the domain changed after following redirects."""
    if not final_url:
        return False
    try:
        orig = urlparse(original_url).netloc.lower().lstrip("www.")
        final = urlparse(final_url).netloc.lower().lstrip("www.")
        return orig != final
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Async URL checking
# ---------------------------------------------------------------------------

async def _request_with_retry(
    client: httpx.AsyncClient,
    method: str,
    url: str,
) -> httpx.Response:
    """Make an HTTP request with retry on 429 and 5xx.

    Respects Retry-After header. Retries up to MAX_RETRIES times.
    """
    for attempt in range(MAX_RETRIES + 1):
        resp = await getattr(client, method)(url, follow_redirects=True)

        if resp.status_code == 429 or (resp.status_code >= 500 and attempt < MAX_RETRIES):
            retry_after = resp.headers.get("retry-after")
            if retry_after:
                try:
                    wait = min(float(retry_after), 120)  # cap at 2 minutes
                except ValueError:
                    wait = 30
            else:
                wait = 2 ** (attempt + 1)  # 2, 4, 8 seconds
            log.debug("Got %d from %s, retrying in %.0fs (attempt %d/%d)",
                      resp.status_code, url, wait, attempt + 1, MAX_RETRIES)
            await asyncio.sleep(wait)
            continue

        return resp

    return resp  # return last response even if still failing


async def check_url(
    client: httpx.AsyncClient,
    global_sem: asyncio.Semaphore,
    domain_sems: dict[str, asyncio.Semaphore],
    domain_last_request: dict[str, float],
    link: dict,
) -> dict:
    """Check a single URL. Returns a result dict.

    link dict has keys: url, link_pks (list of link.pk values sharing this URL).

    Strategy:
      1. Skip FTP URLs
      2. GET to read body for title extraction (first 8KB)
      3. Respect 429 Retry-After headers
      6. Per-domain pacing (DOMAIN_DELAY between requests)
      7. Pattern-match for known signals
    """
    link_pks = link["link_pks"]
    url = link["url"]

    # Skip FTP
    if url.lower().startswith("ftp://") or url.lower().startswith("ftps://"):
        return {
            "link_pks": link_pks,
            "url": url,
            "http_status": 0,
            "message": "FTP — skipped",
            "is_working": False,
            "final_url": None,
            "page_title": None,
            "domain_changed": False,
            "note": "FTP — skipped",
        }

    # Per-domain rate limit
    domain = urlparse(url).netloc.lower()
    if domain not in domain_sems:
        domain_sems[domain] = asyncio.Semaphore(MAX_PER_DOMAIN)

    async with global_sem, domain_sems[domain]:
        # Per-domain pacing: wait if we hit this domain too recently
        now = time.monotonic()
        last = domain_last_request.get(domain, 0)
        gap = DOMAIN_DELAY - (now - last)
        if gap > 0:
            await asyncio.sleep(gap)
        domain_last_request[domain] = time.monotonic()

        http_status = 0
        message = ""
        final_url = None
        page_title = None
        note = None
        body_html = ""

        try:
            # Single GET request — gets status and body for title extraction
            resp = await _request_with_retry(client, "get", url)
            body_html = resp.text[:TITLE_READ_LIMIT]

            http_status = resp.status_code
            message = resp.reason_phrase or ""

            # Record final URL if redirected
            if str(resp.url) != url:
                final_url = str(resp.url)

        except httpx.TimeoutException as exc:
            http_status = 0
            message = str(exc)[:255]

        except (httpx.ConnectError, Exception) as exc:
            exc_str = str(exc)
            exc_lower = exc_str.lower()

            if "ssl" in exc_lower or "certificate" in exc_lower or "dh" in exc_lower:
                # Retry with relaxed SSL — handles bad certs, weak DH keys, etc.
                import ssl as _ssl
                try:
                    ctx = _ssl.create_default_context()
                    ctx.check_hostname = False
                    ctx.verify_mode = _ssl.CERT_NONE
                    ctx.set_ciphers('DEFAULT:@SECLEVEL=1')
                    insecure_client = httpx.AsyncClient(
                        timeout=client.timeout,
                        headers={"User-Agent": USER_AGENT},
                        follow_redirects=True,
                        verify=ctx,
                    )
                    async with insecure_client:
                        resp = await insecure_client.get(url, follow_redirects=True)
                        http_status = resp.status_code
                        message = resp.reason_phrase or ""
                        body_html = resp.text[:TITLE_READ_LIMIT]
                        if str(resp.url) != url:
                            final_url = str(resp.url)
                        note = "SSL certificate error (site reachable without verification)"
                except Exception:
                    http_status = -1
                    message = exc_str[:255]
                    note = "SSL certificate error"
            elif isinstance(exc, httpx.ConnectError):
                http_status = 0
                message = exc_str[:255]
            else:
                http_status = -2
                message = exc_str[:255]

        # Extract title and detect patterns
        if body_html:
            page_title = extract_title(body_html)
            detected_note = detect_note(body_html, page_title)
            if detected_note:
                note = detected_note  # pattern-matched note takes priority

        is_working = http_status in WORKING_CODES

        # Servers that reject bots but are clearly alive
        if http_status in PROBABLY_WORKING_CODES:
            is_working = True
            if not note:
                note = f"Server returned {http_status} (probably working)"

        # Server error but page has real content (misconfigured status code)
        if http_status >= 500 and not is_working and page_title:
            is_working = True
            if not note:
                note = f"Server returned {http_status} but page has content"

        return {
            "link_pks": link_pks,
            "url": url,
            "http_status": http_status,
            "message": message[:255],
            "is_working": is_working,
            "final_url": final_url,
            "page_title": page_title,
            "domain_changed": domains_differ(url, final_url),
            "note": note,
        }


# ---------------------------------------------------------------------------
# Database writes
# ---------------------------------------------------------------------------

def write_result(
    connection: pymysql.Connection,
    result: dict,
    *,
    dry_run: bool = False,
) -> None:
    """Write check result for all link_pks sharing the same URL."""
    if dry_run:
        return

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    is_working = result["is_working"]

    params = {
        "http_status": result["http_status"],
        "message": result["message"],
        "is_working": result["is_working"],
        "final_url": result["final_url"],
        "page_title": result["page_title"],
        "domain_changed": result["domain_changed"],
        "now": now,
        "init_fail_count": 0 if is_working else 1,
        "note": result["note"],
        "last_working": now if is_working else None,
        "title_ok": result["page_title"] if is_working else None,
        "final_url_ok": result["final_url"] if is_working else None,
    }

    with connection.cursor() as cursor:
        for link_pk in result["link_pks"]:
            # Upsert into link_check
            params["link_pk"] = link_pk
            cursor.execute("""
                INSERT INTO link_check
                    (link_pk, http_status, message, is_working, final_url, page_title,
                     domain_changed, checked_at, fail_count, note,
                     last_working, title_ok, final_url_ok)
                VALUES
                    (%(link_pk)s, %(http_status)s, %(message)s, %(is_working)s,
                     %(final_url)s, %(page_title)s, %(domain_changed)s, %(now)s,
                     %(init_fail_count)s, %(note)s,
                     %(last_working)s, %(title_ok)s, %(final_url_ok)s)
                ON DUPLICATE KEY UPDATE
                    http_status    = VALUES(http_status),
                    message        = VALUES(message),
                    is_working     = VALUES(is_working),
                    final_url      = VALUES(final_url),
                    page_title     = VALUES(page_title),
                    domain_changed = VALUES(domain_changed),
                    checked_at     = VALUES(checked_at),
                    note           = VALUES(note),
                    fail_count     = CASE WHEN VALUES(is_working) = 1 THEN 0
                                          ELSE fail_count + 1 END,
                    last_working   = CASE WHEN VALUES(is_working) = 1 THEN VALUES(checked_at)
                                          ELSE last_working END,
                    title_ok       = CASE WHEN VALUES(is_working) = 1 THEN VALUES(page_title)
                                          ELSE title_ok END,
                    final_url_ok   = CASE WHEN VALUES(is_working) = 1 THEN VALUES(final_url)
                                          ELSE final_url_ok END
            """, params)

            # Also update the link table for backward compatibility
            if is_working:
                cursor.execute(
                    "UPDATE link SET is_working=%s, message=%s, last_working=%s WHERE pk=%s",
                    (1, result["message"], now, link_pk),
                )
            else:
                cursor.execute(
                    "UPDATE link SET is_working=%s, message=%s WHERE pk=%s",
                    (0, result["message"], link_pk),
                )


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

async def run(args: argparse.Namespace) -> None:
    db_cfg = read_db_config()
    connection = get_connection(db_cfg, args.database)

    try:
        links = fetch_links(connection, args.link_type,
                            retry_failed=args.retry_failed)
    except Exception:
        connection.close()
        raise

    if not links:
        log.info("No links to check.")
        connection.close()
        return

    global_sem = asyncio.Semaphore(args.concurrency)
    domain_sems: dict[str, asyncio.Semaphore] = {}
    domain_last_request: dict[str, float] = {}

    timeout = httpx.Timeout(
        connect=args.connect_timeout,
        read=args.read_timeout,
        write=10.0,
        pool=10.0,
    )

    results_queue: asyncio.Queue = asyncio.Queue()
    total = len(links)
    checked = 0
    working = 0
    failed = 0
    interactive = getattr(args, "interactive", False)
    start_time = datetime.datetime.now()

    # Recent failures for the interactive ticker
    recent_failures: list[str] = []
    MAX_RECENT = 5

    def _render_progress():
        """Render the interactive progress display."""
        if not interactive:
            return

        elapsed = (datetime.datetime.now() - start_time).total_seconds()
        rate = checked / elapsed if elapsed > 0 else 0
        remaining = (total - checked) / rate if rate > 0 else 0

        pct = checked * 100 / total if total else 0
        bar_width = 30
        filled = int(bar_width * checked / total) if total else 0
        bar = "█" * filled + "░" * (bar_width - filled)

        # Format ETA
        if remaining > 3600:
            eta = f"{remaining/3600:.1f}h"
        elif remaining > 60:
            eta = f"{remaining/60:.0f}m{remaining%60:.0f}s"
        else:
            eta = f"{remaining:.0f}s"

        # Clear screen area and draw
        lines = []
        lines.append(f"\033[2K  {bar} {pct:5.1f}%  ({checked}/{total})")
        lines.append(f"\033[2K  ✓ {working} working   ✗ {failed} failed   "
                     f"{rate:.1f}/s   ETA {eta}")

        if recent_failures:
            lines.append(f"\033[2K  ── recent failures ──")
            for entry in recent_failures[-MAX_RECENT:]:
                lines.append(f"\033[2K    {entry}")

        # Move cursor up and redraw
        output = f"\033[{len(lines)}A" if checked > 1 else ""
        output += "\n".join(lines)
        print(output, flush=True)

    # Print initial blank lines so _render_progress has space to overwrite
    if interactive:
        print(f"  Checking {total} links ({args.link_type})...\n" * 1, end="")
        # Reserve lines: progress bar + stats + header + MAX_RECENT failures
        for _ in range(2 + 1 + MAX_RECENT):
            print()

    async def producer():
        async with httpx.AsyncClient(
            timeout=timeout,
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
        ) as client:
            tasks = [
                check_url(client, global_sem, domain_sems, domain_last_request, link)
                for link in links
            ]
            for coro in asyncio.as_completed(tasks):
                result = await coro
                await results_queue.put(result)
            await results_queue.put(None)  # sentinel

    async def consumer():
        nonlocal checked, working, failed
        uncommitted = 0

        while True:
            result = await results_queue.get()
            if result is None:
                break

            try:
                connection.ping(reconnect=True)
                write_result(connection, result, dry_run=args.dry_run)
                uncommitted += 1

                if result["is_working"]:
                    working += 1
                else:
                    failed += 1
                    if interactive:
                        url_short = result["url"][:50]
                        status = result["http_status"]
                        note = result.get("note") or result["message"][:30]
                        recent_failures.append(f"[{status:>4}] {url_short}  {note}")
                checked += 1

                if uncommitted >= 50 and not args.dry_run:
                    connection.commit()
                    uncommitted = 0

                _render_progress()

            except Exception:
                log.exception("Error writing result for link_pks=%s %s",
                              result["link_pks"], result["url"])

        # Final commit
        if uncommitted > 0 and not args.dry_run:
            connection.commit()

    await asyncio.gather(producer(), consumer())

    connection.close()

    elapsed = (datetime.datetime.now() - start_time).total_seconds()
    if interactive:
        print(f"\n\033[2K  Done. {checked}/{total} checked — "
              f"{working} working, {failed} failed "
              f"({elapsed:.1f}s)")
    elif not getattr(args, "quiet", False):
        print(f"Done. {checked}/{total} checked — "
              f"{working} working, {failed} failed.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser(parser: argparse.ArgumentParser | None = None) -> argparse.ArgumentParser:
    """Build the argument parser. Accepts an existing parser for subcommand use."""
    if parser is None:
        parser = argparse.ArgumentParser(
            description="Async link checker for the ASCL v4 database.",
        )

    parser.add_argument(
        "database", nargs="?", default="ascl_db_v4",
        help="Database name (default: ascl_db_v4)",
    )
    parser.add_argument(
        "--link-type", default="code-site",
        help="Link type short_name to check (default: code-site). Use 'all' for all.",
    )
    parser.add_argument(
        "--concurrency", type=int, default=MAX_CONCURRENT,
        help=f"Max concurrent HTTP requests (default: {MAX_CONCURRENT})",
    )
    parser.add_argument(
        "--connect-timeout", type=float, default=CONNECT_TIMEOUT,
        help=f"HTTP connect timeout in seconds (default: {CONNECT_TIMEOUT})",
    )
    parser.add_argument(
        "--read-timeout", type=float, default=READ_TIMEOUT,
        help=f"HTTP read timeout in seconds (default: {READ_TIMEOUT})",
    )
    parser.add_argument(
        "--retry-failed", action="store_true",
        help="Only re-check links that previously failed (is_working=0 in link_check)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Check URLs but skip database writes",
    )
    parser.add_argument(
        "-i", "--interactive", action="store_true",
        help="Show rich interactive progress display (for terminal use)",
    )
    parser.add_argument(
        "-q", "--quiet", action="store_true",
        help="Suppress all output (default for cron)",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Enable debug logging (implies --interactive)",
    )

    return parser


def cmd_linkcheck(args: argparse.Namespace) -> None:
    """Entry point for both standalone and CLI subcommand."""
    if args.verbose:
        args.interactive = True

    if args.quiet:
        args.interactive = False
        log_level = logging.CRITICAL
    elif args.verbose:
        log_level = logging.DEBUG
    else:
        log_level = logging.WARNING

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(levelname)-8s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    asyncio.run(run(args))


def register_subcommands(subparsers, load_config_fn):
    """Register 'linkcheck' subcommand on the main ascl CLI parser."""
    p = subparsers.add_parser("linkcheck", help="Check links in the ASCL database")
    build_parser(p)
    p.set_defaults(func=cmd_linkcheck)


def main():
    parser = build_parser()
    args = parser.parse_args()
    cmd_linkcheck(args)


if __name__ == "__main__":
    main()
