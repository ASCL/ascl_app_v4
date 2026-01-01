# Author Name Linking Fix

**Date**: 2025-12-01
**Issue**: Author names in v4 Flask are plain text, but v3 PHP links them to author search pages
**Status**: ✅ Fixed

---

## Problem

On the homepage (and other code listings), author names should be clickable links that take users to a credit search page showing all codes by that author.

**v3 PHP Behavior**:
```
Author One; Author Two; Author Three
↓ (becomes) ↓
[Author One] ; [Author Two] ; [Author Three]
(each name is a clickable link)
```

**v4 Flask (Before Fix)**:
```
Author One; Author Two; Author Three
(plain text, not clickable)
```

---

## PHP v3 Implementation (Reference)

### Function: `link_author_credit()`
**File**: `ascl_php_application/web_root/ascl_php_application/application/helpers/ascl_helper.php:185-199`

```php
function link_author_credit($string) {
    $arr = explode(";",$string);        // Split by semicolon
    $newstring = '';
    foreach($arr as $k => $v) {
        $v = trim($v);                   // Trim whitespace
        if($k > 0)
            $newstring .= "; ";          // Add semicolon separator

        // Create link to credit search: /code/cs/{author_name}
        $newstring .= '<a href="/code/cs/'.rawurlencode($v).'" class="local">'.$v.'</a>';
    }
    return $newstring;
}
```

**Usage** (in `get_code_row()` function, line 86):
```php
$code['credit'] = link_author_credit($row->credit);
```

**Link Format**: `/code/cs/{URL_ENCODED_AUTHOR_NAME}`
- Example: `/code/cs/John%20Smith`
- Links to credit search page showing all codes by that author
- Class `local` added for styling

---

## Flask v4 Fix

### 1. Created Jinja2 Filter
**File**: `alt_ascl/source/ascl_net_app_project_home/ascl_net_app/jinja_filters.py:82-112`

```python
@contextfilter
@blueprint.app_template_filter()
def link_author_credit(context, credit_string):
    """Convert author credits to linked author names

    Matches PHP production function: link_author_credit($string)
    Input: "Author One; Author Two; Author Three"
    Output: '<a href="/code/cs/Author%20One">Author One</a>; <a href="/code/cs/Author%20Two">Author Two</a>; ...'

    Each author name becomes a link to a credit search page (/code/cs/{name})
    where users can find all codes by that author.
    """
    from urllib.parse import quote

    if not credit_string:
        return ''

    # Split by semicolon
    authors = credit_string.split(';')

    # Build linked author list
    linked_authors = []
    for author in authors:
        author = author.strip()
        if author:
            # URL-encode the author name and create link
            encoded_name = quote(author)
            linked_authors.append(f'<a href="/code/cs/{encoded_name}" class="local">{author}</a>')

    # Join with semicolons
    return Markup('; '.join(linked_authors))
```

**Key Features**:
- ✅ Splits credit string by semicolons
- ✅ Trims whitespace from each author name
- ✅ URL-encodes author names using `urllib.parse.quote()`
- ✅ Creates links to `/code/cs/{encoded_name}`
- ✅ Adds CSS class `local` for styling
- ✅ Returns `Markup()` object (prevents double-escaping)
- ✅ Handles empty/None credit strings gracefully

### 2. Updated Template
**File**: `alt_ascl/source/ascl_net_app_project_home/ascl_net_app/templates/index.html:37-39`

**Before**:
```jinja2
{% if code.credit %}
<div class="credit">{{ code.credit }}</div>
{% endif %}
```

**After**:
```jinja2
{% if code.credit %}
<div class="credit">{{ code.credit | link_author_credit }}</div>
{% endif %}
```

---

## How It Works

### Example Input
```
credit = "Jane Smith; John Doe; Alice Johnson"
```

### Processing Steps

1. **Split by semicolon**:
   ```python
   ['Jane Smith', ' John Doe', ' Alice Johnson']
   ```

2. **Trim whitespace**:
   ```python
   ['Jane Smith', 'John Doe', 'Alice Johnson']
   ```

3. **URL-encode each name**:
   ```python
   ['Jane%20Smith', 'John%20Doe', 'Alice%20Johnson']
   ```

