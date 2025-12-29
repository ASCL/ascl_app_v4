#!/bin/bash
################################################################################
# ASCL Development Environment Setup Script
################################################################################
# This script sets up the complete Docker-based MySQL development environment:
#   1. Creates Docker container with MySQL 8.0.42 on port 3307
#   2. Restores ascl_db, ascl_wordpress, and ascl_phpbb databases
#   3. Runs DB_UPGRADE_PLAYBOOK.sql to create ascl_db_v4
#   4. Configures ~/.my.cnf for password-less access
#
# Usage:
#   ./setup_dev_environment.sh
#
# Requirements:
#   - Docker and docker-compose installed
#   - Database backup files in /home/demitri/repositories/ASCL/db_backups/
#   - DB_UPGRADE_PLAYBOOK.sql in /home/demitri/repositories/ASCL/alt_ascl/agents/
#   - ~/.my.cnf exists (will append [client_ascl] section if needed)
#
# Created: 2025-12-03
################################################################################

set -e  # Exit on any error

# Color output helpers
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Configuration
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
REPO_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
DB_BACKUPS_DIR="$REPO_ROOT/db_backups"
AGENTS_DIR="$REPO_ROOT/alt_ascl/agents"
DOCKER_DIR="$SCRIPT_DIR"

CONTAINER_NAME="mysql_ascl_dev"
MYSQL_ROOT_PASSWORD="${ASCLDB_ROOT_PASSWORD:-ascl_root_dev_password}"
MYSQL_USER="${ASCLDB_USER:-ascl_db}"
MYSQL_PASSWORD="${ASCLDB_PASSWORD:-ascl_dev_password}"
MYSQL_PORT="3307"

# Export variables for docker-compose to use
export MYSQL_ROOT_PASSWORD
export MYSQL_USER
export MYSQL_PASSWORD

################################################################################
# Step 1: Check Prerequisites
################################################################################

log_info "Checking prerequisites..."

# Check Docker
if ! command -v docker &> /dev/null; then
    log_error "Docker is not installed. Please install Docker first."
    exit 1
fi

# Check docker-compose
if ! command -v docker-compose &> /dev/null; then
    log_error "docker-compose is not installed. Please install docker-compose first."
    exit 1
fi

# Check if user is in docker group (Linux only)
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    if ! groups | grep -q docker; then
        log_warning "Your user is not in the 'docker' group. You may need sudo privileges."
        log_warning "To fix: sudo usermod -aG docker $USER && newgrp docker"
    fi
fi

# Check backup files exist
ASCL_DB_BACKUP="$DB_BACKUPS_DIR/ascl_db-backup_2011.11.29.sql"
WORDPRESS_BACKUP="$DB_BACKUPS_DIR/ascl_wordpress-backup_2025.11.29.sql"
PHPBB_BACKUP="$DB_BACKUPS_DIR/ascl_phpbb-database-backup-2025.12.02.sql.gz"
UPGRADE_PLAYBOOK="$AGENTS_DIR/DB_UPGRADE_PLAYBOOK.sql"

if [ ! -f "$ASCL_DB_BACKUP" ]; then
    log_error "ASCL database backup not found: $ASCL_DB_BACKUP"
    exit 1
fi

if [ ! -f "$WORDPRESS_BACKUP" ]; then
    log_error "WordPress database backup not found: $WORDPRESS_BACKUP"
    exit 1
fi

if [ ! -f "$PHPBB_BACKUP" ]; then
    log_error "phpBB database backup not found: $PHPBB_BACKUP"
    exit 1
fi

if [ ! -f "$UPGRADE_PLAYBOOK" ]; then
    log_error "DB_UPGRADE_PLAYBOOK.sql not found: $UPGRADE_PLAYBOOK"
    exit 1
fi

log_success "All prerequisites met"

################################################################################
# Step 2: Update docker-compose.yml with unique container name
################################################################################

log_info "Updating docker-compose.yml..."

cd "$DOCKER_DIR"

# Backup original if it exists
if [ -f "docker-compose.yml.bak" ]; then
    log_info "Backup already exists: docker-compose.yml.bak"
else
    cp docker-compose.yml docker-compose.yml.bak
    log_success "Created backup: docker-compose.yml.bak"
fi

