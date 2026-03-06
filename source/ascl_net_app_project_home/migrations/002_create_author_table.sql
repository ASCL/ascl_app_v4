-- Migration: Move codes.credit data into a normalized author table
-- Date: 2026-02-03
--
-- Notes:
-- 1) This migration creates table `author`.
-- 2) It backfills rows from `codes.credit` (semicolon-delimited names).
-- 3) It DOES NOT drop `codes.credit` yet; keep it during app transition.

CREATE TABLE IF NOT EXISTS author (
    pk INT NOT NULL AUTO_INCREMENT,
    code_pk INT NOT NULL,
    raw_name TEXT NOT NULL COMMENT 'Original author token (unparsed) from credit string',
    display_name VARCHAR(255) NULL COMMENT 'Preferred display name (can be normalized later)',
    raw_credit_text TEXT NULL COMMENT 'Original full, unparsed codes.credit string',
    orcid_id VARCHAR(19) NULL COMMENT 'ORCID iD format: 0000-0000-0000-0000',
    email VARCHAR(255) NULL,
    display_order INT NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (pk),
    KEY idx_author_code_pk (code_pk),
    KEY idx_author_display_name (display_name),
    KEY idx_author_orcid_id (orcid_id),
    UNIQUE KEY uq_author_code_order (code_pk, display_order),
    CONSTRAINT fk_author_code_pk
        FOREIGN KEY (code_pk) REFERENCES codes(pk)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Backfill from codes.credit if author table is currently empty.
-- Split on ';' and preserve list order into display_order.
WITH RECURSIVE seq AS (
    SELECT 1 AS n
    UNION ALL
    SELECT n + 1 FROM seq WHERE n < 64
),
split_credit AS (
    SELECT
        c.pk AS code_pk,
        c.credit AS raw_credit_text,
        seq.n AS part_num,
        TRIM(SUBSTRING_INDEX(SUBSTRING_INDEX(c.credit, ';', seq.n), ';', -1)) AS raw_name
    FROM codes c
    JOIN seq
      ON seq.n <= 1 + (LENGTH(c.credit) - LENGTH(REPLACE(c.credit, ';', '')))
    WHERE c.credit IS NOT NULL
      AND TRIM(c.credit) <> ''
)
INSERT INTO author (code_pk, raw_name, display_name, raw_credit_text, display_order)
SELECT
    sc.code_pk,
    sc.raw_name,
    sc.raw_name,
    sc.raw_credit_text,
    sc.part_num - 1 AS display_order
FROM split_credit sc
WHERE sc.raw_name <> ''
  AND NOT EXISTS (
      SELECT 1
      FROM author a
      WHERE a.code_pk = sc.code_pk
        AND a.display_order = sc.part_num - 1
  );
