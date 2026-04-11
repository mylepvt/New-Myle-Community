"""
When admin sets or changes upline so a member sits under a parent:

- **Team:** pipeline execution (leads.assigned_user_id) follows the same rules
  as the ₹196 handoff / Day‑1 routing. Permanent claimer (leads.current_owner)
  is never updated (DB also blocks changing it after claim).

- **Team or leader:** daily_reports rows with a blank upline_name get that
  field set to the **direct parent** username admin chose — in-place UPDATE only
  (no new rows, no duplicates). Non-empty upline_name is left as historical record.

Only assigned_user_id, assigned_to, updated_at on leads; only upline_name on
daily_reports (where blank).
"""
from __future__ import annotations

from helpers import (
    apply_leads_update,
    sqlite_row_get,
    team_in_pre_day1_execution,
    user_id_for_username,
)


def _resolved_parent_username_db(db, username: str) -> str | None:
    """
    Same link resolution as admin org-tree (upline username, display name, or FBO).
    Kept here to avoid importing route modules (circular imports).
    """
    if not username:
        return None
    row = db.execute(
        "SELECT username, upline_username, upline_name, upline_fbo_id FROM users WHERE username=?",
        (username,),
    ).fetchone()
    if not row:
        return None
    u = (row["username"] or "").strip()
    upline_un = (row["upline_username"] or "").strip()
    upline_nm = (row["upline_name"] or "").strip()
    ufbo = (row["upline_fbo_id"] or "").strip()
    if upline_un and upline_un != u:
        hit = db.execute("SELECT username FROM users WHERE username=?", (upline_un,)).fetchone()
        if hit:
            return (hit["username"] or "").strip()
    if upline_nm and upline_nm != u:
        hit = db.execute("SELECT username FROM users WHERE username=?", (upline_nm,)).fetchone()
        if hit:
            return (hit["username"] or "").strip()
    if ufbo:
        hit = db.execute(
            "SELECT username FROM users WHERE TRIM(fbo_id)=? AND username!=?",
            (ufbo, u),
        ).fetchone()
        if hit:
            return (hit["username"] or "").strip()
    return None


def nearest_approved_leader_username(db, start_username: str) -> str | None:
    """
    Walk upline (FBO-aware) until the first approved user with role=leader.
    Returns None if there is no leader above (e.g. chain ends at admin or broken link).

    Use this for ₹196 / Day 1 execution handoff and hierarchy sync so behavior matches
    org-tree downline visibility (leader sees nested team); direct-upline-only resolution
    would wrongly route execution to an intermediate team member.
    """
    visited: set[str] = set()
    current = (start_username or "").strip()
    while current and current not in visited:
        visited.add(current)
        parent_un = _resolved_parent_username_db(db, current)
        if not parent_un:
            return None
        parent = db.execute(
            "SELECT username, role, status FROM users WHERE username=? LIMIT 1",
            (parent_un,),
        ).fetchone()
        if not parent:
            return None
        if (parent["status"] or "").strip() != "approved":
            return None
        role = (parent["role"] or "").strip()
        if role == "leader":
            return (parent["username"] or "").strip() or None
        if role == "admin":
            return None
        current = parent_un
    return None


def leader_day1_routing_on(db, leader_username: str) -> bool:
    """Same rules as lead_routes._leader_day1_routing_on: leaders use day1_routing_on; admin → True."""
    u = (leader_username or "").strip()
    if not u:
        return False
    row = db.execute(
        "SELECT day1_routing_on, role FROM users WHERE username=? LIMIT 1",
        (u,),
    ).fetchone()
    if not row:
        return False
    role = ((row["role"] or "") or "").strip().lower()
    if role == "admin":
        return True
    if role != "leader":
        return False
    return bool(int(row["day1_routing_on"] or 0))


