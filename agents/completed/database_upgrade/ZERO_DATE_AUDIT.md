# Zero Date ('0000-00-00') Usage Audit

**Date**: 2025-12-01
**Issue**: MySQL InnoDB strict mode doesn't allow '0000-00-00 00:00:00' timestamp values
**Context**: DB_UPGRADE_PLAYBOOK.sql converted all '0000-00-00' dates to NULL in database

---

## Summary

The database upgrade (DB_UPGRADE_PLAYBOOK.sql Step 1) converted all '0000-00-00 00:00:00' values to NULL in timestamp columns. However, the original PHP code still uses `"00-00-00"` in WHERE clauses for filtering. We need to ensure the Flask v4 code doesn't replicate this pattern.

---

## Database Changes (Already Applied)

### Step 1 in DB_UPGRADE_PLAYBOOK.sql (Lines 46-101)

**Tables Modified**:
- `codes.time_added` - Converted '0000-00-00' → NULL
- `codes.time_updated` - Converted '0000-00-00' → NULL
- `links_new.updated_at` - Converted '0000-00-00' → NULL
- `links_new.last_working` - Converted '0000-00-00' → NULL

**Column Definitions Changed**:
```sql
-- Before (old schema):
`time_added` timestamp NOT NULL DEFAULT '0000-00-00 00:00:00'
`time_updated` timestamp NOT NULL DEFAULT '0000-00-00 00:00:00'

-- After (upgraded):
`time_added` TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP
`time_updated` TIMESTAMP NULL DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP
```

**Data Migration**:
```sql
-- Converted invalid dates to NULL
UPDATE `codes` SET `time_updated` = NULL WHERE `time_updated` = '0000-00-00 00:00:00';
UPDATE `codes` SET `time_added` = NULL WHERE `time_added` = '0000-00-00 00:00:00';
UPDATE `links_new` SET `updated_at` = NULL WHERE `updated_at` = '0000-00-00 00:00:00';
UPDATE `links_new` SET `last_working` = NULL WHERE `last_working` = '0000-00-00 00:00:00';
```

---

## PHP v3 Code Usage (Production - Reference Only)

### 1. Homepage Controller
**File**: `ascl_php_application/web_root/ascl_php_application/application/controllers/home.php:29`

```php
$this->db->order_by("time_added", "desc");
$this->db->where("time_added >", "00-00-00");  // ← Using '00-00-00' comparison
$this->db->where("published", 1);
$this->db->limit("10");
```

**Purpose**: Filter out codes without valid timestamps
**Issue**: This works in PHP/MySQL non-strict mode, but won't work with InnoDB strict mode
**Why it worked**: MySQL non-strict mode allowed comparisons with invalid dates

### 2. WordPress Code (Not ASCL-specific)
**Files**:
- `ascl_php_application/web_root/wordpress/wp-links-opml.php:85`
- `ascl_php_application/web_root/wordpress/wp-admin/includes/ajax-actions.php:2283`

```php
if ('0000-00-00 00:00:00' !== $bookmark->link_updated) {
    echo $bookmark->link_updated;
}

if ('0000-00-00 00:00:00' === $post->post_date) {
    // Handle unpublished posts
}
```

**Status**: WordPress code - not ASCL-specific, no action needed

---

## Flask v4 Code Status

### ✅ FIXED: Homepage Controller
**File**: `alt_ascl/source/ascl_net_app_project_home/ascl_net_app/controllers/index.py:23-32`

```python
# Get the 10 most recently added published codes
# Matches PHP logic: where("time_added >", "00-00-00") and where("published", 1)
# Note: Using IS NOT NULL instead of > '0000-00-00' to avoid MySQL strict mode issues
recent_codes_query = (
    session.query(ASCLCode)
    .filter(ASCLCode.published == 1)                   # Only published codes
    .filter(ASCLCode.time_added.isnot(None))          # ✅ Valid dates only (not NULL)
    .order_by(ASCLCode.time_added.desc())
    .limit(10)
    .all()
)
```

**Status**: ✅ **Correctly implemented** - uses `.isnot(None)` instead of comparing to '0000-00-00'
**Date Fixed**: 2025-12-01

---

## Verification Queries (From DB_UPGRADE_PLAYBOOK.sql)

### Check for Remaining Zero Dates (Lines 760-776)

```sql
-- Should all return 0 if successful
SET @old_sql_mode_verify = @@sql_mode;
SET sql_mode = REPLACE(REPLACE(@@sql_mode,'NO_ZERO_DATE',''),'NO_ZERO_IN_DATE','');

SELECT 'codes.time_added' as column_name, COUNT(*) as zero_date_count
FROM codes WHERE time_added = '0000-00-00 00:00:00'
UNION ALL
SELECT 'codes.time_updated', COUNT(*)
FROM codes WHERE time_updated = '0000-00-00 00:00:00'
UNION ALL
SELECT 'links_new.updated_at', COUNT(*)
FROM links_new WHERE updated_at = '0000-00-00 00:00:00'
UNION ALL
SELECT 'links_new.last_working', COUNT(*)
FROM links_new WHERE last_working = '0000-00-00 00:00:00';

SET sql_mode = @old_sql_mode_verify;
```

**Expected Result**: All counts should be 0

---

## Potential Issues to Watch For

### 1. ⚠️ Date Insertion/Update Operations

