-- Drop PHP-serialized columns from codes table after migration to normalized tables
-- These columns have been migrated to the link table via migrate_serialized_to_links.py

SET SESSION sql_mode = '';

-- Drop the PHP serialized array columns (data now in link table)
ALTER TABLE codes DROP COLUMN site_list;
ALTER TABLE codes DROP COLUMN ref_list;
ALTER TABLE codes DROP COLUMN described_in;
ALTER TABLE codes DROP COLUMN used_in;
ALTER TABLE codes DROP COLUMN see_also;
