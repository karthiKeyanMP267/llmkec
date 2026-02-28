import "dotenv/config";
import express from "express";
import cors from "cors";
import { Pool } from "pg";
import jwt from "jsonwebtoken";
import logger from "./logger.js";

// Simple Express server dedicated to login/authentication only.
const PORT = Number(process.env.AUTH_PORT || process.env.PORT || 4000);
const JWT_SECRET = process.env.AUTH_JWT_SECRET || "dev-secret-change-me";
const JWT_ISS = process.env.AUTH_JWT_ISS || "kec-auth";
const JWT_TTL_SECONDS = Number(process.env.AUTH_JWT_TTL || 3600);

// Allow DATABASE_URL or discrete PG* environment variables.
const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
  host: process.env.PGHOST,
  port: process.env.PGPORT ? Number(process.env.PGPORT) : undefined,
  database: process.env.PGDATABASE,
  user: process.env.PGUSER,
  password: process.env.PGPASSWORD,
  ssl: process.env.PGSSL === "1" ? { rejectUnauthorized: false } : undefined,
});

const app = express();
app.use(cors());
app.use(express.json());

// Email patterns per requirements.
const studentEmail = /^[A-Za-z]+\.\d{2}[A-Za-z]+@kongu\.edu$/i;
const facultyEmail = /^[A-Za-z]+\.[A-Za-z]+@kongu\.edu$/i;
const adminEmail = /^admin@kongu\.edu$/i;

const serverAccess = {
  STUDENT: ["student_server_2022", "student_server_2024"],
  FACULTY: ["student_server_2022", "student_server_2024", "faculty_server"],
  ADMIN: ["student_server_2022", "student_server_2024", "faculty_server"],
};

function detectRole(email) {
  const normalized = String(email || "").trim().toLowerCase();
  if (adminEmail.test(normalized)) return "ADMIN";
  if (studentEmail.test(normalized)) return "STUDENT";
  if (facultyEmail.test(normalized)) return "FACULTY";
  return null;
}

app.post("/auth/login", async (req, res) => {
  const { email, password } = req.body || {};
  if (!email || !password) {
    return res.status(400).json({ ok: false, error: "Email and password are required" });
  }

  const role = detectRole(email);
  if (!role) {
    return res.status(400).json({ ok: false, error: "Invalid email format for student, faculty, or admin" });
  }

  try {
    const normalizedEmail = String(email).trim().toLowerCase();
    const result = await pool.query(
      "SELECT id, email, password, role FROM users WHERE email = $1 LIMIT 1",
      [normalizedEmail]
    );
    logger.debug("Database query result:", result);
    const user = result.rows[0];

    if (!user || user.password !== password) {
      return res.status(401).json({ ok: false, error: "Invalid credentials" });
    }

    const storedRole = String(user.role || "").toUpperCase();
    if (storedRole !== role) {
      return res.status(403).json({ ok: false, error: "Email role does not match stored role" });
    }

    const allowedServers = serverAccess[role];
    const token = jwt.sign(
      {
        sub: user.id,
        email: normalizedEmail,
        role,
        allowedServers,
      },
      JWT_SECRET,
      { issuer: JWT_ISS, expiresIn: JWT_TTL_SECONDS }
    );

    return res.json({
      ok: true,
      role,
      allowedServers,
      token,
      expiresIn: JWT_TTL_SECONDS,
      message: `${role} login successful`,
    });
  } catch (error) {
    logger.error("Login error", error);
    return res.status(500).json({ ok: false, error: "Server error" });
  }
});

app.get("/health", (_req, res) => res.json({ status: "ok" }));

app.listen(PORT, () => {
  logger.info("Auth server listening on http://localhost:%d", PORT);
});
