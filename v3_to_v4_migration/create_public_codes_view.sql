-- =============================================================================
-- create_public_codes_view.sql
-- =============================================================================
-- Creates a view for publicly visible codes: published, not archived,
-- and not the placeholder ascl_id '0000.000' (submitted but unassigned).
--
-- This view centralizes the filtering logic used by browse, discovery,
-- search, and export queries. If the criteria for "public" ever change,
-- update this view rather than every individual query.
-- =============================================================================

CREATE OR REPLACE VIEW public_codes AS
SELECT * FROM codes
WHERE published = 1
  AND archived = 0
  AND ascl_id != '0000.000';
