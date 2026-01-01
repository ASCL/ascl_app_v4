# Search Implementation - Analysis and Recommendations

**Date**: 2025-12-01
**Status**: Basic search implemented, significant improvements needed
**Priority**: Medium (works for current scale, will need enhancement as site grows)

---

## Executive Summary

The current search implementation uses simple SQL LIKE queries across multiple fields. This approach works adequately for the current scale (~4,400 codes) but has significant limitations:

- ❌ No relevance ranking
- ❌ No fuzzy matching
- ❌ No author name intelligence
- ❌ Poor performance on large result sets
- ❌ No result highlighting
- ❌ No faceted search/filtering

**Recommendation**: Implement incremental improvements starting with MySQL FULLTEXT, then evaluate need for PostgreSQL FTS or Elasticsearch based on user feedback and performance metrics.

---

## Current Implementation

### 1. General Search (`/search?q={query}`)

**File**: `alt_ascl/source/ascl_net_app_project_home/ascl_net_app/controllers/search.py:9-41`

```python
@search_page.route("/search", methods=['GET'])
def search():
    query_string = request.args.get('q', '').strip()

    if query_string:
        search_pattern = f"%{query_string}%"

        results = session.query(ascldb.ASCLCode).filter(
            or_(
                ascldb.ASCLCode.title.like(search_pattern),
                ascldb.ASCLCode.abstract.like(search_pattern),
                ascldb.ASCLCode.credit.like(search_pattern)
            )
        ).order_by(ascldb.ASCLCode.time_added.desc(), ascldb.ASCLCode.pk.desc()).all()
```

**SQL Equivalent**:
```sql
SELECT * FROM codes
WHERE title LIKE '%query%'
   OR abstract LIKE '%query%'
   OR credit LIKE '%query%'
ORDER BY time_added DESC, pk DESC;
```

**Issues**:
1. ❌ **No published filter**: Searches unpublished codes (should filter `published=1`)
2. ❌ **No pagination**: Loads all results into memory
3. ❌ **No relevance ranking**: Results ordered by date, not match quality
4. ❌ **No highlighting**: Matched terms not highlighted
5. ❌ **Case-sensitive in some MySQL collations**: May miss results
6. ❌ **Poor performance**: Full table scan on TEXT fields

### 2. Credit Search (`/code/cs/{author_name}`)

**File**: `alt_ascl/source/ascl_net_app_project_home/ascl_net_app/controllers/search.py:43-83`

```python
@search_page.route("/code/cs/<path:search_term>", methods=['GET'])
def credit_search(search_term):
    search_term = unescape(unquote(search_term))
    search_pattern = f"%{search_term}%"

    results = (
        session.query(ASCLCode)
        .filter(ASCLCode.credit.like(search_pattern))
        .filter(ASCLCode.published == 1)
        .order_by(ASCLCode.time_added.desc())
        .limit(100)
        .all()
    )
```

**SQL Equivalent**:
```sql
SELECT * FROM codes
WHERE credit LIKE '%author%'
  AND published = 1
ORDER BY time_added DESC
LIMIT 100;
```

**Issues**:
1. ❌ **No name parsing**: Doesn't understand "Last, First" vs "First Last"
2. ❌ **No fuzzy matching**: Typos or variations miss results
3. ❌ **No ranking**: Results ordered by date, not relevance
4. ❌ **No grouping**: Same author variants scattered in results
5. ❌ **Poor performance**: Full table scan on TEXT field

---

## Problem Analysis

### Problem 1: Author Name Format Inconsistency

**Data Examples**:
```
"Smith, John K."
"Smith, J. K."
"Smith, John"
"John K. Smith"
"Smith"
"J. K. Smith"
```

**Current Behavior**:
- Search "Smith" → Finds all variations ✅
- Search "John Smith" → Misses "Smith, John" ❌
- Search "Smith, J." → Finds exact match only ❌

