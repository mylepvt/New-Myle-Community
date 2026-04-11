# Legacy SQLite (Flask) → Myle vl2 (PostgreSQL) mapping

Source: `legacy/myle_dashboard/database.py` (`init_db` + `migrate_db` columns).  
Target: `backend/app/models/*.py` + Alembic revisions.

**Conventions**

- Legacy stores many timestamps as **IST text** (`datetime('now', '+5 hours', '+30 minutes')`); vl2 uses **`timestamptz`** — import scripts must parse → aware UTC or Asia/Kolkata.
- Legacy **username** is the stable login handle; vl2 primary login is **`fbo_id`** + password, with **`email`** required — importers must synthesize or supply emails.
- Legacy lead **status** strings are free-form (e.g. `New`, `Paid ₹196`); vl2 uses **`app/core/lead_status.py`** — normalize in import or map to closest bucket.

---

## 1. Table-level map

| Legacy table | vl2 target | Notes |
|--------------|----------|--------|
| `users` | `users` | Narrower columns in vl2; see §3. Many legacy fields **not** in vl2 (training, badges JSON, …) — store in `meta` JSON later or drop for v1 import. |
| `leads` | `leads` | Legacy has **80+** columns after migrations; vl2 has a **reduced** model — see §4. Unmapped columns → optional JSON extension table / future migration. |
| `activity_log` | `activity_log` | Shape differs — see §5. |
| `wallet_recharges` | `wallet_recharges` | Legacy uses `username` + `REAL amount`; vl2 uses `user_id` + **`amount_cents`** `INTEGER`. |
| — | `wallet_ledger_entries` | **No** direct legacy table; vl2 ledger is append-only credits/debits. Rebuild from business rules or leave empty until post-migrate adjustments. |
| `lead_notes` | — | No `lead_notes` table in vl2; **notes on lead** are `leads.notes` (single text) or use **`activity_log`** / future timeline. |
| `daily_reports` | — | Not modeled in vl2 yet; keep in sidecar / CSV or new table later. |
| `team_members` | — | Not in vl2; overlap with users/network — ignore or manual. |
| `app_settings` | — | Use env + `GET /meta` in vl2; or seed `app_settings` if added. |
| `announcements` | — | Stub APIs only in vl2. |
| `push_subscriptions` | — | Not in vl2 core. |
| `password_reset_tokens` | — | vl2 auth flow differs (JWT cookies). |
| `training_*`, `targets`, `user_badges`, `training_questions`, … | — | Not in vl2 models; **out of scope** for first import unless you add tables. |
| `lead_stage_history`, `lead_assignments`, `admin_tasks`, … | — | Legacy-only; port only if product requires. |

---

## 2. Users (`users`)

| Legacy column | vl2 `User` column | Transform |
|---------------|-------------------|-----------|
| `id` | `id` | Remap FKs if IDs not preserved (prefer sequence on insert + mapping table `legacy_user_id → new_id`). |
| `username` | — | vl2 has optional `username` — copy as display handle. Login in vl2 is **`fbo_id`**-centric. |
| `password` | `hashed_password` | Legacy may be Werkzeug hash — if compatible with passlib/bcrypt used in vl2, copy; else force password reset. |
| `role` | `role` | Map strings: `team` / `leader` / `admin` — align with `app/types/role` / seed data. |
| `fbo_id` | `fbo_id` | Lowercase trim; must be **non-empty unique** in vl2. |
| `email` | `email` | If empty: e.g. `{sanitized_username}@legacy.import.local` (must stay unique). |
| `phone`, `upline_*`, `status`, `training_*`, `badges_json`, … | — | **Dropped** in minimal import; optional future columns or JSON profile table. |
| `created_at` | `created_at` | Parse text → `timestamptz`. |

---

## 3. Leads (`leads`)

