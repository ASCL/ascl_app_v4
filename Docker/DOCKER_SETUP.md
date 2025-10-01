# Docker Setup Guide for ASCL Project

This guide provides step-by-step instructions for setting up and managing the MySQL Docker container for the ASCL project.

---

## Initial Setup

### 1. Install Docker

If you don't have Docker installed:

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install docker.io docker-compose
sudo systemctl start docker
sudo systemctl enable docker
```

**macOS:**
- Download and install [Docker Desktop for Mac](https://www.docker.com/products/docker-desktop)

**Verify installation:**
```bash
docker --version
docker-compose --version
```

### 2. Add Your User to Docker Group (Linux only)

To run Docker without `sudo`:
```bash
sudo usermod -aG docker $USER
```

Log out and back in for this to take effect.

---

## Setting Up the Database

### Step 1: Configure Credentials

**Option A: Using a `.env` file (Recommended)**

1. Copy the example file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` with your preferred editor:
   ```bash
   nano .env
   ```

3. Update the passwords:
   ```bash
   ASCLDB_USER=ascl_user
   ASCLDB_PASSWORD=your_secure_password
   ASCLDB_ROOT_PASSWORD=your_secure_root_password
   ```

4. Save and exit

**Option B: Using environment variables**

```bash
export ASCLDB_USER=ascl_user
export ASCLDB_PASSWORD=your_secure_password
export ASCLDB_ROOT_PASSWORD=your_secure_root_password
```

**Option C: Use defaults (development only)**

Skip this step - Docker will use default passwords from `docker-compose.yml`

### Step 2: Verify the Database Backup File

Make sure the decompressed SQL file exists:
```bash
ls -lh ascl_db_2025.09.30_bkup.sql
```

If you only have the `.gz` file, decompress it:
```bash
gunzip ascl_db_2025.09.30_bkup.sql.gz
```

### Step 3: Start the MySQL Container

```bash
docker-compose up -d
```

The `-d` flag runs it in detached mode (background).

**What this does:**
- Downloads MySQL 8.0.42 image (first time only)
- Creates a container named `ascl_mysql`
- Creates a persistent volume `mysql_data` for database storage
- Imports the database backup automatically
- Starts MySQL on port 3306

### Step 4: Verify the Container is Running

```bash
docker-compose ps
```

You should see:
```
NAME         STATUS    PORTS
ascl_mysql   healthy   0.0.0.0:3306->3306/tcp
```

Wait for the status to show `healthy` (may take 10-20 seconds).

### Step 5: Check Database Restoration

View the logs to confirm the database was restored:
```bash
docker-compose logs mysql
```

Look for messages like:
- `MySQL init process done. Ready for start up.`
- `mysqld: ready for connections`

### Step 6: Test the Connection

```bash
# Using environment variables
docker exec -it ascl_mysql mysql -u "$ASCLDB_USER" -p"$ASCLDB_PASSWORD" ascl_db -e "SHOW TABLES;"

# Or with defaults
docker exec -it ascl_mysql mysql -u ascl_user -pascl_password ascl_db -e "SHOW TABLES;"
```

You should see a list of database tables.

---

## Running the Flask Application

Once the database is running:

### Option 1: With Environment Variables

```bash
# Set credentials (same as Docker)
export ASCLDB_USER=ascl_user
export ASCLDB_PASSWORD=your_secure_password

# Navigate to app directory
cd source/ascl_net_app_project_home/

# Install dependencies (first time only)
pip install -r requirements.txt

# Run the app
python run_ascl_net_app.py --debug --port 5000
```

### Option 2: With Default Credentials

If using defaults in `default.cfg`:
```bash
cd source/ascl_net_app_project_home/
python run_ascl_net_app.py --debug --port 5000
```

The app will be available at: http://localhost:5000

---

## Daily Usage

### Starting the Database

If the container is stopped:
```bash
docker-compose start
```

Or use `up` if it was removed:
```bash
docker-compose up -d
```

### Stopping the Database

```bash
docker-compose stop
```

This stops the container but preserves all data.

### Restarting the Database

```bash
docker-compose restart
```

### Viewing Logs

```bash
# Follow logs in real-time
docker-compose logs -f mysql

# View last 100 lines
docker-compose logs --tail=100 mysql
```

---

## Shutting Down

### Stop the Container (Keep Data)

```bash
docker-compose stop
```

- Container stops running
- All data is preserved in the `mysql_data` volume
- Can restart with `docker-compose start`

### Remove the Container (Keep Data)

```bash
docker-compose down
```

- Container is removed
- All data is still preserved in the `mysql_data` volume
- Next `docker-compose up -d` will create a new container with existing data

