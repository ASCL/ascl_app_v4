# ASCL Icecave — Code Archival & Preservation System

## Overview

The ASCL Icecave is an automated archival system for preserving copies of every code in the ASCL catalog. It replaces manual curator downloads to a Google Drive (~250GB) with automated git mirroring and structured storage on a dedicated VPS.

## Goals

1. Automate archival of all ASCL codes (currently ~3,958 published)
2. Eliminate single point of failure (Google account dependency)
3. Provide admin dashboard for archive status monitoring
4. Integrate with archive.org for web-only codes

## Current State (2026-04-03)

### Completed

- **`short_name` column** added to `codes` table — populated from GitHub repo names for 2,745 codes; 1,213 remain (plan: use AI model like Gemma to generate from titles, deferred for now)
- **`code_archive` table** created and populated with 3,958 rows
- **Archive type classification**: 2,951 git, 124 download, 879 webonly, 4 missing
- **Clone script** tested — 5 repos successfully cloned as bare mirrors
- **Sync script** written — ready for daily cron
- **Directory structure** established at `/data/ascl_icecave/`

### Not Yet Built

- Admin dashboard page (`/admin/archive`)
- Download handler for non-git codes (tarballs, zips)
- Archive.org integration (Save Page Now API, Wayback Availability API)
- Cron job setup for daily sync
- VPS migration (developing on dev server first, will rsync to VPS later)

## Architecture

### Directory Layout

```
/data/ascl_icecave/
├── codes/           # bare git mirrors + downloaded archives
│   ├── emcee-2010.001/        # git mirror (bare repo)
│   ├── astropy-1207.007/      # git mirror
│   └── some-tool-2015.042/    # could be downloaded tarballs
├── by-id/           # symlinks for lookup by ASCL ID
│   ├── 2010.001-emcee -> ../codes/emcee-2010.001
│   └── 1207.007-astropy -> ../codes/astropy-1207.007
└── logs/            # timestamped clone/sync logs
```

### Three Categories of Codes

| Category | Count | Strategy | Update method |
|----------|-------|----------|---------------|
| Git repos (GitHub, GitLab, Bitbucket, self-hosted) | 2,951 | `git clone --mirror` | `git remote update` daily |
| Downloadable archives (PyPI, CRAN, DOI, tarballs) | 124 | Download files | Check HTTP headers for changes |
| Web-only (department pages, personal sites) | 879 | Curator submits to archive.org | Link checker + Wayback API |
| No URL available | 4 | Manual investigation | — |

### Database Schema

**`codes.short_name`** (VARCHAR(100), nullable) — added after `title` column. Used for directory naming. Populated from GitHub repo names via migration step 17/18 in `migrate_v3_to_v4.sh`.

**`code_archive` table** (migration `005_create_code_archive_table.sql`):

| Column | Type | Description |
|--------|------|-------------|
| pk | INT AUTO_INCREMENT | Primary key |
| code_pk | INT NOT NULL | FK → codes.pk (unique) |
| archive_type | ENUM('git','download','webonly') | How to archive this code |
| source_url | VARCHAR(500) | URL used for cloning/downloading |
| dir_name | VARCHAR(200) | Directory name under codes/ |
| last_checked | DATETIME | Last sync attempt |
| last_updated | DATETIME | Last time new content was found |
| last_wayback | DATETIME | Most recent archive.org capture |
| wayback_url | VARCHAR(500) | Wayback URL |
| size_bytes | BIGINT | Size on disk |
| status | ENUM('pending','active','stale','error','missing') | Current state |
| error_message | TEXT | Last error details |
| created_at | TIMESTAMP | Row creation time |

## Scripts

All in `bin/`:

### `icecave_populate.py`

Populates `code_archive` from the `link` table. Determines archive type by domain:
- Known git domains (github.com, gitlab.com, bitbucket.org, plus ~30 self-hosted instances) → `git`
- Heuristic: any domain starting with `git.` or `gitlab.` → `git`
- pypi.org, cran.r-project.org, doi.org → `download`
- sourceforge.net → `download` (some have git, needs manual review)
- Everything else → `webonly`

