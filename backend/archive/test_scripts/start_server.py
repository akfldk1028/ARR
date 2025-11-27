import subprocess
import sys

if __name__ == "__main__":
    subprocess.run([
        sys.executable,
        "-m",
        "daphne",
        "-b", "0.0.0.0",
        "-p", "8000",
        "backend.asgi:application"
    ])
