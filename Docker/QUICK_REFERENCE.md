# ASCL Docker MySQL - Quick Reference Card

## 🚀 Setup (First Time)

```bash
cd /home/demitri/repositories/ASCL/alt_ascl/Docker
./setup_dev_environment.sh
```

---

## 🔌 Connect to Database

### Via Docker
```bash
docker exec -it mysql_ascl_dev mysql -uascl_db -pascl_dev_password ascl_db_v4
```

### Via ~/.my.cnf (Local Client)
```bash
mysql --defaults-group-suffix=_ascl -D ascl_db_v4
```

### From Python
```python
from ascl_core.database.connections.Trillian2DBConnection import db, Session
```

---

## 🎛️ Container Management

| Action | Command |
|--------|---------|
| **Start** | `docker-compose up -d` |
| **Stop** | `docker-compose stop` |
| **Restart** | `docker-compose restart` |
| **Status** | `docker-compose ps` |
| **Logs** | `docker-compose logs -f mysql` |
| **Shell** | `docker exec -it mysql_ascl_dev bash` |

---

## 💾 Database Operations

### Backup
```bash
docker exec mysql_ascl_dev mysqldump -uroot -pascl_root_dev_password ascl_db_v4 | gzip > backup.sql.gz
```

### Restore
```bash
gunzip -c backup.sql.gz | docker exec -i mysql_ascl_dev mysql -uroot -pascl_root_dev_password ascl_db_v4
```

### Quick Query
```bash
docker exec mysql_ascl_dev mysql -uroot -pascl_root_dev_password ascl_db_v4 -e "SELECT COUNT(*) FROM codes"
```

---

## 🔍 Verification

### Check Tables
```bash
mysql --defaults-group-suffix=_ascl -D ascl_db_v4 -e "SHOW TABLES;"
```

### Check Foreign Keys
```bash
mysql --defaults-group-suffix=_ascl -D ascl_db_v4 -e "
SELECT TABLE_NAME, CONSTRAINT_NAME, REFERENCED_TABLE_NAME
FROM information_schema.KEY_COLUMN_USAGE
WHERE TABLE_SCHEMA='ascl_db_v4' AND REFERENCED_TABLE_NAME IS NOT NULL;"
```

### Check Engine Types
```bash
mysql --defaults-group-suffix=_ascl -D ascl_db_v4 -e "
SELECT ENGINE, COUNT(*) FROM information_schema.TABLES
WHERE TABLE_SCHEMA='ascl_db_v4' GROUP BY ENGINE;"
```

---

## 🧪 Test Flask App

```bash
cd /home/demitri/repositories/ASCL/alt_ascl/source/ascl_net_app_project_home
python run_ascl_net_app.py --debug --port 5000
```

---

## ⚠️ Troubleshooting

### Container won't start
```bash
# Check if port is in use
sudo lsof -i :3307

# View logs
docker-compose logs mysql
```

### Can't connect
```bash
# Verify container is healthy
docker-compose ps

# Test connection
docker exec mysql_ascl_dev mysql -uascl_db -pascl_dev_password -e "SELECT 1"
```

### Reset everything
```bash
docker-compose down -v
./setup_dev_environment.sh
```

---

## 📊 Database Info

| Database | Purpose | Engine |
|----------|---------|--------|
| `ascl_db` | Original backup | MyISAM |
| `ascl_db_v4` | Upgraded schema | InnoDB |
| `ascl_wordpress` | WordPress content | InnoDB |
| `ascl_phpbb` | phpBB forum | InnoDB |

**Container**: `mysql_ascl_dev`
**Port**: `3307` (host) → `3306` (container)
**Version**: MySQL 8.0.42

---

## 📝 Files

- Setup Script: `./setup_dev_environment.sh`
- Docker Compose: `./docker-compose.yml`
- Full Docs: `./README_DEV_SETUP.md`
- Upgrade SQL: `../agents/DB_UPGRADE_PLAYBOOK.sql`
- Connection: `../ascl_core/database/connections/Trillian2DBConnection.py`
