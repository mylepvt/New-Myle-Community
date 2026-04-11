"""
Rule Engine — single source of truth for all business rules.

All lead pipeline rules, status flow, call classification, track pricing,
and hard validation live here. Import from this module, not from helpers.py.

helpers.py re-exports everything below for backward compatibility.
"""
from __future__ import annotations

# ─────────────────────────────────────────────────────────────────────────────
# Call Classification Buckets (Step 3 — discipline engine)
# ─────────────────────────────────────────────────────────────────────────────

CALL_STATUS_NOT_INTERESTED_BUCKET = frozenset({'Called - Not Interested'})

CALL_STATUS_NO_RESPONSE_BUCKET = frozenset({
    'Called - No Answer',
    'Called - Switch Off',
    'Called - Busy',
})

CALL_STATUS_INTERESTED_BUCKET = frozenset({
    'Called - Interested',
    'Called - Follow Up',
    'Call Back',
    'Video Sent',
    'Video Watched',
    'Payment Done',
})

# ─────────────────────────────────────────────────────────────────────────────
# Claim Gate Exit Statuses
# ─────────────────────────────────────────────────────────────────────────────

CLAIM_GATE_EXIT_STATUSES = ('Lost', 'Retarget', 'Converted', 'Fully Converted')

# ─────────────────────────────────────────────────────────────────────────────
# Pipeline Stage Rules
# ─────────────────────────────────────────────────────────────────────────────

# Active pipeline stages that auto-expire to Inactive after 24 hrs of no status change.
# Prospecting/enrollment leads (New Lead → Paid ₹196) are EXCLUDED — team members
# need unlimited time to contact and enroll leads. Only training pipeline stages expire.
PIPELINE_AUTO_EXPIRE_STATUSES = [
    'Day 1', 'Day 2', 'Interview', '2cc Plan', 'Track Selected', 'Seat Hold Confirmed',
    'Level Up',
]

# Soft SLA watch: all statuses except these (terminal / exits). Anchor = updated_at → claimed_at → created_at.
SLA_SOFT_WATCH_EXCLUDE = (
    'Lost', 'Retarget', 'Inactive', 'Converted',
)

# Maps lead status → pipeline_stage column value
STATUS_TO_STAGE = {
    'New Lead':            'prospecting',
    'New':                 'prospecting',
    'Contacted':           'prospecting',
    'Invited':             'prospecting',
    'Video Sent':          'prospecting',
    'Video Watched':       'prospecting',
    'Paid ₹196':           'enrolled',
    'Day 1':               'day1',
    'Day 2':               'day2',
    'Interview':           'day3',
    '2cc Plan':            'plan_2cc',
    'Track Selected':      'day3',
    'Seat Hold Confirmed': 'seat_hold',
    'Pending':             'pending',
    'Level Up':            'level_up',
    'Fully Converted':     'closing',
    'Training':            'training',
    'Converted':           'complete',
    'Lost':                'lost',
    'Retarget':            'prospecting',
    'Inactive':            'inactive',
}

# Maps pipeline_stage → default lead status when entering that stage
STAGE_TO_DEFAULT_STATUS = {
    'enrollment': 'New Lead',
    'day1':       'Day 1',
    'day2':       'Day 2',
    'day3':       'Interview',
    'seat_hold':  'Seat Hold Confirmed',
    'closing':    'Fully Converted',
    'training':   'Training',
    'complete':   'Converted',
    'lost':       'Lost',
}

# ─────────────────────────────────────────────────────────────────────────────
# Role-Based Status Permissions
# ─────────────────────────────────────────────────────────────────────────────

# Statuses team role cannot set directly via the status dropdown
TEAM_FORBIDDEN_STATUSES = frozenset([
    'Day 1', 'Day 2', 'Interview', 'Track Selected',
    'Seat Hold Confirmed', 'Fully Converted', 'Level Up',
    'Training', 'Converted', 'Pending', '2cc Plan',
])

# My Leads / team: only these choices — no other status can be injected via dropdown
TEAM_ALLOWED_STATUSES = (
    'New Lead', 'Contacted', 'Invited',
    'Video Sent', 'Video Watched',
    'Paid ₹196',
    'Lost', 'Retarget',
)

