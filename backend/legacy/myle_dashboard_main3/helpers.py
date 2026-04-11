"""
helpers.py — Shared constants and utility functions extracted from app.py.

All functions here are pure helpers: they operate on DB connections, lead dicts,
or datetime values.  None of them depend on Flask's `app` object or `current_app`.
Some import `request` from flask for IP logging but gracefully fall back.

**Time zone:** All business dates/times use ``Asia/Kolkata`` (IST, UTC+5:30, no DST).
Use ``_now_ist`` / ``_today_ist`` and ``SQLITE_NOW_IST`` in SQL — never ``datetime.now()`` or
SQLite ``datetime('now','localtime')`` for product logic.
"""

import datetime
import logging
import os
import re as _re
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

LOG = logging.getLogger(__name__)

# ── Application time zone (locked: India Standard Time, GMT+5:30, no DST) ─────
APP_TIMEZONE_NAME = 'Asia/Kolkata'
_IST_ZONE = ZoneInfo(APP_TIMEZONE_NAME)

# SQLite: built-in 'now' is UTC; shift by +5:30 to match IST wall times written by Python.
# Use in DEFAULT(...) and SQL comparisons so DB behavior does not depend on server OS TZ.
SQLITE_NOW_IST = "datetime('now', '+5 hours', '+30 minutes')"


def sqlite_row_get(row, key: str, default=None):
    """Optional field read from a DB row or dict. sqlite3.Row has no .get() before Python 3.12."""
    if row is None:
        return default
    if isinstance(row, dict):
        return row.get(key, default)
    if callable(getattr(row, "get", None)):
        return row.get(key, default)
    if hasattr(row, "keys") and key in row.keys():
        return row[key]
    return default


# ─────────────────────────────────────────────────────────────────────────────
#  Constants
# ─────────────────────────────────────────────────────────────────────────────

# Team / leader inactivity tiers (hours since last logged app activity)
INACTIVITY_WARN_HOURS = 24
INACTIVITY_BLOCK_CLAIM_HOURS = 48
INACTIVITY_LOCK_HOURS = 72

# Step 4 — minimum distinct leads “called” (non–Not Called Yet) touched today (IST)
DAILY_CALL_TARGET_DEFAULT = 15
DAILY_CALL_WARN_CAP = 15
# IST hour (0–23) when strict daily-call / claim discipline and “evening” UI kick in
DAILY_CALL_ENFORCE_START_HOUR_IST = 21
LOW_PERF_CALL_THRESHOLD = 6
LOW_PERF_STREAK_BLOCK = 2
LOW_PERF_STREAK_REMOVE = 3
GRACE_MAX_PER_30_DAYS = 2
GRACE_REPEAT_THRESHOLD = 2

# Step 5 — quality / effort (never block on conversion count alone)
QUALITY_TREND_WINDOW_DAYS = 5
QUALITY_TREND_MIN_GOOD_DAYS = 3
LOW_EFFORT_BLOCK_STREAK = 2
QUALITY_MARKET_COLD_MIN_TOUCHED = 5
QUALITY_MARKET_COLD_NO_RESPONSE_RATIO = 0.55

# Rule Engine — single source of truth for all business rules
from services.wallet_ledger import sum_pool_spent_for_buyer  # noqa: E402
from services.rule_engine import (  # noqa: E402
    CALL_STATUS_NOT_INTERESTED_BUCKET,
    CALL_STATUS_NO_RESPONSE_BUCKET,
    CALL_STATUS_INTERESTED_BUCKET,
    CLAIM_GATE_EXIT_STATUSES,
    PIPELINE_AUTO_EXPIRE_STATUSES,
    SLA_SOFT_WATCH_EXCLUDE,
    STATUS_TO_STAGE,
    STAGE_TO_DEFAULT_STATUS,
    TEAM_FORBIDDEN_STATUSES,
    TEAM_ALLOWED_STATUSES,
    STATUS_FLOW_ORDER,
    CALL_STATUS_VALUES,
    TEAM_CALL_STATUS_VALUES,
    TRACKS,
    normalize_flow_status,
    is_valid_forward_status_transition,
    validate_lead_business_rules,
)

STATUSES = ['New Lead', 'New', 'Contacted', 'Invited', 'Video Sent', 'Video Watched',
            'Paid ₹196',
            'Day 1', 'Day 2', 'Interview',
            '2cc Plan',
            'Track Selected', 'Seat Hold Confirmed',
            'Pending',
            'Level Up',
            'Fully Converted',
            'Training', 'Converted', 'Lost', 'Retarget', 'Inactive']

# Working board / Archived Leads — keep in sync with app.py ENROLLMENT_STATUSES + ENROLLED_STATUSES
WORKING_ENROLLMENT_STATUSES = (
    'New Lead', 'New', 'Contacted', 'Invited', 'Video Sent', 'Video Watched',
)
WORKING_ENROLLED_STATUSES = ('Paid ₹196',)
WORKING_SIDE_PIPELINE_STATUSES = (
    'Retarget', 'Inactive', '2cc Plan', 'Level Up', 'Training',
)
WORKING_BOARD_HOME_STATUSES = frozenset(
    list(WORKING_ENROLLMENT_STATUSES)
    + list(WORKING_ENROLLED_STATUSES)
    + [
        'Day 1', 'Day 2', 'Interview', 'Track Selected', 'Seat Hold Confirmed',
        'Fully Converted', 'Converted', 'Lost',
    ]
    + list(WORKING_SIDE_PIPELINE_STATUSES)
)

# Admin dashboard — read-only pipeline buckets (GROUP BY status; does not change STATUSES)
ADMIN_PIPELINE_BUCKET_ENROLLMENT = (
    'New Lead', 'Contacted', 'Invited', 'Video Sent', 'Video Watched',
    'Paid ₹196',
)
ADMIN_PIPELINE_BUCKET_TRAINING = (
    'Day 1', 'Day 2', 'Interview', 'Track Selected', '2cc Plan', 'Seat Hold Confirmed',
)
ADMIN_PIPELINE_BUCKET_CLOSING = (
    'Pending', 'Converted', 'Fully Converted',
)

# PIPELINE_AUTO_EXPIRE_STATUSES, STATUS_TO_STAGE, STAGE_TO_DEFAULT_STATUS,
# TEAM_FORBIDDEN_STATUSES, TEAM_ALLOWED_STATUSES — imported from services.rule_engine above


# After ₹196 → leader Day 1 handoff, team does not manage this pipeline on My Leads / edit.
TEAM_MY_LEADS_READONLY_STATUSES = frozenset({
    'Day 1', 'Day 2', 'Interview', 'Track Selected', 'Seat Hold Confirmed',
    'Fully Converted', 'Converted', 'Pending', '2cc Plan', 'Level Up', 'Training',
})


def team_my_leads_status_readonly(status: str) -> bool:
    return (status or '').strip() in TEAM_MY_LEADS_READONLY_STATUSES


def team_status_dropdown_choices(current_status: str) -> list:
    """Team dropdown = only TEAM_ALLOWED_STATUSES; leader pipeline = current only; else legacy row = current only."""
    cur = (current_status or '').strip()
    cur_n = normalize_flow_status(cur)
    if cur_n in TEAM_MY_LEADS_READONLY_STATUSES:
        return [cur]
    # Legacy aliases (e.g. "New" vs "New Lead") must not collapse to a single-option dropdown.
    if cur_n and cur_n not in TEAM_ALLOWED_STATUSES:
        return [cur]
    return list(TEAM_ALLOWED_STATUSES)


def team_status_option_selected(option: str, lead_status: str) -> bool:
    """Whether dropdown row `option` should appear selected for this lead (handles New / New Lead)."""
    return normalize_flow_status(option or '') == normalize_flow_status(lead_status or '')


# Pipeline stages where team may use assignee-centric execution routes (pre–Day 1 funnel).
PRE_DAY1_PIPELINE_STAGES = frozenset({'prospecting', 'enrolled', 'enrollment'})


def team_in_pre_day1_execution(lead_row: Any) -> bool:
    st = str(sqlite_row_get(lead_row, 'pipeline_stage') or 'prospecting').strip()
    return st in PRE_DAY1_PIPELINE_STAGES


def actor_may_use_assignee_execution_routes(
    db,
    lead_row: Any,
    *,
    role: str,
    acting_uid: Optional[int],
    acting_un: str,
) -> bool:
    """
    Admin: any lead.
    Leader: own assignee/current-owner/stale-owner or downline assignee.
    Team: own assignee/current-owner/stale-owner and pre–Day 1 pipeline only.
    """
    if role == 'admin':
        return True
    aid_raw = sqlite_row_get(lead_row, 'assigned_user_id')
    try:
        au_int = int(aid_raw) if aid_raw is not None else None
    except (TypeError, ValueError):
        au_int = None
    acting_un_n = (acting_un or '').strip().lower()
    co_n = str(sqlite_row_get(lead_row, 'current_owner') or '').strip().lower()
    sw_n = str(sqlite_row_get(lead_row, 'stale_worker') or '').strip().lower()
    owner_name_match = bool(acting_un_n) and acting_un_n in {co_n, sw_n}
    owner_uid_match = (
        acting_uid is not None
        and au_int is not None
        and int(acting_uid) == int(au_int)
    )

    if role == 'team':
        if not (owner_uid_match or owner_name_match):
            return False
        return team_in_pre_day1_execution(lead_row)

    if role == 'leader':
        if owner_uid_match or owner_name_match:
            return True
        assignee_un = (_assignee_username_for_lead(db, lead_row) or '').strip()
        if assignee_un and assignee_un == (acting_un or '').strip():
            return True
        downline = _get_network_usernames(db, acting_un or '')
        return assignee_un in downline
    return False


# STATUS_FLOW_ORDER, normalize_flow_status, is_valid_forward_status_transition
# — imported from services.rule_engine above


def leader_own_assigned_lead(row: Any, acting_user_id: Optional[int]) -> bool:
    """True when the acting user is the assigned owner (leader's *own* claim / import / quick-add lead)."""
    if acting_user_id is None:
        return False
    try:
        aid = int(sqlite_row_get(row, 'assigned_user_id') or 0)
    except (TypeError, ValueError):
        return False
    return aid == int(acting_user_id)


def payment_proof_approval_status_value(row: Any) -> str:
    s = (sqlite_row_get(row, 'payment_proof_approval_status') or '').strip().lower()
    if s in ('pending', 'rejected', 'approved'):
        return s
    return 'pending'


def _approved_196_proof_on_file(row: Any) -> bool:
    return bool((sqlite_row_get(row, 'payment_proof_path') or '').strip()) and (
        payment_proof_approval_status_value(row) == 'approved'
    )


def rupees_196_execution_blocked_for_role(
    row: Any,
    *,
    role: str,
    acting_user_id: Optional[int],
    current_status: str,
    is_transition_to_paid_196_funnel: bool,
    gate_enabled: bool = True,
) -> Tuple[bool, str]:
    """
    ₹196 execution: proof upload + leader (team) or admin (leader own lead) approval — one time.
    No Video Watched prerequisite. After proof is approved on file, never block again on this gate.
    Leader bulk/downline Paid ₹196 is not gated here (execution is on team + approver).
    Returns (True, user_message) if blocked; (False, '') if allowed.
    """
    if not gate_enabled:
        return False, ''
    if not is_transition_to_paid_196_funnel:
        return False, ''
    if role == 'admin':
        return False, ''
    cur_n = normalize_flow_status((current_status or '').strip())
    proof = (sqlite_row_get(row, 'payment_proof_path') or '').strip()
    ap = payment_proof_approval_status_value(row)

    if _approved_196_proof_on_file(row):
        return False, ''

    if role == 'team':
        if cur_n == 'Paid ₹196':
            return False, ''
        if not proof:
            return True, '₹196 payment proof screenshot upload karo, phir Paid ₹196 set karo.'
        if ap != 'approved':
            if ap == 'pending':
                return True, (
                    'Apne leader se ₹196 proof approve hone ka wait karo — tab hi Paid / Payment Done allowed.'
                )
            return True, (
                '₹196 proof reject ho chuka hai — naya screenshot upload karo aur leader se dubara approve karwao.'
            )
        return False, ''

    if role == 'leader' and leader_own_assigned_lead(row, acting_user_id):
        if cur_n == 'Paid ₹196':
            return False, ''
        if not proof:
            return True, (
                '₹196 payment proof screenshot upload karo (leader — apni claimed / import / quick-add lead).'
            )
        if ap != 'approved':
            if ap == 'pending':
                return True, (
                    'Admin se ₹196 proof approve hone ka wait karo — tab hi Paid / Day 1 / Payment Done allowed.'
                )
            return True, (
                '₹196 proof reject ho chuka hai — naya screenshot upload karo aur dubara admin se approve karwao.'
            )
        return False, ''

    return False, ''

# CALL_STATUS_VALUES, TEAM_CALL_STATUS_VALUES, TRACKS
# — imported from services.rule_engine above

# Call tag = after-call reason only (7 user options + blank). Do not duplicate Lead Status.
CALL_RESULT_TAGS = [
    '',
    'No Answer',
    'Switched Off',
    'Busy',
    'Call Later',
    'Not Interested',
    'Follow-up Needed',
    'Hot Lead',
]

# Legacy / system-set values still valid in DB and on POST (migration-friendly)
CALL_RESULT_LEGACY = frozenset({
    'Missed Follow-up',
    'Call Not Picked', 'Phone Switched Off', 'Not Reachable',
    'Follow Up Later', 'Callback Requested',
    'Wrong Number', 'Interested', 'Connected', 'Spoke to lead',
    'Already Forever Living Distributor', 'Already in Another Network', 'Underage', 'Language Barrier',
})

def call_result_allowed(tag: str) -> bool:
    return (tag in CALL_RESULT_TAGS) or (tag in CALL_RESULT_LEGACY)

# Retarget list + dashboard counts: new tags + legacy rows still in DB
RETARGET_TAGS = (
    'No Answer', 'Switched Off', 'Busy', 'Call Later', 'Follow-up Needed',
    'Call Not Picked', 'Phone Switched Off', 'Not Reachable',
    'Follow Up Later', 'Callback Requested',
)

FOLLOWUP_TAGS = (
    'Call Later', 'Follow-up Needed', 'No Answer', 'Switched Off', 'Busy', 'Hot Lead',
    'Follow Up Later', 'Callback Requested', 'Call Not Picked', 'Phone Switched Off', 'Not Reachable',
)

SOURCES = ['WhatsApp', 'Facebook', 'Instagram', 'LinkedIn',
           'Walk-in', 'Referral', 'YouTube', 'Cold Call', 'Meta', 'Other']

BADGE_DEFS = {
    'first_sale':   {'label': 'First Sale',      'icon': 'bi-trophy-fill',       'color': '#f59e0b',
                     'desc': 'Convert your first lead'},
    'ten_leads':    {'label': 'Getting Started',  'icon': 'bi-person-plus-fill',  'color': '#6366f1',
                     'desc': 'Add 10 leads'},
    'century':      {'label': 'Century',          'icon': 'bi-123',               'color': '#0891b2',
                     'desc': 'Add 100 leads'},
    'payment_10':   {'label': '₹1960 Club',       'icon': 'bi-cash-stack',        'color': '#059669',
                     'desc': '10 payments collected'},
    'seat_hold_5':  {'label': 'Seat Holder',      'icon': 'bi-shield-fill-check', 'color': '#7c3aed',
                     'desc': '5 seat holds confirmed'},
    'fully_conv_1': {'label': 'Track Master',     'icon': 'bi-star-fill',         'color': '#d97706',
                     'desc': 'First fully converted lead'},
    'streak_7':     {'label': '7-Day Streak',     'icon': 'bi-fire',              'color': '#ef4444',
                     'desc': 'Submit daily report 7 days in a row'},
}

PAYMENT_AMOUNT = 196.0


def _lead_row_to_dict(lead) -> dict:
    if lead is None or not hasattr(lead, "keys"):
        return {}
    return {k: lead[k] for k in lead.keys()}


def normalize_lead_payment_row(lead) -> tuple[int, float]:
    """
    Core rules (single source of truth for stored columns):
    - payment_done = 0 → payment_amount = 0
    - payment_done = 1 → payment_amount > 0 via derivation priority
    """
    keys = lead.keys() if lead is not None and hasattr(lead, "keys") else []

    def _i(col: str) -> int:
        if col not in keys:
            return 0
        try:
            return int(lead[col] or 0)
        except (TypeError, ValueError):
            return 0

    def _f(col: str) -> float:
        if col not in keys:
            return 0.0
        try:
            return float(lead[col] or 0)
        except (TypeError, ValueError):
            return 0.0

    pd = _i("payment_done")
    pa = _f("payment_amount")
    if pd == 0:
        return 0, 0.0
    if pa > 0:
        return 1, pa
    st = (lead["status"] or "").strip() if "status" in keys else ""
    _lid = None
    try:
        _lid = int(lead["id"]) if "id" in keys and lead["id"] is not None else None
    except (TypeError, ValueError):
        pass
    _amt = payment_amount_when_marking_paid(lead, st)
    LOG.info(
        "normalize_lead_payment_row: backfilled payment_amount (lead_id=%s status=%s -> %s)",
        _lid,
        st,
        _amt,
    )
    return 1, _amt


def payment_amount_when_marking_paid(lead, status_hint: Optional[str] = None) -> float:
    """
    When setting payment_done=1, store a positive payment_amount for revenue dashboards.
    Prefer track/seat totals when status is closing; else existing payment_amount; else ₹196.
    """
    st = status_hint
    if st is None and lead is not None:
        try:
            st = (lead["status"] or "") if hasattr(lead, "__getitem__") else ""
        except (KeyError, TypeError):
            st = ""
    st = (st or "").strip()
    keys = lead.keys() if lead is not None and hasattr(lead, "keys") else []

    def _f(col: str, default: float = 0.0) -> float:
        if col not in keys:
            return default
        try:
            return float(lead[col] or 0)
        except (TypeError, ValueError):
            return default

    tp, sh, ex = _f("track_price"), _f("seat_hold_amount"), _f("payment_amount")
    if st == "Seat Hold Confirmed" and sh > 0:
        return sh
    if st == "Fully Converted" and tp > 0:
        return tp
    if ex > 0:
        return ex
    return float(PAYMENT_AMOUNT)


def payment_fields_after_status_change(lead, new_status: str) -> tuple[int, float]:
    """
    Status-based payment fields before finalize. Always run through normalize_lead_payment_row.
    """
    keys = lead.keys() if hasattr(lead, "keys") else []

    def _i(col: str) -> int:
        if col not in keys:
            return 0
        try:
            return int(lead[col] or 0)
        except (TypeError, ValueError):
            return 0

    def _f(col: str) -> float:
        if col not in keys:
            return 0.0
        try:
            return float(lead[col] or 0)
        except (TypeError, ValueError):
            return 0.0

    pd, pa = _i("payment_done"), _f("payment_amount")

    if new_status == "Paid ₹196":
        pd = 1
        if pa <= 0:
            pa = float(PAYMENT_AMOUNT)
    elif new_status == "Day 1":
        pd = 1
        if pa <= 0:
            pa = payment_amount_when_marking_paid(lead, new_status)
    elif new_status in ("Seat Hold Confirmed", "Fully Converted"):
        pd = 1
        pa = payment_amount_when_marking_paid(lead, new_status)
    elif pd == 1 and pa <= 0:
        pd = 1
        pa = payment_amount_when_marking_paid(lead, new_status)

    tmp = _lead_row_to_dict(lead)
    tmp["status"] = new_status
    tmp["payment_done"] = pd
    tmp["payment_amount"] = pa
    return normalize_lead_payment_row(tmp)


