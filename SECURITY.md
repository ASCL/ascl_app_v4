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

### Application Configuration

In `default.cfg` or `production.cfg`:

```ini
DB_PASSWORD = ''  # Empty string uses ~/.my.cnf
```

### Environment Variables

For production deployments, use environment variables:

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

Add to `.gitignore`:
```
.env
.env.*
*.key
*.pem
*_password*
config/production.cfg  # If it contains secrets
```

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

- [ ] Remove all hardcoded passwords from config files
- [ ] Use environment variables or credential files
- [ ] Set `chmod 600` on credential files
- [ ] Add credential files to `.gitignore`
- [ ] Use separate credentials for dev/staging/production
- [ ] Rotate passwords regularly
- [ ] Enable SSL/TLS for database connections
- [ ] Use principle of least privilege for database users
- [ ] Enable MySQL audit logging
- [ ] Regular security updates

---

*Last Updated: 2025-10-01*
