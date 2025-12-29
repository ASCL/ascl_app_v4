# ASCL Development Environment Setup Guide

This guide documents the complete setup process for the ASCL MySQL development environment using Docker.

## Overview

The development environment consists of:
- **MySQL 8.0.42** running in a Docker container named `mysql_ascl_dev`
- **Port 3307** (to avoid conflicts with other MySQL instances)
- **Four databases**:
  - `ascl_db` - Original production backup (MyISAM, no FKs)
  - `ascl_db_v4` - Upgraded schema (InnoDB, foreign keys, code_pk migration)
  - `ascl_wordpress` - WordPress content database
  - `ascl_phpbb` - phpBB forum database

## Quick Start

### Prerequisites

1. **Docker and docker-compose installed**
   ```bash
   docker --version
   docker-compose --version
   ```

2. **Database backup files** in `/home/demitri/repositories/ASCL/db_backups/`:
   - `ascl_db-backup_2011.11.29.sql`
   - `ascl_wordpress-backup_2025.11.29.sql`
   - `ascl_phpbb-database-backup-2025.12.02.sql.gz`

3. **Upgrade playbook** at `/home/demitri/repositories/ASCL/alt_ascl/agents/DB_UPGRADE_PLAYBOOK.sql`

4. **~/.my.cnf exists** (the script will add a `[client_ascl]` section)

### Automated Setup

Run the automated setup script:

```bash
cd /home/demitri/repositories/ASCL/alt_ascl/Docker
./setup_dev_environment.sh
```

This script will:
1. ✅ Check prerequisites
2. ✅ Update docker-compose.yml with container name `mysql_ascl_dev`
3. ✅ Start MySQL 8.0.42 container on port 3307
4. ✅ Create four databases
5. ✅ Restore `ascl_db` from backup
6. ✅ Restore `ascl_wordpress` from backup
7. ✅ Restore `ascl_phpbb` from backup
8. ✅ Copy `ascl_db` → `ascl_db_v4`
9. ✅ Run `DB_UPGRADE_PLAYBOOK.sql` to upgrade v4 schema
10. ✅ Verify databases and foreign keys
11. ✅ Add `[client_ascl]` section to ~/.my.cnf

### Expected Output

```
[SUCCESS] Development environment setup complete!

Container Details:
  Name:           mysql_ascl_dev
  Port:           127.0.0.1:3307
  User:           ascl_db
  Password:       [configured]

Databases:
  ascl_db         - Original production backup
  ascl_db_v4      - Upgraded with InnoDB, FKs, code_pk migration
  ascl_wordpress  - WordPress content
  ascl_phpbb      - phpBB forum database
```

---

## Manual Setup (Alternative)

If you prefer to set up manually or need to troubleshoot:

### Step 1: Update docker-compose.yml

Edit `/home/demitri/repositories/ASCL/alt_ascl/Docker/docker-compose.yml`:

```yaml
services:
  mysql:
    image: mysql:8.0.42
    container_name: mysql_ascl_dev
    restart: unless-stopped
    environment:
      MYSQL_ROOT_PASSWORD: ${ASCLDB_ROOT_PASSWORD:-ascl_root_dev_password}
      MYSQL_USER: ${ASCLDB_USER:-ascl_db}
      MYSQL_PASSWORD: ${ASCLDB_PASSWORD:-ascl_dev_password}
    ports:
      - "3307:3306"
    volumes:
      - mysql_ascl_dev_data:/var/lib/mysql
    command: --default-authentication-plugin=mysql_native_password
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost", "-u", "root", "-p$$MYSQL_ROOT_PASSWORD"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  mysql_ascl_dev_data:
```

### Step 2: Start Container

```bash
cd /home/demitri/repositories/ASCL/alt_ascl/Docker
docker-compose up -d
```

Wait for healthy status:
```bash
docker-compose ps
# Wait for STATUS column to show "healthy"
```

### Step 3: Create Databases

