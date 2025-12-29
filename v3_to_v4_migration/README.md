# v3 to v4 Migration Directory

This directory contains scripts, documentation, and utilities for migrating ASCL from v3 (PHP+CodeIgniter+MySQL) to v4 (Python+Flask+MySQL/PostgreSQL).

## Contents

### Database Migration
- **`copy_ascl_database.sh`** - Script to copy the ASCL database (works around mysqldump config issues)
- **`restore_wordpress_backup.sh`** - Restore a provided WordPress backup SQL into the dev MySQL instance (explicit SQL path required)
- **`README_DATABASE_COPY.md`** - Documentation for the database copy process

#### Restoring WordPress Backup
```bash
# Default target DB is ascl_wordpress
./restore_wordpress_backup.sh ascl_wordpress /path/to/ascl_wordpress-backup_2025.11.29.sql

# Or choose a different target DB name
./restore_wordpress_backup.sh my_wp_db /path/to/backup.sql
```
## Organization Guidelines

As we add more migration-related files, please organize them by category:

- **Database scripts** - Schema changes, data migrations, conversion scripts
- **Documentation** - Migration notes, decisions, troubleshooting guides
- **Testing** - Migration validation scripts, data integrity checks
- **Utilities** - Helper scripts for the migration process

## Related Documentation

See the main project TODO at `../agents/TODO_MASTER.md` for the complete migration plan.

---
Last updated: 2025-11-30
