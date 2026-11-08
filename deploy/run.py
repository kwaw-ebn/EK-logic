"""Supervise both processes in a single container; fail if either exits."""
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def commands(port):
    return [
        ([sys.executable, '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8000'], ROOT / 'backend'),
        (['node', 'node_modules/next/dist/bin/next', 'start', '--hostname', '0.0.0.0', '--port', str(port)], ROOT / 'frontend'),
    ]


def main():
    port = int(os.environ.get('PORT', '10000'))
    if not 1 <= port <= 65535 or port == 8000:
        raise RuntimeError('PORT must be a valid public port different from internal API port 8000')
    subprocess.run([sys.executable, '-m', 'alembic', 'upgrade', 'head'], cwd=ROOT / 'backend', check=True)
    children = []
    stopping = False

    def stop(signum, frame):
        nonlocal stopping
        stopping = True
        for child in children:
            if child.poll() is None:
                child.terminate()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    exit_code = 0
    try:
        for command, directory in commands(port):
            children.append(subprocess.Popen(command, cwd=directory))
        while not stopping:
            for child in children:
                if child.poll() is not None:
                    # An unexpected clean exit still means the service is unavailable.
                    exit_code = child.returncode or 1
                    stopping = True
                    break
            if not stopping:
                time.sleep(.2)
    finally:
        stop(None, None)
        for child in children:
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
    return exit_code


if __name__ == '__main__':
    sys.exit(main())
