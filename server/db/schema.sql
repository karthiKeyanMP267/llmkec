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

CREATE TABLE IF NOT EXISTS chat_conversations (
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  conversation_id VARCHAR(100) NOT NULL,
  title VARCHAR(255) NOT NULL DEFAULT 'New Chat',
  thread_id VARCHAR(255),
  messages JSONB NOT NULL DEFAULT '[]'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (user_id, conversation_id)
);

CREATE INDEX IF NOT EXISTS idx_chat_conversations_user_updated
  ON chat_conversations(user_id, updated_at DESC);