_COL_SAFE = _re.compile(r"^[a-z_][a-z0-9_]*$")


def assert_lead_owner_invariant(db, *, lead_id: Optional[int] = None, context: str = "") -> None:
    """
    Hard invariant:
      if in_pool = 0 then assigned_user_id must be present and > 0.
    Raises RuntimeError to force rollback / fail-fast on invalid state.
    """
    if lead_id is None:
        bad = db.execute(
            """
            SELECT id, in_pool, assigned_user_id
            FROM leads
            WHERE in_pool=0 AND (assigned_user_id IS NULL OR assigned_user_id=0)
            ORDER BY id ASC
            LIMIT 1
            """
        ).fetchone()
    else:
        bad = db.execute(
            """
            SELECT id, in_pool, assigned_user_id
            FROM leads
            WHERE id=? AND in_pool=0 AND (assigned_user_id IS NULL OR assigned_user_id=0)
            LIMIT 1
            """,
            (lead_id,),
        ).fetchone()
    if bad:
        msg = (
            f"Lead owner invariant violated (ctx={context or 'n/a'}): "
            f"lead_id={bad['id']} in_pool={bad['in_pool']} assigned_user_id={bad['assigned_user_id']}"
        )
        LOG.critical(msg)
        raise RuntimeError(msg)


# validate_lead_business_rules — imported from services.rule_engine above


def apply_leads_update(
    db,
    set_fields: Dict[str, Any],
    *,
    where_sql: str,
    where_params: tuple,
    log_context: str = "",
) -> None:
    """
    Leads table UPDATE choke point: always sets updated_at = IST.
    Do not pass id in set_fields.
    """
    ts = _now_ist().strftime("%Y-%m-%d %H:%M:%S")
    sf = dict(set_fields)
    sf["updated_at"] = ts
    for k in sf:
        if not _COL_SAFE.match(k):
            raise ValueError(f"Invalid column name: {k}")
    cols = ", ".join(f"{k}=?" for k in sf.keys())
    vals = list(sf.values()) + list(where_params)
    db.execute(f"UPDATE leads SET {cols} WHERE {where_sql}", vals)
    # Fail fast: never allow off-pool lead rows without owner.
    assert_lead_owner_invariant(db, context=f"apply_leads_update:{log_context or where_sql}")


def payment_columns_mark_paid(lead) -> tuple[int, float]:
    """Bulk/single mark-paid: derive via payment_amount_when_marking_paid + normalize."""
    tmp = _lead_row_to_dict(lead)
    tmp["payment_done"] = 1
    st = (tmp.get("status") or "").strip() if tmp else ""
    tmp["payment_amount"] = payment_amount_when_marking_paid(lead, st)
    return normalize_lead_payment_row(tmp)


def touch_lead_updated_at(db, lead_id: int, *, log_context: str = "") -> None:
    """
    Bump leads.updated_at to now (IST). Admin \"Today Calls\" / enrollments use
    sql_ts_calendar_day(updated_at); any call_status path that skips this will
    look like \"no call today\" in the dashboard.
    """
    ts = _now_ist().strftime("%Y-%m-%d %H:%M:%S")
    db.execute(
        """UPDATE leads SET updated_at=?, stale_worker='', stale_worker_since='', stale_worker_by=''
           WHERE id=? AND in_pool=0 AND deleted_at=''""",
        (ts, lead_id),
    )
    if log_context:
        LOG.debug("touch_lead_updated_at id=%s ctx=%s", lead_id, log_context)


def repair_lead_payment_invariants(db) -> dict:
    """Fix payment_done=1 with invalid amount (cron / manual)."""
    now_s = _now_ist().strftime("%Y-%m-%d %H:%M:%S")
    rows = db.execute(
        """
        SELECT * FROM leads
        WHERE in_pool=0 AND deleted_at=''
          AND payment_done=1
          AND (payment_amount IS NULL OR payment_amount <= 0)
        """
    ).fetchall()
    n = 0
    for r in rows:
        pd, pa = normalize_lead_payment_row(r)
        db.execute(
            "UPDATE leads SET payment_done=?, payment_amount=?, updated_at=? WHERE id=?",
            (pd, pa, now_s, r["id"]),
        )
        n += 1
    if n:
        LOG.info("repair_lead_payment_invariants: fixed %s lead(s)", n)
    return {"payment_rows_repaired": n}


BADGE_META = {
    'hot_streak':    ('\U0001f525', 'Hot Streak',    '7+ days active in a row'),
    'speed_closer':  ('\u26a1', 'Speed Closer',  'Enrollment \u2192 Day1 in \u22643 days'),
    'money_maker':   ('\U0001f4b0', 'Money Maker',   '5+ payments collected'),
    'first_convert': ('\U0001f3c6', 'Converter',     'First full conversion'),
    'rising_star':   ('\u2b50', 'Rising Star',   'Top scorer this week'),
    'centurion':     ('\U0001f4af', 'Centurion',     '10,000+ total points'),
    'batch_master':  ('\U0001f4da', 'Batch Master',  '100 batches marked total'),
}

# STAGE_TO_DEFAULT_STATUS — imported from services.rule_engine above

# Day 2 business evaluation test (leads table: test_* columns)
DAY2_BUSINESS_TEST_PASS_MARK = 18
DAY2_BUSINESS_TEST_MAX_ATTEMPTS = 2
DAY2_BUSINESS_TEST_TOTAL_Q = 30


def _lead_row_value(lead, key, default=None):
    """Safe read from sqlite Row or dict (column may be missing on old rows)."""
    if lead is None:
        return default
    try:
        keys = lead.keys()
        if key not in keys:
            return default
        v = lead[key]
        return default if v is None else v
    except (TypeError, KeyError, IndexError):
        return default


def lead_day2_business_test_passed(lead):
    return (_lead_row_value(lead, 'test_status') or 'pending').strip().lower() == 'passed'


def lead_day2_business_test_exhausted(lead):
    """True if failed twice — no more attempts."""
    st = (_lead_row_value(lead, 'test_status') or 'pending').strip().lower()
    if st == 'passed':
        return False
    if st == 'failed':
        return True
    try:
        att = int(_lead_row_value(lead, 'test_attempts') or 0)
    except (TypeError, ValueError):
        att = 0
    return att >= DAY2_BUSINESS_TEST_MAX_ATTEMPTS


def lead_day2_interview_cleared_for_certificate(lead):
    """True if interview marked done/cleared — reporting/analytics; not used for Day 2 certificate gate."""
    iv = (_lead_row_value(lead, 'interview_status') or '').strip().lower()
    if iv == 'cleared':
        return True
    try:
        return int(_lead_row_value(lead, 'interview_done') or 0) == 1
    except (TypeError, ValueError):
        return False


def lead_day2_certificate_eligible(lead):
    """Day 2 business evaluation certificate: available as soon as test status is passed (quality filter on Day 2)."""
    return lead_day2_business_test_passed(lead)


# ─────────────────────────────────────────────────────────────────────────────
#  Time helpers
# ─────────────────────────────────────────────────────────────────────────────

def _now_ist():
    """Current Asia/Kolkata wall time as naive datetime (matches SQLITE_NOW_IST semantics)."""
    return datetime.datetime.now(_IST_ZONE).replace(tzinfo=None)


def _today_ist():
    """Current calendar date in Asia/Kolkata."""
    return datetime.datetime.now(_IST_ZONE).date()


def format_day2_certificate_display_date(iso_date: str) -> str:
    """Format certificate date for display, e.g. 2026-03-29 -> '29 March 2026'."""
    s = (iso_date or "").strip()[:10]
    if len(s) >= 10:
        try:
            return datetime.datetime.strptime(s[:10], "%Y-%m-%d").strftime("%d %B %Y")
        except ValueError:
            pass
    return _now_ist().strftime("%d %B %Y")


def phones_match_for_lead_verification(entered: str, lead_phone: str) -> bool:
    """Compare user-entered phone to lead.phone (digits, last-10 for IN numbers)."""
    import re

    def _dig(x: str) -> str:
        return re.sub(r'\D', '', (x or '').strip())

    e, lph = _dig(entered), _dig(lead_phone)
    if not e or not lph:
        return False
    if e == lph:
        return True
    if len(e) >= 10 and len(lph) >= 10 and e[-10:] == lph[-10:]:
        return True
    if len(e) >= 7 and (lph.endswith(e) or e.endswith(lph)):
        return True
    return False


def day2_test_token_expired(expiry_str: str) -> bool:
    """True if token_expiry is missing or before now (IST naive datetimes)."""
    raw = (expiry_str or '').strip()
    if len(raw) < 19:
        return True
    try:
        exp = datetime.datetime.strptime(raw[:19], '%Y-%m-%d %H:%M:%S')
    except ValueError:
        return True
    return _now_ist() > exp


# ─────────────────────────────────────────────────────────────────────────────
#  DB helpers
# ─────────────────────────────────────────────────────────────────────────────

def _log_activity(db, username, event_type, details=''):
    """Log a user activity event (login, lead_update, etc.)."""
    try:
        from flask import request
        ip = request.remote_addr or ''
    except Exception:
        ip = ''
    try:
        now_s = _now_ist().strftime('%Y-%m-%d %H:%M:%S')
        db.execute(
            "INSERT INTO activity_log (username, event_type, details, ip_address, created_at) VALUES (?, ?, ?, ?, ?)",
            (username, event_type, details, ip, now_s)
        )
        if username and username != 'system':
            try:
                db.execute(
                    "UPDATE users SET last_activity_at=? WHERE username=? AND role IN ('team','leader')",
                    (now_s, username),
                )
            except Exception:
                pass
    except Exception:
        pass


def user_inactivity_hours(db, username: str) -> float:
    """
    Hours since last *work* activity for discipline (team/leader).
    When work-style rows exist in activity_log, login/logout do not move this clock.
    If there are no work rows yet, we use last login time (not account created_at) as the
    reference — otherwise a DB restore missing activity_log or old accounts look 72h+ idle
    since signup and everyone hits the 24/48/72h loop at once.
    users.last_activity_at (updated on real work and on admin Reset activity clock) is
    included so the decision engine and member detail match admin resets.
    Returns 0.0 until the user has logged in at least once (no maiden-login penalty).
    """
    row = db.execute(
        """
        SELECT u.created_at,
               TRIM(COALESCE(u.last_activity_at, '')) AS user_last_act,
               (SELECT COUNT(*) FROM activity_log WHERE username=u.username AND event_type='login') AS login_cnt,
               (SELECT MAX(created_at) FROM activity_log
                WHERE username=u.username
                  AND IFNULL(event_type,'') NOT IN ('login','logout')) AS work_last,
               (SELECT MAX(created_at) FROM activity_log
                WHERE username=u.username AND event_type='login') AS login_last
        FROM users u WHERE u.username=?
        """,
        (username,),
    ).fetchone()
    if not row:
        return 0.0
    if (row['login_cnt'] or 0) == 0:
        return 0.0
    work_last = (row['work_last'] or '').strip()
    login_last = (row['login_last'] or '').strip()
    created = (row['created_at'] or '').strip()
    user_last_act = (row['user_last_act'] or '').strip()

    def _parse_ts(ts_str: str):
        if not ts_str:
            return None
        if len(ts_str) >= 19:
            try:
                return datetime.datetime.strptime(ts_str[:19], '%Y-%m-%d %H:%M:%S')
            except ValueError:
                return None
        if len(ts_str) >= 10:
            try:
                return datetime.datetime.strptime(ts_str[:10], '%Y-%m-%d')
            except ValueError:
                return None
        return None

    candidates = []
    for s in (work_last, login_last, created, user_last_act):
        dt = _parse_ts(s)
        if dt is not None:
            candidates.append(dt)
    if not candidates:
        return 0.0
    ts = max(candidates)
    now = _now_ist().replace(tzinfo=None)
    return max(0.0, (now - ts).total_seconds() / 3600.0)


def process_inactivity_escalation(db, username: str) -> None:
    """
    Step 1.1 — record first IST calendar day user is at 72h+ work inactivity; clear when <72h.
    """
    today_d = _today_ist().isoformat()
    row = db.execute(
        "SELECT inactivity_72h_start_date FROM users WHERE username=?",
        (username,),
    ).fetchone()
    start = _user_row_safe(row, 'inactivity_72h_start_date', '').strip()[:10]
    h = user_inactivity_hours(db, username)
    if h < float(INACTIVITY_LOCK_HOURS):
        if start:
            db.execute(
                "UPDATE users SET inactivity_72h_start_date='' WHERE username=?",
                (username,),
            )
        return
    if not start or len(start) < 10:
        db.execute(
            "UPDATE users SET inactivity_72h_start_date=? WHERE username=?",
            (today_d, username),
        )


def inactivity_escalation_days(db, username: str) -> int:
    """IST calendar days since inactivity_72h_start_date while still 72h+ inactive; else 0."""
    process_inactivity_escalation(db, username)
    inh = float(user_inactivity_hours(db, username))
    if inh < float(INACTIVITY_LOCK_HOURS):
        return 0
    row = db.execute(
        "SELECT inactivity_72h_start_date FROM users WHERE username=?",
        (username,),
    ).fetchone()
    s = _user_row_safe(row, 'inactivity_72h_start_date', '').strip()[:10]
    if len(s) < 10:
        return 0
    try:
        d0 = datetime.date.fromisoformat(s)
    except ValueError:
        return 0
    return max(0, (_today_ist() - d0).days)


def followup_discipline_process_overdue(db, username: str) -> None:
    """
    Step 3 — missed follow-up: mark, optional penalty, bump next due after 1st miss;
    auto-Retarget after 2nd miss on a later overdue cycle.

    Team members are skipped: follow-up discipline is enforced for leader/admin assignees only.
    """
    role_row = db.execute("SELECT role FROM users WHERE username=?", (username,)).fetchone()
    if role_row and (role_row["role"] or "").strip() == "team":
        return
    _uid = user_id_for_username(db, username)
    if _uid is None:
        return
    today_d = _today_ist().isoformat()
    now_str = _now_ist().strftime('%Y-%m-%d %H:%M:%S')
    ex_ph = ','.join('?' * len(CLAIM_GATE_EXIT_STATUSES))
    rows = db.execute(
        f"""
        SELECT id, follow_up_date, follow_up_miss_logged_for, follow_up_missed_count
        FROM leads
        WHERE assigned_user_id=? AND in_pool=0 AND deleted_at=''
          AND follow_up_date IS NOT NULL AND TRIM(COALESCE(follow_up_date,''))!=''
          AND date(substr(trim(follow_up_date), 1, 10)) < date(?)
          AND status NOT IN ({ex_ph})
        """,
        (_uid, today_d, *CLAIM_GATE_EXIT_STATUSES),
    ).fetchall()
    for row in rows:
        lid = row['id']
        assignee = username
        fu = (row['follow_up_date'] or '').strip()
        fu_key = fu[:10] if len(fu) >= 10 else fu
        logged = (row['follow_up_miss_logged_for'] or '').strip()[:10]
        # One processing pass per overdue due-date (avoid duplicate penalties same day)
        if fu_key and logged == fu_key:
            continue
        missc = int(row['follow_up_missed_count'] or 0) + 1
        if missc >= 2:
            db.execute(
                """
                UPDATE leads SET status='Retarget', pipeline_stage='prospecting',
                    follow_up_date='', follow_up_time='', follow_up_missed_count=0,
                    no_response_attempt_count=0, follow_up_miss_logged_for='',
                    call_result='Follow-up Needed', updated_at=?
                WHERE id=?
                """,
                (now_str, lid),
            )
        else:
            nxt = (_today_ist() + datetime.timedelta(days=1)).strftime('%Y-%m-%d')
            db.execute(
                """
                UPDATE leads SET follow_up_missed_count=?, follow_up_miss_logged_for=?,
                    call_result='Follow-up Needed', updated_at=?,
                    follow_up_date=?, follow_up_time='18:00'
                WHERE id=?
                """,
                (missc, fu_key, now_str, nxt, lid),
            )
        try:
            from services.scoring_service import apply_penalty

            apply_penalty(assignee, 'FOLLOWUP_MISSED', f'Lead #{lid} follow-up overdue', db=db)
        except Exception:
            pass


def apply_call_outcome_discipline(db, lead, call_status: str, triggered_by: str = 'system') -> None:
    """
    Step 3 — after mandatory call classification: set follow-ups, exits, no-response strikes.
    Does not commit. Caller runs auto status / points after.
    """
    lead_id = lead['id']
    lead_keys = lead.keys() if hasattr(lead, 'keys') else []

    def _col(name, default=0):
        if name not in lead_keys:
            return default
        v = lead[name]
        if v is None:
            return default
        return v

    now = _now_ist().replace(tzinfo=None)
    now_str = now.strftime('%Y-%m-%d %H:%M:%S')
    nores = int(_col('no_response_attempt_count', 0) or 0)

    if call_status in CALL_STATUS_NOT_INTERESTED_BUCKET:
        db.execute(
            """
            UPDATE leads SET call_status=?, updated_at=?, status='Lost', pipeline_stage='lost',
                follow_up_date='', follow_up_time='', follow_up_missed_count=0,
                no_response_attempt_count=0, follow_up_miss_logged_for=''
            WHERE id=?
            """,
            (call_status, now_str, lead_id),
        )
        _log_activity(db, triggered_by, 'discipline_status_change',
                      f"Lead #{lead_id} → Lost (not interested, call_status: {call_status})")
        return

    if call_status == 'Wrong Number':
        db.execute(
            """
            UPDATE leads SET call_status=?, updated_at=?, status='Lost', pipeline_stage='lost',
                follow_up_date='', follow_up_time='', follow_up_missed_count=0,
                no_response_attempt_count=0, follow_up_miss_logged_for=''
            WHERE id=?
            """,
            (call_status, now_str, lead_id),
        )
        _log_activity(db, triggered_by, 'discipline_status_change',
                      f"Lead #{lead_id} → Lost (wrong number)")
        return

    if call_status in CALL_STATUS_NO_RESPONSE_BUCKET:
        nores += 1
        if nores >= 3:
            db.execute(
                """
                UPDATE leads SET call_status=?, updated_at=?, status='Retarget', pipeline_stage='prospecting',
                    follow_up_date='', follow_up_time='', no_response_attempt_count=0,
                    follow_up_missed_count=0, follow_up_miss_logged_for=''
                WHERE id=?
                """,
                (call_status, now_str, lead_id),
            )
            _log_activity(db, triggered_by, 'discipline_status_change',
                          f"Lead #{lead_id} → Retarget (3+ no-response attempts)")
        else:
            nxt = (now + datetime.timedelta(days=1)).strftime('%Y-%m-%d')
            db.execute(
                """
                UPDATE leads SET call_status=?, updated_at=?, no_response_attempt_count=?,
                    follow_up_date=?, follow_up_time='10:00',
                    follow_up_missed_count=0, follow_up_miss_logged_for=''
                WHERE id=?
                """,
                (call_status, now_str, nores, nxt, lead_id),
            )
        return

    if call_status in CALL_STATUS_INTERESTED_BUCKET:
        due = now + datetime.timedelta(hours=24)
        db.execute(
            """
            UPDATE leads SET call_status=?, updated_at=?, follow_up_date=?, follow_up_time=?,
                follow_up_missed_count=0, follow_up_miss_logged_for='', no_response_attempt_count=0
            WHERE id=?
            """,
            (call_status, now_str, due.strftime('%Y-%m-%d'), due.strftime('%H:%M'), lead_id),
        )
        return

    if call_status in ('Already forever', 'Retarget'):
        db.execute(
            "UPDATE leads SET call_status=?, updated_at=? WHERE id=?",
            (call_status, now_str, lead_id),
        )
        return

    db.execute(
        "UPDATE leads SET call_status=?, updated_at=? WHERE id=?",
        (call_status, now_str, lead_id),
    )