# Update container name in docker-compose.yml
cat > docker-compose.yml <<EOF
services:
  mysql:
    image: mysql:8.0.42
    container_name: $CONTAINER_NAME
    restart: unless-stopped
    environment:
      MYSQL_ROOT_PASSWORD: ${MYSQL_ROOT_PASSWORD}
      MYSQL_USER: ${MYSQL_USER}
      MYSQL_PASSWORD: ${MYSQL_PASSWORD}
    ports:
      - "${MYSQL_PORT}:3306"
    volumes:
      - mysql_ascl_dev_data:/var/lib/mysql
    command: --default-authentication-plugin=mysql_native_password
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost", "-u", "root", "-p\${MYSQL_ROOT_PASSWORD}"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  mysql_ascl_dev_data:
EOF

log_success "docker-compose.yml updated with container name: $CONTAINER_NAME"

################################################################################
# Step 3: Stop and remove existing container (if running)
################################################################################

log_info "Checking for existing containers..."

if docker ps -a | grep -q "$CONTAINER_NAME"; then
    log_warning "Found existing container: $CONTAINER_NAME"
    read -p "Remove existing container and data? [y/N] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        log_info "Stopping and removing container..."
        # Force remove container (handles corrupted containers)
        docker stop "$CONTAINER_NAME" 2>/dev/null || true
        docker rm -f "$CONTAINER_NAME" 2>/dev/null || true

        # Remove volume
        VOLUME_NAME="docker_mysql_ascl_dev_data"
        if docker volume ls | grep -q "$VOLUME_NAME"; then
            docker volume rm "$VOLUME_NAME" 2>/dev/null || true
        fi

        log_success "Removed existing container and volumes"
    else
        log_error "Cannot proceed with existing container. Exiting."
        exit 1
    fi
fi

################################################################################
# Step 4: Start MySQL container
################################################################################

log_info "Starting MySQL container..."

docker-compose up -d

log_info "Waiting for MySQL to be healthy..."
TIMEOUT=60
ELAPSED=0
while [ $ELAPSED -lt $TIMEOUT ]; do
    if docker inspect --format='{{.State.Health.Status}}' "$CONTAINER_NAME" 2>/dev/null | grep -q "healthy"; then
        log_success "MySQL container is healthy"
        break
    fi
    sleep 2
    ELAPSED=$((ELAPSED + 2))
    echo -n "."
done
echo

if [ $ELAPSED -ge $TIMEOUT ]; then
    log_error "Timed out waiting for MySQL to become healthy"
    log_error "Check logs with: docker-compose logs mysql"
    exit 1
fi

################################################################################
# Step 5: Create databases
################################################################################

log_info "Creating databases..."

# Create databases
docker exec -i "$CONTAINER_NAME" mysql -uroot -p"$MYSQL_ROOT_PASSWORD" <<EOF
CREATE DATABASE IF NOT EXISTS ascl_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE IF NOT EXISTS ascl_db_v4 CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE IF NOT EXISTS ascl_wordpress CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE IF NOT EXISTS ascl_phpbb CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
GRANT ALL PRIVILEGES ON ascl_db.* TO '$MYSQL_USER'@'%';
GRANT ALL PRIVILEGES ON ascl_db_v4.* TO '$MYSQL_USER'@'%';
GRANT ALL PRIVILEGES ON ascl_wordpress.* TO '$MYSQL_USER'@'%';
GRANT ALL PRIVILEGES ON ascl_phpbb.* TO '$MYSQL_USER'@'%';
FLUSH PRIVILEGES;
EOF

log_success "Databases created: ascl_db, ascl_db_v4, ascl_wordpress, ascl_phpbb"

################################################################################
# Step 6: Restore ascl_db backup
################################################################################

log_info "Restoring ascl_db database (this may take a few minutes)..."

docker exec -i "$CONTAINER_NAME" mysql -uroot -p"$MYSQL_ROOT_PASSWORD" ascl_db < "$ASCL_DB_BACKUP"

log_success "ascl_db database restored"

################################################################################
# Step 7: Restore ascl_wordpress backup
################################################################################

log_info "Restoring ascl_wordpress database (this may take a few minutes)..."

docker exec -i "$CONTAINER_NAME" mysql -uroot -p"$MYSQL_ROOT_PASSWORD" ascl_wordpress < "$WORDPRESS_BACKUP"

log_success "ascl_wordpress database restored"

