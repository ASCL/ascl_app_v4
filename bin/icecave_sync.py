#!/usr/bin/env python3
"""
icecave_sync.py — Daily sync of git mirrors in the icecave.

For each code_archive row with archive_type='git' and status='active',
runs `git remote update` on the bare mirror and records whether new
content was fetched.

Intended to be run daily via cron.

Usage:
    python3 icecave_sync.py [--database ascl_db_v4]
"""

import argparse
import configparser
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import MySQLdb

DEFAULT_ROOT = '/data/ascl_icecave'


def get_mysql_connection(database):
    """Connect using ~/.my.cnf [client_ascl_root] section."""
    cnf = configparser.ConfigParser()
    cnf.read(str(Path.home() / '.my.cnf'))
    section = 'client_ascl_root'
    return MySQLdb.connect(
        host=cnf.get(section, 'host', fallback='127.0.0.1'),
        port=int(cnf.get(section, 'port', fallback='3307')),
        user=cnf.get(section, 'user'),
        passwd=cnf.get(section, 'password'),
        db=database,
        charset='utf8mb4',
    )


def get_dir_size(path):
    """Get total size of a directory in bytes."""
    total = 0
    for dirpath, dirnames, filenames in os.walk(path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            if os.path.isfile(fp):
                total += os.path.getsize(fp)
    return total


def sync_mirror(repo_path):
    """Run git remote update on a bare mirror. Returns (had_updates, error_msg)."""
    try:
        result = subprocess.run(
            ['git', 'remote', 'update'],
            cwd=str(repo_path),
            capture_output=True, text=True, timeout=300
        )
        if result.returncode != 0:
            return None, result.stderr.strip()[:500]

        # If stderr contains "Fetching origin" + branch info, there were updates
        # If it just says "Fetching origin" with no branch lines, no updates
        stderr = result.stderr.strip()
        had_updates = '->' in stderr  # e.g. "  abc123..def456  main -> main"
        return had_updates, None
    except subprocess.TimeoutExpired:
        return None, 'sync timed out after 300s'
    except Exception as e:
        return None, str(e)[:500]


def main():
    parser = argparse.ArgumentParser(description='Daily sync of icecave git mirrors')
    parser.add_argument('--root', default=DEFAULT_ROOT, help='Icecave root directory')
    parser.add_argument('--database', default='ascl_db_v4', help='Database name')
    parser.add_argument('--retry-errors', action='store_true',
                        help='Also retry repos with status=error')
    args = parser.parse_args()

    root = Path(args.root)
    codes_dir = root / 'codes'
    logs_dir = root / 'logs'
    logs_dir.mkdir(parents=True, exist_ok=True)

    conn = get_mysql_connection(args.database)
    cursor = conn.cursor()

    # Get active git repos (and optionally errored ones)
    statuses = "('active')"
    if args.retry_errors:
        statuses = "('active', 'error')"

    cursor.execute(f"""
        SELECT ca.pk, ca.dir_name, c.ascl_id
        FROM code_archive ca
        JOIN codes c ON c.pk = ca.code_pk
        WHERE ca.archive_type = 'git' AND ca.status IN {statuses}
        ORDER BY c.ascl_id
    """)
    repos = cursor.fetchall()
    print(f"Syncing {len(repos)} git mirrors")

    log_file = logs_dir / f"sync_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    updated = 0
    unchanged = 0
    errors = 0

    with open(log_file, 'w') as log:
        for i, (pk, dir_name, ascl_id) in enumerate(repos, 1):
            repo_path = codes_dir / dir_name
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            if not repo_path.exists():
                msg = f"directory missing: {repo_path}"
                cursor.execute("""
                    UPDATE code_archive
                    SET status='error', last_checked=%s, error_message=%s
                    WHERE pk=%s
                """, (now, msg, pk))
                log.write(f"{now} {ascl_id} ERROR: {msg}\n")
                errors += 1
                conn.commit()
                continue

            had_updates, error = sync_mirror(repo_path)

            if error is not None:
                cursor.execute("""
                    UPDATE code_archive
                    SET status='error', last_checked=%s, error_message=%s
                    WHERE pk=%s
                """, (now, error, pk))
                log.write(f"{now} {ascl_id} ERROR: {error}\n")
                errors += 1
            elif had_updates:
                size = get_dir_size(repo_path)
                cursor.execute("""
                    UPDATE code_archive
                    SET status='active', last_checked=%s, last_updated=%s,
                        size_bytes=%s, error_message=NULL
                    WHERE pk=%s
                """, (now, now, size, pk))
                log.write(f"{now} {ascl_id} UPDATED\n")
                updated += 1
            else:
                cursor.execute("""
                    UPDATE code_archive
                    SET last_checked=%s, error_message=NULL
                    WHERE pk=%s
                """, (now, pk))
                log.write(f"{now} {ascl_id} unchanged\n")
                unchanged += 1

            conn.commit()

    print(f"\nResults: {updated} updated, {unchanged} unchanged, {errors} errors")
    print(f"Log: {log_file}")

    cursor.close()
    conn.close()


if __name__ == '__main__':
    main()
