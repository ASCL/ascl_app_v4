# Quick Start Guide - ASCL Link Feature

**Full details in:** `SETUP_PLAN_LINK_FEATURE.md`

## Quick Setup Commands

### 1. Database Setup
```bash
# Connect to MySQL
mysql -h localhost -P 3307 -u root -p

# In MySQL prompt:
CREATE DATABASE IF NOT EXISTS ascl_db CHARACTER SET utf8mb3 COLLATE utf8mb3_general_ci;
CREATE USER 'ascl_db'@'localhost' IDENTIFIED BY 'your_password';
GRANT ALL PRIVILEGES ON ascl_db.* TO 'ascl_db'@'localhost';
FLUSH PRIVILEGES;
EXIT;

# Import schema
mysql -h localhost -P 3307 -u ascl_db -p ascl_db < ascl_db-schema-2025-10-30.sql
```

### 2. Update Config Files

**File:** `web_root/ascl_php_application/application/config/database.php`
```php
$db['default']['hostname'] = 'localhost:3307';
$db['default']['username'] = 'ascl_db';
$db['default']['password'] = 'your_password';
```

**File:** `web_root/ascl_php_application/application/config/config.php`
```php
$config['base_url'] = 'http://localhost:8080/';
```

### 3. Permissions
```bash
cd /home/demitri/repositories/ASCL/ascl_php_application/web_root/ascl_php_application
chmod -R 775 application/cache application/logs
```

### 4. Test
```bash
curl http://localhost:8080/
```

## Next: Create Link Tables

See **Part 2** in `SETUP_PLAN_LINK_FEATURE.md`

## Status Checklist

- [ ] Database created and schema loaded
- [ ] Config files updated
- [ ] nginx configured and running
- [ ] Can access http://localhost:8080/
- [ ] Can browse codes at /code/all
- [ ] Link tables created (link_types, code_links)
- [ ] Ready for code changes
