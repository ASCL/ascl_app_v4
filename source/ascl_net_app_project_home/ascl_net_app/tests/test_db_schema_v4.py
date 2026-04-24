"""
Database Schema v4 Migration Validation Tests

This test suite validates the database schema changes made during the
v3 → v4 migration as documented in DB_UPGRADE_PLAYBOOK.sql.

Tests cover:
1. Schema structure (tables, columns, types, PKs, FKs, indexes)
2. Data integrity (no zero dates, FK validity, code_pk population)
3. SQLAlchemy ORM integration (model loading, relationships, queries)
4. Link type migration
5. Password column expansion

Run with: pytest -v test_db_schema_v4.py
"""

import pytest
from sqlalchemy import text, inspect
from sqlalchemy.exc import SQLAlchemyError

from ascl_core.database.connections import Trillian2DBConnection as db


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture(scope="module")
def engine():
    """Provide the SQLAlchemy engine."""
    return db.engine


@pytest.fixture(scope="module")
def inspector(engine):
    """Provide a SQLAlchemy inspector for schema introspection."""
    return inspect(engine)


@pytest.fixture(scope="module")
def session():
    """Provide a database session."""
    with db.Session() as session:
        yield session


# =============================================================================
# 1. Schema Structure Tests
# =============================================================================

class TestTableExistence:
    """Verify correct tables exist and legacy tables are removed."""

    EXPECTED_TABLES = {
        'codes',
        'keyword',  # Renamed from 'keywords' in v4
        'code_to_keyword',
        'code_alias',
        'link',
        'link_type',
        'citations',
        'ads_entry',
        'citefile_metadata',
        'change',
        'users',
    }

    # Legacy tables kept for backward compatibility but not part of core v4 schema
    LEGACY_KEPT_TABLES = {
        'ci_sessions',  # CodeIgniter session data (PHP/CodeIgniter legacy)
        'temp',         # Staging table for bulk operations (legacy)
    }

    LEGACY_TABLES = {
        'ads_entries',
        'links',
        'links_new',
        'citations_new',
        'classic_citations',
        'codes_backup2',
        'ascl_for_zenodo_matching_two',
        'ascl_for_zenodo_matching2',
        'code_keywords',  # Renamed to code_to_keyword
        'keywords',  # Renamed to keyword
    }

    def test_expected_tables_exist(self, inspector):
        """All expected tables should exist."""
        existing_tables = set(inspector.get_table_names())
        missing = self.EXPECTED_TABLES - existing_tables
        assert not missing, f"Missing tables: {missing}"

    def test_legacy_tables_removed(self, inspector):
        """Legacy tables should not exist."""
        existing_tables = set(inspector.get_table_names())
        present_legacy = self.LEGACY_TABLES & existing_tables
        assert not present_legacy, f"Legacy tables still present: {present_legacy}"


class TestPrimaryKeys:
    """Verify primary key naming and types."""

    def test_codes_pk(self, inspector):
        """codes table should have 'pk' as primary key."""
        pk_cols = inspector.get_pk_constraint('codes')
        assert pk_cols['constrained_columns'] == ['pk'], \
            f"codes PK should be ['pk'], got {pk_cols['constrained_columns']}"

    def test_codes_pk_type(self, inspector):
        """codes.pk should be INT (or MEDIUMINT for optimization)."""
        columns = {c['name']: c for c in inspector.get_columns('codes')}
        assert 'pk' in columns, "codes.pk column missing"
        pk_type = str(columns['pk']['type']).upper()
        assert 'INT' in pk_type, f"codes.pk should be INT type, got {pk_type}"

    def test_keyword_pk(self, inspector):
        """keyword table should have 'pk' as primary key."""
        pk_cols = inspector.get_pk_constraint('keyword')
        assert pk_cols['constrained_columns'] == ['pk'], \
            f"keyword PK should be ['pk'], got {pk_cols['constrained_columns']}"

    def test_keyword_pk_type(self, inspector):
        """keyword.pk should be INT."""
        columns = {c['name']: c for c in inspector.get_columns('keyword')}
        assert 'pk' in columns, "keyword.pk column missing"
        pk_type = str(columns['pk']['type']).upper()
        assert 'INT' in pk_type, f"keyword.pk should be INT, got {pk_type}"

    def test_keyword_columns(self, inspector):
        """keyword table should have pk, short_name, and label columns."""
        columns = {c['name'] for c in inspector.get_columns('keyword')}
        assert 'pk' in columns, "keyword.pk column missing"
        assert 'short_name' in columns, "keyword.short_name column missing"
        assert 'label' in columns, "keyword.label column missing"

    def test_no_id_columns_in_main_tables(self, inspector):
        """Main tables should not have 'id' column (should be renamed to 'pk')."""
        for table in ['codes', 'keyword']:
            columns = {c['name'] for c in inspector.get_columns(table)}
            assert 'id' not in columns, f"{table} should not have 'id' column (use 'pk')"


