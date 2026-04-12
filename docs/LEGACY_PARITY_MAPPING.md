# Legacy ↔ Myle vl2 — parity mapping (no guesswork)

This document is the **only** place where we claim **“matches legacy app”** for a feature.  
**Rule:** Do **not** invent legacy behavior from this repo. The **Legacy** columns stay **empty or TBD** until someone attaches **evidence** (see below).

## How parity is verified

| Column | Meaning |
|--------|---------|
| **Legacy ref** | Stable id in the old product: screen name + path or menu label **as in legacy**, plus **evidence** (one or more). |
| **Evidence (required for “match” claims)** | At least one of: link to legacy repo path + tag; exported spec / Notion / sheet row id; screenshot set with date; API contract from legacy; product owner sign-off with date. |
| **New app path** | `frontend` URL under **`/dashboard/...`** — from **`frontend/src/config/dashboard-registry.ts`** (`DASHBOARD_ROUTE_DEFS`). |
| **New wiring** | `surface`: **`full`** (real UI component in `DashboardNestedPage`) vs **`stub`** (`ShellStubPage` → `stubApiPath`) vs **`dashboard-home`**. |
| **Backend (new)** | Authoritative behavior — file or router (see inventory). |

If **Legacy ref** or **Evidence** is missing, status = **TBD — not parity-claimed**.

---

## Cross-cutting behavior (new app — factual, code pointers)

These apply everywhere; legacy comparison rows belong in the **matrix** only after evidence.

| Topic | New app behavior | Source |
|--------|------------------|--------|
| Lead visibility | `admin`: all; `leader`: self + downline (`upline_user_id` tree); `team`: own created | `backend/app/services/lead_scope.py` |
| Workboard buckets | Same visibility as `GET /leads`, grouped by `status`, capped | `backend/app/api/v1/workboard.py` |
| Dashboard routes & roles | Single registry + JSON roles | `frontend/src/config/dashboard-registry.ts`, `frontend/src/config/dashboard-route-roles.json` |
| Feature flag (Intelligence nav) | `GET /api/v1/meta` → `features.intelligence` | `backend` meta router + `frontend` `useMetaQuery` |

---

## New app — full route inventory (factual)

Base URL prefix: **`/dashboard/`** + path below.  
Roles: **`frontend/src/config/dashboard-route-roles.json`** (exact list per path).

| Path | `surface` | Renders / API |
|------|------------|----------------|
| *(home)* | `dashboard-home` | `DashboardHomePage` |
| `work/leads` | full | `LeadsWorkPage` (active) |
| `work/workboard` | full | `WorkboardPage` |
| `work/follow-ups` | full | `FollowUpsWorkPage` |
| `work/retarget` | full | `RetargetWorkPage` |
| `work/lead-flow` | full | `LeadFlowPage` |
| `work/archived` | full | `LeadsWorkPage` (archived) |
| `work/add-lead` | full | `LeadsWorkPage` (active) |
| `work/lead-pool` | full | `LeadPoolWorkPage` |
| `work/lead-pool-admin` | full | `LeadPoolWorkPage` |
| `work/recycle-bin` | full | `RecycleBinWorkPage` |
| `intelligence` | full | `IntelligenceWorkPage` (gated by `features.intelligence`) |
| `team/members` | full | `TeamMembersPage` |
| `team/reports` | full | `TeamReportsPage` + `GET /api/v1/team/reports` (live metrics) |
| `team/approvals` | full | `TeamApprovalsPage` — `GET /api/v1/team/pending-registrations` + `POST /api/v1/team/pending-registrations/{id}/decision` (approve/reject). Shell parity: `GET /api/v1/team/approvals` still returns short links JSON |
| `team/enrollment-approvals` | full | `EnrollmentApprovalsPage` |
| `team/my-team` | full | `MyTeamPage` |
| `system/training` | full | `SystemSurfacePage` (training) |
| `system/decision-engine` | full | `SystemSurfacePage` (decision-engine) |
| `system/coaching` | full | `SystemSurfacePage` (coaching) |
| `analytics/activity-log` | full | `AnalyticsSurfacePage` (activity-log) — nav **System** |
| `analytics/day-2-report` | full | `AnalyticsSurfacePage` (day-2-report) — nav **System** |
| `finance/recharges` | full | `FinanceRechargesPage` |
| `finance/wallet` | full | `WalletPage` |
| `finance/recharge-request` | full | `WalletRechargePage` |
| `finance/recharge-admin` | full | `WalletRechargeAdminPage` |
| `other/leaderboard` | stub | `GET /api/v1/other/leaderboard` |
| `other/notice-board` | full | `NoticeBoardPage` + `GET/POST/DELETE` `/api/v1/other/notice-board` |
| `other/live-session` | stub | `GET /api/v1/other/live-session` |
| `other/daily-report` | full | `DailyReportFormPage` + `GET /api/v1/other/daily-report` |
| `settings/app` | stub | `GET /api/v1/settings/app` |
| `settings/help` | stub | `GET /api/v1/settings/help` |
| `settings/org-tree` | stub | `GET /api/v1/settings/org-tree` |

