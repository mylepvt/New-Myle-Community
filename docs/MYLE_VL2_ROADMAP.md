# Myle vl2 — full roadmap & execution plan

Yeh document **poora plan** aur **phase-by-phase execution order** define karta hai. Fine-grained tick items **`MYLE_VL2_CHECKLIST.md`** mein rahenge — wahan PR / ship ke waqt boxes tick karo. Is file mein **“hum kahan hain”** snapshot + **agla kya karna hai** clear rahega.

---

## Progress snapshot (repo state — update jab phase advance ho)

| Phase | Focus | Status | Notes |
|-------|--------|--------|--------|
| **0** | Foundation (stack + dashboard IA + dev auth) | **Done** | FastAPI + Vite, docker-compose, `/dashboard/*`, JWT cookie, `users` + seed, errors + `X-Request-ID`, `/leads` auth + FE query |
| **1** | Hardening & visibility | **Done** | CI (GHA), `docker-compose.prod.yml` + `config/.env.production.example`, `/me`→role sync + dashboard error boundary; structured logging still optional |
| **2** | Production auth | **Pending** | Password/OAuth/OTP, refresh/rotation, rate limits, `AUTH_DEV_LOGIN_ENABLED=false` prod |
| **3** | Leads domain MVP | **Pending** | `Lead` table, list from DB, CRUD + filters + role rules; remove/replace `examples` |
| **4** | Work & pipeline | **Pending** | Workboard, follow-ups, flow, archived (nav parity) |
| **5** | Admin / team / finance (slices) | **Pending** | Execution, pool, wallet, reports — phased by product priority |
| **6** | Quality & deploy | **Pending** | Pytest coverage, optional Vitest, hosts + secrets |
| **7** | PWA & polish | **Pending** | SW when Vite tooling ready, icons, i18n if needed |

**Approx. overall (engineering foundation vs full product parity):** foundation ~**35–40%**; legacy nav parity + finance **bahut bada** — intentionally phased.

---

## Kaise kaam karenge (process)

1. **Ek waqt mein ek phase (ya uska ek clear slice)** — scope creep avoid.
2. Har slice ke baad: **`npm run lint` / `npm run build`**, **`pytest`**, checklist tick.
3. **Source of truth:** detailed lines = `docs/MYLE_VL2_CHECKLIST.md`; yahan sirf **order + dependencies + snapshot**.

---

## Phase 0 — Foundation *(complete)*

**Goal:** Naya stack chalna, single dashboard IA, dev login, leads API contract + minimal UI.

- [x] Monorepo, Postgres, Docker, Alembic on start  
- [x] Core API: health, meta, CORS, router layout  
- [x] Global errors + `X-Request-ID`  
- [x] `users` table + seeded dev emails + JWT `sub` = user id  
- [x] `GET /api/v1/leads` authenticated stub + `work/leads` UI + Query  
- [x] Pytest with SQLite `get_db` override  

**Checklist:** Infra, Backend core, DB (users), Auth (dev paths), Leads stub, Frontend shell, Quality (baseline tests).

---

## Phase 1 — Hardening & visibility *(complete)*

**Goal:** Tumhein aur team ko **confidence + traceability** — prod-like discipline bina feature explosion.

**Shipped:**

1. **CI** — `.github/workflows/ci.yml`: Python 3.12 + `pip install -r backend/requirements.txt` + `pytest tests/`; Node 22 + `npm ci` + lint + build in `frontend/`.  
2. **Env split** — `docker-compose.prod.yml` (reference), `config/.env.production.example`, `config/README.md`, root `.gitignore` for `.env.production`.  
3. **Frontend auth truth** — `useSyncRoleFromMe`: jab server par `user_id` + `role` ka pair badle (login / doosra user), Zustand role align; dropdown **preview** tab tak rehta hai jab tak session identity change na ho.  
4. **Error boundary** — `DashboardOutletErrorBoundary` around dashboard `<Outlet />`.  

**Still optional (Phase 1 backlog / later):**

5. **Structured logging** — JSON logs + request id in log line (`uvicorn`/middleware).  

**Checklist maps to:** Infra (CI, prod compose), Frontend (nav vs JWT, error boundary), Backend core (logging optional).

---

## Phase 2 — Production auth

**Goal:** Dev-login band prod mein; real sessions.

- Password (bcrypt/argon2) + `hashed_password` **or** OAuth/OTP (product decision).  
- Short-lived access + refresh **or** rotation strategy.  
- Rate limit / lockout on auth endpoints.  
- Deploy: **`AUTH_DEV_LOGIN_ENABLED=false`**, secrets host par.  

**Depends on:** Phase 1 CI + env discipline (recommended).  

**Checklist:** Backend auth (real sign-in, refresh, rate limit, prod dev-login off), Deploy secrets.

---

## Phase 3 — Leads domain MVP

**Goal:** Stub se **asli data** + minimal permissions.

- SQLAlchemy `Lead` model + migration.  
- `GET /api/v1/leads` DB-backed; pagination/filter sketch.  
- `POST/PATCH/...` as needed; **role-based** scopes (admin vs leader vs team).  
- Frontend: table/form minimal; loading & error states.  
- Remove / replace **`examples`** table when replaced by real domain.  

**Depends on:** Phase 2 for production; dev mein Phase 1 ke baad bhi implement ho sakta hai with dev-login.  

**Checklist:** Backend DB domain tables, Leads CRUD + permissions, Quality tests.

---

## Phase 4 — Work & pipeline (nav parity chunk)

**Goal:** “Work” section ke core flows API se.

- Workboard / pipeline endpoints.  
- Follow-ups, retarget, lead flow, archived — **priority order product se**.  

**Checklist:** API domains (Workboard, Follow-ups, …).

---

## Phase 5 — Admin, team, finance *(large — slice by slice)*

**Goal:** Legacy dashboard areas **incrementally**; har slice = own router + migration + FE page.

- Admin execution, lead pool, recycle bin, AI (flagged).  
- Team, approvals, analytics.  
- Finance: wallet, recharges, targets, …  

**Checklist:** corresponding “API domains” lines.

---

## Phase 6 — Quality & deploy

**Goal:** Ship confidently.

- Pytest grow per router; optional Vitest RTL.  
- Optional OpenAPI → TS types.  
- Backend + frontend hosts; managed Postgres; `VITE_API_URL`.  

**Checklist:** Quality, Deploy sections.

---

## Phase 7 — PWA & polish

**Goal:** Installable / mobile-friendly UX.

- Service worker jab Vite 8 + plugin story clear ho.  
- Maskable icons audit.  
- i18n / Hindi if product requires.  

**Checklist:** PWA & mobile, Frontend i18n.

---

## Risk / dependency notes (short)

- **ProtectedRoute** abhi Zustand pe hai; **server** hi final authority hai — Phase 2–3 mein alignment tight karna.  
- **JWT cookies** + **CSRF** — agar non-cookie clients aayein toh Bearer strategy alag phase.  
- **Legacy parity** 100% ek sprint mein nahi — Phase 4–5 mein **product-priority** se chunna.

---

## Document maintenance

- **Har phase complete hone par:** is file ke **Progress snapshot** table mein status column update karo.  
- **Detailed ticks:** hamesha `MYLE_VL2_CHECKLIST.md`.  

_Last aligned with checklist: 2026-04-10._
