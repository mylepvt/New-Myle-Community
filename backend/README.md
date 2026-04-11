# Myle vl2 API (FastAPI)

Async **FastAPI** + **SQLAlchemy 2** + **Alembic** + **PostgreSQL** (`asyncpg`). Entry: `main.py`; routes under `app/api/v1/`.

## Setup

1. Copy **`.env.example`** → **`.env`** and set **`DATABASE_URL`** (must use `postgresql+asyncpg://…`).
2. Install: `pip install -r requirements.txt` (or `pip install -r requirements-dev.txt` for tests).
3. Migrations: `alembic upgrade head`.
4. Run API: `uvicorn main:app --reload` (from this directory).

## CLI scripts (same env as the API)

Run from **`backend/`** so `DATABASE_URL` and `app.*` imports match production.

| Script | Purpose |
|--------|---------|
| `scripts/create_user.py` | Bootstrap / reset a user (bcrypt; same as `POST /api/v1/auth/login`). |
| `scripts/legacy_sqlite_inspect.py` | Read-only: list legacy SQLite tables + row counts (`LEGACY_SQLITE_PATH`). |
| `scripts/import_legacy_sqlite.py` | Copy **legacy Flask `leads.db`** → vl2 PostgreSQL (users → leads → wallet → activity). |

### Legacy import (Flask SQLite → this stack)

1. Ensure Alembic is at head and Postgres is empty **or** you accept duplicate-key skips for users.
2. Optional: set in **`.env`** (see `.env.example`):
   - **`LEGACY_SQLITE_PATH`** — default path for `--legacy-db`
   - **`IMPORT_DEFAULT_PASSWORD`** — plain password used when legacy hashes are not bcrypt (Werkzeug, etc.)
3. Commands:

```bash
cd backend

# Inspect SQLite only (no Postgres)
python scripts/import_legacy_sqlite.py --sqlite-only --legacy-db /path/to/leads.db

# Dry-run against Postgres (no writes)
python scripts/import_legacy_sqlite.py --dry-run --legacy-db /path/to/leads.db

# Import
python scripts/import_legacy_sqlite.py --legacy-db /path/to/leads.db

# Save id maps after a real import
python scripts/import_legacy_sqlite.py --legacy-db /path/to/leads.db --write-mapping ./legacy_id_maps.json
```

Field mapping and gaps: **`legacy/LEGACY_TO_VL2_MAPPING.md`**. Legacy Flask sources (reference only): **`legacy/myle_dashboard/`**.

### Docker Compose (repo root)

Database URL inside the API container is already `postgresql+asyncpg://myle:myle@db:5432/myle`. Mount the host SQLite file read-only:

```bash
# from repo root — dry-run
docker compose run --rm \
  -v /absolute/path/to/parent:/legacy:ro \
  backend \
  python scripts/import_legacy_sqlite.py --dry-run --legacy-db /legacy/leads.db
```

Replace `/absolute/path/to/parent` so `/legacy/leads.db` is your `leads.db`. Omit `--dry-run` only after you are sure.
