"""Quick script to restart Daphne server"""
import psutil
import subprocess
import time
import sys

# Find and kill process on port 8002
for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
    try:
        cmdline = proc.cmdline()
        if cmdline and 'daphne' in ' '.join(cmdline) and '8002' in ' '.join(cmdline):
            print(f"Killing PID {proc.pid}: {' '.join(cmdline)}")
            proc.kill()
            proc.wait(timeout=5)
            print(f"Process {proc.pid} terminated")
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired):
        pass

# Wait for port to be free
time.sleep(2)

# Start new server
print("Starting new Daphne server...")
subprocess.Popen([
    sys.executable, '-m', 'daphne',
    '-b', '0.0.0.0',
    '-p', '8002',
    'backend.asgi:application'
])
print("Server restarted!")
