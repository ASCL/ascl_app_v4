-- ============================================================================
-- ASCL Database Upgrade Playbook
-- ============================================================================
-- Purpose: Upgrade ascl_db to v4 with InnoDB, proper PKs, FKs, and indexes
-- Source: ascl_db (MyISAM, no FKs)
-- Target: ascl_db_v4 (InnoDB, with FKs)
--
-- This file can be replayed from a fresh dump of production database
-- Execute with: mysql --defaults-group-suffix=_ascl < DB_UPGRADE_PLAYBOOK.sql
--
-- Started: 2025-11-29
-- ============================================================================

-- ============================================================================
-- STEP 0: Create Database and Copy Data
-- ============================================================================
-- NOTE: Requires elevated privileges (root or admin user)
-- Run separately with root user:
--
-- CREATE DATABASE ascl_db_v4 CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
-- GRANT ALL PRIVILEGES ON ascl_db_v4.* TO 'ascl_db'@'%';
-- FLUSH PRIVILEGES;
--
-- Then copy data:
-- mysqldump --defaults-group-suffix=_ascl ascl_db | mysql --defaults-group-suffix=_ascl ascl_db_v4
-- ============================================================================

USE ascl_db_v4;

-- ============================================================================
-- STEP 0a: Remove Legacy Tables (Do Not Carry Forward)
-- ============================================================================
-- Decision (2025-11-30): Drop these legacy tables from ascl_db_v4 and exclude
-- them from any future imports or replays.
-- ============================================================================

DROP TABLE IF EXISTS `ascl_for_zenodo_matching_two`;
DROP TABLE IF EXISTS `ascl_for_zenodo_matching2`;
DROP TABLE IF EXISTS `ads_entries`;
DROP TABLE IF EXISTS `codes_backup2`;
DROP TABLE IF EXISTS `classic_citations`;
DROP TABLE IF EXISTS `citations_new`;
DROP TABLE IF EXISTS `links`;

-- ============================================================================
-- STEP 1: Fix Timestamp Columns (Required for InnoDB Conversion)
-- ============================================================================
-- InnoDB in strict mode doesn't allow '0000-00-00 00:00:00' values
-- Must convert these to NULL before engine conversion
-- ============================================================================

-- Save current SQL mode
SET @old_sql_mode = @@sql_mode;

-- Drop NO_ZERO_DATE and NO_ZERO_IN_DATE for this session
SET sql_mode = REPLACE(REPLACE(@@sql_mode,'NO_ZERO_DATE',''),'NO_ZERO_IN_DATE','');

-- ----------------------------------------------------------------------------
-- Table: codes
-- ----------------------------------------------------------------------------
ALTER TABLE `codes`
  MODIFY `time_added` TIMESTAMP NULL,
  MODIFY `time_updated` TIMESTAMP NULL;

UPDATE `codes`
  SET `time_updated` = NULL
  WHERE `time_updated` = '0000-00-00 00:00:00';

UPDATE `codes`
  SET `time_added` = NULL
  WHERE `time_added` = '0000-00-00 00:00:00';

ALTER TABLE `codes`
  MODIFY `time_added` TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
  MODIFY `time_updated` TIMESTAMP NULL DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP;

-- Note: Legacy tables (codes_backup2, links) are removed and should be excluded from future imports.

-- ----------------------------------------------------------------------------
-- Table: links_new
-- ----------------------------------------------------------------------------
ALTER TABLE `links_new`
  MODIFY `created_at` TIMESTAMP NULL,
  MODIFY `updated_at` TIMESTAMP NULL,
  MODIFY `last_working` DATETIME NULL;

UPDATE `links_new`
  SET `updated_at` = NULL
  WHERE `updated_at` = '0000-00-00 00:00:00';

UPDATE `links_new`
  SET `last_working` = NULL
  WHERE `last_working` = '0000-00-00 00:00:00';

ALTER TABLE `links_new`
  MODIFY `created_at` TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
  MODIFY `updated_at` TIMESTAMP NULL DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP,
  MODIFY `last_working` DATETIME NULL DEFAULT NULL;

-- Restore SQL mode
SET sql_mode = @old_sql_mode;

-- ============================================================================
-- STEP 2: Convert Tables from MyISAM to InnoDB
-- ============================================================================
-- Note: Zenodo tables and link_type already InnoDB, skipping those
-- ============================================================================

-- Note: Legacy tables dropped/omitted from ascl_db_v4 and future imports:
--   ads_entries, links, citations_new, classic_citations, codes_backup2,
--   ascl_for_zenodo_matching_two, ascl_for_zenodo_matching2

ALTER TABLE `ads_entries_new` ENGINE = InnoDB;
ALTER TABLE `change` ENGINE = InnoDB;
ALTER TABLE `citations` ENGINE = InnoDB;
ALTER TABLE `citefile_metadata` ENGINE = InnoDB;
ALTER TABLE `ci_sessions` ENGINE = InnoDB;
ALTER TABLE `codes` ENGINE = InnoDB;
ALTER TABLE `code_aliases` ENGINE = InnoDB;
ALTER TABLE `code_keywords` ENGINE = InnoDB;
ALTER TABLE `keywords` ENGINE = InnoDB;
ALTER TABLE `links_new` ENGINE = InnoDB;
ALTER TABLE `temp` ENGINE = InnoDB;
ALTER TABLE `users` ENGINE = InnoDB;

