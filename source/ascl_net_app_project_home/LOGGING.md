# Logging Configuration Guide

This document describes the logging setup for the ASCL.net Flask application.

## Overview

The application uses Python's built-in `logging` module with a centralized configuration that handles:

1. **Flask application logs** - Application-level events, requests, errors
2. **ascl_core module logs** - Database operations and ORM events
3. **SQLAlchemy query logs** - SQL queries (optional, controlled by config)

## Quick Start

Logging is **automatically configured** when the Flask app starts. No manual setup is required!

### Enable SQL Query Logging

To see all SQL queries being executed, edit your config file:

```python
# In default.cfg or production.cfg
LOG_SQL_QUERIES = True
```

### Disable Colored Console Output

```python
# In default.cfg or production.cfg
ENABLE_COLOR_LOGS = False
```

## Log Outputs

### 1. Console (stdout)
- **Format**: `LEVEL [logger_name] message`
- **Colors**: Enabled by default (can be disabled with `ENABLE_COLOR_LOGS = False`)
- **Filters**: Shows all logs from the application

### 2. File (`logs/app.log`)
- **Format**: `YYYY-MM-DD HH:MM:SS LEVEL [logger_name:line_number] message`
- **Rotation**: Automatically rotates when file reaches 10 MB
- **Retention**: Keeps 5 backup files (app.log.1, app.log.2, etc.)
- **Location**: `source/ascl_net_app_project_home/logs/app.log`

## Log Levels by Mode

### Debug Mode (`python run_ascl_net_app.py --debug`)
- **Flask app**: `DEBUG` - Shows detailed application flow
- **ascl_core**: `DEBUG` - Shows database connection details, metadata caching
- **SQLAlchemy**: `INFO` (or enabled with `LOG_SQL_QUERIES`)
- **Libraries**: `WARNING` - Suppresses noise from urllib3, werkzeug, etc.

### Production Mode (`uvicorn asgi:application`)
- **Flask app**: `INFO` - Important events only
- **ascl_core**: `INFO` - Database connection events
- **SQLAlchemy**: `WARNING` (unless `LOG_SQL_QUERIES = True`)
- **Libraries**: `WARNING`

## Using Logging in Your Code

### In Flask Controllers/Views

```python
from flask import current_app as app

@blueprint.route('/example')
def example():
    app.logger.info("Processing example request")
    app.logger.debug("Debug details here")
    app.logger.warning("Something might be wrong")
    app.logger.error("An error occurred!")
    return "OK"
```

### In Other Application Modules

```python
from ascl_net_app.utilities import get_logger
# or
from ascl_net_app.utilities.logging_config import get_logger

logger = get_logger(__name__)

def my_function():
    logger.info("Doing something important")
    logger.debug("Detailed information")
    logger.error("Something failed!")
```

### In ascl_core Module

The `ascl_core` module already has logging configured:

```python
import logging

logger = logging.getLogger("DatabaseConnection logger")

# Logging is automatically set up when Flask app starts
logger.info("Database connection established")
logger.debug("Metadata cache loaded")
```

## Log Message Best Practices

### Good Log Messages ✅

```python
logger.info("Processing 150 codes from database")
logger.debug(f"User {user_id} requested page {page_num}")
logger.error(f"Failed to connect to database: {error}")
logger.warning(f"Slow query took {duration}s: {query[:100]}")
```

### Poor Log Messages ❌

```python
logger.info("Processing")  # Too vague
logger.debug(data)  # Don't log raw objects
logger.error("Error!")  # No context
```

## Color Scheme (Console Output)

When `ENABLE_COLOR_LOGS = True`:

- **DEBUG**: Cyan - Detailed diagnostic information
- **INFO**: Green - Normal application flow
- **WARNING**: Yellow - Something unexpected but handled
- **ERROR**: Red - Error that needs attention
- **CRITICAL**: Bold Red - Severe error

Logger names are also colored:
- **ascl_net_app**: Bright Blue
- **DatabaseConnection logger**: Magenta
- **sqlalchemy.engine**: Bright Cyan
- **Other loggers**: Gray

## Viewing Logs

### Watch logs in real-time (development)
```bash
# In one terminal
python run_ascl_net_app.py --debug

# In another terminal
tail -f logs/app.log
```

### Search logs
```bash
# Find all errors
grep ERROR logs/app.log

# Find database-related logs
grep "DatabaseConnection" logs/app.log

# Find SQL queries (if LOG_SQL_QUERIES enabled)
grep "SELECT\|INSERT\|UPDATE\|DELETE" logs/app.log
```

### View recent logs
```bash
tail -n 100 logs/app.log  # Last 100 lines
head -n 50 logs/app.log   # First 50 lines
```

## Configuration Reference

All logging-related config options in `default.cfg` or `production.cfg`:

```python
# Enable colored console output (default: True)
ENABLE_COLOR_LOGS = True

# Log all SQL queries to console and file (default: False)
# WARNING: Very verbose! Only use for debugging
LOG_SQL_QUERIES = False
```

## Log File Rotation

