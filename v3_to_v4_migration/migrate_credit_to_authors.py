#!/usr/bin/env python3
"""
Migrate codes.credit to the author and code_to_author tables.

Splits the semicolon-delimited credit field into individual author rows,
uses the nameparser library to parse each name into given/middle/family,
and creates code_to_author join records preserving display order.

Prerequisites:
    - Run create_author_table.sql first to create the tables.
    - pip install nameparser mysqlclient

Usage:
    python migrate_credit_to_authors.py DATABASE [--dry-run]
"""

import sys
import os

try:
    from nameparser import HumanName
except ImportError:
    print("ERROR: nameparser module not found. Install with: pip install nameparser")
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


def migrate_credit_to_authors(cursor, dry_run=False):
    """Parse codes.credit and populate author + code_to_author tables."""
    cursor.execute("""
        SELECT pk, credit FROM codes
        WHERE credit IS NOT NULL AND credit != ''
    """)
    rows = cursor.fetchall()

    # Cache: name string → author.pk (avoid duplicate author rows)
    author_cache = {}

    codes_processed = 0
    authors_created = 0
    links_created = 0

    for code_pk, credit in rows:
        names = [n.strip() for n in credit.split(';') if n.strip()]
        codes_processed += 1

        for display_order, name in enumerate(names):
            # Skip entries that are too long to be a single author name
            if len(name) > 512:
                print(f"  WARNING: Skipping oversized name ({len(name)} chars) "
                      f"for code pk={code_pk}: \"{name[:80]}...\"")
                continue

            # Look up or create author row
            if name in author_cache:
                author_pk = author_cache[name]
            else:
                parsed = HumanName(name)
                given = parsed.first or None
                middle = parsed.middle or None
                family = parsed.last or None

                if dry_run:
                    # Use a placeholder pk for dry run
                    author_pk = len(author_cache) + 1
                    print(f"    [DRY] author: \"{name}\" → "
                          f"given=\"{given}\", middle=\"{middle}\", family=\"{family}\"")
                else:
                    cursor.execute("""
                        INSERT INTO author (name, given, middle, family)
                        VALUES (%s, %s, %s, %s)
                    """, (name, given, middle, family))
                    author_pk = cursor.lastrowid

                author_cache[name] = author_pk
                authors_created += 1

            # Create code_to_author join record
            if dry_run:
                pass  # already printed above
            else:
                cursor.execute("""
                    INSERT IGNORE INTO code_to_author (code_pk, author_pk, display_order)
                    VALUES (%s, %s, %s)
                """, (code_pk, author_pk, display_order))

            links_created += 1

    return codes_processed, authors_created, links_created


def main():
    if len(sys.argv) < 2:
        print("Usage: python migrate_credit_to_authors.py DATABASE [--dry-run]")
        sys.exit(1)

    database = sys.argv[1]
    dry_run = '--dry-run' in sys.argv

    print(f"{'[DRY RUN] ' if dry_run else ''}Migrating codes.credit → author table in {database}")

    conn = get_mysql_connection(database)
    cursor = conn.cursor()

    print("\nParsing credit field and populating author + code_to_author tables...")
    codes_count, authors_count, links_count = migrate_credit_to_authors(cursor, dry_run)

    print(f"\n   Processed {codes_count} codes")
    print(f"   Created {authors_count} unique authors")
    print(f"   Created {links_count} code↔author links")

    if not dry_run:
        conn.commit()
        print("\n✓ Migration completed successfully!")
    else:
        print("\n[DRY RUN] No changes made. Run without --dry-run to apply.")

    cursor.close()
    conn.close()


if __name__ == '__main__':
    main()