def daily_call_target(db) -> int:
    """Pool-claim gate: min leads with a real call_status logged today. 0 = disabled."""
    raw = (_get_setting(db, 'daily_call_target', '') or '').strip()
    if not raw:
        return DAILY_CALL_TARGET_DEFAULT
    try:
        return max(0, min(int(raw), 500))
    except ValueError:
        return DAILY_CALL_TARGET_DEFAULT


def _claim_discipline_auto_start_enabled() -> bool:
    """
    When True and ``claim_discipline_start_date`` is unset, the first gate check
    persists today's IST date once (no internet — server clock / Asia/Kolkata logic).

    Env ``CLAIM_DISCIPLINE_AUTO_START``: ``0``/``false``/``off`` = disabled;
    ``1``/``true``/``on`` = enabled; unset = enabled (production default).
    Tests set ``CLAIM_DISCIPLINE_AUTO_START=0`` before importing the app.
    """
    v = (os.environ.get('CLAIM_DISCIPLINE_AUTO_START') or '').strip().lower()
    if v in ('0', 'false', 'no', 'off'):
        return False
    if v in ('1', 'true', 'yes', 'on'):
        return True
    return True


def maybe_auto_seed_claim_discipline_start(db) -> None:
    """
    If auto-start is on and no valid ``claim_discipline_start_date`` exists, set it
    to today's IST calendar date. Caller should ``commit`` when not inside a doomed
    transaction (claim POST runs this before ``BEGIN IMMEDIATE``).
    """
    if not _claim_discipline_auto_start_enabled():
        return
    raw = (_get_setting(db, 'claim_discipline_start_date', '') or '').strip()
    if len(raw) >= 10:
        d = raw[:10]
        if d[4] == '-' and d[7] == '-':
            try:
                datetime.date.fromisoformat(d)
                return
            except ValueError:
                pass
    _set_setting(db, 'claim_discipline_start_date', _today_ist().isoformat())


def claim_discipline_start_date_iso(db) -> Optional[str]:
    """
    If set in app_settings (YYYY-MM-DD), pool-claim hard gates only consider leads
    claimed (or, if claimed_at empty, created) on/after this IST calendar date.
    Empty/invalid with auto-start off = legacy behaviour (all assignments count).

    With auto-start on, ``maybe_auto_seed_claim_discipline_start`` runs first so the
    date is written once (first pool / claim gate hit), not re-fetched from the internet.
    """
    raw = (_get_setting(db, 'claim_discipline_start_date', '') or '').strip()
    if len(raw) < 10:
        return None
    d = raw[:10]
    if d[4] != '-' or d[7] != '-':
        return None
    try:
        datetime.date.fromisoformat(d)
    except ValueError:
        return None
    return d


def sql_ts_calendar_day(column: str = "updated_at") -> str:
    """
    SQLite expression: IST calendar day from stored wall-clock datetime
    'YYYY-MM-DD HH:MM:SS' (written via _now_ist in Python).

    Compare to ? using ``= date(?)`` with ?_ist = _today_ist().isoformat().
    Use this everywhere leads.updated_at (or similar) is filtered by India date
    so admin / gates / dashboard counts stay aligned.
    """
    col = (column or "updated_at").strip()
    return f"date(substr(trim(COALESCE({col},'')), 1, 10))"


def get_today_metrics(db, *, day_iso: str, user_ids=None, usernames=None,
                      approved_only: bool = False,
                      proof_approved_only: bool = True) -> dict:
    """
    SSOT for daily metrics. Reuse this in team/leader/admin dashboards.

    Definitions:
    - claimed: claimed_at non-empty + claimed_at IST date == day_iso
    - enrolled: enrolled_at IST date == day_iso + ₹196 proof exists
                (+ proof approval required only when proof_approved_only=True)
    - calls: distinct lead ids with valid call_status + updated_at IST date == day_iso
             + lead was actually called after claiming (updated_at > claimed_at for pool leads)

    Pass `usernames` alongside `user_ids` to also count leads handed off to a leader
    (where assigned_user_id changed) but originally claimed by these users (current_owner).
    """
    _d_claim = sql_ts_calendar_day("l.claimed_at")
    _d_upd = sql_ts_calendar_day("l.updated_at")
    where = ["l.in_pool=0", "l.deleted_at=''"]
    params = []

    if user_ids is not None or usernames is not None:
        uid_conds: list[str] = []
        if user_ids is not None:
            ids = [int(x) for x in user_ids if x is not None]
            if ids:
                ph = ",".join("?" * len(ids))
                uid_conds.append(f"l.assigned_user_id IN ({ph})")
                params.extend(ids)
        if usernames is not None:
            uns = [str(u) for u in usernames if u]
            if uns:
                uph = ",".join("?" * len(uns))
                uid_conds.append(f"l.current_owner IN ({uph})")
                params.extend(uns)
        if not uid_conds:
            return {"claimed": 0, "enrolled": 0, "calls": 0}
        where.append(f"({' OR '.join(uid_conds)})")

    if approved_only:
        where.append(
            "EXISTS (SELECT 1 FROM users u WHERE u.id=l.assigned_user_id "
            "AND u.role IN ('team','leader') AND u.status='approved')"
        )

    base = " AND ".join(where)
    claimed = db.execute(
        f"""
        SELECT COUNT(*) FROM leads l
        WHERE {base}
          AND l.claimed_at IS NOT NULL
          AND TRIM(COALESCE(l.claimed_at,''))!=''
          AND {_d_claim} = date(?)
        """,
        [*params, day_iso],
    ).fetchone()[0] or 0
    _d_enroll = sql_ts_calendar_day("l.enrolled_at")
    _enroll_proof_cond = (
        "AND LOWER(COALESCE(l.payment_proof_approval_status,'')) = 'approved'"
        if proof_approved_only else ""
    )
    enrolled = db.execute(
        f"""
        SELECT COUNT(*) FROM leads l
        WHERE {base}
          AND TRIM(COALESCE(l.enrolled_at,'')) != ''
          AND {_d_enroll} = date(?)
          AND TRIM(COALESCE(l.payment_proof_path,'')) != ''
          {_enroll_proof_cond}
        """,
        [*params, day_iso],
    ).fetchone()[0] or 0
    _d_claim_l = sql_ts_calendar_day("l.claimed_at")
    _d_create_l = sql_ts_calendar_day("l.created_at")
    calls = db.execute(
        f"""
        SELECT COUNT(DISTINCT l.id) FROM leads l
        WHERE {base}
          AND {_d_upd} = date(?)
          AND {LEAD_SQL_CALL_LOGGED.replace('call_status', 'l.call_status')}
          AND (
            (
              {_d_claim_l} = date(?)
              AND l.updated_at > l.claimed_at
            )
            OR (COALESCE(TRIM(l.claimed_at),'') = '' AND {_d_create_l} = date(?))
          )
        """,
        [*params, day_iso, day_iso, day_iso],
    ).fetchone()[0] or 0
    return {"claimed": int(claimed), "enrolled": int(enrolled), "calls": int(calls)}


# Lead row counts as “call logged” for metrics (matches count_distinct_valid_calls_on_date)
LEAD_SQL_CALL_LOGGED = (
    "call_status IS NOT NULL AND TRIM(COALESCE(call_status,'')) != '' "
    "AND call_status != 'Not Called Yet'"
)


def _FRESH_LEAD_SQL(day_iso_param_idx: int = 2) -> str:
    """SQL fragment: lead is 'fresh' = claimed today OR created today (no pool claim)."""
    _d_claim = sql_ts_calendar_day("claimed_at")
    _d_create = sql_ts_calendar_day("created_at")
    p = f"?{day_iso_param_idx}" if day_iso_param_idx > 1 else "?"
    return (
        f"( ({_d_claim} = date({p}))"
        f"  OR (COALESCE(TRIM(claimed_at),'') = '' AND {_d_create} = date({p})) )"
    )


def count_distinct_valid_calls_on_date(db, username: str, day_iso: str) -> int:
    """Valid call = distinct fresh lead (claimed today / created today), call_status set.
    Includes leads originally claimed by this user but later handed off to a leader
    (matched via current_owner which is immutable after claim)."""
    _uid = user_id_for_username(db, username)
    if _uid is None:
        return 0
    _d = sql_ts_calendar_day("updated_at")
    _d_claim = sql_ts_calendar_day("claimed_at")
    _d_create = sql_ts_calendar_day("created_at")
    row = db.execute(
        f"""
        SELECT COUNT(DISTINCT id) AS c FROM leads
        WHERE (assigned_user_id=? OR current_owner=?) AND in_pool=0 AND deleted_at=''
          AND updated_at IS NOT NULL AND TRIM(COALESCE(updated_at,''))!=''
          AND {_d} = date(?)
          AND {LEAD_SQL_CALL_LOGGED}
          AND (
            (
              {_d_claim} = date(?)
              AND updated_at > claimed_at
            )
            OR (COALESCE(TRIM(claimed_at),'') = '' AND {_d_create} = date(?))
          )
        """,
        (_uid, username, day_iso, day_iso, day_iso),
    ).fetchone()
    return int(row['c'] or 0) if row else 0


def count_call_logged_leads_today(db, username: str, today_d: str) -> int:
    """Distinct leads with a valid call logged on `today_d` (IST calendar date)."""
    return count_distinct_valid_calls_on_date(db, username, today_d)


def count_assigned_leads_total(db, username: str) -> int:
    """All non-pool assignments (any status) — deadlock safety for Step 4."""
    _uid = user_id_for_username(db, username)
    if _uid is None:
        return 0
    row = db.execute(
        """
        SELECT COUNT(*) AS c FROM leads
        WHERE assigned_user_id=? AND in_pool=0 AND deleted_at=''
        """,
        (_uid,),
    ).fetchone()
    return int(row['c'] or 0) if row else 0


def count_assigned_leads_for_claim_discipline(db, username: str) -> int:
    """
    Rows that count toward Step 4 (daily call target) and related claim pressure.
    When claim_discipline_start_date is set, ignores older pool/manual assignments.
    """
    start = claim_discipline_start_date_iso(db)
    if not start:
        return count_assigned_leads_total(db, username)
    _uid = user_id_for_username(db, username)
    if _uid is None:
        return 0
    row = db.execute(
        """
        SELECT COUNT(*) AS c FROM leads
        WHERE assigned_user_id=? AND in_pool=0 AND deleted_at=''
          AND (
            (claimed_at IS NOT NULL AND TRIM(COALESCE(claimed_at,''))!=''
             AND date(substr(trim(claimed_at),1,10)) >= date(?))
            OR
            ((claimed_at IS NULL OR TRIM(COALESCE(claimed_at,''))='')
             AND date(substr(trim(created_at),1,10)) >= date(?))
          )
        """,
        (_uid, start, start),
    ).fetchone()
    return int(row['c'] or 0) if row else 0


def count_active_leads_for_daily_gate(db, username: str) -> int:
    """Working assignments that justify enforcing the daily call target (exits excluded)."""
    _uid = user_id_for_username(db, username)
    if _uid is None:
        return 0
    row = db.execute(
        """
        SELECT COUNT(*) AS c FROM leads
        WHERE assigned_user_id=? AND in_pool=0 AND deleted_at=''
          AND status NOT IN ('Lost','Retarget','Converted','Fully Converted')
        """,
        (_uid,),
    ).fetchone()
    return int(row['c'] or 0) if row else 0


def has_overdue_followups_active(db, username: str, today_d: str) -> bool:
    """Any assigned active lead with follow-up date before today (IST)."""
    _uid = user_id_for_username(db, username)
    if _uid is None:
        return False
    row = db.execute(
        """
        SELECT COUNT(*) AS c FROM leads
        WHERE assigned_user_id=? AND in_pool=0 AND deleted_at=''
          AND status NOT IN ('Converted','Lost','Fully Converted','Retarget')
          AND follow_up_date IS NOT NULL AND TRIM(COALESCE(follow_up_date,''))!=''
          AND date(substr(trim(follow_up_date), 1, 10)) < date(?)
        """,
        (_uid, today_d),
    ).fetchone()
    return int(row['c'] or 0) > 0 if row else False


def conversions_distinct_leads_on_date(db, username: str, day_iso: str) -> int:
    """Enrollment-style signals that day (not used for any hard block)."""
    _uid = user_id_for_username(db, username)
    if _uid is None:
        return 0
    _d = sql_ts_calendar_day("updated_at")
    row = db.execute(
        f"""
        SELECT COUNT(DISTINCT id) AS c FROM leads
        WHERE assigned_user_id=? AND in_pool=0 AND deleted_at=''
          AND {_d} = date(?)
          AND (
            payment_done=1
            OR status IN ('Paid ₹196','Day 1','Day 2','Interview',
                          '2cc Plan','Track Selected','Seat Hold Confirmed',
                          'Fully Converted','Converted','Training','Level Up')
          )
        """,
        (_uid, day_iso),
    ).fetchone()
    return int(row['c'] or 0) if row else 0


def has_lead_progression_signal(db, username: str) -> bool:
    """Any active assignment moved past raw new / contacted (effort outcome)."""
    _uid = user_id_for_username(db, username)
    if _uid is None:
        return False
    row = db.execute(
        """
        SELECT COUNT(*) AS c FROM leads
        WHERE assigned_user_id=? AND in_pool=0 AND deleted_at=''
          AND status NOT IN ('Lost','Retarget','Converted','Fully Converted')
          AND (
            payment_done=1
            OR status NOT IN ('New','New Lead','Contacted')
          )
        """,
        (_uid,),
    ).fetchone()
    return int(row['c'] or 0) > 0 if row else False


def effort_quality_safe(
    db, username: str, today_d: str, daily_tgt: int, today_calls: int, assigned_total: int,
) -> bool:
    """
    Rule 3 — high effort path: calls target, follow-ups not overdue, some funnel movement.
    Safe even with zero conversions today.
    Team members are exempt from the follow-up overdue check (they don't manage follow-ups).
    """
    role_row = db.execute("SELECT role FROM users WHERE username=?", (username,)).fetchone()
    _role = ((role_row['role'] if role_row else '') or '').strip()
    if _role == 'admin':
        return True
    if assigned_total == 0:
        return True
    if daily_tgt > 0 and today_calls < daily_tgt:
        return False
    if _role != 'team' and has_overdue_followups_active(db, username, today_d):
        return False
    if not has_lead_progression_signal(db, username):
        return False
    return True


def quality_market_cold_excuse(db, username: str) -> bool:
    """
    Rule 6 — many no-response touches: do not treat as fake work / low effort.
    """
    _uid = user_id_for_username(db, username)
    if _uid is None:
        return False
    nr = tuple(CALL_STATUS_NO_RESPONSE_BUCKET)
    ph = ','.join('?' * len(nr))
    row = db.execute(
        f"""
        SELECT
          SUM(CASE WHEN call_status IN ({ph}) THEN 1 ELSE 0 END) AS nr,
          SUM(CASE WHEN call_status IS NOT NULL AND TRIM(COALESCE(call_status,''))!=''
                    AND call_status != 'Not Called Yet' THEN 1 ELSE 0 END) AS touched
        FROM leads
        WHERE assigned_user_id=? AND in_pool=0 AND deleted_at=''
          AND status NOT IN ('Lost','Retarget','Converted','Fully Converted')
        """,
        (_uid, *nr),
    ).fetchone()
    touched = int(row['touched'] or 0) if row else 0
    if touched < QUALITY_MARKET_COLD_MIN_TOUCHED:
        return False
    nrc = int(row['nr'] or 0) if row else 0
    return (nrc / max(1, touched)) >= QUALITY_MARKET_COLD_NO_RESPONSE_RATIO


def quality_trend_high_effort_zero_conversion(db, username: str, today_d: str, daily_tgt: int) -> bool:
    """
    Rule 2 — soft coaching only: several recent days hit call bar, no conversions those days.
    """
    if not db.execute(
        "SELECT 1 FROM activity_log WHERE username=? AND event_type='lead_claim' LIMIT 1",
        (username,),
    ).fetchone():
        return False
    if quality_market_cold_excuse(db, username):
        return False
    tc_today = count_distinct_valid_calls_on_date(db, username, today_d)
    assigned = count_assigned_leads_total(db, username)
    if not effort_quality_safe(db, username, today_d, daily_tgt, tc_today, assigned):
        return False
    need = daily_tgt if daily_tgt > 0 else LOW_PERF_CALL_THRESHOLD
    good_days = 0
    for i in range(QUALITY_TREND_WINDOW_DAYS):
        d = (_today_ist() - datetime.timedelta(days=i)).isoformat()
        if conversions_distinct_leads_on_date(db, username, d) > 0:
            return False
        cday = count_distinct_valid_calls_on_date(db, username, d)
        if cday >= need:
            good_days += 1
    return good_days >= QUALITY_TREND_MIN_GOOD_DAYS


def stuck_early_single_stage(db, username: str) -> bool:
    """Rule 4 — many active leads frozen in early funnel (same status)."""
    _uid = user_id_for_username(db, username)
    if _uid is None:
        return False
    rows = db.execute(
        """
        SELECT status, COUNT(*) AS c FROM leads
        WHERE assigned_user_id=? AND in_pool=0 AND deleted_at=''
          AND status NOT IN ('Lost','Retarget','Converted','Fully Converted')
        GROUP BY status
        """,
        (_uid,),
    ).fetchall()
    if len(rows) != 1:
        return False
    st = rows[0]['status'] or ''
    c = int(rows[0]['c'] or 0)
    if c < 4:
        return False
    return st in ('New', 'New Lead', 'Contacted', 'Invited')


