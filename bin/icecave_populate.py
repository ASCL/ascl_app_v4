#!/usr/bin/env python3
"""
icecave_populate.py — Populate the code_archive table from existing link data.

Reads code-site links (link_type_pk=2) for all published codes, determines
the archive type (git, download, webonly), and inserts rows into code_archive.

Codes with no code-site link get status='missing'.

Usage:
    python3 icecave_populate.py [--database ascl_db_v4]
"""

import argparse
import configparser
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

import MySQLdb

# Domains whose URLs can be cloned with git
GIT_DOMAINS = {
    'github.com',
    'gitlab.com',
    'bitbucket.org',
    'gitee.com',
    'codeberg.org',
    # Self-hosted GitLab / Gitea instances used by ASCL codes
    'gitlab.mpcdf.mpg.de',
    'gitlab.in2p3.fr',
    'git.ligo.org',
    'www.ict.inaf.it',
    'gitlab.lam.fr',
    'gitlab.obspm.fr',
    'gitlab.gwdg.de',
    'git.ias.u-psud.fr',
    'git.ncsa.illinois.edu',
    'cosmo-gitlab.phys.ethz.ch',
    'git.astron.nl',
    'www.gitlab.erc-atmo.eu',
    'git.aquila-consortium.org',
    'gitlab.desy.de',
    'git.km3net.de',
    'gitlab.nublado.org',
    'gitlab.astro.rug.nl',
    'gitlab.oca.eu',
    'git.rwth-aachen.de',
    'gitlab.unige.ch',
    'git.maneage.org',
    'git.dias.ie',
    'gitlab.cosma.dur.ac.uk',
    'gitlab.irap.omp.eu',
    'gitlab1.mpifr-bonn.mpg.de',
    'git.ia2.inaf.it',
    'gitlab.aip.de',
}


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


def slugify(text):
    """Convert text to a filesystem-safe slug."""
    text = text.lower().strip()
    text = re.sub(r'[^a-z0-9\-_.]', '-', text)
    text = re.sub(r'-+', '-', text)
    return text.strip('-')


def normalize_git_url(url):
    """Normalize a git hosting URL to a clonable form."""
    url = url.rstrip('/')
    # Remove trailing tree/master, /wiki, /releases, etc.
    url = re.sub(r'/(tree|blob|wiki|releases|issues|pulls?|archive|raw|tags|commits?|actions|security|network|settings|stargazers|watchers|graphs?|milestone)(\/.*)?$', '', url)
    return url


def determine_archive_type(url):
    """Determine archive type from a code-site URL."""
    parsed = urlparse(url)
    domain = parsed.hostname or ''

    # Check known git hosting domains + heuristic for git*/gitlab* subdomains
    if domain in GIT_DOMAINS:
        return 'git'
    if domain.startswith('git.') or domain.startswith('gitlab.') or domain.startswith('gitea.'):
        return 'git'

    # SourceForge — some have git, but treat as download for now
    # (can be manually upgraded after review)
    if 'sourceforge.net' in domain:
        return 'download'

    # Downloadable archive URLs
    if re.search(r'\.(tar\.gz|tgz|tar\.bz2|zip|tar|gz)$', parsed.path, re.I):
        return 'download'

    # PyPI, CRAN — downloadable
    if domain in ('pypi.org', 'cran.r-project.org'):
        return 'download'

    # DOI — resolve later, treat as download
    if domain in ('doi.org', 'dx.doi.org'):
        return 'download'

    # Everything else is web-only
    return 'webonly'


def build_dir_name(short_name, ascl_id):
    """Build the directory name: {short_name}-{ascl_id}."""
    name = slugify(short_name) if short_name else 'unknown'
    return f"{name}-{ascl_id}"


def main():
    parser = argparse.ArgumentParser(description='Populate code_archive table')
    parser.add_argument('--database', default='ascl_db_v4', help='Database name')
    parser.add_argument('--dry-run', action='store_true', help='Print actions without writing to DB')
    args = parser.parse_args()

    conn = get_mysql_connection(args.database)
    cursor = conn.cursor()

    # Get all published codes with real ASCL IDs
    cursor.execute("""
        SELECT pk, ascl_id, short_name, title
        FROM codes
        WHERE published = 1 AND ascl_id != '0000.000'
        ORDER BY ascl_id
    """)
    codes = cursor.fetchall()
    print(f"Found {len(codes)} published codes")

    # Get all code-site links (link_type_pk=2), preferring git-hosting URLs
    cursor.execute("""
        SELECT code_pk, url
        FROM link
        WHERE link_type_pk = 2
        ORDER BY code_pk, pk
    """)
    # Group links by code_pk; keep all for choosing best
    code_links = {}
    for code_pk, url in cursor.fetchall():
        code_links.setdefault(code_pk, []).append(url)

    # Check what's already in code_archive
    cursor.execute("SELECT code_pk FROM code_archive")
    existing = {row[0] for row in cursor.fetchall()}

    stats = {'git': 0, 'download': 0, 'webonly': 0, 'missing': 0, 'skipped': 0}
    inserts = []

    for code_pk, ascl_id, short_name, title in codes:
        if code_pk in existing:
            stats['skipped'] += 1
            continue

        urls = code_links.get(code_pk, [])

        if not urls:
            # No code-site link at all
            name_source = short_name or title.split(':')[0].strip()
            dir_name = build_dir_name(name_source, ascl_id)
            inserts.append((code_pk, 'webonly', '', dir_name, 'missing'))
            stats['missing'] += 1
            continue

        # Prefer a git URL if available
        best_url = None
        best_type = None
        for url in urls:
            atype = determine_archive_type(url)
            if atype == 'git':
                best_url = normalize_git_url(url)
                best_type = 'git'
                break
        if best_url is None:
            best_url = urls[0]
            best_type = determine_archive_type(best_url)

        name_source = short_name or title.split(':')[0].strip()
        dir_name = build_dir_name(name_source, ascl_id)
        inserts.append((code_pk, best_type, best_url, dir_name, 'pending'))
        stats[best_type] += 1

    print(f"\nArchive type breakdown:")
    print(f"  git:      {stats['git']}")
    print(f"  download: {stats['download']}")
    print(f"  webonly:  {stats['webonly']}")
    print(f"  missing:  {stats['missing']}")
    print(f"  skipped:  {stats['skipped']} (already in code_archive)")
    print(f"  total:    {sum(stats.values())}")

    if args.dry_run:
        print("\n[DRY RUN] No changes written. Sample entries:")
        for row in inserts[:10]:
            print(f"  {row}")
        return

    # Bulk insert
    cursor.executemany("""
        INSERT INTO code_archive (code_pk, archive_type, source_url, dir_name, status)
        VALUES (%s, %s, %s, %s, %s)
    """, inserts)
    conn.commit()
    print(f"\nInserted {len(inserts)} rows into code_archive")

    cursor.close()
    conn.close()


if __name__ == '__main__':
    main()