**Root Cause**: Authors stored as free-text strings without normalization

**Impact**: Users must know exact format to find all codes by an author

### Problem 2: No Relevance Ranking

**Scenario**: User searches "Einstein"

**Current Results** (ordered by date):
1. Code from 2024 mentioning "Einstein" in abstract
2. Code from 2023 with "Einstein" as co-author
3. Code from 2020 by "Albert Einstein" (primary author)

**Expected Results** (ordered by relevance):
1. Code by "Albert Einstein" (primary author) - exact match
2. Code with "Einstein" as co-author - high relevance
3. Code mentioning "Einstein" in abstract - lower relevance

**Root Cause**: ORDER BY time_added instead of relevance score

**Impact**: Best matches buried in results, poor user experience

### Problem 3: Poor Performance

**Current Performance** (with ~4,400 codes):
- General search: ~50-200ms (acceptable)
- Credit search: ~30-100ms (acceptable)

**Projected Performance** (with ~50,000 codes):
- General search: ~500-2000ms (slow)
- Credit search: ~300-1000ms (slow)

**Root Cause**:
```sql
EXPLAIN SELECT * FROM codes WHERE credit LIKE '%smith%';
+------+-------------+-------+------+---------------+------+---------+------+------+-------------+
| type | key         | rows  | Extra                                              |
+------+-------------+-------+------+---------------+------+---------+------+------+-------------+
| ALL  | NULL        | 4400  | Using where                                        |
+------+-------------+-------+------+---------------+------+---------+------+------+-------------+
```
- Full table scan (type=ALL)
- No index can be used for `LIKE '%term%'` (leading wildcard)

**Impact**: Acceptable now, will become slow as database grows

### Problem 4: No Fuzzy Matching

**Examples of Missed Results**:
- Search "O'Brien" misses "OBrien" (punctuation variation)
- Search "Mueller" misses "Müller" (diacritic variation)
- Search "MacKenzie" misses "McKenzie" (spelling variation)
- Search "Smyth" misses "Smith" (phonetic similarity)

**Root Cause**: Exact substring matching only

**Impact**: Users frustrated by missed results, especially with international names

---

## Recommended Solutions

### Phase 1: Quick Wins (Stay with MySQL LIKE)
**Timeline**: 1-2 days
**Complexity**: Low
**Impact**: Medium

#### 1.1: Add Published Filter to General Search
```python
# Before
results = session.query(ASCLCode).filter(
    or_(title.like(...), abstract.like(...), credit.like(...))
).all()

# After
results = session.query(ASCLCode).filter(
    ASCLCode.published == 1  # ← Add this
).filter(
    or_(title.like(...), abstract.like(...), credit.like(...))
).all()
```

#### 1.2: Add Pagination
```python
page = request.args.get('page', 1, type=int)
per_page = request.args.get('per_page', 50, type=int)

results = query.paginate(page=page, per_page=per_page, error_out=False)
```

#### 1.3: Add Basic Relevance Scoring
```python
from sqlalchemy import case, func

# Score: title match = 3, credit match = 2, abstract match = 1
score = case(
    (ASCLCode.title.like(search_pattern), 3),
    (ASCLCode.credit.like(search_pattern), 2),
    (ASCLCode.abstract.like(search_pattern), 1),
    else_=0
).label('score')

results = session.query(ASCLCode, score).filter(
    or_(...)
).order_by(score.desc(), ASCLCode.time_added.desc()).all()
```

#### 1.4: Add Simple Name Parsing for Credit Search
```python
def parse_author_name(name):
    """Extract search terms from author name."""
    # "John Smith" → ["John Smith", "Smith, John", "Smith"]
    # "Smith, John" → ["Smith, John", "John Smith", "Smith"]
    parts = name.split(',')
    if len(parts) == 2:
        last, first = parts[0].strip(), parts[1].strip()
        return [name, f"{first} {last}", last]
    else:
        words = name.split()
        if len(words) >= 2:
            return [name, f"{words[-1]}, {' '.join(words[:-1])}", words[-1]]
        return [name]

# Search for all variations
search_terms = parse_author_name(search_term)
results = session.query(ASCLCode).filter(
    or_(*[ASCLCode.credit.like(f"%{term}%") for term in search_terms])
).filter(ASCLCode.published == 1).all()
```