```bash
docker exec -i mysql_ascl_dev mysql -uroot -pascl_root_dev_password <<EOF
CREATE DATABASE IF NOT EXISTS ascl_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE IF NOT EXISTS ascl_db_v4 CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE IF NOT EXISTS ascl_wordpress CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE IF NOT EXISTS ascl_phpbb CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
GRANT ALL PRIVILEGES ON ascl_db.* TO 'ascl_db'@'%';
GRANT ALL PRIVILEGES ON ascl_db_v4.* TO 'ascl_db'@'%';
GRANT ALL PRIVILEGES ON ascl_wordpress.* TO 'ascl_db'@'%';
GRANT ALL PRIVILEGES ON ascl_phpbb.* TO 'ascl_db'@'%';
FLUSH PRIVILEGES;
EOF
```

### Step 4: Restore Backups

```bash
# Restore ascl_db
docker exec -i mysql_ascl_dev mysql -uroot -pascl_root_dev_password ascl_db \
  < /home/demitri/repositories/ASCL/db_backups/ascl_db-backup_2011.11.29.sql

# Restore ascl_wordpress
docker exec -i mysql_ascl_dev mysql -uroot -pascl_root_dev_password ascl_wordpress \
  < /home/demitri/repositories/ASCL/db_backups/ascl_wordpress-backup_2025.11.29.sql

# Restore ascl_phpbb (gzip compressed)
gunzip -c /home/demitri/repositories/ASCL/db_backups/ascl_phpbb-database-backup-2025.12.02.sql.gz | \
  docker exec -i mysql_ascl_dev mysql -uroot -pascl_root_dev_password ascl_phpbb
```

### Step 5: Copy and Upgrade to v4

```bash
# Copy ascl_db to ascl_db_v4
docker exec mysql_ascl_dev bash -c \
  "mysqldump -uroot -pascl_root_dev_password ascl_db | mysql -uroot -pascl_root_dev_password ascl_db_v4"

# Run upgrade playbook
docker exec -i mysql_ascl_dev mysql -uroot -pascl_root_dev_password \
  < /home/demitri/repositories/ASCL/alt_ascl/agents/DB_UPGRADE_PLAYBOOK.sql
```

### Step 6: Configure ~/.my.cnf

Add this section to your `~/.my.cnf`:

```ini
# ASCL Development Database
[client_ascl]
user=ascl_db
password=ascl_dev_password
host=127.0.0.1
port=3307
```

Then set permissions:
```bash
chmod 600 ~/.my.cnf
```

---

## Connecting to the Database

### Option 1: Via Docker (Direct)

```bash
# Connect to ascl_db_v4
docker exec -it mysql_ascl_dev mysql -uascl_db -pascl_dev_password ascl_db_v4

# Connect as root
docker exec -it mysql_ascl_dev mysql -uroot -pascl_root_dev_password
```

### Option 2: Via ~/.my.cnf (Local MySQL Client)

```bash
# Connect using [client_ascl] section
mysql --defaults-group-suffix=_ascl -D ascl_db_v4

# Or shorter with alias (add to ~/.bashrc):
alias mysql-ascl='mysql --defaults-group-suffix=_ascl'
mysql-ascl -D ascl_db_v4
```

### Option 3: From Python (Trillian2DBConnection)

The `Trillian2DBConnection.py` is already configured:

```python
from alt_ascl.ascl_core.database.connections.Trillian2DBConnection import db, Session

# Use the connection
with Session() as session:
    result = session.execute("SELECT COUNT(*) FROM codes")
    print(result.scalar())
```

---

## Database Schema Details

### ascl_db (Original)
- **Engine**: MyISAM (no foreign keys)
- **Purpose**: Unchanged production backup for reference
- **Use case**: Compare with upgraded schema

### ascl_db_v4 (Upgraded)
- **Engine**: InnoDB (ACID-compliant, supports foreign keys)
- **Changes applied by DB_UPGRADE_PLAYBOOK.sql**:
  - ✅ Converted all tables from MyISAM → InnoDB
  - ✅ Fixed timestamp columns (removed zero dates)
  - ✅ Standardized character set to utf8mb4_unicode_ci
  - ✅ Renamed `codes.id` → `codes.pk`
  - ✅ Added foreign key constraints:
    - `code_aliases.code_id` → `codes.pk`
    - `code_keywords.code_id` → `codes.pk`
    - `code_keywords.keyword_id` → `keywords.id`
    - `citations.code_pk` → `codes.pk`
    - `ads_entries_new.code_pk` → `codes.pk`
    - `link.code_pk` → `codes.pk`
    - `change.code_pk` → `codes.pk`
    - `citefile_metadata.code_pk` → `codes.pk`
    - `ascl_for_zenodo_matching.code_pk` → `codes.pk`
  - ✅ Migrated from `ascl_id` (varchar) to `code_pk` (integer) for all foreign keys
  - ✅ Dropped legacy tables (codes_backup2, links, ads_entries, etc.)
  - ✅ Added indexes for performance

