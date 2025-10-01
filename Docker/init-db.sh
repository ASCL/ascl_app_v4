#!/bin/bash
# This script runs inside the MySQL container to restore the database backup

set -e

echo "Waiting for MySQL to be ready..."
until mysqladmin ping -h"localhost" -u"root" -p"${MYSQL_ROOT_PASSWORD}" --silent; do
    echo "MySQL is unavailable - sleeping"
    sleep 2
done

echo "MySQL is up - restoring database backup..."

# Decompress and import the SQL backup
gunzip -c /docker-entrypoint-initdb.d/ascl_db_2025.09.30_bkup.sql.gz | mysql -u"root" -p"${MYSQL_ROOT_PASSWORD}" "${MYSQL_DATABASE}"

echo "Database restoration complete!"