**Benefits**:
- ✅ Fixes critical published filter bug
- ✅ Adds pagination (performance improvement)
- ✅ Basic relevance ranking
- ✅ Better author name matching
- ✅ No new dependencies
- ✅ Quick to implement

**Limitations**:
- Still using LIKE (no fuzzy matching)
- Name parsing is simplistic
- No highlighting
- Still slow on very large datasets

---

### Phase 2: MySQL FULLTEXT Index
**Timeline**: 2-3 days
**Complexity**: Medium
**Impact**: High

#### 2.1: Add FULLTEXT Index

**Migration SQL**:
```sql
-- Add FULLTEXT index to codes table
ALTER TABLE codes ADD FULLTEXT INDEX ft_search (title, abstract, credit);

-- Optional: Add FULLTEXT to credit only for faster credit search
ALTER TABLE codes ADD FULLTEXT INDEX ft_credit (credit);
```

#### 2.2: Update Search Query

**Before (LIKE)**:
```python
results = session.query(ASCLCode).filter(
    or_(
        ASCLCode.title.like(f"%{query}%"),
        ASCLCode.abstract.like(f"%{query}%"),
        ASCLCode.credit.like(f"%{query}%")
    )
).all()
```

**After (FULLTEXT)**:
```python
from sqlalchemy import text, literal_column

# Use MATCH...AGAINST for natural language search with built-in ranking
score = literal_column(
    f"MATCH(title, abstract, credit) AGAINST(:query IN NATURAL LANGUAGE MODE)"
).label('score')

results = session.query(ASCLCode, score).filter(
    text("MATCH(title, abstract, credit) AGAINST(:query IN NATURAL LANGUAGE MODE)")
).params(query=query_string).order_by(score.desc()).all()
```

**Benefits**:
- ✅ Built-in relevance ranking
- ✅ Much faster than LIKE (uses index)
- ✅ Automatic word stemming (search "running" finds "run")
- ✅ Stop word filtering (ignores "the", "a", "an")
- ✅ Natural language processing

**Limitations**:
- ❌ No fuzzy matching (typos still miss results)
- ❌ Minimum word length (default 4 chars)
- ❌ Boolean mode less user-friendly
- ❌ Not as powerful as Elasticsearch

**Performance Improvement**:
```
Before (LIKE):  ~500-2000ms for 50k codes
After (FULLTEXT): ~10-50ms for 50k codes
```

---

### Phase 3: Author Normalization Table
**Timeline**: 3-5 days
**Complexity**: Medium-High
**Impact**: High (for author search)

#### 3.1: Create Authors Junction Table

**Migration SQL**:
```sql
CREATE TABLE code_authors (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    code_pk MEDIUMINT UNSIGNED NOT NULL,
    author_name VARCHAR(255) NOT NULL,          -- Full name as stored
    author_last VARCHAR(100),                   -- Extracted last name
    author_first VARCHAR(100),                  -- Extracted first name
    author_initials VARCHAR(20),                -- Extracted initials
    author_normalized VARCHAR(255),             -- Normalized form
    position INT UNSIGNED,                      -- Position in author list
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (code_pk) REFERENCES codes(pk) ON DELETE CASCADE,
    INDEX idx_code_pk (code_pk),
    INDEX idx_author_last (author_last),
    INDEX idx_author_normalized (author_normalized),
    FULLTEXT INDEX ft_author_name (author_name, author_normalized)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

#### 3.2: Parse and Populate Table

**Python Script**:
```python
import re
from sqlalchemy import select

