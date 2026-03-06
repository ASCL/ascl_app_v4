# Production Deployment Guide

## Overview

This document describes the production deployment setup for the ASCL.net Flask application. This is a **development server production deployment** - it runs on your current server with the intent to migrate to a cPanel/Apache server later.

## Quick Reference

**Public Access:**
- URL: http://ascl.bistromath.net
- Server IP: 38.49.210.20

**Management Commands:**
```bash
./start_production.sh start     # Start the app
./start_production.sh stop      # Stop the app
./start_production.sh restart   # Restart the app
./start_production.sh status    # Check status
```

**Logs:**
```bash
tail -f logs/production.log                              # App logs
sudo tail -f /var/log/nginx/ascl_production_access.log  # Nginx access
sudo tail -f /var/log/nginx/ascl_production_error.log   # Nginx errors
```

## Current Setup

- **Public Domain**: ascl.bistromath.net (publicly accessible)
- **Port**: 5050 (internal, proxied by Nginx)
- **Host**: 127.0.0.1 (localhost only, accessed via Nginx)
- **Database**: `ascl_db_v4` (read-only copy, separate from development)
- **Workers**: 2 Uvicorn workers
- **Configuration**: `production.cfg`
- **Server**: Uvicorn (ASGI) with WSGI-to-ASGI adapter (asgiref)
- **Reverse Proxy**: Nginx (handles public HTTP requests)

### Deployment Architecture

```
Internet
    ↓
DNS: ascl.bistromath.net → 38.49.210.20
    ↓
Nginx (Port 80)
    ↓ (reverse proxy)
Uvicorn (127.0.0.1:5050)
    ↓ (asgiref: WSGI → ASGI)
Flask Application
    ↓
MySQL Database (ascl_db_v4, Port 3307)
```

**Request Flow:**
1. User visits http://ascl.bistromath.net
2. DNS resolves to server IP (38.49.210.20)
3. Nginx receives request on port 80
4. Nginx proxies request to Uvicorn (127.0.0.1:5050)
5. Uvicorn uses asgiref to convert ASGI → WSGI
6. Flask processes request, queries MySQL database
7. Response flows back through the chain

## Quick Start

### Starting the Production App

```bash
cd /home/demitri/repositories/ASCL/alt_ascl/source/ascl_net_app_project_home
./start_production.sh start
```

### Stopping the Production App

```bash
./start_production.sh stop
```

### Restarting the Production App

```bash
./start_production.sh restart
```

### Checking Status

```bash
./start_production.sh status
```

## Access

- **Public URL**: http://ascl.bistromath.net (via Nginx reverse proxy)
- **Direct Access**: http://127.0.0.1:5050 (localhost only)
- **Server IP**: 38.49.210.20

## Database Configuration

The production deployment uses a **separate database** (`ascl_db_v4`) to avoid interference with development work.

**Database Details:**
- Database: `ascl_db_v4`
- User: `ascl_db`
- Host: 127.0.0.1
- Port: 3307
- Credentials: Uses `~/.my.cnf` [client_ascl] section

**Read-Only Deployment:**
The current production deployment is effectively read-only - it serves content from the database but doesn't allow edits through the web interface (admin editing features not yet implemented).

## Configuration Files

### Main Configuration

File: `ascl_net_app/configuration_files/production.cfg`

Key settings:
- Database: ascl_db_v4
- Debug: Disabled
- SQL Query Logging: Disabled
- Session cookies: HTTP-only, SameSite=Lax

### Secrets Configuration

File: `/etc/ascl/secrets.cfg` (not in repo)

Secrets (`SECRET_KEY`, `ADS_API_TOKEN`, `TYPESENSE_API_KEY`) are loaded from an external file that is not committed to the repository. See `ascl_net_app/configuration_files/secrets.cfg.example` for the template.

The app refuses to start in production if required secrets are missing. Override the default path with `ASCL_SECRETS_FILE` env var.