### ascl_wordpress (WordPress)
- **Engine**: InnoDB
- **Purpose**: WordPress blog/news content
- **Tables**: `0hjpDo4yM_posts`, `0hjpDo4yM_postmeta`, etc.

### ascl_phpbb (phpBB Forum)
- **Engine**: InnoDB
- **Purpose**: phpBB forum database
- **Tables**: Forum posts, users, topics, etc.

---

## Verification Commands

### Check Container Status
```bash
docker-compose ps
```

### View Logs
```bash
docker-compose logs -f mysql
```

### Count Tables
```bash
docker exec mysql_ascl_dev mysql -uroot -pascl_root_dev_password -e "
SELECT TABLE_SCHEMA, COUNT(*) as table_count
FROM information_schema.TABLES
WHERE TABLE_SCHEMA IN ('ascl_db', 'ascl_db_v4', 'ascl_wordpress', 'ascl_phpbb')
GROUP BY TABLE_SCHEMA;"
```

### Verify InnoDB Conversion
```bash
docker exec mysql_ascl_dev mysql -uroot -pascl_root_dev_password -e "
SELECT ENGINE, COUNT(*) as count
FROM information_schema.TABLES
WHERE TABLE_SCHEMA = 'ascl_db_v4'
GROUP BY ENGINE;"
```

Should show only InnoDB, no MyISAM.

### Verify Foreign Keys
```bash
docker exec mysql_ascl_dev mysql -uroot -pascl_root_dev_password -e "
SELECT TABLE_NAME, CONSTRAINT_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME
FROM information_schema.KEY_COLUMN_USAGE
WHERE TABLE_SCHEMA = 'ascl_db_v4'
  AND REFERENCED_TABLE_NAME IS NOT NULL
ORDER BY TABLE_NAME;"
```

Should show 9 foreign key constraints.

### Test Python Connection
```bash
cd /home/demitri/repositories/ASCL/alt_ascl
python3 -c "
from ascl_core.database.connections.Trillian2DBConnection import db, Session
with Session() as session:
    result = session.execute('SELECT COUNT(*) FROM codes')
    print(f'Total codes: {result.scalar()}')
"
```

---

## Management Commands

### Start Container
```bash
cd /home/demitri/repositories/ASCL/alt_ascl/Docker
docker-compose up -d
```

### Stop Container
```bash
cd /home/demitri/repositories/ASCL/alt_ascl/Docker
docker-compose stop
```

### Restart Container
```bash
cd /home/demitri/repositories/ASCL/alt_ascl/Docker
docker-compose restart
```

### View Logs
```bash
cd /home/demitri/repositories/ASCL/alt_ascl/Docker
docker-compose logs -f mysql
```

### Backup Database
```bash
docker exec mysql_ascl_dev mysqldump -uroot -pascl_root_dev_password ascl_db_v4 | gzip > ascl_db_v4_backup_$(date +%Y%m%d).sql.gz
```

### Complete Reset (⚠️ Destroys all data)
```bash
cd /home/demitri/repositories/ASCL/alt_ascl/Docker
docker-compose down -v
./setup_dev_environment.sh  # Re-run setup
```

---

## Troubleshooting

### Container won't start - port 3307 in use
Check what's using the port:
```bash
sudo lsof -i :3307
```

Kill the process or change the port in docker-compose.yml.

### Container unhealthy after starting
Check logs for errors:
```bash
docker-compose logs mysql
```

Common issues:
- Password mismatch in environment variables
- Insufficient disk space
- Corrupted volume (solution: `docker-compose down -v` and restart)

### Can't connect from Python
1. Verify container is running: `docker-compose ps`
2. Check ~/.my.cnf has [client_ascl] section
3. Test connection manually: `mysql --defaults-group-suffix=_ascl -e "SELECT 1"`
4. Check Trillian2DBConnection.py port matches (3307)