def parse_author(author_str):
    """Parse author name into components."""
    author_str = author_str.strip()

    # "Last, First M." format
    if ',' in author_str:
        parts = author_str.split(',', 1)
        last = parts[0].strip()
        first_parts = parts[1].strip().split()
        first = first_parts[0] if first_parts else ''
        initials = ''.join([p[0] for p in first_parts if p])
    # "First M. Last" format
    else:
        parts = author_str.split()
        last = parts[-1] if parts else ''
        first = parts[0] if len(parts) > 1 else ''
        initials = ''.join([p[0] for p in parts[:-1] if p])

    # Normalized form: "Last, F. I."
    normalized = f"{last}, {initials}" if initials else last

    return {
        'author_name': author_str,
        'author_last': last,
        'author_first': first,
        'author_initials': initials,
        'author_normalized': normalized
    }

# Populate table
for code in session.query(ASCLCode).all():
    if code.credit:
        authors = code.credit.split(';')
        for position, author_str in enumerate(authors, 1):
            author_data = parse_author(author_str)
            author_record = CodeAuthor(
                code_pk=code.pk,
                position=position,
                **author_data
            )
            session.add(author_record)
session.commit()
```

#### 3.3: Update Credit Search to Use Junction Table

**Before**:
```python
results = session.query(ASCLCode).filter(
    ASCLCode.credit.like(f"%{search_term}%")
).all()
```

**After**:
```python
# Search multiple fields with ranking
results = session.query(ASCLCode,
    case(
        # Exact normalized match = highest score
        (CodeAuthor.author_normalized == normalized_term, 10),
        # Last name exact match
        (CodeAuthor.author_last == last_name, 8),
        # Full name match
        (CodeAuthor.author_name == search_term, 6),
        # Partial matches
        (CodeAuthor.author_last.like(f"%{last_name}%"), 4),
        (CodeAuthor.author_name.like(f"%{search_term}%"), 2),
        else_=0
    ).label('score')
).join(CodeAuthor).filter(
    or_(
        CodeAuthor.author_normalized.like(f"%{normalized_term}%"),
        CodeAuthor.author_last.like(f"%{last_name}%"),
        CodeAuthor.author_name.like(f"%{search_term}%")
    )
).order_by('score DESC', ASCLCode.time_added.desc()).all()
```

**Benefits**:
- ✅ Intelligent name matching
- ✅ Finds all author name variations
- ✅ Relevance ranking by match quality
- ✅ Fast (indexed searches)
- ✅ Can group by author variant
- ✅ Foundation for ORCID integration

**Maintenance**:
- Trigger or cron job to update when codes.credit changes
- Admin tool to manually correct/merge author entries

---

### Phase 4: Advanced Search Engine (Future)
**Timeline**: 2-4 weeks
**Complexity**: High
**Impact**: Very High

#### Option A: PostgreSQL Full-Text Search

**Migration Effort**: High (requires PostgreSQL migration)

**Implementation**:
```sql
-- Add tsvector column
ALTER TABLE codes ADD COLUMN search_vector tsvector;

-- Create index
CREATE INDEX idx_search_vector ON codes USING GIN(search_vector);

-- Populate search vector
UPDATE codes SET search_vector =
    setweight(to_tsvector('english', coalesce(title,'')), 'A') ||
    setweight(to_tsvector('english', coalesce(credit,'')), 'B') ||
    setweight(to_tsvector('english', coalesce(abstract,'')), 'C');

-- Trigger to keep search_vector updated
CREATE TRIGGER tsvector_update BEFORE INSERT OR UPDATE ON codes
FOR EACH ROW EXECUTE FUNCTION
    tsvector_update_trigger(search_vector, 'pg_catalog.english', title, credit, abstract);
```

**Search Query**:
```python
from sqlalchemy import func

