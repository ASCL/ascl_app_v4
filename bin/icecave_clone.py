#!/usr/bin/env python3
"""
icecave_clone.py — Initial clone of git repos into the icecave.

Reads code_archive rows with archive_type='git' and status='pending',
clones each as a bare mirror, creates symlinks in by-id/, and updates
the database.

Usage:
    python3 icecave_clone.py [--limit 50] [--database ascl_db_v4]
"""

import argparse
import configparser
import json
import os
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

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


def resolve_github_org(url, short_name=None, title=None):
    """If URL points to a GitHub org (not a repo), find the best repo.

    Uses the GitHub API to list org repos sorted by stars, then picks
    the one whose name best matches the code's short_name, title, or
    org name. Returns the resolved URL, or the original URL if it
    already has a repo path or resolution fails.
    """
    parsed = urlparse(url)
    if parsed.hostname != 'github.com':
        return url

    path_parts = parsed.path.strip('/').split('/')
    if len(path_parts) != 1:
        # Already has owner/repo
        return url

    org = path_parts[0]
    api_url = f'https://api.github.com/orgs/{org}/repos?sort=stars&per_page=30'
    try:
        req = urllib.request.Request(api_url, headers={'Accept': 'application/vnd.github.v3+json'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            repos = json.loads(resp.read())
    except Exception:
        return url

    if not repos:
        return url

    def normalize(s):
        return s.lower().replace('-', '').replace('_', '').replace('.', '')

    # Build list of candidate names to match against (most specific first)
    candidates = []
    if short_name:
        candidates.append(normalize(short_name))
    if title:
        # Extract short name from "ShortName: description" pattern
        title_prefix = title.split(':')[0].strip()
        candidates.append(normalize(title_prefix))
    candidates.append(normalize(org))

    # Try exact match against each candidate
    for candidate in candidates:
        for repo in repos:
            if normalize(repo['name']) == candidate:
                return f"https://github.com/{org}/{repo['name']}"

    # Try substring match (repo name contains candidate or vice versa)
    for candidate in candidates:
        for repo in repos:
            repo_norm = normalize(repo['name'])
            if candidate in repo_norm or repo_norm in candidate:
                return f"https://github.com/{org}/{repo['name']}"

    # Fallback: most-starred repo
    return f"https://github.com/{org}/{repos[0]['name']}"


def _to_clone_url(url):
    """Convert a human-readable git hosting URL to a clonable URL.

    GitHub handles both forms transparently, but most GitLab instances
    and other git hosts require the .git suffix for clone operations.
    The stored source_url stays as the human-readable page; this
    transformation is applied only at clone time.
    """
    url = url.rstrip('/')
    if not url.endswith('.git'):
        url += '.git'
    return url


def clone_mirror(source_url, dest_path):
    """Clone a git repo as a bare mirror. Returns (success, error_msg)."""
    clone_url = _to_clone_url(source_url)
    try:
        result = subprocess.run(
            ['git', 'clone', '--mirror', clone_url, str(dest_path)],
            capture_output=True, text=True, timeout=600
        )
        if result.returncode != 0:
            # If .git suffix failed and we added it, try the original URL
            if clone_url != source_url:
                result = subprocess.run(
                    ['git', 'clone', '--mirror', source_url, str(dest_path)],
                    capture_output=True, text=True, timeout=600
                )
            if result.returncode != 0:
                return False, result.stderr.strip()[:500]
        return True, None
    except subprocess.TimeoutExpired:
        return False, 'clone timed out after 600s'
    except Exception as e:
        return False, str(e)[:500]


def create_symlink(codes_dir, by_id_dir, dir_name):
    """Create the by-id symlink: {ascl_id}-{name} -> ../codes/{name}-{ascl_id}."""
    # dir_name is like "emcee-2010.001", we want symlink "2010.001-emcee"
    parts = dir_name.rsplit('-', 1)
    if len(parts) == 2:
        name_part, ascl_id = parts
        # Handle ASCL IDs that contain dots (all do: YYMM.NNN)
        # The dir_name format is {slug}-{ascl_id}, but ascl_id has a dot
        # Need to split more carefully
        pass

    # Extract ascl_id from dir_name (last 8 chars: NNNN.NNN)
    ascl_id = dir_name[-8:]  # e.g. "2010.001"
    name_part = dir_name[:-9]  # e.g. "emcee" (strip the "-NNNN.NNN")

    symlink_name = f"{ascl_id}-{name_part}"
    symlink_path = by_id_dir / symlink_name
    target = Path('..') / 'codes' / dir_name

    if symlink_path.exists() or symlink_path.is_symlink():
        symlink_path.unlink()
    symlink_path.symlink_to(target)


def main():
    parser = argparse.ArgumentParser(description='Clone git repos into the icecave')
    parser.add_argument('--root', default=DEFAULT_ROOT, help='Icecave root directory')
    parser.add_argument('--database', default='ascl_db_v4', help='Database name')
    parser.add_argument('--limit', type=int, default=0, help='Max repos to clone (0=all)')
    parser.add_argument('--skip-errors', action='store_true',
                        help='Skip repos with status=error (default: retry them)')
    parser.add_argument('--dry-run', action='store_true', help='Print actions without cloning')
    args = parser.parse_args()

    root = Path(args.root)
    codes_dir = root / 'codes'
    by_id_dir = root / 'by-id'
    logs_dir = root / 'logs'

    shared_dir = root / 'shared'

    # Create directories
    for d in [codes_dir, by_id_dir, logs_dir, shared_dir]:
        d.mkdir(parents=True, exist_ok=True)

    conn = get_mysql_connection(args.database)
    cursor = conn.cursor()

    # Get pending and errored git repos (skip errors only if explicitly asked)
    statuses = "('pending')" if args.skip_errors else "('pending', 'error')"

    cursor.execute(f"""
        SELECT ca.pk, ca.code_pk, ca.source_url, ca.dir_name, c.ascl_id,
               c.short_name, c.title
        FROM code_archive ca
        JOIN codes c ON c.pk = ca.code_pk
        WHERE ca.archive_type = 'git' AND ca.status IN {statuses}
        ORDER BY c.ascl_id
    """)
    repos = cursor.fetchall()

    if args.limit:
        repos = repos[:args.limit]

    print(f"Found {len(repos)} pending git repos to clone")

    if args.dry_run:
        for pk, code_pk, url, dir_name, ascl_id, short_name, title in repos[:10]:
            print(f"  Would clone: {url} -> codes/{dir_name}")
        return

    # Build map of source_url -> already-cloned directory for deduplication.
    # Check both active clones in DB and existing shared/ directories.
    cursor.execute("""
        SELECT source_url, dir_name FROM code_archive
        WHERE archive_type = 'git' AND status = 'active'
    """)
    url_to_existing = {}
    for existing_url, existing_dir in cursor.fetchall():
        if existing_url not in url_to_existing:
            url_to_existing[existing_url] = existing_dir

    # Also index shared/ directories by name (owner-repo format)
    for shared_entry in shared_dir.iterdir():
        if shared_entry.is_dir():
            url_to_existing.setdefault(f'__shared__:{shared_entry.name}', str(shared_entry))

    # Pre-scan pending repos to identify URLs that appear multiple times
    url_counts = {}
    for pk, code_pk, url, dir_name, ascl_id, short_name, title in repos:
        url_counts[url] = url_counts.get(url, 0) + 1

    # Log file (single rolling log, appended to each run)
    log_file = logs_dir / 'clone.log'
    successes = 0
    failures = 0
    deduped = 0

    with open(log_file, 'a') as log:
        log.write(f"\n{'='*72}\n")
        log.write(f"Run started: {datetime.now().isoformat()}\n")
        log.write(f"Repos to process: {len(repos)}\n")
        log.write(f"{'='*72}\n")
        for i, (pk, code_pk, url, dir_name, ascl_id, short_name, title) in enumerate(repos, 1):
            dest = codes_dir / dir_name
            print(f"[{i}/{len(repos)}] {ascl_id} -> {dir_name} ... ", end='', flush=True)
            log.write(f"{datetime.now().isoformat()} {ascl_id} {url}\n")

            if dest.exists() or dest.is_symlink():
                # Already present (real dir or symlink) — update DB and skip
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute("""
                    UPDATE code_archive SET status='active', last_checked=%s
                    WHERE pk=%s AND status != 'active'
                """, (now, pk))
                conn.commit()
                print("exists, skipping")
                log.write(f"  SKIP: directory already exists\n")
                continue

            # Resolve GitHub org-only URLs to actual repos
            resolved_url = resolve_github_org(url, short_name=short_name, title=title)
            if resolved_url != url:
                print(f"(resolved: {resolved_url}) ", end='', flush=True)
                log.write(f"  RESOLVED: {url} -> {resolved_url}\n")
                # Update the source_url in the database
                cursor.execute("UPDATE code_archive SET source_url=%s WHERE pk=%s",
                               (resolved_url, pk))
                url = resolved_url

            # Deduplication: if this URL is already cloned, symlink via shared/
            is_shared = url in url_to_existing or url_counts.get(url, 0) > 1

            if url in url_to_existing:
                # Already cloned — just symlink
                existing_dir = url_to_existing[url]
                # Derive shared name from URL: "Owner-repo"
                shared_name = url.rstrip('/').split('/')[-2] + '-' + url.rstrip('/').split('/')[-1]
                shared_path = shared_dir / shared_name

                # Move existing clone to shared/ if not already there
                if not shared_path.exists():
                    existing_path = codes_dir / existing_dir
                    if existing_path.exists() and not existing_path.is_symlink():
                        existing_path.rename(shared_path)
                        # Replace original with symlink too
                        existing_path.symlink_to(Path('..') / 'shared' / shared_name)
                        log.write(f"  SHARED: moved {existing_dir} to shared/{shared_name}\n")

                # Create symlink for this code
                if dest.exists() or dest.is_symlink():
                    dest.unlink()
                dest.symlink_to(Path('..') / 'shared' / shared_name)

                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                size = get_dir_size(shared_path) if shared_path.exists() else 0
                cursor.execute("""
                    UPDATE code_archive
                    SET status='active', last_checked=%s, last_updated=%s, size_bytes=%s, error_message=NULL
                    WHERE pk=%s
                """, (now, now, size, pk))
                create_symlink(codes_dir, by_id_dir, dir_name)
                print(f"LINKED (shared/{shared_name})")
                log.write(f"  LINKED: -> shared/{shared_name}\n")
                deduped += 1
                conn.commit()
                continue

            # Clone the repo
            if is_shared:
                # First clone of a URL that will be shared — clone into shared/
                shared_name = url.rstrip('/').split('/')[-2] + '-' + url.rstrip('/').split('/')[-1]
                shared_path = shared_dir / shared_name
                success, error = clone_mirror(url, shared_path)
                if success:
                    # Symlink from codes/
                    dest.symlink_to(Path('..') / 'shared' / shared_name)
                    url_to_existing[url] = dir_name
            else:
                success, error = clone_mirror(url, dest)

            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            if success:
                actual_path = shared_path if is_shared else dest
                size = get_dir_size(actual_path)
                cursor.execute("""
                    UPDATE code_archive
                    SET status='active', last_checked=%s, last_updated=%s, size_bytes=%s, error_message=NULL
                    WHERE pk=%s
                """, (now, now, size, pk))
                create_symlink(codes_dir, by_id_dir, dir_name)
                label = f"OK ({size / 1024 / 1024:.1f} MB)"
                if is_shared:
                    label += f" [shared/{shared_name}]"
                print(label)
                log.write(f"  OK: {size} bytes\n")
                successes += 1
            else:
                cursor.execute("""
                    UPDATE code_archive
                    SET status='error', last_checked=%s, error_message=%s
                    WHERE pk=%s
                """, (now, error, pk))
                print(f"FAILED: {error[:80]}")
                log.write(f"  FAIL: {error}\n")
                failures += 1

            conn.commit()

            # Brief pause to avoid hammering git hosts
            time.sleep(0.5)

        log.write(f"\nRun finished: {datetime.now().isoformat()}\n")
        log.write(f"Results: {successes} cloned, {deduped} deduped, {failures} failed\n")

    print(f"\nDone: {successes} cloned, {deduped} deduped, {failures} failed")
    print(f"Log: {log_file}")


if __name__ == '__main__':
    main()
