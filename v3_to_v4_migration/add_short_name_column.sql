-- =============================================================================
-- add_short_name_column.sql
-- =============================================================================
-- Add short_name column to codes table and populate from GitHub repo names.
--
-- The short_name is used for directory naming in the ASCL archive (ascl-cave).
-- GitHub-hosted codes get their repo name; remaining codes need manual or
-- AI-assisted population.
-- =============================================================================

SET SESSION sql_mode = '';

-- Add the column
ALTER TABLE codes ADD COLUMN short_name VARCHAR(100) DEFAULT NULL AFTER title;

-- Populate from GitHub repo URLs (link_type_pk=2 is 'code-site')
-- Extracts the repo name (last path component of github.com/owner/repo)
UPDATE codes c
JOIN (
    SELECT code_pk,
           LOWER(SUBSTRING_INDEX(
               SUBSTRING_INDEX(
                   REPLACE(REPLACE(url, 'https://github.com/', ''), 'http://github.com/', ''),
                   '/', 2),
               '/', -1)
           ) AS repo_name
    FROM link
    WHERE link_type_pk = 2
      AND (url LIKE 'https://github.com/%/%' OR url LIKE 'http://github.com/%/%')
    GROUP BY code_pk
) g ON g.code_pk = c.pk
SET c.short_name = g.repo_name;

-- Report results
SELECT
    COUNT(*) AS total_codes,
    SUM(short_name IS NOT NULL) AS populated,
    SUM(short_name IS NULL) AS remaining
FROM codes
WHERE published = 1 AND ascl_id != '0000.000';
