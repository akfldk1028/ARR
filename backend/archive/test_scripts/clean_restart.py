"""Clean server restart with startup verification"""
import subprocess
import time
import sys

def kill_process_on_port(port=8002):
    """Kill process listening on specified port"""
    print(f"Checking for processes on port {port}...")

    # Find process
    result = subprocess.run(
        f'netstat -ano | findstr :{port}',
        shell=True,
        capture_output=True,
        text=True
    )

    if result.stdout:
        lines = result.stdout.strip().split('\n')
        pids_killed = set()

        for line in lines:
            if 'LISTENING' in line:
                parts = line.split()
                pid = parts[-1]

                if pid not in pids_killed:
                    print(f"  Killing PID {pid}...")
                    subprocess.run(f'taskkill /F /PID {pid}', shell=True, capture_output=True)
                    pids_killed.add(pid)

        print(f"  Killed {len(pids_killed)} process(es)")
        time.sleep(2)
    else:
        print(f"  No process found on port {port}")

def start_server():
    """Start Daphne server in foreground"""
    print("\nStarting Daphne server...")
    print("=" * 60)

    # Start server (will run in foreground)
    subprocess.run([
        sys.executable, '-m', 'daphne',
        '-b', '0.0.0.0',
        '-p', '8002',
        'backend.asgi:application'
    ])

if __name__ == "__main__":
    try:
        kill_process_on_port(8002)
        start_server()
    except KeyboardInterrupt:
        print("\n\nServer stopped by user")
        sys.exit(0)
