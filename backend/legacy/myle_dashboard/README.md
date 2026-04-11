# Legacy Myle Dashboard (Flask + SQLite)

These files are **copied from the old monolith** for **reference and phased porting**. They are **not** imported by the Myle vl2 FastAPI app at runtime.

## What’s here

| File | Role |
|------|------|
| `database.py` | SQLite `init_db`, `migrate_db`, seeds, Flask `get_db()` request scope |
| `app.py` | Flask routes, sessions, helpers, Maya/push, etc. |

## Why not “just run” them?

- **vl2** uses **FastAPI + async SQLAlchemy + PostgreSQL + Alembic** (`backend/app/`, `backend/main.py`).
- The legacy app expects **Flask**, **Jinja templates**, sibling modules (`helpers.py`, `auth_context.py`, `services/`, …), and **SQLite** file `leads.db`.
- Dropping this `app.py` into vl2 would require the **entire old tree** and a second HTTP stack — we instead **map features** into `app/api/v1/` and **migrate data** with scripts.

## Practical next steps

1. **Column/table mapping (Flask SQLite → FastAPI PostgreSQL):**  
   [`../LEGACY_TO_VL2_MAPPING.md`](../LEGACY_TO_VL2_MAPPING.md)
2. **Inspect old data** (read-only):  
   `LEGACY_SQLITE_PATH=/path/to/leads.db python scripts/legacy_sqlite_inspect.py`
3. **Import pipeline:** `backend/scripts/import_legacy_sqlite.py` — see **`backend/README.md`** (CLI + Docker Compose).

## `DATABASE_PATH`

Legacy code uses `DATABASE_PATH` or `leads.db` next to `database.py`. For local experiments, point `DATABASE_PATH` at your old file **without** moving production data into this repo.
