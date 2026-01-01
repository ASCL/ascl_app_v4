# Typesense Implementation Plan for ASCL

**Date**: 2025-12-01
**Decision**: Implement Typesense for search with live type-ahead
**Status**: Planning Phase
**Priority**: High (significant UX improvement)

---

## Executive Summary

**Typesense** is an excellent choice for ASCL because it provides:
- ✅ **Lightning-fast typo-tolerant search** (< 50ms response times)
- ✅ **Instant search-as-you-type** with no lag
- ✅ **Much simpler than Elasticsearch** (single binary, easy deployment)
- ✅ **Built-in typo tolerance** (fixes "Einstien" → "Einstein")
- ✅ **Faceted search** (filter by keywords, year, language)
- ✅ **Tunable ranking** (boost title matches over abstract)
- ✅ **Low resource usage** (~100MB RAM for 10k documents)
- ✅ **Great developer experience** (clear docs, active community)

**Why Typesense > Elasticsearch for ASCL**:
- Simpler to deploy and maintain (single binary vs cluster)
- Faster for typical use cases (optimized for speed)
- Lower resource requirements (important for VPS hosting)
- Better out-of-the-box experience (less tuning needed)
- Built specifically for instant search (not analytics)

**Why Typesense > MySQL FULLTEXT**:
- Typo tolerance (MySQL FULLTEXT has none)
- Instant search-as-you-type (MySQL too slow)
- Faceted search built-in
- Better relevance ranking
- Highlighting and snippets
- Modern API (REST/GraphQL)

---

## What is Typesense?

**Typesense** is an open-source, typo-tolerant search engine optimized for instant search experiences. Think "Algolia alternative" but self-hosted.

**Key Features**:
1. **Typo Tolerance**: Automatically corrects typos (configurable fuzzy matching)
2. **Instant Search**: Sub-50ms response times for type-ahead search
3. **Faceting**: Filter results by multiple criteria
4. **Highlighting**: Shows matching text snippets
5. **Geo Search**: Search by location (not needed for ASCL, but nice)
6. **Synonyms**: Configure "Mueller" = "Müller"
7. **Curation**: Pin/boost specific results for queries
8. **Analytics**: Track popular searches

**Use Cases**:
- E-commerce product search
- Documentation sites (Typesense powers their own docs)
- Content discovery
- Academic paper search
- **Code repository search** ← ASCL fits here

**Live Examples**:
- https://typesense.org/docs/ (Typesense's own docs - try search)
- https://songs-search.typesense.org/ (32M songs dataset demo)
- https://books-search.typesense.org/ (28M books dataset demo)

---

## Architecture Overview

### Current (MySQL LIKE)
```
User → Flask → MySQL (LIKE query) → Flask → User
                 ↓
            (slow, no typo tolerance)
```

### With Typesense
```
User → Flask → Typesense (instant search) → Flask → User
       ↓
       MySQL (source of truth for data)
       ↓
       Typesense (read-only search index)
```

**Data Flow**:
1. **MySQL** = Source of truth (all CRUD operations)
2. **Typesense** = Search index (read-only, synced from MySQL)
3. **Flask** = Orchestrator (writes to MySQL, searches via Typesense)
4. **Sync** = Keep Typesense updated when MySQL changes

---

## Typesense Schema for ASCL

### Collection: `codes`

```json
{
  "name": "codes",
  "fields": [
    {
      "name": "ascl_id",
      "type": "string",
      "facet": false
    },
    {
      "name": "pk",
      "type": "int32",
      "facet": false
    },
    {
      "name": "title",
      "type": "string",
      "facet": false,
      "infix": true
    },
    {
      "name": "abstract",
      "type": "string",
      "facet": false
    },
    {
      "name": "credit",
      "type": "string",
      "facet": false,
      "infix": true
    },
    {
      "name": "authors",
      "type": "string[]",
      "facet": true,
      "optional": true
    },
    {
      "name": "keywords",
      "type": "string[]",
      "facet": true,
      "optional": true
    },
    {
      "name": "programming_languages",
      "type": "string[]",
      "facet": true,
      "optional": true
    },
    {
      "name": "year",
      "type": "int32",
      "facet": true
    },
    {
      "name": "month",
      "type": "int32",
      "facet": true
    },
    {
      "name": "published",
      "type": "bool",
      "facet": true
    },
    {
      "name": "time_added",
      "type": "int64",
      "facet": false,
      "sort": true
    },
    {
      "name": "views",
      "type": "int32",
      "facet": false,
      "sort": true
    }
  ],
  "default_sorting_field": "time_added"
}
```

