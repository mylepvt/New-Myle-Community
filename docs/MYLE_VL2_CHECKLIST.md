# Myle vl2 — feature & migration checklist

**Full phased plan + progress snapshot:** [`MYLE_VL2_ROADMAP.md`](./MYLE_VL2_ROADMAP.md) — nitty-gritty ticks here; roadmap has order and the progress table.

**Names**

- **This repo / folder:** `myle vl2` — new stack (FastAPI + Vite/React, velvet UI).
- **Legacy app:** **Myle main dashboard** (Flask + Bootstrap) — ideas / IA only; we do not copy that stack here.

Tick items in Git/PRs as you ship.

## Infra & repo

- [x] Monorepo: `backend/` + `frontend/` + root `docker-compose.yml`
- [x] Postgres service + volume + healthcheck
- [x] Backend Dockerfile + Alembic on container start
- [x] Frontend Dockerfile (Vite dev)
- [x] `backend/.env.example` (incl. `SECRET_KEY`, `AUTH_DEV_LOGIN_ENABLED`, JWT + rate limit keys)
- [x] Production reference compose (`docker-compose.prod.yml`) + `config/.env.production.example` + root `.gitignore` for env files
- [x] CI: GitHub Actions — `pytest`, `npm run lint`, **`npm run test`**, `npm run build` (`.github/workflows/ci.yml`)

## Architecture (smart stack — legacy gaps)

- [x] Documented principles: server-first, API-driven shell, single sources — **`MYLE_VL2_ROADMAP.md`** → *Architecture & smart UX*
- [x] **`GET /api/v1/meta`** — `environment` + `auth_dev_login_enabled` + `features.intelligence` (env: **`FEATURE_INTELLIGENCE`**); dashboard nav uses flags; login hides dev quick-login when **`auth_dev_login_enabled`** is false; **no webhooks** on this route; **no Maya / bundled third-party AI** — product-only Intelligence nav stub

## Backend — core

- [x] FastAPI app, CORS from settings, lifespan DB engine dispose
- [x] `GET /health`, `GET /health/db`, **`GET /health/migrations`** (Alembic head vs DB `alembic_version`)
- [x] `GET /api/v1/meta`
- [x] `app/api/v1/router.py` aggregator (new domains only here + new module)
- [x] `app/api/deps.py` (`get_db`)
- [x] `app/core/config.py` (Settings)
- [x] Request id: `X-Request-ID` middleware + CORS `expose_headers` (optional inbound header)
- [x] HTTP access log: one JSON line per request (`myle.access` logger: method, path, status, duration, `request_id`)
- [x] Global exception handler + stable error JSON shape

## Backend — database

- [x] Async SQLAlchemy engine + `get_db`
- [x] Alembic + migrations; **`examples` removed** (no `Example` model)
- [x] `users` table + Alembic migration + seeded dev accounts (`dev-{admin|leader|team}@myle.local`); JWT `sub` = user id; dev **`hashed_password`** via migration
- [x] Password sign-in (bcrypt) + `hashed_password` + **access + refresh** JWT cookies (`JWT_ACCESS_MINUTES`, `JWT_REFRESH_DAYS`, `POST /api/v1/auth/refresh`)
- [ ] OAuth/OTP — optional future (not in V1 JWT + password MVP)
- [x] **Wallet ledger** — `wallet_ledger_entries` (append-only, **`idempotency_key`**); further legacy parity (full wallet SKU, …) optional

## Backend — auth

- [x] `GET /api/v1/auth/me` (access JWT cookie)
- [x] `POST /api/v1/auth/dev-login` (gated by `AUTH_DEV_LOGIN_ENABLED`)
- [x] `POST /api/v1/auth/login` (email + password → bcrypt)
- [x] `POST /api/v1/auth/refresh` (refresh cookie → new access + refresh)
- [x] `POST /api/v1/auth/logout` (clears access + refresh cookies)
- [x] `SECRET_KEY`, `SESSION_COOKIE_SECURE` in settings
- [x] Rate limit: sliding window on `POST` **`/api/v1/auth/login`**, **`/api/v1/auth/dev-login`**, **`/api/v1/auth/refresh`** (`AUTH_LOGIN_RATE_LIMIT_PER_MINUTE`, `0` = off)
- [x] Production reference: **`AUTH_DEV_LOGIN_ENABLED=false`** in **`config/.env.production.example`** (set on real hosts per **Deploy** section)
- [x] Prod user bootstrap — **`backend/scripts/create_user.py`** (bcrypt; same hashing as **`POST /api/v1/auth/login`**)

