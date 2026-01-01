# Homepage Fixes Needed - Flask v4 vs PHP v3

## Issue Summary
The Flask v4 homepage at `/` does not match the production PHP v3 homepage. Three main issues identified:

1. ❌ Shows `[ascl:0000.000]` instead of `[submitted]` for unpublished codes
2. ❌ Missing date headers that group codes by day
3. ❌ Not filtering to only show published codes

---

## Current Flask Implementation

**Controller:** `/home/demitri/repositories/ASCL/alt_ascl/source/ascl_net_app_project_home/ascl_net_app/controllers/index.py`

```python
# Lines 25-26 - Current query (INCORRECT)
recent_codes = session.query(ASCLCode).order_by(ASCLCode.time_added.desc()).limit(10).all()
templateDict['recent_codes'] = recent_codes
```

**Template:** `/home/demitri/repositories/ASCL/alt_ascl/source/ascl_net_app_project_home/ascl_net_app/templates/index.html`

```jinja2
{# Lines 14-32 - Current display (INCORRECT) #}
{% for code in recent_codes %}
<div class="item">
    <span class="ascl_id">
        [ascl:{{ code.ascl_id }}]  {# ❌ Always shows ascl_id #}
    </span>
    <span class="title">
        <a href="/{{ code.ascl_id }}">{{ code.title | safe }}</a>
    </span>
    ...
</div>
{% endfor %}
```

---

## Production PHP v3 Implementation (Reference)

**Controller:** `/home/demitri/repositories/ASCL/ascl_php_application/web_root/ascl_php_application/application/controllers/home.php`

```php
// Lines 28-40 - PHP query logic (CORRECT)
$this->db->order_by("time_added", "desc");
$this->db->where("time_added >", "00-00-00");        // ✅ Filter out empty dates
$this->db->where("published", 1);                     // ✅ Only published codes
$this->db->limit("10");
$query = $this->db->get("codes");

// Group records by date
$records = array();
foreach($query->result() as $row) {
    $date = substr($row->time_added, 0, 10);          // ✅ Extract YYYY-MM-DD
    $records[$date][$row->id] = get_code_row($row);   // ✅ Group by date
}
```

**Template:** `/home/demitri/repositories/ASCL/ascl_php_application/web_root/ascl_php_application/application/views/home.php`

```php
// Lines 14-24 - PHP display logic (CORRECT)
foreach($records as $k => $v) {
    $date = date("Y M d", strtotime($k));             // ✅ Format date header
    echo "<h3>$date</h3>";                            // ✅ Date header as h3

    $codes = array();
    foreach($v as $kk => $vv) {
        $codes[$kk] = $vv;
    }
    include("template/codelist.php");                 // ✅ Display code list
}
```

**Code Display:** `/home/demitri/repositories/ASCL/ascl_php_application/web_root/ascl_php_application/application/views/template/codelist.php`

```php
// Lines 36-43 - ID display logic (CORRECT)
<span class="ascl_id">
    <? if($v['ascl_id'] == "0000.000") { ?>
        [submitted]                                    // ✅ Show [submitted]
    <? } else { ?>
        [ascl:<?=$v['ascl_id']?>]                     // ✅ Show [ascl:XXXX.XXX]
    <? } ?>
</span>
```

---

## Required Fixes

### Fix 1: Update Controller Query Logic

**File:** `alt_ascl/source/ascl_net_app_project_home/ascl_net_app/controllers/index.py`

```python
# Lines 25-28 - Replace with:
from datetime import date
from collections import OrderedDict

# Get the 10 most recently added published codes
recent_codes_query = (
    session.query(ASCLCode)
    .filter(ASCLCode.published == 1)                   # ✅ Only published
    .filter(ASCLCode.time_added > '00-00-00')          # ✅ Valid dates only
    .order_by(ASCLCode.time_added.desc())
    .limit(10)
    .all()
)

# Group by date (YYYY-MM-DD)
records_by_date = OrderedDict()
for code in recent_codes_query:
    # Extract date from datetime (assumes time_added is datetime or string)
    if isinstance(code.time_added, str):
        date_key = code.time_added[:10]  # First 10 chars: YYYY-MM-DD
    else:
        date_key = code.time_added.strftime('%Y-%m-%d')

    if date_key not in records_by_date:
        records_by_date[date_key] = []

    records_by_date[date_key].append(code)

templateDict['records_by_date'] = records_by_date
```

### Fix 2: Update Template Display Logic

**File:** `alt_ascl/source/ascl_net_app_project_home/ascl_net_app/templates/index.html`