-- ============================================================================
-- STEP 2.5: Convert Character Sets to utf8mb4_unicode_ci
-- ============================================================================
-- Standardize all tables to utf8mb4_unicode_ci for:
--   - Full Unicode support (emojis, international characters)
--   - Consistent collation (prevents JOIN errors)
--   - Foreign key compatibility (FKs require matching collations)
--   - PostgreSQL migration readiness
--
-- Current state: Mix of latin1, utf8mb3_general_ci, utf8mb3_unicode_ci, utf8mb4_general_ci
-- Target state: All utf8mb4_unicode_ci
-- See DB_CHARSET_ANALYSIS.md for detailed analysis
--
-- NOTE: Legacy tables dropped/omitted from ascl_db_v4 and future imports:
--   ascl_for_zenodo_matching_two, ascl_for_zenodo_matching2, ads_entries,
--   links, citations_new, classic_citations, codes_backup2
-- ============================================================================

-- Convert tables without foreign keys first
ALTER TABLE ascl_for_zenodo_matching CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
ALTER TABLE temp CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
ALTER TABLE citefile_metadata CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- Convert core tables (will have FKs referencing them)
ALTER TABLE keywords CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
ALTER TABLE codes CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- Convert junction/reference tables
ALTER TABLE code_keywords CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
ALTER TABLE code_aliases CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- Convert citation/link tables
ALTER TABLE citations CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
ALTER TABLE ads_entries_new CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
ALTER TABLE links_new CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
ALTER TABLE link_type CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- Convert remaining tables
ALTER TABLE `change` CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
ALTER TABLE ci_sessions CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
ALTER TABLE users CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- ============================================================================
-- STEP 3: Normalize key column types for FK compatibility
-- ============================================================================

-- Rename codes.id -> codes.pk (only if id still exists)
SET @has_codes_id := (
  SELECT COUNT(*)
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'codes'
    AND COLUMN_NAME = 'id'
);
SET @sql_codes_pk := IF(
  @has_codes_id = 1,
  'ALTER TABLE `codes` CHANGE COLUMN `id` `pk` MEDIUMINT UNSIGNED NOT NULL AUTO_INCREMENT',
  'SELECT \"codes.pk already present\"'
);
PREPARE stmt FROM @sql_codes_pk;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

ALTER TABLE `keywords`
  MODIFY `id` INT UNSIGNED NOT NULL AUTO_INCREMENT;

ALTER TABLE `code_keywords`
  MODIFY `code_id` MEDIUMINT UNSIGNED NOT NULL,
  MODIFY `keyword_id` INT UNSIGNED NOT NULL;

ALTER TABLE `code_aliases`
  MODIFY `code_id` MEDIUMINT UNSIGNED NOT NULL;

-- ============================================================================
-- STEP 4: Add Indexes on ascl_id Column (non-unique; duplicates exist)
-- ============================================================================

-- Add non-unique index on ascl_id if missing
SET @has_idx_codes_ascl_id := (
  SELECT COUNT(*)
  FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'codes'
    AND INDEX_NAME = 'idx_codes_ascl_id'
);
SET @sql_idx_codes_ascl_id := IF(
  @has_idx_codes_ascl_id = 0,
  'ALTER TABLE `codes` ADD KEY idx_codes_ascl_id (ascl_id)',
  'SELECT \"idx_codes_ascl_id already present\"'
);
PREPARE stmt FROM @sql_idx_codes_ascl_id;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Note: Legacy tables dropped/omitted, no indexes added for:
--   ads_entries, links, citations_new, codes_backup2,
--   ascl_for_zenodo_matching2, ascl_for_zenodo_matching_two

