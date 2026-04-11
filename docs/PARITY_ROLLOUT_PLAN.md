# Old app ↔ New app — side‑by‑side rollout plan (stepwise)

**Purpose:** Ek‑ek karke implement / verify karna, **bina guess ke**. Purani taraf sirf tab bharna jab **evidence** ho (screenshot, URL, spec, sign‑off).  
**Pairing doc:** Har “match” claim **`docs/LEGACY_PARITY_MAPPING.md`** matrix mein lock honi chahiye.  
**Technical inventory (new app):** `frontend/src/config/dashboard-registry.ts` + `dashboard-route-roles.json` — yahi sidebar + routes ka source of truth hai.

---

## Kaise use karein (short)

1. **Phase 0** mein legacy se menu / URLs / roles export karo (table khali mat chhodo — “TBD” likho).
2. Neeche **waves** ke order mein chalo: pehle **core work** (leads / pipeline), phir team / finance, phir baaki stubs.
3. Har row complete hone par: **matrix update** + `npm` / `pytest` + PR.
4. **Stub → full** promote karte waqt neeche wala **checklist** repeat karo.

**▶ Abhi start:** Week 1 execution — **`docs/PARITY_SPRINT_1.md`** (day-by-day + Wave A manual verify table).

---

## Phase 0 — Legacy discovery (product / owner; repo se guess nahi)

| Step | Output |
|------|--------|
| 0.1 | Legacy app ka **navigation tree** (section → label → URL path) — spreadsheet / doc id |
| 0.2 | Har important screen par **role** (admin / leader / team) — kaun dekhta hai |
| 0.3 | **Evidence pack** per screen: 1–2 screenshots + date, ya old repo path + tag, ya written spec |
| 0.4 | `LEGACY_PARITY_MAPPING.md` ke **Parity matrix** mein har meaningful legacy screen ke liye ek row: **Legacy ref** + **Evidence id** bharein; **New path** column mein best‑fit `/dashboard/...` (guess nahi — agar unsure ho to row mat bharen) |

Is phase ke bina **implementation order** sirf “new app readiness” ke hisaab se hoga, legacy parity claim nahi.

---

## Side‑by‑side master table (template)

Har **new app path** ke liye ek line maintain karo (copy `LEGACY_PARITY_MAPPING` / spreadsheet mein).

| Wave | Legacy screen / menu (TBD) | Evidence ref (TBD) | New path | Ab kya hai (fact) | Target | Status |
|------|----------------------------|--------------------|----------|-------------------|--------|--------|
| A | | | `work/leads` | full | verify vs legacy | ☐ |
| A | | | `work/workboard` | full | verify vs legacy | ☐ |
| … | | | … | full / stub | full + parity / stub OK | ☐ |

**Status:** `TBD` · `verified` · `in progress` · `done` · `won’t match (reason + sign‑off)`.

---

## New app — suggested wave order (dependency + business impact)

Yeh order **implement / review** ke liye hai. Legacy row jis wave mein aaye, wahan **side‑by‑side** compare karo.

### Wave A — Core pipeline (already `full`; mostly **verify + tweak**)

| New path | Component | Notes |
|----------|-----------|--------|
| `work/leads` | `LeadsWorkPage` | List, filters, archive, admin pool actions |
| `work/workboard` | `WorkboardPage` | Kanban snapshot; same scope as leads API |
| `work/archived` | `LeadsWorkPage` archived | |
| `work/add-lead` | `LeadsWorkPage` | Same surface as leads |
| `work/follow-ups` | `FollowUpsWorkPage` | Admin + leader only (routes JSON) |
| `work/retarget` | `RetargetWorkPage` | |
| `work/lead-flow` | `LeadFlowPage` | Read‑only diagram |
| `work/lead-pool` / `work/lead-pool-admin` | `LeadPoolWorkPage` | Two paths, same UI kind |
| `work/recycle-bin` | `RecycleBinWorkPage` | |
| `intelligence` | `IntelligenceWorkPage` | Needs `meta.features.intelligence` |

**Wave A checklist (per row):** Legacy evidence → compare flows (create lead, move status, pool, archive) → gaps list → small PRs → matrix `verified`.

### Wave B — Team (mix of `full` + **stub**)

| New path | Now | Typical promotion |
|----------|-----|-------------------|
| `team/members` | full | verify vs legacy admin member list |
| `team/enrollment-approvals` | full | verify INR / approval flow |
| `team/my-team` | full | today may be self‑only stub note — parity may need **backend hierarchy** |
| `team/reports` | **stub** | stub → full: API + UI |
| `team/approvals` | **stub** | stub → full or merge with enrollment — **product call** |

