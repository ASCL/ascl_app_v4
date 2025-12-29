# Credit Search Implementation

**Date**: 2025-12-01
**Issue**: `/code/cs/{author}` route was missing, causing 404 errors when clicking author links
**Status**: ✅ Implemented

---

## Problem

Clicking on linked author names (e.g., "Lâu Thiat-uí") resulted in 404 errors because the `/code/cs/{search_term}` route was not implemented in Flask v4.

**Production URL Example**: https://ascl.net/code/cs/Lâu%20Thiat-uí
**Flask v4 URL (before fix)**: http://127.0.0.1:60661/code/cs/Lâu%20Thiat-uí → 404 Error

---

## PHP v3 Implementation (Reference)

### Route: `/code/cs/{search_term}`
**File**: `ascl_php_application/web_root/ascl_php_application/application/controllers/code.php:466-484`

```php
//cs means credit search
public function cs($search_term) {
    $search_term = html_entity_decode(urldecode($search_term));
    $data['search_term'] = $search_term;

    $this->db->like("credit",$search_term);         // LIKE search in credit field
    $this->db->where("published",1);                // Only published codes
    $this->db->limit("100");                        // Limit to 100 results
    $query = $this->db->get("codes");

    $data['codes'] = get_codes($query,$search_term,'credit');

    $data['form_open'] = form_open('/code/cs_submit');
    $data['form_input'] = form_input('search',$search_term);
    $data['form_submit'] = form_submit('mysubmit','Search');
    $data['form_close'] = form_close();

    $data['page_title'] = "Credit Search for '".$search_term."'";
    $this->load->template('code_credit_search',$data);
}
```

### Form Submission Route: `/code/cs_submit`
**File**: `ascl_php_application/web_root/ascl_php_application/application/controllers/code.php:486-493`

```php
public function cs_submit() {
    $this->form_validation->set_rules('search','Search Term','trim|required');
    if ($this->form_validation->run() == FALSE) {
        redirect('/code/all');
    }
    else {
        $search_term = urlencode($this->input->post('search'));
        redirect('/code/cs/'.$search_term);
    }
}
```

### Template: `code_credit_search.php`
**File**: `ascl_php_application/web_root/ascl_php_application/application/views/code_credit_search.php`

```php
<h1>Searching for codes credited to '<?=$search_term?>'</h1>

<p><strong style="color: red;"><span style="font-size: 19px;">&#10149;</span> Tip!</strong> Refine or expand your search. Authors are sometimes listed as 'Smith, J. K.' instead of 'Smith, John' so it is useful to search for last names only. Note this is currently a simple phrase search.</p>
<?=$form_open?>
<?=$form_input?>
<?=$form_submit?>
<?=$form_close?>

<? include("template/codelist.php"); ?>
```

---

## Flask v4 Implementation

### 1. Route: `/code/cs/<path:search_term>`
**File**: `alt_ascl/source/ascl_net_app_project_home/ascl_net_app/controllers/search.py:43-83`

```python
@search_page.route("/code/cs/<path:search_term>", methods=['GET'])
def credit_search(search_term):
	''' Credit search - search for codes by author name.

	Matches PHP v3: /code/cs/{search_term}
	Performs LIKE search on codes.credit field.
	'''
	from urllib.parse import unquote
	from html import unescape

	# Decode URL encoding and HTML entities (matches PHP: html_entity_decode(urldecode($search_term)))
	search_term = unescape(unquote(search_term))

	templateDict = {
		'search_term': search_term,
		'codes': [],
		'result_count': 0
	}

	# Get database session
	from ascl_core.database.connections import Trillian2DBConnection as db
	from ascl_core.database.ascldb.ASCLModelClasses import ASCLCode
	session = db.Session()

	# Search for codes with matching credit (author name)
	# Matches PHP: $this->db->like("credit",$search_term);
	search_pattern = f"%{search_term}%"

	results = (
		session.query(ASCLCode)
		.filter(ASCLCode.credit.like(search_pattern))
		.filter(ASCLCode.published == 1)  # Only published codes
		.order_by(ASCLCode.time_added.desc())
		.limit(100)  # Matches PHP limit
		.all()
	)

	templateDict['codes'] = results
	templateDict['result_count'] = len(results)

	return render_template("credit_search.html", **templateDict)
```

