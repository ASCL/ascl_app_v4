# ASCL Flask Application Deployment Guide

This guide covers deploying the ASCL Flask application to a production environment. It is written for both human operators and AI agents.

**Location of this file**: `/home/demitri/repositories/ASCL/alt_ascl/deployment/`

## Overview

| Component | Location |
|-----------|----------|
| **This Directory** | `/home/demitri/repositories/ASCL/alt_ascl/deployment/` |
| **Development** | `/home/demitri/repositories/ASCL/alt_ascl/source/ascl_net_app_project_home` |
| **Production** | `/var/www/ascl_net_app` |
| **Dependencies** | `/var/www/dm-dbcore`, `/var/www/ascl_core` |
| **Server** | Uvicorn on port 5050 via systemd |
| **Reverse Proxy** | Nginx proxying `ascl.bistromath.net` to port 5050 |
| **Logs** | `/var/log/ascl_v4_uvicorn.log` |

## Files in This Directory

| File | Purpose | Install Location |
|------|---------|------------------|
| `ascl_net_app.service` | Systemd service unit | `/etc/systemd/system/` |
| `nginx_ascl_production.conf` | Nginx site configuration | `/etc/nginx/sites-available/ascl_production` |
| `redeploy.sh` | Script to sync updates from dev repo | Run directly from repo |
| `my.cnf.template` | MySQL credentials template | `/var/www/.my.cnf` |

**Related configuration files (in source tree):**

| File | Purpose | Install Location |
|------|---------|------------------|
| `secrets.cfg.example` | Template for application secrets | `/etc/ascl/secrets.cfg` |

The secrets template is at `source/ascl_net_app_project_home/ascl_net_app/configuration_files/secrets.cfg.example`.

---

## Initial Deployment (Fresh Server)

### Prerequisites

- Ubuntu 24.04 or similar Linux distribution
- Python 3.12+
- Nginx installed
- MySQL/MariaDB server accessible on port 3307
- `uv` package manager installed
- sudo access

### Step 1: Install System Dependencies

```bash
sudo apt-get update
sudo apt-get install -y python3-dev libmysqlclient-dev nginx
```

### Step 2: Create Production Directories

```bash
sudo mkdir -p /var/www/ascl_net_app
sudo mkdir -p /var/www/dm-dbcore
sudo mkdir -p /var/www/ascl_core
sudo mkdir -p /var/cache/uv
sudo chown www-data:www-data /var/www/ascl_net_app /var/www/dm-dbcore /var/www/ascl_core /var/cache/uv
```

### Step 3: Copy Application Files

```bash
# Main application
sudo rsync -av --exclude='venv' --exclude='.venv' --exclude='__pycache__' \
    --exclude='*.pyc' --exclude='.git' --exclude='logs/*.log' \
    --exclude='*.egg-info' --exclude='.uv' --exclude='.claude' \
    /home/demitri/repositories/ASCL/alt_ascl/source/ascl_net_app_project_home/ \
    /var/www/ascl_net_app/

# dm-dbcore dependency
sudo rsync -av --exclude='__pycache__' --exclude='*.pyc' --exclude='.git' \
    --exclude='.venv' --exclude='venv' --exclude='.claude' \
    /home/demitri/repositories/ASCL/dm-dbcore/ /var/www/dm-dbcore/

# ascl_core dependency
sudo rsync -av --exclude='__pycache__' --exclude='*.pyc' --exclude='.git' \
    --exclude='.venv' --exclude='venv' --exclude='.claude' \
    /home/demitri/repositories/ASCL/ascl_core/ /var/www/ascl_core/

# Set ownership
sudo chown -R www-data:www-data /var/www/ascl_net_app /var/www/dm-dbcore /var/www/ascl_core
```

### Step 4: Create Virtual Environment and Install Dependencies

```bash
cd /var/www/ascl_net_app
sudo -u www-data UV_CACHE_DIR=/var/cache/uv uv venv
sudo -u www-data UV_CACHE_DIR=/var/cache/uv uv pip install "/var/www/dm-dbcore/[mysql]"
sudo -u www-data UV_CACHE_DIR=/var/cache/uv uv pip install /var/www/ascl_core/
sudo -u www-data UV_CACHE_DIR=/var/cache/uv uv pip install -r requirements.txt
```

