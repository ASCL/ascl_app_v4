#!/usr/bin/env python3
"""
Async link checker for the ASCL database.

Checks all URLs in the `codes` table for availability using concurrent
HTTP requests and writes results to the `links_new` table.

Drop-in replacement for link_checker.py — same DB tables, same result codes.
Requires Python 3.13+, httpx, pymysql, phpserialize.

Usage:
    python3 link_checker_async.py                  # full run
    python3 link_checker_async.py --dry-run -v     # check URLs, skip DB writes
    python3 link_checker_async.py --concurrency 10 # limit concurrency
    
History:
  2026-02-20 Initial creation.
"""

import argparse
import asyncio
import configparser
import datetime
import logging
import os
import sys

import httpx
import pymysql
from phpserialize import dict_to_tuple, loads as php_loads

# ---------------------------------------------------------------------------
# Tunable constants (overridable via CLI args)
# ---------------------------------------------------------------------------
MAX_CONCURRENT = 50
CONNECT_TIMEOUT = 10   # seconds
READ_TIMEOUT = 20      # seconds
USER_AGENT = "ASCL Link Checker/2.0 (+https://ascl.net)"

WORKING_CODES = {"200", "202"}

log = logging.getLogger("link_checker")

# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def read_db_config() -> dict:
    """Read MySQL credentials from ~/.my.cnf.

    Prefers the [client_ascl] section, falls back to [client].
    """
    cnf_path = os.path.expanduser("~/.my.cnf")
    if not os.path.exists(cnf_path):
        sys.exit(f"Error: {cnf_path} not found. Create it with [client] or [client_ascl] section.")

    config = configparser.ConfigParser()
    config.read(cnf_path)

    section = "client_ascl" if config.has_section("client_ascl") else "client"
    if not config.has_section(section):
        sys.exit(f"Error: No [client] or [client_ascl] section in {cnf_path}")

    cfg = {
        "host":     config.get(section, "host", fallback="localhost"),
        "user":     config.get(section, "user"),
        "password": config.get(section, "password"),
        "database": config.get(section, "database", fallback="ascl_db"),
        "port":     config.getint(section, "port", fallback=3306),
    }

    # Support Unix socket connections (common on shared/cPanel hosts).
    socket = config.get(section, "socket", fallback=None)
    if socket:
        cfg["unix_socket"] = socket

    return cfg


