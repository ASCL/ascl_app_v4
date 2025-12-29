# ASCL.net - Astrophysics Source Code Library

> Modern rebuild of the ASCL.net website using Flask, SQLAlchemy, MySQL/PostgreSQL, and Uvicorn

## Overview

The Astrophysics Source Code Library (ASCL) is a registry of source codes used in astronomy and astrophysics research. This repository contains a complete rebuild of the ascl.net website, transitioning from WordPress to a modern Python stack while maintaining the MySQL database (with PostgreSQL support for future migration).

**Technology Stack:**
- **Flask 3.0+** - Web framework with async support
- **SQLAlchemy 2.0** - ORM and database abstraction
- **MySQL 8.0** - Current database (PostgreSQL supported for future migration)
- **Uvicorn** - High-performance ASGI server
- **Nginx** - Reverse proxy and static file server
- **bcrypt** - Secure password hashing

## Features

### Core Functionality
- ✅ **Browse & Search**: Full-text search with Typesense integration
- ✅ **Code Detail Pages**: Comprehensive information for each software entry
- ✅ **News System**: Latest updates and announcements
- ✅ **Statistics Dashboard**: Public metrics and visualizations at `/dashboard`
  - Total codes, citations, views, keywords
  - Codes added by year with bar charts
  - Most viewed and most cited codes
  - Recently added codes
  - Top keywords
  - Metadata completeness tracking

### Admin Interface
- ✅ **Secure Authentication**: bcrypt password hashing with automatic SHA-1 migration
- ✅ **Session Management**: Login/logout with attempt tracking (lockout after 10 failures)
- ✅ **Code Management**: View unpublished and archived codes
- ⏳ **Future**: Code editing, insertion, bulk operations

### Security
- ✅ **Password Hashing**: Industry-standard bcrypt (work factor 12)
- ✅ **Automatic Migration**: Legacy SHA-1 passwords upgraded on login
- ✅ **Login Protection**: Rate limiting with lockout mechanism
- ⏳ **Future**: CSRF protection, role-based access control

## Project Structure

```
alt_ascl/
├── source/
│   ├── ascl_core/              # Core database module (reusable)
│   │   └── database/
│   │       ├── DatabaseConnection.py
│   │       └── ascldb/
│   │           └── ASCLModelClasses.py
│   │
│   └── ascl_net_app_project_home/  # Flask web application
│       ├── ascl_net_app/
│       │   ├── __init__.py           # App factory
│       │   ├── configuration_files/
│       │   │   ├── default.cfg
│       │   │   └── production.cfg
│       │   ├── controllers/          # URL route handlers
│       │   ├── model/                # Database integration
│       │   ├── templates/            # Jinja2 templates
│       │   └── static/               # CSS, JS, images
│       ├── run_ascl_net_app.py       # Development server
│       ├── asgi.py                   # ASGI entry point
│       ├── requirements.txt
│       ├── nginx_ascl_net_app.cfg
│       └── systemd/
│           └── ascl_net_app.service
│
├── ascl_db_2025.09.30_bkup.sql.gz  # MySQL database backup
├── CLAUDE.md                         # Detailed technical documentation
└── README.md                         # This file
```

## Quick Start

### Prerequisites

- Python 3.8 or higher
- MySQL 8.0 or higher (or PostgreSQL 12+ for future migration)
- pip and virtualenv
- (Production) Nginx web server
- (Optional) Docker for MySQL containerized setup

### Development Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd alt_ascl/source/ascl_net_app_project_home
   ```

2. **Create and activate virtual environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure database** (Optional - see Database Setup below)

   Edit `ascl_net_app/configuration_files/default.cfg`:
   ```ini
   USING_SQLALCHEMY = True
   DB_TYPE = 'mysql'  # or 'postgresql'

   DB_DATABASE = 'ascl_db'
   DB_HOST = 'localhost'
   DB_USER = 'your_username'
   DB_PASSWORD = ''  # Empty = use ~/.my.cnf (MySQL) or ~/.pgpass (PostgreSQL)
   DB_PORT = '3306'  # MySQL: 3306, PostgreSQL: 5432
   ```

5. **Run development server**
   ```bash
   python run_ascl_net_app.py --debug --port 5000
   ```

6. **Access the application**

   Open your browser to: http://localhost:5000

### Development Server Options

```bash
# Run with debug mode on custom port
python run_ascl_net_app.py --debug --port 8080

