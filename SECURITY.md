# Security Best Practices

## Credential Management

**NEVER hardcode credentials in configuration files or source code.**

### MySQL Credentials

Use `~/.my.cnf` for password-less authentication:

```ini
[client_ascl]
user=ascl_user
password=your_password_here
host=localhost
port=3307
```

**Important**:
- No quotes around values
- Set permissions: `chmod 600 ~/.my.cnf`
- Do NOT commit `.my.cnf` to version control

### Application Secrets (`secrets.cfg`)

Production secrets are stored in `/etc/ascl/secrets.cfg`, which is **not committed to the repository**. This file is loaded by Flask after the main config files and contains:

- `SECRET_KEY` - Flask session signing key
- `ADS_API_TOKEN` - NASA ADS API token
- `TYPESENSE_API_KEY` - Typesense search API key

**Setup:**
```bash
sudo mkdir -p /etc/ascl
sudo cp source/ascl_net_app_project_home/ascl_net_app/configuration_files/secrets.cfg.example /etc/ascl/secrets.cfg
sudo nano /etc/ascl/secrets.cfg   # Fill in actual values
sudo chown root:www-data /etc/ascl/secrets.cfg
sudo chmod 640 /etc/ascl/secrets.cfg
```

The app validates these secrets at startup and **refuses to start in production** if any are missing. Override the path with the `ASCL_SECRETS_FILE` environment variable.

A `secrets.cfg.example` template is committed to the repo for reference.

### Application Configuration

In `default.cfg` or `production.cfg`:

```ini
DB_PASSWORD = ''  # Empty string uses ~/.my.cnf
```

### Environment Variables

For production deployments, database credentials can use environment variables:

```bash
export ASCLDB_USER=ascl_user
export ASCLDB_PASSWORD=secure_password
export ASCLDB_HOST=localhost
export ASCLDB_PORT=3307
```

### Command-Line Access

```bash
# Use helper script (reads from ~/.my.cnf [client_ascl])
./scripts/mysql_ascl.sh

# Or use mysql directly
mysql --defaults-group-suffix=_ascl ascl_db
```

### Python Scripts

```python
import os
from ascl_core.database.DatabaseConnection import DatabaseConnection

# Option 1: Use empty password to read from ~/.my.cnf
db = DatabaseConnection(
    database_connection_string='mysql://ascl_user:@localhost:3307/ascl_db'
)

# Option 2: Use environment variables
password = os.environ.get('ASCLDB_PASSWORD', '')
connection_string = f'mysql://ascl_user:{password}@localhost:3307/ascl_db'
db = DatabaseConnection(database_connection_string=connection_string)
```

## Files to Keep Secure

The following are already in `.gitignore`:
```
.env
.env.*
*.key
*.pem
*_password*
secrets.cfg          # Actual secrets file (secrets.cfg.example IS committed)
```

**Important**: `production.cfg` no longer contains secrets. All secrets are in `/etc/ascl/secrets.cfg`.

## Docker Compose

Use `.env` file for Docker secrets:

```bash
# .env
ASCLDB_ROOT_PASSWORD=secure_root_password
ASCLDB_USER=ascl_user
ASCLDB_PASSWORD=secure_password
```

Reference in `docker-compose.yml`:
```yaml
environment:
  MYSQL_USER: ${ASCLDB_USER}
  MYSQL_PASSWORD: ${ASCLDB_PASSWORD}
```

## Production Checklist

- [x] Remove all hardcoded secrets from config files (moved to `/etc/ascl/secrets.cfg`)
- [x] App validates required secrets at startup (refuses to start if missing)
- [x] Redeploy script checks for secrets file before deploying
- [x] `secrets.cfg` excluded from repo via `.gitignore`
- [x] `secrets.cfg.example` template committed for reference
- [ ] Use environment variables or credential files for database
- [ ] Set `chmod 600` on credential files
- [ ] Use separate credentials for dev/staging/production
- [ ] Rotate passwords regularly
- [ ] Enable SSL/TLS for database connections
- [ ] Use principle of least privilege for database users
- [ ] Enable MySQL audit logging
- [ ] Regular security updates

---

*Last Updated: 2026-02-20*
