# KEC AI Assistant Platform (Current Setup)

This repository contains the full KEC assistant stack:

- React + Vite client UI
- Node.js chat/API gateway (OpenCode + MCP integration)
- Node.js auth server (PostgreSQL-backed login)
- Python ingestion APIs (main + student_2024 + faculty)

This README is for **first-time setup from zero**.

---

## 1) Prerequisites

Install these before starting:

- Node.js 20+ and npm
- Python 3.10+ (3.11 recommended)
- PostgreSQL 14+
- Git

Optional but commonly needed:

- OpenCode provider keys (OpenAI/Anthropic/Groq/Google/Mistral, etc.)
- `llama-parse` API key for document parsing

---

## 2) Project Structure (important folders)

- `client/` → React frontend
- `server/src/index.js` → Main chat API gateway (default port `8787`)
- `server/src/auth.js` → Auth server (default port `4005`)
- `server/run_all_ingestions.py` → Starts all ingestion services together
- `server/app/` → Main ingestion API code
- `server/student_2024/` → Student 2024 ingestion config/data
- `server/faculty/` → Faculty ingestion config/data
- `server/db/schema.sql` → PostgreSQL users table + seed users

---

## 3) Install Node dependencies

From repo root:

```bash
npm install
```

This installs workspace dependencies for root, `client`, and `server`.

---

## 4) Setup Python environment (for ingestion APIs)

From repo root (PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r server\student_2024\requirements.txt
pip install -r server\faculty\requirements.txt
pip install fastapi uvicorn python-multipart
```

Why extra install? `fastapi`/`uvicorn` are used by ingestion runtime and are not listed in both requirements files.

---

## 5) Setup PostgreSQL (required for login)

1. Create database (example name): `auth`
2. Execute schema file:

```sql
-- run file: server/db/schema.sql
```

This creates `users` and seeds demo accounts.

---

## 6) Environment configuration

### 6.1 Server auth/API env

Edit `server/.env` and verify at least:

- `AUTH_PORT=4005`
- `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, `PGPASSWORD`
- `AUTH_JWT_SECRET`
- `LLAMA_PARSE_API_KEY` (needed for some ingestion flows)

### 6.2 Ingestion env files

Already present in repo:

- `server/student_2024/.env.ingestion` (default `API_PORT=9001`)
- `server/faculty/.env.ingestion` (default `API_PORT=9002`)

Main ingestion instance is started via `server/run_all_ingestions.py` with `MAIN_INGESTION_PORT` defaulting to `9000`.

### 6.3 Client env

Edit `client/.env.local` and ensure URLs match your running services:

- `VITE_AUTH_URL=http://localhost:4005`
- `VITE_ADMIN_API_URL=http://localhost:9000`
- `VITE_AUTO_INGEST_URL=http://localhost:9000/ingestion`
- `VITE_STUDENT_2022_API_URL=http://localhost:9000/ingestion`
- `VITE_STUDENT_2024_API_URL=http://localhost:9001/ingestion`
- `VITE_FACULTY_API_URL=http://localhost:9002/ingestion`

---

## 7) First-time startup order (recommended)

### Terminal A: Start all Python ingestion services

```powershell
.\.venv\Scripts\Activate.ps1
python server\run_all_ingestions.py
```

Expected ingestion ports:

- `9000` → main ingestion
- `9001` → student_2024 ingestion
- `9002` → faculty ingestion

### Terminal B: Start Node services + frontend

```bash
npm run dev
```

This starts:

- `server/src/index.js` (chat API, default `8787`)
- `server/src/auth.js` (auth API, default `4005`)
- `client` Vite dev server (default `5173`)

---

## 8) URLs and health checks

- Frontend: `http://localhost:5173`
- Chat API health: `http://localhost:8787/api/health`
- Auth health: `http://localhost:4005/health`
- Main ingestion health: `http://localhost:9000/ingestion/health`
- Student ingestion health: `http://localhost:9001/ingestion/health`
- Faculty ingestion health: `http://localhost:9002/ingestion/health`

---

## 9) Default login users (from seeded schema)

After running `server/db/schema.sql`:

- Student: `student.23aid@kongu.edu` / `studentpass`
- Faculty: `faculty.ai@kongu.edu` / `facultypass`
- Admin: `admin@kongu.edu` / `adminpass`

Use these only for local/dev testing.

---

## 10) Build and production-style run

Build frontend:

```bash
npm run build
```

Run Node server only:

```bash
npm run start
```

Note: production deployment still requires running ingestion services separately unless you provide an alternative runtime process manager.

---

## 11) Common issues and fixes

### Login fails with DB errors

- Verify PostgreSQL is running.
- Re-check `PG*` values in `server/.env`.
- Ensure schema in `server/db/schema.sql` has been executed.

### Frontend cannot call APIs (CORS/connection refused)

- Ensure `client/.env.local` ports match running services.
- Confirm all service processes are up.

### Ingestion fails at startup

- Ensure Python venv is active.
- Reinstall dependencies from both requirements files.
- Verify `LLAMA_PARSE_API_KEY` if parse features are used.

### `npm run dev` works but answers are empty/slow first time

- Check OpenCode/provider credentials in your environment.
- Check chat API logs in `server/src/index.js` process.

---

## 12) Security notes (important)

- Do not commit real API keys or DB passwords to git.
- Rotate any secrets that were previously shared.
- For non-local environments, replace seeded demo credentials and enforce strong passwords.
