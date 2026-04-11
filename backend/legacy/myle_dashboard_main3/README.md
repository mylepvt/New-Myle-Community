# Myle-Dashboard-main-3 (reference)

- `auth_context.py` — Flask session helpers (`acting_user_id`, `refresh_session_user`).  
  **vl2 equivalent:** `app/core/auth_context.py` + `POST /api/v1/auth/sync-identity` + JWT cookies (`app/core/auth_cookies.py`).

- `helpers.py` — Shared constants and pure helpers from the old monolith (IST timezone, pipeline/status rules, discipline/metrics SQL, lead enrichment, admin decision helpers, etc.). Imports `services.*` from that repo; **not runnable** from this tree — read next to the original app for context.  
  **vl2 port (stateless surface):** `app/core/pipeline_rules.py` (ex-`services/rule_engine`), `app/core/pipeline_legacy.py` (constants + team/₹196/call-tag helpers), `app/core/time_ist.py`, `app/core/row_utils.py`, `app/core/legacy_status_bridge.py`, facade `app/core/legacy_helpers.py`. DB-heavy metrics/discipline from `helpers.py` are **not** ported — add under `app/services/` when product needs them.

- `execution_enforcement.py` — Team funnel, follow-up attack SQL, downline aggregates, admin at-risk / weak members / leak map, stale redistribution.  
  **vl2:** `app/services/execution_enforcement.py` + `app/api/v1/execution.py`. At-risk staleness uses last-activity `coalesce` on `Lead` (no `updated_at` column yet). `POST /execution/stale-redistribute` returns `implemented: false` until `stale_worker`-style columns exist.

- `reliability.py` — Request correlation id, incident codes, structured `[reliability]` log lines, `safe_user_error`.  
  **vl2:** `app/core/reliability.py`; request ids via `RequestIdMiddleware` + `ensure_request_id`. Unhandled exceptions log/return `incident_id` (`API-500-…`) in `app/core/errors.py`.

### `services/` (full tree snapshot + vl2 ports)

| Monolith file | Verbatim snapshot | Runnable in vl2 |
|---------------|-------------------|-----------------|
| `rule_engine.py` | `legacy/.../services/rule_engine.py` | `app/services/rule_engine.py` → `app.core.pipeline_rules` |
| `wallet_ledger.py` | ✓ | `app/services/wallet_ledger.py` (SQLite + legacy lead columns) |
| `scoring_service.py` | ✓ | `app/services/scoring_service.py` (optional `database.get_db` / `helpers._upsert_daily_score`) |
| `hierarchy_lead_sync.py` | ✓ | `app/services/hierarchy_lead_sync.py` (`apply_leads_update` subset in-module) |
| `day2_certificate_pdf.py` | ✓ | `app/services/day2_certificate_pdf.py` (needs `reportlab` in `requirements.txt`) |
