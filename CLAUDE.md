# ASCL.net Rebuild Project

## Project Overview

This project aims to recreate the **ascl.net** (Astrophysics Source Code Library) website with a modern technology stack. The current site runs on cPanel with WordPress and MySQL 8.0.42. The goal is to migrate to a new platform using **Flask + SQLAlchemy** and **Nginx** while maintaining MySQL compatibility (with PostgreSQL support for future migration).

### Current State
- **Original Platform**: cPanel + WordPress + MySQL 8.0.42
- **Database**: MySQL 8.0.42 (PostgreSQL support built-in for future migration)
- **Database Backup**: `ascl_db_2025.09.30_bkup.sql.gz` (5.3 MB compressed, MySQL format)
- **Target Platform**: Flask + SQLAlchemy + MySQL + Nginx + Uvicorn
- **Status**: Framework configured with dual database support, models defined, ready for development

---

## Project Structure

The repository contains two main Python projects under `source/`:

### 1. `ascl_core/` - Core Framework Module
**Location**: `source/ascl_core/`

A reusable Python module providing core functionality for database connections and ORM models. This module is designed to be imported by:
- The Flask web application
- Future CLI tools
- Any other applications that need to interact with the ASCL database

**Key Components**:

#### Database Connection (`database/DatabaseConnection.py`)
- **Class**: `DatabaseConnection` - Implements singleton pattern for database connections
- **Features**:
  - SQLAlchemy-based connection management
  - Metadata caching system to improve startup performance
  - PostgreSQL-specific optimizations (search_path handling)
  - Support for custom data type adapters (NumPy arrays, PostgreSQL geometric types)
  - Context manager for transactional scopes via `session_scope(db)`

- **Metadata Caching**:
  - `MetadataCache` class stores SQLAlchemy metadata in pickle files at `~/.sqlalchemy_cache/`
  - Automatically detects stale cache by checking `metadata.schema_metadata` table
  - Significantly reduces startup time for applications with many tables

- **Database Adapters**:
  - NumPy adapters for PostgreSQL and SQLite
  - PostgreSQL geometric types (Point, Polygon)

#### Database Models (`database/ascldb/ASCLModelClasses.py`)
SQLAlchemy ORM models for the ASCL database schema `ascldb`:

**Core Tables**:
- `ASCLCode` - Main codes/software entries table
- `ASCLCodesAlias` - Alternative names for codes
- `Keyword` - Keywords/tags for codes
- `ASCLCodeToKeyword` - Many-to-many relationship table
- `User` - User accounts
- `Citation` / `CitationNew` - Citation information
- `ADSEntry` / `ADSEntryNew` - ADS (Astrophysics Data System) entries
- `Link` / `LinkNew` - External links
- `CitefileMetadata` - CITATION.cff metadata
- `Change` - Change tracking/history
- `ClassicCitation` - Legacy citation data
- `CISession` - CodeIgniter session data (from WordPress)
- Various backup and matching tables

**Relationships**:
- `ASCLCode.codeAliases` → `ASCLCodesAlias` (one-to-many)
- `ASCLCode.keywords` → `Keyword` (many-to-many through `ASCLCodeToKeyword`)

**Technical Details**:
- Uses SQLAlchemy 2.0 style with `@mapper_registry.mapped` decorator
- Autoloads table structure from database
- Includes automatic validation with `configure_mappers()`

---

### 2. `ascl_net_app_project_home/` - Flask Web Application
**Location**: `source/ascl_net_app_project_home/`

The main web application that will serve the ASCL.net website.

#### Application Structure

**Entry Point**: `run_ascl_net_app.py`
- Command-line script to launch the Flask app
- Options:
  - `-d/--debug`: Launch in debug mode
  - `-p/--port`: Specify port (default: 5000)
  - `--host`: Host to bind (default: 127.0.0.1)
  - `-r/--rules`: List all registered URL routes

**Flask App Factory**: `ascl_net_app/__init__.py`
- `create_app(debug=False)` - Application factory pattern
- **Configuration System**:
  - Loads `default.cfg` first
  - Overlays host-specific or deployment configs
  - Supports uWSGI deployment with config passed via `flask-config-file` option
