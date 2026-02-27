/**
 * Lightweight logger for production deployment.
 * Outputs structured, timestamped log lines to stdout/stderr
 * so they are captured by systemd, pm2, Docker, etc.
 */

import { format } from "node:util";

const LOG_LEVEL = (process.env.LOG_LEVEL || "info").toLowerCase();

const LEVELS = { error: 0, warn: 1, info: 2, debug: 3 };
const currentLevel = LEVELS[LOG_LEVEL] ?? LEVELS.info;

function ts() {
  return new Date().toISOString();
}

const logger = {
  error(...args) {
    if (currentLevel >= LEVELS.error) {
      process.stderr.write(`[${ts()}] ERROR: ${format(...args)}\n`);
    }
  },
  warn(...args) {
    if (currentLevel >= LEVELS.warn) {
      process.stderr.write(`[${ts()}] WARN: ${format(...args)}\n`);
    }
  },
  info(...args) {
    if (currentLevel >= LEVELS.info) {
      process.stdout.write(`[${ts()}] INFO: ${format(...args)}\n`);
    }
  },
  debug(...args) {
    if (currentLevel >= LEVELS.debug) {
      process.stdout.write(`[${ts()}] DEBUG: ${format(...args)}\n`);
    }
  },
};

export default logger;
