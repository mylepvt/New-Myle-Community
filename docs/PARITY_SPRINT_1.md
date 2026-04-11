# Parity Sprint 1 — plan ke sath start (Week 1)

**Goal:** Plan activate karna — **product track** (evidence) aur **engineering track** (Wave A verify) **parallel**.

**Timebox:** ~5 working days. Owner assign karo (tum + Sam + 1 engineer).

**Sprint status:** ▶ **Started** — Day 1 eng baseline run (automated) ✅ 2026-04-10.

---

## Day 1 — Kickoff (2–3 hours)

| Who | Task | Done |
|-----|------|------|
| Product | Legacy app se **nav tree** export (sheet / doc): section → label → URL | ☐ |
| Product | **`LEGACY_PARITY_MAPPING.md`** matrix mein **kam se kam 5 rows** start karo: legacy name + evidence id (screenshot link / doc id) — **New path** sirf jab confident ho | ☐ |
| Eng | Repo pull; `docker compose up` (ya apna env); dev login; **`/dashboard`** open (**manual**) | ☐ |
| Eng | **Automated baseline (CI):** `pytest` (90) + `npm run build` + `npm test` + **`npm run lint`** — green | ✅ |

---

## Day 2–3 — Product: Phase 0 depth

| Task | Done |
|------|------|
| Har major role (admin / leader / team) se **1 user journey** screenshot + short note | ☐ |
| **Pilot group** 3–5 log fix karo (names + roles) | ☐ |
| **`TEAM_MIGRATION_PLAYBOOK.md`** → “Owner checklist” mein se **pilot + support channel** line items assign | ☐ |

---

## Day 2–3 — Engineering: Wave A manual verify (no legacy claim)

Nayi app paths **chalti hain** — yeh checklist **regression / readiness** hai; “legacy match” sirf matrix evidence ke baad.

### Auth & shell

| # | Check | Pass |
|---|--------|------|
| 1 | Login → `/dashboard` load; sidebar links visible for your role | ☐ |
| 2 | Header search: type text → Enter → `/dashboard/work/leads?q=...` | ☐ |
| 3 | Logout works | ☐ |

### Core pipeline (Wave A)

| # | Path | Check | Pass |
|---|------|--------|------|
| 4 | `work/leads` | Create lead; filter status; archive one; restore from archived | ☐ |
| 5 | `work/workboard` | Columns load; change status dropdown on card | ☐ |
| 6 | `work/follow-ups` | Opens (admin/leader only); team user par route gate → home OK | ☐ |
| 7 | `work/lead-pool` / admin pool | As per role; claim if applicable | ☐ |
| 8 | `work/recycle-bin` | List loads (admin) | ☐ |
| 9 | `intelligence` | Only if `meta.features.intelligence` true; else hidden / redirect | ☐ |

### Notes column (eng)

| # | Issue | Ticket / PR |
|---|--------|-------------|
| | | |

---

## Day 4 — Sync

| Task | Done |
|------|------|
| Product + Eng: **gaps** list — “stub hai”, “behavior alag”, “data chahiye” | ☐ |
| Matrix mein har Wave A row ke liye status: `TBD` / `verified (internal)` / `blocked` | ☐ |

**“Verified (internal)”** = nayi app mein flow OK; **legacy parity** tabhi `verified` jab evidence row complete ho.

---

## Day 5 — Close sprint

| Task | Done |
|------|------|
| Short **summary** (5 bullets) Notion / Slack — kya verify hua, kya next sprint | ☐ |
| Next sprint: **Wave A tweaks** (small PRs) **ya** pehla **stub → full** (product priority se) | ☐ |

---

## Commands (reference)

```bash
# Backend
cd backend && pytest ../tests/ -q

# Frontend
cd frontend && npm run build && npm test
```

---

## Related

- `PARITY_ROLLOUT_PLAN.md` — waves + stub checklist  
- `LEGACY_PARITY_MAPPING.md` — evidence matrix  
- `TEAM_MIGRATION_PLAYBOOK.md` — team shift  

**Agla sprint:** `PARITY_SPRINT_2.md` tab banao jab Sprint 1 close ho (optional; ya isi file mein “Sprint 2” section add karo).