## Backend — API domains (nav parity, incremental)

Stub = contract only; **Done** = backed by DB + rules.

- [x] Hello (`GET /api/v1/hello`)
- [x] Leads **CRUD** + **scoped list** (admin: all; leader/team: own rows) + pagination query params; **auth required**
- [x] Leads list filters: **`q`** (name substring, case-insensitive) + **`status`**; **`PATCH`** accepts **`name`** and/or **`status`**
- [x] **Permissions (V1):** leads scoped by role + `created_by_user_id` (see Leads API); **cross-team / org hierarchy** deferred until product models org lines
- [x] Workboard: **`GET /api/v1/workboard`** — scoped leads grouped by **`status`** (counts + capped cards per column); Work → **Workboard** UI (read-only pipeline; edit status on Leads page)
- [x] **Archived leads:** `leads.archived_at`; **`GET /api/v1/leads?archived_only=true`**; **`PATCH`** body **`archived`** (bool); default list + workboard exclude archived; Work → **Archived leads** (`/dashboard/work/archived`) restore + delete
- [x] **Follow-ups:** `follow_ups` table; **`GET/POST/PATCH/DELETE /api/v1/follow-ups`** (scoped via parent lead); Work → **Follow-ups** UI
- [x] **Retarget:** **`GET /api/v1/retarget`** — active leads with **`status`** in `lost` \| `contacted`; Work → **Retarget** UI + status updates (invalidates with leads/workboard)
- [x] **Lead flow:** read-only pipeline page (**`work/lead-flow`**) aligned with `Lead.status` values
- [x] **Execution (nav parity stubs):** **`GET /api/v1/execution/at-risk-leads`**, **`GET /api/v1/execution/lead-ledger`** (admin, **`SystemStubResponse`**) — weak members / leak map / stabilization watch remain **out of product v1**
- [x] **Lead pool** + **recycle bin** — `leads.in_pool`, `leads.deleted_at` (soft delete); `GET /api/v1/lead-pool`; `POST /api/v1/leads/{id}/claim`; `GET /api/v1/leads?deleted_only=true` (admin); `PATCH` **`in_pool`** / **`restored`** (admin); main list + workboard + retarget exclude pool & deleted; Work → **Lead pool** (leader/team), **Admin lead pool** (same API), **Recycle bin**
- [x] Work → **Intelligence** — placeholder page + **hard redirect** if `GET /api/v1/meta` → `features.intelligence` is false (env `FEATURE_INTELLIGENCE`); product-only, no third-party AI
- [x] **Team:** **`GET /api/v1/team/members`**, **`POST /api/v1/team/members`** (admin — create user, bcrypt); **`my-team`**, **`enrollment-requests`**, **`reports`**, **`approvals`** — list + enrollment real/empty as before; reports/approvals stubs; **Team → All members** includes admin **Add user** form; all Team nav items wired in FE
- [x] **System (V1 stubs):** **`GET /api/v1/system/training`**, **`/system/decision-engine`** (admin); **`/system/coaching`** (admin + leader); JSON **`items`/`total`/`note`** — empty until product models data; System → **Training**, **Decision engine**, **Coaching** wired
- [x] **Analytics (V1 stubs):** **`GET /api/v1/analytics/activity-log`**, **`GET /api/v1/analytics/day-2-report`** (admin); reuse **`SystemStubResponse`** shape; Analytics → **Activity log**, **Day 2 test report** wired
- [x] **Finance:** **Smart wallet** — **`GET /api/v1/wallet/me`**, **`GET /api/v1/wallet/ledger`**, **`POST /api/v1/wallet/adjustments`** (admin, idempotent key, signed cents); **Recharges** FE posts adjustments; **budget export**, **monthly targets**, **lead pool purchase** (FE nav) = **`GET /api/v1/finance/*`** stubs
- [x] **Other:** **`GET /api/v1/other/*`** (leaderboard, notice-board, live-session, training, daily-report) — stubs + FE **`ShellStubPage`**
- [x] **Settings:** **`GET /api/v1/settings/*`** (`app`, `help`, `all-members`, `org-tree`) — stubs + FE **`ShellStubPage`**

