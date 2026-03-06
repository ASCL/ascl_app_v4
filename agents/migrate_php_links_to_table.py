#!/usr/bin/env python3
"""
Migrate PHP-serialized link fields from codes table to link table.

This script unpacks PHP-serialized arrays from the following codes table columns:
- site_list → link_type 'Code Site' (code-site)
- described_in → link_type 'Described In' (described-in)
- used_in → link_type 'Used In' (used-in)
- ref_list → link_type 'Reference' (reference)

Each URL found in these fields will create a new row in the link table
with the appropriate link_type_pk.

Usage:
    python3 migrate_php_links_to_table.py [--dry-run] [--limit N]

Options:
    --dry-run    Show what would be migrated without making changes
    --limit N    Process only N codes (for testing)
"""

import sys
import argparse
from typing import List, Optional, Dict
import logging
from pathlib import Path

try:
    from ascl_core.database.connections.Trillian2DBConnection import db, Session
except ModuleNotFoundError:
    # Local-dev fallback when ascl_core is not installed.
    repo_root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(repo_root / "ascl_core" / "source"))
    from ascl_core.database.connections.Trillian2DBConnection import db, Session
from sqlalchemy import text

try:
    import phpserialize
except ImportError:
    print("ERROR: phpserialize library not found.")
    print("Install it with: pip install phpserialize")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class LinkMigrator:
    """Migrates PHP-serialized link data from codes table to link table."""

    # Map field names to link_type short_names
    FIELD_TO_LINK_TYPE = {
        'site_list': 'code-site',
        'described_in': 'described-in',
        'used_in': 'used-in',
        'ref_list': 'reference'
    }

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.session = Session()
        self.link_type_map = {}  # Cache for link_type pk lookups
        self.stats = {
            'codes_processed': 0,
            'links_created': 0,
            'errors': 0,
            'skipped_empty': 0,
            'skipped_existing': 0
        }

    def load_link_types(self):
        """Load link_type table and create lookup map."""
        logger.info("Loading link_type table...")
        result = self.session.execute(
            text("SELECT pk, short_name, label FROM link_type")
        )
        for row in result:
            self.link_type_map[row.short_name] = {
                'pk': row.pk,
                'label': row.label
            }
        logger.info(f"Loaded {len(self.link_type_map)} link types")

    def unserialize_php(self, serialized_data: Optional[str]) -> List[str]:
        """
        Unserialize PHP array data.

        Args:
            serialized_data: PHP-serialized string (e.g., 'a:1:{i:0;s:20:"http://example.com";}')

        Returns:
            List of URLs, or empty list if data is None/empty/invalid
        """
        if not serialized_data or serialized_data.strip() == '':
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
            logger.warning(f"Failed to unserialize data: {e}")
            logger.debug(f"Problematic data: {serialized_data[:100]}")
            return []

    def link_exists(self, code_pk: int, url: str) -> bool:
        """Check if a link already exists for this code and URL."""
        result = self.session.execute(
            text("SELECT COUNT(*) as count FROM link WHERE code_pk = :code_pk AND url = :url"),
            {'code_pk': code_pk, 'url': url}
        ).fetchone()
        return result.count > 0

    def create_link(self, code_pk: int, url: str, link_type_short_name: str):
        """
        Create a new link record.

        Args:
            code_pk: Primary key of the code
            url: URL to link to
            link_type_short_name: short_name from link_type table
        """
        if link_type_short_name not in self.link_type_map:
            logger.error(f"Unknown link type: {link_type_short_name}")
            self.stats['errors'] += 1
            return

        link_type_pk = self.link_type_map[link_type_short_name]['pk']

        # Check if link already exists
        if self.link_exists(code_pk, url):
            logger.debug(f"  Link already exists: {url}")
            self.stats['skipped_existing'] += 1
            return

        if self.dry_run:
            logger.info(f"  [DRY RUN] Would create link: {url} (type: {link_type_short_name})")
        else:
            try:
                self.session.execute(
                    text("""
                        INSERT INTO link (code_pk, url, link_type_pk, is_working)
                        VALUES (:code_pk, :url, :link_type_pk, 0)
                    """),
                    {
                        'code_pk': code_pk,
                        'url': url,
                        'link_type_pk': link_type_pk
                    }
                )
                logger.debug(f"  Created link: {url} (type: {link_type_short_name})")
                self.stats['links_created'] += 1
            except Exception as e:
                logger.error(f"  Failed to create link: {e}")
                logger.error(f"    code_pk={code_pk}, url={url}, type={link_type_short_name}")
                self.stats['errors'] += 1

    def process_code(self, code: Dict):
        """
        Process a single code record.

        Args:
            code: Dict with keys: pk, ascl_id, site_list, described_in, used_in, ref_list
        """
        logger.info(f"Processing code {code['ascl_id']} (pk={code['pk']})")

        links_found = 0

        # Process each PHP-serialized field
        for field_name, link_type_short_name in self.FIELD_TO_LINK_TYPE.items():
            serialized_data = code[field_name]

            if not serialized_data:
                continue

            urls = self.unserialize_php(serialized_data)

            if not urls:
                logger.debug(f"  {field_name}: No URLs found")
                continue

            logger.info(f"  {field_name}: Found {len(urls)} URL(s)")

            for url in urls:
                self.create_link(code['pk'], url, link_type_short_name)
                links_found += 1

        if links_found == 0:
            self.stats['skipped_empty'] += 1

        self.stats['codes_processed'] += 1

        # Commit every 100 codes
        if not self.dry_run and self.stats['codes_processed'] % 100 == 0:
            self.session.commit()
            logger.info(f"Committed {self.stats['codes_processed']} codes...")

    def migrate_all(self, limit: Optional[int] = None):
        """
        Migrate all PHP-serialized link fields.

        Args:
            limit: If set, process only this many codes (for testing)
        """
        try:
            self.load_link_types()

            # Query codes with PHP-serialized link fields
            query = """
                SELECT pk, ascl_id, site_list, described_in, used_in, ref_list
                FROM codes
                WHERE site_list IS NOT NULL
                   OR described_in IS NOT NULL
                   OR used_in IS NOT NULL
                   OR ref_list IS NOT NULL
                ORDER BY pk
            """

            if limit:
                query += f" LIMIT {limit}"
                logger.info(f"Processing up to {limit} codes (--limit specified)")

            result = self.session.execute(text(query))

            for row in result:
                code = {
                    'pk': row.pk,
                    'ascl_id': row.ascl_id,
                    'site_list': row.site_list,
                    'described_in': row.described_in,
                    'used_in': row.used_in,
                    'ref_list': row.ref_list
                }
                self.process_code(code)

            # Final commit
            if not self.dry_run:
                self.session.commit()
                logger.info("Final commit complete")

            self.print_summary()

        except Exception as e:
            logger.error(f"Migration failed: {e}")
            if not self.dry_run:
                self.session.rollback()
            raise
        finally:
            self.session.close()

    def print_summary(self):
        """Print migration summary statistics."""
        logger.info("=" * 60)
        logger.info("Migration Summary:")
        logger.info("=" * 60)
        logger.info(f"Codes processed:      {self.stats['codes_processed']}")
        logger.info(f"Links created:        {self.stats['links_created']}")
        logger.info(f"Skipped (empty):      {self.stats['skipped_empty']}")
        logger.info(f"Skipped (existing):   {self.stats['skipped_existing']}")
        logger.info(f"Errors:               {self.stats['errors']}")
        logger.info("=" * 60)

        if self.dry_run:
            logger.info("DRY RUN - No changes were made to the database")
        else:
            logger.info("Migration complete!")


def main():
    parser = argparse.ArgumentParser(
        description='Migrate PHP-serialized link fields to link table'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be migrated without making changes'
    )
    parser.add_argument(
        '--limit',
        type=int,
        help='Process only N codes (for testing)'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    migrator = LinkMigrator(dry_run=args.dry_run)
    migrator.migrate_all(limit=args.limit)


if __name__ == '__main__':
    main()
