"""Vercel entrypoint for the existing FastAPI prototype."""

import sys
from pathlib import Path


backend_dir = Path(__file__).resolve().parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.main import app  # noqa: E402,F401
