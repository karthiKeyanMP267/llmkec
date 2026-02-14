-- Users table for simple login demo.
CREATE TABLE IF NOT EXISTS users (
  id SERIAL PRIMARY KEY,
  email VARCHAR(255) UNIQUE NOT NULL,
  password VARCHAR(255) NOT NULL,
  role VARCHAR(10) NOT NULL CHECK (role IN ('STUDENT', 'FACULTY', 'ADMIN'))
);

-- For existing databases where users table was created without ADMIN in the check constraint,
-- drop and recreate the role check constraint safely.
DO $$
DECLARE
  constraint_name TEXT;
BEGIN
  SELECT c.conname
  INTO constraint_name
  FROM pg_constraint c
  JOIN pg_class t ON t.oid = c.conrelid
  JOIN pg_namespace n ON n.oid = t.relnamespace
  WHERE t.relname = 'users'
    AND c.contype = 'c'
    AND pg_get_constraintdef(c.oid) ILIKE '%role%'
  LIMIT 1;

  IF constraint_name IS NOT NULL THEN
    EXECUTE format('ALTER TABLE users DROP CONSTRAINT %I', constraint_name);
  END IF;

  ALTER TABLE users
    ADD CONSTRAINT users_role_check CHECK (role IN ('STUDENT', 'FACULTY', 'ADMIN'));
EXCEPTION
  WHEN duplicate_object THEN
    NULL;
END $$;

-- Seed records (id auto-generated). Adjust passwords as needed.
INSERT INTO users (email, password, role) VALUES
  ('teststudent.23cse@kongu.edu', 'studentpass', 'STUDENT'),
  ('testfaculty.ai@kongu.edu', 'facultypass', 'FACULTY'),
  ('admin@kongu.edu', 'adminpass', 'ADMIN')
ON CONFLICT (email) DO NOTHING;
