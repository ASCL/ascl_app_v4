# Flask App Logging Integration with dm-dbcore

## Overview

This Flask app uses the `dm-dbcore` package for database connections. The `dm-dbcore` module already has logging configured, so you just need to set up the Flask app's logging configuration to capture those logs.

## Current Setup

The Flask app configures logging in `ascl_net_app/utilities/logging_config.py`:

```python
# dm-dbcore module logger (database operations)
dm_dbcore_logger = logging.getLogger('DatabaseConnection logger')
dm_dbcore_logger.setLevel(dm_dbcore_log_level)
dm_dbcore_logger.addHandler(console_handler)
dm_dbcore_logger.addHandler(file_handler)
```

## How It Works

1. Flask app calls `setup_logging(app)` in `ascl_net_app/__init__.py`
2. The logging configuration finds and configures the "DatabaseConnection logger" from dm-dbcore
3. All log messages from `dm-dbcore` are sent to both console and log file (`logs/app.log`)

## Log Output Examples

### Normal Operations

```
INFO     [DatabaseConnection logger] Metadata cache is current.
INFO     [ascl_net_app.controllers.index] Rendering homepage
```

### Debug Mode

```
DEBUG    [DatabaseConnection logger] Loading metadata from cache
DEBUG    [DatabaseConnection logger]     - ascldb.codes
DEBUG    [DatabaseConnection logger]     - ascldb.keywords
INFO     [DatabaseConnection logger] Metadata cache loaded: 14 tables
```

## Configuration

The Flask app's logging is configured in `ascl_net_app/utilities/logging_config.py`. To adjust dm-dbcore logging:

```python
# Change log level for dm-dbcore
dm_dbcore_log_level = logging.DEBUG if debug_mode else logging.INFO

# Get the logger
dm_dbcore_logger = logging.getLogger('DatabaseConnection logger')
dm_dbcore_logger.setLevel(dm_dbcore_log_level)
```

## Testing Logging

To verify logging is working:

```python
# In a Flask route or controller
from dm_dbcore import DatabaseConnection

db = DatabaseConnection()  # Will log connection status
# Check logs/app.log or console output
```

## Best Practices

1. **Don't create duplicate loggers** - dm-dbcore already has logging
2. **Use appropriate log levels** in Flask app configuration
3. **Check logs/app.log** for persistent log history
4. **Use colored console output** in development for easier reading

## Troubleshooting

### Not seeing dm-dbcore logs?

Check that the logger is configured:
```python
import logging
logger = logging.getLogger('DatabaseConnection logger')
print(f"Logger level: {logger.level}")
print(f"Handlers: {logger.handlers}")
```

### Too many logs?

Increase the log level:
```python
logging.getLogger('DatabaseConnection logger').setLevel(logging.WARNING)
```

### Want file-only logging?

Remove the console handler:
```python
dm_dbcore_logger = logging.getLogger('DatabaseConnection logger')
dm_dbcore_logger.handlers = [file_handler]  # Only file handler
```

## See Also

- `/home/demitri/repositories/ASCL/dm-dbcore/LOGGING_INTEGRATION.md` - Full dm-dbcore logging documentation
- `ascl_net_app/utilities/logging_config.py` - Flask logging configuration
- `ascl_net_app/utilities/color_print.py` - Color formatting utilities
