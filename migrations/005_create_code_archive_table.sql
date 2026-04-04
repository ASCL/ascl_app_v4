-- =============================================================================
-- 005_create_code_archive_table.sql
-- =============================================================================
-- Tracks the archival status of each ASCL code in the icecave.
--
-- archive_type:
--   'git'      — cloned as a bare git mirror (GitHub, GitLab, Bitbucket, etc.)
--   'download' — downloadable archive (tarball, zip, etc.)
--   'webonly'  — only available as a web page (department sites, etc.)
--
-- status:
--   'pending'  — not yet archived, awaiting initial clone/download
--   'active'   — archived and being updated
--   'stale'    — source URL appears dead or unchanged for a long time
--   'error'    — last sync attempt failed
--   'missing'  — no code-site URL available
-- =============================================================================

SET SESSION sql_mode = '';

CREATE TABLE IF NOT EXISTS code_archive (
    pk              INT AUTO_INCREMENT PRIMARY KEY,
    code_pk         INT NOT NULL,
    archive_type    ENUM('git', 'download', 'webonly') NOT NULL,
    source_url      VARCHAR(500) NOT NULL COMMENT 'URL used for cloning or downloading',
    dir_name        VARCHAR(200) NOT NULL COMMENT 'Directory name under /codes/ (e.g. emcee-2010.001)',
    last_checked    DATETIME DEFAULT NULL COMMENT 'Last time sync was attempted',
    last_updated    DATETIME DEFAULT NULL COMMENT 'Last time new content was found',
    last_wayback    DATETIME DEFAULT NULL COMMENT 'Most recent archive.org capture',
    wayback_url     VARCHAR(500) DEFAULT NULL,
    size_bytes      BIGINT DEFAULT NULL,
    status          ENUM('pending', 'active', 'stale', 'error', 'missing') NOT NULL DEFAULT 'pending',
    error_message   TEXT DEFAULT NULL,
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_code_archive_code (code_pk),
    CONSTRAINT fk_code_archive_code FOREIGN KEY (code_pk) REFERENCES codes(pk)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