**Field Explanations**:
- `infix: true` = Allows matching anywhere in string (important for names)
- `facet: true` = Can filter/group by this field
- `sort: true` = Can sort results by this field
- `string[]` = Array for multi-value fields (keywords, authors)
- `optional: true` = Field can be missing

---

## Implementation Plan

### Phase 1: Setup & Testing (Week 1)
**Goal**: Get Typesense running locally, test basic search

#### 1.1: Install Typesense Server

**Option A: Docker (Recommended for Development)**
```bash
# Start Typesense in Docker
docker run -d \
  -p 8108:8108 \
  -v /tmp/typesense-data:/data \
  -e TYPESENSE_API_KEY=your_development_key_here \
  -e TYPESENSE_DATA_DIR=/data \
  typesense/typesense:26.0

# Verify it's running
curl http://localhost:8108/health
```

**Option B: Native Binary (Recommended for Production)**
```bash
# Download Typesense binary
wget https://dl.typesense.org/releases/26.0/typesense-server-26.0-linux-amd64.tar.gz
tar -xzf typesense-server-26.0-linux-amd64.tar.gz

# Run Typesense
./typesense-server \
  --data-dir=/var/lib/typesense \
  --api-key=your_production_key_here \
  --listen-port=8108
```

**Option C: Typesense Cloud (Managed Service)**
- No infrastructure management
- $0.03/hour for smallest instance (~$22/month)
- Automatic backups, HA
- https://cloud.typesense.org/

#### 1.2: Install Python Client

```bash
pip install typesense
```

**Add to requirements.txt**:
```
typesense>=0.18.0
```

#### 1.3: Create Initial Schema

**File**: `alt_ascl/scripts/typesense_setup.py`

```python
#!/usr/bin/env python
"""Initialize Typesense schema for ASCL codes."""

import typesense

# Initialize client
client = typesense.Client({
    'nodes': [{
        'host': 'localhost',
        'port': '8108',
        'protocol': 'http'
    }],
    'api_key': 'your_development_key_here',
    'connection_timeout_seconds': 2
})

# Define schema
codes_schema = {
    'name': 'codes',
    'fields': [
        {'name': 'ascl_id', 'type': 'string', 'facet': False},
        {'name': 'pk', 'type': 'int32', 'facet': False},
        {'name': 'title', 'type': 'string', 'facet': False, 'infix': True},
        {'name': 'abstract', 'type': 'string', 'facet': False},
        {'name': 'credit', 'type': 'string', 'facet': False, 'infix': True},
        {'name': 'authors', 'type': 'string[]', 'facet': True, 'optional': True},
        {'name': 'keywords', 'type': 'string[]', 'facet': True, 'optional': True},
        {'name': 'programming_languages', 'type': 'string[]', 'facet': True, 'optional': True},
        {'name': 'year', 'type': 'int32', 'facet': True},
        {'name': 'month', 'type': 'int32', 'facet': True},
        {'name': 'published', 'type': 'bool', 'facet': True},
        {'name': 'time_added', 'type': 'int64', 'facet': False, 'sort': True},
        {'name': 'views', 'type': 'int32', 'facet': False, 'sort': True}
    ],
    'default_sorting_field': 'time_added'
}

# Create collection
try:
    client.collections.create(codes_schema)
    print("✅ Collection 'codes' created successfully")
except Exception as e:
    print(f"❌ Error creating collection: {e}")
```

Run it:
```bash
python alt_ascl/scripts/typesense_setup.py
```

#### 1.4: Initial Data Import

**File**: `alt_ascl/scripts/typesense_import.py`

```python
#!/usr/bin/env python
"""Import all published codes from MySQL to Typesense."""

import typesense
from datetime import datetime
from ascl_core.database.connections import Trillian2DBConnection as db
from ascl_core.database.ascldb.ASCLModelClasses import ASCLCode

# Initialize Typesense client
client = typesense.Client({
    'nodes': [{'host': 'localhost', 'port': '8108', 'protocol': 'http'}],
    'api_key': 'your_development_key_here',
    'connection_timeout_seconds': 10
})

# Get MySQL session
session = db.Session()

# Query all published codes
codes = session.query(ASCLCode).filter(ASCLCode.published == 1).all()

print(f"Importing {len(codes)} codes to Typesense...")

# Prepare documents for Typesense
documents = []
for code in codes:
    # Parse ASCL ID to extract year/month
    year, month = None, None
    if code.ascl_id and code.ascl_id != "0000.000":
        parts = code.ascl_id.split('.')
        if len(parts) == 2:
            year = 2000 + int(parts[0][:2])  # "1404" → 2014
            month = int(parts[0][2:4])        # "1404" → 04

    # Parse authors from credit field
    authors = []
    if code.credit:
        authors = [a.strip() for a in code.credit.split(';') if a.strip()]

    # Parse keywords (from PHP-serialized field)
    keywords = []
    if code.keywords:
        # TODO: Properly deserialize PHP keywords field
        # For now, placeholder
        pass

    # Prepare document
    doc = {
        'id': str(code.pk),  # Typesense requires string ID
        'ascl_id': code.ascl_id or "0000.000",
        'pk': code.pk,
        'title': code.title or "",
        'abstract': code.abstract or "",
        'credit': code.credit or "",
        'authors': authors,
        'keywords': keywords,
        'published': bool(code.published),
        'time_added': int(code.time_added.timestamp()) if code.time_added else 0,
        'views': code.views or 0
    }

    # Add year/month if available
    if year:
        doc['year'] = year
        doc['month'] = month

    documents.append(doc)

# Import in batches (Typesense recommends 1000 per batch)
batch_size = 1000
for i in range(0, len(documents), batch_size):
    batch = documents[i:i+batch_size]
    result = client.collections['codes'].documents.import_(batch, {'action': 'upsert'})
    print(f"Imported batch {i//batch_size + 1}: {len(batch)} documents")

print(f"✅ Import complete! {len(documents)} codes indexed.")
```

