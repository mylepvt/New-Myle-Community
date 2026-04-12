# Core app structure (product lock)

**Canonical narrative:** role-based CRM + execution — `team` / `leader` / `admin`. Onboarding → wallet → lead pool claim → prospecting pipeline → proof → Day 1 / Day 2 + test → interview → seat hold → converted → daily reporting and org monitoring.

**Implementation map:** sidebar order, paths, and roles are defined only in:

- `frontend/src/config/dashboard-registry.ts` — `DASHBOARD_ROUTE_DEFS`
- `frontend/src/config/dashboard-route-roles.json`

Do not add parallel nav lists elsewhere.

## Spine (user journey)

1. Register → admin approval → login → **training gate** (if required) → dashboard. **Shell:** when `users.training_required` and `training_status` ≠ `completed`, the app redirects to **`/dashboard/system/training`** and hides other nav (JWT claims `training_required` + `training_status`). **Admin:** pending signups → **`/dashboard/team/approvals`** (`GET/POST /api/v1/team/pending-registrations/...`). **Training complete** when certification test passes **or** all catalog days marked done (`POST /api/v1/system/training/mark-day` per day) — server sets `training_status=completed`, `training_required=false`; client calls **`POST /auth/sync-identity`** to refresh JWT.
2. **Wallet:** recharge request → admin credit.
3. **Lead pool:** claim (atomic assign + rules).
4. **Execution:** My Leads / Workboard — pipeline stages aligned with `Lead.status` / workboard.
5. **Enrollment:** video link → watch sync → ₹196 proof → leader/admin approval → Day 1 onward.
6. **Side flows:** follow-ups, retarget, archived, recycle (work section).
7. **Reporting:** daily report, team reports, notice board, leaderboard, live session (**Community**).
8. **System:** training, decision engine, coaching, activity log, Day 2 test report (admin monitoring).
9. **Settings:** general, help, org tree (admin).

## Section labels (sidebar)

| Section id | Label | Purpose |
|------------|--------|---------|
| `main` | — | Dashboard home |
| `work` | — | Leads, workboard, pool, intelligence (flagged), side flows |
| `finance` | Wallet | Wallet, recharges, recharge request/admin |
| `team` | Team | Members, reports, approvals, ₹196 approvals, my team |
| `other` | Community | Leaderboard, notice board, live session, daily report |
| `system` | System | Training, coaching, decision engine, activity, Day 2 report |
| `settings` | Settings | Admin settings stubs |

## Removed from nav (by design)

Duplicate or non-core dashboard entries were dropped: second training path, finance budget/monthly/duplicate lead-pool stubs, execution dashboard pages, duplicate “all members” under Settings. **Backend routes** for execution/finance/other may still exist for API/tests; they are not surfaced in the shell until product promotes them again.

## Parity claims

Behaviour vs the shipped Flask app remains governed by **`docs/LEGACY_PARITY_MAPPING.md`** and **`docs/LEGACY_100_PARITY_LOCK.md`**. This doc is **IA + journey only**, not a legacy evidence matrix.