################################################################################
# Step 7a: Restore ascl_phpbb backup
################################################################################

log_info "Restoring ascl_phpbb database (this may take a few minutes)..."

# The phpBB backup is gzip compressed, so we need to decompress it first
gunzip -c "$PHPBB_BACKUP" | docker exec -i "$CONTAINER_NAME" mysql -uroot -p"$MYSQL_ROOT_PASSWORD" ascl_phpbb

log_success "ascl_phpbb database restored"

################################################################################
# Step 8: Run DB_UPGRADE_PLAYBOOK.sql
################################################################################

log_info "Running DB_UPGRADE_PLAYBOOK.sql to create ascl_db_v4..."

# Copy ascl_db to ascl_db_v4 first
docker exec "$CONTAINER_NAME" bash -c "mysqldump -uroot -p'$MYSQL_ROOT_PASSWORD' ascl_db | mysql -uroot -p'$MYSQL_ROOT_PASSWORD' ascl_db_v4"

log_success "Copied ascl_db to ascl_db_v4"

# Run upgrade playbook
docker exec -i "$CONTAINER_NAME" mysql -uroot -p"$MYSQL_ROOT_PASSWORD" < "$UPGRADE_PLAYBOOK"

log_success "DB_UPGRADE_PLAYBOOK.sql executed successfully"

################################################################################
# Step 9: Verify databases
################################################################################

log_info "Verifying databases..."

# Check table count in each database
ASCL_DB_TABLES=$(docker exec "$CONTAINER_NAME" mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -e "SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA='ascl_db'" -sN)
ASCL_DB_V4_TABLES=$(docker exec "$CONTAINER_NAME" mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -e "SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA='ascl_db_v4'" -sN)
WORDPRESS_TABLES=$(docker exec "$CONTAINER_NAME" mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -e "SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA='ascl_wordpress'" -sN)
PHPBB_TABLES=$(docker exec "$CONTAINER_NAME" mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -e "SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA='ascl_phpbb'" -sN)

log_success "ascl_db: $ASCL_DB_TABLES tables"
log_success "ascl_db_v4: $ASCL_DB_V4_TABLES tables"
log_success "ascl_wordpress: $WORDPRESS_TABLES tables"
log_success "ascl_phpbb: $PHPBB_TABLES tables"

# Verify InnoDB conversion
log_info "Verifying InnoDB conversion in ascl_db_v4..."
MYISAM_COUNT=$(docker exec "$CONTAINER_NAME" mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -e "SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA='ascl_db_v4' AND ENGINE='MyISAM'" -sN)

if [ "$MYISAM_COUNT" -eq "0" ]; then
    log_success "All tables converted to InnoDB"
else
    log_warning "Found $MYISAM_COUNT MyISAM tables remaining"
fi

# Verify foreign keys
FK_COUNT=$(docker exec "$CONTAINER_NAME" mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -e "SELECT COUNT(*) FROM information_schema.KEY_COLUMN_USAGE WHERE TABLE_SCHEMA='ascl_db_v4' AND REFERENCED_TABLE_NAME IS NOT NULL" -sN)
log_success "Found $FK_COUNT foreign key constraints"

# Display detailed database summary
log_info "Database summary:"
docker exec "$CONTAINER_NAME" mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -e "
SELECT
    TABLE_SCHEMA as 'Database',
    COUNT(*) as 'Tables',
    ROUND(SUM(DATA_LENGTH + INDEX_LENGTH) / 1024 / 1024, 2) as 'Size_MB'
FROM information_schema.TABLES
WHERE TABLE_SCHEMA IN ('ascl_db', 'ascl_db_v4', 'ascl_wordpress', 'ascl_phpbb')
GROUP BY TABLE_SCHEMA
ORDER BY TABLE_SCHEMA;" 2>/dev/null || log_warning "Could not display database summary"

# Display foreign key details for ascl_db_v4
log_info "Foreign key constraints in ascl_db_v4:"
docker exec "$CONTAINER_NAME" mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -e "
SELECT
    TABLE_NAME as 'Table',
    CONSTRAINT_NAME as 'FK_Name',
    COLUMN_NAME as 'Column',
    REFERENCED_TABLE_NAME as 'Ref_Table',
    REFERENCED_COLUMN_NAME as 'Ref_Column'
