#!/usr/bin/env python3
"""
Migrate PHP-serialized fields to the link table.

This script is called by copy_ascl_database.sh as part of the v3→v4 migration.
It reads PHP-serialized arrays from codes.site_list, codes.ref_list,
codes.described_in, codes.used_in and inserts them into the link table
with appropriate link_type_pk values.

It also migrates see_also to a new code_see_also junction table.

Usage:
    python migrate_serialized_to_links.py DATABASE [--dry-run]
"""

import sys
import os
import re

try:
    import phpserialize
except ImportError:
    print("ERROR: phpserialize module not found. Install with: pip install phpserialize")
    sys.exit(1)

try:
    import MySQLdb
except ImportError:
    print("ERROR: MySQLdb module not found. Install with: pip install mysqlclient")
    sys.exit(1)


def get_mysql_connection(database):
    """Create MySQL connection using credentials from ~/.my.cnf"""
    my_cnf = os.path.expanduser("~/.my.cnf")
    creds = {}
    in_section = False

    with open(my_cnf, 'r') as f:
        for line in f:
            line = line.strip()
            if line == '[client_ascl_root]':
                in_section = True
                continue
            if line.startswith('[') and in_section:
                break
            if in_section and '=' in line:
                key, value = line.split('=', 1)
                creds[key.strip()] = value.strip()

    return MySQLdb.connect(
        host=creds.get('host', '127.0.0.1'),
        port=int(creds.get('port', 3307)),
        user=creds.get('user', 'root'),
        passwd=creds.get('password', ''),
        db=database,
        charset='utf8mb4'
    )


def unserialize_php(data):
    """Safely unserialize PHP data, returning empty list on failure."""
    if not data:
        return []
    try:
        result = phpserialize.loads(data.encode('utf-8') if isinstance(data, str) else data)
        if isinstance(result, dict):
            return [v.decode('utf-8') if isinstance(v, bytes) else str(v)
                    for v in result.values() if v]
        return []
    except Exception:
        return []


def get_or_create_link_types(cursor):
    """Ensure link_type table has the required types, return pk mapping."""
    required_types = [
        ('code-site', 'Code Site'),
        ('reference', 'Reference'),
        ('described-in', 'Described In'),
        ('used-in', 'Used In'),
    ]

    type_pks = {}

    for short_name, display_name in required_types:
        cursor.execute("SELECT pk FROM link_type WHERE short_name = %s", (short_name,))
        row = cursor.fetchone()
        if row:
            type_pks[short_name] = row[0]
        else:
            cursor.execute(
                "INSERT INTO link_type (short_name, name) VALUES (%s, %s)",
                (short_name, display_name)
            )
            type_pks[short_name] = cursor.lastrowid
            print(f"  Created link_type: {short_name} (pk={type_pks[short_name]})")

    return type_pks


