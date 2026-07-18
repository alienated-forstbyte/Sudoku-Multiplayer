#!/usr/bin/env python3
"""Start all services locally (no Docker, in-memory mode)."""
import subprocess, sys, time, os, signal

project = os.path.dirname(os.path.abspath(__file__))
venv_python = os.path.join(project, ".venv", "bin", "python")

procs = []

def start(name, cmd, env=None):
    e = {**os.environ, **(env or {})}
    p = subprocess.Popen(cmd, env=e, stdout=open(f"/tmp/{name}.log", "w"),
                         stderr=subprocess.STDOUT, cwd=project)
    procs.append((name, p))
    print(f"  {name}: PID {p.pid}")
    return p

print("Starting services...")
start("ml", [venv_python, "-m", "uvicorn", "ml_service.app:app",
             "--host", "0.0.0.0", "--port", "8001"])
start("blockchain", [venv_python, "-m", "uvicorn", "blockchain.app:app",
                     "--host", "0.0.0.0", "--port", "8002"])

time.sleep(2)

start("game", [venv_python, "-m", "uvicorn", "server.main:app",
               "--host", "0.0.0.0", "--port", "8000"], env={
    "ML_SERVICE_URL": "http://127.0.0.1:8001",
    "BLOCKCHAIN_SERVICE_URL": "http://127.0.0.1:8002",
    "REDIS_URL": "",
    "GAME_TIME_LIMIT_SECONDS": "30",
    "ROOM_EXPIRY_SECONDS": "15",
})

time.sleep(2)

for name, _ in procs:
    log = open(f"/tmp/{name}.log").read().strip().split("\n")
    print(f"\n=== {name} (last 3 lines) ===")
    for line in log[-3:]:
        print(f"  {line}")

print("\nAll services running. Ctrl+C to stop.")
print("Open http://localhost:8000 in your browser")

try:
    while True:
        time.sleep(1)
        for name, p in procs:
            if p.poll() is not None:
                print(f"\n{name} (PID {p.pid}) exited with code {p.returncode}")
                sys.exit(1)
except KeyboardInterrupt:
    print("\nShutting down...")
    for name, p in procs:
        p.terminate()
    for name, p in procs:
        p.wait(timeout=5)
    print("Done.")