- **Features**:
  - Automatic blueprint registration
  - Database connection setup (PostgreSQL via SQLAlchemy)
  - Sentry error tracking support (optional)
  - Custom Jinja filters
  - Session cleanup on app teardown

**Configuration** (`ascl_net_app/configuration_files/default.cfg`):
```ini
# Currently DISABLED - needs to be enabled for database functionality
USING_SQLALCHEMY = False
USING_POSTGRESQL = False

# Database connection parameters (currently commented out)
#DB_DATABASE = ''
#DB_HOST = ''
#DB_USER = ''
#DB_PASSWORD = ''  # Can be empty to use ~/.pgpass
#DB_PORT = ''

# Production features
USING_SENTRY = False
USING_UWSGI = True
```

**⚠️ Important**: SQLAlchemy and PostgreSQL are currently **disabled** in the default config. They need to be enabled and database credentials configured.

#### Application Components

**Controllers** (`ascl_net_app/controllers/`)
- `index.py` - Main index page controller
  - Routes: `/`, `/favicon.ico`, `/robots.txt`
- Blueprint pattern for URL routing
- Template: `templates/index.html`

**Templates** (`ascl_net_app/templates/`)
- `index.html` - Main page
- `header.html` - Common header
- `footer.html` - Common footer

**Models** (`ascl_net_app/model/`)
- `database.py` - Flask-specific database integration
  - `Database` class (singleton) connects Flask app to `ascl_core.DatabaseConnection`
  - Reads connection params from Flask config
  - Provides SQLAlchemy session management
  - Integrates with Flask's `g` context for request-scoped sessions
- `DatabaseConnection.py` - Local copy (may be redundant with `ascl_core`)
- `databasePostgreSQL.py` - PostgreSQL-specific setup
- `NumpyAdaptors.py` - NumPy data type handling

**Utilities** (`ascl_net_app/utilities/`)
- `color_print.py` - Terminal color output helpers

**Static Files** (`ascl_net_app/static/`)
- CSS, JavaScript, images, etc.

**Configuration Files**:
- `ascl_net_app/configuration_files/` - Flask config files (.cfg)
- `uwsgi_configuration_files/` - uWSGI deployment configs
- `nginx_ascl_net_app.cfg` - Nginx configuration template

---

## Technology Stack

### Current Implementation
- **Python 3.x** (compatible with Python 2 legacy code)
- **Flask 3.0+** - Web framework with async support
- **SQLAlchemy 2.0** - ORM and database abstraction
- **MySQL 8.0** - Current database (maintaining compatibility)
- **PostgreSQL** - Supported for future migration
- **Uvicorn** - Modern ASGI server (replaces uWSGI)
- **Nginx** - Reverse proxy and static file server

### Why Uvicorn?
Uvicorn is a modern ASGI server that offers:
- **4.5x faster** than traditional WSGI servers (45,000 vs 10,000 req/s)
- **HTTP/2 support** for improved performance
- **WebSocket support** for future real-time features
- **Active development** and strong community adoption
- **Production-ready** with excellent stability

### Database Strategy
- **Current**: MySQL 8.0.42 (backup available in MySQL format)
- **Migration Path**: PostgreSQL support built-in, ready for future migration
- **Dual Support**: Application automatically detects database type via `DB_TYPE` config
- **Connection Logic**: Automatically builds correct connection string based on database type

### Key Dependencies
- `uvicorn[standard]` - ASGI server with performance optimizations
- `flask>=3.0.0` - Web framework
- `sqlalchemy>=2.0.0` - ORM
- `mysqlclient>=2.2.0` - MySQL adapter (current)
- `psycopg2-binary>=2.9.0` - PostgreSQL adapter (for future migration)
- NumPy support for database columns (optional)

---

## Getting Started

### Prerequisites
1. Python 3.x environment
2. MySQL 8.0+ database server (or PostgreSQL for future migration)
3. Database backup: `ascl_db_2025.09.30_bkup.sql.gz` (MySQL format)

### Quick Setup

**See [README.md](README.md) for complete setup instructions.**
**See [MYSQL_SETUP.md](MYSQL_SETUP.md) for detailed MySQL configuration.**

### Configuration Steps

