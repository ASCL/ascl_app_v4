-- Migration: Upgrade password hashing from SHA-1 to bcrypt
-- Date: 2025-12-28
-- Description: Expand password field to support bcrypt hashes (60 chars vs SHA-1's 40 chars)
--
-- This migration prepares the database for bcrypt password hashing while maintaining
-- backward compatibility with existing SHA-1 hashes during transition period.

-- Expand password field to support bcrypt hashes
-- SHA-1: 40 characters (hex)
-- Bcrypt: 60 characters ($2b$12$... format)
ALTER TABLE users
MODIFY COLUMN password VARCHAR(60) NOT NULL
COMMENT 'Password hash (SHA-1 legacy or bcrypt)';

-- Optional: Add a field to track hash type (for monitoring migration progress)
-- Uncomment if you want to explicitly track which users have been migrated
-- ALTER TABLE users ADD COLUMN password_hash_type ENUM('sha1', 'bcrypt') DEFAULT 'sha1' AFTER password;

-- Note: The application will automatically migrate users from SHA-1 to bcrypt
-- on their next successful login. No password reset is required.