-- ads_entries_new.ascl_id
SET @has_idx_ads_entries_new_ascl_id := (
  SELECT COUNT(*)
  FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'ads_entries_new'
    AND INDEX_NAME = 'idx_ads_entries_new_ascl_id'
);
SET @sql_idx_ads_entries_new_ascl_id := IF(
  @has_idx_ads_entries_new_ascl_id = 0,
  'ALTER TABLE `ads_entries_new` ADD KEY idx_ads_entries_new_ascl_id (ascl_id)',
  'SELECT \"idx_ads_entries_new_ascl_id already present\"'
);
PREPARE stmt FROM @sql_idx_ads_entries_new_ascl_id;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- ascl_for_zenodo_matching.ascl_id
SET @has_idx_ascl_for_zenodo_matching_ascl_id := (
  SELECT COUNT(*)
  FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'ascl_for_zenodo_matching'
    AND INDEX_NAME = 'idx_ascl_for_zenodo_matching_ascl_id'
);
SET @sql_idx_ascl_for_zenodo_matching_ascl_id := IF(
  @has_idx_ascl_for_zenodo_matching_ascl_id = 0,
  'ALTER TABLE `ascl_for_zenodo_matching` ADD KEY idx_ascl_for_zenodo_matching_ascl_id (ascl_id)',
  'SELECT \"idx_ascl_for_zenodo_matching_ascl_id already present\"'
);
PREPARE stmt FROM @sql_idx_ascl_for_zenodo_matching_ascl_id;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- citefile_metadata.ascl_id
SET @has_idx_citefile_ascl_id := (
  SELECT COUNT(*)
  FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'citefile_metadata'
    AND INDEX_NAME = 'idx_citefile_ascl_id'
);
SET @sql_idx_citefile_ascl_id := IF(
  @has_idx_citefile_ascl_id = 0,
  'ALTER TABLE `citefile_metadata` ADD KEY idx_citefile_ascl_id (ascl_id)',
  'SELECT \"idx_citefile_ascl_id already present\"'
);
PREPARE stmt FROM @sql_idx_citefile_ascl_id;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- links_new.ascl_id
SET @has_idx_links_new_ascl_id := (
  SELECT COUNT(*)
  FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'links_new'
    AND INDEX_NAME = 'idx_links_new_ascl_id'
);
SET @sql_idx_links_new_ascl_id := IF(
  @has_idx_links_new_ascl_id = 0,
  'ALTER TABLE `links_new` ADD KEY idx_links_new_ascl_id (ascl_id)',
  'SELECT \"idx_links_new_ascl_id already present\"'
);
PREPARE stmt FROM @sql_idx_links_new_ascl_id;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- change.ascl_id
SET @has_idx_change_ascl_id := (
  SELECT COUNT(*)
  FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'change'
    AND INDEX_NAME = 'idx_change_ascl_id'
);
SET @sql_idx_change_ascl_id := IF(
  @has_idx_change_ascl_id = 0,
  'ALTER TABLE `change` ADD KEY idx_change_ascl_id (ascl_id)',
  'SELECT \"idx_change_ascl_id already present\"'
);
PREPARE stmt FROM @sql_idx_change_ascl_id;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- ============================================================================
-- STEP 5: Add Other Performance Indexes
-- ============================================================================

-- citations.entry_asclid
SET @has_idx_citations_entry_asclid := (
  SELECT COUNT(*)
  FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'citations'
    AND INDEX_NAME = 'idx_citations_entry_asclid'
);
SET @sql_idx_citations_entry_asclid := IF(
  @has_idx_citations_entry_asclid = 0,
  'ALTER TABLE `citations` ADD KEY idx_citations_entry_asclid (entry_asclid)',
  'SELECT \"idx_citations_entry_asclid already present\"'
);
PREPARE stmt FROM @sql_idx_citations_entry_asclid;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- citations.entry_asclid,year
SET @has_idx_citations_entry_year := (
  SELECT COUNT(*)
  FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'citations'
    AND INDEX_NAME = 'idx_citations_entry_year'
);
SET @sql_idx_citations_entry_year := IF(
  @has_idx_citations_entry_year = 0,
  'ALTER TABLE `citations` ADD KEY idx_citations_entry_year (entry_asclid, year)',
  'SELECT \"idx_citations_entry_year already present\"'
);
PREPARE stmt FROM @sql_idx_citations_entry_year;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Note: Legacy tables dropped/omitted (citations_new, links)

-- code_aliases.code_id
SET @has_idx_code_aliases_code_id := (
  SELECT COUNT(*)
  FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'code_aliases'
    AND INDEX_NAME = 'idx_code_aliases_code_id'
);
SET @sql_idx_code_aliases_code_id := IF(
  @has_idx_code_aliases_code_id = 0,
  'ALTER TABLE `code_aliases` ADD KEY idx_code_aliases_code_id (code_id)',
  'SELECT \"idx_code_aliases_code_id already present\"'
);
PREPARE stmt FROM @sql_idx_code_aliases_code_id;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- ============================================================================
-- STEP 6: Add Unique Constraints
-- ============================================================================

-- links_new unique (ascl_id, url)
SET @has_uniq_links_new_asclid_url := (
  SELECT COUNT(*)
  FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'links_new'
    AND INDEX_NAME = 'uniq_links_new_asclid_url'
);
SET @sql_uniq_links_new_asclid_url := IF(
  @has_uniq_links_new_asclid_url = 0,
  'ALTER TABLE `links_new` ADD UNIQUE KEY `uniq_links_new_asclid_url` (`ascl_id`, `url`)',
  'SELECT \"uniq_links_new_asclid_url already present\"'
);
PREPARE stmt FROM @sql_uniq_links_new_asclid_url;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- ============================================================================
-- STEP 7: Add Foreign Keys
-- ============================================================================
-- Only adding FKs that reference codes.pk (PRIMARY KEY)
-- Cannot add FKs to codes.ascl_id (not unique - 604 unpublished codes = '0000.000')
-- See ASCL_DB Upgrade.md for detailed design notes and future enhancements
-- ============================================================================

