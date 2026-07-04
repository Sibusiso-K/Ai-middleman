"""
start_all.py — One-command startup for the local demo/dev stack: Docker
Postgres, the FastAPI backend, and the ngrok tunnel, each health-checked
before moving on to the next.

Exists because these are three independent, easy-to-forget processes — a
real scare during demo prep was ngrok dying silently mid-session while the
API and DB stayed perfectly healthy, and the dashboard falsely showed
everything "offline" as a result. This script starts whatever's missing,
skips whatever's already running (safe to re-run any time), and prints a
clear go/no-go summary instead of three terminals of subprocess mush.

Usage:
    python scripts/start_all.py
"""

import os
import subprocess
import sys
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / ".env")

DB_CONTAINER = "ai-middleman-db-1"
API_PORT = int(os.getenv("PORT", "8000"))
API_HEALTH_URL = f"http://localhost:{API_PORT}/health"
NGROK_DOMAIN = os.getenv("NGROK_DOMAIN", "plating-marmalade-outthink.ngrok-free.dev")
TUNNEL_HEALTH_URL = f"https://{NGROK_DOMAIN}/health"
NGROK_BYPASS_HEADERS = {"ngrok-skip-browser-warning": "true"}

POLL_INTERVAL_SECONDS = 1.0
POLL_TIMEOUT_SECONDS = 30
# New, detached console windows on Windows so the API/tunnel keep running
# after this script exits; plain background processes elsewhere.
_DETACHED = subprocess.CREATE_NEW_CONSOLE if os.name == "nt" else 0


def _ok(msg: str) -> None:
    print(f"  [OK] {msg}")


def _already_healthy(url: str, headers: dict | None = None, attempts: int = 3) -> bool:
    """A single flaky check here is dangerous, not just wrong: if it
    falsely reports "not running" for the tunnel, we'd launch a second
    ngrok session on the same reserved domain — free-tier ngrok allows only
    one, so that risks killing the working tunnel instead of just failing
    to add a redundant one. Retry a few times before concluding "start it"."""
    for attempt in range(attempts):
        try:
            if httpx.get(url, headers=headers or {}, timeout=5.0).status_code == 200:
                return True
        except httpx.HTTPError:
            pass
        if attempt < attempts - 1:
            time.sleep(1.5)
    return False


def _wait_healthy(label: str, url: str, headers: dict | None = None) -> bool:
    print(f"  Waiting for {label} ...", end="", flush=True)
    deadline = time.time() + POLL_TIMEOUT_SECONDS
    while time.time() < deadline:
        try:
            if httpx.get(url, headers=headers or {}, timeout=5.0).status_code == 200:
                print(" up")
                return True
        except httpx.HTTPError:
            pass
        print(".", end="", flush=True)
        time.sleep(POLL_INTERVAL_SECONDS)
    print(" TIMED OUT")
    return False


def start_database() -> bool:
    print("1. Database (Docker Postgres)")
    inspect = subprocess.run(
        ["docker", "inspect", "-f", "{{.State.Running}}", DB_CONTAINER],
        capture_output=True, text=True,
    )
    if inspect.returncode == 0 and inspect.stdout.strip() == "true":
        _ok(f"{DB_CONTAINER} already running")
        return True

    print(f"  Starting {DB_CONTAINER} ...")
    started = subprocess.run(["docker", "start", DB_CONTAINER], capture_output=True, text=True)
    if started.returncode != 0:
        print(f"  [FAIL] Could not start {DB_CONTAINER}: {started.stderr.strip()}")
        print(f"  If the container has never been created, run: docker compose up -d  (from {ROOT})")
        return False
    time.sleep(2)  # Postgres needs a moment after container start before accepting connections
    _ok(f"{DB_CONTAINER} started")
    return True


def start_api() -> bool:
    print("2. API (uvicorn)")
    if _already_healthy(API_HEALTH_URL):
        _ok(f"already healthy at {API_HEALTH_URL}")
        return True

    print("  Starting uvicorn ...")
    subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(API_PORT)],
        cwd=ROOT, creationflags=_DETACHED,
    )
    return _wait_healthy(f"API at {API_HEALTH_URL}", API_HEALTH_URL)


def start_tunnel() -> bool:
    print("3. ngrok tunnel")
    if _already_healthy(TUNNEL_HEALTH_URL, headers=NGROK_BYPASS_HEADERS):
        _ok(f"already healthy at {TUNNEL_HEALTH_URL}")
        return True

    print("  Starting dev_tunnel.py ...")
    subprocess.Popen(
        [sys.executable, "dev_tunnel.py"],
        cwd=ROOT, creationflags=_DETACHED,
    )
    return _wait_healthy(f"tunnel at {TUNNEL_HEALTH_URL}", TUNNEL_HEALTH_URL, headers=NGROK_BYPASS_HEADERS)


def main() -> None:
    print("=" * 60)
    print("AI Middleman — starting the full local stack")
    print("=" * 60)

    db_ok = start_database()
    api_ok = start_api() if db_ok else False
    tunnel_ok = start_tunnel() if api_ok else False

    print()
    print("=" * 60)
    if db_ok and api_ok and tunnel_ok:
        print("ALL SYSTEMS GO")
        print(f"  API:      http://localhost:{API_PORT}")
        print(f"  Tunnel:   https://{NGROK_DOMAIN}")
        print("  Now start the frontend separately: cd frontend && npm run dev")
    else:
        print("NOT READY — see [FAIL] / TIMED OUT messages above")
        sys.exit(1)
    print("=" * 60)


if __name__ == "__main__":
    main()