### Database restored but tables are empty
This means the backup import failed. Check:
1. Backup file exists and is readable
2. Docker has enough memory (increase in Docker settings)
3. Re-run setup script with fresh start: `docker-compose down -v && ./setup_dev_environment.sh`

### Foreign keys not created
Run verification query (see above). If FKs are missing:
1. Check DB_UPGRADE_PLAYBOOK.sql ran successfully
2. Look for errors in `docker-compose logs mysql`
3. Manually re-run playbook:
   ```bash
   docker exec -i mysql_ascl_dev mysql -uroot -pascl_root_dev_password \
     < /home/demitri/repositories/ASCL/alt_ascl/agents/DB_UPGRADE_PLAYBOOK.sql
   ```

---

## Environment Variables

You can override default passwords using environment variables:

```bash
export ASCLDB_ROOT_PASSWORD=my_secure_root_password
export ASCLDB_USER=ascl_db
export ASCLDB_PASSWORD=my_secure_password
./setup_dev_environment.sh
```

Or create a `.env` file in the Docker directory:
```bash
cp .env.example .env
# Edit .env with your passwords
./setup_dev_environment.sh
```

---

## Files Modified by Setup Script

1. **docker-compose.yml** - Updated with container name and volume
   - Backup saved as `docker-compose.yml.bak`

2. **~/.my.cnf** - Added `[client_ascl]` section
   - Only appends if section doesn't exist
   - Does not create file (must already exist)

---

## Next Steps

After setup completes:

1. **Test Flask Application**:
   ```bash
   cd /home/demitri/repositories/ASCL/alt_ascl/source/ascl_net_app_project_home
   python run_ascl_net_app.py --debug --port 5000
   ```

2. **Verify Database Models**:
   ```bash
   cd /home/demitri/repositories/ASCL/alt_ascl
   python3 -c "from ascl_core.database.ascldb.ASCLModelClasses import ASCLCode; print('Models loaded successfully')"
   ```

3. **Run Database Queries**:
   ```bash
   mysql --defaults-group-suffix=_ascl -D ascl_db_v4 -e "SELECT ascl_id, title FROM codes LIMIT 5;"
   ```

---

## Architecture

```
┌─────────────────────────────────────────────┐
│  Host Machine (localhost)                   │
│                                             │
│  ┌──────────────────────────────────────┐  │
│  │ ~/.my.cnf [client_ascl]               │  │
│  │   user=ascl_db                         │  │
│  │   password=***                         │  │
│  │   host=127.0.0.1                       │  │
│  │   port=3307                            │  │
│  └──────────────────────────────────────┘  │
│                    │                         │
│                    │ port 3307               │
│                    ▼                         │
│  ┌──────────────────────────────────────┐  │
│  │ Docker Container: mysql_ascl_dev     │  │
│  │   Image: mysql:8.0.42                 │  │
│  │   Port: 3306 → 3307                   │  │
│  │                                        │  │
│  │   ┌─────────────────────────────────┐│  │
│  │   │ MySQL Server                     ││  │
│  │   │                                  ││  │
│  │   │  📁 ascl_db (MyISAM)            ││  │
│  │   │  📁 ascl_db_v4 (InnoDB + FKs)   ││  │
│  │   │  📁 ascl_wordpress              ││  │
│  │   └─────────────────────────────────┘│  │
│  │                                        │  │
│  │  Volume: mysql_ascl_dev_data          │  │
│  └──────────────────────────────────────┘  │
└─────────────────────────────────────────────┘
```

---

## References

- Main TODO: `/home/demitri/repositories/ASCL/alt_ascl/agents/TODO_MASTER.md`
- DB Upgrade Playbook: `/home/demitri/repositories/ASCL/alt_ascl/agents/DB_UPGRADE_PLAYBOOK.sql`
- Connection Config: `/home/demitri/repositories/ASCL/alt_ascl/ascl_core/database/connections/Trillian2DBConnection.py`
- Docker Compose: `/home/demitri/repositories/ASCL/alt_ascl/Docker/docker-compose.yml`

---

**Last Updated**: 2025-12-03
**Maintainer**: Demitri Muna
