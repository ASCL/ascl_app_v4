#!/usr/bin/env python3
"""
ASCL.net citation importer (v3 schema).

Pulls citation data for every ASCL code entry from NASA ADS and updates the
v3 `citations` and `ads_entries_new` tables INCREMENTALLY (no truncate/rebuild),
preserving `created_at` timestamps and writing only changed rows.

Quiet by default so cron does not email a full log on every run: only warnings
and errors are emitted. Pass -v for a detailed report, --dry-run to preview.

Requires: Python 3.6+, ads (pip install ads), peewee, a MySQL server, and an
ADS API key at ~/.ads/dev_key.

Usage:
    python3 ascl_citations.py                 # normal (quiet) run
    python3 ascl_citations.py -v              # verbose report
    python3 ascl_citations.py --dry-run -v    # preview, no DB writes
    python3 ascl_citations.py --remove-deleted  # also delete citations gone from ADS

History:
  Originally a Python 2 truncate/rebuild script.
  2026-06-24 Ported to Python 3, made incremental and quiet-on-success.
"""

import argparse
import datetime
import logging
import sys

from db_config import read_db_config, pymysql_kwargs

try:
    import ads
except ImportError:
    sys.exit("ERROR: the 'ads' library is not installed (pip install ads).")

try:
    from peewee import (
        Model, MySQLDatabase, CharField, DateTimeField, IntegerField,
    )
except ImportError:
    sys.exit("ERROR: the 'peewee' library is not installed (pip install peewee).")

log = logging.getLogger("ascl_citations")

# --- Database config (v3) ---------------------------------------------------
# Credentials come from ~/.my.cnf [client_ascl]; see db_config.py.
citations_table = "citations"
ads_entries_table = "ads_entries_new"

# Deferred initialisation: the models below need `database` to exist at import
# time, but reading ~/.my.cnf here would make even `--help` fail when the file
# is missing. connect_database() fills it in once arguments are parsed.
database = MySQLDatabase(None)


def connect_database():
    """Point `database` at the configured server and open the connection."""
    kwargs = pymysql_kwargs(read_db_config())
    database.init(kwargs.pop("database"), **kwargs)
    database.connect()


class BaseModel(Model):
    class Meta:
        database = database


class Citations(BaseModel):
    content = CharField()
    created_at = DateTimeField()
    updated_at = DateTimeField()
    entry_asclid = CharField()
    journal = CharField()
    year = IntegerField()
    type = CharField(default="ascl_entry")

    class Meta:
        table_name = citations_table


class AdsEntries(BaseModel):
    ascl_id = CharField()
    created_at = DateTimeField()
    updated_at = DateTimeField()

    class Meta:
        table_name = ads_entries_table


# --- Bibcode parsing --------------------------------------------------------
def find_ascl_id(bibcode):
    """2012ascl.soft03003C -> 1203.003"""
    try:
        return bibcode[2:4] + bibcode[13:15] + "." + bibcode[15:18]
    except (IndexError, TypeError):
        log.warning("Could not parse ASCL ID from bibcode: %r", bibcode)
        return "0000.000"


def find_year(bibcode):
    try:
        return int(bibcode[0:4])
    except (ValueError, IndexError, TypeError):
        return 0


def find_journal(bibcode):
    try:
        return bibcode[4:9]
    except (IndexError, TypeError):
        return ""


# --- ADS query --------------------------------------------------------------
ADS_ROWS = 2000
ADS_MAX_PAGES = 20