**Risk**: New code that tries to insert/update with '0000-00-00' will fail

**Example Problem**:
```python
# ❌ BAD - Will fail with strict mode
code.time_added = '0000-00-00 00:00:00'

# ✅ GOOD - Use NULL for missing dates
code.time_added = None
```

**Action**: Review any code that sets timestamp values

### 2. ⚠️ Date Comparison in Queries

**Risk**: Comparing timestamps to '0000-00-00' string will fail

**Example Problem**:
```python
# ❌ BAD - Will fail with strict mode
.filter(ASCLCode.time_added > '0000-00-00')

# ✅ GOOD - Check for NULL instead
.filter(ASCLCode.time_added.isnot(None))
```

**Action**: Use NULL checks instead of date string comparisons

### 3. ⚠️ Legacy Data Imports

**Risk**: Importing old data dumps with '0000-00-00' values will fail

**Solution**: Always run DB_UPGRADE_PLAYBOOK.sql after importing production data

### 4. ⚠️ Search/Filter Operations

**Risk**: User-provided date filters might include '0000-00-00'

**Example Problem**:
```python
# If user submits form with date_from = '0000-00-00'
.filter(ASCLCode.time_added >= date_from)  # ❌ Will fail
```

**Solution**: Validate date inputs, convert invalid dates to None

---

## Best Practices for Flask v4

### ✅ DO:
1. **Use NULL checks**: `.isnot(None)` instead of `> '0000-00-00'`
2. **Set timestamps to None**: `code.time_added = None` for missing dates
3. **Validate date inputs**: Convert invalid dates to None before queries
4. **Use datetime objects**: Work with Python datetime, not string comparisons
5. **Document NULL semantics**: NULL means "no date" or "not set"

### ❌ DON'T:
1. **Don't compare to '0000-00-00'**: Will fail in strict mode
2. **Don't set timestamps to '0000-00-00'**: Not allowed in InnoDB strict mode
3. **Don't assume dates exist**: Always check for NULL
4. **Don't import raw production dumps**: Must run upgrade playbook first
5. **Don't replicate PHP date logic**: Use Pythonic NULL checks instead

---

## Migration Checklist

### Database
- [x] Convert all '0000-00-00' dates to NULL in codes table
- [x] Convert all '0000-00-00' dates to NULL in links_new table
- [x] Update column definitions to allow NULL
- [x] Set proper defaults (CURRENT_TIMESTAMP for created, NULL for updated)
- [x] Verify no zero dates remain (verification queries)

### Flask Application
- [x] Update homepage query to use `.isnot(None)` instead of `> '0000-00-00'`
- [ ] Audit all other date comparisons in codebase
- [ ] Audit all date insertion/update operations
- [ ] Add date validation in forms
- [ ] Document NULL handling in code comments
- [ ] Add tests for NULL date handling

### Future Code
- [ ] Add linting rule to prevent '0000-00-00' string literals
- [ ] Document date handling conventions in developer guide
- [ ] Add database migration guide for production cutover

---

## Related Files

**Database Schema**:
- Production schema: `ascl_php_application/ascl_db-schema-2025-10-30.sql`
- Upgrade playbook: `alt_ascl/agents/DB_UPGRADE_PLAYBOOK.sql` (Step 1, Lines 46-101)

**PHP Code (Reference)**:
- Homepage: `ascl_php_application/web_root/ascl_php_application/application/controllers/home.php:29`

**Flask Code**:
- Homepage: `alt_ascl/source/ascl_net_app_project_home/ascl_net_app/controllers/index.py:23-32` ✅

**Documentation**:
- `alt_ascl/agents/DB_UPGRADE_SUMMARY.md`
- `alt_ascl/agents/DB_UPGRADE_ANALYSIS.md`
- `alt_ascl/agents/ASCL_DB Upgrade.md`

---

## Testing Recommendations

### 1. Database Verification
```sql
-- Should return 0 rows
SELECT * FROM codes WHERE time_added = '0000-00-00 00:00:00';
SELECT * FROM codes WHERE time_updated = '0000-00-00 00:00:00';

-- Should return rows where dates are NULL
SELECT COUNT(*) FROM codes WHERE time_added IS NULL;
SELECT COUNT(*) FROM codes WHERE time_updated IS NULL;
```

### 2. Flask Application Testing
```python
# Test homepage loads without errors
# Test that only published codes with valid dates appear
# Test that NULL dates don't cause crashes
# Test date filtering in search/browse features
```

### 3. Edge Case Testing
- Import production data and run upgrade playbook
- Test with codes that have NULL time_added
- Test with codes that have NULL time_updated
- Verify sorting works correctly with NULL dates
- Test date range filters with NULL values

---

## Conclusion

✅ **Status**: Flask v4 homepage is correctly handling date filtering using `.isnot(None)`

⚠️ **Action Required**:
1. Audit remaining Flask code for any date comparisons
2. Add date validation to forms that accept date inputs
3. Document NULL date handling in developer guide
4. Add tests for NULL date scenarios

📝 **Key Takeaway**: The database upgrade converted '0000-00-00' to NULL. Flask v4 code must use NULL checks (`.isnot(None)`) instead of string comparisons (`> '0000-00-00'`) to work with InnoDB strict mode.

---

**Last Updated**: 2025-12-01
**Related TODO Items**: WEB-001 (Homepage controller), DB-002 (InnoDB conversion)
