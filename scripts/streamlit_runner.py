from __future__ import annotations

import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEPS = ROOT / ".streamlit_deps"

sys.path.insert(0, str(DEPS))
os.chdir(ROOT)

from streamlit.web.cli import main  # noqa: E402


sys.argv = [
    "streamlit",
    "run",
    str(ROOT / "streamlit_app.py"),
    "--global.developmentMode",
    "false",
    "--server.port",
    "8502",
    "--server.address",
    "127.0.0.1",
    "--server.headless",
    "true",
    "--server.fileWatcherType",
    "none",
]

raise SystemExit(main())