**Stub map derivation:** `SHELL_STUB_API_PATHS` in `dashboard-registry.ts` — do not duplicate.

**Backend-only (no `/dashboard/` route):** `GET /api/v1/execution/*`, `GET /api/v1/finance/budget-export`, `GET /api/v1/finance/monthly-targets`, `GET /api/v1/finance/lead-pool`, `GET /api/v1/other/training`, `GET /api/v1/settings/all-members` — see **`docs/CORE_APP_STRUCTURE.md`**.

---

## Phase 0.1 — Legacy navigation export (paste here)

Product: legacy app se export karke neeche table bharein (section → menu label → URL). Exact strings **guess mat karo** — purane app se copy.

| Section (legacy) | Menu label (legacy) | URL path (legacy) | Roles (legacy) | Notes |
|------------------|----------------------|-------------------|----------------|-------|
| | | | | |

*Export id (for matrix Evidence column):* `NAV-EXPORT-001` — jab yeh table bhari ho, matrix rows mein Evidence mein `NAV-EXPORT-001` cite karo.

---

## Parity matrix (legacy ↔ new) — fill with evidence

**Minimum starter rows (2026-04):** New-path side is factual; **Legacy ref** = exact label/URL from Phase 0.1 table jab mile; tab tak **TBD** text + Evidence id reserve.

| Legacy ref (id + menu/path) | Evidence | New path | New wiring | Parity status | Owner / date |
|-----------------------------|----------|----------|------------|---------------|--------------|
| TBD — *replace with Phase 0.1 row for primary lead list* | `EVID-2026-001` — attach screenshot or spec when ready | `work/leads` | full | TBD | |
| TBD — *pipeline / board view* | `EVID-2026-002` | `work/workboard` | full | TBD | |
| TBD — *follow-up queue* | `EVID-2026-003` | `work/follow-ups` | full | TBD | |
| TBD — *archived / closed list* | `EVID-2026-004` | `work/archived` | full | TBD | |
| TBD — *shared pool* | `EVID-2026-005` | `work/lead-pool` or `work/lead-pool-admin` | full | TBD | |
| TBD — *recycle / deleted* | `EVID-2026-006` | `work/recycle-bin` | full | TBD | |

**Evidence ids:** Repo-local reference slots — jab file/Notion/screenshot attach ho, yahi id matrix aur evidence store mein use karo. **“match”** sirf jab dono legacy + new documented hon.

**Parity status values:** `TBD` | `partial` | `match` | `won’t match (reason)` — only with evidence for legacy + new.

---

## Backend v1 routers (new app — for wiring checks)

Aggregate: `backend/app/api/v1/router.py`. Domains include: `meta`, `auth`, `leads`, `team`, `system`, `analytics`, `execution`, `finance`, `other`, `settings`, `wallet`, `lead-pool`, `retarget`, `follow-ups`, `workboard`, `gate-assistant`, `realtime_ws` (WebSocket).

When mapping a legacy feature, point the **new** row to the concrete router module under `backend/app/api/v1/` if HTTP behavior is in scope.

---

## Maintenance

- When adding a dashboard screen: update **`DASHBOARD_ROUTE_DEFS`** first, then add or adjust a row in the **inventory** table above.
- When legacy parity is agreed: fill **Parity matrix** — never claim parity in chat or PR description without updating this file.
- **Implementation order (waves, stub→full checklist):** **`docs/PARITY_ROLLOUT_PLAN.md`**.
- **Full behavior port (backend + frontend, lossless rules):** **`docs/LOSSLESS_FULLSTACK_PORT.md`**.
