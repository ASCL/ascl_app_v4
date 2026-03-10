-- Migration: Create code_note table for tracking note history
-- This replaces the single 'notes' field on codes with a full history table
--
-- Run with: mysql -u user -p database < create_code_note_table.sql

SET SESSION sql_mode = '';

-- Create note_type lookup table
CREATE TABLE IF NOT EXISTS note_type (
    pk INT AUTO_INCREMENT PRIMARY KEY,
    short_name VARCHAR(32) NOT NULL UNIQUE COMMENT 'Internal identifier',
    name VARCHAR(64) NOT NULL COMMENT 'Display name',
    description VARCHAR(255) NULL COMMENT 'Optional description of when to use this type',
    display_order INT DEFAULT 0 COMMENT 'Order in dropdown menus'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Lookup table for note types';

-- Populate note types
INSERT INTO note_type (short_name, name, description, display_order) VALUES
    ('legacy', 'Legacy', 'Notes migrated from v3', 0),
    ('general', 'General', 'General notes', 1),
    ('review', 'Review', 'Code review notes', 2),
    ('followup', 'Follow-up', 'Follow-up items / action needed', 3),
    ('attention', 'Needs Attention', 'Requires admin attention', 4),
    ('submission', 'Submission', 'Notes from original submission', 5),
    ('update', 'Update', 'Notes about updates to the code', 6),
    ('internal', 'Internal', 'Internal admin notes', 7);

-- Create code_note table
CREATE TABLE IF NOT EXISTS code_note (
    pk INT AUTO_INCREMENT PRIMARY KEY,
    code_pk INT NOT NULL COMMENT 'FK to codes table',
    correction_pk INT NULL COMMENT 'FK to code_correction (if note is about a specific correction)',
    user_pk INT NULL COMMENT 'FK to users table (who created the note)',
    note_type_pk INT NOT NULL COMMENT 'FK to note_type table',
    note TEXT NOT NULL COMMENT 'The note content',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT 'When the note was created',
    is_pinned TINYINT(1) DEFAULT 0 COMMENT 'Pin important notes to top',
    hidden TINYINT(1) DEFAULT 0 COMMENT 'Hide note without deleting',

    -- Indexes
    INDEX idx_code_pk (code_pk),
    INDEX idx_correction_pk (correction_pk),
    INDEX idx_user_pk (user_pk),
    INDEX idx_note_type_pk (note_type_pk),
    INDEX idx_created_at (created_at),
    INDEX idx_hidden (hidden),

    -- Foreign keys
    CONSTRAINT fk_code_note_code FOREIGN KEY (code_pk) REFERENCES codes(pk) ON DELETE CASCADE,
    CONSTRAINT fk_code_note_user FOREIGN KEY (user_pk) REFERENCES users(pk) ON DELETE SET NULL,
    CONSTRAINT fk_code_note_note_type FOREIGN KEY (note_type_pk) REFERENCES note_type(pk) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='History of notes for each code entry';

-- Migrate existing notes from codes.notes field
-- Each existing note becomes a 'legacy' type note with no user attribution
INSERT INTO code_note (code_pk, user_pk, note_type_pk, note, created_at)
SELECT
    c.pk,
    NULL,  -- No user attribution for legacy notes
    nt.pk,
    c.notes,
    COALESCE(c.time_updated, c.time_added, NOW())  -- Use update time, or add time, or now
FROM codes c
CROSS JOIN note_type nt
WHERE nt.short_name = 'legacy'
  AND c.notes IS NOT NULL
  AND c.notes != '';

-- Create ASCLbot system user for automated curator notes (e.g. URL normalization)
INSERT IGNORE INTO users (username, real_name, password, login_attempts)
VALUES ('ASCLbot', 'ASCL Bot', '', 0);

-- Report migration results
SELECT
    CONCAT('Migrated ', COUNT(*), ' existing notes to code_note table') AS result
FROM code_note;