-- code_aliases: Each alias must belong to a valid code
SET @fk_code_aliases_code_exists := (
  SELECT COUNT(*) FROM information_schema.REFERENTIAL_CONSTRAINTS
  WHERE CONSTRAINT_SCHEMA = DATABASE()
    AND CONSTRAINT_NAME = 'fk_code_aliases_code'
    AND TABLE_NAME = 'code_aliases'
);
SET @sql_fk_code_aliases_code := IF(
  @fk_code_aliases_code_exists = 0,
  'ALTER TABLE `code_aliases` ADD CONSTRAINT `fk_code_aliases_code` FOREIGN KEY (`code_id`) REFERENCES `codes` (`pk`) ON DELETE RESTRICT ON UPDATE CASCADE',
  'SELECT \"fk_code_aliases_code already present\"'
);
PREPARE stmt FROM @sql_fk_code_aliases_code;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- code_keywords: Links codes to keywords (many-to-many junction table)
SET @fk_code_keywords_code_exists := (
  SELECT COUNT(*) FROM information_schema.REFERENTIAL_CONSTRAINTS
  WHERE CONSTRAINT_SCHEMA = DATABASE()
    AND CONSTRAINT_NAME = 'fk_code_keywords_code'
    AND TABLE_NAME = 'code_keywords'
);
SET @sql_fk_code_keywords_code := IF(
  @fk_code_keywords_code_exists = 0,
  'ALTER TABLE `code_keywords` ADD CONSTRAINT `fk_code_keywords_code` FOREIGN KEY (`code_id`) REFERENCES `codes` (`pk`) ON DELETE CASCADE ON UPDATE CASCADE',
  'SELECT \"fk_code_keywords_code already present\"'
);
PREPARE stmt FROM @sql_fk_code_keywords_code;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @fk_code_keywords_keyword_exists := (
  SELECT COUNT(*) FROM information_schema.REFERENTIAL_CONSTRAINTS
  WHERE CONSTRAINT_SCHEMA = DATABASE()
    AND CONSTRAINT_NAME = 'fk_code_keywords_keyword'
    AND TABLE_NAME = 'code_keywords'
);
SET @sql_fk_code_keywords_keyword := IF(
  @fk_code_keywords_keyword_exists = 0,
  'ALTER TABLE `code_keywords` ADD CONSTRAINT `fk_code_keywords_keyword` FOREIGN KEY (`keyword_id`) REFERENCES `keywords` (`id`) ON DELETE CASCADE ON UPDATE CASCADE',
  'SELECT \"fk_code_keywords_keyword already present\"'
);
PREPARE stmt FROM @sql_fk_code_keywords_keyword;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- ============================================================================
-- STEP 8: Update link_type table and rename links_new to links
-- ============================================================================
-- Add short_name and description columns to link_type table
-- These fields allow better categorization and description of link types

ALTER TABLE link_type
ADD COLUMN short_name VARCHAR(50) NULL AFTER label,
ADD COLUMN description TEXT NULL AFTER short_name;

-- Insert new link types for PHP-serialized field migration
-- These types correspond to the PHP-serialized fields in codes table:
-- site_list → 'Code Site'
-- described_in → 'Described In'
-- used_in → 'Used In'
-- ref_list → 'Reference'

INSERT INTO link_type (label, short_name, description) VALUES
('Code Site', 'code-site', 'This should be the URL to a site from where the code can be downloaded or copied.'),
('Described In', 'described-in', 'Publication where the code is described.'),
('Used In', 'used-in', 'Publications that use the code.'),
('Refereed', 'refereed', 'Paper that uses the code.');

-- Rename links_new to link (singular, to match Python class naming convention)
-- The legacy 'links' table was already dropped in STEP 0a

ALTER TABLE links_new RENAME TO link;

-- ============================================================================
-- STEP 9: Prepare dependent tables to reference codes.pk (numeric FK)
-- ============================================================================
-- Goal: Move off codes.ascl_id string linkage; keep ascl_id for backward compat
-- Approach: Add nullable code_pk columns, backfill via join on ascl_id, index,
--           then add FKs to codes.pk.
-- ============================================================================

-- Add code_pk columns (idempotent via information_schema check)
SET @has_ads_entries_new_code_pk := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'ads_entries_new' AND COLUMN_NAME = 'code_pk'
);
SET @sql_ads_entries_new_code_pk := IF(
  @has_ads_entries_new_code_pk = 0,
  'ALTER TABLE `ads_entries_new` ADD COLUMN `code_pk` MEDIUMINT UNSIGNED NULL AFTER `ascl_id`',
  'SELECT \"ads_entries_new.code_pk already present\"'
);
PREPARE stmt FROM @sql_ads_entries_new_code_pk;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_link_code_pk := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'link' AND COLUMN_NAME = 'code_pk'
);
SET @sql_link_code_pk := IF(
  @has_link_code_pk = 0,
  'ALTER TABLE `link` ADD COLUMN `code_pk` MEDIUMINT UNSIGNED NULL AFTER `ascl_id`',
  'SELECT \"link.code_pk already present\"'
);
PREPARE stmt FROM @sql_link_code_pk;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_citefile_metadata_code_pk := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'citefile_metadata' AND COLUMN_NAME = 'code_pk'
);
SET @sql_citefile_metadata_code_pk := IF(
  @has_citefile_metadata_code_pk = 0,
  'ALTER TABLE `citefile_metadata` ADD COLUMN `code_pk` MEDIUMINT UNSIGNED NULL AFTER `ascl_id`',
  'SELECT \"citefile_metadata.code_pk already present\"'
);
PREPARE stmt FROM @sql_citefile_metadata_code_pk;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_change_code_pk := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'change' AND COLUMN_NAME = 'code_pk'
);
SET @sql_change_code_pk := IF(
  @has_change_code_pk = 0,
  'ALTER TABLE `change` ADD COLUMN `code_pk` MEDIUMINT UNSIGNED NULL AFTER `ascl_id`',
  'SELECT \"change.code_pk already present\"'
);
PREPARE stmt FROM @sql_change_code_pk;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_ascl_for_zenodo_matching_code_pk := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'ascl_for_zenodo_matching' AND COLUMN_NAME = 'code_pk'
);
SET @sql_ascl_for_zenodo_matching_code_pk := IF(
  @has_ascl_for_zenodo_matching_code_pk = 0,
  'ALTER TABLE `ascl_for_zenodo_matching` ADD COLUMN `code_pk` MEDIUMINT UNSIGNED NULL AFTER `ascl_id`',
  'SELECT \"ascl_for_zenodo_matching.code_pk already present\"'
);
PREPARE stmt FROM @sql_ascl_for_zenodo_matching_code_pk;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Backfill code_pk from codes.pk via ascl_id match; leave NULL if placeholder/unknown
UPDATE `ads_entries_new` a
JOIN `codes` c ON a.ascl_id = c.ascl_id
SET a.code_pk = c.pk
WHERE a.code_pk IS NULL;