| Legacy column | vl2 `Lead` column | Transform |
|---------------|-------------------|-----------|
| `id` | `id` | Same as users: mapping table if not identity-copy. |
| `name` | `name` | Direct. |
| `phone` | `phone` | Direct; normalize `+`/digits if needed. |
| `email` | `email` | Direct. |
| `source` | `source` | Direct (length check ≤ 50). |
| `status` | `status` | Normalize to vl2 allowed set / lowercase convention — see `lead_status.py`. |
| `notes` | `notes` | Direct. |
| `city` | `city` | Direct. |
| `deleted_at` (text `''` or ISO) | `deleted_at` | Empty string → `NULL`; else parse datetime. |
| `in_pool` (0/1) | `in_pool` | Boolean. |
| `assigned_user_id` | `assigned_to_user_id` | FK to `users.id` after user remap. |
| `contact_count` | `call_count` | Direct int. |
| `last_contacted` | `last_called_at` | Parse text → `timestamptz` or `NULL`. |
| `call_result` / pipeline call fields | `call_status` | Map loose legacy string → vl2 `call_status` enum width (e.g. `not_called`, …). |
| `payment_done` / `payment_amount` | `payment_status`, `payment_amount_cents` | `payment_amount` REAL rupees → **cents** `int`; derive `payment_status` from legacy flags. |
| `payment_proof_path` | `payment_proof_url` | If path is relative file, upload to storage first or store `file://` note — **manual** step often needed. |
| `day1_done` / `day2_done` / interview | `day*_completed_at` | If only flags: set completion time to legacy `updated_at` or `NULL` if unknown. |
| `created_at` | `created_at` | Parse. |
| `referred_by` | — | Append to `notes` or drop. |
| `assigned_to` (text) | — | Resolve via `assigned_user_id` primary. |
| `archived` | `archived_at` | Legacy may use separate concept — if only `status`/pipeline, map business rules. |
| `claimed_at`, `pool_price`, pipeline columns, `d1_morning`, … | — | **Not** on vl2 `Lead` model — store in **`meta` JSON** column if you add one, or separate `legacy_lead_extra` table, or omit v1. |

**vl2-only (no legacy column)**

- `created_by_user_id` — set from legacy owner creator or `assigned_user_id` / admin user id per rule.

---

## 4. Activity log

| Legacy | vl2 `ActivityLog` | Transform |
|--------|-------------------|-----------|
| `username` | `user_id` | Join `users` by legacy username → new id. |
| `event_type` | `action` | Direct or rename. |
| `details` | `meta` | Put string in `{"detail": "..."}` or parse JSON if legacy stored JSON. |
| — | `entity_type`, `entity_id` | Often `NULL` in legacy — fill when parseable. |
| `ip_address` | `ip_address` | Direct. |
| `created_at` | `created_at` | Parse. |

---

## 5. Wallet recharges

| Legacy | vl2 `WalletRecharge` | Transform |
|--------|----------------------|-----------|
| `username` | `user_id` | Resolve user. |
| `amount` (REAL rupees) | `amount_cents` | `round(amount * 100)`. |
| `utr_number` | `utr_number` | Direct. |
| `status` | `status` | Align enums (`pending` / `approved` / …). |
| `requested_at` | `created_at` | Parse. |
| `processed_at` | `reviewed_at` | Parse. |
| `admin_note` | `admin_note` | Direct. |
| — | `proof_url`, `reviewed_by_user_id`, `idempotency_key` | Optional / synthetic. |

---

## 6. Follow-ups & calls (no dedicated legacy tables in `init_db` core)

- Legacy may store follow-up dates **on `leads`** (`follow_up_date`, `follow_up_time`). vl2 has **`follow_ups`** rows — import by creating **`FollowUp`** per lead when dates/notes exist.
- Legacy has no `call_events` table in base `init_db`; vl2 **`call_events`** may be filled from `contact_count` + synthetic rows or left empty.

---

## 7. Suggested import order

1. `users` (with ID mapping)
2. `leads` (FK `created_by_user_id`, `assigned_to_user_id`)
3. `wallet_recharges`
4. `activity_log`
5. Optional: `follow_ups` / `call_events` derived from lead fields

---

## 8. Import script (implemented)

Run from **`backend/`** so the `app` package resolves — see **`backend/README.md`** for full setup, `.env`, and Docker.

| Command | Purpose |
|---------|---------|
| `python scripts/import_legacy_sqlite.py --sqlite-only --legacy-db /path/to/leads.db` | Inspect legacy SQLite only (no PostgreSQL). |
| `python scripts/import_legacy_sqlite.py --dry-run --legacy-db /path/to/leads.db` | Connect to PostgreSQL, print samples, **no writes**. |
| `python scripts/import_legacy_sqlite.py --legacy-db /path/to/leads.db` | Full import (`--users-only`, `--skip-wallet`, `--skip-activity` optional). |
| `IMPORT_DEFAULT_PASSWORD=…` | Used when legacy password hash is not bcrypt (Werkzeug etc.). |

- **`--write-mapping /path/to/maps.json`** — save legacy→new id maps after a real import.
- Env **`LEGACY_SQLITE_PATH`** can replace `--legacy-db`.

Adjust the script when Alembic adds columns; this doc stays the **field mapping contract**.

---

## 9. Supporting utilities

- **`scripts/legacy_sqlite_inspect.py`** — table list + row counts (read-only).
- Keep **`legacy_user_id → users.id`** and **`legacy_lead_id → leads.id`** JSON from `--write-mapping` for reruns and FK fixes.