results = session.query(ASCLCode,
    func.ts_rank(ASCLCode.search_vector, func.to_tsquery('english', query)).label('rank')
).filter(
    ASCLCode.search_vector.match(query, postgresql_regconfig='english')
).order_by('rank DESC').all()
```

**Additional Features**:
```python
# Fuzzy matching with trigrams
from sqlalchemy.dialects.postgresql import TRGM

session.query(ASCLCode).filter(
    ASCLCode.title.op('%')(search_term)  # Trigram similarity
).all()

# Phonetic matching
from sqlalchemy import func
session.query(ASCLCode).filter(
    func.soundex(ASCLCode.credit).like(func.soundex(search_term))
).all()
```

**Benefits**:
- ✅ Better than MySQL FULLTEXT
- ✅ Trigram similarity (fuzzy matching)
- ✅ Better language support
- ✅ Phrase search, proximity search
- ✅ Configurable ranking weights
- ✅ No additional service to maintain

**Drawbacks**:
- ❌ Requires PostgreSQL migration
- ❌ Learning curve for team
- ❌ Less powerful than Elasticsearch

#### Option B: Elasticsearch

**Infrastructure**:
- Elasticsearch cluster (can start with single node)
- Kibana for admin/debugging (optional)
- Sync mechanism (real-time or batch)

**Implementation**:
```python
from elasticsearch import Elasticsearch

es = Elasticsearch(['localhost:9200'])

# Index definition
index_settings = {
    "settings": {
        "analysis": {
            "analyzer": {
                "author_analyzer": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": ["lowercase", "asciifolding", "author_synonyms"]
                }
            },
            "filter": {
                "author_synonyms": {
                    "type": "synonym",
                    "synonyms": [
                        "o'brien, obrien",
                        "mueller, müller"
                    ]
                }
            }
        }
    },
    "mappings": {
        "properties": {
            "ascl_id": {"type": "keyword"},
            "title": {"type": "text", "boost": 3.0},
            "abstract": {"type": "text", "boost": 1.0},
            "credit": {"type": "text", "boost": 2.0, "analyzer": "author_analyzer"},
            "keywords": {"type": "keyword"},
            "time_added": {"type": "date"}
        }
    }
}

# Search with fuzzy matching
search_query = {
    "query": {
        "multi_match": {
            "query": query_string,
            "fields": ["title^3", "credit^2", "abstract^1"],
            "fuzziness": "AUTO",
            "operator": "and"
        }
    },
    "highlight": {
        "fields": {
            "title": {},
            "credit": {},
            "abstract": {}
        }
    },
    "aggs": {
        "keywords": {
            "terms": {"field": "keywords"}
        },
        "years": {
            "date_histogram": {
                "field": "time_added",
                "calendar_interval": "year"
            }
        }
    }
}