UPDATE `link` l
JOIN `codes` c ON l.ascl_id = c.ascl_id
SET l.code_pk = c.pk
WHERE l.code_pk IS NULL;

UPDATE `citefile_metadata` m
JOIN `codes` c ON m.ascl_id = c.ascl_id
SET m.code_pk = c.pk
WHERE m.code_pk IS NULL;

UPDATE `change` ch
JOIN `codes` c ON ch.ascl_id = c.ascl_id
SET ch.code_pk = c.pk
WHERE ch.code_pk IS NULL;

UPDATE `ascl_for_zenodo_matching` z
JOIN `codes` c ON z.ascl_id = c.ascl_id
SET z.code_pk = c.pk
WHERE z.code_pk IS NULL;

-- Index the new FK columns (idempotent)
SET @has_idx_ads_entries_new_code_pk := (
  SELECT COUNT(*) FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'ads_entries_new'
    AND INDEX_NAME = 'idx_ads_entries_new_code_pk'
);
SET @sql_idx_ads_entries_new_code_pk := IF(
  @has_idx_ads_entries_new_code_pk = 0,
  'ALTER TABLE `ads_entries_new` ADD INDEX idx_ads_entries_new_code_pk (code_pk)',
  'SELECT \"idx_ads_entries_new_code_pk already present\"'
);
PREPARE stmt FROM @sql_idx_ads_entries_new_code_pk;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_idx_link_code_pk := (
  SELECT COUNT(*) FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'link'
    AND INDEX_NAME = 'idx_link_code_pk'
);
SET @sql_idx_link_code_pk := IF(
  @has_idx_link_code_pk = 0,
  'ALTER TABLE `link` ADD INDEX idx_link_code_pk (code_pk)',
  'SELECT \"idx_link_code_pk already present\"'
);
PREPARE stmt FROM @sql_idx_link_code_pk;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_idx_citefile_metadata_code_pk := (
  SELECT COUNT(*) FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'citefile_metadata'
    AND INDEX_NAME = 'idx_citefile_metadata_code_pk'
);
SET @sql_idx_citefile_metadata_code_pk := IF(
  @has_idx_citefile_metadata_code_pk = 0,
  'ALTER TABLE `citefile_metadata` ADD INDEX idx_citefile_metadata_code_pk (code_pk)',
  'SELECT \"idx_citefile_metadata_code_pk already present\"'
);
PREPARE stmt FROM @sql_idx_citefile_metadata_code_pk;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_idx_change_code_pk := (
  SELECT COUNT(*) FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'change'
    AND INDEX_NAME = 'idx_change_code_pk'
);
SET @sql_idx_change_code_pk := IF(
  @has_idx_change_code_pk = 0,
  'ALTER TABLE `change` ADD INDEX idx_change_code_pk (code_pk)',
  'SELECT \"idx_change_code_pk already present\"'
);
PREPARE stmt FROM @sql_idx_change_code_pk;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_idx_ascl_for_zenodo_matching_code_pk := (
  SELECT COUNT(*) FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'ascl_for_zenodo_matching'
    AND INDEX_NAME = 'idx_ascl_for_zenodo_matching_code_pk'
);
SET @sql_idx_ascl_for_zenodo_matching_code_pk := IF(
  @has_idx_ascl_for_zenodo_matching_code_pk = 0,
  'ALTER TABLE `ascl_for_zenodo_matching` ADD INDEX idx_ascl_for_zenodo_matching_code_pk (code_pk)',
  'SELECT \"idx_ascl_for_zenodo_matching_code_pk already present\"'
);
PREPARE stmt FROM @sql_idx_ascl_for_zenodo_matching_code_pk;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Add foreign keys to codes.pk (idempotent via information_schema guard)
SET @fk_ads_entries_new_code_pk_exists := (
  SELECT COUNT(*) FROM information_schema.REFERENTIAL_CONSTRAINTS
  WHERE CONSTRAINT_SCHEMA = DATABASE()
    AND CONSTRAINT_NAME = 'fk_ads_entries_new_code_pk'
    AND TABLE_NAME = 'ads_entries_new'
);
SET @sql_fk_ads_entries_new_code_pk := IF(
  @fk_ads_entries_new_code_pk_exists = 0,
  'ALTER TABLE `ads_entries_new` ADD CONSTRAINT fk_ads_entries_new_code_pk FOREIGN KEY (code_pk) REFERENCES codes(pk) ON DELETE SET NULL ON UPDATE CASCADE',
  'SELECT \"fk_ads_entries_new_code_pk already present\"'
);
PREPARE stmt FROM @sql_fk_ads_entries_new_code_pk;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @fk_link_code_pk_exists := (
  SELECT COUNT(*) FROM information_schema.REFERENTIAL_CONSTRAINTS
  WHERE CONSTRAINT_SCHEMA = DATABASE()
    AND CONSTRAINT_NAME = 'fk_link_code_pk'
    AND TABLE_NAME = 'link'
);
SET @sql_fk_link_code_pk := IF(
  @fk_link_code_pk_exists = 0,
  'ALTER TABLE `link` ADD CONSTRAINT fk_link_code_pk FOREIGN KEY (code_pk) REFERENCES codes(pk) ON DELETE SET NULL ON UPDATE CASCADE',
  'SELECT \"fk_link_code_pk already present\"'
);
PREPARE stmt FROM @sql_fk_link_code_pk;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @fk_citefile_metadata_code_pk_exists := (
  SELECT COUNT(*) FROM information_schema.REFERENTIAL_CONSTRAINTS
  WHERE CONSTRAINT_SCHEMA = DATABASE()
    AND CONSTRAINT_NAME = 'fk_citefile_metadata_code_pk'
    AND TABLE_NAME = 'citefile_metadata'
);
SET @sql_fk_citefile_metadata_code_pk := IF(
  @fk_citefile_metadata_code_pk_exists = 0,
  'ALTER TABLE `citefile_metadata` ADD CONSTRAINT fk_citefile_metadata_code_pk FOREIGN KEY (code_pk) REFERENCES codes(pk) ON DELETE SET NULL ON UPDATE CASCADE',
  'SELECT \"fk_citefile_metadata_code_pk already present\"'
);
PREPARE stmt FROM @sql_fk_citefile_metadata_code_pk;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @fk_change_code_pk_exists := (
  SELECT COUNT(*) FROM information_schema.REFERENTIAL_CONSTRAINTS
  WHERE CONSTRAINT_SCHEMA = DATABASE()
    AND CONSTRAINT_NAME = 'fk_change_code_pk'
    AND TABLE_NAME = 'change'
);
SET @sql_fk_change_code_pk := IF(
  @fk_change_code_pk_exists = 0,
  'ALTER TABLE `change` ADD CONSTRAINT fk_change_code_pk FOREIGN KEY (code_pk) REFERENCES codes(pk) ON DELETE SET NULL ON UPDATE CASCADE',
  'SELECT \"fk_change_code_pk already present\"'
);
PREPARE stmt FROM @sql_fk_change_code_pk;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @fk_ascl_for_zenodo_matching_code_pk_exists := (
  SELECT COUNT(*) FROM information_schema.REFERENTIAL_CONSTRAINTS
  WHERE CONSTRAINT_SCHEMA = DATABASE()
    AND CONSTRAINT_NAME = 'fk_ascl_for_zenodo_matching_code_pk'
    AND TABLE_NAME = 'ascl_for_zenodo_matching'
);
SET @sql_fk_ascl_for_zenodo_matching_code_pk := IF(
  @fk_ascl_for_zenodo_matching_code_pk_exists = 0,
  'ALTER TABLE `ascl_for_zenodo_matching` ADD CONSTRAINT fk_ascl_for_zenodo_matching_code_pk FOREIGN KEY (code_pk) REFERENCES codes(pk) ON DELETE SET NULL ON UPDATE CASCADE',
  'SELECT \"fk_ascl_for_zenodo_matching_code_pk already present\"'
);
PREPARE stmt FROM @sql_fk_ascl_for_zenodo_matching_code_pk;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================

