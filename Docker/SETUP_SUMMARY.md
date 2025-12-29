# ASCL Development Environment Setup - Summary

## What Was Created

The automated setup system for recreating the ASCL MySQL development environment on a new server.

### Files Created

1. **`setup_dev_environment.sh`** ⭐ Main automation script
   - Fully automated Docker MySQL setup
   - Restores databases from backups
   - Runs DB_UPGRADE_PLAYBOOK.sql
   - Configures ~/.my.cnf
   - Idempotent (safe to re-run)

2. **`README_DEV_SETUP.md`** - Comprehensive documentation
   - Detailed setup instructions (automated and manual)
   - Database schema documentation
   - Troubleshooting guide
   - Verification commands
   - Architecture diagram

3. **`QUICK_REFERENCE.md`** - Quick reference card
   - Common commands
   - Connection examples
   - Management operations
   - One-liners for quick tasks

4. **`SETUP_SUMMARY.md`** - This file
   - Overview of the setup system
   - Quick start guide

---

## Quick Start

### Run the Setup Script

```bash
cd /home/demitri/repositories/ASCL/alt_ascl/Docker
./setup_dev_environment.sh
```

The script will:
1. ✅ Verify prerequisites (Docker, backups, playbook)
2. ✅ Create Docker container `mysql_ascl_dev` on port 3307
3. ✅ Create databases: `ascl_db`, `ascl_db_v4`, `ascl_wordpress`, `ascl_phpbb`
4. ✅ Restore database backups
5. ✅ Run `DB_UPGRADE_PLAYBOOK.sql`
6. ✅ Configure `~/.my.cnf` with `[client_ascl]` section
7. ✅ Verify setup (tables, foreign keys, InnoDB conversion)

**Runtime**: ~5-10 minutes (depending on hardware)

---

## What Gets Set Up

### Docker Container

- **Name**: `mysql_ascl_dev`
- **Image**: `mysql:8.0.42`
- **Port**: `3307` (host) → `3306` (container)
- **Volume**: `mysql_ascl_dev_data` (persistent storage)
- **Restart**: Unless stopped (survives reboots)

### Databases

| Database | Size | Tables | Description |
|----------|------|--------|-------------|
| `ascl_db` | 18 MB | ~20 | Original backup (MyISAM) |
| `ascl_db_v4` | ~18 MB | ~13 | Upgraded (InnoDB + FKs) |
| `ascl_wordpress` | 26 MB | ~20 | WordPress content |
| `ascl_phpbb` | 27 MB | ~60 | phpBB forum database |

### Credentials

Default credentials (can be overridden via environment variables):

```
Root Password:  ascl_root_dev_password
Database User:  ascl_db
User Password:  ascl_dev_password
```

### Configuration

The script adds this section to `~/.my.cnf`:

```ini
[client_ascl]
user=ascl_db
password=ascl_dev_password
host=127.0.0.1
port=3307
```

This allows password-less connection:
```bash
mysql --defaults-group-suffix=_ascl -D ascl_db_v4
```

---

## Schema Changes (ascl_db_v4)

The `DB_UPGRADE_PLAYBOOK.sql` applies these changes:

### ✅ Table Engine Conversion
- All tables: MyISAM → InnoDB
- Enables foreign keys and ACID compliance

### ✅ Character Set Standardization
- All tables: utf8mb4_unicode_ci
- Full Unicode support (emojis, international characters)

### ✅ Primary Key Renaming
- `codes.id` → `codes.pk`
- Consistent naming convention

### ✅ Foreign Key Migration
- Migrated from `ascl_id` (varchar) to `code_pk` (integer)
- Added 9 foreign key constraints:
  - `code_aliases` → `codes`
  - `code_keywords` → `codes`, `keywords`
  - `citations` → `codes`
  - `ads_entries_new` → `codes`
  - `link` → `codes`
  - `change` → `codes`
  - `citefile_metadata` → `codes`
  - `ascl_for_zenodo_matching` → `codes`

### ✅ Legacy Table Cleanup
Dropped obsolete tables:
- `codes_backup2`
- `classic_citations`
- `citations_new`
- `links` (superseded by `link`)
- `ads_entries` (superseded by `ads_entries_new`)
- `ascl_for_zenodo_matching_two`
- `ascl_for_zenodo_matching2`

### ✅ Timestamp Fixes
- Converted zero dates (`0000-00-00 00:00:00`) to NULL
- Added proper defaults for created/updated timestamps

---

## Verification

After setup completes, verify:

### 1. Container Running
```bash
docker-compose ps
# Should show: mysql_ascl_dev (healthy)
```

### 2. Databases Created
```bash
docker exec mysql_ascl_dev mysql -uroot -pascl_root_dev_password -e "SHOW DATABASES;"
# Should list: ascl_db, ascl_db_v4, ascl_wordpress, ascl_phpbb
```

