# Myle vl2 — full roadmap & execution plan

This document defines the **full plan** and **phase-by-phase execution order**. Fine-grained checkboxes live in **`MYLE_VL2_CHECKLIST.md`** — tick those when you merge or ship. This file keeps a **“where we are”** snapshot plus **what to do next**.

---

## Progress snapshot (repo state — update when a phase advances)

| Phase | Focus | Status | Notes |
|-------|--------|--------|-------|
| **0** | Foundation (stack + dashboard IA + dev auth) | **Done** | FastAPI + Vite, docker-compose, `/dashboard/*`, JWT cookie, `users` + seed, errors + `X-Request-ID`, `/leads` auth + FE query |
| **1** | Hardening & visibility | **Done** | CI (GHA), `docker-compose.prod.yml` + `config/.env.production.example`, `/me`→role sync + dashboard error boundary; HTTP JSON access log middleware |
| **2** | Production auth | **Mostly done** | Password + bcrypt, access/refresh JWT + `POST /auth/refresh`, rate limit on auth POSTs, JSON access logs; prod still: `AUTH_DEV_LOGIN_ENABLED=false`, OAuth/OTP optional |
| **3** | Leads domain MVP | **Done** | `Lead` CRUD + scoped list + pagination; FE; `examples` removed |
| **4** | Work & pipeline | **Done (MVP)** | Workboard, archived, follow-ups, retarget, lead-flow, Intelligence stub, **lead pool** + **recycle bin** (soft delete) |
| **5** | Admin / team / finance (slices) | **Done (MVP)** | Team + System + Analytics stubs; **wallet ledger** + adjustments; Execution / Finance / Other / Settings **GET stubs**; nav routes wired |
| **6** | Quality & deploy | **Mostly done** | **78+ pytest**; **Vitest** in CI; **OpenAPI** types; **`render.yaml`** + split-host **cookie SameSite** + hosted **DATABASE_URL** normalization; **apply Blueprint / secrets** = your account |
| **7** | PWA & polish | **Partial** | Manifest + **maskable purpose** on SVG icon; **SW** still blocked on Vite 8 + `vite-plugin-pwa`; i18n if product needs |

**Rough overall picture (engineering foundation vs full product parity):** dashboard **nav parity + wallet MVP** is shipped; **Render Blueprint + prod cookie/DB env** are in-repo; deeper business rules, OAuth, PWA SW, and **clicking “Deploy” on a cloud account** remain on you.

---

## How we work (process)

1. **One phase (or one clear slice) at a time** — avoid scope creep.
2. After each slice: **`npm run lint` / `npm run build`**, **`pytest`**, tick the checklist.
3. **Source of truth:** detailed lines = `docs/MYLE_VL2_CHECKLIST.md`; here you only keep **order + dependencies + snapshot**.

---

## Architecture & smart UX (beyond the legacy app)

**Goal:** Avoid the “feel” of the old stack — **hardcoded toggles**, **different rules** on UI vs server, and **magic state**.

1. **Server-first authority** — permissions, scoping, counts, feature flags come from the **API**; JWT + `/auth/me` is the source of identity; the client only **previews** (e.g. role dropdown) until the server confirms.
2. **API-driven shell** — `GET /api/v1/meta` → `environment` + `features` (e.g. `intelligence` for Work → Intelligence nav). **JSON `GET` only** — **do not add webhooks** here (no Meta/Facebook/social ingest). Nav / gates come **from this API**, not hardcoded toggles in the frontend.
3. **Single sources** — sidebar IA = `dashboard-nav.ts`; errors = stable `{ error: { code, message, request_id } }`; server data = TanStack Query keys (avoid duplicate global stores for the same facts).
4. **Composition over monolith pages** — each screen: **hooks (data) + dumb sections**; reuse patterns (Leads / Archived / Workboard).
5. **Progressive & honest UI** — skeletons, retry, route error boundary; empty states **actionable** (link, filter hint).
6. **Performance discipline** — pagination + caps (leads, workboard); reasonable `staleTime`; virtual lists later where lists grow long.
7. **Accessibility** — `aria-label`, focus rings, semantic headings; keyboard flows must not break.
8. **Phased domains** — each new area = router + migration + FE slice + tests; not **everything at once**.

**Out of scope (explicit):** Do not add **Maya AI** or any bundled third-party “AI assistant” in this repo unless product decides otherwise. **Intelligence** nav is a stub for a future **in-house / product** module, gated by flag.

**Repo:** dashboard sidebar uses **`FEATURE_INTELLIGENCE`** (legacy **`FEATURE_AI_INTELLIGENCE`** still accepted) from `/meta`; **`APP_ENV`** ≠ `production` shows an env badge.

**Smart wallet:** balance is derived from **ledger/transaction** lines; writes **idempotent** where possible; **immutable audit**; rules **API-only** (UI only displays).

---

## Phase 0 — Foundation *(complete)*

**Goal:** New stack running, single dashboard IA, dev login, leads API contract + minimal UI.

- [x] Monorepo, Postgres, Docker, Alembic on start  
- [x] Core API: health, meta, CORS, router layout  
- [x] Global errors + `X-Request-ID`  
- [x] `users` table + seeded dev emails + JWT `sub` = user id  
- [x] `GET /api/v1/leads` authenticated stub + `work/leads` UI + Query  
- [x] Pytest with SQLite `get_db` override  

**Checklist:** Infra, Backend core, DB (users), Auth (dev paths), Leads stub, Frontend shell, Quality (baseline tests).

---

## Phase 1 — Hardening & visibility *(complete)*

**Goal:** **Confidence + traceability** for you and the team — production-like discipline without a feature explosion.

**Shipped:**

