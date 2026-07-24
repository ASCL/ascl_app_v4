#!/usr/bin/env python3
"""
Detect codemeta.json / CITATION.cff files in the GitHub repos of ASCL codes
and record their locations in the v3 `citefile_metadata` table.

For every code whose `site_list` contains a GitHub URL, this probes the repo's
default branch (via the `HEAD` ref, so both `main`- and `master`-based repos
work) for `codemeta.json` and `CITATION.cff`, then upserts the result.

Quiet by default so cron does not email a full log on every run: only warnings
and errors are emitted. Pass -v for progress, --dry-run to skip DB writes.

Fixes over the previous version:
  - Adds the missing connection.commit() (it previously wrote nothing).
  - Wraps all network calls in try/except (no more uncaught tracebacks).
  - Uses the `HEAD` ref instead of hardcoded `master`.
  - Probes raw.githubusercontent.com (not rate-limited like the API) and is
    polite about request pacing; honours an optional GITHUB_TOKEN env var.
  - Silent on success.

Usage:
    python3 citefile_metadata.py                # normal (quiet) run
    python3 citefile_metadata.py -v             # show progress
    python3 citefile_metadata.py --dry-run -v   # probe, no DB writes
    python3 citefile_metadata.py --limit 50     # only the 50 stalest entries

History:
  2026-06-24 Rewritten: correctness fixes + quiet-on-success.
"""

import argparse
import datetime
import logging
import os
import re
import sys
import time

try:
    import pymysql
except ImportError:
    sys.exit("ERROR: the 'pymysql' library is not installed (pip install pymysql).")

try:
    import requests
except ImportError:
    sys.exit("ERROR: the 'requests' library is not installed (pip install requests).")

log = logging.getLogger("citefile_metadata")

# --- Database config (v3) ---------------------------------------------------
db_name = "ascl_db"
db_user = "ascl_db"
db_pass = "voCNg.K={Zn~"

codes_table = "codes"
citefiles_table = "citefile_metadata"

PLACEHOLDER_ID = "0000.000"
GITHUB_URL_RE = re.compile(r'"([^"]+github[^"]+)"')

REQUEST_TIMEOUT = 15  # seconds
REQUEST_PAUSE = 0.1   # seconds between requests, to be polite


def get_connection():
    return pymysql.connect(
        host="localhost", user=db_user, password=db_pass, db=db_name,
        charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor,
    )


def make_session():
    session = requests.Session()
    session.headers["User-Agent"] = "ASCL citefile metadata bot (+https://ascl.net)"
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        session.headers["Authorization"] = f"token {token}"
    return session


def load_entries(connection, limit=None):
    """Return [{ascl_id, urls: [github_url], present: bool}] for codes with GitHub URLs."""
    with connection.cursor() as cursor:
        deleted = cursor.execute(
            f"DELETE FROM `{citefiles_table}` WHERE `ascl_id` = %s", (PLACEHOLDER_ID,)
        )
        if deleted:
            log.info("Removed %d placeholder (%s) citefile rows", deleted, PLACEHOLDER_ID)

        sql = (
            f"SELECT {citefiles_table}.time_updated AS citefile_time_updated, "
            f"       {codes_table}.ascl_id, {codes_table}.site_list "
            f"FROM {codes_table} "
            f"LEFT OUTER JOIN {citefiles_table} "
            f"  ON {codes_table}.ascl_id = {citefiles_table}.ascl_id "
            f"WHERE {codes_table}.ascl_id <> %s "
            f"  AND {codes_table}.site_list LIKE %s "
            # Process stalest (or never-checked) entries first.
            f"ORDER BY {citefiles_table}.time_updated IS NOT NULL, "
            f"         {citefiles_table}.time_updated ASC"
        )
        params = [PLACEHOLDER_ID, "%github%"]
        if limit:
            sql += " LIMIT %s"
            params.append(limit)
        cursor.execute(sql, params)
        rows = cursor.fetchall()

    connection.commit()  # persist the placeholder DELETE

    entries = []
    for row in rows:
        urls = GITHUB_URL_RE.findall(row["site_list"] or "")
        if not urls:
            continue
        entries.append({
            "ascl_id": row["ascl_id"],
            "urls": urls,
            "present": bool(row["citefile_time_updated"]),
        })
    return entries


