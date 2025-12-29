# Password Hashing Security Upgrade

**Date**: 2025-12-28
**Status**: ✅ Completed
**Migration Type**: Automatic (no user action required)

## Overview

The ASCL admin authentication system has been upgraded from **SHA-1** (cryptographically weak) to **bcrypt** (industry-standard secure hashing).

### Why This Matters

- **SHA-1 is deprecated**: SHA-1 is vulnerable to collision attacks and not recommended for password hashing
- **Bcrypt is secure**: Bcrypt uses adaptive hashing with configurable work factor, making brute-force attacks computationally expensive
- **Automatic migration**: Existing users don't need to reset passwords - migration happens transparently on their next login

## Technical Changes

### 1. Database Schema Update

**Migration**: `migrations/001_upgrade_password_hashing.sql`

```sql
-- Expanded password field from 40 to 60 characters
ALTER TABLE users
MODIFY COLUMN password VARCHAR(60) NOT NULL;
```

- **SHA-1 hash**: 40 hex characters (e.g., `477f575e76ca79dfecc5...`)
- **Bcrypt hash**: 60 characters (e.g., `$2b$12$O9CgpcaWFGz7qlwqtTvGNO...`)

### 2. Dual-Hash Authentication System

The login system now supports **both** hash types during the migration period:

```python
def _verify_password(password, stored_hash):
    """Verify password against bcrypt OR SHA-1 hash."""
    if stored_hash.startswith('$2'):
        # Bcrypt hash - use bcrypt verification
        return bcrypt.checkpw(...)
    elif len(stored_hash) == 40:
        # Legacy SHA-1 hash - verify and mark for migration
        return (sha1_hash == stored_hash, is_legacy=True)
```

### 3. Automatic Migration on Login

When a user with a legacy SHA-1 password logs in successfully:

1. Password is verified against SHA-1 hash
2. System detects it's a legacy hash
3. Password is automatically re-hashed using bcrypt
4. Database is updated with new bcrypt hash
5. Next login uses bcrypt verification (faster, more secure)

**Implementation**: `ascl_net_app/controllers/admin.py:_migrate_user_password()`

```python
if is_legacy:
    _migrate_user_password(user, password, db_session)
    # User password now upgraded to bcrypt
```

## Migration Status

### Current Status

- ✅ Database schema updated (password field expanded to 60 chars)
- ✅ Bcrypt dependency added to requirements.txt
- ✅ Dual-hash authentication implemented
- ✅ Automatic migration on login enabled
- ✅ Tests passing (see `test_password_hashing.py`)

### User Migration Progress

To check how many users have been migrated:

```sql
-- Count users by hash type
SELECT
    CASE
        WHEN password LIKE '$2%' THEN 'bcrypt'
        WHEN LENGTH(password) = 40 THEN 'sha1'
        ELSE 'unknown'
    END as hash_type,
    COUNT(*) as user_count
FROM users
GROUP BY hash_type;
```

**Initial state** (2025-12-28):
- All users have SHA-1 hashes
- Migration will happen automatically as users log in

## Security Improvements

### Before (SHA-1)
- **Algorithm**: SHA-1 (deprecated since 2017)
- **Vulnerability**: Fast hashing allows ~8 billion hashes/second on modern GPUs
- **Work factor**: None (single hash operation)
- **Salt**: No built-in salt mechanism

### After (Bcrypt)
- **Algorithm**: Bcrypt (industry standard)
- **Resistance**: Adaptive work factor makes brute-force attacks impractical
- **Work factor**: 12 rounds (configurable), ~0.3 seconds per hash
- **Salt**: Automatically included in hash (unique per password)
- **Future-proof**: Work factor can be increased as hardware improves

## Testing

### Unit Tests

Run the test suite:

```bash
cd /home/demitri/repositories/ASCL/alt_ascl/source/ascl_net_app_project_home
python test_password_hashing.py
```

Expected output:
```
✓ SHA-1 hashing works correctly
✓ Bcrypt hashing works correctly
✓ SHA-1 password verification works correctly
✓ Bcrypt password verification works correctly
✓ Migration scenario works correctly
✓ ALL TESTS PASSED
```

### Manual Testing

1. **Test legacy SHA-1 login**:
   - Log in with existing credentials
   - Should authenticate successfully
   - Check logs for migration message
   - Verify password hash in database changed to bcrypt

2. **Test bcrypt login**:
   - Log in again with same credentials
   - Should authenticate successfully (now using bcrypt)
   - No migration message (already migrated)

## Usage for New Users

### Creating a New User with Bcrypt

```python
from ascl_net_app.controllers.admin import _hash_password_bcrypt

# Hash a new password
password = "secure_password_123"
hashed = _hash_password_bcrypt(password)

# Store in database
# INSERT INTO users (username, real_name, password, login_attempts)
# VALUES ('newuser', 'New User', '...bcrypt_hash...', 0);
```

### Manual Password Reset (if needed)

```sql
-- Generate hash using Python first:
-- >>> from ascl_net_app.controllers.admin import _hash_password_bcrypt
-- >>> _hash_password_bcrypt('new_password')
-- '$2b$12$...'

UPDATE users
SET password = '$2b$12$...',
    login_attempts = 0
WHERE username = 'username';
```

## Rollback (Emergency Only)

If you need to rollback the changes:

1. **Stop the application**
2. **Revert database schema**:
   ```sql
   ALTER TABLE users MODIFY COLUMN password VARCHAR(40) NOT NULL;
   ```
3. **Restore `admin.py` from git** (before bcrypt changes)
4. **Remove bcrypt from requirements.txt**

**WARNING**: This will break authentication for any users already migrated to bcrypt!

## Files Modified

| File | Change |
|------|--------|
| `requirements.txt` | Added `bcrypt>=4.0.0` |
| `migrations/001_upgrade_password_hashing.sql` | Database migration script |
| `ascl_net_app/controllers/admin.py` | Password hashing functions and login logic |
| `test_password_hashing.py` | Comprehensive test suite |

## References

- [OWASP Password Storage Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html)
- [bcrypt Python Documentation](https://github.com/pyca/bcrypt/)
- [Why bcrypt?](https://codahale.com/how-to-safely-store-a-password/)

## Support

For issues or questions:
- Check application logs: `logs/app.log`
- Review migration status with SQL query above
- Run test suite: `python test_password_hashing.py`
