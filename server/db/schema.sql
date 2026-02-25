-- Users table for simple login demo.
CREATE TABLE IF NOT EXISTS users (
  id SERIAL PRIMARY KEY,
  email VARCHAR(255) UNIQUE NOT NULL,
  password VARCHAR(255) NOT NULL,
  role VARCHAR(10) NOT NULL CHECK (role IN ('STUDENT', 'FACULTY', 'ADMIN'))
);


INSERT INTO users (email, password, role) VALUES
  ('student.23aid@kongu.edu', 'studentpass', 'STUDENT'),
  ('faculty.ai@kongu.edu', 'facultypass', 'FACULTY'),
  ('admin@kongu.edu', 'adminpass', 'ADMIN')
ON CONFLICT (email) DO NOTHING;
