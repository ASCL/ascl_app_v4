-- Migration 004: Create link_check table
-- Stores per-link check metadata for the link checker.
-- One row per link (upserted on each check run).

CREATE TABLE IF NOT EXISTS link_check (
    pk              INT AUTO_INCREMENT PRIMARY KEY,
    link_pk         INT          NOT NULL,

    -- Latest check results (updated every check)
    http_status     INT          NULL COMMENT 'HTTP code; 0=timeout, -1=SSL error, -2=other error',
    message         VARCHAR(255) NOT NULL DEFAULT '',
    is_working      TINYINT(1)   NOT NULL DEFAULT 0,
    final_url       VARCHAR(2048) NULL COMMENT 'URL after following redirects',
    page_title      VARCHAR(512) NULL COMMENT 'Current <title> from response',
    domain_changed  TINYINT(1)   NOT NULL DEFAULT 0 COMMENT 'True if final_url domain != original link.url domain',
    checked_at      DATETIME     NOT NULL,
    fail_count      INT          NOT NULL DEFAULT 0 COMMENT 'Consecutive failures; reset to 0 on success',
    note            VARCHAR(255) NULL COMMENT 'Pattern-matched observation, e.g. "Repository archived"',

    -- Baseline: auto-set on first success, only updated when is_working=1
    last_working    DATETIME     NULL COMMENT 'When link was last confirmed working',
    title_ok        VARCHAR(512) NULL COMMENT 'Page title from last successful check',
    final_url_ok    VARCHAR(2048) NULL COMMENT 'Final URL from last successful check',

    UNIQUE KEY idx_link_check_link_pk (link_pk),
    CONSTRAINT fk_link_check_link
        FOREIGN KEY (link_pk) REFERENCES link(pk) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
