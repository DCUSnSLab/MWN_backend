-- Add role column to users table
-- This script adds the missing 'role' column that's causing the login API to fail

-- Add the role column with default value 'user'
ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(20) DEFAULT 'user';

-- Set all existing users to 'user' role (in case the column already exists but is empty)
UPDATE users SET role = 'user' WHERE role IS NULL OR role = '';

-- Create an admin user for testing (optional)
-- You can uncomment this if you want to create an admin user
-- INSERT INTO users (name, email, password_hash, role, is_active, email_verified)
-- VALUES ('Admin', 'admin@example.com', 'your_hashed_password_here', 'admin', true, true)
-- ON CONFLICT (email) DO UPDATE SET role = 'admin';

-- Verify the changes
SELECT COUNT(*) as total_users, role, COUNT(*) as count_by_role 
FROM users 
GROUP BY role;