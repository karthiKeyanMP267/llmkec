/**
 * Client-side logger utility.
 * Wraps console methods so the rest of the code never calls console.* directly.
 * In production the level can be raised via the LOG_LEVEL key in localStorage.
 */

const LEVELS = { error: 0, warn: 1, info: 2, debug: 3 }

function currentLevel() {
  try {
    const stored = localStorage.getItem('LOG_LEVEL')
    if (stored && LEVELS[stored] !== undefined) return LEVELS[stored]
  } catch {
    // localStorage unavailable (SSR, iframe sandbox, etc.)
  }
  return LEVELS.info // default
}

function timestamp() {
  return new Date().toISOString()
}

const logger = {
  error(...args) {
    if (currentLevel() >= LEVELS.error) console.error(`[${timestamp()}] ERROR`, ...args)
  },
  warn(...args) {
    if (currentLevel() >= LEVELS.warn) console.warn(`[${timestamp()}] WARN`, ...args)
  },
  info(...args) {
    if (currentLevel() >= LEVELS.info) console.info(`[${timestamp()}] INFO`, ...args)
  },
  debug(...args) {
    if (currentLevel() >= LEVELS.debug) console.debug(`[${timestamp()}] DEBUG`, ...args)
  },
}

export default logger
