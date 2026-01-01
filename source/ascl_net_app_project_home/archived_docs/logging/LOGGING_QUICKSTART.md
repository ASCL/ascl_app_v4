# Logging Quick Start

## TL;DR

Logging is **already enabled** and configured automatically! You don't need to do anything special.

## Where Logs Go

1. **Console** - Colored output (green for INFO, red for ERROR, etc.)
2. **File** - `logs/app.log` (automatically rotates at 10MB)

## Configuration Options

Edit `ascl_net_app/configuration_files/default.cfg`:

```python
# See all SQL queries (very verbose!)
LOG_SQL_QUERIES = True

# Disable colored console output
ENABLE_COLOR_LOGS = False
```

## Using Logging in Your Code

### In Flask views/controllers:

```python
from flask import current_app as app

@blueprint.route('/example')
def example():
    app.logger.info("Processing request")
    app.logger.error("Something went wrong!")
    return "OK"
```

### In other modules:

```python
from ascl_net_app.utilities import get_logger
# or
from ascl_net_app.utilities.logging_config import get_logger

logger = get_logger(__name__)

def my_function():
    logger.info("Doing something")
    logger.debug("Debug details")
    logger.error("Error occurred!")
```

## Testing

Run the test script to verify logging works:

```bash
# Test in debug mode (more verbose)
python test_logging.py --debug

# Test in production mode
python test_logging.py

# View the log file
cat logs/app.log
```

## Common Tasks

### View logs in real-time:
```bash
tail -f logs/app.log
```

### Find errors:
```bash
grep ERROR logs/app.log
```

### View recent logs:
```bash
tail -n 100 logs/app.log
```

## Log Levels

In **debug mode** (`--debug` flag):
- Shows DEBUG, INFO, WARNING, ERROR, CRITICAL
- Very verbose, good for development

In **production mode** (no `--debug`):
- Shows INFO, WARNING, ERROR, CRITICAL
- Less verbose, good for production

## More Information

See [LOGGING.md](LOGGING.md) for complete documentation.

## What Gets Logged Automatically

When you run the app, you'll see:
- ✅ Application startup messages
- ✅ Database connection events
- ✅ Configuration loading
- ✅ Request processing (if you add logging to your controllers)
- ✅ Errors and exceptions (automatically)
- ✅ SQL queries (if `LOG_SQL_QUERIES = True`)

## Example Output

Console (colored):
```
INFO     [ascl_net_app] Application 'ascl_net_app' created.
INFO     [DatabaseConnection logger] Connecting to MYSQL database at localhost:3307/ascl_db
INFO     [ascl_net_app.model.database] Database connection established successfully
```

Log file (`logs/app.log`):
```
2025-11-29 10:30:45 INFO     [ascl_net_app:121] Application 'ascl_net_app' created.
2025-11-29 10:30:45 INFO     [DatabaseConnection logger:75] Connecting to MYSQL database at localhost:3307/ascl_db
2025-11-29 10:30:45 INFO     [ascl_net_app.model.database:81] Database connection established successfully
```