### Step 5: Configure Application Secrets

Create `/etc/ascl/secrets.cfg` with the required secrets:

```bash
sudo mkdir -p /etc/ascl
sudo cp /home/demitri/repositories/ASCL/alt_ascl/source/ascl_net_app_project_home/ascl_net_app/configuration_files/secrets.cfg.example /etc/ascl/secrets.cfg
sudo nano /etc/ascl/secrets.cfg  # Fill in actual values
sudo chown root:www-data /etc/ascl/secrets.cfg
sudo chmod 640 /etc/ascl/secrets.cfg
```

The secrets file must contain:
- `SECRET_KEY` - Flask session signing key (generate with `python -c "import secrets; print(secrets.token_hex(32))"`)
- `ADS_API_TOKEN` - NASA ADS API token for bibcode lookups
- `TYPESENSE_API_KEY` - Typesense search server API key

The app will refuse to start in production if any of these are missing. Override the default path (`/etc/ascl/secrets.cfg`) with the `ASCL_SECRETS_FILE` environment variable if needed.

### Step 6: Configure MySQL Credentials

Create `/var/www/.my.cnf` with the database credentials:

```bash
DEPLOY_DIR=/home/demitri/repositories/ASCL/alt_ascl/deployment
sudo cp $DEPLOY_DIR/my.cnf.template /var/www/.my.cnf
sudo nano /var/www/.my.cnf  # Edit to add the actual password
sudo chown www-data:www-data /var/www/.my.cnf
sudo chmod 600 /var/www/.my.cnf
```

### Step 7: Install Nginx Configuration

```bash
DEPLOY_DIR=/home/demitri/repositories/ASCL/alt_ascl/deployment
sudo cp $DEPLOY_DIR/nginx_ascl_production.conf /etc/nginx/sites-available/ascl_production
sudo ln -sf /etc/nginx/sites-available/ascl_production /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

### Step 8: Install and Start Systemd Service

```bash
DEPLOY_DIR=/home/demitri/repositories/ASCL/alt_ascl/deployment
sudo cp $DEPLOY_DIR/ascl_net_app.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable ascl_net_app
sudo systemctl start ascl_net_app
```

### Step 9: Create Log File

```bash
sudo touch /var/log/ascl_v4_uvicorn.log
sudo chown www-data:www-data /var/log/ascl_v4_uvicorn.log
```

---

## Redeployment (Updating from Development)

After making changes in the development repository, run the script directly from the repo:

```bash
sudo /home/demitri/repositories/ASCL/alt_ascl/deployment/redeploy.sh
```

**Note**: The script must be run with `sudo`. It uses `runuser` (not nested `sudo`) to run pip commands as www-data, so no password prompts occur during execution.

This script will:
1. Verify `/etc/ascl/secrets.cfg` exists (fails early if missing)
2. Stop the service
3. Sync all files from development (excluding venv, cache, etc.)
4. Update ownership
5. Reinstall dependencies
6. Start the service
7. Show status

---

## Verification

After deployment, verify everything is working:

```bash
# Check service status
sudo systemctl status ascl_net_app

# Test local endpoint
curl -I http://127.0.0.1:5050/

# Test public endpoint (if DNS is configured)
curl -I http://ascl.bistromath.net/

# Test static files
curl -I http://ascl.bistromath.net/static/css/style.css

# Check logs
tail -f /var/log/ascl_v4_uvicorn.log
sudo journalctl -u ascl_net_app -f
```

---

## Common Operations

### Restart the Service
```bash
sudo systemctl restart ascl_net_app
```

### View Logs
```bash
# Application logs
tail -f /var/log/ascl_v4_uvicorn.log

# Systemd journal
sudo journalctl -u ascl_net_app -f

# Nginx access logs
tail -f /var/log/nginx/ascl_production_access.log