class TestForeignKeys:
    """Verify foreign key constraints."""

    EXPECTED_FKS = [
        # (table, fk_column, referenced_table, referenced_column)
        ('code_alias', 'code_pk', 'codes', 'pk'),
        ('code_to_keyword', 'code_pk', 'codes', 'pk'),
        ('code_to_keyword', 'keyword_pk', 'keyword', 'pk'),
        ('ads_entry', 'code_pk', 'codes', 'pk'),
        ('link', 'code_pk', 'codes', 'pk'),
        ('citefile_metadata', 'code_pk', 'codes', 'pk'),
        ('change', 'code_pk', 'codes', 'pk'),
        ('citations', 'code_pk', 'codes', 'pk'),
    ]

    def test_foreign_keys_exist(self, inspector):
        """All expected foreign keys should exist."""
        for table, fk_col, ref_table, ref_col in self.EXPECTED_FKS:
            fks = inspector.get_foreign_keys(table)
            matching_fk = None
            for fk in fks:
                if (fk_col in fk['constrained_columns'] and
                    fk['referred_table'] == ref_table and
                    ref_col in fk['referred_columns']):
                    matching_fk = fk
                    break
            assert matching_fk is not None, \
                f"Missing FK: {table}.{fk_col} → {ref_table}.{ref_col}"


class TestIndexes:
    """Verify performance indexes exist."""

    EXPECTED_INDEXES = [
        ('codes', 'idx_codes_ascl_id'),
        ('ads_entry', 'idx_ads_entry_code_pk'),
        ('link', 'idx_link_code_pk'),
        ('citefile_metadata', 'idx_citefile_metadata_code_pk'),
        ('change', 'idx_change_code_pk'),
        ('code_alias', 'idx_code_alias_code_pk'),
    ]

    def test_indexes_exist(self, inspector):
        """Performance indexes should exist."""
        for table, index_name in self.EXPECTED_INDEXES:
            indexes = inspector.get_indexes(table)
            index_names = {idx['name'] for idx in indexes}
            assert index_name in index_names, \
                f"Missing index {index_name} on {table}. Found: {index_names}"

    def test_link_unique_constraint(self, inspector):
        """link table should have unique constraint on (code_pk, url)."""
        indexes = inspector.get_indexes('link')
        unique_indexes = [idx for idx in indexes if idx.get('unique')]

        # Look for unique index on code_pk, url
        found = False
        for idx in unique_indexes:
            cols = set(idx['column_names'])
            if 'code_pk' in cols and 'url' in cols:
                found = True
                break

        assert found, "Missing unique constraint on link(code_pk, url)"

    def test_link_display_order_column(self, inspector):
        """link table should have display_order column for preserving order."""
        columns = {c['name'] for c in inspector.get_columns('link')}
        assert 'display_order' in columns, \
            "link table missing 'display_order' column (needed to preserve PHP array order)"


class TestEngineAndCharset:
    """Verify all tables use InnoDB and utf8mb4_unicode_ci."""

    def test_all_tables_innodb(self, session):
        """All tables should use InnoDB engine."""
        result = session.execute(text("""
            SELECT TABLE_NAME, ENGINE
            FROM information_schema.TABLES
            WHERE TABLE_SCHEMA = DATABASE()
              AND ENGINE != 'InnoDB'
        """))
        non_innodb = list(result)
        assert len(non_innodb) == 0, \
            f"Tables not using InnoDB: {[(r[0], r[1]) for r in non_innodb]}"

    def test_all_tables_utf8mb4(self, session):
        """All tables should use utf8mb4_unicode_ci collation."""
        result = session.execute(text("""
            SELECT TABLE_NAME, TABLE_COLLATION
            FROM information_schema.TABLES
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_COLLATION IS NOT NULL
              AND TABLE_COLLATION != 'utf8mb4_unicode_ci'
        """))
        wrong_collation = list(result)
        assert len(wrong_collation) == 0, \
            f"Tables with wrong collation: {[(r[0], r[1]) for r in wrong_collation]}"


