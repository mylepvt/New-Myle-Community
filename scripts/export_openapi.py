#!/usr/bin/env python3
"""Write FastAPI OpenAPI JSON to frontend/openapi.json (no running server)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from main import app  # noqa: E402

OUT = ROOT / "frontend" / "openapi.json"
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(app.openapi(), indent=2), encoding="utf-8")
print(f"Wrote {OUT}", file=sys.stderr)