### Wave C — System & Analytics (`full` pages; **content depth** varies)

| New path | Surface | Parity = mostly **data + copy** from legacy |
|----------|---------|---------------------------------------------|
| `system/training` | `SystemSurfacePage` | |
| `system/decision-engine` | `SystemSurfacePage` | |
| `system/coaching` | `SystemSurfacePage` | |
| `analytics/activity-log` | `AnalyticsSurfacePage` | |
| `analytics/day-2-report` | `AnalyticsSurfacePage` | |

### Wave D — Finance

| New path | Now | Notes |
|----------|-----|--------|
| `finance/wallet` | full | Ledger‑backed |
| `finance/recharges` | full | Admin |
| `finance/budget-export` | **stub** | promote when spec ready |
| `finance/monthly-targets` | **stub** | |
| `finance/lead-pool` | **stub** | name collision with work lead pool — clarify product |

### Wave E — Execution (both **stub**)

| New path | Stub API |
|----------|----------|
| `execution/at-risk-leads` | `/api/v1/execution/at-risk-leads` |
| `execution/lead-ledger` | `/api/v1/execution/lead-ledger` |

### Wave F — Other & Settings (all **stub** today)

Promote jab legacy evidence + priority mile — `ShellStubPage` pattern se `full` + real router.

---

## Default first stub → `full` (engineering suggestion — **product confirms**)

Jab product ne priority na di ho, pehla promote candidate pick karte waqt: **chhota scope**, **clear GET stub**, **kam cross‑cut**.

| Order | New path | Why start here |
|-------|----------|----------------|
| 1 (suggested) | `team/reports` | Wave B; isolated list/report UI; stub API `GET /api/v1/team/reports` already wired in registry |
| 2 | `other/notice-board` | Often simple read‑only feed |
| 3 | `execution/at-risk-leads` | If ops needs execution visibility before team reports |

**Product:** Ek row choose karo → `LEGACY_PARITY_MAPPING.md` mein evidence + acceptance → phir neeche **Stub → full** checklist run karo.

---

## Stub → `full` — har feature ke liye same engineering checklist

1. **Spec gate:** Legacy evidence row in `LEGACY_PARITY_MAPPING.md` (acceptance: fields, roles, errors).
2. **Backend:** Router under `backend/app/api/v1/`; Pydantic schemas; auth deps; **`pytest`** (`tests/`).
3. **Frontend:**  
   - `DASHBOARD_ROUTE_DEFS`: `surface: 'full'`, `ui: { kind: '…' }` (new kind if needed).  
   - `DashboardNestedPage` switch branch.  
   - Remove path from stub map (registry drives this).  
4. **Roles:** `dashboard-route-roles.json` only — server must enforce same rules.  
5. **Docs:** Matrix row status → `done` or `partial` with reason.

---

## Cross‑cutting gaps (plan mein alag line items)

| Topic | When to tackle |
|--------|----------------|
| **Leader = team pipeline (org‑wide)** | `lead_scope.py` + user hierarchy — **only after** legacy evidence defines it |
| **Intelligence** | Flag + real module — product |
| **Header search** | Already wired to leads `?q=` — extend if legacy expects global search |

---

## Execution rhythm (suggested)

| Cadence | Action |
|---------|--------|
| Weekly | Pick **one** Wave A/B row → evidence → implement gaps → verify |
| Per PR | Update matrix status + screenshot or API note |
| Milestone | `MYLE_VL2_CHECKLIST.md` + `npm run build` / `pytest` |

---

## File index

| Doc | Role |
|-----|------|
| `LEGACY_PARITY_MAPPING.md` | Inventory + **evidence‑backed** parity matrix |
| `DASHBOARD_UX_AND_PARITY.md` | Stub vs full UX explanation |
| `MYLE_VL2_ROADMAP.md` | Phases + product boundaries |
| `PARITY_ROLLOUT_PLAN.md` | **This file** — order + checklist |
| `TEAM_MIGRATION_PLAYBOOK.md` | **Existing team** — smooth shift (pilot, parallel run, training, support) |
| `PARITY_SPRINT_1.md` | **Week 1** — start execution (product + eng parallel) |

Is plan ko **living doc** maano: jab naya dashboard path add ho, Wave table mein nayi line daalo.