The application uses `RotatingFileHandler` with these settings:

- **Max file size**: 10 MB
- **Backup count**: 5 files
- **File naming**: `app.log`, `app.log.1`, `app.log.2`, ... `app.log.5`

When `app.log` reaches 10 MB:
1. `app.log.4` → `app.log.5` (oldest is deleted)
2. `app.log.3` → `app.log.4`
3. `app.log.2` → `app.log.3`
4. `app.log.1` → `app.log.2`
5. `app.log` → `app.log.1`
6. New `app.log` is created

## Troubleshooting

### No logs appearing

**Check 1**: Verify logging is initialized
```python
# In ascl_net_app/__init__.py, you should see:
from .logging_config import setup_logging
setup_logging(app)
```

**Check 2**: Verify log level
```python
# Try lowering log level temporarily
app.logger.setLevel(logging.DEBUG)
```

### Too many logs (noise)

**Solution 1**: Disable SQL query logging
```python
LOG_SQL_QUERIES = False  # in config file
```

**Solution 2**: Increase log level for specific loggers
```python
# In logging_config.py, add:
logging.getLogger('noisy_library').setLevel(logging.ERROR)
```

### Colors not showing in console

**Check 1**: Verify terminal supports colors
```bash
echo $TERM  # Should show 'xterm-256color' or similar
```

**Check 2**: Verify config setting
```python
ENABLE_COLOR_LOGS = True  # in config file
```

**Check 3**: Check if stdout is a TTY (colors auto-disable for pipes/redirects)
```bash
# Colors work:
python run_ascl_net_app.py --debug

# Colors disabled (redirected to file):
python run_ascl_net_app.py --debug > output.txt
```

### Log file permissions error

```bash
# Fix permissions on logs directory
chmod 755 logs/
chmod 644 logs/app.log
```

## Advanced: Customizing Logging

### Add a new logger

```python
# In logging_config.py, inside setup_logging():

custom_logger = logging.getLogger('my_custom_module')
custom_logger.setLevel(logging.INFO)
custom_logger.handlers.clear()
custom_logger.addHandler(console_handler)
custom_logger.addHandler(file_handler)
custom_logger.propagate = False
```

### Add a separate log file for specific module

```python
# In logging_config.py:

# Create separate handler for database logs
db_file_handler = RotatingFileHandler(
    log_dir / 'database.log',
    maxBytes=10 * 1024 * 1024,
    backupCount=3
)
db_file_handler.setFormatter(file_formatter)

# Attach to database logger
db_logger = logging.getLogger('DatabaseConnection logger')
db_logger.addHandler(db_file_handler)
```

### Send critical errors to email (production)

```python
from logging.handlers import SMTPHandler

if not app.debug and app.config.get('ADMIN_EMAIL'):
    mail_handler = SMTPHandler(
        mailhost='localhost',
        fromaddr='server-error@ascl.net',
        toaddrs=[app.config['ADMIN_EMAIL']],
        subject='ASCL Application Error'
    )
    mail_handler.setLevel(logging.ERROR)
    app.logger.addHandler(mail_handler)
```

## Examples

### Example: Logging a database query

```python
from flask import current_app as app

def get_code_by_id(code_id):
    app.logger.debug(f"Fetching code with ID: {code_id}")

    try:
        code = session.query(ASCLCode).filter_by(id=code_id).first()

        if code:
            app.logger.info(f"Found code: {code.title}")
            return code
        else:
            app.logger.warning(f"Code not found: {code_id}")
            return None

    except Exception as e:
        app.logger.error(f"Database error while fetching code {code_id}: {e}")
        raise
```

### Example: Logging request processing

```python
from flask import Blueprint, request, current_app as app
from ascl_net_app.utilities import get_logger

blueprint = Blueprint('search', __name__)
logger = get_logger(__name__)

@blueprint.route('/search')
def search():
    query = request.args.get('q', '')

    logger.info(f"Search request: query='{query}', ip={request.remote_addr}")

    try:
        results = perform_search(query)
        logger.debug(f"Search returned {len(results)} results")
        return render_template('search_results.html', results=results)

    except Exception as e:
        logger.error(f"Search failed for query '{query}': {e}", exc_info=True)
        return "Search error", 500
```

## Production Recommendations

1. **Use INFO level** in production (already configured)
2. **Disable SQL query logging** unless debugging (`LOG_SQL_QUERIES = False`)
3. **Monitor log file size** - The 10MB limit with 5 backups = ~50MB max
4. **Set up log rotation** with system tools if needed (logrotate)
5. **Consider centralized logging** for multiple servers (ELK stack, Graylog, etc.)
6. **Alert on ERROR/CRITICAL** logs in production
7. **Regularly review logs** for warnings and errors

## See Also

- [Python logging documentation](https://docs.python.org/3/library/logging.html)
- [Flask logging documentation](https://flask.palletsprojects.com/en/latest/logging/)
- [SQLAlchemy logging](https://docs.sqlalchemy.org/en/latest/core/engines.html#configuring-logging)
