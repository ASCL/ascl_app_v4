#!/usr/bin/env python3
"""
icecave_sync.py — Daily sync of git mirrors in the icecave.

Syncs are phased over 7 days: each repo is assigned a day based on
its primary key (pk % 7). Running daily via cron, this means each
repo is synced once per week, with ~420 repos per day instead of ~3000.

Uses the icecave app's SQLAlchemy database (SQLite or PostgreSQL).

Usage:
    python3 icecave_sync.py                   # sync today's batch
    python3 icecave_sync.py --all             # sync everything (2-4 hours)
    python3 icecave_sync.py --day 3           # sync day 3's batch
    python3 icecave_sync.py --code 1010.083   # sync one code
    python3 icecave_sync.py --errors          # retry only errored codes
    python3 icecave_sync.py --config production.cfg

Cron example (run daily at 02:00):
    0 2 * * * cd /path/to/icecave && python3 icecave_sync.py >> /data/ascl_icecave/logs/sync.log 2>&1
"""

import argparse
import os
import subprocess
import sys
import time
from datetime import datetime, timezone

# Add the icecave package to the path
sys.path.insert(0, os.path.dirname(__file__))

from icecave import create_app
from icecave.model.database import Database
from icecave.model.tables import CodeArchive, SyncRun, SyncEvent


def get_dir_size(path):
    """Get total size of a directory in bytes."""
    total = 0
    for dirpath, _, filenames in os.walk(path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            if os.path.isfile(fp):
                total += os.path.getsize(fp)
    return total


def sync_repo(repo_path, timeout):
    """Run git remote update. Returns (had_updates, error_msg).
    had_updates is None on error."""
    if os.path.islink(repo_path):
        repo_path = os.path.realpath(repo_path)

    try:
        result = subprocess.run(
            ['git', 'remote', 'update'],
            cwd=repo_path, capture_output=True, text=True, timeout=timeout,
        )
        if result.returncode != 0:
            return None, result.stderr.strip()[:500]
        had_updates = '->' in result.stderr
        return had_updates, None
    except subprocess.TimeoutExpired:
        return None, f'timed out after {timeout}s'
    except Exception as e:
        return None, str(e)[:500]


def main():
    parser = argparse.ArgumentParser(description='Icecave daily sync')
    parser.add_argument('--all', action='store_true',
                        help='Sync all repos (ignore day-based phasing)')
    parser.add_argument('--day', type=int, default=None,
                        help='Sync a specific day (0-6). Default: today')
    parser.add_argument('--code', type=str, default=None,
                        help='Sync a single code by ASCL ID')
    parser.add_argument('--errors', action='store_true',
                        help='Retry only errored repos')
    parser.add_argument('--cycle', type=int, default=14,
                        help='Number of days in the sync cycle (default: 14)')
    parser.add_argument('--config', default=None,
                        help='Icecave config file name')
    args = parser.parse_args()

    app = create_app(config_name=args.config)

    with app.app_context():
        db = Database()
        session = db.session()
        root = app.config['ARCHIVE_ROOT']
        timeout = app.config.get('SYNC_TIMEOUT_SECONDS', 600)
        pause = app.config.get('SYNC_PAUSE_SECONDS', 0.5)

        # Build query
        query = session.query(CodeArchive).filter(
            CodeArchive.archive_type == 'git',
        )

        if args.code:
            query = query.filter(CodeArchive.ascl_id == args.code)
        elif args.errors:
            query = query.filter(CodeArchive.status == 'error')
        else:
            query = query.filter(CodeArchive.status.in_(['active', 'error']))
            if not args.all:
                sync_day = args.day if args.day is not None else datetime.now().weekday()
                query = query.filter(CodeArchive.pk % args.cycle == sync_day % args.cycle)

        codes = query.order_by(CodeArchive.ascl_id).all()

        if not codes:
            print("No repos to sync.")
            return

        # Determine trigger type
        if args.code:
            trigger = 'manual'
        else:
            trigger = 'cron'

        # Create sync run record
        run = SyncRun(
            started_at=datetime.now(timezone.utc),
            trigger=trigger,
            total_repos=len(codes),
        )
        session.add(run)
        session.flush()

        day_label = f"day {args.day if args.day is not None else datetime.now().weekday()}/{args.cycle}"
        if args.all:
            day_label = "ALL"
        elif args.code:
            day_label = args.code
        elif args.errors:
            day_label = "errors only"

        print(f"[{datetime.now().isoformat()}] Syncing {len(codes)} repos ({day_label})")

        updated = 0
        unchanged = 0
        errors = 0

        for i, code in enumerate(codes, 1):
            repo_path = os.path.join(root, 'codes', code.dir_name)
            now = datetime.now(timezone.utc)

            if not os.path.exists(repo_path):
                msg = f'directory missing: {code.dir_name}'
                code.status = 'error'
                code.last_checked = now
                code.error_message = msg
                session.add(SyncEvent(
                    sync_run_pk=run.pk, code_archive_pk=code.pk,
                    result='error', error_message=msg,
                ))
                errors += 1
                session.commit()
                print(f"  [{i}/{len(codes)}] {code.ascl_id} ERROR: {msg}")
                continue

            had_updates, error = sync_repo(repo_path, timeout)

            if error is not None:
                code.status = 'error'
                code.last_checked = now
                code.error_message = error
                session.add(SyncEvent(
                    sync_run_pk=run.pk, code_archive_pk=code.pk,
                    result='error', error_message=error,
                ))
                errors += 1
                print(f"  [{i}/{len(codes)}] {code.ascl_id} ERROR: {error[:60]}")
            elif had_updates:
                size = get_dir_size(os.path.realpath(repo_path))
                code.status = 'active'
                code.last_checked = now
                code.last_updated = now
                code.size_bytes = size
                code.error_message = None
                session.add(SyncEvent(
                    sync_run_pk=run.pk, code_archive_pk=code.pk,
                    result='updated',
                ))
                updated += 1
                print(f"  [{i}/{len(codes)}] {code.ascl_id} UPDATED ({size / 1048576:.1f} MB)")
            else:
                code.status = 'active'
                code.last_checked = now
                code.error_message = None
                session.add(SyncEvent(
                    sync_run_pk=run.pk, code_archive_pk=code.pk,
                    result='unchanged',
                ))
                unchanged += 1

            session.commit()

            if pause and i < len(codes):
                time.sleep(pause)

        run.updated = updated
        run.unchanged = unchanged
        run.errors = errors
        run.finished_at = datetime.now(timezone.utc)
        session.commit()

        duration = (run.finished_at - run.started_at).total_seconds()
        print(f"[{datetime.now().isoformat()}] Done: {updated} updated, {unchanged} unchanged, {errors} errors ({duration:.0f}s)")


if __name__ == '__main__':
    main()
