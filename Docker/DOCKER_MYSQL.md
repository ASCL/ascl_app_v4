# MySQL Docker Setup for ASCL Development

This guide explains how to run the MySQL database for local development using Docker.

## Prerequisites

- Docker and Docker Compose installed
- The database backup file `ascl_db_2025.09.30_bkup.sql` (decompressed) in the repository root

## Quick Start

### Option 1: Using Environment Variables (Recommended)

1. **Set environment variables:**
   ```bash
   export ASCLDB_USER=your_username
   export ASCLDB_PASSWORD=your_password
   export ASCLDB_ROOT_PASSWORD=your_root_password
   ```

2. **Start the MySQL container:**
   ```bash
   docker-compose up -d
   ```

### Option 2: Using Default Credentials

1. **Start the MySQL container (uses defaults):**
   ```bash
   docker-compose up -d
   ```
   Default credentials:
   - User: `ascl_user`
   - Password: `ascl_password`
   - Root Password: `ascl_root_password`

### Verify Setup

2. **Check the container status:**
   ```bash
   docker-compose ps
   ```

3. **View logs to confirm database restoration:**
   ```bash
   docker-compose logs -f mysql
   ```

   Wait for "MySQL init process done. Ready for start up."

4. **Test the connection:**
   ```bash
   # Using environment variable
   docker exec -it ascl_mysql mysql -u "$ASCLDB_USER" -p"$ASCLDB_PASSWORD" ascl_db -e "SHOW TABLES;"

   # Or with default credentials
   docker exec -it ascl_mysql mysql -u ascl_user -pascl_password ascl_db -e "SHOW TABLES;"
   ```

## Database Credentials

### Environment Variables (Recommended)

Both Docker and Flask read from these environment variables:

- `ASCLDB_USER` - Database username
- `ASCLDB_PASSWORD` - Database password
- `ASCLDB_ROOT_PASSWORD` - MySQL root password (Docker only)

### Default Values

If environment variables are not set, these defaults are used:

- **Host:** localhost
- **Port:** 3306
- **Database:** ascl_db
- **User:** ascl_user
- **Password:** ascl_password
- **Root Password:** ascl_root_password

## Useful Commands

### Stop the database:
```bash
docker-compose stop
```

### Start the database:
```bash
docker-compose start
```

### Stop and remove the container (keeps data):
```bash
docker-compose down
```

### Stop and remove everything including data:
```bash
docker-compose down -v
```

### Access MySQL shell as root:
```bash
# Using environment variable
docker exec -it ascl_mysql mysql -u root -p"$ASCLDB_ROOT_PASSWORD"

# Using default
docker exec -it ascl_mysql mysql -u root -pascl_root_password
```

### Access MySQL shell as database user:
```bash
# Using environment variable
docker exec -it ascl_mysql mysql -u "$ASCLDB_USER" -p"$ASCLDB_PASSWORD" ascl_db

# Using default
docker exec -it ascl_mysql mysql -u ascl_user -pascl_password ascl_db
```

### View container logs:
```bash
docker-compose logs -f mysql
```

### Export current database:
```bash
# Using environment variable
docker exec ascl_mysql mysqldump -u root -p"$ASCLDB_ROOT_PASSWORD" ascl_db | gzip > ascl_db_export_$(date +%Y%m%d).sql.gz

# Using default
docker exec ascl_mysql mysqldump -u root -pascl_root_password ascl_db | gzip > ascl_db_export_$(date +%Y%m%d).sql.gz
```

## Troubleshooting

### Database backup not restoring automatically

The `.sql` file in `docker-entrypoint-initdb.d` is automatically processed on first container start. If the database is empty, check:

1. **Verify the SQL file exists:**
   ```bash
   ls -lh ascl_db_2025.09.30_bkup.sql
   ```

2. **Check container logs for errors:**
   ```bash
   docker-compose logs mysql
   ```

3. **Manually restore if needed:**
   ```bash
   # Using environment variable
   docker exec -i ascl_mysql mysql -u root -p"$ASCLDB_ROOT_PASSWORD" ascl_db < ascl_db_2025.09.30_bkup.sql

   # Using default
   docker exec -i ascl_mysql mysql -u root -pascl_root_password ascl_db < ascl_db_2025.09.30_bkup.sql
   ```

### Port 3306 already in use

If you have MySQL running locally, either:
1. Stop your local MySQL service
2. Or change the port mapping in `docker-compose.yml`:
   ```yaml
   ports:
     - "3307:3306"  # Use port 3307 on host instead
   ```
   Then update `default.cfg` to use port 3307.

### Connection refused from Flask app

Make sure the MySQL container is running and healthy:
```bash
docker-compose ps
```

The `STATUS` should show "healthy" after a few seconds.

## Data Persistence

Database data is stored in a Docker volume named `mysql_data`. This means:
- Data persists across container restarts
- Data survives `docker-compose down` (but not `docker-compose down -v`)
- To reset the database, remove the volume: `docker-compose down -v` then `docker-compose up -d`

## Running the Flask App

Once the database is running, you can start the Flask application:

### Using Environment Variables (Recommended)

```bash
# Set credentials (use same values as Docker)
export ASCLDB_USER=your_username
export ASCLDB_PASSWORD=your_password

# Run the app
cd source/ascl_net_app_project_home/
python run_ascl_net_app.py --debug --port 5000
```

### Using Configuration File

If you don't set environment variables, the app will use credentials from `default.cfg`:

```bash
cd source/ascl_net_app_project_home/
python run_ascl_net_app.py --debug --port 5000
```

**Note:** Environment variables override configuration file values.
