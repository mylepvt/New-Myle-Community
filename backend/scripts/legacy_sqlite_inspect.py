#!/usr/bin/env python3
"""
Read-only inspection of a legacy Flask Myle SQLite database (leads.db).

Usage:
  LEGACY_SQLITE_PATH=/path/to/leads.db python scripts/legacy_sqlite_inspect.py

From repo root:
  cd backend && LEGACY_SQLITE_PATH=... python scripts/legacy_sqlite_inspect.py
"""
from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path


def main() -> int:
    raw = os.environ.get("LEGACY_SQLITE_PATH", "").strip()
    if not raw:
        print(
            "Set LEGACY_SQLITE_PATH to your legacy leads.db file.",
            file=sys.stderr,
        )
        return 1
    path = Path(raw).expanduser().resolve()
    if not path.is_file():
        print(f"Not a file: {path}", file=sys.stderr)
        return 1

    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = [r[0] for r in cur.fetchall()]
        print(f"Database: {path}")
        print(f"Tables ({len(tables)}): {', '.join(tables)}")
        for t in tables:
            try:
                n = conn.execute(f'SELECT COUNT(*) AS c FROM "{t}"').fetchone()[0]
            except sqlite3.Error as e:
                n = f"<error: {e}>"
            print(f"  {t}: {n}")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
