## ASCL_DB Upgrade



### Add Primary Keys to Tables That Don’t Have Them

`````
ascl_for_zenodo_matching
ascl_for_zenodo_matching2
ascl_for_zenodo_matching_two
code_keywords
`````

```sql
-- ascl_for_zenodo_matching
ALTER TABLE ascl_for_zenodo_matching
    ADD COLUMN id INT AUTO_INCREMENT PRIMARY KEY FIRST;
    
-- ascl_for_zenodo_matching2
ALTER TABLE ascl_for_zenodo_matching2
    ADD COLUMN id INT AUTO_INCREMENT PRIMARY KEY FIRST;

-- ascl_for_zenodo_matching_two
ALTER TABLE ascl_for_zenodo_matching_two
    ADD COLUMN id INT AUTO_INCREMENT PRIMARY KEY FIRST;


-- code_keywords
ALTER TABLE code_keywords DROP INDEX code_keyword_unique;
ALTER TABLE code_keywords
   ADD PRIMARY KEY (code_id, keyword_id);
```



### FULLTEXT Indexes

```code_aliases	alias
codes	abstract
codes	credit
codes	title
codes_backup2	abstract
codes_backup2	credit
codes_backup2	title
code_aliases alias
```









### Engine Upgrade

Before tables can be upgraded to the InnoDB engine, these changes need to be made:

```sql
-- save the current mode
SET @old_sql_mode = @@sql_mode;

-- drop NO_ZERO_DATE and NO_ZERO_IN_DATE for this session
SET sql_mode = REPLACE(REPLACE(@@sql_mode,'NO_ZERO_DATE',''),'NO_ZERO_IN_DATE','');

-- codes
-- change to accept NULL values
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

-- codes_backup_2
ALTER TABLE `codes_backup2`
  MODIFY `time_added` TIMESTAMP NULL,
  MODIFY `time_updated` TIMESTAMP NULL;

UPDATE `codes_backup2`
  SET `time_added` = NULL
  WHERE `time_added` = '0000-00-00 00:00:00';

UPDATE `codes_backup2`
  SET `time_updated` = NULL
  WHERE `time_updated` = '0000-00-00 00:00:00';
  
ALTER TABLE `codes_backup2`
  MODIFY `time_added` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  MODIFY `time_updated` TIMESTAMP NULL DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP;

-- links
ALTER TABLE `links`
  MODIFY `created_at` TIMESTAMP NULL,
  MODIFY `updated_at` TIMESTAMP NULL;

UPDATE `links`
  SET `updated_at` = NULL
  WHERE `updated_at` = '0000-00-00 00:00:00';

ALTER TABLE `links`
  MODIFY `created_at` TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
  MODIFY `updated_at` TIMESTAMP NULL DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP,
  MODIFY `last_working` DATETIME NULL DEFAULT NULL;
    
-- links_new
ALTER TABLE `links_new`
  MODIFY `created_at` TIMESTAMP NULL,
  MODIFY `updated_at` TIMESTAMP NULL;

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
    
-- put the mode back
SET sql_mode = @old_sql_mode;
```

Tables to upgrade:

```sql
ALTER TABLE `ads_entries` ENGINE = InnoDB;
ALTER TABLE `ads_entries_new` ENGINE = InnoDB;
ALTER TABLE `change` ENGINE = InnoDB;
ALTER TABLE `citations` ENGINE = InnoDB;
ALTER TABLE `citations_new` ENGINE = InnoDB;
ALTER TABLE `citefile_metadata` ENGINE = InnoDB;
ALTER TABLE `ci_sessions` ENGINE = InnoDB;
ALTER TABLE `classic_citations` ENGINE = InnoDB;
ALTER TABLE `codes` ENGINE = InnoDB;
ALTER TABLE `codes_backup2` ENGINE = InnoDB;
ALTER TABLE `code_aliases` ENGINE = InnoDB;
ALTER TABLE `code_keywords` ENGINE = InnoDB;
ALTER TABLE `keywords` ENGINE = InnoDB;
ALTER TABLE `links` ENGINE = InnoDB;
ALTER TABLE `links_new` ENGINE = InnoDB;
ALTER TABLE `temp` ENGINE = InnoDB;
ALTER TABLE `users` ENGINE = InnoDB;
```

## Indexes on `ascl_id`

```sql
ALTER TABLE codes
  ADD UNIQUE KEY uq_codes_ascl_id (ascl_id);

ALTER TABLE codes_backup2
  ADD UNIQUE KEY uq_codes_backup2_ascl_id (ascl_id);

ALTER TABLE ads_entries
  ADD KEY idx_ads_entries_ascl_id (ascl_id);

ALTER TABLE ads_entries_new
  ADD KEY idx_ads_entries_new_ascl_id (ascl_id);

ALTER TABLE ascl_for_zenodo_matching
  ADD KEY idx_ascl_for_zenodo_matching_ascl_id (ascl_id);

ALTER TABLE ascl_for_zenodo_matching2
  ADD KEY idx_ascl_for_zenodo_matching2_ascl_id (ascl_id);

ALTER TABLE ascl_for_zenodo_matching_two
  ADD KEY idx_ascl_for_zenodo_matching_two_ascl_id (ascl_id);

ALTER TABLE citefile_metadata
  ADD KEY idx_citefile_ascl_id (ascl_id);

ALTER TABLE links
  ADD KEY idx_links_ascl_id (ascl_id);

ALTER TABLE links_new
  ADD KEY idx_links_new_ascl_id (ascl_id);

ALTER TABLE `change`
  ADD KEY idx_change_ascl_id (ascl_id);
```