FROM information_schema.KEY_COLUMN_USAGE
WHERE TABLE_SCHEMA='ascl_db_v4'
    AND REFERENCED_TABLE_NAME IS NOT NULL
ORDER BY TABLE_NAME, CONSTRAINT_NAME;" 2>/dev/null || log_warning "Could not display FK details"

# Quick data sanity check
log_info "Verifying sample data..."
CODE_COUNT=$(docker exec "$CONTAINER_NAME" mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -e "SELECT COUNT(*) FROM ascl_db_v4.codes" -sN 2>/dev/null)
if [ -n "$CODE_COUNT" ] && [ "$CODE_COUNT" -gt 0 ]; then
    log_success "ascl_db_v4.codes has $CODE_COUNT records"
else
    log_warning "Could not verify codes table or table is empty"
fi

################################################################################
# Step 10: Configure ~/.my.cnf for password-less access
################################################################################

log_info "Configuring ~/.my.cnf for password-less access..."

MYCNF_FILE="$HOME/.my.cnf"

# Check if .my.cnf exists
if [ ! -f "$MYCNF_FILE" ]; then
    log_error "~/.my.cnf does not exist. Please create it first."
    exit 1
fi

# Check if [client_ascl] section already exists
if grep -q "\[client_ascl\]" "$MYCNF_FILE"; then
    log_info "[client_ascl] section already exists in ~/.my.cnf"
else
    log_info "Appending [client_ascl] section to ~/.my.cnf"
    cat >> "$MYCNF_FILE" <<EOF

# ASCL Development Database (added by setup_dev_environment.sh on $(date))
[client_ascl]
user=$MYSQL_USER
password=$MYSQL_PASSWORD
host=127.0.0.1
port=$MYSQL_PORT
EOF
    chmod 600 "$MYCNF_FILE"
    log_success "Added [client_ascl] section to ~/.my.cnf"
fi

################################################################################
# Step 11: Test connection
################################################################################

log_info "Testing MySQL connection with ~/.my.cnf..."

if mysql --defaults-group-suffix=_ascl -e "SELECT 1" &> /dev/null; then
    log_success "MySQL connection successful using ~/.my.cnf"
else
    log_warning "Could not connect using ~/.my.cnf (mysql client may not be installed locally)"
    log_info "You can still connect via Docker: docker exec -it $CONTAINER_NAME mysql -u$MYSQL_USER -p$MYSQL_PASSWORD"
fi

################################################################################
# Summary
################################################################################

echo
echo "=========================================="
log_success "Development environment setup complete!"
echo "=========================================="
echo
echo "Container Details:"
echo "  Name:           $CONTAINER_NAME"
echo "  Port:           127.0.0.1:$MYSQL_PORT"
echo "  Root Password:  $MYSQL_ROOT_PASSWORD"
echo "  User:           $MYSQL_USER"
echo "  Password:       $MYSQL_PASSWORD"
echo
echo "Databases:"
echo "  ascl_db         - Original production backup"
echo "  ascl_db_v4      - Upgraded with InnoDB, FKs, code_pk migration"
echo "  ascl_wordpress  - WordPress content"
echo "  ascl_phpbb      - phpBB forum database"
echo
echo "Connection:"
echo "  Via Docker:     docker exec -it $CONTAINER_NAME mysql -u$MYSQL_USER -p$MYSQL_PASSWORD ascl_db_v4"
echo "  Via ~/.my.cnf:  mysql --defaults-group-suffix=_ascl -D ascl_db_v4"
echo
echo "Management Commands:"
echo "  Start:          cd $DOCKER_DIR && docker-compose up -d"
echo "  Stop:           cd $DOCKER_DIR && docker-compose stop"
echo "  Logs:           cd $DOCKER_DIR && docker-compose logs -f mysql"
echo "  Remove:         cd $DOCKER_DIR && docker-compose down -v"
echo
echo "Python Connection:"
echo "  The Trillian2DBConnection.py is configured to use:"
echo "    - Host: localhost"
echo "    - Port: $MYSQL_PORT"
echo "    - Database: ascl_db_v4"
echo "    - Credentials from ~/.my.cnf [client_ascl]"
echo
log_info "To start developing, run: cd $REPO_ROOT/alt_ascl/source/ascl_net_app_project_home && python run_ascl_net_app.py --debug"
echo