def sync_lead_execution_after_team_upline_change(db, team_username: str) -> int:
    """
    Re-point execution assignees (assigned_user_id) only. Permanent owner
    (current_owner = claimer) is read for filtering but never updated.
    Safe to call multiple times (idempotent).
    Returns number of leads for which an UPDATE was attempted (see WHERE guard).
    """
    team_username = (team_username or "").strip()
    if not team_username:
        return 0
    role_row = db.execute(
        "SELECT role FROM users WHERE username=?",
        (team_username,),
    ).fetchone()
    if not role_row or (role_row["role"] or "").strip() != "team":
        return 0
    team_uid = user_id_for_username(db, team_username)
    if team_uid is None:
        return 0

    leader_un = (nearest_approved_leader_username(db, team_username) or "").strip()
    leader_uid = user_id_for_username(db, leader_un)
    routing_on = leader_day1_routing_on(db, leader_un) if leader_un else False

    leads = db.execute(
        """
        SELECT id, status, pipeline_stage, assigned_user_id
        FROM leads
        WHERE in_pool = 0 AND deleted_at = ''
          AND LOWER(TRIM(COALESCE(current_owner, ''))) = LOWER(?)
        """,
        (team_username,),
    ).fetchall()

    updated = 0
    for lead in leads:
        lead_d = dict(lead)
        if team_in_pre_day1_execution(lead_d):
            target_uid = int(team_uid)
        else:
            if routing_on and leader_uid is not None:
                target_uid = int(leader_uid)
            else:
                target_uid = int(team_uid)
        try:
            cur = sqlite_row_get(lead, "assigned_user_id")
            cur_i = int(cur) if cur is not None else None
        except (TypeError, ValueError):
            cur_i = None
        if cur_i is not None and cur_i == target_uid:
            continue
        allowed_exec = {int(team_uid)}
        if not team_in_pre_day1_execution(lead_d) and routing_on and leader_uid is not None:
            allowed_exec.add(int(leader_uid))
        if int(target_uid) not in allowed_exec:
            continue
        # Require current_owner still = this team so we never touch another claimer's row.
        apply_leads_update(
            db,
            {"assigned_user_id": target_uid, "assigned_to": ""},
            where_sql=(
                "id = ? AND in_pool = 0 AND deleted_at = '' "
                "AND LOWER(TRIM(COALESCE(current_owner, ''))) = LOWER(?)"
            ),
            where_params=(int(lead["id"]), team_username),
            log_context="hierarchy_upline_sync",
        )
        updated += 1
    return updated


def backfill_daily_reports_upline_where_blank(
    db,
    member_username: str,
    direct_parent_username: str,
) -> int:
    """
    Attach existing reports to the admin-set upline when upline_name was never
    filled (common for orphans). Does not INSERT; does not overwrite non-blank
    upline_name (avoids clobbering history / duplicates).
    """
    member_username = (member_username or "").strip()
    direct_parent_username = (direct_parent_username or "").strip()
    if not member_username or not direct_parent_username:
        return 0
    cur = db.execute(
        """
        UPDATE daily_reports
        SET upline_name = ?
        WHERE username = ?
          AND TRIM(COALESCE(upline_name, '')) = ''
        """,
        (direct_parent_username, member_username),
    )
    try:
        return int(cur.rowcount or 0)
    except (TypeError, ValueError):
        return 0


def sync_member_under_parent(db, username: str, direct_parent_username: str) -> dict:
    """
    Run all hierarchy-side effects after `users` upline columns are updated.
    Returns counts for observability (e.g. logging); safe to call repeatedly.
    """
    username = (username or "").strip()
    direct_parent_username = (direct_parent_username or "").strip()
    out = {"leads_touched": 0, "daily_reports_touched": 0}
    if not username or not direct_parent_username:
        return out
    role_row = db.execute("SELECT role FROM users WHERE username=?", (username,)).fetchone()
    role = (role_row["role"] or "").strip() if role_row else ""
    if role == "team":
        out["leads_touched"] = sync_lead_execution_after_team_upline_change(db, username)
    out["daily_reports_touched"] = backfill_daily_reports_upline_where_blank(
        db, username, direct_parent_username
    )
    return out