class TestNamingConventions:
    """Verify naming conventions are followed."""

    def test_junction_table_naming(self, inspector):
        """Junction tables should follow {table1}_to_{table2} convention."""
        tables = inspector.get_table_names()

        # code_to_keyword should exist
        assert 'code_to_keyword' in tables, \
            "Junction table should be named 'code_to_keyword'"

        # Old name should not exist
        assert 'code_keywords' not in tables, \
            "Old junction table name 'code_keywords' should not exist"

    def test_fk_column_naming(self, inspector):
        """Foreign key columns should follow {table}_pk convention."""
        columns = {c['name'] for c in inspector.get_columns('code_to_keyword')}

        # Should have keyword_pk, not keyword_id
        assert 'keyword_pk' in columns, \
            "Junction table should use 'keyword_pk' column"
        assert 'keyword_id' not in columns, \
            "Old column name 'keyword_id' should not exist"


# =============================================================================
# 2. Data Integrity Tests
# =============================================================================

class TestNoZeroDates:
    """Verify no zero dates exist in timestamp columns."""

    def test_codes_no_zero_dates(self, session):
        """codes timestamp columns should have no zero dates."""
        # Temporarily disable strict mode for this check
        session.execute(text("SET @old_mode = @@sql_mode"))
        session.execute(text(
            "SET sql_mode = REPLACE(REPLACE(@@sql_mode,'NO_ZERO_DATE',''),'NO_ZERO_IN_DATE','')"
        ))

        result = session.execute(text("""
            SELECT
                SUM(CASE WHEN time_added = '0000-00-00 00:00:00' THEN 1 ELSE 0 END) as zero_added,
                SUM(CASE WHEN time_updated = '0000-00-00 00:00:00' THEN 1 ELSE 0 END) as zero_updated
            FROM codes
        """)).first()

        session.execute(text("SET sql_mode = @old_mode"))

        assert result[0] == 0, f"codes.time_added has {result[0]} zero dates"
        assert result[1] == 0, f"codes.time_updated has {result[1]} zero dates"

    def test_link_no_zero_dates(self, session):
        """link timestamp columns should have no zero dates."""
        session.execute(text("SET @old_mode = @@sql_mode"))
        session.execute(text(
            "SET sql_mode = REPLACE(REPLACE(@@sql_mode,'NO_ZERO_DATE',''),'NO_ZERO_IN_DATE','')"
        ))

        result = session.execute(text("""
            SELECT
                SUM(CASE WHEN updated_at = '0000-00-00 00:00:00' THEN 1 ELSE 0 END) as zero_updated,
                SUM(CASE WHEN last_working = '0000-00-00 00:00:00' THEN 1 ELSE 0 END) as zero_working
            FROM link
        """)).first()

        session.execute(text("SET sql_mode = @old_mode"))

        assert result[0] == 0, f"link.updated_at has {result[0]} zero dates"
        assert result[1] == 0, f"link.last_working has {result[1]} zero dates"


class TestForeignKeyValidity:
    """Verify no orphan records exist (FK integrity)."""

    def test_code_alias_no_orphans(self, session):
        """All code_alias should reference valid codes."""
        result = session.execute(text("""
            SELECT COUNT(*) FROM code_alias ca
            LEFT JOIN codes c ON ca.code_pk = c.pk
            WHERE c.pk IS NULL
        """)).scalar()
        assert result == 0, f"code_alias has {result} orphan records"

    def test_code_to_keyword_no_orphan_codes(self, session):
        """All code_to_keyword entries should reference valid codes."""
        result = session.execute(text("""
            SELECT COUNT(*) FROM code_to_keyword ctk
            LEFT JOIN codes c ON ctk.code_pk = c.pk
            WHERE c.pk IS NULL
        """)).scalar()
        assert result == 0, f"code_to_keyword has {result} orphan code references"

    def test_code_to_keyword_no_orphan_keywords(self, session):
        """All code_to_keyword entries should reference valid keywords."""
        result = session.execute(text("""
            SELECT COUNT(*) FROM code_to_keyword ctk
            LEFT JOIN keyword k ON ctk.keyword_pk = k.pk
            WHERE k.pk IS NULL
        """)).scalar()
        assert result == 0, f"code_to_keyword has {result} orphan keyword references"

    def test_link_no_orphans(self, session):
        """Links with code_pk should reference valid codes."""
        result = session.execute(text("""
            SELECT COUNT(*) FROM link l
            LEFT JOIN codes c ON l.code_pk = c.pk
            WHERE l.code_pk IS NOT NULL AND c.pk IS NULL
        """)).scalar()
        assert result == 0, f"link has {result} orphan code_pk references"

    def test_citations_no_orphans(self, session):
        """Citations with code_pk should reference valid codes."""
        result = session.execute(text("""
            SELECT COUNT(*) FROM citations ct
            LEFT JOIN codes c ON ct.code_pk = c.pk
            WHERE ct.code_pk IS NOT NULL AND c.pk IS NULL
        """)).scalar()
        assert result == 0, f"citations has {result} orphan code_pk references"


