"""
Wallet pool-spend SSOT (single source of truth).

All pool purchase debits for a login user are summed from leads where that user is
the permanent buyer (``current_owner``), not ``assigned_user_id`` (execution).
Hier / Day‑1 handoff only moves ``assigned_user_id``; wallet spend must stay on the
buyer recorded at claim time.
"""
from __future__ import annotations

# SQL fragment: claimed off-pool rows attributable to this buyer for wallet math.
# Params: (owner_key,). ``current_owner`` is set at claim and must not follow handoffs.
_POOL_BUYER_CLAIMED = """
    in_pool = 0
    AND TRIM(COALESCE(deleted_at, '')) = ''
    AND TRIM(COALESCE(claimed_at, '')) != ''
    AND TRIM(COALESCE(current_owner, '')) = ?
"""


def _owner_key_for_ledger(db, username: str) -> str:
    """Strip / resolve login name for equality with ``leads.current_owner``."""
    raw = username or ""
    un = raw.strip()
    row = db.execute("SELECT id FROM users WHERE username=?", (raw,)).fetchone()
    if row is None and un != raw:
        row = db.execute("SELECT id FROM users WHERE username=?", (un,)).fetchone()
    return un


def sum_pool_spent_for_buyer(
    db,
    username: str,
    *,
    claimed_at_min: str | None = None,
    claimed_at_max: str | None = None,
) -> float:
    """SUM(pool_price) for leads charged to this buyer (wallet spent semantics)."""
    un = _owner_key_for_ledger(db, username)
    extra = ""
    params: list = [un]
    if claimed_at_min:
        extra += " AND claimed_at >= ?"
        params.append(claimed_at_min)
    if claimed_at_max:
        extra += " AND claimed_at <= ?"
        params.append(claimed_at_max)
    row = db.execute(
        f"SELECT COALESCE(SUM(pool_price), 0) FROM leads WHERE ({_POOL_BUYER_CLAIMED.strip()}){extra}",
        tuple(params),
    ).fetchone()
    return float(row[0] or 0)


def count_buyer_claimed_leads(
    db,
    username: str,
    *,
    claimed_at_min: str | None = None,
    claimed_at_max: str | None = None,
) -> int:
    un = _owner_key_for_ledger(db, username)
    extra = ""
    params: list = [un]
    if claimed_at_min:
        extra += " AND claimed_at >= ?"
        params.append(claimed_at_min)
    if claimed_at_max:
        extra += " AND claimed_at <= ?"
        params.append(claimed_at_max)
    r = db.execute(
        f"SELECT COUNT(*) FROM leads WHERE ({_POOL_BUYER_CLAIMED.strip()}){extra}",
        tuple(params),
    ).fetchone()
    return int(r[0] or 0)


def count_buyer_claims_on_local_date(db, username: str, ist_timestamp: str) -> int:
    """Claims whose claimed_at falls on the same local calendar day as ``ist_timestamp``."""
    un = _owner_key_for_ledger(db, username)
    r = db.execute(
        f"""
        SELECT COUNT(*) FROM leads
        WHERE ({_POOL_BUYER_CLAIMED.strip()})
          AND DATE(claimed_at) = DATE(?)
        """,
        (un, ist_timestamp),
    ).fetchone()
    return int(r[0] or 0)


def recent_buyer_claimed_leads(db, username: str, *, limit: int = 20):
    """Rows for wallet / lead-pool preview (newest first). ``limit`` capped for safety."""
    un = _owner_key_for_ledger(db, username)
    lim = max(1, min(int(limit), 500))
    return db.execute(
        f"""
        SELECT name, phone, source, pool_price, claimed_at
        FROM leads
        WHERE ({_POOL_BUYER_CLAIMED.strip()})
        ORDER BY claimed_at DESC
        LIMIT ?
        """,
        (un, lim),
    ).fetchall()