### 3. Tables Restored
```bash
mysql --defaults-group-suffix=_ascl -D ascl_db_v4 -e "SELECT COUNT(*) FROM codes;"
# Should return: 4000+ rows
```

### 4. Foreign Keys Created
```bash
mysql --defaults-group-suffix=_ascl -D ascl_db_v4 -e "
SELECT COUNT(*) FROM information_schema.KEY_COLUMN_USAGE
WHERE TABLE_SCHEMA='ascl_db_v4' AND REFERENCED_TABLE_NAME IS NOT NULL;"
# Should return: 9 foreign keys
```

### 5. Python Connection Works
```bash
cd /home/demitri/repositories/ASCL/alt_ascl
python3 -c "from ascl_core.database.connections.Trillian2DBConnection import db; print('✅ Connected')"
```

---

## Daily Usage

### Start Development
```bash
# Start database
cd /home/demitri/repositories/ASCL/alt_ascl/Docker
docker-compose up -d

# Start Flask app
cd /home/demitri/repositories/ASCL/alt_ascl/source/ascl_net_app_project_home
python run_ascl_net_app.py --debug --port 5000
```

### Stop Development
```bash
cd /home/demitri/repositories/ASCL/alt_ascl/Docker
docker-compose stop
```

### View Logs
```bash
cd /home/demitri/repositories/ASCL/alt_ascl/Docker
docker-compose logs -f mysql
```

---

## Customization

### Change Passwords

Set environment variables before running:

```bash
export ASCLDB_ROOT_PASSWORD=my_secure_root_password
export ASCLDB_USER=ascl_db
export ASCLDB_PASSWORD=my_secure_password
./setup_dev_environment.sh
```

Or create a `.env` file:

```bash
cp .env.example .env
nano .env  # Edit passwords
./setup_dev_environment.sh
```

### Change Port

Edit `docker-compose.yml` before running:

```yaml
ports:
  - "3308:3306"  # Use port 3308 instead
```

Then update `~/.my.cnf` and `Trillian2DBConnection.py` accordingly.

---

## Troubleshooting

### Script fails: "Database backup not found"

**Solution**: Verify backup files exist:
```bash
ls -lh /home/demitri/repositories/ASCL/db_backups/
```

Should show:
- `ascl_db-backup_2011.11.29.sql`
- `ascl_wordpress-backup_2025.11.29.sql`

### Script fails: "~/.my.cnf does not exist"

**Solution**: Create the file first:
```bash
touch ~/.my.cnf
chmod 600 ~/.my.cnf
```

Then re-run the script.

### Container won't start: "Port 3307 already in use"

**Solution**: Check what's using the port:
```bash
sudo lsof -i :3307
```

Either kill that process or change the port in `docker-compose.yml`.

### Foreign keys not created

**Solution**: Re-run the upgrade playbook manually:
```bash
docker exec -i mysql_ascl_dev mysql -uroot -pascl_root_dev_password \
  < /home/demitri/repositories/ASCL/alt_ascl/agents/DB_UPGRADE_PLAYBOOK.sql
```

### Complete Reset

If everything is broken, start fresh:
```bash
cd /home/demitri/repositories/ASCL/alt_ascl/Docker
docker-compose down -v  # ⚠️ DELETES ALL DATA
./setup_dev_environment.sh  # Re-run setup
```

---

## Next Steps

After successful setup:

1. **Test the connection**:
   ```bash
   mysql --defaults-group-suffix=_ascl -D ascl_db_v4 -e "SELECT ascl_id, title FROM codes LIMIT 5;"
   ```

2. **Run Flask app**:
   ```bash
   cd /home/demitri/repositories/ASCL/alt_ascl/source/ascl_net_app_project_home
   python run_ascl_net_app.py --debug --port 5000
   ```

3. **Continue development**:
   - See `TODO_MASTER.md` for project status
   - Database models: `ascl_core/database/ascldb/ASCLModelClasses.py`
   - Controllers: `source/ascl_net_app_project_home/ascl_net_app/controllers/`

---

## Files Reference

| File | Purpose |
|------|---------|
| `setup_dev_environment.sh` | Main automation script |
| `docker-compose.yml` | Docker container configuration |
| `README_DEV_SETUP.md` | Full documentation |
| `QUICK_REFERENCE.md` | Command cheat sheet |
| `SETUP_SUMMARY.md` | This file |
| `.env.example` | Template for credentials |
| `../agents/DB_UPGRADE_PLAYBOOK.sql` | Database upgrade script |
| `../ascl_core/database/connections/Trillian2DBConnection.py` | Python connection |

---

## Support

- **Documentation**: See `README_DEV_SETUP.md` for detailed instructions
- **Quick Help**: See `QUICK_REFERENCE.md` for common commands
- **Project Status**: See `../agents/TODO_MASTER.md`

---

**Created**: 2025-12-03
**Version**: 1.0
**Maintainer**: Demitri Muna