### Startup Script

File: `start_production.sh`

Features:
- Start/stop/restart/status commands
- PID file management
- Automatic health checks
- Background process management
- Logging to `logs/production.log`

## ASGI Configuration

The Flask application is wrapped with `asgiref.wsgi.WsgiToAsgi` to run on Uvicorn (ASGI server).

**File**: `asgi.py`

**Required Dependencies:**
- `uvicorn[standard]>=0.27.0` - ASGI server with performance optimizations
- `asgiref>=3.7.0` - WSGI-to-ASGI adapter (Flask → Uvicorn compatibility)

**Installation:**
```bash
pip install -r requirements.txt
```

**Why asgiref?**
Flask is a WSGI application, but Uvicorn is an ASGI server. The `asgiref.wsgi.WsgiToAsgi` adapter bridges this gap, allowing Flask to run on the modern, high-performance Uvicorn server. Without this adapter, you'll get a `TypeError: Flask.__call__() missing 1 required positional argument: 'start_response'` error.

## Logs

Production logs are written to:
```
logs/production.log
```

View live logs:
```bash
tail -f logs/production.log
```

## Nginx Reverse Proxy

Nginx is **installed and running** as a reverse proxy for public access.

**File**: `nginx_production.cfg`
**Domain**: ascl.bistromath.net
**Status**: ✓ Active and configured

### Nginx Configuration:

The Nginx configuration is installed at:
- **Config file**: `/etc/nginx/sites-available/ascl_production`
- **Enabled**: `/etc/nginx/sites-enabled/ascl_production`

### Managing Nginx:

**Reload after config changes:**
```bash
sudo nginx -t  # Test configuration
sudo systemctl reload nginx  # Apply changes
```

**View Nginx logs:**
```bash
# Error log
sudo tail -f /var/log/nginx/ascl_production_error.log

# Access log
sudo tail -f /var/log/nginx/ascl_production_access.log
```

### Nginx Features:
- ✓ Reverse proxy to port 5050
- ✓ Static file serving (faster than Flask)
- ✓ Request buffering
- ✓ Error page handling
- ✓ Dedicated access/error logging
- ✓ Public access via ascl.bistromath.net

## Updating the Production App

When you make changes to the code:

1. Test in development mode first:
   ```bash
   python run_ascl_net_app.py --debug
   ```

2. Restart production to apply changes:
   ```bash
   ./start_production.sh restart
   ```

3. Check logs for errors:
   ```bash
   tail -f logs/production.log
   ```

## Database Updates

The production database (`ascl_db_v4`) is a **snapshot**. If you need to update it with changes from development:

### Option 1: Full Database Refresh
```bash
# Dump development database
mysqldump --defaults-group-suffix=_ascl ascl_db > /tmp/ascl_db_backup.sql

# Stop production app
./start_production.sh stop

# Restore to production database
mysql --defaults-group-suffix=_ascl_root ascl_db_v4 < /tmp/ascl_db_backup.sql

# Start production app
./start_production.sh start
```

### Option 2: Incremental Updates
Run specific SQL commands against `ascl_db_v4` using:
```bash
mysql --defaults-group-suffix=_ascl ascl_db_v4 -e "YOUR SQL HERE"
```

## Troubleshooting

### App Won't Start

Check logs:
```bash
tail -50 logs/production.log
```

Common issues:
- Port 5050 already in use
- Database connection failed
- Missing dependencies

### App Returns 500 Errors

Check logs for Python tracebacks:
```bash
tail -100 logs/production.log | grep -A 10 "ERROR:"
```

### Database Connection Issues

Test database connectivity:
```bash
mysql --defaults-group-suffix=_ascl -e "SELECT COUNT(*) FROM ascl_db_v4.codes;"
```

### Performance Issues

Adjust worker count in `start_production.sh`:
```bash
WORKERS=4  # Increase for more concurrency (max: 2x CPU cores)
```

## Migration to cPanel/Apache