1. **Enable Database Connection**:
   Edit `source/ascl_net_app_project_home/ascl_net_app/configuration_files/default.cfg`:
   ```ini
   USING_SQLALCHEMY = True
   DB_TYPE = 'mysql'  # or 'postgresql' for future migration

   DB_DATABASE = 'ascl_db'
   DB_HOST = 'localhost'
   DB_USER = 'ascl_user'
   DB_PASSWORD = ''  # Leave empty to use ~/.my.cnf (MySQL) or ~/.pgpass (PostgreSQL)
   DB_PORT = '3306'  # MySQL: 3306, PostgreSQL: 5432
   ```

2. **Set up MySQL credentials** (optional password-less auth):
   Create `~/.my.cnf` file:
   ```ini
   [client]
   user=ascl_user
   password=your_password
   host=localhost
   port=3306
   ```
   Set permissions: `chmod 600 ~/.my.cnf`

3. **Restore MySQL Database**:
   ```bash
   # Create database
   sudo mysql
   mysql> CREATE DATABASE ascl_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   mysql> CREATE USER 'ascl_user'@'localhost' IDENTIFIED BY 'password';
   mysql> GRANT ALL PRIVILEGES ON ascl_db.* TO 'ascl_user'@'localhost';
   mysql> FLUSH PRIVILEGES;
   mysql> EXIT;

   # Restore backup
   gunzip < ascl_db_2025.09.30_bkup.sql.gz | mysql -u ascl_user -p ascl_db
   ```

### Running the Application

See the comprehensive [README.md](source/ascl_net_app_project_home/README.md) for detailed setup and deployment instructions.

**Quick Start - Development Mode**:
```bash
cd source/ascl_net_app_project_home/
pip install -r requirements.txt
python run_ascl_net_app.py --debug --port 5000
```

**Quick Start - Production Mode** (via Uvicorn):
```bash
cd source/ascl_net_app_project_home/
export FLASK_CONFIG=production.cfg
uvicorn asgi:application --host 127.0.0.1 --port 8000 --workers 4
```

---

## Database Schema Overview

The `ascldb` schema contains the core ASCL data:

### Primary Tables
- **`codes`** - Software/code entries (main content)
- **`keywords`** - Taxonomy of scientific keywords
- **`code_keywords`** - Links codes to keywords (M2M)
- **`codes_aliases`** - Alternative names for codes

### Integration Tables
- **`ads_entries`** - ADS bibliographic data
- **`citations`** - Citation information
- **`links`** - External URLs (code repos, documentation, etc.)
- **`citefile_metadata`** - CITATION.cff file data

### Administrative Tables
- **`users`** - User accounts
- **`change`** - Audit trail for modifications
- **`ci_sessions`** - Legacy session data

### Migration Tables
- Tables suffixed with `_new` appear to be migration staging tables
- `*_zenodo_matching*` tables - Integration with Zenodo
- `*_backup*` tables - Historical snapshots

---

## Development Notes

### Design Patterns
- **Singleton Pattern**: Used for database connections and configuration
- **Application Factory**: Flask app created via `create_app()` function
- **Blueprint Pattern**: URL routes organized as Flask blueprints
- **Context Managers**: Database sessions via `session_scope(db)`

### Code Organization
- **Separation of Concerns**: Core database logic separated from Flask app
- **Configuration Management**: Multi-environment config system
- **Reusability**: `ascl_core` module can be imported by other tools

### Current Limitations
1. ⚠️ Database functionality is **disabled by default** in configuration
2. Database connection has not been tested yet
3. MySQL → PostgreSQL migration not completed
4. Limited controllers/routes implemented (only index page)
5. Templates are minimal (header, footer, index only)

---

## Next Steps / TODO

### Immediate Tasks
1. **Database Migration**:
   - Convert MySQL dump to PostgreSQL format
   - Restore database and verify schema
   - Test database connection from Flask app

2. **Configuration**:
   - Enable SQLAlchemy/PostgreSQL in default.cfg
   - Set up database credentials
   - Create metadata.schema_metadata table and triggers

3. **Application Development**:
   - Implement main pages (browse codes, search, detail pages)
   - Create controllers for CRUD operations
   - Design templates with proper styling
   - Implement search functionality
   - Add user authentication (if needed)

