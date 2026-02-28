import "dotenv/config";
import express from "express";
import cors from "cors";
import { Pool } from "pg";
import jwt from "jsonwebtoken";
import { createOpencodeClient } from "@opencode-ai/sdk";
import { spawn } from "node:child_process";
import net from "node:net";
import { watch } from "node:fs";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { Client as McpClient } from "@modelcontextprotocol/sdk/client";
import { StreamableHTTPClientTransport } from "@modelcontextprotocol/sdk/client/streamableHttp.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";
import logger from "./logger.js";

const API_PORT = Number(process.env.PORT || 8787);
const OPENCODE_HOSTNAME = process.env.OPENCODE_HOSTNAME || "127.0.0.1";
const OPENCODE_PORT_RAW = process.env.OPENCODE_PORT;
const OPENCODE_PORT_IS_AUTO = OPENCODE_PORT_RAW === "auto";
// Default: auto-select a free port. Set OPENCODE_PORT=<number> to force a fixed port.
const OPENCODE_PORT = OPENCODE_PORT_IS_AUTO || !OPENCODE_PORT_RAW ? null : Number(OPENCODE_PORT_RAW);
const OPENCODE_STARTUP_TIMEOUT_MS = Number(process.env.OPENCODE_STARTUP_TIMEOUT_MS || 30_000);
// By default we eager-start OpenCode so the first chat doesn't pay cold-start cost.
// Set OPENCODE_EAGER_START=0 to disable.
const OPENCODE_EAGER_START = 1;
const CHAT_DEFAULT_PROVIDER_ID = process.env.CHAT_DEFAULT_PROVIDER_ID || "opencode";
const CHAT_DEFAULT_MODEL_ID = process.env.CHAT_DEFAULT_MODEL_ID || "kimi-k2.5-free";
const AUTH_JWT_SECRET = process.env.AUTH_JWT_SECRET || "dev-secret-change-me";
const AUTH_JWT_ISS = process.env.AUTH_JWT_ISS || "kec-auth";

const KEC_SYSTEM_PROMPT = `
You are **KEC Assistant**, the official AI assistant of Kongu Engineering College.

Your purpose:
- Assist students, faculty, and admins using ONLY institution-approved knowledge and tools.
- Operate strictly within the permissions provided by the system.

Identity & Scope:
- You represent Kongu Engineering College.
- Your tone must be professional, clear, and academic.
- Do NOT mention external organizations, public datasets, or the internet.

STRICT RESTRICTIONS:
- You do NOT have access to:
  - Web search
  - Web browsing
  - Web fetching
  - External APIs
  - Public internet knowledge beyond model training
- If a question requires web access, reply:
  "This request requires external web access, which is not permitted."

TOOLS POLICY:
- Use ONLY the custom MCP tools explicitly provided by the system.
- If no tool is available, answer using internal reasoning only.
- Never assume a tool exists unless it is listed.

ROLE-BASED BEHAVIOR:
- If the user role is STUDENT:
  - Do NOT access or reference faculty-only, staff-only, policy, HR, or administrative data.
  - If asked about restricted content, reply exactly:
    "Access denied for faculty content."

- If the user role is FACULTY:
  - You may access faculty-approved tools and datasets.
  - You may answer both academic and administrative questions.

- If the user role is ADMIN:
  - You may access all institution-approved student and faculty datasets/tools.
  - You may answer academic, administrative, and policy-related questions.

OUTPUT RULES:
- Be concise and structured.
- If tabular data is requested, respond using an HTML <table>.
- Do not use markdown code fences for tables.
- Do not hallucinate policies, rules, or internal documents.
- Never expose or mention document/source filenames, paths, URLs, citations, or provenance in answers. Present only the answer content.

FAIL-SAFE:
- If unsure, say:
  "I do not have sufficient permission or data to answer this."
`;

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const MCP_STORE_PATH = process.env.MCP_STORE_PATH || path.resolve(__dirname, "..", "mcp-configs.json");

let opencodePromise;
let opencodeProc;
let opencodeBaseUrl;

const mcpConfigStore = new Map();
let mcpWatcherStarted = false;
let mcpSyncInFlight = null;
let mcpToolPolicy = null;
let resolvedDefaultChatModel = null;

const pgOptions = {
  connectionString: process.env.DATABASE_URL,
  host: process.env.PGHOST,
  port: process.env.PGPORT ? Number(process.env.PGPORT) : undefined,
  database: process.env.PGDATABASE,
  user: process.env.PGUSER,
  password: process.env.PGPASSWORD,
  ssl: process.env.PGSSL === "1" ? { rejectUnauthorized: false } : undefined,
};

const hasDatabaseConfig = Boolean(
  pgOptions.connectionString || (pgOptions.host && pgOptions.database && pgOptions.user)
);

const historyPool = hasDatabaseConfig ? new Pool(pgOptions) : null;
let historySchemaReady = false;

function debounce(fn, delayMs) {
  let t = null;
  return (...args) => {
    if (t) clearTimeout(t);
    t = setTimeout(() => fn(...args), delayMs);
  };
}

async function loadMcpStore({ replace = false } = {}) {
  try {
    const raw = await fs.readFile(MCP_STORE_PATH, "utf8");
    const json = JSON.parse(raw);
    const servers = json?.servers;
    const tools = json?.tools;
    if (servers && typeof servers === "object") {
      if (replace) mcpConfigStore.clear();
      for (const [name, config] of Object.entries(servers)) {
        if (typeof name === "string" && name.trim() && config && typeof config === "object") {
          mcpConfigStore.set(name, config);
        }
      }
    }
    if (tools && typeof tools === "object" && !Array.isArray(tools)) {
      mcpToolPolicy = { ...tools };
    } else if (replace) {
      mcpToolPolicy = null;
    }
    return true;
  } catch (e) {
    logger.debug("Failed to load MCP store: %s", e?.message || e);
    return false;
  }
}

async function saveMcpStore() {
  const servers = Object.fromEntries(mcpConfigStore.entries());
  const payload = { version: 1, servers };
  if (mcpToolPolicy && typeof mcpToolPolicy === "object") {
    payload.tools = mcpToolPolicy;
  }
  const content = JSON.stringify(payload, null, 2);
  await fs.writeFile(MCP_STORE_PATH, content, "utf8");
}

