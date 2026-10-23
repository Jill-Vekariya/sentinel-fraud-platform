"""Exercise the real dashboard against a disposable, loopback-only API."""

import os
import secrets
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix="sentinel-dashboard-") as directory:
        temporary = Path(directory)
        env = os.environ.copy()
        env.update(
            DATA_DIR=str(temporary / "data"),
            MODEL_DIR=str(temporary / "models"),
            REDIS_URL="",
            API_KEY=secrets.token_urlsafe(24),
        )
        # Reserve an available address instead of disturbing a running demo on port 8000.
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        url = f"http://127.0.0.1:{port}"
        with (temporary / "backend.log").open("w", encoding="utf-8") as log:
            subprocess.run(
                [sys.executable, "-m", "fraud.train", "--promote"],
                cwd=root,
                env=env,
                stdout=log,
                stderr=log,
                check=True,
                timeout=180,
            )
            server = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "fraud.api:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(port),
                ],
                cwd=root,
                env=env,
                stdout=log,
                stderr=log,
            )
            try:
                deadline = time.monotonic() + 45
                while True:
                    if server.poll() is not None:
                        raise RuntimeError("Temporary API exited before becoming ready")
                    try:
                        with urllib.request.urlopen(url + "/health/ready", timeout=1):
                            break
                    except (urllib.error.URLError, TimeoutError):
                        if time.monotonic() >= deadline:
                            raise TimeoutError("Temporary API did not become ready") from None
                        time.sleep(0.1)
                env.update(SENTINEL_TEST_URL=url, SENTINEL_TEST_API_KEY=env["API_KEY"])
                return subprocess.run(
                    ["node", "tests/dashboard.integration.cjs"],
                    cwd=root,
                    env=env,
                    check=False,
                    timeout=60,
                ).returncode
            finally:
                server.terminate()
                try:
                    server.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait()


if __name__ == "__main__":
    raise SystemExit(main())
