#!/usr/bin/env python3
"""
Development server startup script.

Usage:
  python run.py              -- starts API only
  python run.py --profiler   -- starts Redis (docker), profiler worker, and API
"""

import argparse
import signal
import subprocess  # nosec B404 - Used for docker compose and worker process; no user input
import sys
from pathlib import Path

import uvicorn

from app.core.config import settings

_PROJECT_ROOT = Path(__file__).resolve().parent
_DOCKER_COMPOSE_PATH = _PROJECT_ROOT / "docker-compose.profiler-dev.yml"

_worker_process: subprocess.Popen | None = None


def _start_redis() -> bool:
    """Start Redis via docker-compose. Returns True on success."""
    cmd = [
        "docker",
        "compose",
        "-f",
        str(_DOCKER_COMPOSE_PATH),
        "up",
        "-d",
        "redis",
    ]
    result = subprocess.run(
        cmd, cwd=_PROJECT_ROOT, capture_output=True, text=True
    )  # nosec B603 - cmd is hardcoded; path from project root
    if result.returncode != 0:
        print(
            f"Failed to start Redis: {result.stderr or result.stdout}", file=sys.stderr
        )
        return False
    print("Redis started (docker-compose.profiler-dev.yml)")
    return True


def _start_profiler_worker() -> subprocess.Popen | None:
    """Start profiler worker in background. Returns Popen or None on failure."""
    cmd = [sys.executable, "-m", "app.profiler.workers.run_profiler_worker"]
    try:
        proc = subprocess.Popen(  # nosec B603 - cmd uses sys.executable and fixed module path
            cmd,
            cwd=_PROJECT_ROOT,
            stdout=sys.stdout,
            stderr=sys.stderr,
        )
        print(f"Profiler worker started (PID {proc.pid})")
        return proc
    except Exception as e:
        print(f"Failed to start profiler worker: {e}", file=sys.stderr)
        return None


def _shutdown_worker(signum=None, frame=None):
    global _worker_process
    if _worker_process and _worker_process.poll() is None:
        _worker_process.terminate()
        _worker_process.wait()
        print("Profiler worker stopped")
    if signum is not None:
        sys.exit(0)


def main():
    global _worker_process

    parser = argparse.ArgumentParser(
        description="Development server startup script",
    )
    parser.add_argument(
        "--profiler",
        action="store_true",
        help="Start profiler stack: Redis (docker), profiler worker, and API",
    )
    args = parser.parse_args()

    if args.profiler:
        if not _start_redis():
            sys.exit(1)
        _worker_process = _start_profiler_worker()
        if _worker_process is None:
            sys.exit(1)
        signal.signal(signal.SIGINT, _shutdown_worker)
        signal.signal(signal.SIGTERM, _shutdown_worker)

    try:
        uvicorn.run(
            "app.main:app",
            host="0.0.0.0",  # nosec B104 - Development server, binding to all interfaces is acceptable
            port=8000,
            reload=True,
            log_level=settings.LOG_LEVEL.lower(),
        )
    finally:
        if args.profiler and _worker_process and _worker_process.poll() is None:
            _worker_process.terminate()
            _worker_process.wait()
            print("Profiler worker stopped")


if __name__ == "__main__":
    main()
