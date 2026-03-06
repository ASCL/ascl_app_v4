#!/bin/bash
# Redeploy ASCL Flask app from development repository
# Usage: sudo ./redeploy.sh

set -e

# Check if running as root
if [ "$(id -u)" -ne 0 ]; then
    echo "Error: This script must be run with sudo"
    echo "Usage: sudo $0"
    exit 1
fi

# Check that secrets file exists before deploying
if [ ! -f /etc/ascl/secrets.cfg ]; then
    echo "ERROR: /etc/ascl/secrets.cfg not found. Create it from secrets.cfg.example."
    exit 1
fi

REPO_PATH="/home/demitri/repositories/ASCL/alt_ascl/source/ascl_net_app_project_home"
DEPLOY_PATH="/var/www/ascl_net_app"
DM_DBCORE_PATH="/home/demitri/repositories/ASCL/dm-dbcore"
ASCL_CORE_PATH="/home/demitri/repositories/ASCL/ascl_core"

echo "Stopping service..."
systemctl stop ascl_net_app

echo "Syncing application files from repository..."
rsync -av --delete \
    --exclude='venv' --exclude='.venv' --exclude='__pycache__' \
    --exclude='*.pyc' --exclude='.git' --exclude='logs/*.log' \
    --exclude='*.egg-info' --exclude='.uv' --exclude='redeploy.sh' \
    --exclude='.claude' \
    "$REPO_PATH/" "$DEPLOY_PATH/"

echo "Syncing dm-dbcore..."
rsync -av --delete \
    --exclude='__pycache__' --exclude='*.pyc' --exclude='.git' \
    --exclude='.venv' --exclude='venv' --exclude='.claude' \
    "$DM_DBCORE_PATH/" /var/www/dm-dbcore/

echo "Syncing ascl_core..."
rsync -av --delete \
    --exclude='__pycache__' --exclude='*.pyc' --exclude='.git' \
    --exclude='.venv' --exclude='venv' --exclude='.claude' \
    "$ASCL_CORE_PATH/" /var/www/ascl_core/

echo "Setting ownership..."
chown -R www-data:www-data "$DEPLOY_PATH"
chown -R www-data:www-data /var/www/dm-dbcore
chown -R www-data:www-data /var/www/ascl_core

echo "Updating dependencies..."
cd "$DEPLOY_PATH"
runuser -u www-data -- env UV_CACHE_DIR=/var/cache/uv uv pip install "/var/www/dm-dbcore/[mysql]"
runuser -u www-data -- env UV_CACHE_DIR=/var/cache/uv uv pip install /var/www/ascl_core/
runuser -u www-data -- env UV_CACHE_DIR=/var/cache/uv uv pip install -r requirements.txt

echo "Starting service..."
systemctl start ascl_net_app

echo "Deployment complete. Checking status..."
systemctl status ascl_net_app --no-pager
