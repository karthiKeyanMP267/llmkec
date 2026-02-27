"""Start all ingestion API instances (main, student_2024, faculty) in one command.

Usage:
    python run_all_ingestions.py

Optional environment overrides:
    MAIN_INGESTION_PORT (default: 9000)
"""

from __future__ import annotations

import logging
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent


def load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def start_instance(name: str, env_file: Path, extra_env: dict[str, str] | None = None) -> subprocess.Popen:
    env = os.environ.copy()
    env.update(load_env_file(env_file))
    if extra_env:
        env.update(extra_env)

    process = subprocess.Popen(
        [sys.executable, "run_ingestion.py"],
        cwd=str(ROOT),
        env=env,
    )
    port = env.get("API_PORT", "8000")
    logger.info("[started] %s on port %s (pid=%s)", name, port, process.pid)
    return process


def stop_process(process: subprocess.Popen):
    if process.poll() is not None:
        return
    try:
        process.terminate()
        process.wait(timeout=8)
    except Exception as e:
        logger.debug("Graceful termination failed, killing process: %s", e)
        process.kill()


def main():
    instances: list[tuple[str, Path, dict[str, str]]] = [
        (
            "main",
            ROOT / ".env",
            {
                "API_PORT": os.getenv("MAIN_INGESTION_PORT", "9000"),
                "API_RELOAD": "false",
            },
        ),
        ("student_2024", ROOT / "student_2024" / ".env.ingestion", {"API_RELOAD": "false"}),
        ("faculty", ROOT / "faculty" / ".env.ingestion", {"API_RELOAD": "false"}),
    ]

    processes: list[subprocess.Popen] = []
    try:
        for name, env_file, extra_env in instances:
            processes.append(start_instance(name, env_file, extra_env))

        logger.info("All ingestion instances started. Press Ctrl+C to stop all.")
        while True:
            if any(p.poll() is not None for p in processes):
                for idx, proc in enumerate(processes):
                    if proc.poll() is not None:
                        logger.warning("[exited] %s exited with code %s", instances[idx][0], proc.returncode)
                break
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Stopping ingestion instances...")
    finally:
        for proc in processes:
            stop_process(proc)


if __name__ == "__main__":
    if sys.platform.startswith("win"):
        signal.signal(signal.SIGINT, signal.SIG_DFL)
    main()