-- Verify all tables are InnoDB
SELECT
    TABLE_NAME,
    ENGINE,
    TABLE_ROWS,
    ROUND(DATA_LENGTH/1024/1024, 2) AS 'Size_MB'
FROM information_schema.TABLES
WHERE TABLE_SCHEMA = 'ascl_db_v4'
ORDER BY ENGINE, TABLE_NAME;

-- Verify all tables are utf8mb4_unicode_ci
SELECT
    TABLE_NAME,
    TABLE_COLLATION,
    ENGINE
FROM information_schema.TABLES
WHERE TABLE_SCHEMA = 'ascl_db_v4'
  AND TABLE_COLLATION != 'utf8mb4_unicode_ci'
ORDER BY TABLE_NAME;
-- Should return 0 rows if successful

-- Verify all text columns are utf8mb4
SELECT
    TABLE_NAME,
    COLUMN_NAME,
    CHARACTER_SET_NAME,
    COLLATION_NAME
FROM information_schema.COLUMNS
WHERE TABLE_SCHEMA = 'ascl_db_v4'
  AND CHARACTER_SET_NAME IS NOT NULL
  AND CHARACTER_SET_NAME != 'utf8mb4'
ORDER BY TABLE_NAME, COLUMN_NAME;
-- Should return 0 rows if successful

-- Verify indexes on codes table
SELECT INDEX_NAME, COLUMN_NAME, NON_UNIQUE, INDEX_TYPE
FROM information_schema.STATISTICS
WHERE TABLE_SCHEMA = 'ascl_db_v4'
  AND TABLE_NAME = 'codes'
ORDER BY INDEX_NAME, SEQ_IN_INDEX;