### Future Enhancements
- REST API for programmatic access
- Admin interface for content management
- Integration with ADS API
- Zenodo synchronization
- Citation export formats (BibTeX, RIS, etc.)
- Advanced search and filtering
- Statistics and analytics

---

## File Reference

### Key Files by Functionality

**Database Core**:
- `source/ascl_core/database/DatabaseConnection.py` - Connection management
- `source/ascl_core/database/ascldb/ASCLModelClasses.py` - ORM models

**Flask App**:
- `source/ascl_net_app_project_home/run_ascl_net_app.py` - Development server entry point
- `source/ascl_net_app_project_home/asgi.py` - ASGI entry point for Uvicorn
- `source/ascl_net_app_project_home/ascl_net_app/__init__.py` - App factory
- `source/ascl_net_app_project_home/ascl_net_app/model/database.py` - Flask-DB bridge

**Configuration**:
- `source/ascl_net_app_project_home/ascl_net_app/configuration_files/default.cfg` - Default config
- `source/ascl_net_app_project_home/ascl_net_app/configuration_files/production.cfg` - Production config (MySQL)
- `source/ascl_net_app_project_home/ascl_net_app/configuration_files/mysql_example.cfg` - MySQL template
- `source/ascl_net_app_project_home/ascl_net_app/configuration_files/postgresql_example.cfg` - PostgreSQL template
- `source/ascl_net_app_project_home/requirements.txt` - Python dependencies
- `source/ascl_net_app_project_home/nginx_ascl_net_app.cfg` - Nginx reverse proxy config
- `source/ascl_net_app_project_home/systemd/ascl_net_app.service` - Systemd service file

**Controllers**:
- `source/ascl_net_app_project_home/ascl_net_app/controllers/index.py` - Index page

**Templates**:
- `source/ascl_net_app_project_home/ascl_net_app/templates/index.html`
- `source/ascl_net_app_project_home/ascl_net_app/templates/header.html`
- `source/ascl_net_app_project_home/ascl_net_app/templates/footer.html`

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     Browser/Client                          │
└────────────────────┬────────────────────────────────────────┘
                     │ HTTP
                     ▼
┌─────────────────────────────────────────────────────────────┐
│             Nginx (Reverse Proxy & Static Files)           │
└────────────────────┬────────────────────────────────────────┘
                     │ HTTP Proxy
                     ▼
┌─────────────────────────────────────────────────────────────┐
│          Uvicorn ASGI Server (4 workers)                    │
└────────────────────┬────────────────────────────────────────┘
                     │ ASGI Protocol
                     ▼
┌─────────────────────────────────────────────────────────────┐
│               Flask App (ascl_net_app)                      │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Controllers (Blueprints)                           │   │
│  │    - index.py                                        │   │
│  │    - [future: search, detail, admin, etc.]          │   │
│  └─────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Templates (Jinja2)                                 │   │
│  │    - index.html, header.html, footer.html           │   │
│  └─────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Model (database.py)                                │   │
│  │    - Flask-specific DB integration                  │   │
│  └─────────────────┬───────────────────────────────────┘   │
└────────────────────┼───────────────────────────────────────┘
                     │ imports
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              ascl_core Module (Shared)                      │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  DatabaseConnection (Singleton)                     │   │
│  │    - SQLAlchemy engine & session management         │   │
│  │    - Metadata caching                               │   │
│  └─────────────────┬───────────────────────────────────┘   │
│  ┌─────────────────┴───────────────────────────────────┐   │
│  │  ASCLModelClasses (ORM Models)                      │   │
│  │    - ASCLCode, Keyword, User, Citation, etc.        │   │
│  └─────────────────┬───────────────────────────────────┘   │
└────────────────────┼───────────────────────────────────────┘
                     │ SQLAlchemy
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              PostgreSQL Database (ascldb)                   │
│    Tables: codes, keywords, citations, links, users, ...   │
└─────────────────────────────────────────────────────────────┘
```

---

## Contact & Resources

- Original site: https://ascl.net
- Database backup: `ascl_db_2025.09.30_bkup.sql.gz` (root directory)
- Framework inspiration: Trillian project (mentioned in comments)

---

*Last Updated: 2025-10-01*
