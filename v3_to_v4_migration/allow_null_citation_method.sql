-- Allow citation_method to be NULL (empty values should be NULL, not empty strings)
SET SESSION sql_mode = '';
ALTER TABLE codes MODIFY COLUMN citation_method varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL;
UPDATE codes SET citation_method = NULL WHERE citation_method = '';
