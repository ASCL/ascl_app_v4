# ASCL.net Deployment Guide

Two deployment targets are supported:

- **VPS** — Nginx → Uvicorn (4 workers) → systemd. Artifacts in `deployments/{systemd,nginx}/`.
- **cPanel** — Phusion Passenger. Artifacts in `deployments/passenger/`.

Both are managed through `bin/ascl` (see top-level `README.md` for CLI commands: `restart`, `redeploy`, `status`, `test`, `dumpdb`, `typesense`, `linkcheck`). This document covers the environment-variable and credentials side of both targets. For a cPanel-specific walkthrough see `PRODUCTION_DEPLOYMENT.md`.

## Environment Configuration

### Local Development

For local development, use the `.env` file:

```bash
# .env (local development only)
ASCLDB_MYCNF_SECTION=client_ascl
```

**Important:** The `.env` file is **only** loaded by `run_ascl_net_app.py` (development script). Production uses `asgi.py` which does NOT load `.env`, ensuring it's never accidentally used in production.

Run the development server:
```bash
python run_ascl_net_app.py --host 0.0.0.0 --port 6444
```

You'll see:
```
✓ [DEV] Loaded environment variables from /path/to/.env
```

---

### Production Deployment (systemd)

For production deployment using systemd, environment variables are configured in the service file:

**File:** `deployments/systemd/ascl_net_app.service`

```ini
[Service]
Environment="ASCLDB_MYCNF_SECTION=client_ascl"
```

**Note:** Production uses `asgi.py` as the entry point (via uvicorn), which does NOT load `.env` files.

**Deployment steps:**

1. Copy service file to systemd:
   ```bash
   sudo cp deployments/systemd/ascl_net_app.service /etc/systemd/system/
   ```

2. Reload systemd:
   ```bash
   sudo systemctl daemon-reload
   ```

3. Enable and start service:
   ```bash
   sudo systemctl enable ascl_net_app
   sudo systemctl start ascl_net_app
   ```

4. Check status:
   ```bash
   sudo systemctl status ascl_net_app
   ```

---

### Production Deployment (cPanel + Passenger)

On cPanel the entry point is `deployments/passenger/passenger_wsgi.py`, which sets
`FLASK_CONFIG` and any needed env vars *inside* the file before importing `create_app`
(there's no systemd `Environment=` directive available). Typical contents:

```python
import os, sys, pymysql
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
pymysql.install_as_MySQLdb()
os.environ['FLASK_CONFIG']        = 'ascl_net.cfg'
os.environ['ASCLDB_MYCNF_SECTION'] = 'client_ascl'
os.environ['ASCL_SECRETS_FILE']   = '/itss/home/<account>/secrets/secrets.cfg'
from ascl_net_app import create_app
application = create_app(debug=False)
```

Restart Passenger after changes: `touch ~/ascl_app_v4/tmp/restart.txt`
(or use `ascl restart cpanel`). See `PRODUCTION_DEPLOYMENT.md` for full cPanel setup.

---

## Database Credentials

The app reads database credentials from `~/.my.cnf` based on the section specified in `ASCLDB_MYCNF_SECTION`.

**Example `~/.my.cnf`:**

```ini
[client_ascl]
host = 127.0.0.1
port = 3307                # dev Docker MySQL; cPanel uses 3306
user = ascl_user
password = your_secure_password
database = ascl_db_v4
```

**Security Notes:**
- Set proper file permissions: `chmod 600 ~/.my.cnf`
- Never commit `.my.cnf` to version control
- Use different sections for dev/staging/production

---

## Environment Variables Reference

| Variable | Description | Example | Required |
|----------|-------------|---------|----------|
| `ASCLDB_MYCNF_SECTION` | Section in ~/.my.cnf to use | `client_ascl` | Yes |
| `ASCLDB_HOST` | Database host (overrides .my.cnf) | `127.0.0.1` | No |
| `ASCLDB_PORT` | Database port (overrides .my.cnf) | `3306` | No |
| `ASCLDB_USER` | Database user (overrides .my.cnf) | `ascl_user` | No |
| `ASCLDB_PASSWORD` | Database password (overrides .my.cnf) | - | No |
| `ASCLDB_DATABASE` | Database name (overrides .my.cnf) | `ascl_db_v4` | No |
| `ASCL_SECRETS_FILE` | Path to `secrets.cfg` (cPanel override) | `~/secrets/secrets.cfg` | No |
| `FLASK_CONFIG` | Flask config file to load | `ascl_net.cfg` | Production |

---

## Troubleshooting

### Connection Issues

If you see "Access denied" errors:

1. Check the section name matches:
   ```bash
   echo $ASCLDB_MYCNF_SECTION
   ```

2. Verify `.my.cnf` has the correct section:
   ```bash
   cat ~/.my.cnf | grep -A5 "\[client_ascl\]"
   ```

3. Test MySQL connection manually:
   ```bash
   mysql --defaults-group-suffix=_ascl
   ```

### Service Not Starting

Check logs:
```bash
sudo journalctl -u ascl_net_app -f
```

Check environment variables are loaded:
```bash
sudo systemctl show ascl_net_app | grep Environment
```
