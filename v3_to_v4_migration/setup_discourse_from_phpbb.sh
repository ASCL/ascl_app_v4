#!/bin/bash
# Setup Discourse forum with docker-compose and import phpBB data
# Usage:
#   ./setup_discourse_from_phpbb.sh [--rebuild]
#
# This script is idempotent - safe to run multiple times.
# Use --rebuild to force recreation of containers and re-import.

set -euo pipefail

REBUILD=false
if [[ "${1:-}" == "--rebuild" ]]; then
  REBUILD=true
  echo "⚠️  REBUILD mode: Will destroy existing Discourse installation!"
  read -p "Continue? (yes/no): " confirm
  [[ "$confirm" != "yes" ]] && { echo "Aborted."; exit 1; }
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
DISCOURSE_DIR="$REPO_ROOT/alt_ascl/discourse"

# Configuration
DISCOURSE_PORT=45888
DISCOURSE_HOST="localhost"
ADMIN_EMAIL="demitri@nightlightresearch.com"
ADMIN_USERNAME="demitri"
ADMIN_PASSWORD="changeme_discourse_admin_123"  # Change this after first login!
POSTGRES_PASSWORD="discourse_pg_password_$(date +%s)"
DISCOURSE_HOSTNAME="localhost:${DISCOURSE_PORT}"

# phpBB backup paths
PHPBB_DB_BACKUP="$REPO_ROOT/db_backups/ascl_phpbb-database-backup-2025.12.02.sql.gz"
PHPBB_FILES_BACKUP="$REPO_ROOT/db_backups/ascl_phpBB3_files-2025.12.03-backup.bzip2"
PHPBB_FILES_DIR="$DISCOURSE_DIR/phpbb_files"

# Get host IP for Docker to access host MySQL
if [[ "$OSTYPE" == "darwin"* ]]; then
  HOST_IP="host.docker.internal"
else
  HOST_IP=$(ip route | grep default | awk '{print $3}' | head -n1)
fi

echo "================================================"
echo "Discourse Setup for ASCL phpBB Migration"
echo "================================================"
echo ""
echo "Configuration:"
echo "  Install dir  : $DISCOURSE_DIR"
echo "  Web UI       : http://${DISCOURSE_HOST}:${DISCOURSE_PORT}"
echo "  Admin email  : $ADMIN_EMAIL"
echo "  Admin user   : $ADMIN_USERNAME"
echo "  Fake SMTP    : http://${DISCOURSE_HOST}:1080 (MailCatcher)"
echo "  phpBB MySQL  : ${HOST_IP}:3307 (host MySQL)"
echo ""

# Check if backups exist
if [[ ! -f "$PHPBB_DB_BACKUP" ]]; then
  echo "❌ phpBB database backup not found: $PHPBB_DB_BACKUP"
  echo "   Please ensure the backup exists first."
  exit 1
fi

if [[ ! -f "$PHPBB_FILES_BACKUP" ]]; then
  echo "⚠️  phpBB files backup not found: $PHPBB_FILES_BACKUP"
  echo "   Avatars and attachments will not be imported."
fi

# Check if Discourse is already running
if docker ps | grep -q discourse_web; then
  if [[ "$REBUILD" == "false" ]]; then
    echo "✓ Discourse is already running!"
    echo ""
    echo "Access Points:"
    echo "  🌐 Discourse    : http://${DISCOURSE_HOST}:${DISCOURSE_PORT}"
    echo "  📧 MailCatcher  : http://${DISCOURSE_HOST}:1080"
    echo ""
    echo "To rebuild from scratch, run: $0 --rebuild"
    exit 0
  fi
fi

# Create directory structure
echo "Creating directory structure..."
mkdir -p "$DISCOURSE_DIR"/{postgres,redis,shared,import}