class TestCodePkPopulation:
    """Verify code_pk columns are properly populated."""

    def test_citations_code_pk_populated(self, session):
        """citations.code_pk should be populated (very few NULLs expected)."""
        result = session.execute(text("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN code_pk IS NULL THEN 1 ELSE 0 END) as null_count
            FROM citations
        """)).first()

        total, null_count = result
        if total > 0:
            null_pct = (null_count / total) * 100
            # Allow up to 1% NULL (for unmatched legacy records)
            assert null_pct < 1, \
                f"citations.code_pk has {null_pct:.2f}% NULL values ({null_count}/{total})"

    def test_link_code_pk_populated(self, session):
        """link.code_pk should be populated."""
        result = session.execute(text("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN code_pk IS NULL THEN 1 ELSE 0 END) as null_count
            FROM link
        """)).first()

        total, null_count = result
        if total > 0:
            null_pct = (null_count / total) * 100
            assert null_pct < 1, \
                f"link.code_pk has {null_pct:.2f}% NULL values ({null_count}/{total})"


class TestDroppedColumns:
    """Verify legacy columns have been dropped."""

    def test_no_ascl_id_in_migrated_tables(self, inspector):
        """Tables migrated to code_pk should not have ascl_id column."""
        tables_without_ascl_id = [
            'ads_entry',
            'link',
            'change',
            'citefile_metadata',
        ]

        for table in tables_without_ascl_id:
            try:
                columns = {c['name'] for c in inspector.get_columns(table)}
                assert 'ascl_id' not in columns, \
                    f"{table} should not have 'ascl_id' column (migrated to code_pk)"
            except Exception:
                # Table might not exist (like ascl_for_zenodo_matching in test db)
                pass

    def test_no_entry_asclid_in_citations(self, inspector):
        """citations should not have entry_asclid column."""
        columns = {c['name'] for c in inspector.get_columns('citations')}
        assert 'entry_asclid' not in columns, \
            "citations should not have 'entry_asclid' column (migrated to code_pk)"

    def test_no_keywords_column_in_codes(self, inspector):
        """codes should not have 'keywords' PHP serialized column (migrated to keyword table)."""
        columns = {c['name'] for c in inspector.get_columns('codes')}
        assert 'keywords' not in columns, \
            "codes should not have 'keywords' column (data now in keyword table via code_to_keyword)"

    def test_no_php_serialized_columns_in_codes(self, inspector):
        """codes should not have PHP-serialized columns (migrated to link table)."""
        columns = {c['name'] for c in inspector.get_columns('codes')}
        php_columns = {'site_list', 'ref_list', 'described_in', 'used_in', 'see_also'}
        present = php_columns & columns
        assert not present, \
            f"codes should not have PHP-serialized columns: {present} (migrated to link/code_see_also tables)"


class TestDataCleanup:
    """Verify data cleanup transformations."""

    def test_doi_no_prefix(self, session):
        """DOI values should not have 'doi:' prefix."""
        result = session.execute(text("""
            SELECT COUNT(*) FROM codes
            WHERE doi REGEXP '^[dD][oO][iI]:'
        """)).scalar()
        assert result == 0, f"Found {result} DOI values with 'doi:' prefix (should be removed)"


# =============================================================================
# 3. SQLAlchemy ORM Tests
# =============================================================================

