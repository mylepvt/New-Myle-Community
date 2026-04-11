import datetime
import logging

# Legacy Flask app used ``database.get_db``; vl2 has no such module — pass ``db=`` explicitly.
try:
    from database import get_db
except ImportError:
    get_db = None  # type: ignore[misc, assignment]

# Points rollup lives in monolith ``helpers._upsert_daily_score``; optional for imports.
try:
    from helpers import _upsert_daily_score
except ImportError:

    def _upsert_daily_score(db, username: str, points: int, **metrics) -> None:
        logging.getLogger("scoring").debug(
            "scoring_service: _upsert_daily_score no-op (helpers not loaded)"
        )

# The strict Action Matrix
ACTION_POINTS = {
    "CALL_ATTEMPT": 5,
    "CONNECTED_CALL": 20,
    "VIDEO_SENT": 15,
    "PAYMENT_DONE": 40,
    "BATCH_MARKED": 15,  # legacy — kept for point_history reads
    "BATCH_MARKED_D1_MORNING": 15,
    "BATCH_MARKED_D1_AFTERNOON": 15,
    "BATCH_MARKED_D1_EVENING": 15,
    "BATCH_MARKED_D2_MORNING": 15,
    "BATCH_MARKED_D2_AFTERNOON": 15,
    "BATCH_MARKED_D2_EVENING": 15,
    "FOLLOWUP_SET": 10,
    "FOLLOWUP_COMPLETED": 25,
    "DAY1_COMPLETE": 50,
    "DAY2_COMPLETE": 100,
    "CONVERSION": 300,
    "FOLLOWUP_ONTIME": 10,
    "FOLLOWUP_MISSED": -10,
}

# Actions that are per-lead-per-day idempotent (can only earn once per lead per day)
_IDEMPOTENT_PER_LEAD_ACTIONS = frozenset(
    {
        "CALL_ATTEMPT",
        "CONNECTED_CALL",
        "VIDEO_SENT",
        "PAYMENT_DONE",
        "FOLLOWUP_SET",
        "FOLLOWUP_COMPLETED",
        "BATCH_MARKED_D1_MORNING",
        "BATCH_MARKED_D1_AFTERNOON",
        "BATCH_MARKED_D1_EVENING",
        "BATCH_MARKED_D2_MORNING",
        "BATCH_MARKED_D2_AFTERNOON",
        "BATCH_MARKED_D2_EVENING",
    }
)

# Actions that are per-lead lifetime idempotent (can only earn once ever per lead)
_IDEMPOTENT_LIFETIME_ACTIONS = frozenset(
    {
        "CONVERSION",
    }
)

# Batch marked: only award when toggling ON (new_val=1), not OFF
# This is enforced at call site via delta_batches check below


def add_points(
    username: str,
    action_type: str,
    description: str = "",
    db=None,
    lead_id: int = 0,
    **metrics,
) -> None:
    """
    Awards or deducts points for a specific action, logs it, and auto-promotes the user.
    lead_id: pass the lead ID for idempotency checks on per-lead actions.
    Metrics (e.g., delta_calls=1) can be passed as keyword arguments.
    """
    points = ACTION_POINTS.get(action_type, 0)
    if points == 0 and not metrics:
        return

    # Skip if batch is toggled OFF (delta_batches < 0) — no points for unmarking
    if action_type.startswith("BATCH_MARKED") and metrics.get("delta_batches", 1) < 0:
        return

    _db = db
    close_db = False
    if _db is None:
        if get_db is None:
            logging.getLogger("scoring").warning(
                "scoring_service.add_points: no db= and database.get_db unavailable"
            )
            return
        _db = get_db()
        close_db = True

    try:
        today = datetime.date.today().isoformat()

        # Idempotency: per-lead-per-day — only award once per lead per action per day
        if lead_id and action_type in _IDEMPOTENT_PER_LEAD_ACTIONS:
            existing = _db.execute(
                """SELECT 1 FROM point_history
                   WHERE username=? AND action_type=? AND lead_id=?
                     AND DATE(created_at)=?
                   LIMIT 1""",
                (username, action_type, lead_id, today),
            ).fetchone()
            if existing:
                return  # Already awarded today for this lead

        # Idempotency: per-lead lifetime — only award once ever per lead
        if lead_id and action_type in _IDEMPOTENT_LIFETIME_ACTIONS:
            existing = _db.execute(
                """SELECT 1 FROM point_history
                   WHERE username=? AND action_type=? AND lead_id=?
                   LIMIT 1""",
                (username, action_type, lead_id),
            ).fetchone()
            if existing:
                return  # Already awarded lifetime for this lead

        # 1. Log the history — INSERT OR IGNORE makes the unique indexes the atomic guard
        if points != 0:
            result = _db.execute(
                """
                INSERT OR IGNORE INTO point_history (username, action_type, points, description, lead_id)
                VALUES (?, ?, ?, ?, ?)
                """,
                (username, action_type, points, description, lead_id),
            )
            if result.rowcount == 0:
                return  # Duplicate blocked by unique index — skip metrics update too

        # 2. Update via unified _upsert_daily_score (it handles users table + metrics)
        _upsert_daily_score(_db, username, points, **metrics)

        if close_db:
            _db.commit()
    except Exception as e:
        logging.getLogger("scoring").error("Error adding points for %s: %s", username, e)
    finally:
        if close_db:
            _db.close()

    # Trigger the progression auto-check
    check_progression(username, db=_db)


def apply_penalty(
    username: str, penalty_action: str = "FOLLOWUP_MISSED", description: str = "", db=None
) -> None:
    """
    Applies a negative score explicitly.
    """
    add_points(username, penalty_action, description, db=db)


def check_progression(username: str, db=None) -> None:
    """
    Strict Auto-Progression Engine. No manual overrides allowed.
    Day 1 -> Day 2: 50+ points OR 3+ follow-ups completed.
    Day 2 -> Day 3: Exclusively unlocked by Test (Handled in test_routes, not here).
    """
    _db = db
    close_db = False
    if _db is None:
        if get_db is None:
            return
        _db = get_db()
        close_db = True

    promote_to_day2 = False

    try:
        user = _db.execute(
            "SELECT user_stage, total_points FROM users WHERE username = ?", (username,)
        ).fetchone()
        if not user:
            return

        current_stage = user["user_stage"]
        total_points = user["total_points"]

        if current_stage == "day1":
            res = _db.execute(
                "SELECT COUNT(*) as count FROM point_history WHERE username = ? AND action_type = 'FOLLOWUP_COMPLETED'",
                (username,),
            ).fetchone()
            followups = res["count"] if res else 0

            # Progression Rule
            if total_points >= 50 or followups >= 3:
                _db.execute("UPDATE users SET user_stage = 'day2' WHERE username = ?", (username,))
                if close_db:
                    _db.commit()
                promote_to_day2 = True

    except Exception as e:
        logging.getLogger("scoring").error("Error checking progression for %s: %s", username, e)
    finally:
        if close_db:
            _db.close()

    # If promoted, trigger the DAY1_COMPLETE bonus safely (after connection is closed to avoid lock issues)
    if promote_to_day2:
        add_points(username, "DAY1_COMPLETE", "Auto-Promotion: Unlocked Day 2", db=db)