## Other Indexes

```sql
ALTER TABLE citations
  ADD KEY idx_citations_entry_asclid (entry_asclid),
  ADD KEY idx_citations_entry_year (entry_asclid, year);

ALTER TABLE citations_new
  ADD KEY idx_citations_new_entry_asclid (entry_asclid),
  ADD KEY idx_citations_new_entry_year (entry_asclid, year);
  
ALTER TABLE links
  ADD KEY idx_links_url (url),
  ADD KEY idx_links_ascl_working (ascl_id, is_working);
  
ALTER TABLE code_aliases
  ADD KEY idx_code_aliases_code_id (code_id);
```



## Constraints

```sql
-- links_new
ALTER TABLE `links_new`
  ADD UNIQUE KEY `uniq_links_new_asclid_url` (`ascl_id`, `url`);
```







## Foreign Keys

**Design Notes:**
- Foreign keys reference `codes.id` (PRIMARY KEY), not `codes.ascl_id`
- Reason: `ascl_id` is not unique (604 unpublished codes have ascl_id='0000.000')
- All orphan checks passed: 0 orphaned records found in all tables
- Safe to add FKs with RESTRICT to prevent deletion of referenced codes

```sql
-- ============================================================================
-- Foreign Key Constraints
-- ============================================================================

-- ----------------------------------------------------------------------------
-- code_aliases: References codes table
-- ----------------------------------------------------------------------------
-- Each alias must belong to a valid code
-- Composite PK: (code_id, alias)
-- ON DELETE RESTRICT: Cannot delete a code that has aliases
-- ON UPDATE CASCADE: If code.id changes, update alias references
-- ----------------------------------------------------------------------------
ALTER TABLE `code_aliases`
  ADD CONSTRAINT `fk_code_aliases_code`
    FOREIGN KEY (`code_id`)
    REFERENCES `codes` (`id`)
    ON DELETE RESTRICT
    ON UPDATE CASCADE;

-- ----------------------------------------------------------------------------
-- code_keywords: References both codes and keywords tables (Many-to-Many)
-- ----------------------------------------------------------------------------
-- Links codes to keywords (junction table)
-- Composite PK: (code_id, keyword_id)
-- ON DELETE CASCADE: If code or keyword deleted, remove the link
-- ----------------------------------------------------------------------------
ALTER TABLE `code_keywords`
  ADD CONSTRAINT `fk_code_keywords_code`
    FOREIGN KEY (`code_id`)
    REFERENCES `codes` (`id`)
    ON DELETE CASCADE
    ON UPDATE CASCADE;

ALTER TABLE `code_keywords`
  ADD CONSTRAINT `fk_code_keywords_keyword`
    FOREIGN KEY (`keyword_id`)
    REFERENCES `keywords` (`id`)
    ON DELETE CASCADE
    ON UPDATE CASCADE;

-- ----------------------------------------------------------------------------
-- Note: The following tables reference ascl_id (STRING), not codes.id
-- Cannot create FK to ascl_id because it's not unique (0000.000 used for unpublished)
-- Options:
--   1. Add FK after making ascl_id unique (requires handling unpublished codes)
--   2. Keep as application-enforced referential integrity
--   3. Create a unique index on ascl_id WHERE ascl_id != '0000.000'
--
-- For now: Document but do NOT create these FKs
-- ----------------------------------------------------------------------------

-- citations table: entry_asclid -> codes.ascl_id
-- Cannot add FK: ascl_id is not unique in codes table

-- ads_entries_new table: ascl_id -> codes.ascl_id
-- Cannot add FK: ascl_id is not unique in codes table

-- links_new table: ascl_id -> codes.ascl_id
-- Cannot add FK: ascl_id is not unique in codes table

-- change table: ascl_id -> codes.ascl_id
-- Cannot add FK: ascl_id is not unique in codes table

-- citefile_metadata table: ascl_id -> codes.ascl_id
-- Cannot add FK: ascl_id is not unique in codes table

-- ============================================================================
-- Future Enhancement: Making ascl_id Unique
-- ============================================================================
-- To enable FK constraints on ascl_id, consider:
--
-- Option 1: Set NULL for unpublished codes
-- UPDATE codes SET ascl_id = NULL WHERE ascl_id = '0000.000';
-- ALTER TABLE codes MODIFY ascl_id VARCHAR(8) NULL;
-- ALTER TABLE codes ADD UNIQUE KEY uq_codes_ascl_id_notnull (ascl_id);
--
-- Option 2: Use a different placeholder value per unpublished code
-- UPDATE codes SET ascl_id = CONCAT('UNPUB-', id) WHERE ascl_id = '0000.000';
-- ALTER TABLE codes ADD UNIQUE KEY uq_codes_ascl_id (ascl_id);
--
-- Option 3: Keep ascl_id='0000.000' and enforce integrity at application level
-- (Current approach - no schema changes needed)
-- ============================================================================
```

