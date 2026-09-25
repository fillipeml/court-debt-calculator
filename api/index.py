"""Serverless entry point (Vercel): exposes the FastAPI app.

The API project's root directory is the repository root; `vercel.json` routes everything to
this function and bundles the engine (`src/`) and the versioned indices (`indices/data`).
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from debt_api.main import app  # noqa: E402,F401  (ASGI app served by the Python runtime)