def probe_file(session, owner, repo, filename):
    """Return a github.com blob URL (default branch) if the file exists, else None."""
    raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/HEAD/{filename}"
    try:
        resp = session.get(raw_url, timeout=REQUEST_TIMEOUT, stream=True)
        resp.close()
    except requests.RequestException as exc:
        log.warning("Request failed for %s/%s %s: %s", owner, repo, filename, exc)
        return None
    finally:
        time.sleep(REQUEST_PAUSE)

    if resp.status_code == 200:
        # Human-facing URL; blob/HEAD redirects to whatever the default branch is.
        return f"https://github.com/{owner}/{repo}/blob/HEAD/{filename}"
    return None


def check_entry(session, entry):
    """Return {ascl_id, codemeta_url, citation_cff_url, present}."""
    codemeta_url = None
    citation_cff_url = None
    for url in entry["urls"]:
        # Expect https://github.com/<owner>/<repo> (4 slashes).
        if url.count("/") != 4:
            log.debug("Skipping non-standard GitHub URL: %s", url)
            continue
        owner, repo = url.split("/")[-2], url.split("/")[-1]
        codemeta_url = codemeta_url or probe_file(session, owner, repo, "codemeta.json")
        # CITATION.cff: capitalization matters.
        citation_cff_url = citation_cff_url or probe_file(session, owner, repo, "CITATION.cff")
    return {
        "ascl_id": entry["ascl_id"],
        "codemeta_url": codemeta_url,
        "citation_cff_url": citation_cff_url,
        "present": entry["present"],
    }


def write_result(connection, result, dry_run=False):
    if dry_run:
        return
    now = datetime.datetime.now()
    with connection.cursor() as cursor:
        if result["present"]:
            cursor.execute(
                f"UPDATE `{citefiles_table}` SET `codemeta_url` = %s, "
                f"`citation_cff_url` = %s, `time_updated` = %s WHERE `ascl_id` = %s",
                (result["codemeta_url"], result["citation_cff_url"], now, result["ascl_id"]),
            )
        else:
            cursor.execute(
                f"INSERT INTO `{citefiles_table}` "
                f"(`ascl_id`, `codemeta_url`, `citation_cff_url`, `time_updated`) "
                f"VALUES (%s, %s, %s, %s)",
                (result["ascl_id"], result["codemeta_url"], result["citation_cff_url"], now),
            )
    connection.commit()


def main():
    parser = argparse.ArgumentParser(
        description="Record codemeta.json / CITATION.cff locations for ASCL GitHub repos (v3).")
    parser.add_argument("--dry-run", action="store_true",
                        help="Probe repos but do not write to the database.")
    parser.add_argument("--limit", type=int, default=None,
                        help="Only process the N stalest entries (default: all).")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Show progress (default: quiet, errors only).")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)-8s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    connection = get_connection()
    session = make_session()
    found_codemeta = found_cff = 0
    try:
        entries = load_entries(connection, limit=args.limit)
        log.info("Checking %d codes with GitHub URLs", len(entries))
        for i, entry in enumerate(entries, 1):
            result = check_entry(session, entry)
            write_result(connection, result, dry_run=args.dry_run)
            found_codemeta += bool(result["codemeta_url"])
            found_cff += bool(result["citation_cff_url"])
            if args.verbose and i % 100 == 0:
                log.info("  processed %d/%d", i, len(entries))
    finally:
        connection.close()

    log.info("%sDone: %d codemeta.json, %d CITATION.cff found",
             "[DRY RUN] " if args.dry_run else "", found_codemeta, found_cff)


if __name__ == "__main__":
    main()