## Frontend — shell & UX

- [x] Vite + React + TS, velvet-dark theme (not legacy Bootstrap clone)
- [x] Tailwind + shadcn-style primitives (`Button`, `Skeleton`)
- [x] TanStack Query + `apiFetch` + `credentials: 'include'`
- [x] React Router + **`ProtectedRoute`** — gate uses **`GET /api/v1/auth/me`** (server truth); Zustand syncs from that; staleTime `0` + refetch on mount on protected paths
- [x] Zustand: `auth`, `role` (preview), `shell` sidebar
- [x] Dashboard layout + **single** `/dashboard/*` splat (no per-route duplication)
- [x] Nav IA from `frontend/src/config/dashboard-nav.ts` (single source)
- [x] Login + dev API sign-in + password login + sign out clears cookies
- [x] `authRefresh()` helper → `POST /api/v1/auth/refresh` (optional proactive rotation)
- [x] `/dashboard/work/leads` uses TanStack Query → `GET /api/v1/leads` (cookie auth)
- [x] `/dashboard/work/workboard` → `GET /api/v1/workboard` (TanStack Query)
- [x] `/dashboard/work/archived` — archived-only lead list + restore (same `LeadsWorkPage` + `archived_only` API)
- [x] `/dashboard/work/follow-ups` — follow-ups list + create + done/reopen/delete
- [x] `/dashboard/work/retarget` → `GET /api/v1/retarget`
- [x] `/dashboard/work/lead-flow` — pipeline reference (no extra API)
- [x] `/dashboard/intelligence` — gated placeholder (`useMetaQuery` + redirect when disabled)
- [x] `/dashboard/work/lead-pool` + `/dashboard/work/lead-pool-admin` + `/dashboard/work/recycle-bin`
- [x] `/dashboard/team/members`, `/dashboard/team/my-team`, `/dashboard/team/enrollment-approvals`
- [x] `/dashboard/system/training`, `/dashboard/system/decision-engine`, `/dashboard/system/coaching`
- [x] `/dashboard/analytics/activity-log`, `/dashboard/analytics/day-2-report`
- [x] `/dashboard/execution/*`, `/dashboard/finance/*` (wallet + recharges + finance stubs), `/dashboard/other/*`, `/dashboard/settings/*`
- [x] `/dashboard/work/add-lead` — same **`LeadsWorkPage`** as active list (create form at top)
- [x] Nav role vs JWT: `useSyncRoleFromMe` syncs Zustand when `user_id` + server `role` changes; header dropdown remains **preview** until next session change
- [x] Dashboard route error boundary (`DashboardOutletErrorBoundary` around `<Outlet />`)
- [x] Route-level loading: **`lazy(() => import(DashboardNestedPage))`** + **`Suspense`** skeleton in **`App.tsx`**
- [x] **i18n hub (English V1):** `frontend/src/lib/i18n.ts` — add locales later without rewiring every file

## PWA & mobile

- [x] `manifest.webmanifest` + meta theme-color
- [x] **Minimal service worker** — `frontend/public/sw.js` (install/activate only, **no offline cache**); registered in prod from `main.tsx` — full precache when **`vite-plugin-pwa`** supports Vite 8 or product needs offline
- [x] **Icons / manifest audit** — `manifest.webmanifest` uses `/favicon.svg` with **`purpose: "any maskable"`** and `sizes: "any"`; for stricter store-style installs, add **192×192 / 512×512 PNGs** later

## Quality

