# Myle-Dashboard-main-3 (reference)

- `auth_context.py` — Flask session helpers (`acting_user_id`, `refresh_session_user`).  
  **vl2 equivalent:** `app/core/auth_context.py` + `POST /api/v1/auth/sync-identity` + JWT cookies (`app/core/auth_cookies.py`).

- `helpers.py` — Shared constants and pure helpers from the old monolith (IST timezone, pipeline/status rules, discipline/metrics SQL, lead enrichment, admin decision helpers, etc.). Imports `services.*` from that repo; **not runnable** from this tree — read next to the original app for context.  
  **vl2 direction:** domain logic lands in `app/core/` (e.g. `lead_status.py`), `app/services/` (`lead_scope.py`, `lead_access.py`), and API routers — not a single `helpers` module.
