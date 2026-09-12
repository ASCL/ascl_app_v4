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
  2026-09-11 Distinguish a 404 from an unreachable repo (ProbeResult). A
             non-200 was previously recorded as absence, so one GitHub
             outage would null out already-discovered URLs.
  2026-06-24 Rewritten: correctness fixes + quiet-on-success.
"""

import argparse
import datetime
import enum
import logging
import os
import re
import sys
import time

from db_config import read_db_config, pymysql_kwargs

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
# Credentials come from ~/.my.cnf [client_ascl]; see db_config.py.
codes_table = "codes"
citefiles_table = "citefile_metadata"

PLACEHOLDER_ID = "0000.000"
GITHUB_URL_RE = re.compile(r'"([^"]+github[^"]+)"')

REQUEST_TIMEOUT = 15  # seconds
REQUEST_PAUSE = 0.1   # seconds between requests, to be polite

# Fail the run if more than this fraction of probes could not be resolved.
# A few flaky repos are normal; a systemic GitHub outage or a block is not,
# and must not pass as a quiet success.
INDETERMINATE_FAIL_RATE = 0.10


class ProbeResult(enum.Enum):
    """Outcome of probing one repo for one file.

    ABSENT means GitHub answered 404: the file really is not there.
    INDETERMINATE means we could not find out (rate limit, 5xx, timeout,
    DNS). The two must never be conflated -- recording INDETERMINATE as
    absence erases real data on the next write.
    """

    FOUND = "found"
    ABSENT = "absent"
    INDETERMINATE = "indeterminate"


def get_connection():
    kwargs = pymysql_kwargs(read_db_config())
    kwargs["cursorclass"] = pymysql.cursors.DictCursor
    return pymysql.connect(**kwargs)


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
    """Probe a repo's default branch for `filename`.

    Returns (ProbeResult, url). Only a 404 is treated as absence. Any other
    outcome is INDETERMINATE, and write_result leaves the stored column alone
    for those, so a transient GitHub failure cannot erase a URL we previously
    discovered.
    """
    raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/HEAD/{filename}"
    try:
        resp = session.get(raw_url, timeout=REQUEST_TIMEOUT, stream=True)
        resp.close()
    except requests.RequestException as exc:
        log.warning("Indeterminate (request failed) %s/%s %s: %s",
                    owner, repo, filename, exc)
        return ProbeResult.INDETERMINATE, None
    finally:
        time.sleep(REQUEST_PAUSE)

    if resp.status_code == 200:
        # Human-facing URL; blob/HEAD redirects to whatever the default branch is.
        return ProbeResult.FOUND, f"https://github.com/{owner}/{repo}/blob/HEAD/{filename}"
    if resp.status_code == 404:
        return ProbeResult.ABSENT, None

    log.warning("Indeterminate (HTTP %s) %s/%s %s",
                resp.status_code, owner, repo, filename)
    return ProbeResult.INDETERMINATE, None


def check_entry(session, entry):
    """Return {ascl_id, codemeta, citation_cff, present}.

    `codemeta` and `citation_cff` are (ProbeResult, url) pairs. A repo that
    yields FOUND short-circuits further probing for that file; otherwise
    INDETERMINATE outranks ABSENT, so we never claim a file is missing on the
    strength of a repo we could not reach.
    """
    states = {
        "codemeta.json": (ProbeResult.ABSENT, None),
        "CITATION.cff": (ProbeResult.ABSENT, None),
    }
    parsed_any_url = False

    for url in entry["urls"]:
        # Expect https://github.com/<owner>/<repo> (4 slashes).
        if url.count("/") != 4:
            log.debug("Skipping non-standard GitHub URL: %s", url)
            continue
        parsed_any_url = True
        owner, repo = url.split("/")[-2], url.split("/")[-1]
        for filename in states:
            if states[filename][0] is ProbeResult.FOUND:
                continue
            state, found_url = probe_file(session, owner, repo, filename)
            if state is ProbeResult.FOUND:
                states[filename] = (state, found_url)
            elif state is ProbeResult.INDETERMINATE:
                states[filename] = (state, None)

    if not parsed_any_url:
        # Every URL was unparseable, so we learned nothing about this code.
        # Recording absence here would be an assertion we never tested.
        log.warning("No parseable GitHub URL for %s; leaving row unchanged",
                    entry["ascl_id"])
        states = {name: (ProbeResult.INDETERMINATE, None) for name in states}

    return {
        "ascl_id": entry["ascl_id"],
        "codemeta": states["codemeta.json"],
        "citation_cff": states["CITATION.cff"],
        "present": entry["present"],
    }


def write_result(connection, result, dry_run=False):
    """Persist only the determinate outcomes for one code.

    An INDETERMINATE column is omitted from the statement entirely, so the
    stored value survives. Writing NULL because GitHub was unreachable would
    destroy a real, previously discovered URL -- and the next run would have
    no way to tell that had happened.
    """
    if dry_run:
        return

    # Fixed literals, not user input: safe to interpolate as identifiers.
    columns = {}
    for key, column in (("codemeta", "codemeta_url"),
                        ("citation_cff", "citation_cff_url")):
        state, url = result[key]
        if state is not ProbeResult.INDETERMINATE:
            columns[column] = url

    if not columns:
        log.warning("No determinate result for %s; leaving row unchanged",
                    result["ascl_id"])
        return

    now = datetime.datetime.now()
    with connection.cursor() as cursor:
        if result["present"]:
            assignments = ", ".join(f"`{c}` = %s" for c in columns)
            cursor.execute(
                f"UPDATE `{citefiles_table}` SET {assignments}, `time_updated` = %s "
                f"WHERE `ascl_id` = %s",
                (*columns.values(), now, result["ascl_id"]),
            )
        else:
            names = ", ".join(f"`{c}`" for c in columns)
            marks = ", ".join(["%s"] * len(columns))
            cursor.execute(
                f"INSERT INTO `{citefiles_table}` (`ascl_id`, {names}, `time_updated`) "
                f"VALUES (%s, {marks}, %s)",
                (result["ascl_id"], *columns.values(), now),
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
    probes = indeterminate = 0
    try:
        entries = load_entries(connection, limit=args.limit)
        log.info("Checking %d codes with GitHub URLs", len(entries))
        for i, entry in enumerate(entries, 1):
            result = check_entry(session, entry)
            write_result(connection, result, dry_run=args.dry_run)
            for key in ("codemeta", "citation_cff"):
                state, _ = result[key]
                probes += 1
                if state is ProbeResult.INDETERMINATE:
                    indeterminate += 1
            found_codemeta += result["codemeta"][0] is ProbeResult.FOUND
            found_cff += result["citation_cff"][0] is ProbeResult.FOUND
            if args.verbose and i % 100 == 0:
                log.info("  processed %d/%d", i, len(entries))
    finally:
        connection.close()

    log.info("%sDone: %d codemeta.json, %d CITATION.cff found",
             "[DRY RUN] " if args.dry_run else "", found_codemeta, found_cff)

    # Unresolved probes are reported at WARNING so they surface even in the
    # quiet mode cron uses, and a systemic failure fails the run outright
    # rather than passing as a night with "nothing found".
    if indeterminate:
        rate = indeterminate / probes if probes else 0.0
        log.warning(
            "%d of %d probes were indeterminate (%.1f%%); those values were "
            "left unchanged", indeterminate, probes, 100 * rate)
        if rate > INDETERMINATE_FAIL_RATE:
            log.error(
                "Indeterminate rate exceeds %.0f%% -- treating this run as "
                "failed. GitHub may be rate limiting or unreachable.",
                100 * INDETERMINATE_FAIL_RATE)
            sys.exit(1)


if __name__ == "__main__":
    main()