def create_see_also_table(cursor):
    """Create the code_see_also junction table if it doesn't exist."""
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS code_see_also (
            pk INT AUTO_INCREMENT PRIMARY KEY,
            code_pk INT NOT NULL,
            related_code_pk INT NOT NULL COMMENT 'FK to related code',
            display_order INT DEFAULT 0,
            INDEX idx_code_pk (code_pk),
            INDEX idx_related_code_pk (related_code_pk),
            FOREIGN KEY (code_pk) REFERENCES codes(pk) ON DELETE CASCADE,
            FOREIGN KEY (related_code_pk) REFERENCES codes(pk) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """)
    print("  Ensured code_see_also table exists")


def migrate_field_to_links(cursor, field_name, link_type_pk, dry_run=False):
    """Migrate a PHP-serialized field to the link table, preserving order.

    The link-checker rows (link_type_pk IS NULL) from v3 links_new have already
    been deleted by rename_pk_columns.sql. Only EMAC rows remain. This function
    inserts new rows from the PHP-serialized codes fields.
    """
    cursor.execute(f"""
        SELECT pk, {field_name} FROM codes
        WHERE {field_name} IS NOT NULL AND {field_name} != ''
    """)
    rows = cursor.fetchall()

    inserted = 0
    for code_pk, serialized in rows:
        urls = unserialize_php(serialized)
        for display_order, url in enumerate(urls):
            url = url.strip() if url else ''
            if not url:
                continue
            if dry_run:
                print(f"    [DRY] code_pk={code_pk}, order={display_order}, url={url[:60]}...")
            else:
                cursor.execute("""
                    INSERT IGNORE INTO link (code_pk, url, link_type_pk, display_order)
                    VALUES (%s, %s, %s, %s)
                """, (code_pk, url, link_type_pk, display_order))
                inserted += cursor.rowcount

    return len(rows), inserted


def migrate_see_also(cursor, dry_run=False):
    """Migrate see_also field to code_see_also table."""
    cursor.execute("""
        SELECT pk, see_also FROM codes
        WHERE see_also IS NOT NULL AND see_also != ''
    """)
    rows = cursor.fetchall()

    # Build ascl_id → pk lookup
    cursor.execute("SELECT pk, ascl_id FROM codes")
    ascl_lookup = {r[1]: r[0] for r in cursor.fetchall()}

    migrated = 0
    skipped = 0

    for code_pk, see_also_str in rows:
        items = re.split(r'[;\s]+', see_also_str)
        for order, ascl_id in enumerate(items):
            ascl_id = ascl_id.strip()
            if not ascl_id:
                continue

            related_pk = ascl_lookup.get(ascl_id)
            if not related_pk:
                skipped += 1
                continue  # Skip unresolved references

            if dry_run:
                print(f"    [DRY] code_pk={code_pk} → {ascl_id}")
            else:
                cursor.execute("""
                    INSERT INTO code_see_also (code_pk, related_code_pk, display_order)
                    VALUES (%s, %s, %s)
                """, (code_pk, related_pk, order))
                migrated += 1

    return len(rows), migrated, skipped


def main():
    if len(sys.argv) < 2:
        print("Usage: python migrate_serialized_to_links.py DATABASE [--dry-run]")
        sys.exit(1)

    database = sys.argv[1]
    dry_run = '--dry-run' in sys.argv

    print(f"{'[DRY RUN] ' if dry_run else ''}Migrating serialized fields in {database}")

    conn = get_mysql_connection(database)
    cursor = conn.cursor()

    # Get/create link types
    print("\n1. Ensuring link_type entries exist...")
    type_pks = get_or_create_link_types(cursor)
    print(f"   Link types: {type_pks}")

    # Create see_also table
    print("\n2. Creating code_see_also table...")
    create_see_also_table(cursor)

    # Migrate each field
    field_mapping = [
        ('site_list', 'code-site'),
        ('ref_list', 'reference'),
        ('described_in', 'described-in'),
        ('used_in', 'used-in'),
    ]

    print("\n3. Migrating PHP-serialized fields to link table...")
    for field, link_type in field_mapping:
        print(f"\n   {field} → link (type={link_type}):")
        codes_count, inserted = migrate_field_to_links(
            cursor, field, type_pks[link_type], dry_run
        )
        print(f"   Processed {codes_count} codes, inserted {inserted} new links")

    # Migrate see_also
    print("\n4. Migrating see_also to code_see_also...")
    codes_count, links_count, skipped = migrate_see_also(cursor, dry_run)
    print(f"   Processed {codes_count} codes, inserted {links_count} relationships")
    if skipped:
        print(f"   (skipped {skipped} references to non-existent codes)")

    if not dry_run:
        conn.commit()
        print("\n✓ Migration completed successfully!")
    else:
        print("\n[DRY RUN] No changes made. Run without --dry-run to apply.")

    cursor.close()
    conn.close()


if __name__ == '__main__':
    main()