def get_connection(db_cfg: dict) -> pymysql.Connection:
    """Open a pymysql connection from the config dict."""
    kwargs = {
        "user":     db_cfg["user"],
        "password": db_cfg["password"],
        "database": db_cfg["database"],
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
# URL extraction
# ---------------------------------------------------------------------------

def fetch_urls(connection: pymysql.Connection) -> list[tuple[str, str]]:
    """Read all (ascl_id, url) pairs from the codes table."""
    urls = []
    with connection.cursor() as cursor:
        cursor.execute("SELECT ascl_id, site_list FROM codes")
        for row in cursor.fetchall():
            if row["ascl_id"] == "0000.000":
                continue
            if not row["site_list"]:
                continue
            try:
                site_data = php_loads(
                    row["site_list"].encode("utf-8"),
                    decode_strings=True,
                )
                for url in dict_to_tuple(site_data):
                    urls.append((row["ascl_id"], url))
            except Exception as exc:
                log.warning("Failed to deserialize site_list for %s: %s",
                            row["ascl_id"], exc)
    log.debug("Loaded %d URLs from %d code entries", len(urls), cursor.rowcount)
    return urls


# ---------------------------------------------------------------------------
# Async URL checking
# ---------------------------------------------------------------------------

async def check_url(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    ascl_id: str,
    url: str,
) -> tuple[str, str, str, str]:
    """Check a single URL. Returns (ascl_id, url, code, message).

    Tries HEAD first (avoids downloading body), falls back to GET on 405.
    """
    async with semaphore:
        try:
            resp = await client.head(url, follow_redirects=True)
            if resp.status_code == 405:
                resp = await client.get(url, follow_redirects=True)
            return (ascl_id, url, str(resp.status_code), " ")

        except httpx.TimeoutException as exc:
            return (ascl_id, url, "0", str(exc)[:255])

        except httpx.ConnectError as exc:
            return (ascl_id, url, "0", str(exc)[:255])

        except Exception as exc:
            # SSL errors in httpx surface as generic exceptions;
            # detect them by inspecting the message or cause chain.
            exc_str = str(exc)
            exc_lower = exc_str.lower()
            if "ssl" in exc_lower or "certificate" in exc_lower:
                return (ascl_id, url, "-1", exc_str[:255])
            return (ascl_id, url, "-2", exc_str[:255])


# ---------------------------------------------------------------------------
# Database writes
# ---------------------------------------------------------------------------

def write_result(
    connection: pymysql.Connection,
    ascl_id: str,
    url: str,
    code: str,
    message: str,
    *,
    dry_run: bool = False,
) -> None:
    """Write a single check result to the links_new table."""
    is_working = code in WORKING_CODES
    message = (message or " ")[:255]

    log.debug("%s %s code=%s %s Working=%s", ascl_id, url, code, message, is_working)

    if dry_run:
        return

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT * FROM `links_new` WHERE `url`=%s AND `ascl_id`=%s",
            (url, ascl_id),
        )
        record = cursor.fetchone()

        if record is None:
            last_working = now if is_working else "0000-00-00 00:00:00"
            cursor.execute(
                "INSERT INTO `links_new` "
                "(`url`, `code`, `message`, `created_at`, `updated_at`, "
                "`last_working`, `ascl_id`, `is_working`) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (url, code, message, now, now, last_working, ascl_id, is_working),
            )
        else:
            if is_working:
                cursor.execute(
                    "UPDATE `links_new` SET `code`=%s, `message`=%s, "
                    "`updated_at`=%s, `last_working`=%s, `is_working`=%s "
                    "WHERE `id`=%s",
                    (code, message, now, now, is_working, record["id"]),
                )
            else:
                cursor.execute(
                    "UPDATE `links_new` SET `code`=%s, `message`=%s, "
                    "`updated_at`=%s, `is_working`=%s "
                    "WHERE `id`=%s",
                    (code, message, now, is_working, record["id"]),
                )


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

async def run(args: argparse.Namespace) -> None:
    db_cfg = read_db_config()
    connection = get_connection(db_cfg)

    try:
        urls = fetch_urls(connection)
    except Exception:
        connection.close()
        raise

    if not urls:
        log.debug("No URLs to check.")
        connection.close()
        return

    semaphore = asyncio.Semaphore(args.concurrency)
    timeout = httpx.Timeout(
        connect=args.connect_timeout,
        read=args.read_timeout,
        write=10.0,
        pool=10.0,
    )

    results_queue: asyncio.Queue = asyncio.Queue()
    total = len(urls)
    checked = 0
    working = 0
    failed = 0

    async def producer():
        async with httpx.AsyncClient(
            timeout=timeout,
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
        ) as client:
            tasks = [
                check_url(client, semaphore, ascl_id, url)
                for ascl_id, url in urls
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

            ascl_id, url, code, message = result

            try:
                connection.ping(reconnect=True)
                write_result(connection, ascl_id, url, code, message,
                             dry_run=args.dry_run)
                uncommitted += 1

                if code in WORKING_CODES:
                    working += 1
                else:
                    failed += 1
                checked += 1

                if uncommitted >= 50 and not args.dry_run:
                    connection.commit()
                    uncommitted = 0

                if args.progress:
                    pct = checked * 100 // total
                    print(f"\r[{pct:3d}%] {checked}/{total}  "
                          f"{working} working, {failed} failed", end="", flush=True)

            except Exception:
                log.exception("Error writing result for %s %s", ascl_id, url)

        # Final commit
        if uncommitted > 0 and not args.dry_run:
            connection.commit()

    await asyncio.gather(producer(), consumer())

    connection.close()

    if args.progress:
        print(f"\rDone. {checked}/{total} checked — {working} working, {failed} failed.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Async link checker for the ASCL database.",
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
        "--dry-run", action="store_true",
        help="Check URLs but skip database writes",
    )
    parser.add_argument(
        "-p", "--progress", action="store_true",
        help="Print a one-line summary when finished",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Enable verbose logging (implies --progress)",
    )
    args = parser.parse_args()

    if args.verbose:
        args.progress = True

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)-8s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    asyncio.run(run(args))


if __name__ == "__main__":
    main()
