"""Start the local database and frontend when running the development API."""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import make_url

from app.core.config import settings
from app.core.database import engine


REPO_ROOT = Path(__file__).resolve().parents[3]
FRONTEND_DIR = REPO_ROOT / "Frontend"
VITE_ENTRY = FRONTEND_DIR / "node_modules" / "vite" / "bin" / "vite.js"
LOCAL_DIR = REPO_ROOT / ".local"
FRONTEND_URL = "http://127.0.0.1:5173/"
_frontend_process: subprocess.Popen | None = None


def _database_address() -> tuple[str, int]:
    url = make_url(settings.database_url)
    return url.host or "127.0.0.1", url.port or 5432


def _tcp_is_open(host: str, port: int, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _database_connection_works() -> bool:
    try:
        with engine.connect() as connection:
            return connection.execute(text("SELECT 1")).scalar_one() == 1
    except Exception:
        return False


def _start_installed_postgres_service(host: str) -> str | None:
    """On Windows, start PostgreSQL when exactly one local service is installed."""
    if sys.platform != "win32" or host.lower() not in {"localhost", "127.0.0.1", "::1"}:
        return None

    powershell = shutil.which("powershell.exe")
    if not powershell:
        return None

    command = (
        "$services = @(Get-Service -Name 'postgresql*' -ErrorAction SilentlyContinue); "
        "if ($services.Count -ne 1) { exit 3 }; "
        "$service = $services[0]; "
        "if ($service.Status -ne 'Running') { "
        "Start-Service -Name $service.Name; "
        "$service.WaitForStatus('Running', [TimeSpan]::FromSeconds(30)) "
        "}; "
        "[Console]::Out.Write($service.Name)"
    )
    result = subprocess.run(
        [powershell, "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", command],
        capture_output=True,
        text=True,
        timeout=35,
        check=False,
    )
    service_name = result.stdout.strip()
    if result.returncode != 0 or not service_name:
        return None
    print(f"[local] PostgreSQL Windows service is ready: {service_name}")
    return service_name


def _start_bundled_postgres(host: str, port: int) -> bool:
    pg_ctl = REPO_ROOT / ".local" / "postgres" / "pgsql" / "bin" / "pg_ctl.exe"
    if not pg_ctl.exists() or host.lower() not in {"localhost", "127.0.0.1", "::1"}:
        return False

    data_dir = LOCAL_DIR / "pgdata"
    if not data_dir.exists():
        return False

    LOCAL_DIR.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [
            str(pg_ctl),
            "-D",
            str(data_dir),
            "-l",
            str(LOCAL_DIR / "postgres-server.log"),
            "-o",
            f"-h 127.0.0.1 -p {port}",
            "start",
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if result.returncode != 0 and not _tcp_is_open(host, port):
        details = (result.stderr or result.stdout).strip()
        raise RuntimeError(f"Could not start bundled PostgreSQL: {details or 'pg_ctl failed'}")
    print(f"[local] PostgreSQL is available on {host}:{port}")
    return True


def _ensure_database() -> None:
    host, port = _database_address()
    if not _tcp_is_open(host, port):
        _start_installed_postgres_service(host)
    if not _tcp_is_open(host, port):
        _start_bundled_postgres(host, port)

    if not _tcp_is_open(host, port):
        raise RuntimeError(
            f"PostgreSQL is not available at {host}:{port}. Start the server configured by DATABASE_URL in backend/.env."
        )
    if not _database_connection_works():
        raise RuntimeError(
            f"PostgreSQL accepts connections at {host}:{port}, but the configured database credentials or database are unavailable."
        )
    print(f"[local] Database connection is ready at {host}:{port}")


def _frontend_is_ready() -> bool:
    try:
        with urllib.request.urlopen(FRONTEND_URL, timeout=1) as response:
            document = response.read(16_384)
            return (
                response.status == 200
                and b"/@vite/client" in document
                and b"<title>Neonatal Monitor</title>" in document
                and b"/src/main.jsx" in document
            )
    except (OSError, urllib.error.URLError):
        return False


def _ensure_frontend() -> None:
    global _frontend_process

    if _frontend_is_ready():
        print("[local] Frontend is already running at http://127.0.0.1:5173")
        return
    if not VITE_ENTRY.exists():
        raise RuntimeError("Frontend dependencies are missing. Run `npm ci` in the Frontend directory.")
    node = shutil.which("node")
    if not node:
        raise RuntimeError("Node.js is required to start the frontend. Install Node.js and try again.")

    LOCAL_DIR.mkdir(parents=True, exist_ok=True)
    with (LOCAL_DIR / "frontend.stdout.log").open("ab") as stdout_log:
        _frontend_process = subprocess.Popen(
            [node, str(VITE_ENTRY), "--host", "127.0.0.1", "--port", "5173", "--strictPort"],
            cwd=FRONTEND_DIR,
            stdout=stdout_log,
            stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

    for _ in range(30):
        if _frontend_is_ready():
            print("[local] Frontend is ready at http://127.0.0.1:5173")
            return
        if _frontend_process.poll() is not None:
            break
        time.sleep(1)

    stop_local_services()
    raise RuntimeError("Frontend did not start. Check .local/frontend.stdout.log for details.")


def start_local_services() -> None:
    """Ensure PostgreSQL and the Vite development server are ready."""
    if settings.environment != "development" or os.getenv("PYTEST_CURRENT_TEST"):
        return
    _ensure_database()
    _ensure_frontend()


def stop_local_services() -> None:
    """Stop the frontend process started by this backend process."""
    global _frontend_process

    if _frontend_process is None:
        return
    if _frontend_process.poll() is None:
        _frontend_process.terminate()
        try:
            _frontend_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _frontend_process.kill()
            _frontend_process.wait(timeout=5)
    _frontend_process = None