# Nginx error logs
tail -f /var/log/nginx/ascl_production_error.log
```

### Stop the Service
```bash
sudo systemctl stop ascl_net_app
```

### Check if Port 5050 is in Use
```bash
sudo lsof -i :5050
# or
sudo ss -tlnp | grep 5050
```

---

## Troubleshooting

### Service Fails to Start

1. Check the logs:
   ```bash
   sudo journalctl -u ascl_net_app -n 50 --no-pager
   cat /var/log/ascl_v4_uvicorn.log
   ```

2. Common issues:
   - **Missing secrets**: The app requires `/etc/ascl/secrets.cfg` in production. See Step 5.
   - **Missing dependencies**: Run `uv pip install -r requirements.txt`
   - **Database connection**: Verify `/var/www/.my.cnf` has correct credentials
   - **Port already in use**: Check for existing processes on port 5050
   - **Permission issues**: Ensure www-data owns all files in `/var/www/ascl_net_app`

### Static Files Not Loading

1. Verify the path in nginx config matches:
   ```bash
   ls -la /var/www/ascl_net_app/ascl_net_app/static/
   ```

2. Check nginx error logs:
   ```bash
   tail -f /var/log/nginx/ascl_production_error.log
   ```

### Database Connection Errors

1. Verify MySQL is accessible:
   ```bash
   mysql --defaults-group-suffix=_ascl -e "SELECT 1"
   ```

2. Check the credentials file permissions:
   ```bash
   ls -la /var/www/.my.cnf
   # Should be: -rw------- www-data www-data
   ```

---

## AI Agent Instructions

When deploying or troubleshooting this application, follow these guidelines:

### For Fresh Deployment
1. Execute all steps in "Initial Deployment" section sequentially
2. Verify each step completes successfully before proceeding
3. If a step fails, check the troubleshooting section
4. Always verify the deployment at the end using the verification commands

### For Updates/Redeployment
1. Run the script from the repo: `sudo /home/demitri/repositories/ASCL/alt_ascl/deployment/redeploy.sh`
2. If the script fails, check logs and address the specific error
3. Common issues: missing new dependencies (add to requirements.txt)

### Key Environment Variables
- `FLASK_CONFIG=production.cfg` - Flask configuration file
- `ASCLDB_MYCNF_SECTION=client_ascl` - MySQL config section name
- `HOME=/var/www` - Required for www-data to find .my.cnf
- `UV_CACHE_DIR=/var/cache/uv` - uv package manager cache

### File Locations to Remember
- Application: `/var/www/ascl_net_app`
- Virtual environment: `/var/www/ascl_net_app/.venv`
- Service file: `/etc/systemd/system/ascl_net_app.service`
- Nginx config: `/etc/nginx/sites-available/ascl_production`
- Secrets file: `/etc/ascl/secrets.cfg` (SECRET_KEY, ADS_API_TOKEN, TYPESENSE_API_KEY)
- MySQL credentials: `/var/www/.my.cnf`
- Logs: `/var/log/ascl_v4_uvicorn.log`

### Dependencies (Local Packages)
This application depends on two local packages that are not on PyPI:
- `dm-dbcore` at `/var/www/dm-dbcore` (from `/home/demitri/repositories/ASCL/dm-dbcore`)
- `ascl_core` at `/var/www/ascl_core` (from `/home/demitri/repositories/ASCL/ascl_core`)

These must be installed before the main requirements.txt:
```bash
uv pip install "/var/www/dm-dbcore/[mysql]"
uv pip install /var/www/ascl_core/
uv pip install -r requirements.txt
```

---

## Architecture Notes

```
Internet
    │
    ▼
┌─────────────────┐
│     Nginx       │ (port 80)
│  Reverse Proxy  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│    Uvicorn      │ (port 5050, 4 workers)
│   ASGI Server   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Flask App      │
│ (via asgiref)   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   MySQL DB      │ (port 3307)
│   ascl_db_v4    │
└─────────────────┘
```

The application runs as a WSGI Flask app wrapped with asgiref to work with the Uvicorn ASGI server. Nginx handles static files directly and proxies dynamic requests to Uvicorn.
