-- Update link_type table schema for v4
-- v3 schema: pk, label
-- v4 schema: pk, short_name, name

SET SESSION sql_mode = '';

-- Add short_name column and rename label to name
ALTER TABLE link_type
    ADD COLUMN short_name VARCHAR(32) NOT NULL AFTER pk,
    CHANGE COLUMN label name VARCHAR(255) NOT NULL;

-- Populate short_name from name (lowercase, spaces to dashes)
UPDATE link_type SET short_name = LOWER(REPLACE(name, ' ', '-'));

-- Add unique index on short_name
ALTER TABLE link_type ADD UNIQUE INDEX idx_short_name (short_name);

-- Add description column
ALTER TABLE link_type ADD COLUMN description VARCHAR(255) NULL AFTER name;

-- Rename 'reference' to 'refereed' (v4 terminology)
UPDATE link_type SET short_name = 'refereed', name = 'Refereed' WHERE short_name = 'reference';

-- Fix collation to match other tables
ALTER TABLE link_type CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
