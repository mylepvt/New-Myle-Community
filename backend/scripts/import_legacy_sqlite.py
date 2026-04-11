#!/usr/bin/env python3
"""
Import rows from a legacy Flask Myle SQLite DB into the vl2 PostgreSQL database.

Read mapping rules in: legacy/LEGACY_TO_VL2_MAPPING.md

Examples (run from ``backend/`` so ``app`` package resolves):

  # Plan only — no writes
  python scripts/import_legacy_sqlite.py --dry-run --legacy-db /path/to/leads.db

  # Import (set DATABASE_URL / .env like the API)
  python scripts/import_legacy_sqlite.py --legacy-db /path/to/leads.db

  # Save legacy→new id maps for debugging
  python scripts/import_legacy_sqlite.py --dry-run --legacy-db ./leads.db --write-mapping /tmp/legacy_maps.json

Environment:
  IMPORT_DEFAULT_PASSWORD  If legacy password hash is not bcrypt, new users get this password
                           (bcrypt-hashed on insert). Default: ChangeMeAfterImport!
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ``backend/`` — same layout as ``scripts/create_user.py`` (FastAPI + pydantic-settings + ``DATABASE_URL``).
BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

try:
    from dotenv import load_dotenv
except ImportError:
    pass
else:
    load_dotenv(BACKEND / ".env")
    load_dotenv(BACKEND.parent / ".env")

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.constants.roles import ROLES_SET
from app.core.lead_status import LEAD_STATUS_SET
from app.core.passwords import hash_password
from app.db.session import AsyncSessionLocal
from app.models.activity_log import ActivityLog
from app.models.lead import Lead
from app.models.user import User
from app.models.wallet_recharge import WalletRecharge

_LEGACY_SOURCE_ALIASES = {
    "fb": "facebook",
    "facebook": "facebook",
    "ig": "instagram",
    "instagram": "instagram",
    "referral": "referral",
    "ref": "referral",
    "walk": "walk_in",
    "walk_in": "walk_in",
    "walk-in": "walk_in",
    "other": "other",
}

_PAYMENT_OK = frozenset({"pending", "proof_uploaded", "approved", "rejected"})
_CALL_OK = frozenset(
    {
        "not_called",
        "called",
        "callback_requested",
        "not_interested",
        "converted",
    }
)


def _parse_ts(val: Any) -> datetime | None:
    if val is None:
        return None
    s = str(val).strip()
    if not s:
        return None
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def _norm_role(raw: str) -> str:
    r = (raw or "team").strip().lower()
    return r if r in ROLES_SET else "team"


def _norm_email(username: str, legacy_id: int, raw_email: str) -> str:
    e = (raw_email or "").strip().lower()
    if e:
        return e
    safe = re.sub(r"[^a-z0-9._+-]", "_", (username or f"user{legacy_id}").lower())[:80]
    return f"{safe}.{legacy_id}@legacy.import.local"


def _norm_fbo(raw: str, legacy_id: int) -> str:
    s = (raw or "").strip()
    if s:
        return s.lower()[:64]
    return f"legacy-{legacy_id}"


def normalize_lead_status(raw: str) -> str:
    x = (raw or "").strip().lower()
    if x in LEAD_STATUS_SET:
        return x
    if any(k in x for k in ("lost", "retarget")):
        return "lost"
    if any(k in x for k in ("won", "convert", "paid", "complete", "closing")):
        return "won"
    if any(k in x for k in ("contact", "call", "follow")):
        return "contacted"
    if "qualif" in x:
        return "qualified"
    return "new"


def normalize_source(raw: str | None) -> str | None:
    if raw is None:
        return None
    s = (raw or "").strip().lower()
    if not s:
        return None
    if s in _LEGACY_SOURCE_ALIASES:
        return _LEGACY_SOURCE_ALIASES[s]
    if s in ("facebook", "instagram", "referral", "walk_in", "other"):
        return s
    return "other"


def normalize_call_status(raw: str | None) -> str | None:
    if raw is None:
        return None
    s = (raw or "").strip().lower().replace(" ", "_")
    if not s:
        return "not_called"
    if s in _CALL_OK:
        return s
    if "not" in s and "call" in s:
        return "not_called"
    if "call" in s or "contact" in s:
        return "called"
    return "not_called"


def normalize_payment_status_from_legacy(
    payment_done: int | None, raw: str | None,
) -> str | None:
    if raw:
        t = raw.strip().lower()
        if t in _PAYMENT_OK:
            return t
    if payment_done:
        return "approved"
    return "pending"


def legacy_table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    ).fetchone()
    return row is not None


def migrate_password_hash(legacy_pw: str) -> str | None:
    """Return hash string usable by vl2 (bcrypt) or None if importer must set default."""
    p = legacy_pw or ""
    if p.startswith("$2a$") or p.startswith("$2b$") or p.startswith("$2y$"):
        return p
    return None


async def import_users_phase(
    legacy: sqlite3.Connection,
    dry_run: bool,
    default_pw_hash: str,
) -> dict[int, int]:
    """legacy user id -> new users.id"""
    mapping: dict[int, int] = {}
    rows = legacy.execute("SELECT * FROM users ORDER BY id").fetchall()
    if not rows:
        print("  [users] no rows in legacy DB")
        return mapping

    print(f"  [users] legacy rows: {len(rows)}")

    if dry_run:
        for row in rows[:3]:
            print(f"    sample id={row['id']} username={row['username']!r} fbo={row['fbo_id']!r}")
        if len(rows) > 3:
            print(f"    ... and {len(rows) - 3} more (dry-run)")
        return mapping

    skipped = 0
    for row in rows:
        lid = int(row["id"])
        username = str(row["username"] or "").strip()
        email = _norm_email(username, lid, str(row["email"] or ""))
        fbo = _norm_fbo(str(row["fbo_id"] or ""), lid)
        role = _norm_role(str(row["role"] or "team"))
        hp = migrate_password_hash(str(row["password"] or ""))
        if hp is None:
            hp = default_pw_hash

        u = User(
            fbo_id=fbo,
            username=username or None,
            email=email,
            role=role,
            hashed_password=hp,
        )
        async with AsyncSessionLocal() as session:
            session.add(u)
            try:
                await session.commit()
                await session.refresh(u)
                mapping[lid] = u.id
            except IntegrityError as e:
                await session.rollback()
                skipped += 1
                print(f"    SKIP legacy user id={lid} ({e.orig})")

    print(f"  [users] imported {len(mapping)}, skipped {skipped}")
    return mapping


async def pick_default_creator_id(user_map: dict[int, int]) -> int:
    """Prefer any admin in DB (e.g. dev seed); else smallest imported user id."""
    async with AsyncSessionLocal() as session:
        r = await session.execute(select(User).where(User.role == "admin").limit(1))
        admin = r.scalar_one_or_none()
        if admin is not None:
            return admin.id
    return min(user_map.values()) if user_map else 1


def build_username_to_new_id(
    legacy: sqlite3.Connection,
    user_map: dict[int, int],
) -> dict[str, int]:
    out: dict[str, int] = {}
    for row in legacy.execute("SELECT id, username FROM users"):
        lid = int(row["id"])
        if lid not in user_map:
            continue
        un = str(row["username"] or "").strip().lower()
        if un:
            out[un] = user_map[lid]
    return out


async def import_leads_phase(
    legacy: sqlite3.Connection,
    user_map: dict[int, int],
    dry_run: bool,
) -> dict[int, int]:
    """legacy lead id -> new lead id"""
    lead_map: dict[int, int] = {}
    if not legacy_table_exists(legacy, "leads"):
        print("  [leads] table missing")
        return lead_map

    rows = legacy.execute("SELECT * FROM leads ORDER BY id").fetchall()
    if not rows:
        print("  [leads] no rows")
        return lead_map

    print(f"  [leads] legacy rows: {len(rows)}")

    if dry_run:
        for row in rows[:2]:
            print(
                f"    sample id={row['id']} name={row['name']!r} status={row['status']!r}",
            )
        return lead_map

    default_creator = await pick_default_creator_id(user_map)

    async with AsyncSessionLocal() as session:
        for row in rows:
            lid = int(row["id"])
            keys = row.keys()

            assigned_raw = row["assigned_user_id"] if "assigned_user_id" in keys else None
            try:
                aid = int(assigned_raw) if assigned_raw not in (None, "") else None
            except (TypeError, ValueError):
                aid = None
            assigned_new = user_map.get(aid) if aid else None
            creator = assigned_new if assigned_new is not None else default_creator

            name = str(row["name"] or "Imported").strip() or "Imported"
            status = normalize_lead_status(str(row["status"] or "new"))
            phone = (str(row["phone"]) if row["phone"] else None) or None
            em = str(row["email"]).strip() if "email" in keys and row["email"] else None
            email = em or None
            city = (
                str(row["city"]).strip()
                if "city" in keys and row["city"]
                else None
            ) or None
            src = normalize_source(
                str(row["source"]) if "source" in keys else None,
            )
            notes = row["notes"] if "notes" in keys else None
            notes_s = str(notes) if notes else None

            deleted_at = _parse_ts(row["deleted_at"]) if "deleted_at" in keys else None
            if deleted_at is None and "deleted_at" in keys:
                ds = str(row["deleted_at"] or "").strip()
                if ds == "":
                    deleted_at = None

            in_pool = bool(int(row["in_pool"] or 0)) if "in_pool" in keys else False

            cc = int(row["contact_count"] or 0) if "contact_count" in keys else 0
            last_c = (
                _parse_ts(row["last_contacted"])
                if "last_contacted" in keys
                else None
            )

            cr = str(row["call_result"] or "") if "call_result" in keys else ""
            call_st = normalize_call_status(cr)

            pd = int(row["payment_done"] or 0) if "payment_done" in keys else 0
            pamt = float(row["payment_amount"] or 0) if "payment_amount" in keys else 0.0
            amt_cents = int(round(pamt * 100)) if pamt else None

            pay_raw = str(row["payment_status"]) if "payment_status" in keys else None
            pay_st = normalize_payment_status_from_legacy(pd, pay_raw)

            proof = (
                str(row["payment_proof_path"])
                if "payment_proof_path" in keys and row["payment_proof_path"]
                else None
            )

            d1 = bool(int(row["day1_done"] or 0)) if "day1_done" in keys else False
            d2 = bool(int(row["day2_done"] or 0)) if "day2_done" in keys else False
            d3 = bool(int(row["interview_done"] or 0)) if "interview_done" in keys else False
            upd = _parse_ts(row["updated_at"]) if "updated_at" in keys else None

            lead = Lead(
                name=name[:255],
                status=status[:32],
                created_by_user_id=creator,
                phone=phone[:20] if phone else None,
                email=email[:320] if email else None,
                city=city[:100] if city else None,
                source=src[:50] if src else None,
                notes=notes_s,
                archived_at=None,
                deleted_at=deleted_at,
                in_pool=in_pool,
                assigned_to_user_id=assigned_new,
                call_status=call_st[:32] if call_st else None,
                call_count=cc,
                last_called_at=last_c,
                payment_status=pay_st[:32] if pay_st else None,
                payment_amount_cents=amt_cents,
                payment_proof_url=proof[:500] if proof else None,
                day1_completed_at=upd if d1 else None,
                day2_completed_at=upd if d2 else None,
                day3_completed_at=upd if d3 else None,
            )
            session.add(lead)
            await session.flush()
            lead_map[lid] = lead.id

        await session.commit()

    print(f"  [leads] imported {len(lead_map)}")
    return lead_map


async def import_wallet_phase(
    legacy: sqlite3.Connection,
    user_map: dict[int, int],
    dry_run: bool,
) -> int:
    if not legacy_table_exists(legacy, "wallet_recharges"):
        print("  [wallet_recharges] table missing")
        return 0
    rows = legacy.execute("SELECT * FROM wallet_recharges ORDER BY id").fetchall()
    print(f"  [wallet_recharges] legacy rows: {len(rows)}")
    if dry_run or not rows:
        return 0

    uname_to_id = build_username_to_new_id(legacy, user_map)
    n = 0
    async with AsyncSessionLocal() as session:
        for row in rows:
            un = str(row["username"] or "").strip().lower()
            uid = uname_to_id.get(un)
            if uid is None:
                continue
            amt = float(row["amount"] or 0)
            cents = int(round(amt * 100))
            st = str(row["status"] or "pending").strip().lower()
            if st not in ("pending", "approved", "rejected"):
                st = "pending"
            wr = WalletRecharge(
                user_id=uid,
                amount_cents=cents,
                utr_number=(str(row["utr_number"])[:50] if row["utr_number"] else None),
                status=st,
                admin_note=(str(row["admin_note"])[:512] if row["admin_note"] else None),
            )
            session.add(wr)
            n += 1
        await session.commit()
    print(f"  [wallet_recharges] imported {n}")
    return n


async def import_activity_phase(
    legacy: sqlite3.Connection,
    user_map: dict[int, int],
    dry_run: bool,
) -> int:
    if not legacy_table_exists(legacy, "activity_log"):
        print("  [activity_log] table missing")
        return 0
    rows = legacy.execute("SELECT * FROM activity_log ORDER BY id").fetchall()
    print(f"  [activity_log] legacy rows: {len(rows)}")
    if dry_run or not rows:
        return 0

    uname_to_id = build_username_to_new_id(legacy, user_map)
    n = 0
    async with AsyncSessionLocal() as session:
        for row in rows:
            un = str(row["username"] or "").strip().lower()
            uid = uname_to_id.get(un)
            if uid is None:
                continue
            ev = str(row["event_type"] or "import")[:100]
            det = str(row["details"] or "")
            meta = {"detail": det} if det else None
            ip = str(row["ip_address"] or "")[:45] or None
            created = _parse_ts(row["created_at"]) or datetime.now(timezone.utc)
            log = ActivityLog(
                user_id=uid,
                action=ev,
                entity_type=None,
                entity_id=None,
                meta=meta,
                ip_address=ip,
                created_at=created,
            )
            session.add(log)
            n += 1
        await session.commit()
    print(f"  [activity_log] imported {n}")
    return n


async def _pg_smoke() -> None:
    async with AsyncSessionLocal() as s:
        await s.execute(text("SELECT 1"))


async def main() -> int:
    p = argparse.ArgumentParser(description="Import legacy SQLite into vl2 PostgreSQL")
    p.add_argument(
        "--legacy-db",
        default=os.environ.get("LEGACY_SQLITE_PATH", ""),
        help="Path to legacy leads.db (or set LEGACY_SQLITE_PATH)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not write to PostgreSQL; print counts and samples",
    )
    p.add_argument(
        "--write-mapping",
        default="",
        help="Write JSON file with legacy→new id maps (users + leads)",
    )
    p.add_argument("--users-only", action="store_true")
    p.add_argument("--skip-wallet", action="store_true")
    p.add_argument("--skip-activity", action="store_true")
    p.add_argument(
        "--sqlite-only",
        action="store_true",
        help="Do not connect to PostgreSQL (for dry-run inspection without API DB)",
    )
    args = p.parse_args()

    db_path = (args.legacy_db or "").strip()
    if not db_path:
        print("Provide --legacy-db or LEGACY_SQLITE_PATH", file=sys.stderr)
        return 1
    lp = Path(db_path).expanduser().resolve()
    if not lp.is_file():
        print(f"Not a file: {lp}", file=sys.stderr)
        return 1

    os.environ.setdefault(
        "IMPORT_DEFAULT_PASSWORD",
        "ChangeMeAfterImport!",
    )
    default_plain = os.environ["IMPORT_DEFAULT_PASSWORD"]
    default_pw_hash = hash_password(default_plain)

    dry_run = bool(args.dry_run or args.sqlite_only)

    print(f"Legacy DB: {lp}")
    print(f"Dry-run: {dry_run}" + (" (sqlite-only)" if args.sqlite_only else ""))

    legacy = sqlite3.connect(str(lp))
    legacy.row_factory = sqlite3.Row

    if not args.sqlite_only:
        try:
            await _pg_smoke()
        except Exception as e:
            print(f"PostgreSQL connection failed: {e}", file=sys.stderr)
            return 1

    user_map: dict[int, int] = {}
    lead_map: dict[int, int] = {}

    try:
        user_map = await import_users_phase(legacy, dry_run, default_pw_hash)
        if args.users_only:
            pass
        elif not dry_run and not user_map:
            print("No users imported; skipping leads.", file=sys.stderr)
        else:
            if dry_run:
                await import_leads_phase(legacy, user_map, True)
            else:
                lead_map = await import_leads_phase(legacy, user_map, False)
                if not args.skip_wallet:
                    await import_wallet_phase(legacy, user_map, False)
                if not args.skip_activity:
                    await import_activity_phase(legacy, user_map, False)
    finally:
        legacy.close()

    if args.write_mapping:
        out = {
            "users": {str(k): v for k, v in user_map.items()},
            "leads": {str(k): v for k, v in lead_map.items()},
        }
        Path(args.write_mapping).write_text(json.dumps(out, indent=2), encoding="utf-8")
        print(f"Wrote mapping: {args.write_mapping}")

    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