1. **CI** — `.github/workflows/ci.yml`: Python 3.12 + `pip install -r backend/requirements.txt` + `pytest tests/`; Node 22 + `npm ci` + lint + build in `frontend/`.  
2. **Env split** — `docker-compose.prod.yml` (reference), `config/.env.production.example`, `config/README.md`, root `.gitignore` for `.env.production`.  
3. **Frontend auth truth** — `useSyncRoleFromMe`: when the server’s `user_id` + `role` pair changes (login / different user), Zustand role aligns; the dropdown stays **preview** until session identity changes.  
4. **Error boundary** — `DashboardOutletErrorBoundary` around dashboard `<Outlet />`.  

**Still optional (Phase 1 backlog / later):**

5. **Access logging** — JSON lines per request (`myle.access`: `request_id`, path, status, duration).  

**Checklist maps to:** Infra (CI, prod compose), Frontend (nav vs JWT, error boundary), Backend core (access logs).

---

## Phase 2 — Production auth

**Goal:** Turn off dev-login in production; real sessions.

**Shipped in repo:** Password login (bcrypt) + `hashed_password`; **`myle_access`** + **`myle_refresh`** cookies; **`POST /api/v1/auth/refresh`**; env **`JWT_ACCESS_MINUTES`**, **`JWT_REFRESH_DAYS`**; **`AUTH_LOGIN_RATE_LIMIT_PER_MINUTE`** on auth POST paths.  

**Still for prod / product:** OAuth/OTP if required; deploy **`AUTH_DEV_LOGIN_ENABLED=false`**; optional account lockout beyond rate limit.  

**Depends on:** Phase 1 CI + env discipline (recommended).  

**Checklist:** Backend auth (prod dev-login off), Deploy secrets.

---

## Phase 3 — Leads domain MVP

**Goal:** Move from stub to **real data** + minimal permissions.

- [x] SQLAlchemy `Lead` model + migration (`created_by_user_id` → `users.id`).  
- [x] `GET /api/v1/leads` DB-backed, **`limit` / `offset`**, `total` = scoped count.  
- [x] **Role rules:** `admin` sees all leads; `leader` / `team` see only `created_by_user_id = self`.  
- [x] `POST /leads`, `PATCH /leads/{id}`, `DELETE /leads/{id}` (owner or admin).  
- [x] Frontend: add lead + list + delete (Work → Leads).  
- [x] List filters **`q`** / **`status`**, row status updates, initial status on create.  
- [x] **Archive / restore** — `archived_at`, list + workboard omit archived by default, archived-only view.  
- [x] **`examples`** table removed (no `Example` model).  

**Depends on:** Phase 2 for production; in dev you can still implement after Phase 1 with dev-login.  

**Checklist:** Backend DB domain tables, Leads CRUD + permissions, Quality tests.

---

## Phase 4 — Work & pipeline (nav parity chunk)

**Goal:** Core **Work** flows backed by the API.

- [x] Workboard — **`GET /api/v1/workboard`** (scoped columns by lead `status` + FE Kanban read view); drag/drop status changes = future (use Leads **PATCH** today).  
- [x] Follow-ups — `follow_ups` + CRUD scoped by lead visibility.  
- [x] Retarget — `GET /api/v1/retarget` (lost/contacted, non-archived); lead flow page (read-only IA).  
- [x] Lead pool (`in_pool`, `GET /lead-pool`, `POST /leads/{id}/claim`) + recycle bin (soft delete, `deleted_only` list, restore).  

**Checklist:** API domains (Workboard, Follow-ups, …).

---

## Phase 5 — Admin, team, finance *(large — slice by slice)*

**Goal:** Legacy dashboard areas **incrementally**; each slice = router + migration + FE page.

- [x] Execution nav stubs (**`/execution/*`**, admin); weak members / leak map / stabilization watch **not** in product v1.  
- [x] Lead pool + recycle bin (see checklist).  
- [x] Team: members, my-team, enrollment stub, **reports**, **approvals**.  
- [x] System + Analytics stubs.  
- [x] Other + Settings **`GET`** stubs for all sidebar paths.  
- [ ] Deeper org / reporting persistence when product defines it.  
- [x] Finance MVP: **wallet ledger** + admin **adjustments** + FE recharges; other finance nav = stubs.  
- [ ] Production deploy, OAuth, deep analytics persistence — see checklist **Deploy** / optional rows.  

**Checklist:** corresponding “API domains” lines.

---

## Phase 6 — Quality & deploy

**Goal:** Ship confidently.

- Pytest + **Vitest** smoke; **OpenAPI snapshot** (`frontend/openapi.json`) + **`npm run generate-api-types`**.  
- Backend + frontend hosts; managed Postgres; `VITE_API_URL`.  

**Checklist:** Quality, Deploy sections.

---

## Phase 7 — PWA & polish

**Goal:** Installable / mobile-friendly UX.

- Service worker when **vite-plugin-pwa** supports **Vite 8** (or custom SW).  
- **Icons:** manifest uses SVG with **`any maskable`**; add PNG sizes if install UX needs it.  
- i18n if product requires.  

**Checklist:** PWA & mobile, Frontend i18n.

---

## Risk / dependency notes (short)

- **ProtectedRoute** checks **`/auth/me`** on each protected visit; Zustand **`isAuthenticated`** defaults **false** and syncs from the server.  
- **JWT cookies** + **CSRF** — if non-cookie clients appear, plan Bearer in a separate phase.  
- **Legacy parity** is not 100% in one sprint — pick Phase 4–5 work by **product priority**.

---

## Document maintenance

- **When a phase completes:** update the **Progress snapshot** table status column in this file.  
- **Detailed ticks:** always in `MYLE_VL2_CHECKLIST.md`.  

_Last aligned with checklist: 2026-04-10._