When you're ready to migrate to the production cPanel/Apache server:

1. **Export the database**:
   ```bash
   mysqldump --defaults-group-suffix=_ascl ascl_db_v4 > ascl_db_v4_export.sql
   ```

2. **Archive the application**:
   ```bash
   tar -czf ascl_net_app.tar.gz ascl_net_app/
   ```

3. **On cPanel server**:
   - Import database via phpMyAdmin or command line
   - Extract application files
   - Configure Apache with WSGI (mod_wsgi)
   - Update `production.cfg` with new database credentials
   - Set up Python virtual environment

4. **Alternative**: Use Uvicorn behind Apache as reverse proxy (similar to current Nginx setup)

## Security Notes

### Current Security Measures

- ✓ Secrets externalized to `/etc/ascl/secrets.cfg` (not in repo)
- ✓ App validates required secrets at startup (refuses to start if missing)
- ✓ Session cookies are HTTP-only (prevents XSS)
- ✓ Database credentials stored in `~/.my.cnf` (not in code)
- ✓ Admin authentication uses bcrypt password hashing
- ✓ App bound to localhost only (127.0.0.1:5050), not directly accessible
- ✓ All public traffic routed through Nginx reverse proxy
- ✓ Nginx handles request buffering and validation

### Public Access Considerations

Since the app is **publicly accessible** at http://ascl.bistromath.net:

1. **Firewall**: Ensure ports 80 (HTTP) and 443 (HTTPS) are open
2. **Rate Limiting**: Consider adding Nginx rate limiting for protection
3. **HTTPS**: Strongly recommended for production (see SSL/HTTPS section below)
4. **Admin Access**: Admin login is publicly accessible - ensure strong passwords
5. **Database**: Read-only deployment limits exposure (no public editing)

### Recommended: Enable HTTPS

For public deployments, HTTPS is strongly recommended:

```bash
# Install Let's Encrypt certbot
sudo apt install certbot python3-certbot-nginx

# Obtain SSL certificate (automatically updates Nginx config)
sudo certbot --nginx -d ascl.bistromath.net

# Auto-renewal is handled by certbot timer
sudo systemctl status certbot.timer
```

After enabling HTTPS:
1. Update `production.cfg`: Set `SESSION_COOKIE_SECURE = True`
2. Restart the app: `./start_production.sh restart`

## Next Steps

### Recommended Improvements

1. ✓ ~~**Public Access**: Configure Nginx for public accessibility~~ (COMPLETED)
2. **SSL/HTTPS**: Configure SSL certificates for Nginx (Let's Encrypt) - RECOMMENDED for public deployment
3. **Monitoring**: Set up monitoring/alerting (optional: Sentry)
4. **Backups**: Schedule regular database backups
5. **Systemd Service**: Create systemd unit for automatic startup on reboot (optional)
6. **Rate Limiting**: Add Nginx rate limiting to prevent abuse
7. **Admin Interface**: Complete admin editing features before final migration
8. **Testing**: Full end-to-end testing of all public features

### Future Migration

When migrating to cPanel/Apache production server:
- Export `ascl_db_v4` database
- Archive application files
- Configure Apache/mod_wsgi or Uvicorn as reverse proxy
- Update DNS to point to new server
- Set up SSL certificates on new server

---

## Deployment Status

**Created**: 2025-12-29
**Last Updated**: 2025-12-29

**Configuration:**
- Public URL: http://ascl.bistromath.net
- Internal Port: 5050
- Database: ascl_db_v4 (4,481 codes)
- Server: Uvicorn + Nginx reverse proxy

**Status**: ✓ **LIVE and publicly accessible**

**Verified Endpoints:**
- ✓ Homepage (/)
- ✓ Browse (/browse)
- ✓ Search (/search)
- ✓ About (/about)
- ✓ Code detail pages (/code/*)
- ✓ News pages (/news)
- ✓ Admin interface (/admin)
