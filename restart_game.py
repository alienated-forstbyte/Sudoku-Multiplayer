#!/usr/bin/env python3
"""Restart the game server only (ML and blockchain stay running)."""
import subprocess, os, signal, time

project = os.path.dirname(os.path.abspath(__file__))
venv_python = os.path.join(project, ".venv", "bin", "python")

# Kill old game server
try:
    subprocess.run(["pkill", "-f", "uvicorn server.main"], check=False)
    time.sleep(1)
except Exception:
    pass

env = {
    **os.environ,
    "ML_SERVICE_URL": "http://127.0.0.1:8001",
    "BLOCKCHAIN_SERVICE_URL": "http://127.0.0.1:8002",
    "REDIS_URL": "",
    "GAME_TIME_LIMIT_SECONDS": "30",
    "ROOM_EXPIRY_SECONDS": "15",
}

log = open("/tmp/game_server.log", "w")
p = subprocess.Popen(
    [venv_python, "-m", "uvicorn", "server.main:app",
     "--host", "0.0.0.0", "--port", "8000"],
    env=env, stdout=log, stderr=subprocess.STDOUT, cwd=project,
    start_new_session=True,
)

time.sleep(2)
print(f"Game server restarted: PID {p.pid}")
tail = open("/tmp/game_server.log").read().strip().split("\n")
for line in tail[-3:]:
    print(f"  {line}")