function normalizeMcpConfigs(configRoot) {
  // OpenCode config shape has varied; accept multiple common shapes.
  const candidates = [
    configRoot?.mcp,
    configRoot?.mcpServers,
    configRoot?.mcp_servers,
    configRoot?.experimental?.mcp,
    configRoot?.mcp?.servers,
  ];

  for (const cand of candidates) {
    if (!cand) continue;

    if (Array.isArray(cand)) {
      const out = {};
      for (const entry of cand) {
        if (!entry || typeof entry !== "object") continue;
        const name = typeof entry.name === "string" ? entry.name.trim() : "";
        if (!name) continue;
        out[name] = entry;
      }
      if (Object.keys(out).length) return out;
      continue;
    }

    if (cand && typeof cand === "object") {
      if (cand.servers && typeof cand.servers === "object" && !Array.isArray(cand.servers)) {
        return cand.servers;
      }
      return cand;
    }
  }

  return {};
}

function startMcpStoreWatcher(onValidChange) {
  if (mcpWatcherStarted) return;
  mcpWatcherStarted = true;

  const dir = path.dirname(MCP_STORE_PATH);
  const file = path.basename(MCP_STORE_PATH).toLowerCase();
  const onChange = debounce(async () => {
    const ok = await loadMcpStore({ replace: true });
    if (!ok) return;
    await onValidChange();
  }, 300);

  try {
    watch(dir, { persistent: false }, (_eventType, filename) => {
      if (!filename) return;
      if (String(filename).toLowerCase() !== file) return;
      onChange();
    });
  } catch (e) {
    logger.debug("File watcher setup failed: %s", e?.message || e);
  }
}

async function syncMcpFromStoreIntoOpencode(opencodeClient) {
  if (mcpSyncInFlight) return await mcpSyncInFlight;

  mcpSyncInFlight = (async () => {
    const entries = Array.from(mcpConfigStore.entries());
    if (!entries.length) return;

    for (const [name, config] of entries) {
      if (typeof name !== "string" || !name.trim()) continue;
      if (!config || typeof config !== "object") continue;

      // Apply config (best-effort). OpenCode may reject invalid configs.
      try {
        await opencodeClient.mcp.add({ body: { name, config } });
      } catch (e) {
        logger.debug("MCP add '%s' failed: %s", name, e?.message || e);
      }

      const enabled = config.enabled !== false;
      if (!enabled) {
        try {
          await opencodeClient.mcp.disconnect({ path: { name } });
        } catch (e) {
          logger.debug("MCP disconnect '%s' failed: %s", name, e?.message || e);
        }
        continue;
      }

      try {
        await opencodeClient.mcp.connect({ path: { name } });
      } catch (e) {
        logger.debug("MCP connect '%s' failed: %s", name, e?.message || e);
      }
    }
  })().finally(() => {
    mcpSyncInFlight = null;
  });

  return await mcpSyncInFlight;
}

const DEBUG_CHAT_TIMING = process.env.DEBUG_CHAT_TIMING === "1";

async function getFreePort(hostname) {
  return await new Promise((resolve, reject) => {
    const server = net.createServer();
    server.unref();
    server.on("error", reject);
    server.listen(0, hostname, () => {
      const address = server.address();
      const port = typeof address === "object" && address ? address.port : null;
      server.close(() => resolve(port));
    });
  });
}

async function isPortAvailable(hostname, port) {
  return await new Promise((resolve) => {
    const server = net.createServer();
    server.unref();
    server.once("error", () => resolve(false));
    server.listen(port, hostname, () => {
      server.close(() => resolve(true));
    });
  });
}

async function startOpencodeServer() {
  if (opencodeBaseUrl) return opencodeBaseUrl;

  const t0 = Date.now();

  let port = OPENCODE_PORT ?? (await getFreePort(OPENCODE_HOSTNAME));
  if (!port) {
    logger.error("Failed to allocate a free port for OpenCode server");
    return null;
  }

  // If a fixed port is configured (including the default 8010), check if it's already in use.
  if (OPENCODE_PORT !== null) {
    const available = await isPortAvailable(OPENCODE_HOSTNAME, port);
    if (!available) {
      const explicitlySet = typeof OPENCODE_PORT_RAW === "string" && OPENCODE_PORT_RAW.length > 0;
      if (explicitlySet) {
        logger.error("OpenCode port %d is already in use", port);
        return null;
      }

      // Default port is taken; fall back to an available port automatically.
      const fallback = await getFreePort(OPENCODE_HOSTNAME);
      if (!fallback) {
        logger.error("Failed to allocate a free port for OpenCode server (fallback)");
        return null;
      }
      logger.warn("OpenCode port %d is in use; falling back to free port %d", port, fallback);
      port = fallback;
    }
  }

  const args = [`serve`, `--hostname=${OPENCODE_HOSTNAME}`, `--port=${port}`];
  // IMPORTANT: don't overwrite OPENCODE_CONFIG_CONTENT.
  // If we set it to {}, OpenCode won't load the user's config file and MCP servers won't appear.
  const env = {
    ...process.env,
  };

  // Prefer local CLI install to avoid `npx` downloading (which is slow/unreliable).
  // On Windows, npm CLIs are often .cmd shims, so running through cmd.exe is reliable.
  const child =
    process.platform === "win32"
      ? spawn("cmd.exe", ["/d", "/s", "/c", "npx", "--no-install", "opencode-ai", ...args], { env })
      : spawn("npx", ["--no-install", "opencode-ai", ...args], { env });

  opencodeProc = child;

  const url = await new Promise((resolve, reject) => {
    const timeoutMs = OPENCODE_STARTUP_TIMEOUT_MS;
    const id = setTimeout(() => {
      reject(new Error(`Timeout waiting for OpenCode server to start after ${timeoutMs}ms`));
    }, timeoutMs);

    let output = "";
    const onChunk = (chunk) => {
      output += chunk.toString();
      const lines = output.split("\n");
      for (const line of lines) {
        if (line.startsWith("opencode server listening")) {
          const match = line.match(/on\s+(https?:\/\/[^\s]+)/);
          if (!match) continue;
          clearTimeout(id);
          resolve(match[1]);
          return;
        }
      }
    };

    child.stdout?.on("data", onChunk);
    child.stderr?.on("data", onChunk);

    child.on("exit", (code) => {
      clearTimeout(id);
      let msg = `OpenCode server exited with code ${code}`;
      if (output.trim()) msg += `\nOutput: ${output}`;
      reject(new Error(msg));
    });

    child.on("error", (error) => {
      clearTimeout(id);
      reject(error);
    });
  });

  opencodeBaseUrl = url;
  logger.info("OpenCode server started at %s", opencodeBaseUrl);
  if (DEBUG_CHAT_TIMING) {
    logger.info("[timing] opencode_start_ms=%d", Date.now() - t0);
  }
  return url;
}

