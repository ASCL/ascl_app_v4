#!/usr/bin/env python3
"""
Simplified PHP link migration script.
Uses MySQL command-line client for database operations.

This script unpacks PHP-serialized arrays from the following codes table columns:
- site_list → link_type 'Code Site' (code-site)
- described_in → link_type 'Described In' (described-in)
- used_in → link_type 'Used In' (used-in)
- ref_list → link_type 'Reference' (reference)

Usage:
    python3 migrate_php_links_simple.py [--dry-run] [--limit N]
"""

import sys
import argparse
import subprocess
import json
from typing import List, Optional

try:
    import phpserialize
except ImportError:
    print("ERROR: phpserialize library not found.")
    print("Install it with: pip install phpserialize")
    sys.exit(1)

# Map field names to link_type short_names
FIELD_TO_LINK_TYPE = {
    'site_list': 'code-site',
    'described_in': 'described-in',
    'used_in': 'used-in',
    'ref_list': 'reference'
}

# MySQL connection parameters
MYSQL_OPTS = [
    '--defaults-group-suffix=_ascl',
    '-h', '127.0.0.1',
    '-P', '3307',
    '-D', 'ascl_db_v4'
]


def mysql_query(query):
    """Execute MySQL query and return results as list of dicts."""
    cmd = ['mysql'] + MYSQL_OPTS + ['-N', '-e', query]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return result.stdout.strip()


def mysql_query_json(query):
    """Execute MySQL query and return results as JSON."""
    cmd = ['mysql'] + MYSQL_OPTS + ['--batch', '-e', query]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)

    lines = result.stdout.strip().split('\n')
    if len(lines) < 2:
        return []

    headers = lines[0].split('\t')
    rows = []
    for line in lines[1:]:
        values = line.split('\t')
        row = {headers[i]: values[i] if values[i] != 'NULL' else None
               for i in range(len(headers))}
        rows.append(row)
    return rows


def unserialize_php(serialized_data: Optional[str]) -> List[str]:
    """Unserialize PHP array data."""
    if not serialized_data or serialized_data == 'NULL' or serialized_data.strip() == '':
        return []

    try:
        data = phpserialize.loads(serialized_data.encode('utf-8'))

        # Convert to list if it's a dict (PHP arrays)
        if isinstance(data, dict):
            urls = [v.decode('utf-8') if isinstance(v, bytes) else v
                   for v in data.values()]
        elif isinstance(data, list):
            urls = [v.decode('utf-8') if isinstance(v, bytes) else v
                   for v in data]
        elif isinstance(data, bytes):
            urls = [data.decode('utf-8')]
        else:
            urls = [str(data)]

        # Filter out empty strings and None values
        return [url for url in urls if url and url.strip()]

    except Exception as e:
        print(f"  WARNING: Failed to unserialize data: {e}")
        return []


def load_link_types():
    """Load link_type table and create lookup map."""
    print("Loading link_type table...")
    rows = mysql_query_json("SELECT pk, short_name, label FROM link_type")

    link_type_map = {}
    for row in rows:
        link_type_map[row['short_name']] = {
            'pk': int(row['pk']),
            'label': row['label']
        }

    print(f"Loaded {len(link_type_map)} link types")
    return link_type_map


def link_exists(code_pk: int, url: str) -> bool:
    """Check if a link already exists for this code and URL."""
    # Escape single quotes in URL
    escaped_url = url.replace("'", "\\'")
    query = f"SELECT COUNT(*) FROM link WHERE code_pk = {code_pk} AND url = '{escaped_url}'"
    result = mysql_query(query)
    return int(result) > 0


def create_link(code_pk: int, url: str, link_type_pk: int, dry_run: bool):
    """Create a new link record."""
    # Escape single quotes in URL
    escaped_url = url.replace("'", "\\'")

    if dry_run:
        print(f"    [DRY RUN] Would create link: {url}")
        return True

    query = f"""
        INSERT INTO link (code_pk, url, link_type_pk, created_at)
        VALUES ({code_pk}, '{escaped_url}', {link_type_pk}, NOW())
    """

    try:
        mysql_query(query)
        return True
    except subprocess.CalledProcessError as e:
        print(f"    ERROR: Failed to create link: {e}")
        return False


def migrate_links(dry_run: bool = False, limit: Optional[int] = None):
    """Main migration function."""

    print("=" * 60)
    print("PHP Link Migration Script")
    print("=" * 60)
    print()

    # Load link types
    link_type_map = load_link_types()

    # Verify all required link types exist
    for field_name, link_type_short_name in FIELD_TO_LINK_TYPE.items():
        if link_type_short_name not in link_type_map:
            print(f"ERROR: Link type '{link_type_short_name}' not found in database!")
            print(f"Required for field: {field_name}")
            sys.exit(1)

    print()

    # Get codes to process
    limit_clause = f"LIMIT {limit}" if limit else ""
    query = f"""
        SELECT pk, ascl_id, site_list, described_in, used_in, ref_list
        FROM codes
        {limit_clause}
    """

    print(f"Loading codes{' (limit: ' + str(limit) + ')' if limit else ''}...")
    codes = mysql_query_json(query)
    print(f"Processing {len(codes)} codes")
    print()

    if dry_run:
        print("*** DRY RUN MODE - No database changes will be made ***")
        print()

    # Statistics
    stats = {
        'codes_processed': 0,
        'links_created': 0,
        'skipped_empty': 0,
        'skipped_existing': 0,
        'errors': 0
    }

    # Process each code
    for i, code in enumerate(codes, 1):
        code_pk = int(code['pk'])
        ascl_id = code['ascl_id']

        print(f"[{i}/{len(codes)}] Processing {ascl_id} (pk={code_pk})")

        # Process each field
        for field_name, link_type_short_name in FIELD_TO_LINK_TYPE.items():
            serialized_data = code.get(field_name)

            if not serialized_data or serialized_data == 'NULL':
                continue

            # Unserialize PHP data
            urls = unserialize_php(serialized_data)

            if not urls:
                stats['skipped_empty'] += 1
                continue

            print(f"  {field_name}: Found {len(urls)} URL(s)")

            # Create link for each URL
            for url in urls:
                # Check if link already exists
                if link_exists(code_pk, url):
                    print(f"    SKIP (exists): {url[:80]}")
                    stats['skipped_existing'] += 1
                    continue

                # Create link
                link_type_pk = link_type_map[link_type_short_name]['pk']
                success = create_link(code_pk, url, link_type_pk, dry_run)

                if success:
                    if not dry_run:
                        print(f"    CREATED: {url[:80]}")
                    stats['links_created'] += 1
                else:
                    stats['errors'] += 1

        stats['codes_processed'] += 1

    # Print summary
    print()
    print("=" * 60)
    print("Migration Summary:")
    print("=" * 60)
    print(f"Codes processed:      {stats['codes_processed']}")
    print(f"Links created:        {stats['links_created']}")
    print(f"Skipped (empty):      {stats['skipped_empty']}")
    print(f"Skipped (existing):   {stats['skipped_existing']}")
    print(f"Errors:               {stats['errors']}")
    print("=" * 60)

    if dry_run:
        print()
        print("*** DRY RUN COMPLETE - No changes were made to the database ***")


def main():
    parser = argparse.ArgumentParser(description='Migrate PHP-serialized links to link table')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be migrated without making changes')
    parser.add_argument('--limit', type=int, metavar='N',
                       help='Process only N codes (for testing)')

    args = parser.parse_args()

    try:
        migrate_links(dry_run=args.dry_run, limit=args.limit)
    except KeyboardInterrupt:
        print("\n\nMigration interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
