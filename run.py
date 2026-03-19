"""
run.py — Start all servers for the Android MDM WebApp.

Servers started:
  Port 5000  — User dashboard     (user/app.py)
  Port 5002  — Admin panel        (admin/app.py)
  Port 8000  — API server         (apis/app.py)
  Port 5001  — Streaming server   (streaming-server/app.py)  [optional]

Usage:
  python run.py             # start all servers
  python run.py --no-stream # skip the streaming server
"""

import subprocess
import sys
import os
import signal
import argparse
import time

ROOT = os.path.dirname(os.path.abspath(__file__))

SERVERS = [
    {
        "name": "User App",
        "cmd": [sys.executable, os.path.join(ROOT, "user", "app.py")],
        "port": 5000,
    },
    {
        "name": "Admin App",
        "cmd": [sys.executable, os.path.join(ROOT, "admin", "app.py")],
        "port": 5002,
    },
    {
        "name": "API Server",
        "cmd": [sys.executable, os.path.join(ROOT, "apis", "app.py")],
        "port": 8000,
    },
]

STREAM_SERVER = {
    "name": "Streaming Server",
    "cmd": [
        sys.executable,
        os.path.join(ROOT, "streaming-server", "app.py"),
        "--port", "5001",
    ],
    "port": 5001,
}


def main():
    parser = argparse.ArgumentParser(description="Start all MDM WebApp servers")
    parser.add_argument(
        "--no-stream",
        action="store_true",
        help="Skip the Socket.IO streaming server",
    )
    args = parser.parse_args()

    servers = list(SERVERS)
    if not args.no_stream:
        servers.append(STREAM_SERVER)

    processes = []

    print("Starting servers...\n")
    for srv in servers:
        print(f"  [{srv['name']}] port {srv['port']} → {' '.join(srv['cmd'])}")
        proc = subprocess.Popen(
            srv["cmd"],
            cwd=ROOT,
            env={**os.environ, "PYTHONPATH": ROOT},
        )
        processes.append((srv["name"], proc))
        time.sleep(0.3)  # stagger starts slightly

    print(f"\n{len(processes)} servers running. Press Ctrl+C to stop all.\n")

    def shutdown(sig, frame):
        print("\nShutting down all servers...")
        for name, proc in processes:
            proc.terminate()
            print(f"  Stopped [{name}]")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # Wait for any process to exit unexpectedly
    while True:
        for name, proc in processes:
            ret = proc.poll()
            if ret is not None:
                print(f"\n[{name}] exited with code {ret}. Stopping all servers.")
                shutdown(None, None)
        time.sleep(2)


if __name__ == "__main__":
    main()