def fetch_ads_data():
    """Return {bibcode: {ascl_id, citations: [{content, year, journal, entry_asclid}]}}."""
    log.info("Querying NASA ADS (bibstem:ascl.soft)...")
    try:
        papers = ads.SearchQuery(
            q="bibstem:ascl.soft",
            sort="citation_count",
            rows=ADS_ROWS,
            max_pages=ADS_MAX_PAGES,
            fl=["title", "citation_count", "citation", "bibcode"],
        )
    except Exception as exc:
        sys.exit(f"ERROR: ADS query failed: {exc}")

    ads_data = {}
    processed = 0
    for paper in papers:
        try:
            bibcode = paper.bibcode
            ascl_id = find_ascl_id(bibcode)
            entry = {"ascl_id": ascl_id, "citations": []}
            if paper.citation_count and paper.citation and paper.citation_count > 0:
                for cit in paper.citation:
                    entry["citations"].append({
                        "content": cit,
                        "year": find_year(cit),
                        "journal": find_journal(cit),
                        "entry_asclid": ascl_id,
                    })
            ads_data[bibcode] = entry
            processed += 1
        except Exception as exc:
            log.warning("Error processing ADS entry %d: %s", processed, exc)
    log.info("ADS returned %d entries, %d citations total",
             processed, sum(len(e["citations"]) for e in ads_data.values()))
    return ads_data


# --- Incremental DB update --------------------------------------------------
def update_database(ads_data, dry_run=False, remove_deleted=False):
    now = datetime.datetime.now()
    stats = dict(ads_new=0, ads_updated=0, cit_new=0, cit_updated=0,
                 cit_unchanged=0, cit_removed=0)

    # ads_entries_new: upsert by bibcode
    existing_ads = {e.ascl_id: e for e in AdsEntries.select()}
    for bibcode in ads_data:
        if bibcode in existing_ads:
            if not dry_run:
                e = existing_ads[bibcode]
                e.updated_at = now
                e.save()
            stats["ads_updated"] += 1
        else:
            if not dry_run:
                AdsEntries.create(ascl_id=bibcode, created_at=now, updated_at=now)
            stats["ads_new"] += 1

    # citations: upsert by (entry_asclid, content)
    existing = {(c.entry_asclid, c.content): c for c in Citations.select()}
    ads_keys = set()
    new_rows = []
    for entry in ads_data.values():
        for cit in entry["citations"]:
            key = (cit["entry_asclid"], cit["content"])
            ads_keys.add(key)
            current = existing.get(key)
            if current is None:
                new_rows.append({
                    "entry_asclid": cit["entry_asclid"],
                    "content": cit["content"],
                    "year": cit["year"],
                    "journal": cit["journal"],
                    "type": "ascl_entry",
                    "created_at": now,
                    "updated_at": now,
                })
                stats["cit_new"] += 1
            elif current.year != cit["year"] or current.journal != cit["journal"]:
                if not dry_run:
                    current.year = cit["year"]
                    current.journal = cit["journal"]
                    current.updated_at = now
                    current.save()
                stats["cit_updated"] += 1
            else:
                stats["cit_unchanged"] += 1

    if new_rows and not dry_run:
        with database.atomic():
            for i in range(0, len(new_rows), 1000):
                Citations.insert_many(new_rows[i:i + 1000]).execute()

    if remove_deleted:
        for key, citation in existing.items():
            if key not in ads_keys:
                if not dry_run:
                    citation.delete_instance()
                stats["cit_removed"] += 1

    return stats


def main():
    parser = argparse.ArgumentParser(description="Import ASCL citations from ADS (v3).")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would change without writing to the DB.")
    parser.add_argument("--remove-deleted", action="store_true",
                        help="Delete citations no longer present in ADS (default: keep).")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Print a detailed report (default: quiet, errors only).")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)-8s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    ads_data = fetch_ads_data()
    if not ads_data:
        log.warning("ADS returned no entries; nothing to do.")
        return

    connect_database()
    try:
        stats = update_database(ads_data, dry_run=args.dry_run,
                                remove_deleted=args.remove_deleted)
    finally:
        if not database.is_closed():
            database.close()

    log.info("%scitations: +%d new, %d updated, %d unchanged, %d removed; "
             "ads_entries: +%d new, %d updated",
             "[DRY RUN] " if args.dry_run else "",
             stats["cit_new"], stats["cit_updated"], stats["cit_unchanged"],
             stats["cit_removed"], stats["ads_new"], stats["ads_updated"])


if __name__ == "__main__":
    main()
