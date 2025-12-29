# ASCL.net Flask Web Application - Development Summary

## What Was Built

I successfully created a functional Flask web application that replicates ASCL.net (Astrophysics Source Code Library). The application is fully integrated with the MySQL database and uses the `ascl_core` module for database access.

## Project Structure

```
ascl_net_app_project_home/
├── ascl_net_app/              # Main Flask application
│   ├── __init__.py            # App factory, blueprint registration
│   ├── controllers/           # Route handlers
│   │   ├── index.py          # Homepage (shows recent codes)
│   │   ├── browse.py         # Browse all codes with pagination/sorting
│   │   ├── search.py         # Search functionality
│   │   ├── code_detail.py    # Individual code detail pages
│   │   └── about.py          # About page
│   ├── templates/            # Jinja2 HTML templates
│   │   ├── base.html        # Master template with header/footer/nav
│   │   ├── index.html       # Homepage template
│   │   ├── browse.html      # Browse page with controls
│   │   ├── search.html      # Search page
│   │   ├── code_detail.html # Code detail page
│   │   └── about.html       # About page
│   ├── static/
│   │   └── css/
│   │       └── style.css    # Complete styling (ASCL.net theme)
│   ├── model/               # Database integration
│   │   └── database.py      # Flask-database bridge
│   └── configuration_files/  # Flask config files
│       └── default.cfg      # Default configuration
└── run_ascl_net_app.py      # Development server entry point
```

## Key Features Implemented

### Pages
- **Homepage** (`/`) - Displays 10 most recently added codes
- **Browse** (`/browse`) - Paginated code listing with sorting and filtering
  - Sort by: Title or Date
  - View modes: Abstract or Compact
  - Results per page: 50, 100, 250, or All
- **Search** (`/search`) - Full-text search across title, abstract, and authors
- **Code Detail** (`/code/<ascl_id>`) - Individual code information pages
- **About** (`/about`) - Information about ASCL.net

### Database Integration
- Uses `Trillian2Connection` from `ascl_core` module
- Connects to MySQL database on port 3307
- All queries use SQLAlchemy 2.0 syntax
- Column mapping: `title` (code name), `credit` (authors), `abstract`, `ascl_id`

### Technical Improvements Made
1. **Fixed Jinja2 3.0+ compatibility** - Updated `Markup` and `contextfilter` imports
2. **Fixed SQLAlchemy 2.0 compatibility** - Removed deprecated `bind` parameter, `autocommit`
3. **Fixed MySQL compatibility** - Updated `SET search_path` callback to skip for MySQL

## Environment Requirements

Ensure these environment variables are set:
```bash
export ASCLDB_USER=ascl_db
export ASCLDB_PASSWORD=your_password  # or configure in ~/.my.cnf
export ASCLDB_PORT=3307
```

## How to Run

### Development Mode

```bash
cd /home/demitri/repositories/alt_ascl/source/ascl_net_app_project_home

# Run in debug mode on port 5000
python run_ascl_net_app.py --debug --port 5000

# Access at: http://localhost:5000
```

**Development server features:**
- Auto-reload on code changes
- Detailed error pages with debugger
- Logging to console

### Production Mode

#### Option 1: Using Uvicorn (Recommended)

```bash
cd /home/demitri/repositories/alt_ascl/source/ascl_net_app_project_home

# Set production config
export FLASK_CONFIG=production.cfg

# Run with Uvicorn (4 workers)
uvicorn asgi:application --host 127.0.0.1 --port 8000 --workers 4

# Or with auto-reload for testing:
uvicorn asgi:application --host 127.0.0.1 --port 8000 --reload
```

#### Option 2: Using systemd service

```bash
# Copy service file
sudo cp systemd/ascl_net_app.service /etc/systemd/system/

# Enable and start
sudo systemctl enable ascl_net_app
sudo systemctl start ascl_net_app

# Check status
sudo systemctl status ascl_net_app
```

#### Option 3: With Nginx reverse proxy

1. Configure Nginx:
```bash
sudo cp nginx_ascl_net_app.cfg /etc/nginx/sites-available/ascl_net_app
sudo ln -s /etc/nginx/sites-available/ascl_net_app /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

2. Start Uvicorn backend:
```bash
uvicorn asgi:application --host 127.0.0.1 --port 8000 --workers 4
```

3. Access at: http://your-domain.com

## Database Configuration

The app uses configuration from:
- `ascl_net_app/configuration_files/default.cfg` (development)
- `ascl_net_app/configuration_files/production.cfg` (production)

Key settings:
```ini
USING_SQLALCHEMY = True
DB_TYPE = 'mysql'
DB_DATABASE = 'ascl_db'
DB_HOST = 'localhost'
DB_PORT = '3307'
DB_USER = 'ascl_db'
DB_PASSWORD = ''  # Read from ~/.my.cnf or environment
```

## Known Issues / Next Steps

1. **Testing incomplete** - Some pages may need additional testing with live database

2. **Missing features** from original ASCL.net:
   - User authentication/login
   - Code submission forms
   - Admin interface
   - News/blog section

4. **Database schema** - Verify all column names match actual database schema

5. **Code detail page** - May need additional fields like `site_url`, `code_site` links

## Key Files Modified/Created

**New Files:**
- All templates in `ascl_net_app/templates/` (base.html, index.html, browse.html, search.html, code_detail.html, about.html)
- All controllers in `ascl_net_app/controllers/` (browse.py, search.py, code_detail.py, about.py)
- `ascl_net_app/static/css/style.css`

**Modified Files:**
- `ascl_net_app/__init__.py` - Added blueprint registrations
- `ascl_net_app/jinja_filters.py` - Fixed Jinja2 3.0+ compatibility
- `ascl_net_app/model/DatabaseConnection.py` - Fixed SQLAlchemy 2.0 + MySQL compatibility
- `ascl_net_app/controllers/index.py` - Updated to use Trillian2Connection

## Troubleshooting

**Database connection issues:**
- Verify MySQL is running on port 3307
- Check environment variables: `echo $ASCLDB_USER`
- Test connection: `python scripts/db_connection_test.py`

**Import errors:**
- Ensure `ascl_core` is in Python path
- Check: `python -c "import ascl_core; print('OK')"`

**Template errors:**
- Clear Flask cache: `rm -rf __pycache__`
- Restart with: `python run_ascl_net_app.py --debug`

## Quick Start Checklist

- [ ] MySQL database running on port 3307
- [ ] Environment variables set (ASCLDB_USER, ASCLDB_PASSWORD)
- [ ] Python dependencies installed: `pip install -r requirements.txt`
- [ ] Test database connection: `python scripts/db_connection_test.py`
- [ ] Run dev server: `python run_ascl_net_app.py --debug --port 5000`
- [ ] Access: http://localhost:5000

---

**Last Updated:** October 2, 2025
**Status:** Functional prototype with core features implemented
