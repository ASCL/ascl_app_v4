-- =============================================================================
-- seed_mission_keywords.sql
-- =============================================================================
-- Adds mission/survey keywords that are not present in the v3 keyword table.
-- These are used by the discovery bar to show mission-related pills.
--
-- Uses INSERT IGNORE so re-running is safe (won't duplicate existing entries).
-- =============================================================================

INSERT IGNORE INTO keyword (short_name, label) VALUES
  ('gaia', 'Gaia'),
  ('2mass', 'Two Micron All Sky Survey (2MASS)'),
  ('sdss', 'Sloan Digital Sky Survey (SDSS)');
