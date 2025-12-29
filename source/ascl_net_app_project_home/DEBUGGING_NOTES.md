# Debugging Notes - Config and Database Connection Issues

## Issues Found and Fixed

### ✅ FIXED: Issue 1 - Wrong Config File Loading in Debug Mode

**Problem**: When running `python run_ascl_net_app.py --debug`, the app was loading `production.cfg` instead of `default.cfg`.

**Root Cause**:
- The config loading logic in `ascl_net_app/__init__.py` (lines 57-100) was:
  1. Load default.cfg (line 60)
  2. Then load server-specific config based on mode
  3. In debug mode (line 65-73), it was loading default.cfg AGAIN, overwriting values
  4. The environment variables from `.env` were overriding the config file settings

**Fix Applied**:
- Modified lines 65-81 to NOT reload default.cfg in debug/testing mode
- Now debug mode uses default.cfg (already loaded) without reloading
- Only production mode loads production.cfg to override defaults

**Verification**:
```bash
python run_ascl_net_app.py --debug
# Should now show: Connecting to MYSQL database at localhost:3307/ascl_db
# (port 3307 from default.cfg, not 3306 from production.cfg)
```

### ⚠️ PARTIAL: Issue 2 - Trillian2DBConnection Logging Not Appearing

**Problem**: Logging statements added to `Trillian2DBConnection.py` are not appearing in logs.

**Root Cause Analysis**:

1. **Import Order**:
   - Line 131-132: Logging is configured ✅
   - Line 172: Flask app database connection created ✅
   - Line 185: Blueprints registered → imports `index.py` → imports Trillian2DBConnection
   - **Logging SHOULD be working at this point!**

2. **Wrong DatabaseConnection Module**:
   - Trillian2DBConnection imports: `from ..DatabaseConnection import DatabaseConnection`
   - This resolves to `ascl_core.database.DatabaseConnection`
   - BUT the error traceback shows: `/home/demitri/repositories/ASCL/dm-dbcore/dm_dbcore/DatabaseConnection.py`
   - **A different module (dm-dbcore) is being used!**

3. **Dual Database Connections**:
   - Flask app creates connection via `ascl_net_app.model.database.Database` (uses ascl_core)
   - index.py creates SECOND connection via `Trillian2DBConnection` (uses dm-dbcore?)
   - These are TWO SEPARATE database connections!

**Status**: Logging was added to Trillian2DBConnection.py but needs verification that it's using the correct DatabaseConnection module.

**Added Logging Statements**:
```python
# Line 62-63: Connection configuration
logger.info(f"Trillian2DBConnection: Configured to connect to {db_config['host']}:{db_config['port']}/{db_config['database']}")
logger.debug(f"Trillian2DBConnection: Connection string: mysql://{db_config['user']}:***@{db_config['host']}:{db_config['port']}/{db_config['database']}")

# Line 68-74: Singleton pattern with logging
logger.debug("Trillian2DBConnection: Attempting to get existing DatabaseConnection singleton")
# ... etc
```

**Next Steps**:
1. Verify which DatabaseConnection module is actually being imported
2. Ensure ascl_core DatabaseConnection is used (not dm-dbcore)
3. Consider consolidating to use ONLY Flask app's database connection
4. If Trillian2DBConnection is needed, ensure it uses the same connection

### 📋 Issue 3 - Cosmetic Warning Message

**Problem**: Console shows "Warning: No server configuration file found."

**Root Cause**:
- Line 102 in `__init__.py` prints warning when `server_config_file` is None
- In debug mode, we now set `server_config_file = None` (intentionally, to avoid reloading)

**Impact**: Cosmetic only - doesn't affect functionality

**Fix (Optional)**:
Change the condition at line 98-102 to:
```python
if server_config_file:
    print(green_text("Loading config file: "), yellow_text(server_config_file))
    app.config.from_pyfile(server_config_file)
elif app.debug or app.testing:
    # Debug/testing mode already loaded default.cfg, no additional config needed
    pass
else:
    print(yellow_text("Warning: No server configuration file found."))
```

## Current State

### Working ✅
- Logging system fully configured and operational
- Console shows colored output with proper log levels
- Log file created at `logs/app.log` with timestamps
- Flask app logger works: `app.logger.info("message")`
- Module loggers work: `logger = get_logger(__name__)`
- Debug mode now uses correct config file (default.cfg)
- Port 3307 is being used (from default.cfg)
- Database connection established successfully

### Needs Investigation ⚠️
- Trillian2DBConnection logging statements not appearing
- Possible dual database connection issue (Flask + Trillian2)
- dm-dbcore vs ascl_core DatabaseConnection conflict
- Cosmetic warning message in debug mode

## Recommendations

### Option 1: Use Flask App Database Connection (Recommended)

**In controllers/index.py**:
```python
from flask import current_app as app, g
from ascl_net_app.model.database import Database
from ascl_core.database.ascldb.ASCLModelClasses import *

@index_page.route("/", methods=['GET'])
def index():
    # Get database session from Flask app's database connection
    database = Database()
    session = database.get_session()

    # Query
    recent_codes = session.query(ASCLCode).order_by(ASCLCode.time_added.desc()).limit(10).all()

    return render_template("index.html", recent_codes=recent_codes)
```

**Pros**:
- Single database connection for entire app
- Managed by Flask app lifecycle
- Proper session teardown (line 174-182 in __init__.py)
- Consistent with Flask patterns

**Cons**:
- Requires updating all controllers that use Trillian2DBConnection

### Option 2: Make Trillian2DBConnection Use Flask Connection

**In ascl_core/database/connections/Trillian2DBConnection.py**:
```python
# Instead of creating new connection, reuse Flask app's connection
from flask import current_app

# This should only be called from within Flask request context
def get_db_connection():
    from ascl_net_app.model.database import Database
    return Database().db

# Export for backward compatibility
db = None  # Set during Flask app initialization
Session = None  # Set during Flask app initialization
```

**Then in ascl_net_app/__init__.py after line 172**:
```python
# Make Trillian2DBConnection use Flask's database connection
import ascl_core.database.connections.Trillian2DBConnection as t2db
t2db.db = database.db
t2db.Session = database.Session()
```

**Pros**:
- Controllers don't need to change
- Single database connection
- Backward compatible

**Cons**:
- More complex
- Trillian2DBConnection becomes Flask-dependent

## Testing After Fixes

```bash
# Test debug mode with logging
python run_ascl_net_app.py --debug

# Expected output should include:
# ✓ Loading config file: .../default.cfg
# ✓ Connecting to MYSQL database at localhost:3307/ascl_db  (port 3307!)
# ✓ Trillian2DBConnection: Configured to connect to localhost:3307/ascl_db
# ✓ Trillian2DBConnection: Creating new DatabaseConnection singleton

# Check log file
tail -f logs/app.log

# Should see Trillian2DBConnection log messages
```

## Summary

The config file issue has been fixed - debug mode now correctly uses default.cfg (port 3307).

The Trillian2DBConnection logging issue needs further investigation to determine:
1. Why dm-dbcore is being used instead of ascl_core
2. Whether dual database connections are intentional
3. How to consolidate to a single connection approach

The logging system itself is working perfectly - the issue is with which DatabaseConnection module is being imported.
