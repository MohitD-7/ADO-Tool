from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYTHON = Path(r"C:\Users\Lenovo\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe")
DEPS = ROOT / ".streamlit_deps"
LOG = ROOT / "work" / "streamlit.server.log"


def main() -> int:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["PYTHONPATH"] = str(DEPS)
    env["PYTHONUNBUFFERED"] = "1"

    args = [
        str(PYTHON),
        str(ROOT / "scripts" / "streamlit_runner.py"),
    ]

    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS

    with LOG.open("ab", buffering=0) as log:
        process = subprocess.Popen(
            args,
            cwd=ROOT,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            creationflags=creationflags,
            close_fds=True,
        )

    print(f"started pid={process.pid}")
    print(f"log={LOG}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
