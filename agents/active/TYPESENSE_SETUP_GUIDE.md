# Typesense Setup Guide for ASCL
## Complete Setup from Scratch

**Last Updated**: 2025-12-02
**Version**: 1.0
**Status**: Phases 1 & 2 Complete, Ready for Production Use

---

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Installation](#installation)
4. [Initial Setup](#initial-setup)
5. [Populating the Index](#populating-the-index)
6. [Keeping the Index Updated](#keeping-the-index-updated)
7. [Testing and Verification](#testing-and-verification)
8. [Production Deployment](#production-deployment)
9. [Troubleshooting](#troubleshooting)
10. [Maintenance](#maintenance)

---

## Overview

**What is Typesense?**

Typesense is an open-source, typo-tolerant search engine optimized for instant search experiences. For ASCL, it provides:

- ⚡ **Lightning-fast search** (< 50ms response times)
- 🔍 **Typo tolerance** (automatically corrects "einstien" → "Einstein")
- 🎯 **Relevance ranking** (best matches first)
- ✨ **Result highlighting** (shows matching text)
- 📊 **Faceted search** (filter by keywords, year, etc.)
- 🛡️ **Automatic fallback** to MySQL if Typesense is unavailable

**Current Implementation Status**:
- ✅ **Phase 1**: Server installed, collection created, 3,984 codes indexed
- ✅ **Phase 2**: Flask integration with automatic MySQL fallback
- ⏳ **Phase 3**: Instant search UI (type-ahead) - Not yet implemented
- ⏳ **Phase 4**: Real-time sync - Not yet implemented

**Architecture**:
```
MySQL (Source of Truth)
   ↓
Typesense (Search Index)
   ↓
Flask App (Searches Typesense, falls back to MySQL)
   ↓
User
```

---

## Prerequisites

### System Requirements
- **OS**: Linux (tested on Ubuntu/Debian)
- **RAM**: 256MB minimum (62MB currently used for 3,984 documents)
- **Disk**: 1GB free space
- **Python**: 3.8+
- **MySQL**: 8.0+ (with ASCL database)

### Required Python Libraries
```bash
pip install typesense requests
```

### Access Requirements
- MySQL database access (via `~/.my.cnf` with `[client_ascl]` section)
- Ability to run services on port 8108 (or configure different port)

---

## Installation

### Option 1: Native Binary (Recommended for Production)

This is the current deployment method on the ASCL server.

**Step 1: Download Typesense**

```bash
# Download latest version (currently using v29.0)
cd /tmp
wget https://dl.typesense.org/releases/29.0/typesense-server-29.0-linux-amd64.tar.gz

# Extract binary
tar -xzf typesense-server-29.0-linux-amd64.tar.gz

# Move to system location
sudo mv typesense-server /usr/bin/
sudo chmod +x /usr/bin/typesense-server
```

**Step 2: Create Directories**

```bash
# Data directory
sudo mkdir -p /var/lib/typesense
sudo mkdir -p /var/log/typesense

# Configuration directory
sudo mkdir -p /etc/typesense
```

**Step 3: Generate API Key**

```bash
# Generate a secure random API key
openssl rand -base64 32

# Example output (use your own!):
# oWBN1v9zT9C3ZM48gblWobm4ibxcrFcn11hGpb3HiPzT9UOL
```

**Step 4: Create Configuration File**

Create `/etc/typesense/typesense-server.ini`:

```ini
[server]
api-address = 0.0.0.0
api-port = 8108
data-dir = /var/lib/typesense
log-dir = /var/log/typesense
api-key = YOUR_API_KEY_HERE
enable-cors = true
```

**Step 5: Create Systemd Service**

Create `/etc/systemd/system/typesense-server.service`:

```ini
[Unit]
Description=Typesense Search Server
After=network.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/var/lib/typesense
ExecStart=/usr/bin/typesense-server --config=/etc/typesense/typesense-server.ini
Restart=on-failure
RestartSec=5
StandardOutput=append:/var/log/typesense/typesense.log
StandardError=append:/var/log/typesense/typesense-error.log

[Install]
WantedBy=multi-user.target
```

**Step 6: Start Service**

```bash
# Set permissions
sudo chown -R www-data:www-data /var/lib/typesense
sudo chown -R www-data:www-data /var/log/typesense

# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable typesense-server
sudo systemctl start typesense-server

# Check status
sudo systemctl status typesense-server

# Verify it's running
curl http://localhost:8108/health
# Expected output: {"ok":true}
```

### Option 2: Docker (Recommended for Development)

```bash
# Start Typesense in Docker
docker run -d \
  --name typesense \
  -p 8108:8108 \
  -v /tmp/typesense-data:/data \
  -e TYPESENSE_API_KEY=your_development_key_here \
  -e TYPESENSE_DATA_DIR=/data \
  typesense/typesense:29.0

# Verify it's running
curl http://localhost:8108/health
```

### Option 3: Typesense Cloud (Managed Service)

1. Sign up at https://cloud.typesense.org/
2. Create a new cluster
3. Note the hostname and API key
4. No server management required

**Pricing**: ~$22/month for smallest instance (0.5 CPU, 2GB RAM)

---

## Initial Setup

Once Typesense server is running, create the search collection.

### Step 1: Navigate to Agents Directory

```bash
cd /home/demitri/repositories/ASCL/alt_ascl/agents
```

### Step 2: Update API Key in Setup Script

Edit `typesense_setup_collection.py` and update line 16:

```python
TYPESENSE_API_KEY = 'YOUR_API_KEY_HERE'  # Replace with your actual key
```

Also update `typesense_import_data.py` line 27 with the same key.

### Step 3: Create Collection

```bash
python3 typesense_setup_collection.py
```

**Expected Output**:
```
============================================================
ASCL Typesense Collection Setup
============================================================

✅ Typesense is running and healthy

Creating 'codes' collection...
✅ Successfully created 'codes' collection

✅ Collection 'codes' information:
  - Name: codes
  - Number of documents: 0
  - Number of fields: 11
  - Default sorting field: time_added

============================================================
✅ Setup complete!
============================================================

Next steps:
1. Run the import script to populate the collection with data
2. Test search queries via the Typesense API
3. Integrate search into Flask application
```

### Step 4: Verify Collection

```bash
curl -H "X-TYPESENSE-API-KEY: YOUR_API_KEY" \
  http://localhost:8108/collections/codes | jq
```

---

## Populating the Index

### Initial Data Import

**Step 1: Run Import Script**

```bash
cd /home/demitri/repositories/ASCL/alt_ascl/agents
python3 typesense_import_data.py
```

**Parameters**:
- `--batch-size N`: Number of documents per batch (default: 100)
- `--limit N`: Import only N codes (for testing)
- `--published-only`: Import only published codes (default: True)

**Example - Test with 10 codes**:
```bash
python3 typesense_import_data.py --limit 10
```

**Example - Full import**:
```bash
python3 typesense_import_data.py --batch-size 100
```

**Expected Output**:
```
============================================================
ASCL Typesense Data Import
============================================================

Connecting to MySQL database...
✅ Database connected

Loading keywords mapping from database...
✅ Loaded keywords for 196 codes

Querying codes from database...
  Filtering: published=1 only
✅ Found 3984 codes to import

Importing in batches of 100...

Progress: 100/3984 codes (100 success, 0 errors)
Progress: 200/3984 codes (200 success, 0 errors)
...
Progress: 3984/3984 codes (3984 success, 0 errors)

============================================================
✅ Import complete!
============================================================
Total codes processed: 3984
Successfully imported: 3984
Errors: 0

Verifying collection...
✅ Collection 'codes' now has 3984 documents
```

**Import Time**: ~30 seconds for 3,984 codes

### Verify Import

```bash
# Count documents
curl -H "X-TYPESENSE-API-KEY: YOUR_API_KEY" \
  http://localhost:8108/collections/codes | grep num_documents

# Test search
curl -H "X-TYPESENSE-API-KEY: YOUR_API_KEY" \
  "http://localhost:8108/collections/codes/documents/search?q=python&query_by=title,abstract,credit" | jq '.found'
```

---

## Keeping the Index Updated

The index needs to stay synchronized with MySQL database changes. There are three approaches:

### Approach 1: Manual Re-import (Current Default)

**When to use**: After bulk database changes, or periodically (daily/weekly)

**How**:
```bash
cd /home/demitri/repositories/ASCL/alt_ascl/agents
python3 typesense_import_data.py
```

This will **upsert** all documents (update existing, insert new). Safe to run anytime.

**Pros**:
- ✅ Simple and reliable
- ✅ Catches all changes
- ✅ No code changes needed

**Cons**:
- ❌ Not real-time
- ❌ Manual process

### Approach 2: Scheduled Sync (Recommended for Production)

**Setup a cron job** to run import script daily:

```bash
# Edit crontab
crontab -e

# Add this line (runs at 2 AM daily)
0 2 * * * cd /home/demitri/repositories/ASCL/alt_ascl/agents && /usr/bin/python3 typesense_import_data.py >> /var/log/typesense-import.log 2>&1
```

**Pros**:
- ✅ Automatic
- ✅ Predictable schedule
- ✅ No code changes needed

**Cons**:
- ❌ Not real-time (up to 24h delay)

### Approach 3: Real-Time Sync (Future - Phase 4)

**Not yet implemented**. Will require:

1. **Sync hooks** in Flask admin routes (create/update/delete code)
2. **Sync service** to push changes to Typesense
3. **Fallback** to background sync for missed updates

**Implementation Plan** (from `TYPESENSE_IMPLEMENTATION_PLAN.md`):

Create `ascl_core/search/TypesenseSync.py`:

```python
class TypesenseSync:
    @staticmethod
    def index_code(code):
        """Index or update a single code in Typesense."""
        # Convert code to Typesense document
        # Upsert to Typesense
        pass

    @staticmethod
    def delete_code(code_pk):
        """Delete a code from Typesense."""
        # Delete by PK
        pass
```

Then add sync calls to admin routes:

```python
# In admin controller
from ascl_core.search.TypesenseSync import TypesenseSync

@admin_page.route("/admin/insert_code", methods=['POST'])
def insert_code():
    # ... create code in MySQL ...
    session.add(new_code)
    session.commit()

    # Sync to Typesense
    TypesenseSync.index_code(new_code)

    return redirect('/admin/unpublished')
```

**Pros**:
- ✅ Real-time updates
- ✅ Search always current

**Cons**:
- ❌ More complex
- ❌ Requires code changes
- ❌ Need error handling

**Status**: Planned for Phase 4, not yet implemented

---

## Testing and Verification

### Basic Health Check

```bash
curl http://localhost:8108/health
# Expected: {"ok":true}
```

### Check Collection Stats

```bash
curl -H "X-TYPESENSE-API-KEY: YOUR_API_KEY" \
  http://localhost:8108/collections/codes | jq
```

**Expected fields**:
- `num_documents`: Should match number of published codes
- `name`: "codes"
- `default_sorting_field`: "time_added"

### Test Searches

**1. Basic text search**:
```bash
curl -H "X-TYPESENSE-API-KEY: YOUR_API_KEY" \
  "http://localhost:8108/collections/codes/documents/search?q=python&query_by=title,abstract,credit" | jq '.found'
# Should return number like 812
```

**2. Typo tolerance test**:
```bash
curl -H "X-TYPESENSE-API-KEY: YOUR_API_KEY" \
  "http://localhost:8108/collections/codes/documents/search?q=einstien&query_by=title,abstract,credit" | jq '.hits[0].document.title'
# Should find Einstein-related codes despite misspelling
```

**3. Author search**:
```bash
curl -H "X-TYPESENSE-API-KEY: YOUR_API_KEY" \
  "http://localhost:8108/collections/codes/documents/search?q=Smith&query_by=credit" | jq '.found'
# Should find codes by authors named Smith
```

**4. Faceted search**:
```bash
curl -H "X-TYPESENSE-API-KEY: YOUR_API_KEY" \
  "http://localhost:8108/collections/codes/documents/search?q=*&query_by=title&facet_by=keywords&max_facet_values=10" | jq '.facet_counts'
# Should return top 10 keywords with counts
```

### Test Flask Integration

**1. Start Flask app**:
```bash
cd /home/demitri/repositories/ASCL/alt_ascl/source/ascl_net_app_project_home
python run_ascl_net_app.py --debug --port 60661
```

**2. Test search endpoint**:
```bash
curl "http://127.0.0.1:60661/search?q=python"
# Should return HTML with search results
# Look for "via Typesense" indicator in output
```

**3. Test fallback** (stop Typesense, search should still work via MySQL):
```bash
sudo systemctl stop typesense-server
curl "http://127.0.0.1:60661/search?q=python"
# Should return HTML with "MySQL fallback" indicator

# Restart Typesense
sudo systemctl start typesense-server
```

---

## Production Deployment

### Flask Configuration

**File**: `ascl_net_app/configuration_files/production.cfg`

Add/verify these settings:

```ini
# Typesense Search Configuration
USING_TYPESENSE = True
TYPESENSE_HOST = 'localhost'  # or remote server hostname
TYPESENSE_PORT = 8108
TYPESENSE_PROTOCOL = 'http'   # use 'https' for remote servers
TYPESENSE_API_KEY = 'YOUR_PRODUCTION_API_KEY'
TYPESENSE_COLLECTION = 'codes'
TYPESENSE_FALLBACK_TO_MYSQL = True  # Enable MySQL fallback
```

### Environment Variables (Alternative)

For better security, use environment variables instead of hardcoding keys:

```bash
# In .env file (not in git)
export TYPESENSE_API_KEY="your_production_api_key_here"
export TYPESENSE_HOST="localhost"
```

Then in config:
```python
import os
TYPESENSE_API_KEY = os.environ.get('TYPESENSE_API_KEY', 'fallback_key')
```

### Firewall Configuration

```bash
# Allow Typesense port only from localhost (if on same server)
sudo ufw allow from 127.0.0.1 to any port 8108

# Or allow from specific IP if remote
sudo ufw allow from <flask-server-ip> to any port 8108
```

### Nginx Reverse Proxy (Optional)

If you want to expose Typesense via HTTPS:

**File**: `/etc/nginx/sites-available/ascl.net`

```nginx
# Typesense proxy
location /typesense/ {
    proxy_pass http://localhost:8108/;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection 'upgrade';
    proxy_set_header Host $host;
    proxy_cache_bypass $http_upgrade;

    # Security: Only allow from Flask server IP
    allow <flask-server-ip>;
    deny all;
}
```

### Monitoring

**1. Set up health check monitoring**:

Create `/usr/local/bin/check-typesense.sh`:
```bash
#!/bin/bash
if ! curl -f http://localhost:8108/health > /dev/null 2>&1; then
    echo "Typesense is down!" | mail -s "ASCL Typesense Alert" admin@ascl.net
    sudo systemctl restart typesense-server
fi
```

Add to crontab:
```bash
*/5 * * * * /usr/local/bin/check-typesense.sh
```

**2. Log rotation**:

Create `/etc/logrotate.d/typesense`:
```
/var/log/typesense/*.log {
    daily
    rotate 7
    compress
    delaycompress
    notifempty
    missingok
    create 0644 www-data www-data
}
```

---

## Troubleshooting

### Problem: Typesense won't start

**Check logs**:
```bash
sudo journalctl -u typesense-server -n 50
tail -f /var/log/typesense/typesense-error.log
```

**Common issues**:
1. **Port already in use**: Check with `sudo netstat -tulpn | grep 8108`
2. **Permission denied**: Check ownership of `/var/lib/typesense`
3. **Invalid API key**: Check `/etc/typesense/typesense-server.ini`

**Solution**:
```bash
# Fix permissions
sudo chown -R www-data:www-data /var/lib/typesense
sudo chown -R www-data:www-data /var/log/typesense

# Restart service
sudo systemctl restart typesense-server
```

### Problem: Collection not found

**Re-create collection**:
```bash
cd /home/demitri/repositories/ASCL/alt_ascl/agents
python3 typesense_setup_collection.py <<< "yes"
```

### Problem: Search returns no results

**Check document count**:
```bash
curl -H "X-TYPESENSE-API-KEY: YOUR_API_KEY" \
  http://localhost:8108/collections/codes | grep num_documents
```

If 0, re-import:
```bash
python3 typesense_import_data.py
```

### Problem: Flask shows "MySQL fallback" even when Typesense is running

**Diagnose**:
```bash
# 1. Check Typesense health
curl http://localhost:8108/health

# 2. Check Flask logs
tail -f /tmp/flask_output.log | grep Typesense

# 3. Verify API key matches in:
#    - /etc/typesense/typesense-server.ini
#    - ascl_net_app/configuration_files/default.cfg
```

**Solution**: Restart Flask to reload config:
```bash
ps aux | grep run_ascl_net_app | awk '{print $2}' | xargs kill
cd /home/demitri/repositories/ASCL/alt_ascl/source/ascl_net_app_project_home
python run_ascl_net_app.py --debug --port 60661 &
```

### Problem: Import fails with connection error

**Check**:
1. Is Typesense running? `curl http://localhost:8108/health`
2. Is MySQL accessible? `mysql --defaults-group-suffix=_ascl -e "SELECT 1;"`
3. Is API key correct in import script?

### Problem: Slow searches (>100ms)

**Check**:
```bash
# Memory usage
ps aux | grep typesense | awk '{print $6/1024 " MB"}'

# CPU usage
top -p $(pgrep typesense)
```

If high resource usage, consider:
- Reduce batch size during imports
- Add more RAM
- Move to dedicated server

---

## Maintenance

### Daily/Weekly Tasks

**Check health**:
```bash
curl http://localhost:8108/health
```

**Check document count**:
```bash
curl -H "X-TYPESENSE-API-KEY: YOUR_API_KEY" \
  http://localhost:8108/collections/codes | jq '.num_documents'
```

**Check logs for errors**:
```bash
grep -i error /var/log/typesense/typesense-error.log
```

### Monthly Tasks

**Re-import data** (ensures index is fully in sync):
```bash
cd /home/demitri/repositories/ASCL/alt_ascl/agents
python3 typesense_import_data.py
```

**Check disk usage**:
```bash
du -sh /var/lib/typesense
```

**Review search logs** (if analytics enabled):
```bash
# Check Flask logs for search queries
grep "Typesense search" /tmp/flask_output.log | tail -100
```

### Backup

**Manual backup**:
```bash
# Stop Typesense
sudo systemctl stop typesense-server

# Backup data directory
sudo tar -czf /backup/typesense-$(date +%Y%m%d).tar.gz /var/lib/typesense/

# Restart Typesense
sudo systemctl start typesense-server
```

**Automated backup** (add to crontab):
```bash
0 3 * * 0 tar -czf /backup/typesense-$(date +\%Y\%m\%d).tar.gz /var/lib/typesense/
```

### Restore

```bash
# Stop Typesense
sudo systemctl stop typesense-server

# Restore data directory
sudo rm -rf /var/lib/typesense/*
sudo tar -xzf /backup/typesense-20251201.tar.gz -C /
sudo chown -R www-data:www-data /var/lib/typesense

# Start Typesense
sudo systemctl start typesense-server

# Verify
curl http://localhost:8108/health
curl -H "X-TYPESENSE-API-KEY: YOUR_API_KEY" \
  http://localhost:8108/collections/codes | jq '.num_documents'
```

---

## Collection Schema Reference

**Collection Name**: `codes`

**Fields** (11 total):

| Field | Type | Faceted | Indexed | Sortable | Optional | Description |
|-------|------|---------|---------|----------|----------|-------------|
| `pk` | int32 | No | Yes | No | No | Primary key from MySQL |
| `ascl_id` | string | Yes | Yes | No | No | ASCL ID (e.g., "2508.018") |
| `title` | string | No | Yes | No | No | Code title |
| `abstract` | string | No | Yes | No | Yes | Code description |
| `credit` | string | No | Yes | No | Yes | Author names (semicolon-separated) |
| `published` | int32 | Yes | Yes | No | No | Publication status (0 or 1) |
| `time_added` | int64 | No | Yes | Yes | No | Unix timestamp |
| `bibcode` | string | Yes | Yes | No | Yes | ADS bibcode |
| `keywords` | string[] | Yes | Yes | No | Yes | Array of keyword names |
| `described_in` | string | No | Yes | No | Yes | Related publications |
| `url` | string | No | No | No | Yes | Link to code page (e.g., "/2508.018") |

**Default Sorting**: `time_added` (newest first)

**Token Separators**: `-`, `_`, `.` (treats hyphens, underscores, dots as word boundaries)

---

## Quick Reference

### Common Commands

```bash
# Check Typesense status
sudo systemctl status typesense-server
curl http://localhost:8108/health

# View collection info
curl -H "X-TYPESENSE-API-KEY: YOUR_API_KEY" \
  http://localhost:8108/collections/codes | jq

# Re-create collection
cd /home/demitri/repositories/ASCL/alt_ascl/agents
python3 typesense_setup_collection.py <<< "yes"

# Re-import data
python3 typesense_import_data.py

# Test search
curl -H "X-TYPESENSE-API-KEY: YOUR_API_KEY" \
  "http://localhost:8108/collections/codes/documents/search?q=python&query_by=title" | jq '.found'

# Restart Typesense
sudo systemctl restart typesense-server

# View logs
tail -f /var/log/typesense/typesense.log
sudo journalctl -u typesense-server -f
```

---

## Files Reference

**Setup Scripts**:
- `agents/typesense_setup_collection.py` - Create collection schema
- `agents/typesense_import_data.py` - Import/sync data from MySQL

**Flask Integration**:
- `ascl_net_app/services/typesense_client.py` - Typesense client singleton
- `ascl_net_app/controllers/search.py` - Search endpoint with fallback
- `ascl_net_app/configuration_files/default.cfg` - Typesense configuration

**System Configuration**:
- `/etc/typesense/typesense-server.ini` - Typesense server config
- `/etc/systemd/system/typesense-server.service` - Systemd service file
- `/var/lib/typesense/` - Data directory
- `/var/log/typesense/` - Log directory

**Documentation**:
- `agents/TYPESENSE_SETUP_GUIDE.md` - This file
- `agents/TYPESENSE_IMPLEMENTATION_PLAN.md` - Original implementation plan
- `agents/TYPESENSE_PHASE1_COMPLETE.md` - Phase 1 completion report
- `agents/TYPESENSE_PHASE2_COMPLETE.md` - Phase 2 completion report

---

## Summary

**What's Working**:
- ✅ Typesense server running (v29.0)
- ✅ Collection created with 11 fields
- ✅ 3,984 published codes indexed
- ✅ Flask integration with automatic MySQL fallback
- ✅ Sub-50ms search response times
- ✅ Typo tolerance working
- ✅ Result highlighting

**What's Not Yet Implemented**:
- ⏳ Instant search UI (type-ahead widget)
- ⏳ Real-time sync (auto-update on database changes)
- ⏳ Faceted search UI (filter by keywords/year)
- ⏳ Analytics tracking

**When to Update the Index**:
1. **Manual**: Run `python3 typesense_import_data.py` whenever you make bulk changes
2. **Scheduled**: Set up daily cron job for automatic sync
3. **Real-time** (future): Will auto-sync when codes are created/updated via admin interface

**Support**:
- Official Docs: https://typesense.org/docs/
- GitHub: https://github.com/typesense/typesense
- Community: https://join.slack.com/t/typesense-community/

---

**Last Updated**: 2025-12-02
**Maintainer**: ASCL Development Team
**Status**: Production-ready with manual/scheduled sync