# Make accessible from network (use with caution)
python run_ascl_net_app.py --debug --host 0.0.0.0 --port 5000

# List all registered routes
python run_ascl_net_app.py --rules
```

## Database Setup

### Option 1: Run Without Database (Default)

The application can run without a database connection for initial development. The database is disabled by default in `default.cfg`.

### Option 2: Set Up MySQL (Current/Recommended)

The existing database backup is in MySQL format and can be restored directly.

**See [MYSQL_SETUP.md](MYSQL_SETUP.md) for complete MySQL setup instructions.**

**Quick setup:**

1. **Install and restore database:**
   ```bash
   # Install MySQL
   sudo apt install mysql-server  # Ubuntu/Debian
   # or
   brew install mysql             # macOS

   # Create database and user
   sudo mysql
   mysql> CREATE DATABASE ascl_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   mysql> CREATE USER 'ascl_user'@'localhost' IDENTIFIED BY 'your_password';
   mysql> GRANT ALL PRIVILEGES ON ascl_db.* TO 'ascl_user'@'localhost';
   mysql> FLUSH PRIVILEGES;
   mysql> EXIT;

   # Restore backup
   gunzip < ascl_db_2025.09.30_bkup.sql.gz | mysql -u ascl_user -p ascl_db
   ```

2. **Configure application:**
   ```bash
   cd source/ascl_net_app_project_home/ascl_net_app/configuration_files/
   cp mysql_example.cfg development.cfg
   nano development.cfg  # Edit database credentials
   ```

3. **Run with MySQL:**
   ```bash
   export FLASK_CONFIG=development.cfg
   python run_ascl_net_app.py --debug
   ```

### Option 3: Set Up PostgreSQL (Future Migration)

PostgreSQL support is built-in for future migration. See example configuration:

```bash
cd source/ascl_net_app_project_home/ascl_net_app/configuration_files/
cp postgresql_example.cfg my_postgres.cfg
# Edit configuration, then:
export FLASK_CONFIG=my_postgres.cfg
```

**Note:** Migrating from MySQL to PostgreSQL requires data conversion (use `pgloader` or similar tool).

## Production Deployment

### Method 1: Uvicorn with Systemd (Recommended)

This method runs Uvicorn as a systemd service, automatically restarting on failure.

1. **Install system dependencies**
   ```bash
   sudo apt update
   sudo apt install python3-pip python3-venv nginx
   ```

2. **Set up application directory**
   ```bash
   sudo mkdir -p /var/www/ascl_net_app
   sudo chown www-data:www-data /var/www/ascl_net_app
   ```

3. **Deploy application**
   ```bash
   # Copy files to production directory
   sudo cp -r source/ascl_net_app_project_home/* /var/www/ascl_net_app/

   # Set up virtual environment
   cd /var/www/ascl_net_app
   sudo -u www-data python3 -m venv venv
   sudo -u www-data venv/bin/pip install -r requirements.txt
   ```

4. **Configure production settings**

   Edit `/var/www/ascl_net_app/ascl_net_app/configuration_files/production.cfg`:
   ```ini
   # Database configuration
   USING_SQLALCHEMY = True
   DB_TYPE = 'mysql'  # or 'postgresql' for future migration

   # Set production database credentials
   DB_DATABASE = 'ascl_db'
   DB_HOST = 'localhost'
   DB_USER = 'ascl_user'
   DB_PASSWORD = ''  # Use ~/.my.cnf (MySQL) or ~/.pgpass (PostgreSQL)
   DB_PORT = '3306'  # MySQL: 3306, PostgreSQL: 5432

   # IMPORTANT: Change the secret key!
   SECRET_KEY = 'generate-a-random-secret-key-here'

   # Enable HTTPS cookies (requires SSL)
   SESSION_COOKIE_SECURE = True
   ```

5. **Install systemd service**
   ```bash
   sudo cp systemd/ascl_net_app.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable ascl_net_app
   sudo systemctl start ascl_net_app
   ```

6. **Check service status**
   ```bash
   sudo systemctl status ascl_net_app
   sudo journalctl -u ascl_net_app -f  # Follow logs
   ```

7. **Configure Nginx**
   ```bash
   # Copy Nginx configuration
   sudo cp nginx_ascl_net_app.cfg /etc/nginx/sites-available/ascl_net_app

   # Enable site
   sudo ln -s /etc/nginx/sites-available/ascl_net_app /etc/nginx/sites-enabled/

   # Test configuration
   sudo nginx -t

   # Reload Nginx
   sudo systemctl reload nginx
   ```

8. **Set up SSL with Let's Encrypt** (recommended)
   ```bash
   sudo apt install certbot python3-certbot-nginx
   sudo certbot --nginx -d ascl.net -d www.ascl.net
   ```

### Method 2: Manual Uvicorn (Development/Testing)

Run Uvicorn directly without systemd:

```bash
cd source/ascl_net_app_project_home

# Single worker (development)
uvicorn asgi:application --host 127.0.0.1 --port 8000

# Multiple workers (production)
export FLASK_CONFIG=production.cfg
uvicorn asgi:application \
    --host 127.0.0.1 \
    --port 8000 \
    --workers 4 \
    --log-level info \
    --access-log
```

### Production Checklist

- [ ] Database credentials configured
- [ ] SECRET_KEY changed in production.cfg
- [ ] MySQL database set up and populated (see MYSQL_SETUP.md)
- [ ] Systemd service installed and running
- [ ] Nginx configured as reverse proxy
- [ ] SSL certificate installed (Let's Encrypt)
- [ ] Firewall configured (allow 80, 443)
- [ ] Log rotation configured
- [ ] Backups scheduled
- [ ] Monitoring set up (optional: Sentry)

## Configuration

### Environment Variables

```bash
# Specify config file (overrides default)
export FLASK_CONFIG=production.cfg

# Example: Running with custom config
FLASK_CONFIG=my_config.cfg uvicorn asgi:application
```

### Configuration Files

- `default.cfg` - Base configuration, database disabled
- `production.cfg` - Production settings with MySQL (database enabled)
- `mysql_example.cfg` - MySQL configuration template
- `postgresql_example.cfg` - PostgreSQL configuration template (for future migration)

Configuration files are located in:
```
ascl_net_app/configuration_files/
```

### Key Configuration Options

| Setting | Description | Default |
|---------|-------------|---------|
| `USING_SQLALCHEMY` | Enable database | `False` |
| `DB_TYPE` | Database type ('mysql' or 'postgresql') | `'mysql'` |
| `DB_DATABASE` | Database name | Not set |
| `DB_HOST` | Database host | Not set |
| `DB_USER` | Database user | Not set |
| `DB_PASSWORD` | Database password (empty uses ~/.my.cnf or ~/.pgpass) | Not set |
| `DB_PORT` | Database port (3306 for MySQL, 5432 for PostgreSQL) | Not set |
| `SECRET_KEY` | Flask session key | Must change! |
| `SESSION_COOKIE_SECURE` | Require HTTPS | `True` (prod) |
| `USING_SENTRY` | Error tracking | `False` |

**Legacy Flags** (deprecated, use `DB_TYPE` instead):
- `USING_POSTGRESQL` - Sets database to PostgreSQL
- `USING_MYSQL` - Sets database to MySQL

## Performance Tuning

### Uvicorn Workers

Rule of thumb: `(2 x CPU cores) + 1`

```bash
# 4-core machine = 8-9 workers
uvicorn asgi:application --workers 9
```

### Nginx Caching

Add to `nginx_ascl_net_app.cfg`:
```nginx
proxy_cache_path /var/cache/nginx levels=1:2 keys_zone=ascl_cache:10m max_size=1g;

location / {
    proxy_cache ascl_cache;
    proxy_cache_valid 200 10m;
    # ... rest of config
}
```

### Database Connection Pool

Edit `source/ascl_core/database/DatabaseConnection.py`:
```python
me.engine = create_engine(
    me.database_connection_string,
    pool_size=10,           # Adjust based on workers
    max_overflow=20,
    pool_pre_ping=True,
    echo=False
)
```

## Monitoring & Logging

### View Logs

```bash
# Systemd service logs
sudo journalctl -u ascl_net_app -f

# Nginx access logs
sudo tail -f /var/log/nginx/ascl_net_app_access.log

# Nginx error logs
sudo tail -f /var/log/nginx/ascl_net_app_error.log
```

### Enable Sentry (Optional)

1. Sign up at https://sentry.io
2. Get your DSN
3. Edit `production.cfg`:
   ```ini
   USING_SENTRY = True
   SENTRY_DSN = "https://your-dsn@sentry.io/project-id"
   ```
4. Install Sentry SDK:
   ```bash
   pip install sentry-sdk[flask]
   ```

## Development

### Adding New Routes

1. Create controller in `ascl_net_app/controllers/`:
   ```python
   # my_page.py
   import flask

   my_page_bp = flask.Blueprint("my_page", __name__)

   @my_page_bp.route("/mypage")
   def my_page():
       return flask.render_template("my_page.html")
   ```

2. Register blueprint in `ascl_net_app/__init__.py`:
   ```python
   def register_blueprints(app=None):
       from .controllers.index import index_page
       from .controllers.my_page import my_page_bp

       app.register_blueprint(index_page)
       app.register_blueprint(my_page_bp)
   ```

3. Create template in `ascl_net_app/templates/my_page.html`

### Database Queries

```python
from ascl_core.database.ascldb.ASCLModelClasses import ASCLCode
from flask import g

# In a route handler
def my_route():
    session = g.my_session
    codes = session.query(ASCLCode).limit(10).all()
    return render_template("codes.html", codes=codes)
```

### Running Tests

```bash
# Install test dependencies
pip install pytest pytest-flask

# Run tests
pytest
```

## Troubleshooting

### Port Already in Use

```bash
# Find process using port 8000
sudo lsof -i :8000

# Kill process
sudo kill -9 <PID>
```

### Database Connection Errors

1. Check PostgreSQL is running:
   ```bash
   sudo systemctl status postgresql
   ```

2. Verify credentials:
   ```bash
   psql -h localhost -U ascl_user -d ascl_db
   ```

3. Check `~/.pgpass` permissions:
   ```bash
   chmod 600 ~/.pgpass
   ```

### Uvicorn Won't Start

Check logs:
```bash
sudo journalctl -u ascl_net_app -n 50
```

Common issues:
- Virtual environment not activated
- Missing dependencies (`pip install -r requirements.txt`)
- Port already in use
- Permissions (should run as www-data)

### Nginx 502 Bad Gateway

1. Check Uvicorn is running:
   ```bash
   sudo systemctl status ascl_net_app
   ```

2. Check Uvicorn port:
   ```bash
   sudo netstat -tlnp | grep 8000
   ```

3. Check Nginx error log:
   ```bash
   sudo tail -f /var/log/nginx/ascl_net_app_error.log
   ```

## Migration from WordPress

**Status**: In progress

The current database backup is in MySQL format from WordPress. Migration steps:

1. Extract WordPress data structure
2. Map WordPress tables to new schema
3. Convert MySQL dump to PostgreSQL
4. Migrate content and relationships
5. Verify data integrity

See `CLAUDE.md` for detailed database schema documentation.

## Contributing

**Note**: This is currently a private rebuild project. Contribution guidelines will be added when ready for public contributions.

## Documentation

### Project Documentation
- **`CLAUDE.md`** - Comprehensive technical documentation and architecture details
- **`TODO_MASTER.md`** - Complete task list and migration progress tracking
- **`PASSWORD_HASHING_UPGRADE.md`** - Security upgrade documentation (SHA-1 → bcrypt)
- **`DEPLOYMENT.md`** - Production deployment guide (systemd, Docker, Nginx)
- **`LOGGING.md`** - Logging configuration and troubleshooting

### External Resources
- **Flask Documentation**: https://flask.palletsprojects.com/
- **Uvicorn Documentation**: https://www.uvicorn.org/
- **SQLAlchemy Documentation**: https://docs.sqlalchemy.org/
- **bcrypt Documentation**: https://github.com/pyca/bcrypt/

## License

[License information to be added]

## Contact

- Project Repository: [Repository URL]
- Original Site: https://ascl.net

---

*Last Updated: 2025-12-28*

## Recent Changes

### 2025-12-28
- ✅ Implemented public statistics dashboard at `/dashboard`
- ✅ Upgraded admin authentication from SHA-1 to bcrypt password hashing
- ✅ Added automatic password migration (no user password reset required)
- ✅ Database fully operational with MySQL 8.0.42
- ✅ All core pages implemented (index, about, browse, search, code detail, news)
- ✅ Admin interface for managing unpublished/archived codes
- 📝 Comprehensive documentation updates

### 2025-10-01
- Initial project structure setup
- Database schema migration planning
- Flask application framework implementation