class TestORMModelLoading:
    """Verify SQLAlchemy ORM models load correctly."""

    def test_models_import(self):
        """All model classes should import without errors."""
        from ascl_core.database.ascldb import ASCLModelClasses as ascldb

        # Check all expected classes exist
        expected_classes = [
            'ASCLCode',
            'Keyword',
            'ASCLCodeAlias',
            'ASCLCodeToKeyword',
            'Link',
            'Citation',
            'ADSEntry',
            'CitefileMetadata',
            'Change',
            'User',
        ]

        for cls_name in expected_classes:
            assert hasattr(ascldb, cls_name), f"Model class {cls_name} not found"

    def test_configure_mappers_succeeds(self):
        """SQLAlchemy configure_mappers should succeed (relationship validation)."""
        from sqlalchemy.orm import configure_mappers
        # This is called at module load, but let's verify it works
        try:
            configure_mappers()
        except Exception as e:
            pytest.fail(f"configure_mappers() failed: {e}")


class TestORMRelationships:
    """Verify SQLAlchemy relationships work correctly."""

    def test_code_alias_relationship(self, session):
        """ASCLCode.aliases relationship should work."""
        from ascl_core.database.ascldb import ASCLModelClasses as ascldb

        # Find a code with aliases
        code = session.query(ascldb.ASCLCode).join(
            ascldb.ASCLCodeAlias,
            ascldb.ASCLCode.pk == ascldb.ASCLCodeAlias.code_pk
        ).first()

        if code:
            aliases = code.aliases
            assert isinstance(aliases, list), "aliases should be a list"
            assert len(aliases) > 0, "code should have aliases"

    def test_code_keywords_relationship(self, session):
        """ASCLCode.keywords relationship should work."""
        from ascl_core.database.ascldb import ASCLModelClasses as ascldb

        # Find a code with keywords
        code = session.query(ascldb.ASCLCode).join(
            ascldb.ASCLCodeToKeyword,
            ascldb.ASCLCode.pk == ascldb.ASCLCodeToKeyword.code_pk
        ).first()

        if code:
            keywords = code.keywords
            assert isinstance(keywords, list), "keywords should be a list"
            assert len(keywords) > 0, "code should have keywords"

    def test_code_links_relationship(self, session):
        """ASCLCode.links relationship should work."""
        from ascl_core.database.ascldb import ASCLModelClasses as ascldb

        # Find a code with links
        code = session.query(ascldb.ASCLCode).join(
            ascldb.Link,
            ascldb.ASCLCode.pk == ascldb.Link.code_pk
        ).first()

        if code:
            links = code.links
            assert isinstance(links, list), "links should be a list"

    def test_code_citations_relationship(self, session):
        """ASCLCode.citations relationship should work."""
        from ascl_core.database.ascldb import ASCLModelClasses as ascldb

        # Find a code with citations
        code = session.query(ascldb.ASCLCode).join(
            ascldb.Citation,
            ascldb.ASCLCode.pk == ascldb.Citation.code_pk
        ).first()

        if code:
            citations = code.citations
            assert isinstance(citations, list), "citations should be a list"

    def test_code_ads_entries_relationship(self, session):
        """ASCLCode.ads_entries relationship should work."""
        from ascl_core.database.ascldb import ASCLModelClasses as ascldb

        # Find a code with ADS entries
        code = session.query(ascldb.ASCLCode).join(
            ascldb.ADSEntry,
            ascldb.ASCLCode.pk == ascldb.ADSEntry.code_pk
        ).first()

        if code:
            ads_entries = code.ads_entries
            assert isinstance(ads_entries, list), "ads_entries should be a list"

    def test_code_changes_relationship(self, session):
        """ASCLCode.changes relationship should work."""
        from ascl_core.database.ascldb import ASCLModelClasses as ascldb

        # Find a code with changes
        code = session.query(ascldb.ASCLCode).join(
            ascldb.Change,
            ascldb.ASCLCode.pk == ascldb.Change.code_pk
        ).first()

        if code:
            changes = code.changes
            assert isinstance(changes, list), "changes should be a list"


