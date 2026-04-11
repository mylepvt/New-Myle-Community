# Parity Sprint 1 — plan ke sath start (Week 1)

**Goal:** Plan activate karna — **product track** (evidence) aur **engineering track** (Wave A verify) **parallel**.

**Timebox:** ~5 working days. Owner assign karo (tum + Sam + 1 engineer).

**Sprint status:** **Repo / engineering track complete** for automated verification + docs (2026-04-10). Browser **manual** UI checks remain operator-owned when convenient.

---

## Day 1 — Kickoff (2–3 hours)

| Who | Task | Done |
|-----|------|------|
| Product | Legacy app se **nav tree** export (sheet / doc): section → label → URL → paste **`LEGACY_PARITY_MAPPING.md` → Phase 0.1 table** | ☐ |
| Product | **`LEGACY_PARITY_MAPPING.md`** matrix: **≥5 rows** with **Evidence ids** (`EVID-2026-00x`) — legacy labels Phase 0.1 se replace karo jab export ho | ✅ *(starter rows + ids in repo)* |
| Eng | Repo pull; `docker compose up` (ya apna env); dev login; **`/dashboard`** open (**manual UI**) | ☐ |
| Eng | **Automated baseline (CI):** `pytest` + `npm run build` + `npm test` + **`npm run lint`** — green | ✅ |
| Eng | **Wave A API smoke:** `bash scripts/verify_wave_a.sh` | ✅ |

---

## Day 2–3 — Product: Phase 0 depth

| Task | Done |
|------|------|
| Har major role (admin / leader / team) se **1 user journey** screenshot + short note | ☐ |
| **Pilot group** 3–5 log fix karo (names + roles) — update **`TEAM_MIGRATION_PLAYBOOK.md`** pilot table | ☐ |
| **`TEAM_MIGRATION_PLAYBOOK.md`** → support channel + owner assign | ☐ |

---

## Day 2–3 — Engineering: Wave A verify

“Legacy match” sirf matrix evidence ke baad; yahan **nayi app readiness** + **API contract** verify.

### Auth & shell (browser — manual)

| # | Check | Pass |
|---|--------|------|
| 1 | Login → `/dashboard` load; sidebar links visible for your role | ☐ |
| 2 | Header search: type text → Enter → `/dashboard/work/leads?q=...` | ☐ |
| 3 | Logout works | ☐ |

### Core pipeline — API automated (repo)

| # | Path | Automated coverage | Pass |
|---|------|-------------------|------|
| 4 | `work/leads` | `tests/test_api_v1_leads.py` (CRUD, archive, pool, filters) | ✅ |
| 5 | `work/workboard` | `tests/test_api_v1_workboard.py` | ✅ |
| 6 | `work/follow-ups` | `tests/test_api_v1_follow_ups.py` | ✅ |
| 7 | Gate / shell insights | `tests/test_api_v1_gate_assistant.py` | ✅ |
| 8 | `meta` + `auth/me` | `tests/test_api_v1_meta.py`, `tests/test_api_v1_auth_me.py` | ✅ |

**Run locally:** `bash scripts/verify_wave_a.sh` (subset of full suite).

### Core pipeline — browser (manual)

| # | Path | Check | Pass |
|---|------|--------|------|
| M1 | `work/leads` | Create lead; filter; archive; restore | ☐ |
| M2 | `work/workboard` | Columns; status dropdown on card | ☐ |
| M3 | `work/follow-ups` | Opens admin/leader; team → gate | ☐ |
| M4 | `work/lead-pool` / admin pool | Role-appropriate; claim | ☐ |
| M5 | `work/recycle-bin` | Admin list | ☐ |
| M6 | `intelligence` | Gated by `meta.features.intelligence` | ☐ |

### Notes column (eng)

| # | Issue | Ticket / PR |
|---|--------|-------------|
| | | |

---

## Day 4 — Sync (filled for repo-side closeout)

| Task | Done |
|------|------|
| Product + Eng: **gaps** list — see **Gap list** below | ✅ (initial) |
| Matrix Wave A **new paths** — status | ✅ see **Wave A matrix status** |

---

## Day 5 — Close sprint

### Five-bullet summary (Slack / Notion)

1. **Evidence matrix:** Phase 0.1 paste table + 6 starter rows with `EVID-2026-001`…`006` in [`LEGACY_PARITY_MAPPING.md`](LEGACY_PARITY_MAPPING.md); product replaces TBD legacy labels when nav export lands.
2. **Automated Wave A API tests** pass via `scripts/verify_wave_a.sh` + full `pytest` in CI.
3. **First stub→full suggestion:** `team/reports` (product confirms) — [`PARITY_ROLLOUT_PLAN.md`](PARITY_ROLLOUT_PLAN.md).
4. **Migration:** Pilot + support **table structure** in [`TEAM_MIGRATION_PLAYBOOK.md`](TEAM_MIGRATION_PLAYBOOK.md) — assign names + channel.
5. **Next sprint:** Browser manual checklist (M1–M6) + product screenshots; optional first stub→full after product pick.

| Task | Done |
|------|------|
| Short **summary** broadcast | ✅ (bullets above in repo) |
| Next sprint scope | ✅ Wave A UI manual + stub→full after product |

---

## Gap list (initial — 2026-04-10)

| Area | Gap | Owner |
|------|-----|--------|
| Legacy labels | Phase 0.1 nav table empty until product pastes export | Product |
| Browser UI | Manual rows M1–M6 unchecked — needs human QA | Eng |
| Stubs | Execution, Other, Settings, many Finance rows still `ShellStubPage` | Product priority → eng |
| Leader scope | Org-wide team pipeline not modeled — `lead_scope.py` | Product spec + eng |

---

## Wave A matrix status (new app paths — internal verify)

| New path | Internal status | Notes |
|----------|-----------------|-------|
| `work/leads` | verified (API) | Browser manual ☐ |
| `work/workboard` | verified (API) | Browser manual ☐ |
| `work/follow-ups` | verified (API) | Browser manual ☐ |
| `work/archived` | verified (API) | covered in leads tests |
| `work/lead-pool*` | verified (API) | pool/claim in leads tests |
| `work/recycle-bin` | verified (API) | admin delete flow in leads tests |
| `intelligence` | TBD (flag) | `meta.features.intelligence` |

**Legacy parity:** matrix rows stay **TBD** until Phase 0.1 + evidence attachments.

---

## Commands (reference)

```bash
# Wave A API subset
bash scripts/verify_wave_a.sh

# Backend (full)
cd backend && pytest ../tests/ -q

# Frontend
cd frontend && npm run build && npm test && npm run lint
```

---

## Related

- `PARITY_ROLLOUT_PLAN.md` — waves + stub checklist + default first stub  
- `LEGACY_PARITY_MAPPING.md` — evidence matrix  
- `TEAM_MIGRATION_PLAYBOOK.md` — team shift  

**Agla sprint:** Browser manual completion → product evidence → first **stub → full** per product pick.