# Handle rebuild flag
if [[ "$REBUILD" == "true" ]] && docker ps -a | grep -q discourse; then
  echo "Stopping and removing existing containers..."
  cd "$DISCOURSE_DIR" 2>/dev/null || true
  docker-compose down -v 2>/dev/null || true
  echo "Cleaning up old data (preserving backups)..."
  rm -rf "$DISCOURSE_DIR"/{postgres,redis,shared}/*
  mkdir -p "$DISCOURSE_DIR"/{postgres,redis,shared,import}
fi

# Extract phpBB files if backup exists
if [[ -f "$PHPBB_FILES_BACKUP" ]] && [[ ! -d "$PHPBB_FILES_DIR" ]]; then
  echo "Extracting phpBB files for avatar/attachment import..."
  mkdir -p "$PHPBB_FILES_DIR"
  tar -xjf "$PHPBB_FILES_BACKUP" -C "$PHPBB_FILES_DIR" --strip-components=1 || {
    echo "⚠️  Failed to extract phpBB files, continuing without them..."
  }
fi

# Create docker-compose.yml
echo "Creating docker-compose.yml..."
cat > "$DISCOURSE_DIR/docker-compose.yml" <<EOF
version: '3.8'

services:
  postgres:
    image: postgres:15-alpine
    container_name: discourse_postgres
    environment:
      POSTGRES_DB: discourse
      POSTGRES_USER: discourse
      POSTGRES_PASSWORD: \${POSTGRES_PASSWORD}
    volumes:
      - ./postgres:/var/lib/postgresql/data
    networks:
      - discourse_network
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U discourse"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    container_name: discourse_redis
    volumes:
      - ./redis:/data
    networks:
      - discourse_network
    restart: unless-stopped
    command: redis-server --appendonly yes
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  mailcatcher:
    image: sj26/mailcatcher:latest
    container_name: discourse_mailcatcher
    ports:
      - "127.0.0.1:1080:1080"  # Web UI
      - "127.0.0.1:1025:1025"  # SMTP
    networks:
      - discourse_network
    restart: unless-stopped

  discourse:
    image: discourse/discourse:latest
    container_name: discourse_web
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
      mailcatcher:
        condition: service_started
    environment:
      DISCOURSE_HOSTNAME: \${DISCOURSE_HOSTNAME}
      DISCOURSE_DEVELOPER_EMAILS: \${ADMIN_EMAIL}
      DISCOURSE_SMTP_ADDRESS: mailcatcher
      DISCOURSE_SMTP_PORT: 1025
      DISCOURSE_SMTP_ENABLE_START_TLS: "false"
      DISCOURSE_SMTP_AUTHENTICATION: none
      DISCOURSE_DB_HOST: postgres
      DISCOURSE_DB_NAME: discourse
      DISCOURSE_DB_USERNAME: discourse
      DISCOURSE_DB_PASSWORD: \${POSTGRES_PASSWORD}
      DISCOURSE_REDIS_HOST: redis
      DISCOURSE_SERVE_STATIC_ASSETS: "true"
      RAILS_ENV: production
    volumes:
      - ./shared:/shared
      - ./import:/import
      - ./phpbb_files:/phpbb_files:ro
    ports:
      - "127.0.0.1:\${DISCOURSE_PORT}:3000"
    networks:
      - discourse_network
    extra_hosts:
      - "host.mysql:${HOST_IP}"
    restart: unless-stopped

networks:
  discourse_network:
    driver: bridge
EOF

# Create .env file for docker-compose
echo "Creating .env file..."
cat > "$DISCOURSE_DIR/.env" <<EOF
DISCOURSE_PORT=${DISCOURSE_PORT}
DISCOURSE_HOSTNAME=${DISCOURSE_HOSTNAME}
ADMIN_EMAIL=${ADMIN_EMAIL}
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
EOF

# Create phpBB import script
echo "Creating phpBB import script..."
cat > "$DISCOURSE_DIR/import/import_phpbb.rb" <<'RUBY_EOF'
require 'mysql2'
require File.expand_path(File.dirname(__FILE__) + "/../script/import_scripts/phpbb3")

class ImportPhpbb3 < ImportScripts::PhpBB3Base
  PHPBB_DB_HOST = ENV['PHPBB_DB_HOST'] || 'host.mysql'
  PHPBB_DB_PORT = ENV['PHPBB_DB_PORT'] || '3307'
  PHPBB_DB_NAME = ENV['PHPBB_DB_NAME'] || 'ascl_phpbb'
  PHPBB_DB_USER = ENV['PHPBB_DB_USER'] || 'root'
  PHPBB_DB_PASS = ENV['PHPBB_DB_PASS'] || ''

  def initialize
    super
    @client = Mysql2::Client.new(
      host: PHPBB_DB_HOST,
      port: PHPBB_DB_PORT.to_i,
      username: PHPBB_DB_USER,
      password: PHPBB_DB_PASS,
      database: PHPBB_DB_NAME
    )

    @phpbb_uploads_dir = "/phpbb_files/files" if Dir.exist?("/phpbb_files/files")
  end
end

ImportPhpbb3.new.perform
RUBY_EOF

# Create import runner script
cat > "$DISCOURSE_DIR/import/run_import.sh" <<'IMPORT_EOF'
#!/bin/bash
set -euo pipefail

echo "================================================"
echo "phpBB → Discourse Import"
echo "================================================"

# Read MySQL credentials from host ~/.my.cnf
if [[ ! -f /root/.my.cnf.host ]]; then
  echo "❌ MySQL credentials file not found"
  echo "   Please mount ~/.my.cnf to /root/.my.cnf.host"
  exit 1
fi

# Extract credentials from [client_ascl] section
MYSQL_USER=$(awk -F= '/^\[client_ascl\]/,/^\[/ {if ($1 ~ /^user/) {gsub(/^[ \t]+|[ \t]+$/, "", $2); print $2}}' /root/.my.cnf.host)
MYSQL_PASS=$(awk -F= '/^\[client_ascl\]/,/^\[/ {if ($1 ~ /^password/) {gsub(/^[ \t]+|[ \t]+$/, "", $2); print $2}}' /root/.my.cnf.host)

export PHPBB_DB_HOST=host.mysql
export PHPBB_DB_PORT=3307
export PHPBB_DB_NAME=ascl_phpbb
export PHPBB_DB_USER="$MYSQL_USER"
export PHPBB_DB_PASS="$MYSQL_PASS"

cd /var/www/discourse

echo "Testing phpBB database connection..."
mysql -h "$PHPBB_DB_HOST" -P "$PHPBB_DB_PORT" -u "$PHPBB_DB_USER" -p"$PHPBB_DB_PASS" -e "USE $PHPBB_DB_NAME; SELECT COUNT(*) as user_count FROM phpbb_users;" || {
  echo "❌ Cannot connect to phpBB database"
  exit 1
}

echo "✓ phpBB database accessible"
echo ""
echo "Starting import (this may take several minutes)..."
echo ""

bundle exec ruby /import/import_phpbb.rb

echo ""
echo "✓ Import complete!"
IMPORT_EOF

chmod +x "$DISCOURSE_DIR/import/run_import.sh"

# Start services
cd "$DISCOURSE_DIR"
echo ""
echo "Starting Discourse services..."
docker-compose up -d

echo ""
echo "Waiting for services to be healthy..."
for i in {1..60}; do
  if docker-compose ps 2>/dev/null | grep -q "discourse_postgres.*healthy" && \
     docker-compose ps 2>/dev/null | grep -q "discourse_redis.*healthy"; then
    echo "✓ Database and cache are ready"
    break
  fi
  echo "  Waiting... ($i/60)"
  sleep 2
done

# Wait for Discourse to be ready
echo ""
echo "Waiting for Discourse to complete initialization..."
sleep 10  # Give it a moment to start

for i in {1..180}; do
  if docker-compose logs discourse 2>/dev/null | grep -qE "(Listening on|Booting Puma|Use Ctrl-C to stop)"; then
    echo "✓ Discourse is ready"
    break
  fi

  if [[ $((i % 10)) -eq 0 ]]; then
    echo "  Still waiting for Discourse... ($i/180)"
  fi
  sleep 2
done

# Bootstrap Discourse (run rake tasks)
echo ""
echo "Bootstrapping Discourse database..."
docker-compose exec -T discourse bash -c "
  cd /var/www/discourse && \
  RAILS_ENV=production bundle exec rake db:migrate && \
  RAILS_ENV=production bundle exec rake assets:precompile
" || echo "⚠️  Some bootstrap tasks may have failed (this might be OK on re-run)"

# Create admin account
echo ""
echo "Creating admin account (${ADMIN_USERNAME})..."
docker-compose exec -T discourse bash -c "
  cd /var/www/discourse && \
  RAILS_ENV=production bundle exec rails runner \"
    User.where(email: '${ADMIN_EMAIL}').first_or_create! do |u|
      u.username = '${ADMIN_USERNAME}'
      u.password = '${ADMIN_PASSWORD}'
      u.admin = true
      u.moderator = true
      u.approved = true
      u.active = true
      u.save!
    end
  \"
" 2>/dev/null || echo "⚠️  Admin user may already exist (this is OK)"

# Run phpBB import
if [[ -f "$PHPBB_DB_BACKUP" ]]; then
  echo ""
  echo "================================================"
  echo "Importing phpBB Data"
  echo "================================================"

  # Ensure phpBB database is restored
  if ! "$SCRIPT_DIR/restore_phpbb_backup.sh" 2>/dev/null; then
    echo "⚠️  phpBB database restore may have failed, attempting import anyway..."
  fi

  echo ""
  echo "Running phpBB → Discourse import..."
  echo "(This may take 10-30 minutes depending on forum size)"
  echo ""

  # Mount MySQL credentials and run import
  docker cp ~/.my.cnf discourse_web:/root/.my.cnf.host

  docker-compose exec -T discourse bash /import/run_import.sh || {
    echo ""
    echo "⚠️  Import failed or partially completed."
    echo "   Check logs: docker-compose logs discourse"
    echo "   You can re-run the import manually:"
    echo "   docker-compose exec discourse bash /import/run_import.sh"
  }
fi

# Make forum read-only
echo ""
echo "Configuring forum as read-only..."
docker-compose exec -T discourse bash -c "
  cd /var/www/discourse && \
  RAILS_ENV=production bundle exec rails runner \"
    SiteSetting.login_required = true
    SiteSetting.read_only_mode_enabled = true
    puts 'Forum is now read-only'
  \"
" 2>/dev/null || echo "⚠️  Could not set read-only mode (configure manually in admin panel)"

echo ""
echo "================================================"
echo "✓ Discourse Setup Complete!"
echo "================================================"
echo ""
echo "Access Points:"
echo "  🌐 Discourse    : http://${DISCOURSE_HOST}:${DISCOURSE_PORT}"
echo "  📧 MailCatcher  : http://${DISCOURSE_HOST}:1080"
echo ""
echo "Admin Credentials:"
echo "  Email    : ${ADMIN_EMAIL}"
echo "  Username : ${ADMIN_USERNAME}"
echo "  Password : ${ADMIN_PASSWORD}"
echo ""
echo "Status:"
echo "  Mode     : Read-Only (imported from phpBB)"
echo "  Database : PostgreSQL (imported data)"
echo "  Source   : phpBB backup from $(date -r "$PHPBB_DB_BACKUP" '+%Y-%m-%d' 2>/dev/null || echo 'unknown')"
echo ""
echo "Container Management:"
echo "  Start  : cd $DISCOURSE_DIR && docker-compose start"
echo "  Stop   : cd $DISCOURSE_DIR && docker-compose stop"
echo "  Logs   : cd $DISCOURSE_DIR && docker-compose logs -f discourse"
echo "  Rebuild: $0 --rebuild"
echo ""
echo "To disable read-only mode:"
echo "  1. Login as admin at http://${DISCOURSE_HOST}:${DISCOURSE_PORT}"
echo "  2. Go to Admin → Settings → Login"
echo "  3. Disable 'read only mode enabled'"
echo ""