-- Verify foreign keys were created
SELECT
    TABLE_NAME,
    CONSTRAINT_NAME,
    REFERENCED_TABLE_NAME,
    REFERENCED_COLUMN_NAME
FROM information_schema.KEY_COLUMN_USAGE
WHERE TABLE_SCHEMA = 'ascl_db_v4'
  AND REFERENCED_TABLE_NAME IS NOT NULL
ORDER BY TABLE_NAME, CONSTRAINT_NAME;

-- Verify unique constraints
SELECT
    TABLE_NAME,
    CONSTRAINT_NAME,
    CONSTRAINT_TYPE
FROM information_schema.TABLE_CONSTRAINTS
WHERE TABLE_SCHEMA = 'ascl_db_v4'
  AND CONSTRAINT_TYPE = 'UNIQUE'
ORDER BY TABLE_NAME;

-- Verify no zero dates remain in timestamp columns
SET @old_sql_mode_verify = @@sql_mode;
SET sql_mode = REPLACE(REPLACE(@@sql_mode,'NO_ZERO_DATE',''),'NO_ZERO_IN_DATE','');

SELECT 'codes.time_added' as column_name, COUNT(*) as zero_date_count
FROM codes WHERE time_added = '0000-00-00 00:00:00'
UNION ALL
SELECT 'codes.time_updated', COUNT(*)
FROM codes WHERE time_updated = '0000-00-00 00:00:00'
UNION ALL
SELECT 'link.updated_at', COUNT(*)
FROM link WHERE updated_at = '0000-00-00 00:00:00'
UNION ALL
SELECT 'link.last_working', COUNT(*)
FROM link WHERE last_working = '0000-00-00 00:00:00';

SET sql_mode = @old_sql_mode_verify;

-- ============================================================================
-- Step 16: Migrate all tables from ascl_id to code_pk for joins
-- ============================================================================
-- Goal: Replace varchar ascl_id foreign keys with integer pk foreign keys
-- Strategy:
--   1. Add code_pk column where it doesn't exist
--   2. Populate code_pk from ascl_id/entry_asclid lookup via codes table
--   3. Add foreign key constraint on code_pk
--   4. Drop ascl_id/entry_asclid columns (no longer needed for joins)
-- Reason: Integer PKs are faster, more efficient, and enforce proper FK relationships
-- Status: TODO

-- ----------------------------------------------------------------------------
-- 16.1: citations table - Add code_pk, populate from entry_asclid, drop entry_asclid
-- ----------------------------------------------------------------------------
ALTER TABLE citations
ADD COLUMN code_pk MEDIUMINT UNSIGNED NULL AFTER entry_asclid,
ADD INDEX idx_citations_code_pk (code_pk);

UPDATE citations c
JOIN codes co ON c.entry_asclid = co.ascl_id
SET c.code_pk = co.pk;

-- Verify mapping (should be 0)
SELECT 'citations' as table_name, COUNT(*) as unmapped_rows
FROM citations WHERE code_pk IS NULL;

ALTER TABLE citations
ADD CONSTRAINT fk_citations_code_pk
FOREIGN KEY (code_pk) REFERENCES codes(pk)
ON DELETE SET NULL ON UPDATE CASCADE;

-- Drop entry_asclid column (no longer needed - we have code_pk)
ALTER TABLE citations
DROP COLUMN entry_asclid;

-- ----------------------------------------------------------------------------
-- 16.2: ads_entries_new - Populate code_pk from ascl_id, then drop ascl_id
-- ----------------------------------------------------------------------------
UPDATE ads_entries_new a
JOIN codes co ON a.ascl_id = co.ascl_id
SET a.code_pk = co.pk;

-- Verify mapping (should be 0 or very few)
SELECT 'ads_entries_new' as table_name, COUNT(*) as unmapped_rows
FROM ads_entries_new WHERE code_pk IS NULL;

-- Drop ascl_id column (no longer needed - we have code_pk)
ALTER TABLE ads_entries_new
DROP COLUMN ascl_id;

-- ----------------------------------------------------------------------------
-- 16.3: link - Populate code_pk from ascl_id, then drop ascl_id
-- ----------------------------------------------------------------------------
UPDATE link l
JOIN codes co ON l.ascl_id = co.ascl_id
SET l.code_pk = co.pk
WHERE l.code_pk IS NULL;  -- Only update NULL values

-- Verify mapping (should be 0 or very few)
SELECT 'link' as table_name, COUNT(*) as unmapped_rows
FROM link WHERE code_pk IS NULL;

-- Drop the old unique constraint that includes ascl_id
-- Note: Constraint retains original name after table rename (links_new → link)
ALTER TABLE link
DROP INDEX uniq_links_new_asclid_url;

-- Create new unique constraint using code_pk instead
ALTER TABLE link
ADD UNIQUE KEY uniq_link_codepk_url (code_pk, url);

-- Drop ascl_id column and its index
-- Note: Index retains original name after table rename (links_new → link)
ALTER TABLE link
DROP INDEX idx_links_new_ascl_id,
DROP COLUMN ascl_id;

-- ----------------------------------------------------------------------------
-- 16.4: change table - code_pk already populated, just drop ascl_id
-- ----------------------------------------------------------------------------
-- Verify code_pk is populated (should be 0 NULLs)
SELECT 'change' as table_name, COUNT(*) as unmapped_rows
FROM `change` WHERE code_pk IS NULL;