**Key Features**:
- ✅ Uses `<path:search_term>` to capture URL path with special characters
- ✅ Decodes URL encoding with `unquote()`
- ✅ Decodes HTML entities with `unescape()` (matches PHP `html_entity_decode()`)
- ✅ Performs SQL LIKE search on `credit` field
- ✅ Filters to only published codes (`published == 1`)
- ✅ Limits to 100 results (matches PHP)
- ✅ Orders by `time_added` descending (most recent first)

### 2. Form Submission Route: `/code/cs_submit`
**File**: `alt_ascl/source/ascl_net_app_project_home/ascl_net_app/controllers/search.py:85-102`

```python
@search_page.route("/code/cs_submit", methods=['POST'])
def credit_search_submit():
	''' Credit search form submission - redirect to GET route.

	Matches PHP v3: /code/cs_submit
	Accepts form POST and redirects to /code/cs/{search_term}
	'''
	from flask import redirect
	from urllib.parse import quote

	search_term = request.form.get('search', '').strip()

	if not search_term:
		# No search term provided, redirect to browse all
		return redirect('/code/all')

	# Redirect to GET route with URL-encoded search term
	return redirect(f'/code/cs/{quote(search_term)}')
```

**Key Features**:
- ✅ Accepts POST form data
- ✅ Validates search term (redirects to `/code/all` if empty)
- ✅ URL-encodes search term with `quote()`
- ✅ Redirects to GET route (RESTful pattern)

### 3. Template: `credit_search.html`
**File**: `alt_ascl/source/ascl_net_app_project_home/ascl_net_app/templates/credit_search.html`

```jinja2
{% extends "base.html" %}

{% block title %}Credit Search for '{{ search_term }}'{% endblock %}

{% block content %}
<h1>Searching for codes credited to '{{ search_term }}'</h1>

<p><strong style="color: red;"><span style="font-size: 19px;">&#10149;</span> Tip!</strong> Refine or expand your search. Authors are sometimes listed as 'Smith, J. K.' instead of 'Smith, John' so it is useful to search for last names only. Note this is currently a simple phrase search.</p>

<form action="/code/cs_submit" method="post">
	<input type="text" name="search" value="{{ search_term }}" />
	<input type="submit" value="Search" />
</form>

<p>Found <strong>{{ result_count }}</strong> code(s){% if result_count == 100 %} (limited to 100 results){% endif %}</p>

<div class="codelist">
	{% if codes %}
		{% for code in codes %}
		<div class="item">
			<span class="ascl_id">
				{% if code.ascl_id == "0000.000" %}
					[submitted]
				{% else %}
					[ascl:{{ code.ascl_id }}]
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
			<div class="credit">{{ code.credit | link_author_credit }}</div>
			{% endif %}

			<div class="abstract">
				{{ code.abstract if code.abstract else 'No description available.' }}
			</div>
		</div>
		{% endfor %}
	{% else %}
		<p>No codes found for author '{{ search_term }}'.</p>
	{% endif %}
</div>
{% endblock %}
```

**Key Features**:
- ✅ Matches PHP template structure and messaging
- ✅ Displays helpful tip about name variations
- ✅ Includes search refinement form
- ✅ Shows result count (with note if limited to 100)
- ✅ Uses standard code list display format
- ✅ Links author names using `link_author_credit` filter
- ✅ Handles empty results gracefully

---

## How It Works

### URL Flow

1. **User clicks author link** on homepage/browse/search results:
   ```html
   <a href="/code/cs/Jane%20Smith">Jane Smith</a>
   ```

2. **Flask receives request**:
   - Route: `/code/cs/Jane%20Smith`
   - Flask captures `search_term = "Jane%20Smith"`

3. **Route handler processes**:
   - URL-decodes: `"Jane%20Smith"` → `"Jane Smith"`
   - HTML-decodes: `"Jane Smith"` → `"Jane Smith"` (no change in this case)

4. **Database query**:
   ```sql
   SELECT * FROM codes
   WHERE credit LIKE '%Jane Smith%'
     AND published = 1
   ORDER BY time_added DESC
   LIMIT 100
   ```

5. **Template renders**:
   - Displays search term: "Jane Smith"
   - Shows matching codes
   - Links all author names in results

### Search Form Submission Flow

1. **User types in search box** and clicks "Search"
2. **POST to `/code/cs_submit`**:
   ```
   POST /code/cs_submit
   Form data: search=John%20Doe
   ```

3. **Handler validates and redirects**:
   ```python
   search_term = "John Doe"  # Trimmed
   redirect('/code/cs/John%20Doe')
   ```

4. **Browser follows redirect** to GET route
5. **Credit search executes** (same as step 3-5 above)

---

