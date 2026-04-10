# Myle vl2 — feature & migration checklist

**Full phased plan + “kahan tak pahunche” snapshot:** [`MYLE_VL2_ROADMAP.md`](./MYLE_VL2_ROADMAP.md) — yahan nitty-gritty ticks; roadmap mein order aur progress table.

**Names**

- **This repo / folder:** `myle vl2` — new stack (FastAPI + Vite/React, velvet UI).
- **Legacy app:** **Myle main dashboard** (Flask + Bootstrap) — ideas/IA only; stack copy nahi.

Tick items in Git/PRs as you ship.

## Infra & repo

- [x] Monorepo: `backend/` + `frontend/` + root `docker-compose.yml`
- [x] Postgres service + volume + healthcheck
- [x] Backend Dockerfile + Alembic on container start
- [x] Frontend Dockerfile (Vite dev)
- [x] `backend/.env.example` (incl. `SECRET_KEY`, `AUTH_DEV_LOGIN_ENABLED`)
- [x] Production reference compose (`docker-compose.prod.yml`) + `config/.env.production.example` + root `.gitignore` for env files
- [x] CI: GitHub Actions — `pytest`, `npm run lint`, `npm run build` (`.github/workflows/ci.yml`)

## Backend — core

- [x] FastAPI app, CORS from settings, lifespan DB engine dispose
- [x] `GET /health`, `GET /health/db`
- [x] `GET /api/v1/meta`
- [x] `app/api/v1/router.py` aggregator (new domains only here + new module)
- [x] `app/api/deps.py` (`get_db`)
- [x] `app/core/config.py` (Settings)
- [x] Request id: `X-Request-ID` middleware + CORS `expose_headers` (optional inbound header)
- [ ] Structured request/response logging (JSON / structlog) — optional
- [x] Global exception handler + stable error JSON shape

## Backend — database

- [x] Async SQLAlchemy engine + `get_db`
- [x] Alembic + initial migration (`examples` placeholder table)
- [ ] Replace/remove `Example` model when real domains land
- [x] `users` table + Alembic migration + seeded dev accounts (`dev-{admin|leader|team}@myle.local`); JWT `sub` = user id
- [ ] Password/OAuth/OTP sign-in + `hashed_password` + refresh strategy (prod auth)
- [ ] Domain tables aligned with legacy Myle main dashboard (leads, wallet, …) — phased

## Backend — auth

- [x] `GET /api/v1/auth/me` (JWT cookie)
- [x] `POST /api/v1/auth/dev-login` (gated by `AUTH_DEV_LOGIN_ENABLED`)
- [x] `POST /api/v1/auth/logout`
- [x] `SECRET_KEY`, `SESSION_COOKIE_SECURE` in settings
- [ ] Real sign-in (password/OAuth/OTP) + user row lookup
- [ ] Refresh tokens or short access + rotation
- [ ] Rate limit / lockout on auth routes
- [ ] Remove or hard-disable `dev-login` in production deploy config

## Backend — API domains (nav parity, incremental)

Stub = contract only; **Done** = backed by DB + rules.

- [x] Hello (`GET /api/v1/hello`)
- [x] Leads list stub (`GET /api/v1/leads`) — empty list until DB wired; **auth required** (cookie JWT)
- [ ] Leads CRUD + filters + permissions by role
- [ ] Workboard / pipeline (domain-specific endpoints)
- [ ] Follow-ups, retarget, lead flow, archived
- [ ] Admin execution (at-risk, weak members, leak map, ledger)
- [ ] Lead pool (admin vs member), recycle bin
- [ ] AI intelligence (feature-flagged)
- [ ] Team: members, reports, approvals, ₹196 approvals, my team
- [ ] System: training admin, decision engine, coaching
- [ ] Analytics: activity log, day 2 report
- [ ] Finance: wallet, recharges, exports, targets, lead pool purchase
- [ ] Other: leaderboard, notice board, live session, member training, daily report
- [ ] Settings: app settings, help, all members, org tree

## Frontend — shell & UX

- [x] Vite + React + TS, velvet-dark theme (not legacy Bootstrap clone)
- [x] Tailwind + shadcn-style primitives (`Button`, `Skeleton`)
- [x] TanStack Query + `apiFetch` + `credentials: 'include'`
- [x] React Router + `ProtectedRoute`
- [x] Zustand: `auth`, `role` (preview), `shell` sidebar
- [x] Dashboard layout + **single** `/dashboard/*` splat (no per-route duplication)
- [x] Nav IA from `frontend/src/config/dashboard-nav.ts` (single source)
- [x] Login + dev API sign-in + sign out clears cookie
- [x] `/dashboard/work/leads` uses TanStack Query → `GET /api/v1/leads` (cookie auth)
- [x] Nav role vs JWT: `useSyncRoleFromMe` syncs Zustand when `user_id` + server `role` changes; header dropdown remains **preview** until next session change
- [x] Dashboard route error boundary (`DashboardOutletErrorBoundary` around `<Outlet />`)
- [ ] Route-level loading shell (optional beyond current skeletons)
- [ ] i18n / Hindi copy (if product requires)

## PWA & mobile

- [x] `manifest.webmanifest` + meta theme-color
- [ ] Service worker (blocked earlier on Vite 8 + `vite-plugin-pwa` peer — revisit)
- [ ] Icons maskable / sizes audit for install sheet

## Quality

- [x] Pytest: `/auth/me`, dev-login/logout, `/leads` (SQLite in-memory + `get_db` override in `tests/conftest.py`)
- [ ] Pytest: grow per router as domains become real
- [ ] Frontend tests (Vitest + RTL) for critical flows (optional)
- [ ] OpenAPI → generated TS types (optional)

## Cursor / team rules

- [x] `.cursor/rules/myle-frontend-dashboard.mdc`
- [x] `.cursor/rules/myle-backend-api.mdc`

## Deploy

- [ ] Backend host (Fly/Railway/…) + managed Postgres
- [ ] Frontend host (Vercel/Netlify) + `VITE_API_URL`
- [ ] Secrets in host dashboard, never in image
- [ ] `AUTH_DEV_LOGIN_ENABLED=false` in prod

---

**Legend:** [x] done in repo today · [ ] intentional next work.