- [x] Pytest: `/auth/me`, dev-login/logout, password login, `/auth/refresh`, rate limit, `/leads` (SQLite in-memory + `get_db` override in `tests/conftest.py`)
- [x] Pytest: wallet + shell stub routers + broader domain coverage (**~87+** tests in CI)
- [x] Frontend tests — **Vitest + Testing Library** (`npm run test`); **LoginPage** + **`ProtectedRoute`** (CI)
- [x] **OpenAPI → TS types** — `scripts/export_openapi.py` writes `frontend/openapi.json`; **`npm run generate-api-types`** (in `frontend/`) refreshes `src/lib/api-v1.d.ts` via `npx openapi-typescript@7.13.0` (run after API contract changes; commit both JSON + `.d.ts`)

## Cursor / team rules

- [x] `.cursor/rules/myle-frontend-dashboard.mdc`
- [x] `.cursor/rules/myle-backend-api.mdc`

## Deploy

**In-repo templates (you still create/apply services on your cloud account and paste real URLs/secrets in the host dashboard).**

- [x] **Render Blueprint** — root **`render.yaml`**: managed Postgres + **`backend` Docker** (Alembic + Uvicorn, `/health`) + **static** `frontend/dist`; header comments explain deploy order (**API URL** → **`VITE_API_URL`** on static service; **`BACKEND_CORS_ORIGINS`** = exact static site origin)
- [x] **Split-host cookie auth** — **`AUTH_COOKIE_SAMESITE=none`** + **`SESSION_COOKIE_SECURE=true`** for SPA + API on different origins (`config/.env.production.example`, `render.yaml`); JWT **`SameSite`** wired in `auth.py`
- [x] **Hosted `DATABASE_URL`** — `postgres://` / `postgresql://` strings normalized to **`postgresql+asyncpg://`** in `Settings` (Render/Heroku-style)
- [x] **Live stack** — in-repo **`render.yaml`** + host env (Render/Fly/etc.); managed Postgres; secrets only in dashboard (user account applies)
- [x] **`AUTH_DEV_LOGIN_ENABLED=false`** in prod — set in **`render.yaml`** and production env example

---

## Parity rollout (old app → vl2 — tick in PRs)

**Runbook:** `docs/PARITY_SPRINT_1.md` (Week 1) · `docs/PARITY_ROLLOUT_PLAN.md` (waves) · `docs/LEGACY_PARITY_MAPPING.md` (matrix).

- [x] **Sprint 1 — Matrix starter:** ≥5 rows + `EVID-2026-00x` ids + Phase 0.1 paste table (`LEGACY_PARITY_MAPPING.md`)
- [ ] **Sprint 1 — Product:** Phase 0.1 legacy **nav export** pasted (exact labels/URLs from old app)
- [x] **Sprint 1 — Eng (automated):** `pytest` + `npm run build` + `npm test` + `npm run lint` + `bash scripts/verify_wave_a.sh` (`PARITY_SPRINT_1.md`)
- [ ] **Sprint 1 — Eng (browser):** Wave A manual rows M1–M6 (`PARITY_SPRINT_1.md`)
- [x] **Sprint 1 — Playbook structure:** pilot + support **table** in `TEAM_MIGRATION_PLAYBOOK.md` (assign names + channel when ready)
- [ ] **Sprint 1 — Team:** Pilot names + dated start + support channel owner filled in playbook
- [x] **Stub → full default:** engineering suggestion documented (`PARITY_ROLLOUT_PLAN.md` — product confirms)
- [ ] Next: first **stub → full** implementation only after product pick + matrix row (see `PARITY_ROLLOUT_PLAN.md`)

---

## Outstanding (optional / future)

| Item | Notes |
|------|--------|
| OAuth/OTP | Optional; JWT + password + dev-login cover V1 |
| Org-wide team visibility / reporting lines | Needs product org model (beyond role + `created_by_user_id`) |
| Extra locales | `i18n.ts` ready; add JSON + locale switch when product picks languages |
| Offline precache / full PWA | Minimal SW shipped; **`vite-plugin-pwa`** when it supports **Vite 8**, or expand `sw.js` |

**Legend:** [x] done in repo for current roadmap · [ ] only where marked inline above.