-- Drop ascl_id index and column
ALTER TABLE `change`
DROP INDEX idx_change_ascl_id,
DROP COLUMN ascl_id;

-- ----------------------------------------------------------------------------
-- 16.5: citefile_metadata - Populate any missing code_pk, then drop ascl_id
-- ----------------------------------------------------------------------------
UPDATE citefile_metadata cm
JOIN codes co ON cm.ascl_id = co.ascl_id
SET cm.code_pk = co.pk
WHERE cm.code_pk IS NULL;

-- Verify mapping (should be 0 or very few)
SELECT 'citefile_metadata' as table_name, COUNT(*) as unmapped_rows
FROM citefile_metadata WHERE code_pk IS NULL;

-- Drop ascl_id index and column
ALTER TABLE citefile_metadata
DROP INDEX idx_citefile_ascl_id,
DROP COLUMN ascl_id;

-- ----------------------------------------------------------------------------
-- 16.6: ascl_for_zenodo_matching - Populate code_pk, drop ascl_id
-- ----------------------------------------------------------------------------
UPDATE ascl_for_zenodo_matching azm
JOIN codes co ON azm.ascl_id = co.ascl_id
SET azm.code_pk = co.pk
WHERE azm.code_pk IS NULL;

-- Verify mapping
SELECT 'ascl_for_zenodo_matching' as table_name, COUNT(*) as unmapped_rows
FROM ascl_for_zenodo_matching WHERE code_pk IS NULL;

-- Drop ascl_id index and column
ALTER TABLE ascl_for_zenodo_matching
DROP INDEX idx_ascl_for_zenodo_matching_ascl_id,
DROP COLUMN ascl_id;

-- ============================================================================
-- Step 17: Expand password column for bcrypt hashes
-- ============================================================================
-- The v3 application used SHA-1 (40 characters). Flask v4 uses bcrypt (60 characters).
-- This expands the column to support bcrypt while allowing existing SHA-1 hashes
-- to continue working until they are migrated on next login.
-- ============================================================================

ALTER TABLE users MODIFY COLUMN password VARCHAR(60) NOT NULL;

-- ============================================================================
-- Step 18: Standardize Naming Conventions (keywords, junction tables)
-- ============================================================================
-- Conventions:
--   - All primary keys named 'pk'
--   - Foreign keys named '{table}_pk' (singular)
--   - Junction tables named '{table1}_to_{table2}'
--
-- IMPORTANT: Must drop FKs BEFORE renaming columns they reference!
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 18.1: Drop existing FK constraint (required before column renames)
-- ----------------------------------------------------------------------------
-- The FK fk_code_keywords_keyword references keywords.id, which we're renaming.
-- Must drop it first, then recreate after renames.
ALTER TABLE code_keywords DROP FOREIGN KEY fk_code_keywords_keyword;

-- ----------------------------------------------------------------------------
-- 18.2: Rename keywords.id → keywords.pk
-- ----------------------------------------------------------------------------
ALTER TABLE keywords CHANGE COLUMN id pk INT UNSIGNED NOT NULL AUTO_INCREMENT;

-- ----------------------------------------------------------------------------
-- 18.3: Rename code_keywords.keyword_id → keyword_pk (before table rename)
-- ----------------------------------------------------------------------------
ALTER TABLE code_keywords CHANGE COLUMN keyword_id keyword_pk INT UNSIGNED NOT NULL;

-- ----------------------------------------------------------------------------
-- 18.4: Rename code_keywords → code_to_keyword (junction table convention)
-- ----------------------------------------------------------------------------
RENAME TABLE code_keywords TO code_to_keyword;

-- ----------------------------------------------------------------------------
-- 18.5: Recreate FK with new column/table names
-- ----------------------------------------------------------------------------
ALTER TABLE code_to_keyword
ADD CONSTRAINT fk_code_to_keyword_keyword
FOREIGN KEY (keyword_pk) REFERENCES keywords(pk)
ON DELETE CASCADE ON UPDATE CASCADE;

-- ============================================================================
-- Step 19: Rename Tables to Singular Form
-- ============================================================================
-- Convention: Table names should be singular (e.g., 'code' not 'codes')
-- This aligns with SQLAlchemy class naming and improves consistency.
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 19.1: Rename ads_entries_new → ads_entry
-- ----------------------------------------------------------------------------
RENAME TABLE ads_entries_new TO ads_entry;
ALTER TABLE ads_entry RENAME INDEX idx_ads_entries_new_code_pk TO idx_ads_entry_code_pk;

-- ----------------------------------------------------------------------------
-- 19.2: Rename code_aliases → code_alias
-- ----------------------------------------------------------------------------
RENAME TABLE code_aliases TO code_alias;
ALTER TABLE code_alias RENAME INDEX idx_code_aliases_code_id TO idx_code_alias_code_id;

-- ============================================================================
-- UPGRADE COMPLETE
-- ============================================================================
-- Database: ascl_db_v4
-- Status: Ready for testing with Flask application
--
-- Next Steps:
--   1. Update connection configuration to point to ascl_db_v4
--   2. Test Flask application with upgraded database
--   3. Run application test suite
--   4. Verify all features work correctly
--   5. Plan production cutover
-- ============================================================================