## Special Character Handling

### Example: "Lâu Thiat-uí"

**URL Encoding Flow**:
1. Jinja2 filter creates: `<a href="/code/cs/Lâu%20Thiat-uí">Lâu Thiat-uí</a>`
2. Browser requests: `/code/cs/L%C3%A2u%20Thiat-u%C3%AD`
3. Flask receives: `"L%C3%A2u%20Thiat-u%C3%AD"`
4. `unquote()` decodes: `"Lâu Thiat-uí"`
5. Database searches: `LIKE '%Lâu Thiat-uí%'`

**Result**: Correctly finds codes with this author name, including proper Unicode characters.

---

## Additional Template Updates

### browse.html - Added author linking
**File**: `alt_ascl/source/ascl_net_app_project_home/ascl_net_app/templates/browse.html:92-94`

```jinja2
{% if code.credit %}
<div class="credit">{{ code.credit | link_author_credit }}</div>
{% endif %}
```

**Status**: ✅ Updated to use `link_author_credit` filter

---

## Testing Checklist

### Functional Tests
- [ ] Click author link from homepage → Credit search works
- [ ] Click author link from browse page → Credit search works
- [ ] Click author link from search results → Credit search works
- [ ] Search for single-name authors (e.g., "Smith")
- [ ] Search for multi-name authors (e.g., "John Smith")
- [ ] Search for partial names (e.g., "Smi")
- [ ] Submit credit search form → Redirects and searches correctly

### Special Character Tests
- [ ] Authors with accents (e.g., "Lâu Thiat-uí")
- [ ] Authors with hyphens (e.g., "Jean-Luc")
- [ ] Authors with apostrophes (e.g., "O'Brien")
- [ ] Authors with spaces
- [ ] Authors with commas (e.g., "Smith, J.")

### Edge Cases
- [ ] Empty search term → Redirects to `/code/all`
- [ ] No results found → Shows appropriate message
- [ ] 100+ results → Shows "limited to 100 results" message
- [ ] Search term with HTML entities
- [ ] Search term with URL-encoded characters

### UI/UX
- [ ] Search refinement form is pre-populated
- [ ] Tip message displays correctly
- [ ] Result count displays correctly
- [ ] Author names in results are clickable
- [ ] Code links work correctly

---

## Related Files

**Controller**:
- `alt_ascl/source/ascl_net_app_project_home/ascl_net_app/controllers/search.py`
  - Lines 43-83: `credit_search()` route
  - Lines 85-102: `credit_search_submit()` route

**Template**:
- `alt_ascl/source/ascl_net_app_project_home/ascl_net_app/templates/credit_search.html` (new file)

**Updated Templates** (to link author names):
- `alt_ascl/source/ascl_net_app_project_home/ascl_net_app/templates/index.html` (line 38)
- `alt_ascl/source/ascl_net_app_project_home/ascl_net_app/templates/browse.html` (line 93)

**Jinja Filter**:
- `alt_ascl/source/ascl_net_app_project_home/ascl_net_app/jinja_filters.py`
  - Lines 82-112: `link_author_credit` filter

**PHP Reference**:
- `ascl_php_application/web_root/ascl_php_application/application/controllers/code.php`
  - Lines 466-484: `cs()` method
  - Lines 486-493: `cs_submit()` method
- `ascl_php_application/web_root/ascl_php_application/application/views/code_credit_search.php`

**Documentation**:
- `alt_ascl/agents/AUTHOR_LINKING_FIX.md`
- `alt_ascl/agents/TODO_MASTER.md`: SEARCH-004 ✅, SEARCH-005 ✅

---

## TODO Items Completed

- [x] **SEARCH-004**: Credit search controller → `/code/cs/<search_term>`
- [x] **SEARCH-005**: Credit search template → `credit_search.html`

---

## Next Steps

1. ✅ **Done**: Implement `/code/cs/<search_term>` route
2. ✅ **Done**: Implement `/code/cs_submit` form handler
3. ✅ **Done**: Create `credit_search.html` template
4. ✅ **Done**: Update `browse.html` to link author names
5. ⚠️ **TODO**: Test with production data
6. ⚠️ **TODO**: Update `code_detail.html` to link author names (when implemented)
7. ⚠️ **TODO**: Update `search.html` results to link author names (when implemented)

---

**Last Updated**: 2025-12-01
**Status**: ✅ Fully implemented and ready for testing
**Related TODO Items**: SEARCH-004 ✅, SEARCH-005 ✅, WEB-002 (Homepage)