### Complete Removal (Delete Everything)

**⚠️ WARNING: This deletes all database data!**

```bash
docker-compose down -v
```

The `-v` flag removes the volume, permanently deleting all database data.

Use this only when you want to start fresh or reset the database.

---

## Troubleshooting

### Container Won't Start

1. **Check if port 3306 is in use:**
   ```bash
   sudo lsof -i :3306
   ```

   If another MySQL is running, either:
   - Stop it: `sudo systemctl stop mysql`
   - Or change Docker port in `docker-compose.yml`:
     ```yaml
     ports:
       - "3307:3306"
     ```

2. **Check Docker logs for errors:**
   ```bash
   docker-compose logs mysql
   ```

### Permission Denied Errors

```bash
# Linux only - ensure Docker is running
sudo systemctl start docker

# Check if your user is in docker group
groups $USER

# If not, add it:
sudo usermod -aG docker $USER
# Then log out and back in
```

### Database is Empty After Starting

The database should auto-restore on first start. If empty:

1. **Check if SQL file was mounted:**
   ```bash
   docker exec -it ascl_mysql ls -lh /docker-entrypoint-initdb.d/
   ```

2. **Manually restore:**
   ```bash
   docker exec -i ascl_mysql mysql -u root -p"$ASCLDB_ROOT_PASSWORD" ascl_db < ascl_db_2025.09.30_bkup.sql
   ```

### Can't Connect from Flask

1. **Verify container is healthy:**
   ```bash
   docker-compose ps
   ```

2. **Test connection manually:**
   ```bash
   docker exec -it ascl_mysql mysql -u "$ASCLDB_USER" -p"$ASCLDB_PASSWORD" ascl_db -e "SELECT 1;"
   ```

3. **Check Flask config has correct credentials:**
   - Environment variables set?
   - Or `default.cfg` has correct values?

### Reset Everything

To completely reset the database to the backup state:

```bash
# Stop and remove everything
docker-compose down -v

# Start fresh (will re-import backup)
docker-compose up -d

# Wait for healthy status
docker-compose ps
```

---

## Useful Commands

### Access MySQL Shell

```bash
# As database user
docker exec -it ascl_mysql mysql -u "$ASCLDB_USER" -p"$ASCLDB_PASSWORD" ascl_db

# As root
docker exec -it ascl_mysql mysql -u root -p"$ASCLDB_ROOT_PASSWORD"
```

### Export Database

```bash
# Create a backup
docker exec ascl_mysql mysqldump -u root -p"$ASCLDB_ROOT_PASSWORD" ascl_db | gzip > ascl_db_backup_$(date +%Y%m%d).sql.gz
```

### Import SQL File

```bash
docker exec -i ascl_mysql mysql -u root -p"$ASCLDB_ROOT_PASSWORD" ascl_db < your_file.sql
```

### Check Container Resource Usage

```bash
docker stats ascl_mysql
```

### Remove Old/Unused Docker Images

```bash
# See all images
docker images

# Remove unused images
docker image prune

# Remove specific image
docker rmi mysql:8.0.42
```

---

## Data Persistence

### Where is the Data Stored?

Database data is stored in a Docker volume named `mysql_data`.

**View volume details:**
```bash
docker volume ls
docker volume inspect alt_ascl_mysql_data
```

**Backup the volume:**
```bash
docker run --rm \
  -v alt_ascl_mysql_data:/data \
  -v $(pwd):/backup \
  ubuntu tar czf /backup/mysql_volume_backup.tar.gz /data
```

**Restore a volume:**
```bash
docker run --rm \
  -v alt_ascl_mysql_data:/data \
  -v $(pwd):/backup \
  ubuntu tar xzf /backup/mysql_volume_backup.tar.gz -C /
```

---

## Quick Reference

| Task | Command |
|------|---------|
| Start database | `docker-compose up -d` |
| Stop database | `docker-compose stop` |
| Restart database | `docker-compose restart` |
| View logs | `docker-compose logs -f mysql` |
| Check status | `docker-compose ps` |
| Access MySQL shell | `docker exec -it ascl_mysql mysql -u $ASCLDB_USER -p$ASCLDB_PASSWORD ascl_db` |
| Remove container (keep data) | `docker-compose down` |
| Remove everything | `docker-compose down -v` |

---

## See Also

- [DOCKER_MYSQL.md](DOCKER_MYSQL.md) - Detailed MySQL-specific documentation
- [README.md](README.md) - Project overview
- [source/ascl_net_app_project_home/README.md](source/ascl_net_app_project_home/README.md) - Flask app documentation