Run it:
```bash
python alt_ascl/scripts/typesense_import.py
```

#### 1.5: Test Basic Search

```python
# Test instant search
search_params = {
    'q': 'einstein',
    'query_by': 'title,credit,abstract',
    'filter_by': 'published:true',
    'per_page': 10
}

results = client.collections['codes'].documents.search(search_params)

print(f"Found {results['found']} results")
for hit in results['hits']:
    print(f"- [{hit['document']['ascl_id']}] {hit['document']['title']}")
```

---

### Phase 2: Flask Integration (Week 2)
**Goal**: Replace MySQL LIKE queries with Typesense

#### 2.1: Create Typesense Client Singleton

**File**: `alt_ascl/ascl_core/search/TypesenseClient.py`

```python
"""Typesense client singleton for ASCL search."""

import os
import typesense
from typing import Optional

class TypesenseClient:
    """Singleton Typesense client."""

    _instance: Optional[typesense.Client] = None

    @classmethod
    def get_client(cls) -> typesense.Client:
        """Get or create Typesense client instance."""
        if cls._instance is None:
            # Read config from environment or Flask config
            host = os.getenv('TYPESENSE_HOST', 'localhost')
            port = os.getenv('TYPESENSE_PORT', '8108')
            protocol = os.getenv('TYPESENSE_PROTOCOL', 'http')
            api_key = os.getenv('TYPESENSE_API_KEY', 'development_key')

            cls._instance = typesense.Client({
                'nodes': [{
                    'host': host,
                    'port': port,
                    'protocol': protocol
                }],
                'api_key': api_key,
                'connection_timeout_seconds': 2
            })

        return cls._instance

# Convenience function
def get_typesense_client() -> typesense.Client:
    """Get Typesense client instance."""
    return TypesenseClient.get_client()
```

#### 2.2: Update General Search Route

**File**: `alt_ascl/source/ascl_net_app_project_home/ascl_net_app/controllers/search.py`

**Before (MySQL LIKE)**:
```python
@search_page.route("/search", methods=['GET'])
def search():
    query_string = request.args.get('q', '').strip()
    # ... MySQL LIKE query ...
```

**After (Typesense)**:
```python
from ascl_core.search.TypesenseClient import get_typesense_client

@search_page.route("/search", methods=['GET'])
def search():
    """General search using Typesense."""
    query_string = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)

    templateDict = {
        'query': query_string,
        'results': [],
        'result_count': 0,
        'facets': {},
        'page': page,
        'per_page': per_page
    }

    if not query_string:
        return render_template("search.html", **templateDict)

    try:
        client = get_typesense_client()

        # Build search parameters
        search_params = {
            'q': query_string,
            'query_by': 'title,credit,abstract',
            'filter_by': 'published:true',
            'per_page': per_page,
            'page': page,
            'highlight_fields': 'title,credit,abstract',
            'highlight_full_fields': 'title,credit',
            'snippet_threshold': 30,
            'num_typos': 2,  # Allow up to 2 typos
            'typo_tokens_threshold': 1,
            # Boost title matches
            'query_by_weights': '3,2,1',  # title=3x, credit=2x, abstract=1x
            # Return facets for filtering
            'facet_by': 'keywords,year,authors',
            'max_facet_values': 20
        }

        results = client.collections['codes'].documents.search(search_params)

        # Extract documents
        hits = []
        for hit in results['hits']:
            doc = hit['document']
            # Add highlights if available
            if 'highlights' in hit:
                doc['_highlights'] = hit['highlights']
            hits.append(doc)

        templateDict['results'] = hits
        templateDict['result_count'] = results['found']
        templateDict['facets'] = results.get('facet_counts', [])
        templateDict['search_time_ms'] = results['search_time_ms']

    except Exception as e:
        # Fallback to MySQL if Typesense fails
        print(f"Typesense error: {e}, falling back to MySQL")
        # ... original MySQL LIKE code as fallback ...

    return render_template("search.html", **templateDict)
```

