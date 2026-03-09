-- Rename primary key columns from 'id' to 'pk' for v4 schema
-- Also rename tables and foreign key columns for v4 consistency

SET SESSION sql_mode = '';

-- Drop legacy/temporary tables (superseded by *_new versions)
DROP TABLE IF EXISTS links;
DROP TABLE IF EXISTS ads_entries;

-- Rename *_new tables to canonical names
RENAME TABLE links_new TO links;
RENAME TABLE ads_entries_new TO ads_entries;

-- Main tables: rename id -> pk
ALTER TABLE codes CHANGE COLUMN id pk INT AUTO_INCREMENT;
ALTER TABLE keywords CHANGE COLUMN id pk INT AUTO_INCREMENT;
ALTER TABLE users CHANGE COLUMN id pk INT AUTO_INCREMENT;
ALTER TABLE citations CHANGE COLUMN id pk INT AUTO_INCREMENT;
ALTER TABLE ads_entries CHANGE COLUMN id pk INT AUTO_INCREMENT;
ALTER TABLE links CHANGE COLUMN id pk INT AUTO_INCREMENT;
ALTER TABLE `change` CHANGE COLUMN id pk INT AUTO_INCREMENT;
ALTER TABLE citefile_metadata CHANGE COLUMN id pk INT AUTO_INCREMENT;

-- code_aliases has composite PK (alias, code_id), no id column
-- Just rename the FK column
ALTER TABLE code_aliases CHANGE COLUMN code_id code_pk INT;

-- code_keywords FK columns
ALTER TABLE code_keywords CHANGE COLUMN code_id code_pk INT;
ALTER TABLE code_keywords CHANGE COLUMN keyword_id keyword_pk INT;

-- Rename tables to v4 naming convention
RENAME TABLE code_keywords TO code_to_keyword;
RENAME TABLE code_aliases TO code_alias;
RENAME TABLE links TO link;
RENAME TABLE ads_entries TO ads_entry;
RENAME TABLE keywords TO keyword;

-- Delete link-checker rows from v3 links_new. These rows (link_type_pk IS NULL)
-- were populated by the external link_checker.py script for health monitoring and
-- are not canonical link data. Only EMAC rows (link_type_pk = 1) are real links;
-- all other links come from the PHP-serialized codes fields (site_list, ref_list,
-- described_in, used_in) which are migrated by migrate_serialized_to_links.py.
DELETE FROM link WHERE link_type_pk IS NULL;

-- Rename keyword.keyword column to label and add short_name
ALTER TABLE keyword CHANGE COLUMN keyword label VARCHAR(64) NOT NULL;
ALTER TABLE keyword ADD COLUMN short_name VARCHAR(64) NULL AFTER pk;

-- Populate short_name from label (lowercase, spaces to dashes)
UPDATE keyword SET short_name = LOWER(REPLACE(label, ' ', '-'));

-- Make short_name NOT NULL after population
ALTER TABLE keyword MODIFY COLUMN short_name VARCHAR(64) NOT NULL;

-- Add unique index on short_name
ALTER TABLE keyword ADD UNIQUE INDEX idx_keyword_short_name (short_name);

-- Drop redundant codes.keywords PHP serialized column
ALTER TABLE codes DROP COLUMN keywords;

-- Add code_pk and display_order columns to link table
-- (link_type_pk already exists from links_new)
ALTER TABLE link ADD COLUMN code_pk INT NULL AFTER pk;
ALTER TABLE link ADD COLUMN display_order INT NOT NULL DEFAULT 0 AFTER link_type_pk;

-- Fix NULLs in link.message before making NOT NULL
UPDATE link SET message = '' WHERE message IS NULL;

-- Adjust columns for Python migration inserts
ALTER TABLE link MODIFY COLUMN message VARCHAR(255) NOT NULL DEFAULT '';
ALTER TABLE link MODIFY COLUMN ascl_id VARCHAR(8) NULL;
-- Fix timestamp defaults; remove erroneous ON UPDATE from created_at (v3 links_new quirk)
ALTER TABLE link MODIFY COLUMN created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE link MODIFY COLUMN updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP;
ALTER TABLE link MODIFY COLUMN last_working DATETIME NOT NULL DEFAULT '1970-01-01 00:00:01';
ALTER TABLE citations ADD COLUMN code_pk INT NULL AFTER pk;
ALTER TABLE ads_entry ADD COLUMN code_pk INT NULL AFTER pk;
ALTER TABLE citefile_metadata ADD COLUMN code_pk INT NULL AFTER pk;
ALTER TABLE `change` ADD COLUMN code_pk INT NULL AFTER pk;

