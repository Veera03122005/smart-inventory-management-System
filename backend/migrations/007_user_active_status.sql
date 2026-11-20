-- SmartStock AI — Migration 007: Add User Account Active Status
-- Ensures users table has is_active column for account deactivation and authorization checks
ALTER TABLE users ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1;
