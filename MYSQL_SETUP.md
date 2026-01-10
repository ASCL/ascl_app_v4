# MySQL Database Setup Guide

This guide covers setting up MySQL for the ASCL.net application.

## Installing MySQL

### Ubuntu/Debian
```bash
sudo apt update
sudo apt install mysql-server
sudo mysql_secure_installation
```

### macOS
```bash
brew install mysql
brew services start mysql
mysql_secure_installation
```

### Check MySQL is running
```bash
sudo systemctl status mysql  # Linux
brew services list           # macOS
```

## Database Setup

### 1. Connect to MySQL as root
```bash
sudo mysql
# or
mysql -u root -p
```

### 2. Create database and user
```sql
-- Create the database
CREATE DATABASE ascl_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- Create user (change password!)
CREATE USER 'ascl_user'@'localhost' IDENTIFIED BY 'your_secure_password';

-- Grant privileges
GRANT ALL PRIVILEGES ON ascl_db.* TO 'ascl_user'@'localhost';

-- Apply changes
FLUSH PRIVILEGES;

-- Verify
SHOW DATABASES;
SELECT User, Host FROM mysql.user WHERE User='ascl_user';

-- Exit
EXIT;
```

### 3. Test connection
```bash
mysql -u ascl_user -p ascl_db
```

## Restore Database from Backup

The backup file `ascl_db_2025.09.30_bkup.sql.gz` is already in MySQL format.

### Decompress and restore
```bash
# Decompress the backup
gunzip -c ascl_db_2025.09.30_bkup.sql.gz > ascl_db_backup.sql

# Restore to MySQL
mysql -u ascl_user -p ascl_db < ascl_db_backup.sql

# Or do it in one step:
gunzip < ascl_db_2025.09.30_bkup.sql.gz | mysql -u ascl_user -p ascl_db
```

### Verify restoration
```bash
mysql -u ascl_user -p ascl_db
```

```sql
-- Show tables
SHOW TABLES;

-- Check schema (replace 'ascldb' with your schema if different)
USE ascl_db;
SHOW TABLES;

-- Count records in main table
SELECT COUNT(*) FROM codes;

-- Exit
EXIT;
```

## Configure Application

### Method 1: Using Configuration File (Recommended)

1. **Copy example configuration:**
   ```bash
   cd source/ascl_net_app_project_home/ascl_net_app/configuration_files/
   cp mysql_example.cfg development.cfg
   ```

2. **Edit configuration:**
   ```bash
   nano development.cfg
   ```

   Update these values:
   ```ini
   USING_SQLALCHEMY = True
   DB_TYPE = 'mysql'

   DB_DATABASE = 'ascl_db'
   DB_HOST = 'localhost'
   DB_USER = 'ascl_user'
   DB_PASSWORD = 'your_secure_password'  # Or leave empty for ~/.my.cnf
   DB_PORT = '3306'
   ```

3. **Run application:**
   ```bash
   export FLASK_CONFIG=development.cfg
   python run_ascl_net_app.py --debug
   ```

### Method 2: Using ~/.my.cnf (Password-less authentication)

1. **Create ~/.my.cnf:**
   ```bash
   nano ~/.my.cnf
   ```

   Add:
   ```ini
   [client]
   user=ascl_user
   password=your_secure_password
   host=localhost
   port=3306
   ```

2. **Set permissions:**
   ```bash
   chmod 600 ~/.my.cnf
   ```

3. **Update configuration file:**
   ```ini
   DB_PASSWORD = ''  # Empty string uses ~/.my.cnf
   ```

4. **Test connection:**
   ```bash
   mysql ascl_db
   ```

## Database Schema Notes

### Original WordPress Schema

The backup contains WordPress tables with prefix (typically `wp_`). The ASCL data is in a schema/database named `ascldb`.

### Important Tables
- `codes` - Main software entries
- `keywords` - Classification keywords
- `code_keywords` - Many-to-many relationship
- `codes_aliases` - Alternative names
- `citations` - Citation data
- `links` - External URLs
- `users` - User accounts

### Schema Mapping

If the backup uses a different schema structure, you may need to adjust the SQLAlchemy models in:
```
ascl_core/database/ascldb/ASCLModelClasses.py
```

## MySQL-Specific Configuration

### Character Set