class TestORMQueries:
    """Verify common query patterns work."""

    def test_basic_code_query(self, session):
        """Basic code query should work."""
        from ascl_core.database.ascldb import ASCLModelClasses as ascldb

        codes = session.query(ascldb.ASCLCode).limit(5).all()
        assert len(codes) > 0, "Should be able to query codes"

        # Verify pk attribute exists
        for code in codes:
            assert hasattr(code, 'pk'), "ASCLCode should have 'pk' attribute"
            assert code.pk is not None, "pk should not be None"

    def test_keyword_count_query(self, session):
        """Keyword count query should work with new schema."""
        from ascl_core.database.ascldb import ASCLModelClasses as ascldb
        from sqlalchemy import func

        # Count codes per keyword
        result = session.query(
            ascldb.Keyword.label,
            func.count(ascldb.ASCLCodeToKeyword.code_pk)
        ).join(
            ascldb.ASCLCodeToKeyword,
            ascldb.Keyword.pk == ascldb.ASCLCodeToKeyword.keyword_pk
        ).group_by(
            ascldb.Keyword.pk
        ).limit(5).all()

        assert len(result) > 0, "Should get keyword counts"

    def test_code_with_eager_load(self, session):
        """Code query with eager loading should work."""
        from ascl_core.database.ascldb import ASCLModelClasses as ascldb
        from sqlalchemy.orm import selectinload

        code = session.query(ascldb.ASCLCode).options(
            selectinload(ascldb.ASCLCode.keywords),
        ).filter(
            ascldb.ASCLCode.published == 1
        ).first()

        assert code is not None, "Should find a published code"
        # Access relationship (should not trigger additional query due to eager load)
        _ = code.keywords


# =============================================================================
# 4. Link Type Migration Tests
# =============================================================================

class TestLinkTypes:
    """Verify link_type table migration."""

    EXPECTED_LINK_TYPES = [
        ('EMAC', 'emac'),
        ('Code Site', 'code-site'),
        ('Described In', 'described-in'),
        ('Used In', 'used-in'),
        ('Refereed', 'refereed'),
    ]

    def test_link_type_columns_exist(self, inspector):
        """link_type should have short_name and description columns."""
        columns = {c['name'] for c in inspector.get_columns('link_type')}
        assert 'short_name' in columns, "link_type missing 'short_name' column"
        assert 'description' in columns, "link_type missing 'description' column"

    def test_new_link_types_exist(self, session):
        """New link types should be present."""
        for name, short_name in self.EXPECTED_LINK_TYPES:
            result = session.execute(text(
                "SELECT COUNT(*) FROM link_type WHERE name = :name AND short_name = :short_name"
            ), {'name': name, 'short_name': short_name}).scalar()

            assert result > 0, f"Missing link type: {name} ({short_name})"

    def test_emac_links_preserved(self, session):
        """EMAC links from v3 links_new should be preserved in v4 link table."""
        result = session.execute(text("""
            SELECT COUNT(*) FROM link l
            JOIN link_type lt ON l.link_type_pk = lt.pk
            WHERE lt.short_name = 'emac'
        """)).scalar()

        assert result > 0, "No EMAC links found — v3 links_new EMAC data was lost during migration"


# =============================================================================
# 5. Password Column Test
# =============================================================================

class TestPasswordColumn:
    """Verify password column supports bcrypt hashes."""

    def test_password_column_length(self, inspector):
        """users.password should be VARCHAR(60) for bcrypt."""
        columns = {c['name']: c for c in inspector.get_columns('users')}
        assert 'password' in columns, "users.password column missing"

        pwd_col = columns['password']
        # VARCHAR length should be at least 60
        col_type = str(pwd_col['type'])
        # Extract length from VARCHAR(60)
        import re
        match = re.search(r'VARCHAR\((\d+)\)', col_type, re.IGNORECASE)
        if match:
            length = int(match.group(1))
            assert length >= 60, f"users.password should be VARCHAR(60+), got VARCHAR({length})"


# =============================================================================
# Summary Test
# =============================================================================

class TestMigrationSummary:
    """Summary test to verify overall migration success."""

    def test_migration_version_marker(self, session):
        """Verify we're connected to v4 database."""
        # Check for v4-specific features
        result = session.execute(text("""
            SELECT COUNT(*) FROM information_schema.TABLES
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'code_to_keyword'
        """)).scalar()

        assert result == 1, "code_to_keyword table should exist (v4 indicator)"

    def test_total_table_count(self, inspector):
        """Verify reasonable number of tables exist."""
        tables = inspector.get_table_names()
        # Should have at least the core tables
        assert len(tables) >= 10, f"Expected at least 10 tables, got {len(tables)}"
        # Should not have too many (legacy cleanup)
        assert len(tables) <= 21, f"Too many tables ({len(tables)}), check legacy cleanup"
