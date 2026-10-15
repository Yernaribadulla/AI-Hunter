"""Start local services, then the operator; clean up only child processes we own."""

import argparse
import socket
import subprocess
import sys
import time
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cli", action="store_true")
    parser.add_argument("--services-only", action="store_true")
    args = parser.parse_args()
    children = []
    try:
        for name, port in [("analysis", 8011), ("history", 8012)]:
            with socket.socket() as probe:
                if probe.connect_ex(("127.0.0.1", port)) == 0:
                    raise RuntimeError(
                        f"Port {port} is occupied; use the existing services or stop them first"
                    )
            process = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    f"services.{name}:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(port),
                ],
                cwd=ROOT,
            )
            children.append(process)
            deadline = time.monotonic() + 20
            while True:
                if process.poll() is not None:
                    raise RuntimeError(f"{name} exited during startup")
                try:
                    response = requests.get(
                        f"http://127.0.0.1:{port}/health", timeout=1
                    )
                    response.raise_for_status()
                    if response.json().get("service") == name:
                        break
                except requests.RequestException:
                    pass
                if time.monotonic() > deadline:
                    raise RuntimeError(f"{name} startup timed out")
                time.sleep(0.2)
        if args.services_only:
            while all(p.poll() is None for p in children):
                time.sleep(0.5)
            return 1
        operator = subprocess.Popen(
            [sys.executable, "apply.py" if args.cli else "desktop.py"], cwd=ROOT
        )
        children.append(operator)
        return operator.wait()
    except KeyboardInterrupt:
        return 130
    finally:
        for process in reversed(children):
            if process.poll() is None:
                process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


if __name__ == "__main__":
    raise SystemExit(main())