-- Populate code_pk from ascl_id
UPDATE link l JOIN codes c ON l.ascl_id = c.ascl_id SET l.code_pk = c.pk;
UPDATE citations ct JOIN codes c ON ct.entry_asclid = c.ascl_id SET ct.code_pk = c.pk;
UPDATE ads_entry ae JOIN codes c ON ae.ascl_id = c.ascl_id SET ae.code_pk = c.pk;
UPDATE citefile_metadata cf JOIN codes c ON cf.ascl_id = c.ascl_id SET cf.code_pk = c.pk;
UPDATE `change` ch JOIN codes c ON ch.ascl_id = c.ascl_id SET ch.code_pk = c.pk;

-- Drop redundant ascl_id columns (now using code_pk FK)
ALTER TABLE link DROP COLUMN ascl_id;
ALTER TABLE citations DROP COLUMN entry_asclid;
ALTER TABLE ads_entry DROP COLUMN ascl_id;
ALTER TABLE citefile_metadata DROP COLUMN ascl_id;
ALTER TABLE `change` DROP COLUMN ascl_id;

-- Drop legacy/backup tables
DROP TABLE IF EXISTS citations_new;
DROP TABLE IF EXISTS classic_citations;
DROP TABLE IF EXISTS codes_backup2;
DROP TABLE IF EXISTS ascl_for_zenodo_matching;
DROP TABLE IF EXISTS ascl_for_zenodo_matching2;
DROP TABLE IF EXISTS ascl_for_zenodo_matching_two;

-- Extend password column for bcrypt hashes (60 chars)
ALTER TABLE users MODIFY COLUMN password VARCHAR(60) NOT NULL;

-- Fix zero dates in codes table
UPDATE codes SET time_updated = time_added WHERE time_updated = '0000-00-00 00:00:00';
UPDATE codes SET time_updated = '1970-01-01 00:00:01' WHERE time_updated = '0000-00-00 00:00:00';
UPDATE codes SET time_added = '1970-01-01 00:00:01' WHERE time_added = '0000-00-00 00:00:00';

-- Clean up DOI values: remove "doi:" or "DOI:" prefix (correct format is just "10.XXXX/YYYY")
UPDATE codes SET doi = SUBSTRING(doi, 5) WHERE doi REGEXP '^[dD][oO][iI]:';

-- Fix zero dates in link table
UPDATE link SET updated_at = '1970-01-01 00:00:01' WHERE updated_at < '1970-01-01';
UPDATE link SET created_at = '1970-01-01 00:00:01' WHERE created_at < '1970-01-01';
UPDATE link SET last_working = '1970-01-01 00:00:01' WHERE last_working < '1970-01-01';

-- Add foreign key constraints
ALTER TABLE code_alias ADD CONSTRAINT fk_code_alias_code FOREIGN KEY (code_pk) REFERENCES codes(pk) ON DELETE CASCADE;
ALTER TABLE code_to_keyword ADD CONSTRAINT fk_code_to_keyword_code FOREIGN KEY (code_pk) REFERENCES codes(pk) ON DELETE CASCADE;
ALTER TABLE code_to_keyword ADD CONSTRAINT fk_code_to_keyword_keyword FOREIGN KEY (keyword_pk) REFERENCES keyword(pk) ON DELETE CASCADE;
ALTER TABLE ads_entry ADD CONSTRAINT fk_ads_entry_code FOREIGN KEY (code_pk) REFERENCES codes(pk) ON DELETE CASCADE;
ALTER TABLE link ADD CONSTRAINT fk_link_code FOREIGN KEY (code_pk) REFERENCES codes(pk) ON DELETE CASCADE;
ALTER TABLE citefile_metadata ADD CONSTRAINT fk_citefile_metadata_code FOREIGN KEY (code_pk) REFERENCES codes(pk) ON DELETE CASCADE;
ALTER TABLE `change` ADD CONSTRAINT fk_change_code FOREIGN KEY (code_pk) REFERENCES codes(pk) ON DELETE CASCADE;
ALTER TABLE citations ADD CONSTRAINT fk_citations_code FOREIGN KEY (code_pk) REFERENCES codes(pk) ON DELETE CASCADE;

-- Add performance indexes
CREATE INDEX idx_codes_ascl_id ON codes(ascl_id);
CREATE INDEX idx_ads_entry_code_pk ON ads_entry(code_pk);
CREATE INDEX idx_link_code_pk ON link(code_pk);
CREATE INDEX idx_citefile_metadata_code_pk ON citefile_metadata(code_pk);
CREATE INDEX idx_change_code_pk ON `change`(code_pk);
CREATE INDEX idx_code_alias_code_pk ON code_alias(code_pk);

-- Add unique constraint on link(code_pk, url, link_type_pk) to allow same URL with different link types
ALTER TABLE link ADD UNIQUE INDEX idx_link_code_url_type (code_pk, url, link_type_pk);