Ensure UTF-8 support for international characters:

```sql
-- Check database charset
SELECT schema_name, default_character_set_name, default_collation_name
FROM information_schema.schemata
WHERE schema_name = 'ascl_db';

-- Change if needed
ALTER DATABASE ascl_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### Connection Charset

Add to connection string in `model/database.py` if needed:
```python
self.database_connection_string = 'mysql://{user}:{password}@{host}:{port}/{database}?charset=utf8mb4'.format(**self.db_config)
```

### Time Zone

```sql
-- Check timezone
SELECT @@global.time_zone, @@session.time_zone;

-- Set timezone if needed
SET GLOBAL time_zone = '+00:00';  # UTC
```

## Troubleshooting

### Can't connect to MySQL server

```bash
# Check if MySQL is running
sudo systemctl status mysql

# Start MySQL
sudo systemctl start mysql

# Check port
sudo netstat -tlnp | grep 3306
```

### Access denied for user

```bash
# Reset user password
sudo mysql

mysql> ALTER USER 'ascl_user'@'localhost' IDENTIFIED BY 'new_password';
mysql> FLUSH PRIVILEGES;
mysql> EXIT;
```

### Connection refused

Check bind-address in MySQL config:
```bash
sudo nano /etc/mysql/mysql.conf.d/mysqld.cnf
```

Ensure:
```ini
bind-address = 127.0.0.1  # For local connections only
# bind-address = 0.0.0.0  # For remote connections (caution!)
```

Restart MySQL:
```bash
sudo systemctl restart mysql
```

### "Unknown database" error

Verify database was created:
```sql
SHOW DATABASES LIKE 'ascl%';
```

### mysqlclient installation fails

Install development headers:

**Ubuntu/Debian:**
```bash
sudo apt install python3-dev default-libmysqlclient-dev build-essential
pip install mysqlclient
```

**macOS:**
```bash
brew install mysql
pip install mysqlclient
```

**Alternative:** Use PyMySQL (pure Python, no compilation):
```bash
pip install PyMySQL
```

Then change connection string in `model/database.py`:
```python
self.database_connection_string = 'mysql+pymysql://{user}:{password}@{host}:{port}/{database}'.format(**self.db_config)
```

## Performance Tuning

### MySQL Configuration

Edit `/etc/mysql/mysql.conf.d/mysqld.cnf`:

```ini
[mysqld]
# Connection settings
max_connections = 150

# Buffer sizes
innodb_buffer_pool_size = 1G  # Adjust based on available RAM
innodb_log_file_size = 256M

# Query cache (MySQL 5.7 and earlier)
query_cache_type = 1
query_cache_size = 64M

# Slow query log (for debugging)
slow_query_log = 1
slow_query_log_file = /var/log/mysql/slow.log
long_query_time = 2
```

Restart MySQL:
```bash
sudo systemctl restart mysql
```

### SQLAlchemy Connection Pool

The connection pool is configured in:
```
ascl_core/database/DatabaseConnection.py
```

Adjust pool size based on Uvicorn workers:
```python
me.engine = create_engine(
    me.database_connection_string,
    pool_size=10,        # Number of permanent connections
    max_overflow=20,     # Additional connections when needed
    pool_pre_ping=True,  # Verify connections before use
    echo=False
)
```

## Migration to PostgreSQL (Future)

When ready to migrate to PostgreSQL:

1. Use `pgloader` to migrate:
   ```bash
   sudo apt install pgloader
   pgloader mysql://ascl_user:pass@localhost/ascl_db postgresql://ascl_user:pass@localhost/ascl_db
   ```

2. Or manually export/import:
   ```bash
   # Export from MySQL
   mysqldump -u ascl_user -p ascl_db > ascl_dump.sql

   # Convert and import to PostgreSQL
   # (requires conversion tool or manual editing)
   ```

3. Update configuration:
   ```ini
   DB_TYPE = 'postgresql'
   DB_PORT = '5432'
   ```

## Additional Resources

- MySQL Documentation: https://dev.mysql.com/doc/
- SQLAlchemy MySQL Dialect: https://docs.sqlalchemy.org/en/20/dialects/mysql.html
- mysqlclient: https://github.com/PyMySQL/mysqlclient

---

*Last Updated: 2025-10-01*