#### 2.3: Update Credit Search Route

**File**: `alt_ascl/source/ascl_net_app_project_home/ascl_net_app/controllers/search.py`

```python
@search_page.route("/code/cs/<path:search_term>", methods=['GET'])
def credit_search(search_term):
    """Credit search using Typesense."""
    from urllib.parse import unquote
    from html import unescape

    search_term = unescape(unquote(search_term))

    templateDict = {
        'search_term': search_term,
        'codes': [],
        'result_count': 0
    }

    try:
        client = get_typesense_client()

        # Search specifically in credit and authors fields
        search_params = {
            'q': search_term,
            'query_by': 'credit,authors',
            'filter_by': 'published:true',
            'per_page': 100,
            'highlight_fields': 'credit,authors',
            'num_typos': 1,  # Allow 1 typo for names
            'query_by_weights': '2,1',  # credit=2x, authors=1x
            # Prioritize exact matches
            'sort_by': '_text_match:desc,time_added:desc'
        }

        results = client.collections['codes'].documents.search(search_params)

        templateDict['codes'] = [hit['document'] for hit in results['hits']]
        templateDict['result_count'] = results['found']

    except Exception as e:
        # Fallback to MySQL
        print(f"Typesense error: {e}, falling back to MySQL")
        # ... original MySQL code ...

    return render_template("credit_search.html", **templateDict)
```

---

### Phase 3: Instant Search UI (Week 3)
**Goal**: Add type-ahead search with live results

#### 3.1: Install InstantSearch.js (Typesense adapter)

**CDN Method** (add to base.html):
```html
<!-- Typesense InstantSearch adapter -->
<script src="https://cdn.jsdelivr.net/npm/typesense-instantsearch-adapter@2/dist/typesense-instantsearch-adapter.min.js"></script>
<!-- InstantSearch.js -->
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/instantsearch.css@7/themes/satellite-min.css">
<script src="https://cdn.jsdelivr.net/npm/instantsearch.js@4"></script>
```

**OR NPM Method** (if using build system):
```bash
npm install typesense-instantsearch-adapter instantsearch.js
```

#### 3.2: Create Instant Search Component

**File**: `alt_ascl/source/ascl_net_app_project_home/ascl_net_app/static/js/instant-search.js`