async function getOpencode() {
  if (!opencodePromise) {
    opencodePromise = (async () => {
      const baseUrl = await startOpencodeServer();
      if (!baseUrl) {
        logger.error("OpenCode server failed to start — no base URL returned");
        return null;
      }
      const client = createOpencodeClient({ baseUrl });

      // Keep MCP connections alive based on server/mcp-configs.json.
      try {
        await syncMcpFromStoreIntoOpencode(client);
      } catch (e) {
        logger.debug("Initial MCP sync failed: %s", e?.message || e);
      }

      return {
        client,
        server: {
          url: baseUrl,
          close() {
            opencodeProc?.kill();
          },
        },
      };
    })().catch((error) => {
      opencodePromise = undefined;
      logger.error("OpenCode initialization failed: %s", error?.message || error);
      return null;
    });
  }

  return opencodePromise;
}

function unwrap(result) {
  if (!result || typeof result !== "object") return result;
  if ("data" in result && result.data !== undefined) return result.data;
  if ("body" in result && result.body !== undefined) return result.body;
  return result;
}

async function withTimeout(promise, timeoutMs, label) {
  const ms = Number(timeoutMs);
  if (!ms || ms <= 0) return await promise;
  return await Promise.race([
    promise,
    new Promise((_, reject) =>
      setTimeout(() => reject(new Error(`${label || "Operation"} timed out after ${ms}ms`)), ms)
    ),
  ]);
}

async function getMcpConfigsFromOpencode(client) {
  const cfg = unwrap(await client.config.get());
  return normalizeMcpConfigs(cfg);
}

async function listMcpToolsFromConfig(name, config) {
  const client = new McpClient(
    { name: "opencode-chat-ui", version: "1.0.0" },
    { capabilities: {} }
  );

  let transport;
  if (config?.type === "remote") {
    const url = config?.url;
    if (typeof url !== "string" || !url.trim()) {
      logger.error("MCP server '%s' missing url", name);
      return [];
    }
    const headers = config?.headers && typeof config.headers === "object" ? config.headers : undefined;
    transport = new StreamableHTTPClientTransport(new URL(url), {
      requestInit: headers ? { headers } : undefined,
    });
  } else if (config?.type === "local") {
    const cmd = Array.isArray(config?.command) ? config.command : null;
    if (!cmd || cmd.length === 0) {
      logger.error("MCP server '%s' missing command", name);
      return [];
    }
    const env = config?.environment && typeof config.environment === "object" ? config.environment : undefined;
    transport = new StdioClientTransport({
      command: String(cmd[0]),
      args: cmd.slice(1).map(String),
      env,
      cwd: process.cwd(),
      stderr: "pipe",
    });
  } else {
    logger.error("Unsupported MCP config type for '%s'", name);
    return [];
  }

  try {
    await client.connect(transport);
    const timeoutMs = Number(config?.timeout || 5000);
    const result = await withTimeout(client.listTools(), timeoutMs, `List MCP tools for '${name}'`);
    return result?.tools || [];
  } finally {
    try {
      await transport.close();
    } catch (e) {
      logger.debug("MCP transport close failed: %s", e?.message || e);
    }
  }
}