def evaluate_low_effort_today(db, username: str, today_d: str) -> bool:
    """
    Rule 4 + 7 — meaningful calls but missing follow-up discipline or frozen funnel.
    Suppressed when effort-safe or market-cold (Rule 3 / 6).
    """
    if not db.execute(
        "SELECT 1 FROM activity_log WHERE username=? AND event_type='lead_claim' LIMIT 1",
        (username,),
    ).fetchone():
        return False
    if quality_market_cold_excuse(db, username):
        return False
    daily_tgt = daily_call_target(db)
    tc = count_distinct_valid_calls_on_date(db, username, today_d)
    assigned = count_assigned_leads_total(db, username)
    if effort_quality_safe(db, username, today_d, daily_tgt, tc, assigned):
        return False
    active = count_active_leads_for_daily_gate(db, username)
    if active < 3:
        return False
    min_calls = max(LOW_PERF_CALL_THRESHOLD, (daily_tgt + 1) // 2) if daily_tgt > 0 else LOW_PERF_CALL_THRESHOLD
    if tc < min_calls:
        return False
    if has_overdue_followups_active(db, username, today_d):
        role_row = db.execute("SELECT role FROM users WHERE username=?", (username,)).fetchone()
        if role_row and (role_row["role"] or "").strip() != "team":
            return True
    if stuck_early_single_stage(db, username):
        return True
    return False


def process_low_effort_streak(db, username: str) -> None:
    """Once per IST day: update low_effort_days for repeat low-effort pattern (Rule 7)."""
    today_d = _today_ist().isoformat()
    row = db.execute(
        "SELECT low_effort_days, low_effort_tracked_date FROM users WHERE username=?",
        (username,),
    ).fetchone()
    if not row:
        return
    if _user_row_safe(row, 'low_effort_tracked_date', '').strip() == today_d:
        return
    claimed_before = db.execute(
        "SELECT 1 FROM activity_log WHERE username=? AND event_type='lead_claim' LIMIT 1",
        (username,),
    ).fetchone()
    if not claimed_before:
        db.execute(
            "UPDATE users SET low_effort_tracked_date=? WHERE username=?",
            (today_d, username),
        )
        return
    le = int(_user_row_safe(row, 'low_effort_days', 0) or 0)
    if evaluate_low_effort_today(db, username, today_d):
        le += 1
    else:
        le = 0
    db.execute(
        "UPDATE users SET low_effort_days=?, low_effort_tracked_date=? WHERE username=?",
        (le, today_d, username),
    )


def _user_row_safe(row, key: str, default=''):
    if not row:
        return default
    try:
        v = row[key]
        return default if v is None else v
    except (KeyError, IndexError, TypeError):
        return default


def user_in_active_grace(row, today_d: str) -> bool:
    if _user_row_safe(row, 'discipline_status', '').strip() != 'grace':
        return False
    gd = _user_row_safe(row, 'grace_return_date', '').strip()[:10]
    return bool(gd) and gd >= today_d


def user_is_performance_removed(row) -> bool:
    if int(_user_row_safe(row, 'access_blocked', 0) or 0) != 0:
        return True
    return _user_row_safe(row, 'discipline_status', '').strip() == 'removed'


def process_grace_expiry(db, username: str) -> None:
    today_d = _today_ist().isoformat()
    row = db.execute(
        "SELECT discipline_status, grace_return_date FROM users WHERE username=?",
        (username,),
    ).fetchone()
    if not row or _user_row_safe(row, 'discipline_status', '').strip() != 'grace':
        return
    gd = _user_row_safe(row, 'grace_return_date', '').strip()[:10]
    if gd and gd < today_d:
        db.execute(
            """
            UPDATE users SET discipline_status='', grace_reason='', grace_return_date='',
                grace_started_at=''
            WHERE username=?
            """,
            (username,),
        )


def process_low_performance_rollup(db, username: str) -> None:
    """
    Once per IST day: evaluate *yesterday's* valid call count to update streak.
    Avoids punishing 9am same-day zeros. Auto-remove at 3 consecutive low days.
    """
    today_d = _today_ist().isoformat()
    row = db.execute(
        """
        SELECT low_performance_days, low_perf_tracked_date
        FROM users WHERE username=?
        """,
        (username,),
    ).fetchone()
    if not row:
        return
    if (_user_row_safe(row, 'low_perf_tracked_date', '').strip() == today_d):
        return
    claimed_before = db.execute(
        "SELECT 1 FROM activity_log WHERE username=? AND event_type='lead_claim' LIMIT 1",
        (username,),
    ).fetchone()
    if not claimed_before:
        db.execute(
            "UPDATE users SET low_perf_tracked_date=? WHERE username=?",
            (today_d, username),
        )
        return
    yest = (_today_ist() - datetime.timedelta(days=1)).isoformat()
    y_calls = count_distinct_valid_calls_on_date(db, username, yest)
    lpd = int(_user_row_safe(row, 'low_performance_days', 0) or 0)
    if y_calls < LOW_PERF_CALL_THRESHOLD:
        lpd += 1
    else:
        lpd = 0
    flagged = 1 if lpd >= LOW_PERF_STREAK_BLOCK else 0
    if lpd >= LOW_PERF_STREAK_REMOVE:
        db.execute(
            """
            UPDATE users SET low_performance_days=?, low_perf_tracked_date=?,
                performance_flagged=1, discipline_status='removed', access_blocked=1
            WHERE username=?
            """,
            (lpd, today_d, username),
        )
    else:
        db.execute(
            """
            UPDATE users SET low_performance_days=?, low_perf_tracked_date=?,
                performance_flagged=?
            WHERE username=?
            """,
            (lpd, today_d, flagged, username),
        )


def performance_discipline_on_request(db, username: str) -> None:
    """Run grace expiry + daily streak rollup (idempotent per calendar day)."""
    process_grace_expiry(db, username)
    process_inactivity_escalation(db, username)
    process_low_performance_rollup(db, username)
    process_low_effort_streak(db, username)


def normalize_grace_reason(text: str) -> str:
    return ' '.join((text or '').lower().split())[:240]


def grace_approved_count_last_30_days(db, username: str) -> int:
    cutoff = (_today_ist() - datetime.timedelta(days=30)).isoformat()
    row = db.execute(
        """
        SELECT COUNT(*) AS c FROM user_grace_history
        WHERE username=? AND outcome='approved'
          AND date(substr(trim(created_at), 1, 10)) >= date(?)
        """,
        (username, cutoff),
    ).fetchone()
    return int(row['c'] or 0) if row else 0


def grace_repeat_count(db, username: str, reason_normalized: str) -> int:
    row = db.execute(
        """
        SELECT COUNT(*) AS c FROM user_grace_history
        WHERE username=? AND reason_normalized=?
        """,
        (username, reason_normalized),
    ).fetchone()
    return int(row['c'] or 0) if row else 0


def submit_performance_grace_request(db, username: str, reason_text: str, return_date_str: str) -> Tuple[bool, str]:
    """
    Returns (ok, message). On success caller should commit.
    """
    u0 = db.execute(
        "SELECT discipline_status, grace_return_date, access_blocked FROM users WHERE username=?",
        (username,),
    ).fetchone()
    if user_is_performance_removed(u0):
        return False, 'Access blocked.'
    today_iso = _today_ist().isoformat()
    if user_in_active_grace(u0, today_iso):
        return False, 'Grace mode is already active.'

    reason_text = (reason_text or '').strip()
    return_date_str = (return_date_str or '').strip()[:10]
    if len(reason_text) < 8:
        return False, 'Please add a short reason (a bit of detail helps).'
    if not return_date_str or len(return_date_str) < 10:
        return False, 'Expected return date is required.'
    try:
        ret_d = datetime.date.fromisoformat(return_date_str)
    except ValueError:
        return False, 'Return date format is invalid (use YYYY-MM-DD).'
    today_d = _today_ist()
    if ret_d < today_d:
        return False, 'Return date cannot be in the past.'
    if ret_d > today_d + datetime.timedelta(days=60):
        return False, 'Return date cannot be more than 60 days ahead.'

    now_s = _now_ist().strftime('%Y-%m-%d %H:%M:%S')
    norm = normalize_grace_reason(reason_text)
    if grace_repeat_count(db, username, norm) >= GRACE_REPEAT_THRESHOLD:
        db.execute(
            """
            INSERT INTO user_grace_history
            (username, reason_normalized, reason_text, expected_return_date, outcome, created_at)
            VALUES (?,?,?,?, 'rejected', ?)
            """,
            (username, norm, reason_text[:500], return_date_str, now_s),
        )
        return False, 'Repeated excuse pattern detected. Discipline required.'

    if grace_approved_count_last_30_days(db, username) >= GRACE_MAX_PER_30_DAYS:
        return False, 'Grace limit: at most 2 requests per 30 days. Admin review required.'
    db.execute(
        """
        UPDATE users SET discipline_status='grace', grace_reason=?, grace_return_date=?,
            grace_started_at=?, access_blocked=0, performance_flagged=0,
            low_effort_days=0, low_effort_tracked_date=''
        WHERE username=?
        """,
        (reason_text, return_date_str, now_s, username),
    )
    db.execute(
        """
        INSERT INTO user_grace_history
        (username, reason_normalized, reason_text, expected_return_date, outcome, created_at)
        VALUES (?,?,?,?, 'approved', ?)
        """,
        (username, norm, reason_text, return_date_str, now_s),
    )
    return True, 'Grace approved. Step 2 and Step 4 checks are temporarily suspended.'


def build_performance_alerts(
    today_calls: int,
    low_pd: int,
    in_grace: bool,
    grace_until: str,
    daily_tgt: int,
    assigned_total: int = 0,
    *,
    quality_approach_hint: bool = False,
    low_effort_days: int = 0,
    low_effort_today: bool = False,
) -> List[dict]:
    """UI banners: level in ('info','warning','danger')."""
    out: List[dict] = []
    if in_grace and grace_until:
        out.append({
            'level': 'info',
            'text': f'Grace mode active until {grace_until}. Claim gates (Steps 2 and 4) are temporarily waived.',
        })
        return out
    if low_pd >= LOW_PERF_STREAK_BLOCK:
        out.append({
            'level': 'danger',
            'text': 'Performance has been low for 2 days. Claiming new leads is blocked until you recover.',
        })
        return out
    if low_pd == 1:
        out.append({
            'level': 'danger',
            'text': 'Final warning: you have 2 days to improve performance.',
        })
    current_hour = _now_ist().hour
    is_evening = current_hour >= DAILY_CALL_ENFORCE_START_HOUR_IST
    if daily_tgt > 0 and today_calls < DAILY_CALL_WARN_CAP:
        if assigned_total == 0 and low_pd == 0:
            pass
        elif not is_evening:
            remaining = DAILY_CALL_WARN_CAP - today_calls
            out.append({
                'level': 'info',
                'text': f'{today_calls}/{DAILY_CALL_WARN_CAP} calls done. {remaining} remaining — you have time, keep going!',
            })
        elif today_calls >= LOW_PERF_CALL_THRESHOLD:
            out.append({
                'level': 'warning',
                'text': (
                    f'Today’s target is {DAILY_CALL_WARN_CAP} logged calls; you are at {today_calls}. '
                    f'Please finish before end of day.'
                ),
            })
        else:
            out.append({
                'level': 'danger',
                'text': (
                    'Critical: fewer than 6 calls logged. This violates discipline rules — take action now.'
                ),
            })
    if quality_approach_hint:
        out.append({
            'level': 'warning',
            'text': (
                'Consider refreshing your approach — calling and follow-up look consistent but conversions are flat; '
                'try a new angle. (Coaching only — no block.)'
            ),
        })
    if low_effort_days >= LOW_EFFORT_BLOCK_STREAK:
        out.append({
            'level': 'danger',
            'text': (
                'Repeated low-effort pattern — fix follow-ups and pipeline progress first, '
                'then claim new leads.'
            ),
        })
    elif low_effort_today:
        out.append({
            'level': 'warning',
            'text': (
                'Low-effort signal: calls are logged but follow-up or pipeline movement looks thin — '
                'improve or claiming may be restricted.'
            ),
        })
    return out


def get_performance_ui_state(db, username: str) -> dict:
    performance_discipline_on_request(db, username)
    today_d = _today_ist().isoformat()
    row = db.execute(
        """
        SELECT discipline_status, grace_return_date, grace_reason, low_performance_days, access_blocked,
               low_effort_days
        FROM users WHERE username=?
        """,
        (username,),
    ).fetchone()
    in_grace = user_in_active_grace(row, today_d)
    tc = count_distinct_valid_calls_on_date(db, username, today_d)
    tgt = daily_call_target(db)
    assigned_total = count_assigned_leads_total(db, username)
    gu = _user_row_safe(row, 'grace_return_date', '').strip()[:10] if in_grace else ''
    le_days = int(_user_row_safe(row, 'low_effort_days', 0) or 0)
    q_approach = quality_trend_high_effort_zero_conversion(db, username, today_d, tgt)
    le_today = evaluate_low_effort_today(db, username, today_d)
    alerts = build_performance_alerts(
        tc,
        int(_user_row_safe(row, 'low_performance_days', 0) or 0),
        in_grace,
        gu,
        tgt,
        assigned_total,
        quality_approach_hint=q_approach,
        low_effort_days=le_days,
        low_effort_today=le_today,
    )
    removed = user_is_performance_removed(row)
    ds = _user_row_safe(row, 'discipline_status', '').strip()
    show_grace_form = (
        not in_grace and not removed and ds != 'removed'
    )
    return {
        'today_calls': tc,
        'daily_target': tgt,
        'in_grace': in_grace,
        'grace_until': gu,
        'low_performance_days': int(_user_row_safe(row, 'low_performance_days', 0) or 0),
        'low_effort_days': le_days,
        'quality_approach_hint': q_approach,
        'alerts': alerts,
        'show_grace_form': show_grace_form,
        'removed': removed,
    }


def claim_hard_gate_message(db, username: str) -> Optional[str]:
    """
    Block pool claims until recent-lead work is done (team/leader only at call site).
    Only leads claimed in the last 24h / 48h windows count — old leads never block.
    Lost / Retarget / converted exits never block (Step 3).
    Step 5: never blocks on conversions=0 alone; low-effort streak is separate from conversion.

    Rules 2 and 8 (follow-up discipline) apply only to leader/admin — not to team role.

    Optional app_settings key ``claim_discipline_start_date`` (YYYY-MM-DD): when set, Rules 1–3, 8
    and Step 4 only consider leads whose ``claimed_at`` date (or ``created_at`` if unclaimed) is
    on/after that day — legacy backlog does not block new pool claims.
    With env auto-start (default on in production), the first visit seeds that date to today's IST
    once; it does not roll forward daily.

    Returns a short user-facing message if claim must be blocked, else None.
    """
    role_row = db.execute("SELECT role FROM users WHERE username=?", (username,)).fetchone()
    if role_row and (role_row['role'] or '').strip() == 'admin':
        return None
    claim_gate_enabled = ((_get_setting(db, 'gate_claim_discipline_enabled', '1') or '1') == '1')
    followup_gate_enabled = ((_get_setting(db, 'gate_followup_discipline_enabled', '1') or '1') == '1')
    perf_gate_enabled = ((_get_setting(db, 'gate_performance_discipline_enabled', '1') or '1') == '1')
    if not claim_gate_enabled:
        return None

    maybe_auto_seed_claim_discipline_start(db)
    if followup_gate_enabled:
        followup_discipline_process_overdue(db, username)
    if perf_gate_enabled:
        performance_discipline_on_request(db, username)

    today_d = _today_ist().isoformat()
    _luid = user_id_for_username(db, username)
    if _luid is None:
        return None
    uperf = db.execute(
        """
        SELECT discipline_status, grace_return_date, low_performance_days, access_blocked,
               low_effort_days, role
        FROM users WHERE username=?
        """,
        (username,),
    ).fetchone()
    user_role = (_user_row_safe(uperf, "role", "team") or "team").strip()
    if user_in_active_grace(uperf, today_d):
        return None

    now = _now_ist().replace(tzinfo=None)
    cut24 = (now - datetime.timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')
    cut48 = (now - datetime.timedelta(hours=48)).strftime('%Y-%m-%d %H:%M:%S')
    disc_start = claim_discipline_start_date_iso(db)
    _ds_sql = " AND date(substr(trim(claimed_at),1,10)) >= date(?)" if disc_start else ""

    # RULE 1 — uncalled, claimed in last 24h only (exits excluded)
    r1_params: Tuple = (_luid, cut24)
    if disc_start:
        r1_params = (_luid, cut24, disc_start)
    r1 = db.execute(
        f"""
        SELECT COUNT(*) AS c FROM leads
        WHERE assigned_user_id=? AND in_pool=0 AND deleted_at=''
          AND status NOT IN ('Lost','Retarget')
          AND claimed_at IS NOT NULL AND TRIM(COALESCE(claimed_at,''))!=''
          AND claimed_at >= ?
          {_ds_sql}
          AND (call_status IS NULL OR TRIM(COALESCE(call_status,''))=''
               OR call_status='Not Called Yet')
        """,
        r1_params,
    ).fetchone()
    if r1 and (r1['c'] or 0) > 0:
        return 'Call your assigned leads first'

    # RULE 2 — overdue follow-up, lead claimed in last 48h only (leader/admin; not team)
    r2 = None
    if user_role != "team":
        r2_params: Tuple = (_luid, today_d, cut48)
        if disc_start:
            r2_params = (_luid, today_d, cut48, disc_start)
        r2 = db.execute(
            f"""
            SELECT COUNT(*) AS c FROM leads
            WHERE assigned_user_id=? AND in_pool=0 AND deleted_at=''
              AND follow_up_date IS NOT NULL AND TRIM(COALESCE(follow_up_date,''))!=''
              AND date(substr(trim(follow_up_date), 1, 10)) < date(?)
              AND claimed_at IS NOT NULL AND TRIM(COALESCE(claimed_at,''))!=''
              AND claimed_at >= ?
              {_ds_sql}
              AND status NOT IN ('Converted','Lost','Fully Converted','Retarget')
            """,
            r2_params,
        ).fetchone()
    if followup_gate_enabled and r2 and (r2['c'] or 0) > 0:
        return 'Overdue follow-ups — clear them first'

    # RULE 3 — hot funnel, claimed in last 24h, no touch in 24h
    ib = tuple(CALL_STATUS_INTERESTED_BUCKET)
    ph_ib = ','.join('?' * len(ib))
    hot_st = ('Video Watched', 'Paid ₹196', 'Video Sent')
    ph_st = ','.join('?' * len(hot_st))
    r3_params: Tuple = (_luid, cut24, *ib, *hot_st, cut24)
    if disc_start:
        r3_params = (_luid, cut24, disc_start, *ib, *hot_st, cut24)
    r3 = db.execute(
        f"""
        SELECT COUNT(*) AS c FROM leads
        WHERE assigned_user_id=? AND in_pool=0 AND deleted_at=''
          AND claimed_at IS NOT NULL AND TRIM(COALESCE(claimed_at,''))!=''
          AND claimed_at >= ?
          {_ds_sql}
          AND status NOT IN ('Lost','Retarget','Converted','Fully Converted')
          AND (
            call_status IN ({ph_ib})
            OR status IN ({ph_st})
          )
          AND updated_at IS NOT NULL AND TRIM(COALESCE(updated_at,''))!=''
          AND updated_at < ?
        """,
        r3_params,
    ).fetchone()
    if r3 and (r3['c'] or 0) > 0:
        return 'Hot leads are waiting — update them first'

    # RULE 8 — interested / hot lead rows must have a follow-up date set (recent claims; leader/admin)
    r8 = None
    if user_role != "team":
        r8_params: Tuple = (_luid, cut48, *ib, *hot_st)
        if disc_start:
            r8_params = (_luid, cut48, disc_start, *ib, *hot_st)
        r8 = db.execute(
            f"""
            SELECT COUNT(*) AS c FROM leads
            WHERE assigned_user_id=? AND in_pool=0 AND deleted_at=''
              AND status NOT IN ('Lost','Retarget','Converted','Fully Converted')
              AND claimed_at IS NOT NULL AND TRIM(COALESCE(claimed_at,''))!=''
              AND claimed_at >= ?
              {_ds_sql}
              AND (
                call_status IN ({ph_ib})
                OR status IN ({ph_st})
              )
              AND (follow_up_date IS NULL OR TRIM(COALESCE(follow_up_date,''))='')
            """,
            r8_params,
        ).fetchone()
    if followup_gate_enabled and r8 and (r8['c'] or 0) > 0:
        _tomorrow = (_now_ist() + datetime.timedelta(days=1)).strftime('%Y-%m-%d')
        db.execute(
            f"""
            UPDATE leads SET follow_up_date=?, updated_at=?
            WHERE assigned_user_id=? AND in_pool=0 AND deleted_at=''
              AND status NOT IN ('Lost','Retarget','Converted','Fully Converted')
              AND claimed_at IS NOT NULL AND TRIM(COALESCE(claimed_at,''))!=''
              AND claimed_at >= ?
              {_ds_sql}
              AND (
                call_status IN ({ph_ib})
                OR status IN ({ph_st})
              )
              AND (follow_up_date IS NULL OR TRIM(COALESCE(follow_up_date,''))='')
            """,
            (_tomorrow, _now_ist().strftime('%Y-%m-%d %H:%M:%S'), _luid, cut48, *(disc_start and (disc_start,) or ()), *ib, *hot_st),
        )
        db.commit()

    low_pd = int(_user_row_safe(uperf, 'low_performance_days', 0) or 0)
    if perf_gate_enabled and low_pd >= LOW_PERF_STREAK_BLOCK:
        return (
            'Performance has been low for 2+ days — restrictions are active. '
            'Log calls, update lead statuses, and add follow-up dates. '
            'Status refreshes daily at 9 PM.'
        )

    low_eff = int(_user_row_safe(uperf, 'low_effort_days', 0) or 0)
    if perf_gate_enabled and low_eff >= LOW_EFFORT_BLOCK_STREAK:
        return (
            'Low-effort pattern detected for 3+ days. To unblock: log at least '
            f'{LOW_EFFORT_BLOCK_STREAK} calls today, update pipeline stages, and set '
            'follow-up dates on hot leads. Status refreshes daily at 9 PM.'
        )

    # STEP 4 — daily call target (only enforced after 9 PM IST; before that just encourage)
    tgt = daily_call_target(db)
    if tgt > 0 and count_assigned_leads_for_claim_discipline(db, username) > 0:
        ct = count_call_logged_leads_today(db, username, today_d)
        if ct < tgt and _now_ist().hour >= DAILY_CALL_ENFORCE_START_HOUR_IST:
            return f'Complete at least {tgt} logged calls today'

    return None


def _log_lead_event(db, lead_id, username, note):
    """Insert a timeline entry for a lead."""
    db.execute(
        "INSERT INTO lead_notes (lead_id, username, note, created_at) VALUES (?,?,?,?)",
        (lead_id, username, note, _now_ist().strftime('%Y-%m-%d %H:%M:%S'))
    )


def _get_setting(db, key, default=''):
    """Get an app setting value."""
    row = db.execute("SELECT value FROM app_settings WHERE key=?", (key,)).fetchone()
    return row['value'] if row else default


def _set_setting(db, key, value):
    """Upsert an app setting."""
    db.execute(
        "INSERT INTO app_settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value)
    )


def _get_wallet(db, username):
    """Compute wallet stats for a team member (pool spent via ``services.wallet_ledger``).

    ``balance`` is never below zero: effective spend cannot drive displayed/usable
    balance negative (``recharged`` / ``spent`` stay raw for reconciliation).
    """
    recharged = db.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM wallet_recharges "
        "WHERE username=? AND status='approved'",
        (username,)
    ).fetchone()[0] or 0.0

    spent = float(sum_pool_spent_for_buyer(db, username))

    raw = round(float(recharged) - float(spent), 2)
    balance = raw if raw > 0 else 0.0
    return {
        'recharged': round(float(recharged), 2),
        'spent':     round(float(spent), 2),
        'balance':   balance,
    }


def _get_metrics(db, username=None, since=None):
    """All dashboard KPIs. Excludes pool and soft-deleted leads.
    If `since` is provided (YYYY-MM-DD), only leads claimed on/after that date are counted.
    Leads with empty/NULL claimed_at are excluded from new-tracking metrics.
    """
    if username:
        _row = db.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
        _pk = int(_row["id"]) if _row else -1
        where_clause = "WHERE assigned_user_id = ? AND in_pool = 0 AND deleted_at = ''"
        params = [_pk]
        base = "assigned_user_id = ? AND in_pool = 0 AND deleted_at = ''"
    else:
        where_clause = "WHERE in_pool = 0 AND deleted_at = ''"
        params = []
        base = "in_pool = 0 AND deleted_at = ''"

    if since:
        # Use claimed_at when set; fall back to created_at so manually-assigned leads
        # (no claimed_at) are still counted when they were created in the window.
        where_clause += " AND COALESCE(NULLIF(TRIM(claimed_at),''), created_at) >= ?"
        base += " AND COALESCE(NULLIF(TRIM(claimed_at),''), created_at) >= ?"
        params.append(since)

    params = tuple(params)

    row = db.execute(f"""
        SELECT
            COUNT(*)                                                      AS total,
            SUM(CASE WHEN status IN ('Converted','Fully Converted')
                      THEN 1 ELSE 0 END)                                  AS converted,
            SUM(CASE WHEN payment_done=1     THEN 1 ELSE 0 END)          AS paid,
            SUM(COALESCE(payment_amount,0) + COALESCE(revenue,0))        AS revenue,
            SUM(CASE WHEN day1_done=1        THEN 1 ELSE 0 END)          AS day1,
            SUM(CASE WHEN day2_done=1        THEN 1 ELSE 0 END)          AS day2,
            SUM(CASE WHEN interview_done=1   THEN 1 ELSE 0 END)          AS interviews,
            ROUND(
                CAST(SUM(CASE WHEN payment_done=1 THEN 1 ELSE 0 END) AS REAL)
                / NULLIF(COUNT(*), 0) * 100
            , 1)                                                          AS paid196_pct,
            ROUND(
                CAST(SUM(CASE WHEN status IN ('Converted','Fully Converted')
                              THEN 1 ELSE 0 END) AS REAL)
                / NULLIF(COUNT(*), 0) * 100
            , 1)                                                          AS close_pct,
            ROUND(
                SUM(COALESCE(payment_amount,0) + COALESCE(revenue,0))
                / NULLIF(COUNT(*), 0)
            , 2)                                                          AS rev_per_lead
        FROM leads {where_clause}
    """, params).fetchone()

    track_sel    = db.execute(f"SELECT COUNT(*) FROM leads WHERE {base} AND status='Track Selected'", params).fetchone()[0] or 0
    seat_hold    = db.execute(f"SELECT COUNT(*) FROM leads WHERE {base} AND status='Seat Hold Confirmed'", params).fetchone()[0] or 0
    fully_conv   = db.execute(f"SELECT COUNT(*) FROM leads WHERE {base} AND status='Fully Converted'", params).fetchone()[0] or 0
    seat_rev     = db.execute(f"SELECT COALESCE(SUM(seat_hold_amount),0) FROM leads WHERE {base} AND status='Seat Hold Confirmed'", params).fetchone()[0] or 0
    final_rev    = db.execute(f"SELECT COALESCE(SUM(track_price),0) FROM leads WHERE {base} AND status='Fully Converted'", params).fetchone()[0] or 0

    return dict(
        total        = row['total']        or 0,
        converted    = row['converted']    or 0,
        paid         = row['paid']         or 0,
        revenue      = row['revenue']      or 0.0,
        day1         = row['day1']         or 0,
        day2         = row['day2']         or 0,
        interviews   = row['interviews']   or 0,
        paid196_pct  = row['paid196_pct']  or 0.0,
        close_pct    = row['close_pct']    or 0.0,
        rev_per_lead = row['rev_per_lead'] or 0.0,
        track_sel    = track_sel,
        seat_hold    = seat_hold,
        fully_conv   = fully_conv,
        seat_rev     = seat_rev,
        final_rev    = final_rev,
    )


def user_id_for_username(db, username: str):
    """Return users.id for login username, or None."""
    if not username:
        return None
    r = db.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
    return int(r['id']) if r else None


def user_ids_for_usernames(db, usernames: list) -> dict:
    """Batch map username -> users.id (skips missing). Avoids N+1 queries on downline lists."""
    if not usernames:
        return {}
    rows = db.execute(
        "SELECT username, id FROM users WHERE username IN (%s)" % ",".join("?" * len(usernames)),
        tuple(usernames),
    ).fetchall()
    return {str(r["username"]): int(r["id"]) for r in rows}


def network_user_ids_for_username(db, username: str) -> set:
    """user ids visible to username (self + recursive downlines)."""
    out = set()
    for un in _get_network_usernames(db, username):
        i = user_id_for_username(db, un)
        if i is not None:
            out.add(i)
    return out


def _get_downline_usernames(db, username):
    """Return [username] + all recursive downlines via upline username and/or upline FBO."""
    rows = db.execute("""
        WITH RECURSIVE downline(uname, mfbo) AS (
            SELECT u.username, NULLIF(TRIM(COALESCE(u.fbo_id, '')), '')
            FROM users u WHERE u.username = ?
            UNION ALL
            SELECT u.username, NULLIF(TRIM(COALESCE(u.fbo_id, '')), '')
            FROM users u
            INNER JOIN downline d ON u.status = 'approved'
                AND (
                    u.upline_name = d.uname OR u.upline_username = d.uname
                    OR (
                        d.mfbo IS NOT NULL
                        AND TRIM(COALESCE(u.upline_fbo_id, '')) != ''
                        AND TRIM(u.upline_fbo_id) = d.mfbo
                    )
                )
        )
        SELECT uname FROM downline
    """, (username,)).fetchall()
    return [r['uname'] for r in rows]


def _get_network_usernames(db, username):
    """Return [username] + all recursive downlines. Delegates to CTE-based query."""
    return _get_downline_usernames(db, username)


def _get_admin_username(db):
    """Return username of first admin user."""
    row = db.execute("SELECT username FROM users WHERE role='admin' LIMIT 1").fetchone()
    return row['username'] if row else 'admin'


def validate_upline_assignment_roles(child_role: str, parent_role: str) -> Tuple[bool, str]:
    """
    Validate hierarchy assignment roles.

    Rules:
    - team  -> leader or admin (direct-to-admin upline, e.g. admin FBO as sponsor)
    - leader -> admin only
    - admin has no upline
    """
    c = (child_role or '').strip().lower()
    p = (parent_role or '').strip().lower()
    if c == 'team':
        if p not in ('leader', 'admin'):
            return False, 'Team members can only be assigned to a Leader or Admin.'
        return True, ''
    if c == 'leader':
        if p != 'admin':
            return False, 'Leaders can only be assigned to Admin.'
        return True, ''
    if c == 'admin':
        return False, 'Admin account cannot have an upline.'
    return False, f'Unsupported child role: {child_role}'


def ensure_upline_fields_for_user(db, username: str) -> None:
    """
    Keep upline_username, upline_name, upline_fbo_id, and upline_id aligned.
    Source of truth: upline_fbo_id when set (registration), else upline username.
    Call on login and when a member is approved so the network tree stays correct.
    """
    if not username:
        return
    row = db.execute(
        """
        SELECT username, role, status, upline_name, upline_username, upline_fbo_id
        FROM users WHERE username=?
        """,
        (username,),
    ).fetchone()
    if not row:
        return
    if row["role"] not in ("team", "leader") or row["status"] != "approved":
        return

    un = (row["upline_username"] or "").strip() or (row["upline_name"] or "").strip()
    ufbo = (row["upline_fbo_id"] or "").strip()

    target_un = ""
    target_fbo = ""

    if ufbo:
        parent = db.execute(
            """
            SELECT username, COALESCE(NULLIF(TRIM(fbo_id), ''), '') AS fb
            FROM users
            WHERE TRIM(fbo_id)=? AND status='approved'
            LIMIT 1
            """,
            (ufbo,),
        ).fetchone()
        if parent:
            target_un = (parent["username"] or "").strip()
            target_fbo = (parent["fb"] or ufbo).strip()
    if not target_un and un:
        parent = db.execute(
            """
            SELECT username, COALESCE(NULLIF(TRIM(fbo_id), ''), '') AS fb
            FROM users
            WHERE username=? AND status='approved'
            LIMIT 1
            """,
            (un,),
        ).fetchone()
        if parent:
            target_un = (parent["username"] or "").strip()
            target_fbo = (parent["fb"] or "").strip()

    if not target_un:
        return

    uid_row = db.execute("SELECT id FROM users WHERE username=? LIMIT 1", (target_un,)).fetchone()
    up_id = int(uid_row["id"]) if uid_row else None

    db.execute(
        """
        UPDATE users
        SET upline_username=?, upline_name=?, upline_fbo_id=?, upline_id=?
        WHERE username=?
        """,
        (target_un, target_un, target_fbo, up_id, username),
    )


def _assignee_username_for_lead(db, lead) -> str:
    """Resolve team-member username from assigned_user_id."""
    keys = lead.keys() if hasattr(lead, 'keys') else []
    uid = None
    if 'assigned_user_id' in keys:
        try:
            uid = lead['assigned_user_id']
        except (KeyError, TypeError):
            uid = None
    if uid:
        row = db.execute('SELECT username FROM users WHERE id=?', (int(uid),)).fetchone()
        if row:
            return row['username'] or ''
    return ''


def _get_leader_for_user(db, username):
    """Return the direct leader/upline username for a given user."""
    if not username:
        return _get_admin_username(db)
    row = db.execute(
        "SELECT upline_name, upline_username, upline_fbo_id FROM users WHERE username=?",
        (username,),
    ).fetchone()
    if not row:
        return _get_admin_username(db)
    leader = (row['upline_username'] or '').strip() or (row['upline_name'] or '').strip()
    if not leader:
        ufbo = (row['upline_fbo_id'] or '').strip()
        if ufbo:
            lrow = db.execute(
                "SELECT username FROM users WHERE TRIM(fbo_id)=? AND status='approved'",
                (ufbo,),
            ).fetchone()
            if lrow and (lrow['username'] or '').strip():
                return (lrow['username'] or '').strip()
        return _get_admin_username(db)
    lrow = db.execute(
        "SELECT username FROM users WHERE username=? AND status='approved'", (leader,)
    ).fetchone()
    return lrow['username'] if lrow else _get_admin_username(db)


def can_review_rupees_196_proof(db, reviewer_username: str, reviewer_role: str, lead_row: Any) -> bool:
    """
    Who may approve/reject ₹196 screenshots:
    - admin: any lead (covers leader-away / self-assigned leader leads / full queue).
    - leader: full downline tree only (`_get_network_usernames`, same rule as enrollment queue);
      never when the lead is assigned to that leader (self-approve blocked — admin only).
    """
    if reviewer_role == 'admin':
        return True
    if reviewer_role != 'leader':
        return False
    r_un = (reviewer_username or '').strip()
    if not r_un:
        return False
    try:
        aid = int(sqlite_row_get(lead_row, 'assigned_user_id') or 0)
    except (TypeError, ValueError):
        aid = 0
    rid = user_id_for_username(db, r_un)
    if rid is not None and aid and rid == aid:
        return False
    assignee_un = _assignee_username_for_lead(db, lead_row)
    if not assignee_un:
        return False
    a_low = assignee_un.strip().lower()
    if a_low == r_un.lower():
        return False
    net = {((u or '').strip().lower()) for u in _get_network_usernames(db, r_un) if (u or '').strip()}
    return a_low in net


# ─────────────────────────────────────────────────────────────────────────────
#  Priority / Heat / Next-Action / AI-Tip engines
# ─────────────────────────────────────────────────────────────────────────────

def _calculate_priority(lead):
    """Compute a priority score for a lead (call on every query, never cache)."""
    score = 0
    today = _today_ist().isoformat()
    keys = lead.keys() if hasattr(lead, 'keys') else []
    status = lead['status'] if 'status' in keys else ''
    if status == 'Video Watched':
        score += 20
    payment_done = lead['payment_done'] if 'payment_done' in keys else 0
    if payment_done:
        score += 40
    follow_up_date = lead['follow_up_date'] if 'follow_up_date' in keys else ''
    if follow_up_date and follow_up_date[:10] == today:
        score += 50
    created_at = lead['created_at'] if 'created_at' in keys else ''
    if created_at and created_at[:10] == today:
        score += 10
    return score


def _leads_with_priority(raw_leads):
    """Return list of dicts sorted by priority score descending."""
    result = []
    for lead in raw_leads:
        d = dict(lead)
        d['priority_score'] = _calculate_priority(lead)
        result.append(d)
    result.sort(key=lambda x: (-x['priority_score'], x.get('created_at', '')))
    return result


def _calculate_heat_score(lead):
    """Return 0-100 heat score: call_status signal + stage + recency + follow-up."""
    score = 0
    keys  = lead.keys() if hasattr(lead, 'keys') else []
    get   = lambda k, d='': lead[k] if k in keys else d

    _call_pts = {
        'Payment Done':         40,
        'Video Watched':        25,
        'Called - Interested':  20,
        'Called - Follow Up':   15,
        'Video Sent':           10,
        'Called - No Answer':    5,
    }
    _status_pts = {
        'Video Watched': 25,
        'Video Sent':    10,
        'Paid ₹196':     40,
    }
    score += max(_call_pts.get(get('call_status'), 0), _status_pts.get(get('status'), 0))

    stage = get('pipeline_stage', 'enrollment')
    if stage in ('day3', 'seat_hold'):
        score += 20
    elif stage in ('day1', 'day2'):
        score += 10

    upd = get('updated_at') or get('created_at', '')
    if upd:
        try:
            upd_date = datetime.datetime.strptime(upd[:10], '%Y-%m-%d').date()
            days_old = (_today_ist() - upd_date).days
            if   days_old <= 1: score += 20
            elif days_old <= 3: score += 10
            elif days_old >= 8: score -= 15
        except Exception:
            pass

    today_str = _today_ist().isoformat()
    fu = get('follow_up_date', '')
    if fu:
        if   fu[:10] == today_str: score += 20
        elif fu[:10] <  today_str: score -= 10

    return max(0, min(100, int(score)))


def _get_next_action(lead):
    """Return {action, type, priority} -- the single most important next step."""
    keys = lead.keys() if hasattr(lead, 'keys') else []
    get  = lambda k, d='': lead[k] if k in keys else d

    stage        = get('pipeline_stage', 'enrollment')
    call_status  = get('call_status', '')
    status       = get('status', '')
    payment_done = int(get('payment_done', 0) or 0)

    if stage == 'enrollment':
        if not call_status or call_status == 'Not Called Yet':
            return {'action': 'Make first call', 'type': 'urgent', 'priority': 1}
        if call_status == 'Called - Interested' and status not in ('Video Sent', 'Video Watched', 'Paid ₹196'):
            return {'action': 'Send video now', 'type': 'urgent', 'priority': 1}
        if call_status in ('Called - No Answer', 'Called - Follow Up'):
            return {'action': 'Follow-up call', 'type': 'today', 'priority': 2}
        if (call_status == 'Video Watched' or status == 'Video Watched') and not payment_done:
            return {'action': 'Call for payment', 'type': 'urgent', 'priority': 1}
        if payment_done and status == 'Paid ₹196':
            return {'action': 'Move to Day 1', 'type': 'today', 'priority': 2}
        return {'action': 'Follow up', 'type': 'followup', 'priority': 3}

    if stage == 'day1':
        d1_m = int(get('d1_morning', 0) or 0)
        d1_a = int(get('d1_afternoon', 0) or 0)
        d1_e = int(get('d1_evening', 0) or 0)
        rem   = 3 - (d1_m + d1_a + d1_e)
        if rem > 0:
            return {'action': f'{rem} batch(es) left', 'type': 'today', 'priority': 2}
        return {'action': 'Send to Day 2', 'type': 'today', 'priority': 2}

    if stage == 'day2':
        return {'action': 'Admin conducting', 'type': 'followup', 'priority': 4}

    if stage == 'day3':
        if not int(get('interview_done', 0) or 0):
            return {'action': 'Do interview', 'type': 'urgent', 'priority': 1}
        if not int(get('track_selected', 0) or 0):
            return {'action': 'Select track', 'type': 'urgent', 'priority': 1}
        return {'action': 'Confirm Seat Hold', 'type': 'urgent', 'priority': 1}

    if stage == 'seat_hold':
        expiry_str = get('seat_hold_expiry', '')
        if expiry_str:
            try:
                expiry = datetime.datetime.strptime(expiry_str[:19], '%Y-%m-%d %H:%M:%S')
                now    = _now_ist().replace(tzinfo=None)
                hours  = (expiry - now).total_seconds() / 3600
                if hours < 12:
                    return {'action': f'URGENT: expires in {max(0,int(hours))}h',
                            'type': 'urgent', 'priority': 0}
            except Exception:
                pass
        return {'action': 'Final payment follow up', 'type': 'followup', 'priority': 3}

    if stage in ('closing', 'training'):
        return {'action': 'In closing process', 'type': 'followup', 'priority': 4}

    if stage in ('complete', 'lost'):
        return {'action': '\u2014', 'type': 'cold', 'priority': 9}

    return {'action': 'Follow up', 'type': 'followup', 'priority': 3}


def _generate_ai_tip(lead):
    """Return a Hindi/Hinglish AI tip string based on lead state."""
    get   = lambda k, d='': lead.get(k, d) if isinstance(lead, dict) else (
        lead[k] if hasattr(lead, 'keys') and k in lead.keys() else d)
    stage        = get('pipeline_stage', 'enrollment')
    heat         = int(get('heat', _calculate_heat_score(lead)))
    name         = get('name', 'Prospect')
    call_status  = get('call_status', '')
    payment_done = int(get('payment_done', 0) or 0)
    today_str    = _today_ist().isoformat()

    created = get('created_at', '')
    days_in = 0
    if created:
        try:
            days_in = (_today_ist() - datetime.datetime.strptime(created[:10], '%Y-%m-%d').date()).days
        except Exception:
            pass

    expiry_str = get('seat_hold_expiry', '')
    expiry_soon = False
    if expiry_str:
        try:
            expiry = datetime.datetime.strptime(expiry_str[:19], '%Y-%m-%d %H:%M:%S')
            hours  = (expiry - _now_ist().replace(tzinfo=None)).total_seconds() / 3600
            expiry_soon = hours < 24
        except Exception:
            pass

    d1_done = int(get('d1_morning', 0) or 0) + int(get('d1_afternoon', 0) or 0) + int(get('d1_evening', 0) or 0)

    if stage == 'seat_hold' and expiry_soon:
        return f"\u26a0\ufe0f {name}'s seat hold expires soon \u2014 final call today is a must!"
    if stage == 'day1' and d1_done == 3:
        return f"\u2705 All batches complete! Move {name} to Day 2 now."
    if stage == 'enrollment' and heat >= 75:
        return f"\U0001f525 {name} looks very interested \u2014 try to convert today."
    if stage == 'enrollment' and call_status == 'Video Watched' and not payment_done:
        return f"\U0001f440 {name} has watched the video \u2014 make a strong payment call now."
    if stage == 'enrollment' and call_status == 'Payment Done':
        return f"\U0001f4b0 Payment confirmed! Move {name} to Day 1."
    if stage == 'enrollment' and days_in > 5 and heat < 30:
        return f"\u2744\ufe0f {name} has been stuck for {days_in}d and going cold \u2014 do a strong follow-up call."
    if stage == 'enrollment' and (not call_status or call_status == 'Not Called Yet'):
        return f"\U0001f4de {name} has not been called yet \u2014 contact today."
    if stage == 'day1' and d1_done < 3:
        return f"\u23f3 {name} has {d1_done}/3 batches done \u2014 remind for the rest."
    if stage == 'day2':
        return f"\U0001f393 {name} is in Day 2 \u2014 schedule interview with admin."
    if stage == 'day3':
        return f"\U0001f3c1 {name} is at interview stage \u2014 get track selected and confirm seat hold."
    if stage == 'seat_hold':
        return f"\U0001f6e1\ufe0f {name} is on seat hold \u2014 follow up for final payment."
    if heat < 40 and days_in > 3:
        return f"\u2744\ufe0f {name} inactive for {days_in}d \u2014 call once and update status."
    return f"\U0001f4cb Maintain regular follow up with {name}."


def _enrich_lead(lead):
    """Add heat, next_action, next_action_type to a lead. Returns a dict."""
    d  = dict(lead)
    for k in ('day1_batch', 'day2_batch', 'day3_batch',
              'heat', 'next_action', 'next_action_type'):
        d.setdefault(k, '' if 'batch' in k else 0 if k == 'heat' else '')
    for k in ('created_at', 'updated_at', 'claimed_at', 'follow_up_date'):
        if d.get(k) is None:
            d[k] = ''
    try:
        na = _get_next_action(lead)
        d['heat']             = _calculate_heat_score(lead)
        d['next_action']      = na['action']
        d['next_action_type'] = na['type']
    except Exception:
        d['heat']             = 0
        d['next_action']      = ''
        d['next_action_type'] = 'cold'
    return d


def _enrich_leads(lead_list, db=None):
    """Enrich leads with heat, next_action, and assignee_display (from users via FK).
    Pass an existing `db` to avoid opening a new connection."""
    rows = [_enrich_lead(l) for l in lead_list]
    ids = set()
    for d in rows:
        aid = d.get('assigned_user_id')
        if aid is not None:
            try:
                ids.add(int(aid))
            except (TypeError, ValueError):
                pass
    if not ids:
        for d in rows:
            d.setdefault('assignee_display', '—')
            d.setdefault('assignee_username', '')
        return rows

    _close = False
    if db is None:
        from database import get_db
        db = get_db()
        _close = True
    try:
        ph = ','.join('?' * len(ids))
        q = (
            f'SELECT id, username, '
            f"COALESCE(NULLIF(TRIM(name), ''), username) AS display_name FROM users WHERE id IN ({ph})"
        )
        id_map = {}
        for r in db.execute(q, tuple(ids)).fetchall():
            id_map[int(r['id'])] = (r['username'] or '', r['display_name'] or r['username'] or '')
    finally:
        if _close:
            db.close()
    for d in rows:
        aid = d.get('assigned_user_id')
        try:
            i = int(aid) if aid is not None else None
        except (TypeError, ValueError):
            i = None
        if i is not None and i in id_map:
            u, dn = id_map[i]
            d['assignee_username'] = u
            d['assignee_display'] = dn or u or '—'
        else:
            d['assignee_username'] = ''
            d['assignee_display'] = '—'
    return rows


# ─────────────────────────────────────────────────────────────────────────────
#  Pipeline transition helpers
# ─────────────────────────────────────────────────────────────────────────────

def _transition_stage(db, lead_id, new_stage, triggered_by, status_override=None):
    """
    Move a lead to a new pipeline stage while preserving the permanent buyer owner.
    `current_owner` remains the original claimer/buyer for the life of the lead.
    Returns (new_stage, new_owner).
    """
    lead = db.execute("SELECT * FROM leads WHERE id=?", (lead_id,)).fetchone()
    if not lead:
        return new_stage, ''

    lead_keys = lead.keys()
    current_owner = lead['current_owner'] if 'current_owner' in lead_keys else ''
    claimed_at = (lead['claimed_at'] if 'claimed_at' in lead_keys else '') or ''
    assignee_un = (_assignee_username_for_lead(db, lead) or '').strip()
    if (current_owner or '').strip():
        new_owner = current_owner
    elif str(claimed_at).strip():
        new_owner = ''
    else:
        new_owner = assignee_un or _get_admin_username(db)

    new_status = status_override if status_override is not None else STAGE_TO_DEFAULT_STATUS.get(new_stage)
    now_str = _now_ist().strftime('%Y-%m-%d %H:%M:%S')

    # Reset pipeline_entered_at on every stage change for auto-expirable statuses
    effective_status = new_status if new_status is not None else STAGE_TO_DEFAULT_STATUS.get(new_stage)
    entering_active_pipeline = effective_status in PIPELINE_AUTO_EXPIRE_STATUSES
    new_pipeline_entered_at = now_str if entering_active_pipeline else ''

    if new_status is not None:
        if new_owner:
            db.execute(
                "UPDATE leads SET pipeline_stage=?, current_owner=?, status=?, updated_at=?, pipeline_entered_at=? WHERE id=?",
                (new_stage, new_owner, new_status, now_str, new_pipeline_entered_at, lead_id)
            )
        else:
            db.execute(
                "UPDATE leads SET pipeline_stage=?, status=?, updated_at=?, pipeline_entered_at=? WHERE id=?",
                (new_stage, new_status, now_str, new_pipeline_entered_at, lead_id)
            )
    else:
        if new_owner:
            db.execute(
                "UPDATE leads SET pipeline_stage=?, current_owner=?, updated_at=?, pipeline_entered_at=? WHERE id=?",
                (new_stage, new_owner, now_str, new_pipeline_entered_at, lead_id)
            )
        else:
            db.execute(
                "UPDATE leads SET pipeline_stage=?, updated_at=?, pipeline_entered_at=? WHERE id=?",
                (new_stage, now_str, new_pipeline_entered_at, lead_id)
            )

    db.execute(
        "INSERT INTO lead_stage_history (lead_id, stage, owner, triggered_by, created_at) VALUES (?,?,?,?,?)",
        (lead_id, new_stage, new_owner, triggered_by, now_str)
    )

    if new_stage == 'training':
        _trigger_training_unlock(db, lead)

    db.commit()
    return new_stage, new_owner


def _trigger_training_unlock(db, lead):
    """When a lead reaches the training stage, unlock the assigned user training."""
    phone = lead['phone'] if 'phone' in lead.keys() else ''
    clean = _re.sub(r'[^0-9]', '', phone)
    if clean.startswith('91') and len(clean) == 12:
        clean = clean[2:]
    if not clean:
        return
    user_row = db.execute("""
        SELECT * FROM users WHERE
        REPLACE(REPLACE(REPLACE(phone,'+91',''),'+',''),' ','') = ?
        OR REPLACE(REPLACE(phone,'+91',''),' ','') = ?
    """, (clean, clean)).fetchone()
    if user_row and user_row['training_status'] != 'completed':
        db.execute(
            "UPDATE users SET training_status='pending' WHERE username=?",
            (user_row['username'],)
        )
        # Push notification — late import to avoid circular dependency
        try:
            from app import _push_to_users
            _push_to_users(db, user_row['username'],
                           'Training Ready!',
                           'Start 7-day training. You will get a certificate!',
                           '/training')
        except Exception:
            pass
        _log_activity(db, user_row['username'], 'training_unlocked',
                      f'Lead #{lead["id"]} transitioned to training')


def _auto_expire_pipeline_leads(db, username):
    """
    Move leads to Inactive if they've been in an active pipeline stage for 24+ hours.
    Uses COALESCE(pipeline_entered_at, updated_at) so old leads without pipeline_entered_at
    are also caught by their last updated_at timestamp.
    Runs on dashboard load for the given user's assigned leads.
    """
    from datetime import timedelta
    _uid = user_id_for_username(db, username)
    if _uid is None:
        return 0
    cutoff = (_now_ist() - timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')
    placeholders = ','.join('?' * len(PIPELINE_AUTO_EXPIRE_STATUSES))
    expired = db.execute(f"""
        SELECT id, name FROM leads
        WHERE assigned_user_id=? AND in_pool=0 AND deleted_at=''
        AND status IN ({placeholders})
        AND COALESCE(NULLIF(TRIM(pipeline_entered_at),''), updated_at) < ?
    """, (_uid, *PIPELINE_AUTO_EXPIRE_STATUSES, cutoff)).fetchall()

    now_str = _now_ist().strftime('%Y-%m-%d %H:%M:%S')
    for lead in expired:
        db.execute("""
            UPDATE leads SET status='Inactive', pipeline_stage='inactive', updated_at=?
            WHERE id=?
        """, (now_str, lead['id']))
        _log_activity(db, 'system', 'pipeline_expired',
                      f'Lead #{lead["id"]} ({lead["name"]}) auto-moved to Inactive after 24hr inactivity')
    if expired:
        db.commit()
    return len(expired)


def _auto_expire_pipeline_leads_batch(db, usernames):
    """Batch variant: expire stale pipeline leads for multiple usernames in ONE query."""
    from datetime import timedelta
    uid_map = user_ids_for_usernames(db, usernames)
    uids = list(uid_map.values())
    if not uids:
        return 0
    cutoff = (_now_ist() - timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')
    s_ph = ','.join('?' * len(PIPELINE_AUTO_EXPIRE_STATUSES))
    u_ph = ','.join('?' * len(uids))
    expired = db.execute(f"""
        SELECT id, name FROM leads
        WHERE assigned_user_id IN ({u_ph}) AND in_pool=0 AND deleted_at=''
        AND status IN ({s_ph})
        AND COALESCE(NULLIF(TRIM(pipeline_entered_at),''), updated_at) < ?
    """, (*uids, *PIPELINE_AUTO_EXPIRE_STATUSES, cutoff)).fetchall()

    now_str = _now_ist().strftime('%Y-%m-%d %H:%M:%S')
    for lead in expired:
        db.execute("""
            UPDATE leads SET status='Inactive', pipeline_stage='inactive', updated_at=?
            WHERE id=?
        """, (now_str, lead['id']))
        _log_activity(db, 'system', 'pipeline_expired',
                      f'Lead #{lead["id"]} ({lead["name"]}) auto-moved to Inactive after 24hr inactivity')
    if expired:
        db.commit()
    return len(expired)


def _expire_all_pipeline_leads(db):
    """
    Global pipeline expiry — same logic as job_pipeline_expire but uses the
    supplied db connection (no new connection opened).  Call this inline when
    the admin or leader workboard loads so stale leads are cleaned BEFORE the
    Day-1/2/3 queries run.
    """
    from datetime import timedelta
    cutoff = (_now_ist() - timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')
    placeholders = ','.join('?' * len(PIPELINE_AUTO_EXPIRE_STATUSES))
    expired = db.execute(f"""
        SELECT l.id, l.name, COALESCE(u.username, '') AS assignee_username
        FROM leads l
        LEFT JOIN users u ON u.id = l.assigned_user_id
        WHERE l.in_pool=0 AND l.deleted_at=''
        AND l.status IN ({placeholders})
        AND COALESCE(NULLIF(TRIM(l.pipeline_entered_at),''), l.updated_at) < ?
    """, (*PIPELINE_AUTO_EXPIRE_STATUSES, cutoff)).fetchall()

    now_str = _now_ist().strftime('%Y-%m-%d %H:%M:%S')
    count = 0
    for lead in expired:
        db.execute("""
            UPDATE leads SET status='Inactive', pipeline_stage='inactive', updated_at=?
            WHERE id=?
        """, (now_str, lead['id']))
        _log_activity(db, 'system', 'pipeline_expired',
                      f'Lead #{lead["id"]} ({lead["name"]}) → Inactive '
                      f'after 24h at stage (owner: {lead["assignee_username"]})')
        count += 1
    if count:
        db.commit()
    return count


def _penalize_missed_followups(db, username):
    """
    Check if the user has follow-ups that are overdue by 2+ hours and haven't been completed.
    Applies -10 points and clears the follow-up so they aren't penalized twice.
    Team members are exempt — they do not manage follow-ups.
    """
    _uid = user_id_for_username(db, username)
    if _uid is None:
        return
    role_row = db.execute("SELECT role FROM users WHERE username=?", (username,)).fetchone()
    _role = ((role_row['role'] if role_row else '') or '').strip()
    if _role in ('team', 'admin'):
        return
    now = _now_ist().replace(tzinfo=None)
    rows = db.execute(
        "SELECT id, follow_up_date, follow_up_time, name FROM leads "
        "WHERE assigned_user_id=? AND in_pool=0 AND deleted_at='' AND follow_up_date != '' AND follow_up_time != '' "
        "AND status NOT IN ('Lost','Retarget','Inactive','Converted','Fully Converted')",
        (_uid,),
    ).fetchall()

    try:
        from services.scoring_service import apply_penalty
        
        penalized_count = 0
        for row in rows:
            dt_str = f"{row['follow_up_date'][:10]} {row['follow_up_time']}"
            try:
                fu_time = datetime.datetime.strptime(dt_str, '%Y-%m-%d %H:%M')
                if (now - fu_time).total_seconds() > 7200: # 2 hours overdue
                     # Clear follow up and penalize
                     _cl = now.strftime('%Y-%m-%d %H:%M:%S')
                     db.execute(
                         "UPDATE leads SET follow_up_date='', follow_up_time='', updated_at=? WHERE id=?",
                         (_cl, row['id']),
                     )
                     apply_penalty(username, 'FOLLOWUP_MISSED', f"Missed scheduled follow-up for lead #{row['id']}")
                     penalized_count += 1
            except Exception:
                pass
        if penalized_count > 0:
            db.commit()
    except Exception:
        pass


def _check_seat_hold_expiry(db, username):
    """Revert expired seat_hold leads back to day3 stage."""
    now_str = _now_ist().strftime('%Y-%m-%d %H:%M:%S')
    uid = user_id_for_username(db, username)
    if uid is None:
        return
    expired = db.execute("""
        SELECT * FROM leads
        WHERE assigned_user_id=? AND pipeline_stage='seat_hold'
        AND in_pool=0 AND deleted_at=''
        AND seat_hold_expiry != '' AND seat_hold_expiry < ?
    """, (uid, now_str)).fetchall()
    for lead in expired:
        _transition_stage(db, lead['id'], 'day3', 'system_expiry')
        _log_activity(db, 'system', 'seat_hold_expired',
                      f'Lead #{lead["id"]} seat hold expired')


# ─────────────────────────────────────────────────────────────────────────────
#  Badge system
# ─────────────────────────────────────────────────────────────────────────────

def _check_and_award_badges(db, username):
    """Check badge conditions and award new ones. Returns list of new badge keys."""
    try:
        return _check_and_award_badges_inner(db, username)
    except Exception:
        return []


def _check_and_award_badges_inner(db, username):
    new_badges = []
    _buid = user_id_for_username(db, username)
    if _buid is None:
        return []
    today  = _today_ist().strftime('%Y-%m-%d')
    mon    = (_today_ist() - datetime.timedelta(days=_today_ist().weekday())).strftime('%Y-%m-%d')

    def _already_has(key):
        return db.execute(
            "SELECT 1 FROM user_badges WHERE username=? AND badge_key=?", (username, key)
        ).fetchone() is not None

    def _award(key):
        db.execute(
            "INSERT OR IGNORE INTO user_badges (username, badge_key) VALUES (?,?)",
            (username, key)
        )
        new_badges.append(key)

    # hot_streak: 7+ consecutive active days
    streak_row = db.execute(
        "SELECT streak_days FROM daily_scores WHERE username=? AND score_date=?",
        (username, today)
    ).fetchone()
    if streak_row and (streak_row['streak_days'] or 0) >= 7 and not _already_has('hot_streak'):
        _award('hot_streak')

    # speed_closer
    if not _already_has('speed_closer'):
        fast = db.execute("""
            SELECT COUNT(*) as cnt FROM leads
            WHERE assigned_user_id=? AND in_pool=0
              AND pipeline_stage IN ('day1','day2','day3','seat_hold','closing','complete')
              AND claimed_at IS NOT NULL
              AND julianday(datetime(working_date)) - julianday(datetime(claimed_at)) <= 3
        """, (_buid,)).fetchone()
        if fast and (fast['cnt'] or 0) > 0:
            _award('speed_closer')

    # money_maker: 5+ payments
    payments = db.execute(
        "SELECT COUNT(*) as cnt FROM leads WHERE assigned_user_id=? AND payment_done=1 AND in_pool=0 AND deleted_at=''",
        (_buid,),
    ).fetchone()
    if payments and (payments['cnt'] or 0) >= 5 and not _already_has('money_maker'):
        _award('money_maker')

    # first_convert
    if not _already_has('first_convert'):
        conv = db.execute(
            "SELECT COUNT(*) as cnt FROM leads WHERE assigned_user_id=? AND status IN ('Converted','Fully Converted') AND in_pool=0",
            (_buid,),
        ).fetchone()
        if conv and (conv['cnt'] or 0) > 0:
            _award('first_convert')

    # centurion: 10000+ total points
    pts = db.execute(
        "SELECT COALESCE(SUM(total_points),0) as p FROM daily_scores WHERE username=?",
        (username,)
    ).fetchone()
    if pts and (pts['p'] or 0) >= 10000 and not _already_has('centurion'):
        _award('centurion')

    # batch_master: 100+ batches marked
    batches = db.execute(
        "SELECT COALESCE(SUM(batches_marked),0) as b FROM daily_scores WHERE username=?",
        (username,)
    ).fetchone()
    if batches and (batches['b'] or 0) >= 100 and not _already_has('batch_master'):
        _award('batch_master')

    # rising_star: top scorer this week
    if not _already_has('rising_star'):
        top = db.execute("""
            SELECT username, SUM(total_points) as wpts
            FROM daily_scores WHERE score_date >= ?
            GROUP BY username ORDER BY wpts DESC LIMIT 1
        """, (mon,)).fetchone()
        if top and top['username'] == username:
            _award('rising_star')

    return new_badges


def _get_user_badges_emoji(db, username):
    """Return a space-joined emoji string for user's badges."""
    rows = db.execute(
        "SELECT badge_key FROM user_badges WHERE username=?", (username,)
    ).fetchall()
    return ' '.join(BADGE_META[r['badge_key']][0] for r in rows if r['badge_key'] in BADGE_META)


# ─────────────────────────────────────────────────────────────────────────────
#  Daily scores
# ─────────────────────────────────────────────────────────────────────────────

def _upsert_daily_score(db, username, delta_pts,
                        delta_calls=0, delta_videos=0,
                        delta_batches=0, delta_payments=0):
    """Atomically add to today's daily_scores row, creating it if needed."""
    today     = _today_ist().strftime('%Y-%m-%d')
    yesterday = (_today_ist() - datetime.timedelta(days=1)).strftime('%Y-%m-%d')
    existing  = db.execute(
        "SELECT id FROM daily_scores WHERE username=? AND score_date=?",
        (username, today)
    ).fetchone()
    if existing:
        db.execute("""
            UPDATE daily_scores SET
                total_points       = CASE WHEN total_points + ? < 0 THEN 0 ELSE total_points + ? END,
                calls_made         = CASE WHEN calls_made + ? < 0 THEN 0 ELSE calls_made + ? END,
                videos_sent        = CASE WHEN videos_sent + ? < 0 THEN 0 ELSE videos_sent + ? END,
                batches_marked     = CASE WHEN batches_marked + ? < 0 THEN 0 ELSE batches_marked + ? END,
                payments_collected = CASE WHEN payments_collected + ? < 0 THEN 0 ELSE payments_collected + ? END
            WHERE username=? AND score_date=?
        """, (delta_pts, delta_pts,
              delta_calls, delta_calls,
              delta_videos, delta_videos,
              delta_batches, delta_batches,
              delta_payments, delta_payments,
              username, today))
        # Sync to users table (global total)
        db.execute("""
            UPDATE users SET 
                total_points = CASE WHEN total_points + ? < 0 THEN 0 ELSE total_points + ? END 
            WHERE LOWER(username) = LOWER(?)
        """, (delta_pts, delta_pts, username))
    else:
        yrow = db.execute(
            "SELECT streak_days FROM daily_scores WHERE username=? AND score_date=?",
            (username, yesterday)
        ).fetchone()
        streak       = (yrow['streak_days'] + 1) if yrow else 1
        streak_bonus = 10 if yrow else 0
        db.execute("""
            INSERT OR REPLACE INTO daily_scores
                (username, score_date, calls_made, videos_sent,
                 batches_marked, payments_collected, total_points, streak_days)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (username, today,
              max(0, delta_calls), max(0, delta_videos),
              max(0, delta_batches), max(0, delta_payments),
              max(0, delta_pts + streak_bonus), streak))
        # Sync to users table (global total)
        db.execute("""
            UPDATE users SET 
                total_points = CASE WHEN total_points + ? < 0 THEN 0 ELSE total_points + ? END 
            WHERE LOWER(username) = LOWER(?)
        """, (delta_pts + streak_bonus, delta_pts + streak_bonus, username))


def _get_today_score(db, username):
    """Return (total_points, streak_days) for today. 0,1 if no row."""
    today = _today_ist().strftime('%Y-%m-%d')
    row   = db.execute(
        "SELECT total_points, streak_days FROM daily_scores WHERE username=? AND score_date=?",
        (username, today)
    ).fetchone()
    if row:
        return row['total_points'], row['streak_days']
    return 0, 1


_PICKED_STATUSES     = frozenset({'Called - Interested', 'Called - Not Interested',
                                   'Called - Follow Up', 'Call Back'})
_NOT_PICKED_STATUSES = frozenset({'Called - No Answer', 'Called - Switch Off',
                                   'Called - Busy'})
_WRONG_NUMBER        = frozenset({'Wrong Number'})
_ALL_CALLING_REPORT  = _PICKED_STATUSES | _NOT_PICKED_STATUSES | _WRONG_NUMBER
_LEAD_ID_RE_REPORT   = _re.compile(r'Lead #(\d+)')
_STATUS_RE_REPORT    = _re.compile(r'call_status=(.+)$')


def _get_actual_daily_counts(db, username, date=None):
    """
    Returns system-verified counts for a given date (default today).
    Computed directly from activity_log + leads table — tamper-proof.
    """
    if date is None:
        date = _today_ist().strftime('%Y-%m-%d')

    # ── Parse call_status_update events from activity_log ──────────────
    log_rows = db.execute("""
        SELECT details FROM activity_log
        WHERE  username=? AND event_type='call_status_update'
               AND DATE(created_at)=?
        ORDER  BY created_at ASC
    """, (username, date)).fetchall()

    # Last status per lead wins (handles re-updates same day)
    lead_last_status: dict[int, str] = {}
    for row in log_rows:
        details = row['details'] or ''
        m_id     = _LEAD_ID_RE_REPORT.search(details)
        m_status = _STATUS_RE_REPORT.search(details)
        if not m_id or not m_status:
            continue
        lead_last_status[int(m_id.group(1))] = m_status.group(1).strip()

    # Categorise by last-known status of each lead on that day
    called_leads       = set()
    picked_leads       = set()
    not_picked_leads   = set()
    wrong_number_leads = set()
    payment_leads      = set()

    for lead_id, status in lead_last_status.items():
        if status in _ALL_CALLING_REPORT:
            called_leads.add(lead_id)
        if status in _PICKED_STATUSES:
            picked_leads.add(lead_id)
        elif status in _NOT_PICKED_STATUSES:
            not_picked_leads.add(lead_id)
        elif status in _WRONG_NUMBER:
            wrong_number_leads.add(lead_id)
        if status == 'Payment Done':
            payment_leads.add(lead_id)

    # ── Leads claimed from pool on this date ───────────────────────────
    _cuid = user_id_for_username(db, username)
    if _cuid is not None:
        leads_claimed_row = db.execute("""
            SELECT COUNT(*) FROM leads
            WHERE  assigned_user_id=? AND DATE(claimed_at)=?
                   AND in_pool=0 AND deleted_at=''
        """, (_cuid, date)).fetchone()
        leads_claimed = leads_claimed_row[0] if leads_claimed_row else 0
    else:
        leads_claimed = 0

    # ── Enrollments: also check daily_scores as fallback ───────────────
    score_row = db.execute(
        "SELECT payments_collected FROM daily_scores WHERE username=? AND score_date=?",
        (username, date)
    ).fetchone()
    payments_from_scores = (score_row['payments_collected'] if score_row else 0) or 0
    enrollments = max(len(payment_leads), payments_from_scores)

    return {
        'total_calling':    len(called_leads),
        'calls_picked':     len(picked_leads),
        'not_picked':       len(not_picked_leads),
        'wrong_numbers':    len(wrong_number_leads),
        'leads_claimed':    leads_claimed,
        'enrollments_done': enrollments,
    }


# ─────────────────────────────────────────────────────────────────────────────
#  Step 6 — Admin decision engine (IST, one class per user, no circular rules)
# ─────────────────────────────────────────────────────────────────────────────

ADMIN_DECISION_WINDOW_DAYS = 3
ADMIN_DECISION_CALLS_AVG_WARN = 10
ADMIN_DECISION_CALLS_AVG_TOP = 15
ADMIN_DECISION_INACTIVITY_TOP_H = 24.0
ADMIN_DECISION_INACTIVITY_CRITICAL_H = 48.0
ADMIN_DECISION_INACTIVITY_REMOVE_H = 72.0
ADMIN_DECISION_LOW_PERF_REMOVE = 3
ADMIN_DECISION_LOW_PERF_CRITICAL = 2
ADMIN_DECISION_LOW_EFFORT_CRITICAL = 2


def admin_decision_followups_done_window(db, username: str, start_d: str, end_d: str) -> int:
    """Distinct leads with follow-up-related notes in rolling window (last_3_days, IST)."""
    row = db.execute(
        """
        SELECT COUNT(DISTINCT lead_id) AS c FROM lead_notes
        WHERE username=?
          AND date(substr(trim(created_at), 1, 10)) >= date(?)
          AND date(substr(trim(created_at), 1, 10)) <= date(?)
          AND (
            lower(note) LIKE '%follow-up%' OR lower(note) LIKE '%follow up%'
            OR lower(note) LIKE '%followup%' OR lower(note) LIKE '%fu %'
          )
        """,
        (username, start_d, end_d),
    ).fetchone()
    return int(row['c'] or 0) if row else 0


def admin_decision_missed_followups_total(
    db, username: str, today_d: str, window_start_d: str,
) -> int:
    """Backlog overdue FU + miss notes in window (history separate from today snapshot)."""
    _muid = user_id_for_username(db, username)
    overdue = (
        db.execute(
            """
            SELECT COUNT(*) AS c FROM leads
            WHERE assigned_user_id=? AND in_pool=0 AND deleted_at=''
              AND status NOT IN ('Converted','Lost','Fully Converted','Retarget')
              AND follow_up_date IS NOT NULL AND TRIM(COALESCE(follow_up_date,''))!=''
              AND date(substr(trim(follow_up_date), 1, 10)) < date(?)
            """,
            (_muid, today_d),
        ).fetchone()
        if _muid is not None
        else None
    )
    o = int(overdue['c'] or 0) if overdue else 0
    notes = db.execute(
        """
        SELECT COUNT(*) AS c FROM lead_notes
        WHERE username=?
          AND date(substr(trim(created_at), 1, 10)) >= date(?)
          AND date(substr(trim(created_at), 1, 10)) <= date(?)
          AND (note LIKE '%Missed Follow%' OR lower(note) LIKE '%missed follow%')
        """,
        (username, window_start_d, today_d),
    ).fetchone()
    n = int(notes['c'] or 0) if notes else 0
    return o + n


def compute_admin_decision_metrics(db, username: str) -> dict:
    """
    Rolling last_3_days (IST inclusive) for averages; today_calls is live (today only).
    """
    today_d = _today_ist().isoformat()
    start_w = (_today_ist() - datetime.timedelta(days=ADMIN_DECISION_WINDOW_DAYS - 1)).isoformat()
    per_day_calls: List[int] = []
    for i in range(ADMIN_DECISION_WINDOW_DAYS):
        d = (_today_ist() - datetime.timedelta(days=i)).isoformat()
        per_day_calls.append(count_distinct_valid_calls_on_date(db, username, d))
    calls_avg = sum(per_day_calls) / float(ADMIN_DECISION_WINDOW_DAYS)
    today_calls = per_day_calls[0]

    followups_done = admin_decision_followups_done_window(db, username, start_w, today_d)
    missed_followups = admin_decision_missed_followups_total(db, username, today_d, start_w)

    process_inactivity_escalation(db, username)
    inh = float(user_inactivity_hours(db, username))
    inactivity_escalation_day_index = 0
    if inh >= float(INACTIVITY_LOCK_HOURS):
        _srow = db.execute(
            "SELECT inactivity_72h_start_date FROM users WHERE username=?",
            (username,),
        ).fetchone()
        _s = _user_row_safe(_srow, 'inactivity_72h_start_date', '').strip()[:10]
        if len(_s) >= 10:
            try:
                inactivity_escalation_day_index = max(
                    0, (_today_ist() - datetime.date.fromisoformat(_s)).days
                )
            except ValueError:
                inactivity_escalation_day_index = 0

    urow = db.execute(
        """
        SELECT discipline_status, grace_return_date, access_blocked,
               low_performance_days, low_effort_days, status
        FROM users WHERE username=?
        """,
        (username,),
    ).fetchone()
    ds = _user_row_safe(urow, 'discipline_status', '').strip()
    grace_until = _user_row_safe(urow, 'grace_return_date', '').strip()[:10]
    access_blocked = int(_user_row_safe(urow, 'access_blocked', 0) or 0)
    low_pd = int(_user_row_safe(urow, 'low_performance_days', 0) or 0)
    low_eff = int(_user_row_safe(urow, 'low_effort_days', 0) or 0)

    in_grace = user_in_active_grace(urow, today_d)
    claimed_before = bool(
        db.execute(
            "SELECT 1 FROM activity_log WHERE username=? AND event_type='lead_claim' LIMIT 1",
            (username,),
        ).fetchone()
    )
    assigned_total = count_assigned_leads_total(db, username)

    return {
        'username': username,
        'calls_avg': round(calls_avg, 2),
        'today_calls': today_calls,
        'calls_last_3_days': per_day_calls,
        'followups_done': followups_done,
        'missed_followups': missed_followups,
        'inactivity_hours': round(inh, 2),
        'inactivity_escalation_days': inactivity_escalation_day_index,
        'low_performance_days': low_pd,
        'low_effort_days': low_eff,
        'discipline_status': ds,
        'grace_until': grace_until,
        'access_blocked': access_blocked,
        'in_grace': in_grace,
        'claimed_before': claimed_before,
        'assigned_total': assigned_total,
        'window_start': start_w,
        'window_end': today_d,
    }


def classify_admin_decision(m: dict) -> Tuple[str, str]:
    """
    Single pass, first match wins. Returns (class, admin one-line detail).
    Classes: grace, new_idle, remove, critical, warning, top, good
    """
    calls_avg = float(m['calls_avg'])
    today_calls = int(m['today_calls'])
    fu = int(m['followups_done'])
    missed = int(m['missed_followups'])
    inh = float(m['inactivity_hours'])
    low_pd = int(m['low_performance_days'])
    low_eff = int(m['low_effort_days'])
    ds = (m.get('discipline_status') or '').strip()
    grace_until = m.get('grace_until') or ''
    blocked = int(m.get('access_blocked') or 0)
    claimed = bool(m.get('claimed_before'))
    assigned = int(m.get('assigned_total') or 0)
    in_grace = bool(m.get('in_grace'))
    esc_days = int(m.get('inactivity_escalation_days') or 0)

    is_removed = ds == 'removed' or blocked != 0

    if in_grace:
        return 'grace', f'Grace till {grace_until}' if grace_until else 'Grace active'

    if (assigned == 0 and not claimed) or (assigned == 0 and inh >= ADMIN_DECISION_INACTIVITY_CRITICAL_H):
        return 'new_idle', (
            f'0 leads; inactive {inh:.0f}h' if assigned == 0 and inh >= ADMIN_DECISION_INACTIVITY_CRITICAL_H
            else 'Not started / no claims yet'
        )

    if is_removed or low_pd >= ADMIN_DECISION_LOW_PERF_REMOVE:
        parts = []
        if is_removed:
            parts.append('removed / blocked')
        if low_pd >= ADMIN_DECISION_LOW_PERF_REMOVE:
            parts.append(f'low calls streak {low_pd}d')
        return 'remove', '; '.join(parts)

    # Step 1.1 — 72h+ work inactivity, 3rd IST calendar day since first flag → REMOVE (Step 7 applies)
    if (
        inh >= ADMIN_DECISION_INACTIVITY_REMOVE_H
        and esc_days >= 2
        and assigned > 0
    ):
        return (
            'remove',
            f'inactive {inh:.0f}h — Step 1.1 day {esc_days + 1}; no work after final warning',
        )

    if (
        inh >= ADMIN_DECISION_INACTIVITY_CRITICAL_H
        or low_pd >= ADMIN_DECISION_LOW_PERF_CRITICAL
        or low_eff >= ADMIN_DECISION_LOW_EFFORT_CRITICAL
    ):
        parts = []
        if inh >= ADMIN_DECISION_INACTIVITY_CRITICAL_H:
            parts.append(f'inactive {inh:.0f}h')
        if low_pd >= ADMIN_DECISION_LOW_PERF_CRITICAL:
            parts.append(f'low perf {low_pd}d')
        if low_eff >= ADMIN_DECISION_LOW_EFFORT_CRITICAL:
            parts.append(f'low effort {low_eff}d')
        return 'critical', '; '.join(parts)

    if calls_avg < ADMIN_DECISION_CALLS_AVG_WARN or missed > 0:
        parts = []
        if calls_avg < ADMIN_DECISION_CALLS_AVG_WARN:
            parts.append(f'avg {calls_avg:.1f} calls/day')
        if missed > 0:
            parts.append(f'missed / overdue FU ({missed})')
        return 'warning', '; '.join(parts)

    if (
        calls_avg >= ADMIN_DECISION_CALLS_AVG_TOP
        and fu > 0
        and inh < ADMIN_DECISION_INACTIVITY_TOP_H
    ):
        return 'top', f'avg {calls_avg:.1f}/day, today {today_calls}, FU notes {fu}'

    if calls_avg >= ADMIN_DECISION_CALLS_AVG_WARN:
        return 'good', f'avg {calls_avg:.1f}/day, today {today_calls}'

    return 'warning', f'avg {calls_avg:.1f}/day (review)'


def build_admin_decision_report(db) -> Dict[str, List[dict]]:
    """One classification per approved team/leader; buckets for admin UI."""
    rows = db.execute(
        """
        SELECT username FROM users
        WHERE role IN ('team','leader') AND status='approved'
        ORDER BY username
        """
    ).fetchall()
    buckets: dict[str, List[dict]] = {
        'top': [],
        'good': [],
        'warning': [],
        'critical': [],
        'remove': [],
        'grace': [],
        'new_idle': [],
    }
    for r in rows:
        uname = r['username']
        m = compute_admin_decision_metrics(db, uname)
        cls, detail = classify_admin_decision(m)
        entry = {**m, 'decision_class': cls, 'detail': detail}
        if cls in buckets:
            buckets[cls].append(entry)
    return buckets


def admin_decision_action_hint(decision_class: str) -> str:
    hints = {
        'top': 'Reward / highlight',
        'good': 'Keep',
        'warning': 'Push / monitor',
        'critical': 'Final warning',
        'remove': 'Remove from group / access',
        'grace': 'Ignore temporarily (discipline gates relaxed)',
        'new_idle': 'Onboard or wait — not a performance fail',
    }
    return hints.get(decision_class, '')


def log_system_auto_action(db, event_type: str, target_username: str = '', reason: str = '') -> None:
    """Step 7 Rule 9 — audit trail for automated discipline (no secrets in reason)."""
    now_s = _now_ist().strftime('%Y-%m-%d %H:%M:%S')
    db.execute(
        """
        INSERT INTO system_auto_actions (event_type, target_username, reason, created_at)
        VALUES (?,?,?,?)
        """,
        (event_type, target_username or '', (reason or '')[:2000], now_s),
    )


def build_step7_pressure_digest(buckets: Dict[str, List[dict]], today_str: str) -> dict:
    """Rule 3 — nightly pressure copy for admin + optional broadcasts."""
    top_rows = buckets.get('top') or []
    parts = [f"{x['username']} ({int(x.get('today_calls', 0))} calls)" for x in top_rows]
    top_line = 'Top performers today: ' + ', '.join(parts) if parts else 'Top performers today: —'
    return {
        'date': today_str,
        'lines': {
            'top': top_line,
            'good': 'Consistent work — maintain pace' if (buckets.get('good') or []) else '',
            'warning': 'Below target — improve tomorrow' if (buckets.get('warning') or []) else '',
            'critical': 'Final warning — fix within 24 hours' if (buckets.get('critical') or []) else '',
            'remove': 'Removed due to non-performance' if (buckets.get('remove') or []) else '',
        },
        'counts': {k: len(v) for k, v in buckets.items()},
    }


def step7_apply_idle_hidden_flags(db) -> None:
    """
    Rule 4 — no leads, no pool claim history, inactive 24h+ → hide from leaderboards / pulse (no penalty).
    """
    rows = db.execute(
        "SELECT username FROM users WHERE role IN ('team','leader') AND status='approved'"
    ).fetchall()
    for r in rows:
        uname = r['username']
        assigned = count_assigned_leads_total(db, uname)
        claimed = db.execute(
            "SELECT 1 FROM activity_log WHERE username=? AND event_type='lead_claim' LIMIT 1",
            (uname,),
        ).fetchone()
        inh = float(user_inactivity_hours(db, uname))
        if assigned == 0 and (not claimed) and inh >= 24.0:
            db.execute("UPDATE users SET idle_hidden=1 WHERE username=?", (uname,))
        elif assigned > 0 or claimed:
            db.execute("UPDATE users SET idle_hidden=0 WHERE username=?", (uname,))


def reset_user_reentry_discipline(db, username: str) -> None:
    """Rule 5 — after admin brings user back from removal; treat as fresh for streaks."""
    db.execute(
        """
        UPDATE users SET low_performance_days=0, low_perf_tracked_date='',
            low_effort_days=0, low_effort_tracked_date='',
            final_warning_given=0,
            access_blocked=0, discipline_status='', idle_hidden=0,
            inactivity_72h_start_date=''
        WHERE username=?
        """,
        (username,),
    )


def admin_decision_semantic_color(decision_class: str) -> str:
    """Rule 6 — RAG + blue for grace / grey idle."""
    return {
        'remove': 'danger',
        'critical': 'warning',
        'warning': 'warning',
        'top': 'success',
        'good': 'success',
        'grace': 'info',
        'new_idle': 'secondary',
    }.get(decision_class, 'secondary')


# ─────────────────────────────────────────────────────────────────────────────
#  Step 8 — AI insights & appreciation (read-only, no DB writes)
#  Team coach uses ONLY: claimed_at, updated_at, call_status, follow_up_date, status
# ─────────────────────────────────────────────────────────────────────────────

STEP8_EXIT_STATUSES = frozenset({'Lost', 'Retarget', 'Converted', 'Fully Converted'})
STEP8_HOT_STATUSES = frozenset({'Video Sent', 'Video Watched', 'Paid ₹196'})
STEP8_FU_APPRECIATION_CS = frozenset({
    'Called - Follow Up', 'Video Sent', 'Video Watched', 'Payment Done', 'Call Back',
})
STEP8_CALLS_WARN_THRESHOLD = 10


def _step8_date_prefix(val: Optional[str]) -> str:
    s = (val or '').strip()
    return s[:10] if len(s) >= 10 else ''


def _step8_parse_ts(val: Optional[str]) -> Optional[datetime.datetime]:
    if not val:
        return None
    s = str(val).strip()
    if len(s) >= 19:
        try:
            return datetime.datetime.strptime(s[:19], '%Y-%m-%d %H:%M:%S')
        except ValueError:
            pass
    if len(s) >= 10:
        try:
            return datetime.datetime.strptime(s[:10], '%Y-%m-%d')
        except ValueError:
            pass
    return None


def _step8_valid_call(cs: Optional[str]) -> bool:
    x = (cs or '').strip()
    return bool(x and x != 'Not Called Yet')


def load_step8_insight_leads(db, username: str) -> List[Dict[str, str]]:
    """Fetch only Step-8–allowed columns for assigned non-pool leads."""
    _suid = user_id_for_username(db, username)
    if _suid is None:
        return []
    cur = db.execute(
        """
        SELECT claimed_at, updated_at, call_status, follow_up_date, status
        FROM leads
        WHERE assigned_user_id=? AND in_pool=0 AND deleted_at=''
        """,
        (_suid,),
    )
    return [dict(r) for r in cur.fetchall()]


def compute_step8_team_coach(
    rows: List[Dict[str, str]],
    today_iso: str,
    now_local: datetime.datetime,
    daily_call_target: int,
) -> Dict[str, object]:
    """
    Personal coach: next action, priority, appreciation, warnings.
    Pure function over lead rows (allowed columns only).
    """
    active = [r for r in rows if (r.get('status') or '') not in STEP8_EXIT_STATUSES]
    calls_today = sum(
        1
        for r in rows
        if _step8_date_prefix(r.get('updated_at')) == today_iso and _step8_valid_call(r.get('call_status'))
    )
    fu_due = 0
    fu_overdue = 0
    for r in active:
        fu = (r.get('follow_up_date') or '').strip()
        if len(fu) < 10:
            continue
        d = fu[:10]
        if d <= today_iso:
            fu_due += 1
        if d < today_iso:
            fu_overdue += 1

    hot = 0
    for r in active:
        cs = (r.get('call_status') or '').strip()
        st = (r.get('status') or '').strip()
        if cs in CALL_STATUS_INTERESTED_BUCKET or st in STEP8_HOT_STATUSES:
            hot += 1

    conversion_today = sum(
        1
        for r in rows
        if (r.get('status') or '') in ('Converted', 'Fully Converted')
        and _step8_date_prefix(r.get('updated_at')) == today_iso
    )

    followups_logged_today = sum(
        1
        for r in rows
        if _step8_date_prefix(r.get('updated_at')) == today_iso
        and (r.get('call_status') or '').strip() in STEP8_FU_APPRECIATION_CS
    )

    best_upd: Optional[datetime.datetime] = None
    for r in rows:
        t = _step8_parse_ts(r.get('updated_at'))
        if t and (best_upd is None or t > best_upd):
            best_upd = t

    idle_6h = False
    if active and best_upd is not None:
        idle_6h = (now_local - best_upd) >= datetime.timedelta(hours=6)

    # ── Next action (single highest-priority line) ─────────────────
    next_action = 'Keep the pipeline moving — prioritize follow-ups today.'
    if fu_due >= 1:
        next_action = f'{fu_due} follow-up(s) due — finish them first.'
    elif hot >= 2:
        next_action = f'{hot} hot leads — aim to close at least one today.'
    elif hot == 1:
        next_action = '1 hot lead — focus on closing today.'
    elif len(active) > 0 and calls_today < STEP8_CALLS_WARN_THRESHOLD:
        next_action = 'Pick up call pace — touch more new leads.'

    # ── Priority stack ─────────────────────────────────────────────
    pr_parts: List[str] = []
    if fu_due:
        pr_parts.append('Follow-up')
    if hot:
        pr_parts.append('Hot leads')
    pr_parts.append('New calls')
    seen = set()
    priority: List[str] = []
    for i, p in enumerate(pr_parts):
        if p in seen:
            continue
        seen.add(p)
        priority.append(f'{len(priority) + 1}. {p}')
        if len(priority) >= 3:
            break

    # ── Appreciation (max 3 one-liners) ────────────────────────────
    appreciation: List[str] = []
    tgt = int(daily_call_target or 0)
    if tgt > 0 and calls_today >= tgt:
        appreciation.append('🔥 Target hit — maintain momentum')
    if followups_logged_today > 0:
        appreciation.append('📞 Follow-ups strong — keep going')
    if conversion_today > 0:
        appreciation.append('💰 Conversion done — good execution')

    # ── Warnings ───────────────────────────────────────────────────
    warnings: List[str] = []
    if len(active) > 0 and calls_today < STEP8_CALLS_WARN_THRESHOLD:
        warnings.append('⚠️ Calls low — increase pace')
    if idle_6h:
        warnings.append('⏳ Idle detected — start working')

    # Quick one-liner after an action (prefer praise, else nudge)
    quick = ''
    if appreciation:
        quick = appreciation[0]
    elif warnings:
        quick = warnings[0]
    else:
        quick = next_action

    return {
        'next_action': next_action,
        'priority': priority,
        'appreciation': appreciation,
        'warnings': warnings,
        'quick_feedback': quick,
        'calls_today': calls_today,
        'fu_due': fu_due,
        'fu_overdue': fu_overdue,
        'hot_leads': hot,
        'conversion_today': conversion_today,
        'followups_logged_today': followups_logged_today,
    }


def compute_step8_team_coach_for_user(db, username: str) -> Dict[str, object]:
    today_iso = _today_ist().isoformat()
    now_local = _now_ist().replace(tzinfo=None)
    rows = load_step8_insight_leads(db, username)
    tgt = daily_call_target(db)
    return compute_step8_team_coach(rows, today_iso, now_local, tgt)


def compute_step8_quick_feedback_for_assignee(db, assignee_username: str) -> str:
    """After lead action: one line for the lead owner (read-only)."""
    coach = compute_step8_team_coach_for_user(db, assignee_username)
    q = coach.get('quick_feedback')
    return str(q) if q else ''


def _step8_hot_stale(rows: List[Dict[str, str]], now_local: datetime.datetime, hours: float = 24.0) -> bool:
    cut = now_local - datetime.timedelta(hours=hours)
    for r in rows:
        if (r.get('status') or '') in STEP8_EXIT_STATUSES:
            continue
        cs = (r.get('call_status') or '').strip()
        st = (r.get('status') or '').strip()
        if not (cs in CALL_STATUS_INTERESTED_BUCKET or st in STEP8_HOT_STATUSES):
            continue
        t = _step8_parse_ts(r.get('updated_at'))
        if t is not None and t < cut:
            return True
    return False


def compute_step8_leader_coach(
    db,
    member_usernames: List[str],
    today_iso: str,
    now_local: datetime.datetime,
) -> Dict[str, object]:
    """
    Downline pulse from the same five columns only. No writes.
    """
    inactive: List[str] = []
    low_perf: List[str] = []
    need_support: List[str] = []

    for un in member_usernames:
        rows = load_step8_insight_leads(db, un)
        active = [r for r in rows if (r.get('status') or '') not in STEP8_EXIT_STATUSES]
        if not active:
            continue
        coach = compute_step8_team_coach(rows, today_iso, now_local, 0)
        fu_overdue = int(coach.get('fu_overdue') or 0)
        calls_today = int(coach.get('calls_today') or 0)
        best_upd: Optional[datetime.datetime] = None
        for r in rows:
            t = _step8_parse_ts(r.get('updated_at'))
            if t and (best_upd is None or t > best_upd):
                best_upd = t
        if best_upd is not None and (now_local - best_upd) >= datetime.timedelta(hours=24):
            inactive.append(un)
        if calls_today < STEP8_CALLS_WARN_THRESHOLD:
            low_perf.append(un)
        if fu_overdue >= 2 or _step8_hot_stale(rows, now_local):
            need_support.append(un)

    summaries: List[str] = []
    if inactive:
        summaries.append(f'{len(inactive)} member{"s" if len(inactive) != 1 else ""} inactive 24h+')
    if low_perf:
        summaries.append(f'{len(low_perf)} member{"s" if len(low_perf) != 1 else ""} low performance')
    if need_support:
        summaries.append(f'{len(need_support)} member{"s" if len(need_support) != 1 else ""} need support')

    actions: List[str] = []
    first_inactive = inactive[0] if inactive else None
    if first_inactive:
        actions.append(f'Call {first_inactive}')
    guide_u = None
    for u in need_support:
        if u != first_inactive:
            guide_u = u
            break
    if guide_u is None and need_support:
        guide_u = need_support[0]
    if guide_u:
        actions.append(f'Guide {guide_u}')
    elif low_perf:
        pick = low_perf[0]
        if pick != first_inactive:
            actions.append(f'Coach {pick}')

    return {'summaries': summaries, 'actions': actions}


def build_step8_admin_ai_lines(db, snapshot_date: str, limit: int = 18) -> List[str]:
    """Read-only triage copy from today’s decision snapshots (not lead-row derived)."""
    rows = db.execute(
        """
        SELECT username, decision_class, detail
        FROM admin_decision_snapshots
        WHERE snapshot_date=?
        ORDER BY decision_class, username
        """,
        (snapshot_date,),
    ).fetchall()
    label = {
        'remove': 'REMOVE',
        'critical': 'CRITICAL',
        'top': 'TOP',
        'warning': 'WARNING',
        'good': 'GOOD',
    }
    lines: List[str] = []
    for r in rows:
        cls = (r['decision_class'] or '').strip()
        if cls not in label:
            continue
        det = (r['detail'] or '').strip()
        short = det[:100] + ('…' if len(det) > 100 else '')
        lines.append(f"{label[cls]}: {r['username']} — {short}" if short else f"{label[cls]}: {r['username']}")
        if len(lines) >= limit:
            break
    return lines


def build_step8_evening_summary_line(
    coach: Dict[str, object],
    today_iso: str,
    now_local: datetime.datetime,
) -> str:
    """Optional end-of-calling-window one-liner from the same coach metrics (still computed on load)."""
    if now_local.hour < DAILY_CALL_ENFORCE_START_HOUR_IST:
        return ''
    ct = int(coach.get('calls_today') or 0)
    fu = int(coach.get('fu_due') or 0)
    return f'Day wrap ({today_iso}): {ct} calls logged · {fu} follow-ups due'


# ── Layout context cache (nav badges / inactivity) — opt-in: MYLE_LAYOUT_CACHE_SEC ──
import threading as _layout_metrics_threading
import time as _layout_metrics_time

_layout_metrics_lock = _layout_metrics_threading.Lock()
_layout_metrics_store: Dict[tuple, tuple] = {}


def layout_metrics_cache_get(cache_key: tuple, ttl_sec: float):
    """Return cached dict if still fresh; ttl_sec<=0 disables reads."""
    if ttl_sec <= 0:
        return None
    now = _layout_metrics_time.monotonic()
    with _layout_metrics_lock:
        hit = _layout_metrics_store.get(cache_key)
        if not hit:
            return None
        ts, payload = hit
        if now - ts >= ttl_sec:
            return None
        return dict(payload)


def layout_metrics_cache_set(cache_key: tuple, payload: dict, ttl_sec: float) -> None:
    if ttl_sec <= 0:
        return
    with _layout_metrics_lock:
        _layout_metrics_store[cache_key] = (_layout_metrics_time.monotonic(), dict(payload))
