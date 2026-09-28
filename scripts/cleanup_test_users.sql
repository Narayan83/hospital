-- Remove automated smoke-test users (scripts/test_crud.py).
-- Safe to run: only matches testuser.*@example.com emails.

DELETE FROM user_role_mappings
WHERE user_id IN (
    SELECT id FROM users WHERE email LIKE 'testuser.%@example.com'
);

DELETE FROM users
WHERE email LIKE 'testuser.%@example.com';

-- Verify:
-- SELECT full_name, email, is_active FROM users ORDER BY full_name;
