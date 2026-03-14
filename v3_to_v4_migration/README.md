# v3 to v4 Migration Directory

This directory contains scripts, documentation, and utilities for migrating ASCL from v3 (PHP+CodeIgniter+MySQL) to v4 (Python+Flask+MySQL/PostgreSQL).

## Contents

### Database Migration
- **`copy_ascl_database.sh`** - Script to copy the ASCL database and migrate PHP-serialized fields
- **`migrate_serialized_to_links.py`** - Called automatically by copy script to normalize data
- **`restore_wordpress_backup.sh`** - Restore a provided WordPress backup SQL into the dev MySQL instance
- **`README_DATABASE_COPY.md`** - Documentation for the database copy process

#### Restoring WordPress Backup
```bash
# Default target DB is ascl_wordpress
./restore_wordpress_backup.sh ascl_wordpress /path/to/ascl_wordpress-backup_2025.11.29.sql

# Or choose a different target DB name
./restore_wordpress_backup.sh my_wp_db /path/to/backup.sql
```

#### Automatic Migration of PHP Serialized Fields

The `copy_ascl_database.sh` script automatically migrates PHP-serialized fields to normalized tables as part of the copy process.

**Fields being migrated:**

| Old Field (codes table) | Storage Format | Migrated To |
|-------------------------|----------------|-------------|
| `site_list` | PHP serialized array | `link` table (type: code-site) |
| `ref_list` | PHP serialized array | `link` table (type: refereed) |
| `described_in` | PHP serialized array | `link` table (type: described-in) |
| `used_in` | PHP serialized array | `link` table (type: used-in) |
| `see_also` | Semicolon-separated string | `code_see_also` table (new) |

**Usage:**
```bash
# Copy database AND migrate serialized fields in one step
./copy_ascl_database.sh ascl_db ascl_db_v4

# Or run migration separately on an existing database
python migrate_serialized_to_links.py ascl_db_v4

# Preview migration without making changes
python migrate_serialized_to_links.py ascl_db_v4 --dry-run
```

**Link Types (link_type table):**

| short_name | name | Used For |
|------------|------|----------|
| code-site | Code Site | site_list URLs |
| refereed | Refereed | ref_list URLs |
| described-in | Described In | described_in bibcodes/URLs |
| used-in | Used In | used_in bibcodes/URLs |

**New Table for See Also:**

```sql
code_see_also (
    id INT PRIMARY KEY,
    code_pk INT NOT NULL,           -- FK to codes.pk
    related_code_pk INT NULL,       -- FK to codes.pk (NULL if code doesn't exist)
    related_ascl_id VARCHAR(8),     -- ASCL ID string (YYMM.NNN)
    display_order INT,
    created_at TIMESTAMP
)
```

**Note:** The `code_see_also` table stores both the ASCL ID string and an optional FK to the related code, allowing references to codes that may not exist yet.

### Full-Text Search Index

- **`create_fulltext_index.sql`** - Creates FULLTEXT index for improved search relevance

The FULLTEXT index enables MySQL's native relevance ranking with `MATCH...AGAINST` queries. This dramatically improves search results by ranking title matches higher than abstract mentions.

**Usage:**
```bash
mysql -u user -p ascl_db_v4 < create_fulltext_index.sql
```

**Search Ranking (after index is created):**
1. Exact title match (e.g., "astropy" finds Astropy first)
2. Title starts with query
3. Title contains query
4. FULLTEXT relevance score
5. View count (popularity tiebreaker)

**Note:** The application automatically falls back to LIKE-based search with CASE scoring if the FULLTEXT index doesn't exist.

### Notes History Table

- **`create_code_note_table.sql`** - Creates the `note_type` and `code_note` tables for tracking note history

The `code_note` table replaces the single `notes` field on codes with a full history table that tracks who added each note and when.

**Usage:**
```bash
mysql -u user -p ascl_db_v4 < create_code_note_table.sql
```

**note_type Table (lookup):**

| short_name | name | description |
|------------|------|-------------|
| `legacy` | Legacy | Notes migrated from v3 |
| `general` | General | General notes |
| `review` | Review | Code review notes |
| `followup` | Follow-up | Follow-up items / action needed |
| `attention` | Needs Attention | Requires admin attention (shown on admin home) |
| `submission` | Submission | Notes from original submission |
| `update` | Update | Notes about updates to the code |
| `internal` | Internal | Internal admin notes |

**code_note Table:**

| Column | Type | Description |
|--------|------|-------------|
| `pk` | INT | Primary key |
| `code_pk` | INT | FK to codes table |
| `user_pk` | INT | FK to users table (who created the note) |
| `note_type_pk` | INT | FK to note_type table |
| `note` | TEXT | The note content |
| `created_at` | TIMESTAMP | When the note was created |
| `is_pinned` | TINYINT | Pin important notes to top |
| `hidden` | TINYINT | Hide note without deleting |

The migration script automatically imports existing notes from `codes.notes` into the new table with type "Legacy".

## Organization Guidelines

As we add more migration-related files, please organize them by category:

- **Database scripts** - Schema changes, data migrations, conversion scripts
- **Documentation** - Migration notes, decisions, troubleshooting guides
- **Testing** - Migration validation scripts, data integrity checks
- **Utilities** - Helper scripts for the migration process

## Related Documentation

See the main project TODO at `../agents/TODO_MASTER.md` for the complete migration plan.

---
Last updated: 2026-02-01