```jinja2
{# Lines 11-36 - Replace with: #}
{% if records_by_date %}
<div class="codelist">

    {% for date_str, codes in records_by_date.items() %}
        {# Display date header (format: YYYY Mon DD) #}
        <h3>{{ date_str | strftime('%Y %b %d') }}</h3>

        {% for code in codes %}
        <div class="item">
            <span class="ascl_id">
                {% if code.ascl_id == "0000.000" %}
                    [submitted]                        {# ✅ Show [submitted] #}
                {% else %}
                    [ascl:{{ code.ascl_id }}]          {# ✅ Show [ascl:XXXX.XXX] #}
                {% endif %}
            </span>

            <span class="title">
                {% if code.ascl_id == "0000.000" %}
                    <a href="/code/v/{{ code.pk }}">{{ code.title | safe }}</a>
                {% else %}
                    <a href="/{{ code.ascl_id }}">{{ code.title | safe }}</a>
                {% endif %}
            </span>

            {% if code.credit %}
            <div class="credit">{{ code.credit }}</div>
            {% endif %}

            <div class="abstract">{{ code.abstract if code.abstract else 'No description available.' }}</div>
        </div>
        {% endfor %}
    {% endfor %}

</div>
{% else %}
    <p>No codes available at this time.</p>
{% endif %}
```

### Fix 3: Add Jinja2 Date Filter (if needed)

**File:** `alt_ascl/source/ascl_net_app_project_home/ascl_net_app/__init__.py`

```python
# Add custom Jinja2 filter for date formatting
from datetime import datetime

def format_date_header(date_str):
    """Format date string as 'YYYY Mon DD' (e.g., '2025 Dec 01')"""
    try:
        dt = datetime.strptime(date_str, '%Y-%m-%d')
        return dt.strftime('%Y %b %d')
    except:
        return date_str

# In create_app() function, add:
app.jinja_env.filters['strftime'] = format_date_header
```

---

## Database Schema Notes

**Table:** `ascl_db_v4.codes`

Relevant columns:
- `pk` (MEDIUMINT UNSIGNED) - Primary key
- `ascl_id` (VARCHAR) - ASCL identifier (e.g., "1404.008" or "0000.000" for unpublished)
- `time_added` (DATETIME) - When code was added
- `published` (TINYINT) - 1 = published, 0 = unpublished
- `title` (VARCHAR) - Code title
- `credit` (TEXT) - Author credits
- `abstract` (TEXT) - Code description

**Key Logic:**
- `ascl_id == "0000.000"` means unpublished/submitted code
- `published == 1` means code is publicly visible
- `time_added > "00-00-00"` filters out codes with invalid dates

---

## Testing Checklist

After applying fixes:

- [ ] Homepage shows only published codes (`published=1`)
- [ ] Codes are grouped by date with h3 headers (e.g., "2025 Dec 01")
- [ ] Unpublished codes (if any shown) display `[submitted]` instead of `[ascl:0000.000]`
- [ ] Published codes display `[ascl:XXXX.XXX]` format
- [ ] Links for unpublished codes go to `/code/v/{pk}`
- [ ] Links for published codes go to `/{ascl_id}`
- [ ] Most recent codes appear first (descending order by time_added)
- [ ] Maximum 10 codes displayed
- [ ] Date headers are formatted as "YYYY Mon DD" (e.g., "2025 Dec 01")

---

## Additional Notes

### Why `0000.000` is Special

In the ASCL system:
- `0000.000` is a placeholder ASCL ID for codes that haven't been assigned a real ID yet
- These are typically newly submitted codes awaiting curator review
- They should display as `[submitted]` to indicate their status
- They link to `/code/v/{pk}` (view by primary key) instead of by ascl_id

### Date Grouping Behavior

- Codes are grouped by their `time_added` date (YYYY-MM-DD)
- Multiple codes added on the same day appear under one date header
- Date headers use h3 tags for semantic hierarchy
- Date format matches PHP production: "YYYY Mon DD" (e.g., "2025 Dec 01")

### Production Reference Files

For exact behavior comparison:
- Controller: `ascl_php_application/web_root/ascl_php_application/application/controllers/home.php` (lines 20-42)
- View: `ascl_php_application/web_root/ascl_php_application/application/views/home.php` (lines 14-24)
- Code display: `ascl_php_application/web_root/ascl_php_application/application/views/template/codelist.php` (lines 18-41)
- Helper: `ascl_php_application/web_root/ascl_php_application/application/helpers/ascl_helper.php` (lines 66-112)

---

**Last Updated:** 2025-12-01
**Related TODO Items:** WEB-001 (Homepage controller), WEB-002 (Homepage template)