# ─────────────────────────────────────────────────────────────────────────────
# Canonical Status Flow (FSM)
# ─────────────────────────────────────────────────────────────────────────────

STATUS_FLOW_ORDER = [
    'New Lead',
    'Contacted',
    'Invited',
    'Video Sent',
    'Video Watched',
    'Paid ₹196',
    'Day 1',
    'Day 2',
    'Interview',
    'Track Selected',
    'Seat Hold Confirmed',
    'Fully Converted',
]

# ─────────────────────────────────────────────────────────────────────────────
# Call Status Values
# ─────────────────────────────────────────────────────────────────────────────

CALL_STATUS_VALUES = [
    'Not Called Yet',
    'Called - No Answer',
    'Called - Interested',
    'Called - Not Interested',
    'Called - Follow Up',
    'Called - Switch Off',
    'Called - Busy',
    'Call Back',
    'Wrong Number',
    'Video Sent',
    'Video Watched',
    'Payment Done',
    'Already forever',
    'Retarget',
]

# Team: only dial / line outcomes — pipeline progress is via Lead Status
TEAM_CALL_STATUS_VALUES = [
    'Not Called Yet',
    'Called - No Answer',
    'Called - Interested',
    'Called - Not Interested',
    'Called - Follow Up',
    'Called - Switch Off',
    'Called - Busy',
    'Call Back',
    'Wrong Number',
]

# ─────────────────────────────────────────────────────────────────────────────
# Track Pricing
# ─────────────────────────────────────────────────────────────────────────────

TRACKS = {
    'Slow Track':   {'price': 8000,  'seat_hold': 2000},
    'Medium Track': {'price': 18000, 'seat_hold': 4000},
    'Fast Track':   {'price': 38000, 'seat_hold': 5000},
}

# ─────────────────────────────────────────────────────────────────────────────
# Pure Rule Functions
# ─────────────────────────────────────────────────────────────────────────────

def normalize_flow_status(status: str) -> str:
    """Normalize legacy status aliases to canonical names."""
    s = (status or '').strip()
    if s == 'New':
        return 'New Lead'
    if s == 'Converted':
        return 'Fully Converted'
    return s


def is_valid_forward_status_transition(
    current_status: str, target_status: str, *, for_team: bool = False
) -> bool:
    """
    Canonical FSM flow rules.
    - Backward / same / statuses outside STATUS_FLOW_ORDER: allowed (legacy/admin fixes).
    - Default (leader/admin): forward exactly +1 step.
    - Team (for_team=True): any forward jump before Paid ₹196;
      Paid ₹196 only from Video Watched or already Paid ₹196.
    """
    cur = normalize_flow_status(current_status)
    tgt = normalize_flow_status(target_status)
    if not tgt or cur == tgt:
        return True
    flow_idx = {s: i for i, s in enumerate(STATUS_FLOW_ORDER)}
    if cur not in flow_idx or tgt not in flow_idx:
        return True
    if flow_idx[tgt] <= flow_idx[cur]:
        return True
    if for_team:
        paid_i = flow_idx.get('Paid ₹196')
        if tgt == 'Paid ₹196':
            return cur in ('Video Watched', 'Paid ₹196')
        if flow_idx[tgt] < paid_i:
            return flow_idx[tgt] > flow_idx[cur]
        return False
    return flow_idx[tgt] == flow_idx[cur] + 1


def validate_lead_business_rules(
    status: str,
    payment_done: int,
    payment_amount: float,
    seat_hold_amount: float,
    track_price: float,
) -> tuple[bool, str]:
    """Hard validation before DB write (payment + seat hold + track price)."""
    st = (status or '').strip()
    if int(payment_done or 0) == 1 and float(payment_amount or 0) <= 0:
        return False, 'payment_done=1 requires payment_amount > 0'
    if st == 'Seat Hold Confirmed' and float(seat_hold_amount or 0) <= 0:
        return False, 'Seat Hold Confirmed requires seat_hold_amount > 0'
    if st == 'Fully Converted' and float(track_price or 0) <= 0:
        return False, 'Fully Converted requires track_price > 0'
    return True, ''
