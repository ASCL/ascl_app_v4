-- Migration: Create author, orcid_provenance, and code_to_author tables
-- Normalizes the semicolon-delimited codes.credit field into individual author rows
-- with a many-to-many relationship to codes via code_to_author.
--
-- Run with: mysql -u user -p ascl_db < create_author_table.sql

SET SESSION sql_mode = '';

-- Create orcid_provenance lookup table
CREATE TABLE IF NOT EXISTS orcid_provenance (
    pk SMALLINT AUTO_INCREMENT PRIMARY KEY,
    short_name VARCHAR(32) NOT NULL UNIQUE COMMENT 'Internal identifier (e.g. orcid-api, user-submitted, ads)',
    label VARCHAR(64) NOT NULL COMMENT 'Display name'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='How the ORCID was obtained or verified';

-- Populate initial provenance types
INSERT INTO orcid_provenance (short_name, label) VALUES
    ('user-submitted', 'User Submitted'),
    ('orcid-api', 'ORCID API'),
    ('ads', 'ADS Import'),
    ('open-alex', 'OpenAlex');

-- Create author table
CREATE TABLE IF NOT EXISTS author (
    pk INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(512) NOT NULL COMMENT 'Author name as displayed (original from credit field)',
    given VARCHAR(128) NULL COMMENT 'Given (first) name, parsed via nameparser',
    middle VARCHAR(128) NULL COMMENT 'Middle name(s), parsed via nameparser',
    family VARCHAR(128) NULL COMMENT 'Family (last) name, parsed via nameparser',
    orcid VARCHAR(19) NULL COMMENT 'ORCID iD (format: 0000-0000-0000-000X)',
    orcid_provenance_pk SMALLINT NULL COMMENT 'FK to orcid_provenance table',

    -- Indexes
    INDEX idx_author_orcid (orcid),
    INDEX idx_author_name (name),
    INDEX idx_author_family (family),

    -- Foreign keys
    CONSTRAINT fk_author_orcid_provenance FOREIGN KEY (orcid_provenance_pk) REFERENCES orcid_provenance(pk) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Individual authors (normalized from codes.credit)';

-- Create code_to_author many-to-many join table
CREATE TABLE IF NOT EXISTS code_to_author (
    pk INT AUTO_INCREMENT PRIMARY KEY,
    code_pk INT NOT NULL COMMENT 'FK to codes table',
    author_pk INT NOT NULL COMMENT 'FK to author table',
    display_order INT NOT NULL DEFAULT 0 COMMENT 'Position in author list for this code',

    -- Indexes
    INDEX idx_code_to_author_code_pk (code_pk),
    INDEX idx_code_to_author_author_pk (author_pk),
    INDEX idx_code_to_author_order (code_pk, display_order),
    UNIQUE INDEX idx_code_to_author_unique (code_pk, author_pk),

    -- Foreign keys
    CONSTRAINT fk_code_to_author_code FOREIGN KEY (code_pk) REFERENCES codes(pk) ON DELETE CASCADE,
    CONSTRAINT fk_code_to_author_author FOREIGN KEY (author_pk) REFERENCES author(pk) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Many-to-many relationship between codes and authors';
