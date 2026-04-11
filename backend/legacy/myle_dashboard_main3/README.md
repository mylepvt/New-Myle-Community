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

### `routes/` (full tree snapshot — Flask HTML + JSON)

Entire folder: **`backend/legacy/myle_dashboard_main3/routes/`** (19 modules). Monolith registers these with `register_*_routes(app)` from `app.py`. **Not runnable** in vl2 without Flask, `database`, templates, and `helpers` — use as reference when extending FastAPI.

| Monolith module | Role (summary) | vl2 / API direction |
|-----------------|----------------|---------------------|
| `__init__.py` | Package marker | — |
| `auth_routes.py` | Register/login/logout/password reset (HTML + form posts) | `app/api/v1/auth.py` — JWT cookies, `fbo_id` login, dev-login; no HTML templates |
| `lead_routes.py` | My Leads CRUD, status, pool claim, ₹196 flows, files | `app/api/v1/leads.py`, `lead_pool.py`, `retarget.py`, `follow_ups.py`, `workboard.py` |
| `lead_pool_routes.py` | Lead pool browse/claim UI | `app/api/v1/lead_pool.py` |
| `team_routes.py` | Team directory, hierarchy, reports (HTML) | `app/api/v1/team.py` (members, my-team, enrollment-requests, stubs) |
| `wallet_routes.py` | Wallet UI + recharges | `app/api/v1/wallet.py` |
| `enrollment_routes.py` | Enrollment requests / onboarding | Overlaps `team` enrollment + stubs |
| `approvals_routes.py` | Approvals queues | `GET /team/approvals` stub (`SystemStubResponse`) |
| `training_routes.py` | Training surfaces | `GET /system/training` stub |
| `report_routes.py` | Admin/leader reports | `app/api/v1/analytics.py` + execution/team stubs |
| `ai_routes.py` | `/intelligence`, Maya chat, scores (HTML + JSON) | `GET /meta` (`FEATURE_INTELLIGENCE`), `gate_assistant`, `shell_insights` service — no full Maya port in v1 |
| `webhook_routes.py` | Meta webhook | **Disabled** in monolith (`pass`); vl2 `GET /meta` is bootstrap JSON, not Meta ingest |
| `day2_test_routes.py` | Day 2 business test, WhatsApp tokens | Partial parity via `system` / analytics stubs; full flow not ported |
| `day2_eval_questions.py` | Question bank for Day 2 eval | Not ported as HTTP module |
| `progression_routes.py` | User stage progression UI | `scoring_service` + future user profile |
| `profile_routes.py` | Profile/settings HTML | Future `users` profile API |
| `social_routes.py` | Social links / sharing helpers | `other_pages` / nav stubs |
| `tasks_routes.py` | Background/cron-style tasks | No vl2 cron in repo |
| `misc_routes.py` | Misc HTML (health, static checks) | `GET /health`, `GET /health/db`, `GET /hello` |