```bash
python3 bin/icecave_populate.py --dry-run          # preview
python3 bin/icecave_populate.py                     # populate
python3 bin/icecave_populate.py --database other_db # different database
```

### `icecave_clone.py`

Clones pending git repos as bare mirrors. Creates by-id symlinks. Updates DB.

```bash
python3 bin/icecave_clone.py --dry-run       # preview
python3 bin/icecave_clone.py --limit 50      # clone 50 at a time
python3 bin/icecave_clone.py                 # clone all pending
```

- 0.5s pause between clones to avoid rate limiting
- 5-minute timeout per clone
- Logs to `/data/ascl_icecave/logs/clone_YYYYMMDD_HHMMSS.log`

### `icecave_sync.py`

Daily sync of active git mirrors via `git remote update`.

```bash
python3 bin/icecave_sync.py                  # sync active repos
python3 bin/icecave_sync.py --retry-errors   # also retry failed repos
```

- Detects whether new content was fetched (updates `last_updated` only if so)
- Marks repos with missing directories as `error`
- Logs to `/data/ascl_icecave/logs/sync_YYYYMMDD_HHMMSS.log`

## Working with Bare Mirrors

Bare mirrors have no working tree. To get files out:

```bash
# Clean export (no .git, no history) — best for analysis
git --git-dir=/data/ascl_icecave/codes/emcee-2010.001 archive HEAD | tar -x -C /tmp/emcee

# Checkout via worktree (retains git history, can be removed later)
git --git-dir=/data/ascl_icecave/codes/emcee-2010.001 worktree add /tmp/emcee main

# List branches/tags
git --git-dir=/data/ascl_icecave/codes/emcee-2010.001 branch -a
git --git-dir=/data/ascl_icecave/codes/emcee-2010.001 tag
```

## VPS Plan

**Target:** Servarica "Killer Whale Storage" — 3.5 TB HDD, 2 GB RAM, 2 cores, 18 TB bandwidth, $84/yr. RAID-Z2 on host side.

**ZFS on Ubuntu:** Install with `apt install zfsutils-linux`. Even on a single virtual disk, ZFS provides instant snapshots (`zfs snapshot tank@2026-04-03`) and transparent LZ4 compression to stretch storage.

**Migration:** Develop on current dev server, then `rsync` the entire `/data/ascl_icecave/` tree to the VPS. Re-run `icecave_populate.py` on the VPS database to set up `code_archive` there (or dump/restore the table).

## Migration Script Integration

- `v3_to_v4_migration/add_short_name_column.sql` — adds `short_name` to `codes` and populates from GitHub repo names (step 17/18 in `migrate_v3_to_v4.sh`)
- `migrations/005_create_code_archive_table.sql` — creates the `code_archive` table (run separately, not part of v3→v4 migration since it has no v3 equivalent)

## Archive.org Integration (Future)

- **Save Page Now API:** `POST https://web.archive.org/save` — requires free account + S3-style API keys. Rate-limited. Will be triggered from admin page per code.
- **Wayback Availability API:** `GET https://archive.org/wayback/available?url=<url>` — no auth needed. Use to populate `last_wayback` column.
- **Admin workflow:** Curator clicks "Capture on Archive.org" button for webonly codes. Dashboard shows last Wayback snapshot date.

## Remaining Short Name Population (Deferred)

1,213 codes lack a `short_name` (no GitHub URL to derive from). Plan:
- Use a small AI model (e.g. google/gemma-4-31b-it at ~$0.40/M output tokens) to extract short names from titles
- Many titles follow "ShortName: Long Description" pattern
- Could also try regex first-pass (split on `:` or ` - `), send ambiguous ones to AI
- Short names should be slugified (lowercase, hyphens, no special chars)