```javascript
// Initialize Typesense adapter
const typesenseAdapter = new TypesenseInstantsearchAdapter({
  server: {
    apiKey: "{{ typesense_search_key }}",  // Read-only search key
    nodes: [{
      host: "{{ typesense_host }}",
      port: "{{ typesense_port }}",
      protocol: "{{ typesense_protocol }}"
    }]
  },
  additionalSearchParameters: {
    query_by: "title,credit,abstract",
    query_by_weights: "3,2,1",
    num_typos: 2,
    filter_by: "published:true"
  }
});

const searchClient = typesenseAdapter.searchClient;

// Initialize InstantSearch
const search = instantsearch({
  indexName: 'codes',
  searchClient,
  routing: true  // Update URL with search params
});

// Add search box widget
search.addWidgets([
  instantsearch.widgets.searchBox({
    container: '#searchbox',
    placeholder: 'Search codes, authors, keywords...',
    showSubmit: false,
    showReset: true,
    autofocus: false
  })
]);

// Add hits (results) widget
search.addWidgets([
  instantsearch.widgets.hits({
    container: '#hits',
    templates: {
      item: `
        <div class="item">
          <span class="ascl_id">
            {{#helpers.highlight}}{ "attribute": "ascl_id" }{{/helpers.highlight}}
          </span>
          <span class="title">
            <a href="/{{ascl_id}}">
              {{#helpers.highlight}}{ "attribute": "title" }{{/helpers.highlight}}
            </a>
          </span>
          {{#credit}}
          <div class="credit">
            {{#helpers.highlight}}{ "attribute": "credit" }{{/helpers.highlight}}
          </div>
          {{/credit}}
          <div class="abstract">
            {{#helpers.snippet}}{ "attribute": "abstract", "highlightedTagName": "mark" }{{/helpers.snippet}}
          </div>
        </div>
      `,
      empty: 'No codes found for <q>{{ query }}</q>'
    }
  })
]);

// Add facet filters
search.addWidgets([
  instantsearch.widgets.refinementList({
    container: '#keywords-facet',
    attribute: 'keywords',
    limit: 10,
    showMore: true,
    showMoreLimit: 50,
    searchable: true,
    searchablePlaceholder: 'Search keywords...'
  }),

  instantsearch.widgets.refinementList({
    container: '#year-facet',
    attribute: 'year',
    limit: 10,
    sortBy: ['name:desc']  // Most recent years first
  }),

  instantsearch.widgets.refinementList({
    container: '#author-facet',
    attribute: 'authors',
    limit: 10,
    showMore: true,
    searchable: true,
    searchablePlaceholder: 'Search authors...'
  })
]);

// Add stats widget
search.addWidgets([
  instantsearch.widgets.stats({
    container: '#stats',
    templates: {
      text: '{{#hasNoResults}}No results{{/hasNoResults}}{{#hasOneResult}}1 result{{/hasOneResult}}{{#hasManyResults}}{{#helpers.formatNumber}}{{nbHits}}{{/helpers.formatNumber}} results{{/hasManyResults}} found in {{processingTimeMS}}ms'
    }
  })
]);

// Add pagination
search.addWidgets([
  instantsearch.widgets.pagination({
    container: '#pagination',
    showFirst: false,
    showLast: false,
    padding: 3
  })
]);

// Start InstantSearch
search.start();
```

#### 3.3: Update Search Template

**File**: `alt_ascl/source/ascl_net_app_project_home/ascl_net_app/templates/search.html`

```html
{% extends "base.html" %}

{% block title %}Search ASCL Codes{% endblock %}

{% block head %}
{{ super() }}
<!-- InstantSearch CSS -->
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/instantsearch.css@7/themes/satellite-min.css">
<style>
.ais-SearchBox { margin-bottom: 2rem; }
.ais-Hits-item { border-bottom: 1px solid #eee; padding: 1rem 0; }
mark { background-color: #fff3cd; font-weight: bold; }
.facets-sidebar { width: 250px; float: left; margin-right: 2rem; }
.results-main { margin-left: 270px; }
</style>
{% endblock %}

{% block content %}
<h1>Search ASCL Codes</h1>

<!-- Search box -->
<div id="searchbox"></div>

<!-- Stats -->
<div id="stats"></div>

<div class="search-container">
  <!-- Facets sidebar -->
  <div class="facets-sidebar">
    <h3>Filter by Keyword</h3>
    <div id="keywords-facet"></div>

    <h3>Filter by Year</h3>
    <div id="year-facet"></div>

    <h3>Filter by Author</h3>
    <div id="author-facet"></div>
  </div>

  <!-- Results -->
  <div class="results-main">
    <div id="hits"></div>
    <div id="pagination"></div>
  </div>
</div>

<!-- Typesense InstantSearch adapter -->
<script src="https://cdn.jsdelivr.net/npm/typesense-instantsearch-adapter@2/dist/typesense-instantsearch-adapter.min.js"></script>
<!-- InstantSearch.js -->
<script src="https://cdn.jsdelivr.net/npm/instantsearch.js@4"></script>

<!-- Pass config to JavaScript -->
<script>
const TYPESENSE_CONFIG = {
  host: "{{ config.TYPESENSE_HOST }}",
  port: "{{ config.TYPESENSE_PORT }}",
  protocol: "{{ config.TYPESENSE_PROTOCOL }}",
  searchKey: "{{ config.TYPESENSE_SEARCH_KEY }}"
};
</script>

<!-- Initialize instant search -->
<script src="{{ url_for('static', filename='js/instant-search.js') }}"></script>
{% endblock %}
```

---

### Phase 4: Real-Time Sync (Week 4)
**Goal**: Keep Typesense in sync with MySQL changes

#### 4.1: Create Sync Service

**File**: `alt_ascl/ascl_core/search/TypesenseSync.py`

```python
"""Sync MySQL changes to Typesense in real-time."""

from typing import Optional
import typesense
from .TypesenseClient import get_typesense_client
from ascl_core.database.ascldb.ASCLModelClasses import ASCLCode

class TypesenseSync:
    """Sync ASCL codes to Typesense."""

    @staticmethod
    def prepare_document(code: ASCLCode) -> dict:
        """Convert ASCLCode model to Typesense document."""
        # Parse ASCL ID
        year, month = None, None
        if code.ascl_id and code.ascl_id != "0000.000":
            parts = code.ascl_id.split('.')
            if len(parts) == 2:
                year = 2000 + int(parts[0][:2])
                month = int(parts[0][2:4])

        # Parse authors
        authors = []
        if code.credit:
            authors = [a.strip() for a in code.credit.split(';') if a.strip()]

        # Prepare document
        doc = {
            'id': str(code.pk),
            'ascl_id': code.ascl_id or "0000.000",
            'pk': code.pk,
            'title': code.title or "",
            'abstract': code.abstract or "",
            'credit': code.credit or "",
            'authors': authors,
            'published': bool(code.published),
            'time_added': int(code.time_added.timestamp()) if code.time_added else 0,
            'views': code.views or 0
        }

        if year:
            doc['year'] = year
            doc['month'] = month

        return doc

    @staticmethod
    def index_code(code: ASCLCode) -> bool:
        """Index or update a code in Typesense."""
        try:
            client = get_typesense_client()
            doc = TypesenseSync.prepare_document(code)
            client.collections['codes'].documents.upsert(doc)
            return True
        except Exception as e:
            print(f"Error indexing code {code.pk}: {e}")
            return False

    @staticmethod
    def delete_code(code_pk: int) -> bool:
        """Delete a code from Typesense."""
        try:
            client = get_typesense_client()
            client.collections['codes'].documents[str(code_pk)].delete()
            return True
        except Exception as e:
            print(f"Error deleting code {code_pk}: {e}")
            return False
```

#### 4.2: Add Sync Hooks to Flask Routes

**File**: `alt_ascl/source/ascl_net_app_project_home/ascl_net_app/controllers/admin.py` (or wherever codes are created/updated)

```python
from ascl_core.search.TypesenseSync import TypesenseSync

@admin_page.route("/admin/insert_code", methods=['POST'])
def insert_code():
    """Insert new code and sync to Typesense."""
    # ... create code in MySQL ...
    session.add(new_code)
    session.commit()

    # Sync to Typesense
    TypesenseSync.index_code(new_code)

    return redirect('/admin/unpublished')

@admin_page.route("/admin/update_code/<int:code_pk>", methods=['POST'])
def update_code(code_pk):
    """Update code and sync to Typesense."""
    code = session.query(ASCLCode).get(code_pk)
    # ... update code fields ...
    session.commit()

    # Sync to Typesense
    TypesenseSync.index_code(code)

    return redirect(f'/code/view/{code_pk}')

@admin_page.route("/admin/delete_code/<int:code_pk>", methods=['POST'])
def delete_code(code_pk):
    """Delete code and remove from Typesense."""
    code = session.query(ASCLCode).get(code_pk)
    session.delete(code)
    session.commit()

    # Remove from Typesense
    TypesenseSync.delete_code(code_pk)

    return redirect('/admin/codes')
```

#### 4.3: Background Sync Job (Optional)

**File**: `alt_ascl/scripts/typesense_sync_cron.py`

```python
#!/usr/bin/env python
"""
Cron job to sync MySQL → Typesense (run every 5 minutes as backup).

This catches any codes that weren't synced in real-time due to errors.
"""

import sys
from datetime import datetime, timedelta
from ascl_core.database.connections import Trillian2DBConnection as db
from ascl_core.database.ascldb.ASCLModelClasses import ASCLCode
from ascl_core.search.TypesenseSync import TypesenseSync

session = db.Session()

# Find codes updated in last 10 minutes
since = datetime.now() - timedelta(minutes=10)
recent_codes = session.query(ASCLCode).filter(
    ASCLCode.time_updated >= since
).all()

print(f"Syncing {len(recent_codes)} recently updated codes...")

success = 0
for code in recent_codes:
    if TypesenseSync.index_code(code):
        success += 1

print(f"✅ Synced {success}/{len(recent_codes)} codes")
```

**Crontab entry**:
```bash
# Sync MySQL → Typesense every 5 minutes
*/5 * * * * cd /path/to/ascl && /usr/bin/python alt_ascl/scripts/typesense_sync_cron.py >> /var/log/typesense-sync.log 2>&1
```

---

## Configuration

### Flask Config

**File**: `alt_ascl/source/ascl_net_app_project_home/ascl_net_app/configuration_files/production.cfg`

```ini
# Typesense Configuration
TYPESENSE_ENABLED = True
TYPESENSE_HOST = 'localhost'
TYPESENSE_PORT = '8108'
TYPESENSE_PROTOCOL = 'http'
TYPESENSE_API_KEY = 'your_admin_api_key_here'
TYPESENSE_SEARCH_KEY = 'your_search_only_api_key_here'
```

### API Keys

Typesense supports scoped API keys for security:

1. **Admin API Key** (Flask backend only):
   - Can create/update/delete documents
   - Can create/delete collections
   - Never expose to frontend

2. **Search-Only API Key** (Frontend JavaScript):
   - Can only search
   - Can't modify data
   - Safe to expose in HTML/JS

**Generate scoped search key**:
```python
import typesense

client = typesense.Client({...})

# Create search-only key for 'codes' collection
search_key = client.keys.create({
    'description': 'Search-only key for codes collection',
    'actions': ['documents:search'],
    'collections': ['codes']
})

print(f"Search-only API key: {search_key['value']}")
```

---

## Deployment

### Production Deployment (Systemd Service)

**File**: `/etc/systemd/system/typesense.service`

```ini
[Unit]
Description=Typesense Search Server
After=network.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/var/lib/typesense
ExecStart=/usr/local/bin/typesense-server \
    --data-dir=/var/lib/typesense/data \
    --api-key-file=/etc/typesense/api-key.txt \
    --listen-port=8108 \
    --enable-cors=true \
    --log-dir=/var/log/typesense
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

**Enable and start**:
```bash
sudo systemctl daemon-reload
sudo systemctl enable typesense
sudo systemctl start typesense
sudo systemctl status typesense
```

### Nginx Reverse Proxy

**File**: `/etc/nginx/sites-available/ascl.net`

```nginx
# Typesense proxy (for frontend JavaScript)
location /typesense/ {
    proxy_pass http://localhost:8108/;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection 'upgrade';
    proxy_set_header Host $host;
    proxy_cache_bypass $http_upgrade;

    # CORS headers (if needed)
    add_header 'Access-Control-Allow-Origin' '*';
    add_header 'Access-Control-Allow-Methods' 'GET, POST, OPTIONS';
}
```

Now frontend can access Typesense at: `https://ascl.net/typesense/`

---

## Advanced Features

### 1. Synonyms

**Configure synonyms for common variations**:

```python
# Define synonyms
synonyms = {
    "id": "author-name-synonyms",
    "synonyms": [
        ["mueller", "müller"],
        ["o'brien", "obrien"],
        ["mckenzie", "mackenzie"]
    ]
}

client.collections['codes'].synonyms.upsert('author-name-synonyms', synonyms)
```

### 2. Curation (Pinned Results)

**Pin specific codes to top of results for certain queries**:

```python
# Pin "ASCL" code to top when searching "ascl"
override = {
    "rule": {
        "query": "ascl",
        "match": "exact"
    },
    "includes": [
        {"id": "1234", "position": 1}  # Pin code pk=1234 to position 1
    ]
}

client.collections['codes'].overrides.upsert('pin-ascl', override)
```

### 3. Analytics

**Track popular searches**:

```python
# Enable analytics
search_params = {
    'q': query,
    'query_by': 'title,credit,abstract',
    'enable_analytics': True,  # Track this search
    'analytics_tags': ['web-search']  # Tag for segmentation
}

results = client.collections['codes'].documents.search(search_params)
```

**Get analytics**:
```python
# Get popular searches from last 30 days
analytics = client.analytics.rules.retrieve()
```

### 4. Geo-Based Boosting (Future)

If you ever add institution location data:

```python
# Boost results near user's location
search_params = {
    'q': query,
    'query_by': 'title',
    'sort_by': '_geo(48.8566,2.3522):asc'  # Sort by distance from Paris
}
```

---

## Monitoring & Maintenance

### Health Check

```bash
# Check Typesense health
curl http://localhost:8108/health

# Check collection stats
curl -H "X-TYPESENSE-API-KEY: your_api_key" \
  http://localhost:8108/collections/codes
```

### Metrics

Typesense exposes metrics at `/metrics` endpoint:

```bash
curl -H "X-TYPESENSE-API-KEY: your_api_key" \
  http://localhost:8108/metrics.json
```

Key metrics to monitor:
- `typesense_search_requests_per_second`
- `typesense_search_latency_ms`
- `typesense_memory_used_bytes`
- `typesense_disk_used_bytes`

### Backup

**Manual backup**:
```bash
# Create snapshot
curl -H "X-TYPESENSE-API-KEY: your_api_key" \
  -X POST \
  http://localhost:8108/operations/snapshot?snapshot_path=/tmp/typesense-snapshot

# Copy snapshot
cp -r /var/lib/typesense/data /backup/typesense-$(date +%Y%m%d)
```

**Automated backup**:
```bash
# Cron job for daily backups
0 2 * * * /usr/local/bin/typesense-backup.sh
```

### Restore

```bash
# Stop Typesense
sudo systemctl stop typesense

# Restore data directory
rm -rf /var/lib/typesense/data
cp -r /backup/typesense-20251201/data /var/lib/typesense/

# Start Typesense
sudo systemctl start typesense
```

---

## Cost Analysis

### Self-Hosted (VPS)

**Option A: Shared VPS with Flask**
- Current VPS + 200MB RAM for Typesense
- **Cost**: $0 (uses existing resources)
- **Pros**: No additional cost
- **Cons**: Shares resources with Flask/MySQL

**Option B: Dedicated Small VPS**
- 1 CPU, 1GB RAM, 25GB SSD
- DigitalOcean Droplet: $6/month
- Hetzner Cloud CX11: €4/month (~$4.50/month)
- **Cost**: $4-6/month
- **Pros**: Isolated, predictable performance
- **Cons**: Need to manage server

### Typesense Cloud (Managed)

**Pricing** (as of 2025):
- **0.5 CPU, 2GB RAM**: $0.03/hour = ~$22/month
- **1 CPU, 4GB RAM**: $0.06/hour = ~$44/month
- Includes: Automatic backups, HA, SSL, monitoring
- **Pros**: Zero maintenance, automatic updates
- **Cons**: 4-10x more expensive than self-hosted

### Recommendation

**Start**: Self-hosted on existing VPS ($0)
**Scale**: Dedicated VPS when traffic grows ($6/month)
**Enterprise**: Typesense Cloud if you need HA/SLA ($22+/month)

---

## Migration Checklist

### Pre-Launch
- [ ] Install Typesense server (Docker or binary)
- [ ] Create `codes` collection schema
- [ ] Import all published codes from MySQL
- [ ] Test search queries (general + credit search)
- [ ] Verify typo tolerance works
- [ ] Test faceted search (keywords, years, authors)

### Development
- [ ] Install Python client (`pip install typesense`)
- [ ] Create TypesenseClient singleton
- [ ] Create TypesenseSync service
- [ ] Update search routes to use Typesense
- [ ] Add fallback to MySQL if Typesense fails
- [ ] Test search with 10-20 queries

### Frontend
- [ ] Add InstantSearch.js library
- [ ] Create instant search component
- [ ] Update search template with facets
- [ ] Test type-ahead search
- [ ] Test on mobile devices
- [ ] Add loading states

### Sync
- [ ] Add sync hooks to create/update/delete routes
- [ ] Test manual sync (create/update/delete code)
- [ ] Set up background sync cron job (optional)
- [ ] Test sync failure handling

### Production
- [ ] Set up Typesense systemd service
- [ ] Configure Nginx reverse proxy
- [ ] Generate search-only API key
- [ ] Configure environment variables
- [ ] Test production deployment
- [ ] Set up monitoring/alerts
- [ ] Configure automated backups

### Post-Launch
- [ ] Monitor search performance metrics
- [ ] Gather user feedback on search quality
- [ ] Tune typo tolerance settings
- [ ] Add synonyms for common variations
- [ ] Configure curated results (if needed)
- [ ] Review popular searches analytics

---

## Troubleshooting

### Common Issues

**1. "Collection not found" error**
```bash
# Re-create collection
python alt_ascl/scripts/typesense_setup.py
```

**2. "Connection refused" error**
```bash
# Check Typesense is running
sudo systemctl status typesense
curl http://localhost:8108/health
```

**3. "Out of sync" (MySQL has codes Typesense doesn't)**
```bash
# Re-import all codes
python alt_ascl/scripts/typesense_import.py
```

**4. "Search returns nothing"**
```python
# Check filter_by syntax
# Wrong:  filter_by='published:1'
# Correct: filter_by='published:true'
```

**5. "Typo tolerance too aggressive"**
```python
# Reduce typo tolerance
search_params['num_typos'] = 1  # Default is 2
```

---

## Resources

**Official Docs**:
- Typesense: https://typesense.org/docs/
- InstantSearch.js: https://www.algolia.com/doc/guides/building-search-ui/what-is-instantsearch/js/
- Python Client: https://github.com/typesense/typesense-python

**Tutorials**:
- Typesense Guide: https://typesense.org/docs/guide/
- Building Instant Search: https://typesense.org/docs/guide/building-a-search-application.html

**Community**:
- GitHub: https://github.com/typesense/typesense
- Slack: https://join.slack.com/t/typesense-community/

---

## Next Steps

1. ✅ Review this implementation plan
2. ⚠️ **Decision**: Self-hosted vs Typesense Cloud?
3. ⚠️ **Decision**: Docker vs native binary for deployment?
4. ⚠️ Start with Phase 1 (setup & testing) - 1 week
5. ⚠️ Move to Phase 2 (Flask integration) - 1 week
6. ⚠️ Implement Phase 3 (instant search UI) - 1 week
7. ⚠️ Complete Phase 4 (real-time sync) - 1 week

**Total Timeline**: ~4 weeks for full implementation

---

**Last Updated**: 2025-12-01
**Status**: Planning - awaiting approval
**Estimated Effort**: 4 weeks (one phase per week)
**Priority**: High (significant UX improvement)
