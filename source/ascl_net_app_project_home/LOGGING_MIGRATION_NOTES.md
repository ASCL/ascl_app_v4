# Logging Setup - Migration Notes

## Changes Made

The logging configuration module was moved to the `utilities` subdirectory and properly integrated.

### File Structure

```
ascl_net_app/
├── utilities/
│   ├── __init__.py                 # Exports get_logger and setup_logging
│   └── logging_config.py           # Main logging configuration module
└── __init__.py                     # Calls setup_logging(app)
```

### Import Changes

**OLD** (if you were using logging before):
```python
from ascl_net_app.logging_config import get_logger
```

**NEW** (recommended - shorter):
```python
from ascl_net_app.utilities import get_logger
```

**NEW** (explicit - also works):
```python
from ascl_net_app.utilities.logging_config import get_logger
```

### Integration Points

1. **`ascl_net_app/utilities/__init__.py`**
   - Exports `setup_logging` and `get_logger` for convenience
   - Allows clean imports: `from ascl_net_app.utilities import get_logger`

2. **`ascl_net_app/__init__.py`**
   - Imports and calls `setup_logging(app)` after config is loaded
   - Located at line 127-128, right after Sentry setup
   - Runs BEFORE database connection to ensure all logs are captured

3. **`ascl_net_app/model/database.py`**
   - Added `import logging` and `logger = logging.getLogger(__name__)`
   - Added logging statements for database connection events
   - Works automatically once logging is configured

## Verification

The logging system is working correctly:

✅ Console shows colored output
✅ Log file created at `logs/app.log`
✅ Both Flask app and ascl_core loggers configured
✅ Log rotation enabled (10MB files, 5 backups)
✅ Different log levels for debug vs production

## Testing Commands

```bash
# Test debug mode (verbose)
python test_logging.py --debug

# Test production mode (less verbose)
python test_logging.py

# View log file
cat logs/app.log

# Watch logs in real-time
tail -f logs/app.log
```

## No Breaking Changes

Since this is a new feature, there are no breaking changes. Existing code will continue to work, and you can start using logging immediately.

## Next Steps

1. Read `LOGGING_QUICKSTART.md` for basic usage
2. Start adding logging to your controllers and modules
3. Check `LOGGING.md` for advanced features
4. See `ascl_core/LOGGING_INTEGRATION.md` for ascl_core-specific logging

## Questions?

Check the comprehensive documentation:
- `LOGGING_QUICKSTART.md` - Quick reference
- `LOGGING.md` - Full documentation with examples
- `LOGGING_SUMMARY.md` - Implementation overview