results = es.search(index="codes", body=search_query)
```

**Benefits**:
- ✅ Best search quality
- ✅ Fuzzy matching built-in
- ✅ Faceted search (filters by keyword, year, etc.)
- ✅ Result highlighting
- ✅ "Did you mean?" suggestions
- ✅ Synonyms, stemming, phonetic matching
- ✅ Advanced analytics
- ✅ Scales to millions of documents

**Drawbacks**:
- ❌ New service to maintain
- ❌ Additional infrastructure cost
- ❌ Sync complexity (keep MySQL and ES in sync)
- ❌ Learning curve
- ❌ Potential consistency issues

---

## Decision Matrix

| Feature | Current (LIKE) | Phase 1 (Improved LIKE) | Phase 2 (MySQL FT) | Phase 3 (PG FTS) | Phase 4 (Elasticsearch) |
|---------|---------------|------------------------|-------------------|------------------|------------------------|
| **Complexity** | ✅ Low | ✅ Low | ✅ Low | ⚠️ Medium | ❌ High |
| **Cost** | ✅ $0 | ✅ $0 | ✅ $0 | ⚠️ Migration | ❌ Infrastructure |
| **Speed** | ⚠️ Slow | ⚠️ Slow | ✅ Fast | ✅ Fast | ✅ Very Fast |
| **Relevance** | ❌ None | ⚠️ Basic | ✅ Good | ✅ Good | ✅ Excellent |
| **Fuzzy Match** | ❌ No | ❌ No | ❌ No | ✅ Yes | ✅ Yes |
| **Facets** | ❌ No | ❌ No | ❌ No | ⚠️ Manual | ✅ Built-in |
| **Highlights** | ❌ No | ❌ No | ❌ No | ⚠️ Manual | ✅ Built-in |
| **Author Intel** | ❌ No | ⚠️ Basic | ⚠️ Basic | ⚠️ With work | ✅ With config |
| **Maintenance** | ✅ Low | ✅ Low | ✅ Low | ⚠️ Medium | ❌ High |
| **Scalability** | ❌ Poor | ❌ Poor | ⚠️ Good | ✅ Good | ✅ Excellent |

---

## Recommended Implementation Path

### Immediate (This Sprint)
1. ✅ **Fix critical bugs** (Phase 1.1-1.2)
   - Add published=1 filter to general search
   - Add pagination to both searches
   - **Effort**: 2 hours
   - **Impact**: Critical bug fix

### Short Term (Next Sprint)
2. ✅ **Add basic improvements** (Phase 1.3-1.4)
   - Simple relevance scoring
   - Basic name parsing for credit search
   - **Effort**: 1-2 days
   - **Impact**: Better user experience

### Medium Term (Next Month)
3. ✅ **Implement MySQL FULLTEXT** (Phase 2)
   - Add FULLTEXT indexes
   - Update queries to use MATCH...AGAINST
   - Test performance improvements
   - **Effort**: 2-3 days
   - **Impact**: Significant performance and relevance improvements

4. ✅ **Create author normalization table** (Phase 3)
   - Design code_authors table
   - Write parsing script
   - Populate from existing data
   - Update credit search queries
   - **Effort**: 3-5 days
   - **Impact**: Much better author search

### Long Term (3-6 Months)
5. ⚠️ **Evaluate advanced options** (Phase 4)
   - Gather metrics on search usage
   - Measure user satisfaction
   - Evaluate PostgreSQL FTS vs Elasticsearch
   - Make decision based on data
   - **Effort**: 2-4 weeks
   - **Impact**: Best-in-class search

---

## Success Metrics

**Phase 1 Success Criteria**:
- ✅ Published filter working (no unpublished codes in results)
- ✅ Pagination working (no more than 50 results per page)
- ✅ Page load time < 200ms for typical searches

**Phase 2 Success Criteria**:
- ✅ FULLTEXT index created and working
- ✅ Search response time < 50ms for 95% of queries
- ✅ Relevance: best matches in top 5 results for 90% of searches
- ✅ User feedback: "search improved" comments

**Phase 3 Success Criteria**:
- ✅ Author table populated (100% of existing authors)
- ✅ Credit search finds all name variations
- ✅ Author search response time < 50ms
- ✅ User feedback: "author search much better"

**Phase 4 Success Criteria** (if needed):
- ✅ Fuzzy matching working (typos find correct results)
- ✅ Faceted search working (filter by keyword, year)
- ✅ Result highlighting working
- ✅ 95% user satisfaction with search

---

## Related Files

**Controllers**:
- `alt_ascl/source/ascl_net_app_project_home/ascl_net_app/controllers/search.py`

**Templates**:
- `alt_ascl/source/ascl_net_app_project_home/ascl_net_app/templates/search.html`
- `alt_ascl/source/ascl_net_app_project_home/ascl_net_app/templates/credit_search.html`

**Documentation**:
- `alt_ascl/agents/TODO_MASTER.md` (Section 7.4, 7.5)
- `alt_ascl/agents/CREDIT_SEARCH_IMPLEMENTATION.md`

---

**Last Updated**: 2025-12-01
**Next Review**: After Phase 2 implementation
**Owner**: Development Team