async function fetchJson(baseUrl, pathname) {
  const url = new URL(pathname, baseUrl).toString();
  const res = await fetch(url, {
    headers: {
      Accept: "application/json",
    },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    logger.error("OpenCode HTTP %d for %s: %s", res.status, url, text);
    return null;
  }
  return res.json();
}

function extractText(parts) {
  if (!Array.isArray(parts)) return "";
  return parts
    .filter((p) => p && p.type === "text" && typeof p.text === "string")
    .map((p) => p.text)
    .join("");
}

function writeNdjson(res, obj) {
  res.write(`${JSON.stringify(obj)}\n`);
}

function wantsStructuredOutput(message) {
  const text = String(message || "").toLowerCase();
  return (
    text.includes("tabular") ||
    text.includes("table") ||
    text.includes("json") ||
    text.includes("schema") ||
    text.includes("rule") ||
    text.includes("regulation")
  );
}

function redactSecrets(value) {
  if (!value || typeof value !== "object") return value;
  if (Array.isArray(value)) return value.map(redactSecrets);

  const out = {};
  for (const [k, v] of Object.entries(value)) {
    const key = String(k).toLowerCase();
    if (key === "key" || key === "apikey" || key === "api_key" || key === "token" || key.endsWith("_token")) {
      continue;
    }
    out[k] = redactSecrets(v);
  }
  return out;
}

function deriveRole(req) {
  if (req.authUser?.role === "ADMIN") return "ADMIN";
  if (req.authUser?.role === "FACULTY") return "FACULTY";
  if (req.authUser?.role === "STUDENT") return "STUDENT";
  const headerRole = (req.headers["x-role"] || req.headers["x-user-role"] || "").toString().toUpperCase();
  if (headerRole === "ADMIN") return "ADMIN";
  if (headerRole === "FACULTY") return "FACULTY";
  return "STUDENT"; // default safest role
}

function deriveAuthUser(req) {
  const auth = (req.headers.authorization || "").toString();
  if (!auth.toLowerCase().startsWith("bearer ")) return null;
  const token = auth.slice(7).trim();
  if (!token) return null;

  try {
    const payload = jwt.verify(token, AUTH_JWT_SECRET, { issuer: AUTH_JWT_ISS });
    const userId = Number(payload?.sub);
    const email = String(payload?.email || "").trim().toLowerCase();
    const role = String(payload?.role || "").trim().toUpperCase();
    const allowedServers = Array.isArray(payload?.allowedServers)
      ? payload.allowedServers.map((name) => String(name || "").trim()).filter(Boolean)
      : [];

    if (!Number.isFinite(userId) || !email) return null;

    return { userId, email, role, allowedServers };
  } catch {
    return null;
  }
}

async function ensureHistorySchema() {
  if (!historyPool || historySchemaReady) return historySchemaReady;

  await historyPool.query(`
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
  `);

  await historyPool.query(`
    CREATE INDEX IF NOT EXISTS idx_chat_conversations_user_updated
      ON chat_conversations(user_id, updated_at DESC);
  `);

  historySchemaReady = true;
  return true;
}

function requireAuthUser(req, res) {
  if (req.authUser?.userId) return true;
  res.status(401).json({ ok: false, error: "Unauthorized" });
  return false;
}

function parseServerNameFromId(id) {
  if (!id || typeof id !== "string") return null;
  const trimmed = id.trim();
  if (!trimmed) return null;
  const parts = trimmed.split(/[/:]/);
  return parts.length > 1 ? parts[0] : null;
}

function extractToolServer(tool) {
  if (!tool) return null;
  if (typeof tool === "object") {
    const direct =
      tool.server || tool.serverName || tool.serverID || tool.serverId || tool.server_id || tool.provider || tool.source;
    if (typeof direct === "string" && direct.trim()) return direct.trim();
    const idLike = tool.id || tool.name || tool.tool || tool.title || "";
    const parsed = parseServerNameFromId(idLike);
    if (parsed) return parsed;
  }
  if (typeof tool === "string") {
    const parsed = parseServerNameFromId(tool);
    if (parsed) return parsed;
  }
  return null;
}

function filterToolsForRole(role, tools, allowedServers) {
  if (role === "FACULTY" || role === "ADMIN") return tools;
  if (!Array.isArray(tools)) return tools;

  const allowList = new Set((allowedServers || roleDefaultMcpServers(role)).map((s) => String(s || "").trim()).filter(Boolean));

  return tools.filter((tool) => {
    const server = extractToolServer(tool);
    if (!server) return true; // If we cannot detect the server, don't over-block generic tools.
    return allowList.has(server);
  });
}

function listEnabledMcpServers() {
  return Array.from(mcpConfigStore.entries())
    .filter(([, cfg]) => cfg && typeof cfg === "object" && cfg.enabled !== false)
    .map(([name]) => name);
}

function parseAllowedServersHeader(req) {
  const raw = (req.headers["x-allowed-servers"] || "").toString();
  if (!raw.trim()) return null;
  const parsed = raw
    .split(",")
    .map((name) => name.trim())
    .filter(Boolean);
  return parsed.length ? Array.from(new Set(parsed)) : null;
}

function roleDefaultMcpServers(role) {
  if (role === "ADMIN") {
    return ["student_server_2022", "student_server_2024", "faculty_server"];
  }
  if (role === "FACULTY") {
    return ["faculty_server"];
  }
  return ["student_server_2022", "student_server_2024"];
}

function allowedMcpServersForRole(role, req) {
  const enabledServers = new Set(listEnabledMcpServers());
  const roleDefaults = roleDefaultMcpServers(role).filter((name) => enabledServers.has(name));
  const tokenAllowed = Array.isArray(req.authUser?.allowedServers) ? req.authUser.allowedServers : null;
  if (tokenAllowed && tokenAllowed.length) {
    return roleDefaults.filter((name) => tokenAllowed.includes(name));
  }
  const headerAllowed = parseAllowedServersHeader(req);
  if (!headerAllowed) return roleDefaults;
  return roleDefaults.filter((name) => headerAllowed.includes(name));
}

function normalizeProvidersPayload(payload) {
  const providers = Array.isArray(payload?.providers) ? payload.providers : [];
  const defaults = payload?.default && typeof payload.default === "object" ? payload.default : {};
  return { providers, defaults };
}

function normalizeModelList(provider) {
  if (!provider || typeof provider !== "object") return [];
  const models = provider.models;
  if (!models) return [];
  const list = Array.isArray(models) ? models : Object.values(models);
  return list.filter((m) => m && typeof m === "object" && m.id);
}

async function getDefaultChatModel(client) {
  if (resolvedDefaultChatModel) return resolvedDefaultChatModel;

  const payload = unwrap(await client.config.providers());
  const { providers, defaults } = normalizeProvidersPayload(payload);
  if (!providers.length) return null;

  const provider =
    providers.find((p) => p?.id === CHAT_DEFAULT_PROVIDER_ID) ||
    providers.find((p) => /opencode/i.test(String(p?.id || p?.name || ""))) ||
    providers[0];
  if (!provider?.id) return null;

  const models = normalizeModelList(provider);
  const preferredById = models.find((m) => String(m.id) === CHAT_DEFAULT_MODEL_ID);
  const preferredByName =
    models.find((m) => /kimi/i.test(String(m?.name || "")) && /(2\.?5|k2\.?5)/i.test(String(m?.name || ""))) ||
    models.find((m) => /kimi/i.test(String(m?.id || "")) && /(2\.?5|k2\.?5)/i.test(String(m?.id || "")));
  const providerDefault = defaults?.[provider.id]
    ? models.find((m) => String(m.id) === String(defaults[provider.id]))
    : null;
  const chosen = preferredById || preferredByName || providerDefault || models[0];

  if (!chosen?.id) return null;

  resolvedDefaultChatModel = {
    providerID: String(provider.id),
    modelID: String(chosen.id),
  };
  return resolvedDefaultChatModel;
}

const app = express();
app.use(express.json({ limit: "1mb" }));
app.use(cors({ origin: true }));
app.use((req, _res, next) => {
  req.authUser = deriveAuthUser(req);
  next();
});

await loadMcpStore({ replace: true });
startMcpStoreWatcher(async () => {
  if (!opencodePromise) return;
  try {
    const { client } = await getOpencode();
    await syncMcpFromStoreIntoOpencode(client);
  } catch (e) {
    logger.debug("MCP store sync failed: %s", e?.message || e);
  }
});

app.get("/", (_req, res) => {
  res.type("text/plain").send("OK. Try /api/health");
});

app.get("/api/health", async (_req, res) => {
  try {
    const { server } = await getOpencode();
    const health = await fetchJson(server.url, "/global/health");
    res.json({ ok: true, opencode: health, server: { url: server.url } });
  } catch (error) {
    logger.error("GET /api/health failed: %s", error?.message || error);
    res.status(500).json({ ok: false, error: String(error?.message || error) });
  }
});

app.get("/api/models", async (_req, res) => {
  try {
    const { client } = await getOpencode();
    const providers = unwrap(await client.config.providers());
    res.json({ ok: true, providers: redactSecrets(providers) });
  } catch (error) {
    logger.error("GET /api/models failed: %s", error?.message || error);
    res.status(500).json({ ok: false, error: String(error?.message || error) });
  }
});

app.get("/api/mcp/status", async (req, res) => {
  try {
    const { client } = await getOpencode();
    const status = unwrap(await client.mcp.status());
    res.json({ ok: true, status });
  } catch (error) {
    logger.error("GET /api/mcp/status failed: %s", error?.message || error);
    res.status(500).json({ ok: false, error: String(error?.message || error) });
  }
});

app.post("/api/mcp/add", async (req, res) => {
  try {
    const { name, config } = req.body || {};
    if (typeof name !== "string" || !name.trim()) {
      res.status(400).json({ ok: false, error: "Missing 'name'" });
      return;
    }
    if (!config || typeof config !== "object") {
      res.status(400).json({ ok: false, error: "Missing 'config'" });
      return;
    }

    const { client } = await getOpencode();
    const status = unwrap(
      await client.mcp.add({
        body: { name: name.trim(), config },
      })
    );

    // Persist config locally so we can later list tools even if OpenCode doesn't expose the config via config.get().
    mcpConfigStore.set(name.trim(), config);
    try {
      await saveMcpStore();
    } catch (e) {
      logger.debug("MCP store persistence failed: %s", e?.message || e);
    }

    res.json({ ok: true, status });
  } catch (error) {
    logger.error("POST /api/mcp/add failed: %s", error?.message || error);
    res.status(500).json({ ok: false, error: String(error?.message || error) });
  }
});

app.post("/api/mcp/connect", async (req, res) => {
  try {
    const { name } = req.body || {};
    if (typeof name !== "string" || !name.trim()) {
      res.status(400).json({ ok: false, error: "Missing 'name'" });
      return;
    }
    const { client } = await getOpencode();
    const result = unwrap(await client.mcp.connect({ path: { name: name.trim() } }));
    res.json({ ok: true, result });
  } catch (error) {
    logger.error("POST /api/mcp/connect failed: %s", error?.message || error);
    res.status(500).json({ ok: false, error: String(error?.message || error) });
  }
});

app.post("/api/mcp/disconnect", async (req, res) => {
  try {
    const { name } = req.body || {};
    if (typeof name !== "string" || !name.trim()) {
      res.status(400).json({ ok: false, error: "Missing 'name'" });
      return;
    }
    const { client } = await getOpencode();
    const result = unwrap(await client.mcp.disconnect({ path: { name: name.trim() } }));
    res.json({ ok: true, result });
  } catch (error) {
    logger.error("POST /api/mcp/disconnect failed: %s", error?.message || error);
    res.status(500).json({ ok: false, error: String(error?.message || error) });
  }
});

app.get("/api/mcp/tools", async (req, res) => {
  try {
    const role = deriveRole(req);
    const allowedServers = allowedMcpServersForRole(role, req);
    const name = (req.query?.name || "").toString().trim();
    if (!name) {
      res.status(400).json({ ok: false, error: "Missing query param: name" });
      return;
    }

    const baseName = (() => {
      // Some MCP runtimes append instance suffixes like ":1".
      const m = name.match(/^(.*):\d+$/);
      return m ? m[1] : name;
    })();

    const { client } = await getOpencode();
    const fromStore = mcpConfigStore.get(name) || (baseName !== name ? mcpConfigStore.get(baseName) : undefined);
    const mcpConfigs = await getMcpConfigsFromOpencode(client);
    const fromOpencode = mcpConfigs?.[name] || (baseName !== name ? mcpConfigs?.[baseName] : undefined);
    const config = fromStore || fromOpencode;
    if (!config) {
      res
        .status(404)
        .json({
          ok: false,
          error: `No MCP config found for '${name}'. If this server was not added via this UI, add it here (MCP → Add server) so we know how to reach it.`,
        });
      return;
    }

    if (!allowedServers.includes(baseName)) {
      res.status(403).json({ ok: false, error: "Access denied for this MCP server" });
      return;
    }

    const tools = await listMcpToolsFromConfig(name, config);
    res.json({ ok: true, name, tools: filterToolsForRole(role, tools, allowedServers) });
  } catch (error) {
    logger.error("GET /api/mcp/tools failed: %s", error?.message || error);
    res.status(500).json({ ok: false, error: String(error?.message || error) });
  }
});

// Debug endpoint: shows MCP-related parts of OpenCode config (no secrets).
app.get("/api/mcp/config", async (_req, res) => {
  try {
    const { client } = await getOpencode();
    const cfg = unwrap(await client.config.get());
    const mcp = normalizeMcpConfigs(cfg);
    res.json({ ok: true, storePath: MCP_STORE_PATH, stored: Array.from(mcpConfigStore.keys()), opencodeMcp: redactSecrets(mcp) });
  } catch (error) {
    logger.error("GET /api/mcp/config failed: %s", error?.message || error);
    res.status(500).json({ ok: false, error: String(error?.message || error) });
  }
});

app.get("/api/tools", async (req, res) => {
  try {
    const role = deriveRole(req);
    const allowedServers = allowedMcpServersForRole(role, req);
    const provider = (req.query?.provider || "").toString().trim();
    const model = (req.query?.model || "").toString().trim();
    if (!provider || !model) {
      res.status(400).json({ ok: false, error: "Missing query params: provider, model" });
      return;
    }
    const { client } = await getOpencode();
    const tools = unwrap(await client.tool.list({ query: { provider, model } }));
    res.json({ ok: true, tools: filterToolsForRole(role, tools, allowedServers) });
  } catch (error) {
    logger.error("GET /api/tools failed: %s", error?.message || error);
    res.status(500).json({ ok: false, error: String(error?.message || error) });
  }
});

app.get("/api/tool-ids", async (req, res) => {
  try {
    const role = deriveRole(req);
    const allowedServers = allowedMcpServersForRole(role, req);
    const { client } = await getOpencode();
    const ids = unwrap(await client.tool.ids());
    res.json({ ok: true, ids: filterToolsForRole(role, ids, allowedServers) });
  } catch (error) {
    logger.error("GET /api/tool-ids failed: %s", error?.message || error);
    res.status(500).json({ ok: false, error: String(error?.message || error) });
  }
});

app.get("/api/agents", async (_req, res) => {
  try {
    const { client } = await getOpencode();
    const agents = unwrap(await client.app.agents());
    res.json({ ok: true, agents });
  } catch (error) {
    logger.error("GET /api/agents failed: %s", error?.message || error);
    res.status(500).json({ ok: false, error: String(error?.message || error) });
  }
});

app.get("/api/thread/:id/messages", async (req, res) => {
  try {
    const { client } = await getOpencode();
    const sessionId = req.params.id;
    const messages = unwrap(await client.session.messages({ path: { id: sessionId } }));

    const normalized = (messages || []).map((m) => {
      const info = m?.info;
      const parts = m?.parts;
      return {
        id: info?.id,
        role: info?.role,
        createdAt: info?.createdAt,
        text: extractText(parts),
        parts,
      };
    });

    res.json({ ok: true, threadId: sessionId, messages: normalized });
  } catch (error) {
    logger.error("GET /api/thread/:id/messages failed: %s", error?.message || error);
    res.status(500).json({ ok: false, error: String(error?.message || error) });
  }
});

app.get("/api/chat/history", async (req, res) => {
  try {
    if (!requireAuthUser(req, res)) return;
    if (!historyPool) {
      res.status(503).json({ ok: false, error: "Chat history storage is not configured" });
      return;
    }

    await ensureHistorySchema();

    const result = await historyPool.query(
      `
      SELECT conversation_id, title, thread_id, messages, created_at, updated_at
      FROM chat_conversations
      WHERE user_id = $1
      ORDER BY updated_at DESC
      `,
      [req.authUser.userId]
    );

    const conversations = result.rows.map((row) => ({
      id: row.conversation_id,
      title: row.title,
      threadId: row.thread_id,
      messages: Array.isArray(row.messages) ? row.messages : [],
      createdAt: row.created_at,
      updatedAt: row.updated_at,
    }));

    res.json({ ok: true, conversations });
  } catch (error) {
    logger.error("GET /api/chat/history failed: %s", error?.message || error);
    res.status(500).json({ ok: false, error: String(error?.message || error) });
  }
});

app.post("/api/chat/history", async (req, res) => {
  try {
    if (!requireAuthUser(req, res)) return;
    if (!historyPool) {
      res.status(503).json({ ok: false, error: "Chat history storage is not configured" });
      return;
    }

    const { id, title, threadId, messages } = req.body || {};
    const conversationId = String(id || "").trim();
    if (!conversationId) {
      res.status(400).json({ ok: false, error: "Missing conversation id" });
      return;
    }
    if (!Array.isArray(messages)) {
      res.status(400).json({ ok: false, error: "Messages must be an array" });
      return;
    }

    await ensureHistorySchema();

    const normalizedTitle = String(title || "").trim() || "New Chat";
    const normalizedThreadId = threadId ? String(threadId) : null;

    await historyPool.query(
      `
      INSERT INTO chat_conversations (user_id, conversation_id, title, thread_id, messages)
      VALUES ($1, $2, $3, $4, $5::jsonb)
      ON CONFLICT (user_id, conversation_id)
      DO UPDATE SET
        title = EXCLUDED.title,
        thread_id = EXCLUDED.thread_id,
        messages = EXCLUDED.messages,
        updated_at = NOW()
      `,
      [
        req.authUser.userId,
        conversationId,
        normalizedTitle,
        normalizedThreadId,
        JSON.stringify(messages),
      ]
    );

    res.json({ ok: true });
  } catch (error) {
    logger.error("POST /api/chat/history failed: %s", error?.message || error);
    res.status(500).json({ ok: false, error: String(error?.message || error) });
  }
});

app.delete("/api/chat/history/:id", async (req, res) => {
  try {
    if (!requireAuthUser(req, res)) return;
    if (!historyPool) {
      res.status(503).json({ ok: false, error: "Chat history storage is not configured" });
      return;
    }

    await ensureHistorySchema();

    const conversationId = String(req.params.id || "").trim();
    if (!conversationId) {
      res.status(400).json({ ok: false, error: "Missing conversation id" });
      return;
    }

    await historyPool.query(
      `
      DELETE FROM chat_conversations
      WHERE user_id = $1 AND conversation_id = $2
      `,
      [req.authUser.userId, conversationId]
    );

    res.json({ ok: true });
  } catch (error) {
    logger.error("DELETE /api/chat/history/:id failed: %s", error?.message || error);
    res.status(500).json({ ok: false, error: String(error?.message || error) });
  }
});

app.post("/api/chat", async (req, res) => {
  try {
    const t0 = Date.now();
    const { threadId, message, model, title, agent, mode } = req.body || {};
    const role = deriveRole(req);

    if (typeof message !== "string" || !message.trim()) {
      res.status(400).json({ ok: false, error: "Missing 'message'" });
      return;
    }

    const { client } = await getOpencode();

    let sessionId = threadId;
    if (!sessionId) {
      const created = unwrap(
        await client.session.create({
          body: { title: title || "Chat" },
        })
      );
      sessionId = created?.id;
    }

    const body = {
      system: KEC_SYSTEM_PROMPT,
      parts: [{ type: "text", text: message }],
    };

    body.system += `
You must never say that you searched the web, checked online sources, or fetched external data. Such capabilities do not exist.`;

    if ((role === "FACULTY" || role === "ADMIN") && mcpToolPolicy && typeof mcpToolPolicy === "object") {
      body.tools = mcpToolPolicy;
    } else {
      // Students: allow only institution tools (no faculty-only sources) while keeping role guardrails.
      body.tools = mcpToolPolicy || undefined;
      body.system += `

You are answering for a STUDENT.
Do NOT access or reference faculty, staff, HR, policy, or administrative content.
If asked, reply: "Access denied for faculty content."`;
    }

    const allowedServers = allowedMcpServersForRole(role, req);
    if (allowedServers.length) {
      const roleLabel = role === "ADMIN" ? "ADMIN" : role === "FACULTY" ? "FACULTY" : "STUDENT";
      body.system += `

For this ${roleLabel} session, you may use these MCP servers: ${allowedServers.join(",")}.
Consult every available server that is relevant, aggregate their answers, and surface a single concise reply.`;
    }

    if (model && typeof model === "object" && model.providerID && model.modelID) {
      body.model = { providerID: String(model.providerID), modelID: String(model.modelID) };
    } else {
      const defaultModel = await getDefaultChatModel(client);
      if (defaultModel) body.model = defaultModel;
    }

    if (wantsStructuredOutput(message)) {
      body.system += `

If the user asks for tabular output, respond with an HTML <table> element containing appropriate columns based on the data. Use <thead> for headers and <tbody> for rows. Choose column names that match the actual content (e.g., Grade, Travel Mode, Metro DA, Other DA, Duration, etc.). Do not use a fixed schema. Do not include markdown code fences.`;
    }

    const normalizedMode = typeof mode === "string" ? mode.trim().toLowerCase() : "ask";
    if (normalizedMode === "ask") {
      body.agent = "general";
    } else if (agent && typeof agent === "string" && agent.trim()) {
      body.agent = agent.trim();
    }

    const assistant = unwrap(
      await client.session.prompt({
        path: { id: sessionId },
        body,
      })
    );

    const replyText = extractText(assistant?.parts);
    const assistantError = assistant?.info?.error || null;

    res.json({
      ok: true,
      threadId: sessionId,
      reply: replyText,
      assistantError,
      assistant,
    });

    if (DEBUG_CHAT_TIMING) {
      const mid = body?.model ? `${body.model.providerID}/${body.model.modelID}` : "(default)";
      logger.info(
        `[timing] chat_ms=${Date.now() - t0} session=${sessionId} mode=${normalizedMode} agent=${body.agent || "(default)"} model=${mid}`
      );
    }
  } catch (error) {
    logger.error("POST /api/chat failed: %s", error?.message || error);
    res.status(500).json({ ok: false, error: String(error?.message || error) });
  }
});

app.post("/api/chat/generate-title", async (req, res) => {
  try {
    const { messages: chatMessages } = req.body || {};

    // Accept an array of { role, text } messages representing the full conversation
    if (!Array.isArray(chatMessages) || chatMessages.length === 0) {
      return res.status(400).json({ ok: false, error: "Missing 'messages' array" });
    }

    // Build a conversation summary for the LLM to analyze
    const conversationText = chatMessages
      .filter((m) => m && typeof m.text === "string" && m.text.trim())
      .map((m) => `${m.role === "user" ? "User" : "Assistant"}: ${m.text.trim().slice(0, 200)}`)
      .join("\n");

    if (!conversationText.trim()) {
      return res.status(400).json({ ok: false, error: "No valid messages provided" });
    }

    const { client } = await getOpencode();
    const created = unwrap(
      await client.session.create({ body: { title: "Title Generation" } })
    );
    const sessionId = created?.id;

    const body = {
      system: `You are a title generator. Analyze the entire conversation between a user and an assistant. Generate a concise chat history title in exactly 3 to 5 words that summarizes the main topic or intent of the conversation.
Rules:
- Use simple clear words
- Do NOT use any punctuation
- Do NOT use quotes
- Do NOT include filler words like "the", "a", "an", "about", "regarding"
- Do NOT exceed 5 words
- Output ONLY the title, nothing else
- The title should capture the overall conversation theme, not just the first question

Examples:
Conversation about exam rules and eligibility → Exam Eligibility Rules
Conversation about applying for leave → Leave Application Process
Conversation about faculty promotion norms → Faculty Promotion Norms
Conversation about travel allowance policy → Travel Allowance Policy
Conversation about student attendance and results → Student Attendance Results`,
      parts: [{ type: "text", text: `Summarize this conversation in 3-5 words:\n\n${conversationText}` }],
    };

    const defaultModel = await getDefaultChatModel(client);
    if (defaultModel) body.model = defaultModel;

    unwrap(
      await client.session.promptAsync({ path: { id: sessionId }, body })
    );

    // Wait briefly for the model to respond
    const maxWait = 10_000;
    const pollInterval = 500;
    let elapsed = 0;
    let title = "";

    while (elapsed < maxWait) {
      await new Promise((r) => setTimeout(r, pollInterval));
      elapsed += pollInterval;
      try {
        const msgs = unwrap(await client.session.messages({ path: { id: sessionId } }));
        const last = Array.isArray(msgs) ? msgs[msgs.length - 1] : null;
        if (last?.info?.role === "assistant") {
          const raw = extractText(last.parts) || "";
          title = raw
            .replace(/[^a-zA-Z0-9\s]/g, "")
            .trim()
            .split(/\s+/)
            .slice(0, 5)
            .join(" ");
          if (title) break;
        }
      } catch {
        // keep polling
      }
    }

    if (!title) {
      // Fallback: extract keywords from all user messages
      const allUserText = chatMessages
        .filter((m) => m.role === "user" && typeof m.text === "string")
        .map((m) => m.text)
        .join(" ");
      title = allUserText
        .replace(/[^a-zA-Z0-9\s]/g, "")
        .trim()
        .split(/\s+/)
        .filter((w) => w.length > 2 && !["the", "and", "for", "are", "was", "what", "how", "can", "you", "about", "tell", "please"].includes(w.toLowerCase()))
        .slice(0, 4)
        .map((w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase())
        .join(" ") || "New Chat";
    }

    res.json({ ok: true, title });
  } catch (error) {
    logger.error("POST /api/chat/generate-title failed: %s", error?.message || error);
    res.status(500).json({ ok: false, error: String(error?.message || error) });
  }
});

app.post("/api/chat/stream", async (req, res) => {
  res.setHeader("Content-Type", "application/x-ndjson; charset=utf-8");
  res.setHeader("Cache-Control", "no-cache, no-transform");
  res.setHeader("X-Accel-Buffering", "no");

  try {
    const t0 = Date.now();
    const { threadId, message, model, title, agent, mode } = req.body || {};
    const role = deriveRole(req);

    if (typeof message !== "string" || !message.trim()) {
      res.status(400);
      writeNdjson(res, { type: "error", error: "Missing 'message'" });
      res.end();
      return;
    }

    const { client } = await getOpencode();

    let sessionId = threadId;
    if (!sessionId) {
      const created = unwrap(
        await client.session.create({
          body: { title: title || "Chat" },
        })
      );
      sessionId = created?.id;
    }

    const body = {
      system: KEC_SYSTEM_PROMPT,
      parts: [{ type: "text", text: message.trim() }],
    };

    body.system += `
You must never say that you searched the web, checked online sources, or fetched external data. Such capabilities do not exist.`;

    if ((role === "FACULTY" || role === "ADMIN") && mcpToolPolicy && typeof mcpToolPolicy === "object") {
      body.tools = mcpToolPolicy;
    } else {
      body.tools = mcpToolPolicy || undefined;
      body.system += `

You are answering for a STUDENT.
Do NOT access or reference faculty, staff, HR, policy, or administrative content.
If asked, reply: "Access denied for faculty content."`;
    }

    const allowedServers = allowedMcpServersForRole(role, req);
    if (allowedServers.length) {
      const roleLabel = role === "ADMIN" ? "ADMIN" : role === "FACULTY" ? "FACULTY" : "STUDENT";
      body.system += `

For this ${roleLabel} session, you may use these MCP servers: ${allowedServers.join(",")}.
Consult every available server that is relevant, aggregate their answers, and surface a single concise reply.`;
    }

    if (model && typeof model === "object" && model.providerID && model.modelID) {
      body.model = { providerID: String(model.providerID), modelID: String(model.modelID) };
    } else {
      const defaultModel = await getDefaultChatModel(client);
      if (defaultModel) body.model = defaultModel;
    }

    if (wantsStructuredOutput(message)) {
      body.system += `

If the user asks for tabular output, respond with an HTML <table> element containing appropriate columns based on the data. Use <thead> for headers and <tbody> for rows. Choose column names that match the actual content (e.g., Grade, Travel Mode, Metro DA, Other DA, Duration, etc.). Do not use a fixed schema. Do not include markdown code fences.`;
    }
    const normalizedMode = typeof mode === "string" ? mode.trim().toLowerCase() : "ask";
    if (normalizedMode === "ask") {
      body.agent = "general";
    } else if (agent && typeof agent === "string" && agent.trim()) {
      body.agent = agent.trim();
    }

    writeNdjson(res, { type: "meta", threadId: sessionId });

    const abort = new AbortController();
    req.on("close", () => abort.abort());

    // Timeout the streaming request to avoid hanging connections forever.
    const timeoutMs = 120_000;
    const timeoutId = setTimeout(() => abort.abort(), timeoutMs);

    let sawDelta = false;
    let firstDeltaMs = null;
    let aborted = false;
    let sessionError = null;
    let promptError = null;
    const seenToolCalls = new Set();

    try {
      const subscription = await client.event.subscribe({ signal: abort.signal });

      // Start the prompt concurrently; consume the event stream immediately.
      // Awaiting promptAsync here can delay streaming until the request finishes.
      const promptPromise = client.session
        .promptAsync({
          path: { id: sessionId },
          body,
        })
        .catch((e) => {
          promptError = e;
        });

      for await (const evt of subscription.stream) {
        if (!evt || typeof evt !== "object") continue;

        if (evt.type === "message.part.updated") {
          const part = evt.properties?.part;
          const delta = evt.properties?.delta;
          if (
            part &&
            part.sessionID === sessionId &&
            part.type === "text" &&
            typeof delta === "string" &&
            delta
          ) {
            sawDelta = true;
            if (firstDeltaMs === null) firstDeltaMs = Date.now() - t0;
            writeNdjson(res, { type: "delta", text: delta });
          }

          if (part && part.sessionID === sessionId && part.type === "tool") {
            const callId = part.callID || part.id || `${part.tool}-${part.messageID || ""}`;
            if (!seenToolCalls.has(callId)) {
              seenToolCalls.add(callId);
            }
            const status = part.state?.status || "unknown";
            writeNdjson(res, {
              type: "tool",
              callId,
              tool: part.tool,
              status,
              title: part.state?.title,
            });
          }
        }

        if (evt.type === "session.error") {
          const sid = evt.properties?.sessionID;
          if (!sid || sid === sessionId) {
            sessionError = evt.properties?.error || { message: "session.error" };
          }
        }

        if (evt.type === "session.idle" && evt.properties?.sessionID === sessionId) {
          break;
        }
      }

      // Ensure any prompt-level error is observed.
      await promptPromise;
    } catch (e) {
      aborted = abort.signal.aborted;
      if (!aborted) {
        writeNdjson(res, { type: "error", error: String(e?.message || e) });
      }
    } finally {
      clearTimeout(timeoutId);
    }

    if (promptError && !sessionError && !abort.signal.aborted) {
      writeNdjson(res, { type: "assistant_error", error: { message: String(promptError?.message || promptError) } });
    }

    // If we didn't see token deltas (provider may not stream), fetch the final assistant message and emit it.
    if (!sawDelta && !abort.signal.aborted) {
      try {
        const messages = unwrap(await client.session.messages({ path: { id: sessionId } }));
        const last = Array.isArray(messages) ? messages[messages.length - 1] : null;
        const replyText = extractText(last?.parts) || "";
        if (replyText) {
          writeNdjson(res, { type: "delta", text: replyText });
          sawDelta = true;
        }
      } catch (e) {
        logger.debug("Failed to fetch final assistant message: %s", e?.message || e);
      }
    }

    // Ensure tool calls are surfaced even if tool events were not streamed.
    if (!abort.signal.aborted) {
      try {
        const messages = unwrap(await client.session.messages({ path: { id: sessionId } }));
        const last = Array.isArray(messages) ? messages[messages.length - 1] : null;
        const parts = Array.isArray(last?.parts) ? last.parts : [];
        for (const part of parts) {
          if (part && part.type === "tool") {
            const callId = part.callID || part.id || `${part.tool}-${part.messageID || ""}`;
            if (seenToolCalls.has(callId)) continue;
            seenToolCalls.add(callId);
            writeNdjson(res, {
              type: "tool",
              callId,
              tool: part.tool,
              status: part.state?.status || "unknown",
              title: part.state?.title,
            });
          }
        }
      } catch (e) {
        logger.debug("Failed to fetch tool-call info: %s", e?.message || e);
      }
    }

    if (sessionError) {
      writeNdjson(res, { type: "assistant_error", error: sessionError });
    } else if (!sawDelta && aborted) {
      writeNdjson(res, { type: "error", error: `Timed out after ${Math.round(timeoutMs / 1000)}s` });
    }

    writeNdjson(res, { type: "done" });
    res.end();

    if (DEBUG_CHAT_TIMING) {
      const chosenModel = body?.model ? `${body.model.providerID}/${body.model.modelID}` : "(default)";
      logger.info(
        `[timing] stream_total_ms=${Date.now() - t0} first_delta_ms=${firstDeltaMs ?? "null"} saw_delta=${sawDelta} session=${sessionId} mode=${normalizedMode} agent=${body.agent || "(default)"} model=${chosenModel}`
      );
    }
  } catch (error) {
    logger.error("POST /api/chat/stream failed: %s", error?.message || error);
    try {
      res.status(500);
      writeNdjson(res, { type: "error", error: String(error?.message || error) });
      writeNdjson(res, { type: "done" });
      res.end();
    } catch (e) {
      logger.debug("Failed to send error response in stream: %s", e?.message || e);
    }
  }
});

app.listen(API_PORT, () => {
  logger.info("API listening on http://localhost:%d", API_PORT);
  const portHint = OPENCODE_PORT === null ? "auto" : OPENCODE_PORT;
  if (OPENCODE_EAGER_START) {
    logger.info("Starting OpenCode now (target http://%s:%s)", OPENCODE_HOSTNAME, portHint);
    getOpencode().catch((e) => {
      logger.error("Failed to start OpenCode:", e);
      logger.error("If you want to start OpenCode only when needed, set OPENCODE_EAGER_START=0");
    });
  } else {
    logger.info("OpenCode server is started lazily on first /api/* call (target http://%s:%s)", OPENCODE_HOSTNAME, portHint);
  }
});
