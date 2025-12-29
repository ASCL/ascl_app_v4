# Database Copy Script Documentation

## Problem

When trying to copy the ASCL database using `mysqldump`, you may encounter this error:
```
mysqldump: [ERROR] unknown variable 'database=mysql'
```

This happens because `mysqldump` doesn't support the `database=` option that exists in `~/.my.cnf` under the `[client]` section.

## Solution

The `copy_ascl_database.sh` script works around this issue by:

1. Creating a temporary credentials file
2. Extracting the `[client_ascl_root]` section from `~/.my.cnf`
3. Renaming the section header to `[client]`
4. Removing the problematic `database=` entry
5. Using this clean credentials file for both `mysql` and `mysqldump` commands

## Usage

```bash
# Copy ascl_db to ascl_db_v4 (default), excluding legacy tables
./scripts/copy_ascl_database.sh

# Copy any database to another
./scripts/copy_ascl_database.sh source_db target_db
```

## Manual Approach

If you need to do this manually:

```bash
# Create temporary credentials file
tmp=$(mktemp)

# Extract [client_ascl_root] section, rename to [client], remove database= line
awk '
  /^\[client_ascl_root\]/ { in_section=1; print "[client]"; next }
  /^\[/ && in_section { exit }
  in_section && !/^database=/ { print }
' ~/.my.cnf > "$tmp"

# Drop and create target database
mysql --defaults-file="$tmp" --protocol=TCP --host=127.0.0.1 --port=3307 \
  -e "DROP DATABASE IF EXISTS ascl_db_v4; CREATE DATABASE ascl_db_v4;"

# Copy database
mysqldump --defaults-file="$tmp" --protocol=TCP --host=127.0.0.1 --port=3307 ascl_db \
  | mysql --defaults-file="$tmp" --protocol=TCP --host=127.0.0.1 --port=3307 ascl_db_v4

# Clean up
rm -f "$tmp"
```

## Important Notes

- **Do NOT use MySQL tools** (like `my_print_defaults | mysql`) to create the temp credentials file, as they blank out the password
- The `--protocol=TCP --host=127.0.0.1 --port=3307` flags can be omitted if they are already in the temporary defaults file
- The script uses `set -e` to exit on any error
- The temp file is automatically cleaned up using a trap on EXIT
- The script excludes legacy tables so v4 starts clean: `ascl_for_zenodo_matching_two`, `ascl_for_zenodo_matching2`, `ads_entries`, `codes_backup2`, `classic_citations`, `citations_new`, `links`

## Why This Works

By using `--defaults-file` with a clean credentials file (no `database=` option), we can:
- Avoid the `mysqldump` error about unknown variable
- Avoid the problematic `database=` setting in the main `~/.my.cnf`
- Maintain secure credential handling (password stays in the file)

## Date Created
2025-11-30
