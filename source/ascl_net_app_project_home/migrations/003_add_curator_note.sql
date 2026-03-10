-- Add correction_pk to code_note so curator notes can be linked to a specific correction
-- Uses the existing code_note / note_type infrastructure (note_type 'review' pk=3)
ALTER TABLE code_note
    ADD COLUMN correction_pk INT DEFAULT NULL AFTER code_pk,
    ADD INDEX idx_code_note_correction (correction_pk);

-- Create ASCLbot system user for automated curator notes (e.g. URL normalization)
INSERT IGNORE INTO users (username, real_name, password, login_attempts)
VALUES ('ASCLbot', 'ASCL Bot', '', 0);
