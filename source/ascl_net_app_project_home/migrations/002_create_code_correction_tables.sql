-- Migration 002: Create code_correction tables for user-submitted corrections
-- Replaces the old phpBB-based correction system
--
-- Run against ascl_db_v4:
--   mysql --defaults-group-suffix=_ascl_root -h 127.0.0.1 -P 3307 ascl_db_v4 < 002_create_code_correction_tables.sql

CREATE TABLE IF NOT EXISTS code_correction (
    pk              INT AUTO_INCREMENT PRIMARY KEY,
    code_pk         INT NOT NULL,
    -- Proposed changes to scalar fields (NULL = no change proposed)
    title           VARCHAR(255) NULL,
    credit          TEXT NULL,
    abstract        TEXT NULL,
    citation_method VARCHAR(255) NULL,
    -- Submitter info
    submitter_email VARCHAR(255) NOT NULL,
    submitter_name  VARCHAR(255) NULL,
    submitter_notes TEXT NULL,
    -- Review workflow
    status          ENUM('pending', 'applied', 'rejected') NOT NULL DEFAULT 'pending',
    submitted_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    reviewed_at     TIMESTAMP NULL,
    reviewed_by     INT NULL,
    reviewer_notes  TEXT NULL,
    --
    FOREIGN KEY (code_pk) REFERENCES codes(pk) ON DELETE CASCADE,
    FOREIGN KEY (reviewed_by) REFERENCES users(pk) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='User-submitted corrections to code entries';


CREATE TABLE IF NOT EXISTS code_correction_link (
    pk              INT AUTO_INCREMENT PRIMARY KEY,
    correction_pk   INT NOT NULL,
    link_type_pk    INT NOT NULL,
    -- The full set of proposed URLs for this link type (newline-separated)
    urls            TEXT NOT NULL,
    --
    FOREIGN KEY (correction_pk) REFERENCES code_correction(pk) ON DELETE CASCADE,
    FOREIGN KEY (link_type_pk) REFERENCES link_type(pk) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Proposed link changes per correction, one row per link type';