4. **Create links**:
   ```html
   <a href="/code/cs/Jane%20Smith" class="local">Jane Smith</a>
   <a href="/code/cs/John%20Doe" class="local">John Doe</a>
   <a href="/code/cs/Alice%20Johnson" class="local">Alice Johnson</a>
   ```

5. **Join with semicolons**:
   ```html
   <a href="/code/cs/Jane%20Smith" class="local">Jane Smith</a>; <a href="/code/cs/John%20Doe" class="local">John Doe</a>; <a href="/code/cs/Alice%20Johnson" class="local">Alice Johnson</a>
   ```

### Rendered Output
```html
<div class="credit">
  <a href="/code/cs/Jane%20Smith" class="local">Jane Smith</a>;
  <a href="/code/cs/John%20Doe" class="local">John Doe</a>;
  <a href="/code/cs/Alice%20Johnson" class="local">Alice Johnson</a>
</div>
```

---

## Target Route: `/code/cs/<author_name>`

**PHP v3 Route**:
- Controller: `ascl_php_application/web_root/ascl_php_application/application/controllers/code.php`
- Method: `cs()` - Credit search function
- URL: `/code/cs/{author_name}`

**Flask v4 Status**:
- ⚠️ **TODO**: Route `/code/cs/<author_name>` needs to be implemented
- See TODO_MASTER.md: **SEARCH-004** (Credit search controller)
- See TODO_MASTER.md: **SEARCH-005** (Credit search template)

**What the route should do**:
1. Accept author name as URL parameter
2. Search `codes.credit` field for matching author names
3. Display all codes where that author is credited
4. Handle partial matches intelligently
5. Parse author names correctly (handle variations)

---

## Testing Checklist

### Visual Tests
- [ ] Homepage displays author names as links
- [ ] Multiple authors separated by semicolons
- [ ] Links have correct href: `/code/cs/{encoded_name}`
- [ ] Links have CSS class `local`
- [ ] Spaces in names are URL-encoded correctly

### Functional Tests
- [ ] Clicking author link navigates to `/code/cs/{author_name}`
- [ ] Special characters in names are encoded properly
- [ ] Single-author credits work correctly
- [ ] Multi-author credits work correctly
- [ ] Empty/null credits don't cause errors

### Edge Cases
- [ ] Names with special characters (apostrophes, hyphens, accents)
- [ ] Names with multiple spaces
- [ ] Very long author lists (10+ authors)
- [ ] Credits with trailing semicolons
- [ ] Credits with extra whitespace

---

## Related Files

**Jinja Filter**:
- `alt_ascl/source/ascl_net_app_project_home/ascl_net_app/jinja_filters.py` (lines 82-112)

**Template**:
- `alt_ascl/source/ascl_net_app_project_home/ascl_net_app/templates/index.html` (line 38)

**PHP Reference**:
- `ascl_php_application/web_root/ascl_php_application/application/helpers/ascl_helper.php` (lines 185-199)

**TODO Items**:
- TODO_MASTER.md: SEARCH-004 (Credit search controller)
- TODO_MASTER.md: SEARCH-005 (Credit search template)

---

## Next Steps

1. ✅ **Done**: Create `link_author_credit` Jinja2 filter
2. ✅ **Done**: Update homepage template to use filter
3. ⚠️ **TODO**: Implement `/code/cs/<author_name>` route (credit search)
4. ⚠️ **TODO**: Apply filter to other templates (browse, search results, code detail)
5. ⚠️ **TODO**: Test with production data (various author name formats)

---

## Other Templates That Need This Filter

The `link_author_credit` filter should be applied wherever code credits are displayed:

- ✅ `templates/index.html` (homepage) - **DONE**
- ⚠️ `templates/browse.html` (browse all codes) - **TODO**
- ⚠️ `templates/search.html` (search results) - **TODO**
- ⚠️ `templates/code_detail.html` (individual code page) - **TODO**
- ⚠️ Any other code listing templates - **TODO**

**Pattern to use**:
```jinja2
{% if code.credit %}
<div class="credit">{{ code.credit | link_author_credit }}</div>
{% endif %}
```

---

**Last Updated**: 2025-12-01
**Status**: ✅ Filter created and applied to homepage
**Related TODO Items**: WEB-002 (Homepage template), SEARCH-004/005 (Credit search)
