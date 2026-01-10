#!/usr/bin/env python3
"""
Check links in the ASCL database and update their status.

This script verifies that URLs in the link table are reachable and updates:
- is_working: 1 if link works, 0 if broken
- last_working: timestamp of last successful check
- message: error messages or HTTP status codes

Usage:
    python3 check_links.py [--limit N] [--code ASCL_ID] [--type TYPE] [--recheck-working] [--threads N]

Options:
    --limit N             Check only N links (for testing)
    --code ASCL_ID        Check links only for specific code (e.g., 0003.001)
    --type TYPE           Check only links of specific type (code-site, described-in, used-in, reference)
    --recheck-working     Also recheck links that are currently marked as working
    --threads N           Number of concurrent threads (default: 5, max: 20)
    --timeout N           HTTP request timeout in seconds (default: 10)
    --delay N             Delay between requests in seconds (default: 0.5)
"""

import sys
import argparse
import logging
import time
from datetime import datetime
from typing import Optional, List, Tuple
from urllib.parse import urlparse
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add parent directory to path to import ascl_core
sys.path.insert(0, '/home/demitri/repositories/ASCL/alt_ascl')

from ascl_core.database.connections.Trillian2DBConnection import db, Session
from sqlalchemy import text

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class LinkChecker:
    """Checks URLs in the ASCL database and updates their status."""

    def __init__(self, timeout: int = 10, delay: float = 0.5, threads: int = 5):
        self.timeout = timeout
        self.delay = delay
        self.threads = min(threads, 20)  # Cap at 20 threads
        self.session = Session()
        self.stats = {
            'total': 0,
            'working': 0,
            'broken': 0,
            'errors': 0,
            'skipped': 0
        }

        # Configure requests session with reasonable defaults
        self.http_session = requests.Session()
        self.http_session.headers.update({
            'User-Agent': 'ASCL Link Checker (ascl.net contact@ascl.net)'
        })

    def get_links_to_check(self,
                          limit: Optional[int] = None,
                          code_id: Optional[str] = None,
                          link_type: Optional[str] = None,
                          recheck_working: bool = False) -> List[Tuple]:
        """
        Fetch links from database that need checking.

        Args:
            limit: Maximum number of links to check
            code_id: Only check links for this ASCL ID
            link_type: Only check links of this type (short_name)
            recheck_working: If False, skip links where is_working=1

        Returns:
            List of tuples: (link_id, url, code_pk, link_type_pk)
        """
        query = """
            SELECT l.id, l.url, l.code_pk, l.link_type_pk, l.is_working, l.last_working
            FROM link l
        """

        conditions = []
        params = {}

        if code_id:
            query += " JOIN codes c ON l.code_pk = c.pk"
            conditions.append("c.ascl_id = :code_id")
            params['code_id'] = code_id

        if link_type:
            query += " JOIN link_type lt ON l.link_type_pk = lt.pk"
            conditions.append("lt.short_name = :link_type")
            params['link_type'] = link_type

        if not recheck_working:
            conditions.append("(l.is_working = 0 OR l.is_working IS NULL OR l.last_working IS NULL)")

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY l.last_working IS NULL DESC, l.last_working ASC"

        if limit:
            query += f" LIMIT {limit}"

        result = self.session.execute(text(query), params).fetchall()
        logger.info(f"Found {len(result)} links to check")
        return result

    def check_url(self, url: str) -> Tuple[bool, str]:
        """
        Check if a URL is reachable.

        Args:
            url: The URL to check

        Returns:
            Tuple of (is_working, message)
        """
        try:
            # Add delay to avoid overwhelming servers
            time.sleep(self.delay)

            response = self.http_session.get(
                url,
                timeout=self.timeout,
                allow_redirects=True,
                verify=True  # Verify SSL certificates
            )

            if response.status_code == 200:
                return (True, f"HTTP {response.status_code} OK")
            elif response.status_code in [301, 302, 303, 307, 308]:
                # Redirects are okay if they eventually succeed
                return (True, f"HTTP {response.status_code} Redirect to {response.url[:100]}")
            elif response.status_code == 404:
                return (False, f"HTTP 404 Not Found")
            elif response.status_code >= 400:
                return (False, f"HTTP {response.status_code}")
            else:
                # Other status codes (e.g., 201, 204)
                return (True, f"HTTP {response.status_code}")

        except requests.exceptions.SSLError as e:
            return (False, f"SSL Error: {str(e)[:200]}")
        except requests.exceptions.ConnectionError as e:
            return (False, f"Connection Error: {str(e)[:200]}")
        except requests.exceptions.Timeout:
            return (False, f"Timeout after {self.timeout}s")
        except requests.exceptions.TooManyRedirects:
            return (False, "Too many redirects")
        except Exception as e:
            return (False, f"Error: {type(e).__name__}: {str(e)[:200]}")

    def update_link_status(self, link_id: int, is_working: bool, message: str):
        """
        Update link status in database.

        Args:
            link_id: The link ID to update
            is_working: Whether the link is working
            message: Status message
        """
        try:
            now = datetime.now()

            if is_working:
                # Update last_working timestamp only if link is working
                query = text("""
                    UPDATE link
                    SET is_working = :is_working,
                        last_working = :last_working,
                        message = :message
                    WHERE id = :link_id
                """)
                self.session.execute(query, {
                    'is_working': 1,
                    'last_working': now,
                    'message': message,
                    'link_id': link_id
                })
            else:
                # Don't update last_working for broken links
                query = text("""
                    UPDATE link
                    SET is_working = :is_working,
                        message = :message
                    WHERE id = :link_id
                """)
                self.session.execute(query, {
                    'is_working': 0,
                    'message': message,
                    'link_id': link_id
                })

            self.session.commit()

        except Exception as e:
            logger.error(f"Failed to update link {link_id}: {e}")
            self.session.rollback()
            self.stats['errors'] += 1

    def check_link(self, link_data: Tuple) -> None:
        """
        Check a single link and update its status.

        Args:
            link_data: Tuple of (link_id, url, code_pk, link_type_pk, is_working, last_working)
        """
        link_id, url, code_pk, link_type_pk, current_status, last_working = link_data

        self.stats['total'] += 1

        logger.info(f"[{self.stats['total']}] Checking: {url[:80]}")

        is_working, message = self.check_url(url)

        if is_working:
            self.stats['working'] += 1
            logger.info(f"  ✓ Working: {message}")
        else:
            self.stats['broken'] += 1
            logger.warning(f"  ✗ Broken: {message}")

        self.update_link_status(link_id, is_working, message)

    def run(self,
            limit: Optional[int] = None,
            code_id: Optional[str] = None,
            link_type: Optional[str] = None,
            recheck_working: bool = False):
        """
        Run the link checker.

        Args:
            limit: Maximum number of links to check
            code_id: Only check links for this ASCL ID
            link_type: Only check links of this type
            recheck_working: If False, skip links where is_working=1
        """
        logger.info("=" * 80)
        logger.info("ASCL Link Checker Starting")
        logger.info("=" * 80)
        logger.info(f"Settings:")
        logger.info(f"  Threads: {self.threads}")
        logger.info(f"  Timeout: {self.timeout}s")
        logger.info(f"  Delay: {self.delay}s")
        logger.info(f"  Limit: {limit or 'None'}")
        logger.info(f"  Code: {code_id or 'All'}")
        logger.info(f"  Type: {link_type or 'All'}")
        logger.info(f"  Recheck working: {recheck_working}")
        logger.info("=" * 80)

        start_time = time.time()

        # Get links to check
        links = self.get_links_to_check(limit, code_id, link_type, recheck_working)

        if not links:
            logger.info("No links to check!")
            return

        # Check links using thread pool
        with ThreadPoolExecutor(max_workers=self.threads) as executor:
            futures = [executor.submit(self.check_link, link) for link in links]

            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"Thread error: {e}")
                    self.stats['errors'] += 1

        # Print summary
        elapsed = time.time() - start_time
        logger.info("=" * 80)
        logger.info("Link Checking Complete!")
        logger.info("=" * 80)
        logger.info(f"Summary:")
        logger.info(f"  Total checked: {self.stats['total']}")
        logger.info(f"  Working: {self.stats['working']} ({self.stats['working']/self.stats['total']*100:.1f}%)")
        logger.info(f"  Broken: {self.stats['broken']} ({self.stats['broken']/self.stats['total']*100:.1f}%)")
        logger.info(f"  Errors: {self.stats['errors']}")
        logger.info(f"  Time elapsed: {elapsed:.1f}s")
        logger.info(f"  Average: {elapsed/self.stats['total']:.2f}s per link")
        logger.info("=" * 80)


def main():
    parser = argparse.ArgumentParser(description='Check ASCL database links')
    parser.add_argument('--limit', type=int, help='Check only N links')
    parser.add_argument('--code', type=str, help='Check links only for specific ASCL ID')
    parser.add_argument('--type', type=str, choices=['code-site', 'described-in', 'used-in', 'reference'],
                       help='Check only links of specific type')
    parser.add_argument('--recheck-working', action='store_true',
                       help='Also recheck links that are currently marked as working')
    parser.add_argument('--threads', type=int, default=5, help='Number of concurrent threads (default: 5, max: 20)')
    parser.add_argument('--timeout', type=int, default=10, help='HTTP request timeout in seconds (default: 10)')
    parser.add_argument('--delay', type=float, default=0.5, help='Delay between requests in seconds (default: 0.5)')

    args = parser.parse_args()

    checker = LinkChecker(timeout=args.timeout, delay=args.delay, threads=args.threads)
    checker.run(
        limit=args.limit,
        code_id=args.code,
        link_type=args.type,
        recheck_working=args.recheck_working
    )


if __name__ == '__main__':
    main()
