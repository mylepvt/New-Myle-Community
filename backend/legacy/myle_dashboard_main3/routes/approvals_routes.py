"""
Admin approval routes (approve / reject / delete pending user registrations).

Registered via register_approvals_routes(app) at the end of app.py load.
"""
from __future__ import annotations

import threading

from flask import current_app, flash, jsonify, redirect, render_template, request, session, url_for

from database import get_db
from decorators import admin_required, safe_route
from auth_context import acting_username
from helpers import (
    ensure_upline_fields_for_user,
    _log_activity,
    validate_upline_assignment_roles,
)
from services.hierarchy_lead_sync import sync_member_under_parent


def _resolved_parent_username_db(db, username: str):
    """
    Single source of truth for upline link (username, display name field, or upline FBO).
    Returns parent username or None.
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


def _upward_username_chain(db, start_username: str) -> list:
    """Walk from start upward to root; includes start. Used for circular upline checks."""
    chain: list = []
    seen = set()
    cur = start_username
    while cur and cur not in seen:
        seen.add(cur)
        chain.append(cur)
        nxt = _resolved_parent_username_db(db, cur)
        cur = nxt if nxt and nxt != cur else None
    return chain


def register_approvals_routes(app):
    """Attach approval-related URL rules to the Flask app."""
    from app import (  # noqa: PLC0415
        _send_welcome_email,
    )

    @app.route('/admin/approvals')
    @admin_required
    def admin_approvals():
        filter_by = request.args.get('filter', 'all')
        db = get_db()

        query  = "SELECT * FROM users WHERE role != 'admin'"
        params = []
        if filter_by in ('pending', 'approved', 'rejected'):
            query += " AND status=?"
            params.append(filter_by)
        query += " ORDER BY created_at DESC"

        users = db.execute(query, params).fetchall()
        return render_template('admin_approvals.html', users=users, filter_by=filter_by)


    @app.route('/admin/approvals/<int:user_id>/approve', methods=['POST'])
    @admin_required
    def approve_user(user_id):
        db   = get_db()
        user = db.execute("SELECT username, email FROM users WHERE id=?", (user_id,)).fetchone()
        if user:
            db.execute("UPDATE users SET status='approved' WHERE id=?", (user_id,))
            db.commit()
            ensure_upline_fields_for_user(db, user["username"])
            db.commit()
            flash(f'"{user["username"]}" has been approved and can now log in.', 'success')
            login_url = request.host_url.rstrip('/') + url_for('login')
            threading.Thread(target=_send_welcome_email,
                             args=(user['email'], user['username'], login_url),
                             daemon=True).start()
        return redirect(url_for('admin_approvals', filter=request.form.get('current_filter', 'all')))


    @app.route('/admin/approvals/<int:user_id>/reject', methods=['POST'])
    @admin_required
    def reject_user(user_id):
        db   = get_db()
        user = db.execute("SELECT username FROM users WHERE id=?", (user_id,)).fetchone()
        if user:
            db.execute("UPDATE users SET status='rejected' WHERE id=?", (user_id,))
            db.commit()
            flash(f'"{user["username"]}" registration has been rejected.', 'warning')
        return redirect(url_for('admin_approvals', filter=request.form.get('current_filter', 'all')))


    # ── helpers shared by org-tree routes ──────────────────────────────────────
    def _build_org_data(db):
        """Return (all_users, tree_roots, orphans, invalid_list, stats, assignable_map)."""
        all_users = [dict(u) for u in db.execute(
            "SELECT username, fbo_id, role, status, upline_name, upline_username, "
            "upline_fbo_id, phone, display_picture, created_at, name, email "
            "FROM users ORDER BY role DESC, created_at ASC"
        ).fetchall()]

        by_name = {u['username']: dict(u, children=[], issues=[]) for u in all_users}

        # Cycle: if start already appears walking upward from proposed parent → would create a loop
        def _would_create_cycle(start_un, proposed_parent_un):
            return start_un in _upward_username_chain(db, proposed_parent_un)

        # Role-hierarchy rules: team→leader, leader→admin
        def _valid_upline_role(user_role, upline_role):
            ok, _ = validate_upline_assignment_roles(user_role, upline_role)
            return ok

        roots, orphans, invalid_list = [], [], []

        for u in all_users:
            uname = u["username"]
            parent = _resolved_parent_username_db(db, uname)

            # Validate
            issues = []
            if parent and parent in by_name:
                parent_role = (by_name[parent].get('role') or '').strip()
                if not _valid_upline_role(u['role'], parent_role):
                    issues.append(f"Role mismatch: {u['role']} → upline is {parent_role}")
                if _would_create_cycle(uname, parent):
                    issues.append("Circular reference detected")
            elif parent and parent not in by_name:
                issues.append(f"Upline @{parent} not found in system")
            by_name[uname]['issues'] = issues
            if issues:
                invalid_list.append(by_name[uname])

            if u['role'] == 'admin':
                roots.append(by_name[uname])
            elif parent and parent in by_name:
                by_name[parent]['children'].append(by_name[uname])
            else:
                orphans.append(by_name[uname])

        for u in all_users:
            u['resolved_upline'] = _resolved_parent_username_db(db, u['username']) or ''

        # Assignable options per role: team gets leaders only, leader gets admins only
        admins  = [u for u in all_users if u['role'] == 'admin']
        leaders = [u for u in all_users if u['role'] == 'leader']
        assignable = {
            'team':   leaders,
            'leader': admins,
            'admin':  [],
        }

        stats = {
            'total':    len(all_users),
            'leaders':  len(leaders),
            'teams':    sum(1 for u in all_users if u['role'] == 'team'),
            'pending':  sum(1 for u in all_users if u['status'] == 'pending'),
            'orphans':  len(orphans),
            'invalid':  len(invalid_list),
        }

        return all_users, roots, orphans, invalid_list, stats, assignable

    @app.route('/admin/org-tree')
    @admin_required
    @safe_route
    def admin_org_tree():
        db        = get_db()
        all_users, roots, orphans, invalid_list, stats, assignable = _build_org_data(db)
        _d1r = db.execute(
            "SELECT username FROM users WHERE role='leader' AND day1_routing_on=1"
        ).fetchall()
        day1_routing_leaders = {r['username'] for r in _d1r}
        show_d1_routing_debug = request.args.get('d1debug', '').lower() in (
            '1',
            'true',
            'yes',
        )
        d1_routing_leader_rows = []
        if show_d1_routing_debug:
            d1_routing_leader_rows = db.execute(
                "SELECT username, COALESCE(day1_routing_on,0) AS day1_routing_on, status "
                "FROM users WHERE role='leader' ORDER BY username COLLATE NOCASE"
            ).fetchall()
        view = request.args.get('view', 'tree')   # tree | orphans | invalid | flat
        flat_filter = request.args.get('filter', 'all')  # all | no_upline | invalid
        orphan_names = {o['username'] for o in orphans}
        invalid_names = {i['username'] for i in invalid_list}
        return render_template('admin_org_tree.html',
                               tree=roots,
                               all_users=all_users,
                               orphans=orphans,
                               invalid_list=invalid_list,
                               stats=stats,
                               assignable=assignable,
                               view=view,
                               flat_filter=flat_filter,
                               orphan_names=orphan_names,
                               invalid_names=invalid_names,
                               day1_routing_leaders=day1_routing_leaders,
                               show_d1_routing_debug=show_d1_routing_debug,
                               d1_routing_leader_rows=d1_routing_leader_rows)

    @app.route('/admin/fix-hierarchy', methods=['POST'])
    @admin_required
    def admin_fix_hierarchy():
        """One-click hierarchy repair: leaders -> admin, teams -> nearest/fallback leader."""
        db = get_db()
        try:
            admin = db.execute(
                "SELECT id, username, COALESCE(NULLIF(TRIM(fbo_id),''), '') AS fbo_id "
                "FROM users WHERE role='admin' ORDER BY id LIMIT 1"
            ).fetchone()
            if not admin:
                flash('Admin not found.', 'danger')
                return redirect(url_for('admin_org_tree'))

            # 1) Leaders -> Admin
            db.execute(
                "UPDATE users SET upline_username=?, upline_name=?, upline_fbo_id=?, upline_id=? "
                "WHERE role='leader'",
                (admin['username'], admin['username'], admin['fbo_id'], admin['id']),
            )

            # 2) Build fallback leader
            fallback_leader = db.execute(
                "SELECT id, username, COALESCE(NULLIF(TRIM(fbo_id),''), '') AS fbo_id "
                "FROM users WHERE role='leader' ORDER BY id LIMIT 1"
            ).fetchone()
            if not fallback_leader:
                db.commit()
                _log_activity(db, acting_username(), 'fix_hierarchy', 'No leader found for team fallback')
                flash('Leaders mapped to admin, but no leader found for team fallback.', 'warning')
                return redirect(url_for('admin_org_tree'))

            teams = db.execute(
                "SELECT username FROM users WHERE role='team' ORDER BY id"
            ).fetchall()

            fixed_count = 0
            for t in teams:
                team_un = (t['username'] or '').strip()
                if not team_un:
                    continue

                # Climb upward to nearest leader (never allow loops).
                leader_row = None
                visited = set()
                current = team_un
                while current and current not in visited:
                    visited.add(current)
                    parent_un = _resolved_parent_username_db(db, current)
                    if not parent_un:
                        break
                    parent = db.execute(
                        "SELECT id, username, role, COALESCE(NULLIF(TRIM(fbo_id),''), '') AS fbo_id "
                        "FROM users WHERE username=? LIMIT 1",
                        (parent_un,),
                    ).fetchone()
                    if not parent:
                        break
                    if (parent['role'] or '').strip() == 'leader':
                        leader_row = parent
                        break
                    if (parent['role'] or '').strip() != 'team':
                        break
                    current = parent_un

                if not leader_row:
                    leader_row = fallback_leader

                db.execute(
                    "UPDATE users SET upline_username=?, upline_name=?, upline_fbo_id=?, upline_id=? "
                    "WHERE username=?",
                    (
                        leader_row['username'],
                        leader_row['username'],
                        leader_row['fbo_id'],
                        leader_row['id'],
                        team_un,
                    ),
                )
                sync_member_under_parent(db, team_un, leader_row["username"])
                fixed_count += 1

            # 3) Clear invalid upline_fbo_id refs globally (unknown FBO values)
            db.execute(
                "UPDATE users SET upline_fbo_id='' "
                "WHERE TRIM(COALESCE(upline_fbo_id, '')) != '' "
                "AND NOT EXISTS ("
                "  SELECT 1 FROM users p "
                "  WHERE TRIM(COALESCE(p.fbo_id, '')) = TRIM(users.upline_fbo_id)"
                ")"
            )

            db.commit()
            _log_activity(db, acting_username(), 'fix_hierarchy', f'Fixed leaders + {fixed_count} team links')
            flash('Hierarchy fixed successfully.', 'success')
            return redirect(url_for('admin_org_tree'))
        except Exception as e:
            db.rollback()
            flash(f'Error while fixing hierarchy: {e}', 'danger')
            return redirect(url_for('admin_org_tree'))

    @app.route('/admin/org-tree/assign', methods=['POST'])
    @admin_required
    def admin_org_tree_assign():
        """Assign or change upline for one user. Validates role + no circular (FBO-aware)."""
        username   = request.form.get('username', '').strip()
        new_upline = request.form.get('new_upline', '').strip()

        return_view = request.form.get('return_view', 'tree').strip()
        if return_view not in ('tree', 'orphans', 'invalid', 'flat'):
            return_view = 'tree'

        def _back():
            return redirect(url_for('admin_org_tree', view=return_view))

        if not username:
            flash('Username missing.', 'danger')
            return _back()

        db   = get_db()
        user = db.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        if not user:
            flash(f'User @{username} not found.', 'danger')
            return _back()

        if (user['role'] or '').strip() == 'admin':
            flash('Admin account has no upline.', 'danger')
            return _back()

        if not new_upline:
            flash('Upline is required. Team must map to Leader, Leader must map to Admin.', 'danger')
            return _back()

        upline_row = db.execute("SELECT * FROM users WHERE username=?", (new_upline,)).fetchone()
        if not upline_row:
            flash(f'Upline @{new_upline} not found.', 'danger')
            return _back()
        if (upline_row['status'] or '').strip() != 'approved':
            flash(f'Upline @{new_upline} must be approved.', 'danger')
            return _back()

        # Role validation
        u_role  = (user['role'] or '').strip()
        up_role = (upline_row['role'] or '').strip()
        ok, msg = validate_upline_assignment_roles(u_role, up_role)
        if not ok:
            flash(f'{msg} Selected: @{new_upline} ({up_role}).', 'danger')
            return _back()

        if username in _upward_username_chain(db, new_upline):
            flash(f'Circular reference: @{username} is on the upline chain above @{new_upline}.', 'danger')
            return _back()

        upline_fbo = (upline_row['fbo_id'] or '').strip()
        up_uid     = db.execute("SELECT id FROM users WHERE username=?", (new_upline,)).fetchone()
        up_id      = int(up_uid['id']) if up_uid else None
        db.execute(
            "UPDATE users SET upline_username=?, upline_name=?, upline_fbo_id=?, upline_id=? WHERE username=?",
            (new_upline, new_upline, upline_fbo, up_id, username),
        )
        if u_role in ('team', 'leader'):
            sync_member_under_parent(db, username, new_upline)
        db.commit()
        _log_activity(db, acting_username(), 'org_tree_assign', f'@{username} upline → @{new_upline}')
        flash(f'✓ @{username} → upline set to @{new_upline}.', 'success')
        return _back()

    @app.route('/admin/org-tree/bulk-fix-orphans', methods=['POST'])
    @admin_required
    def admin_org_tree_bulk_fix():
        """Assign all orphaned team members to a chosen leader."""
        new_upline = request.form.get('bulk_upline', '').strip()
        if not new_upline:
            flash('Select an upline first.', 'danger')
            return redirect(url_for('admin_org_tree'))

        db  = get_db()
        upl = db.execute("SELECT * FROM users WHERE username=?", (new_upline,)).fetchone()
        if not upl or upl['role'] != 'leader':
            flash('Bulk upline must be a Leader.', 'danger')
            return redirect(url_for('admin_org_tree'))
        if (upl['status'] or '').strip() != 'approved':
            flash('Bulk upline must be an approved account.', 'danger')
            return redirect(url_for('admin_org_tree'))

        rows = db.execute(
            "SELECT username, role FROM users WHERE role='team'"
        ).fetchall()
        up_id = int(upl['id'])
        upline_fbo = (upl['fbo_id'] or '').strip()
        count = 0
        for r in rows:
            un = r['username']
            if un == new_upline:
                continue
            if _resolved_parent_username_db(db, un):
                continue
            db.execute(
                "UPDATE users SET upline_username=?, upline_name=?, upline_fbo_id=?, upline_id=? "
                "WHERE username=?",
                (new_upline, new_upline, upline_fbo, up_id, un),
            )
            sync_member_under_parent(db, un, new_upline)
            count += 1

        db.commit()
        _log_activity(db, acting_username(), 'org_tree_bulk_orphans', f'{count} → @{new_upline}')
        flash(f'Bulk fix done — {count} orphan(s) assigned to @{new_upline}.', 'success')
        return redirect(url_for('admin_org_tree'))


    @app.route('/admin/org-tree/edit', methods=['POST'])
    @admin_required
    def admin_org_tree_edit():
        """Update identity/contact fields from org tree; cascade upline_fbo_id if FBO changes."""
        username = request.form.get('username', '').strip()
        fbo_id = request.form.get('fbo_id', '').strip()
        phone = request.form.get('phone', '').strip()
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        return_view = request.form.get('return_view', 'tree').strip()
        return_filter = request.form.get('return_filter', 'all').strip()

        if return_view not in ('tree', 'orphans', 'invalid', 'flat'):
            return_view = 'tree'
        if return_filter not in ('all', 'no_upline', 'invalid'):
            return_filter = 'all'

        redir = lambda: redirect(
            url_for('admin_org_tree', view=return_view, filter=return_filter)
        )

        if not username:
            flash('Username missing.', 'danger')
            return redir()

        db = get_db()
        user = db.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        if not user:
            flash('User not found.', 'danger')
            return redir()

        role = (user['role'] or '').strip()
        if role != 'admin':
            if not fbo_id:
                flash(f'@{username}: FBO ID is required for team/leader accounts.', 'danger')
                return redir()
            dup = db.execute(
                "SELECT username FROM users WHERE TRIM(fbo_id)=TRIM(?) "
                "AND TRIM(COALESCE(fbo_id,''))!='' AND username!=?",
                (fbo_id, username),
            ).fetchone()
            if dup:
                flash(f'FBO ID already used by @{dup["username"]}.', 'danger')
                return redir()

        old_fbo = (user['fbo_id'] or '').strip()

        db.execute(
            "UPDATE users SET fbo_id=?, phone=?, name=?, email=? WHERE username=?",
            (fbo_id, phone, name, email, username),
        )

        if old_fbo and fbo_id and old_fbo != fbo_id:
            db.execute(
                "UPDATE users SET upline_fbo_id=? "
                "WHERE TRIM(upline_fbo_id)=TRIM(?) AND TRIM(COALESCE(upline_fbo_id,''))!='' "
                "AND username!=?",
                (fbo_id, old_fbo, username),
            )

        db.commit()
        _log_activity(
            db,
            acting_username(),
            'org_tree_edit',
            f'@{username} fbo/name/email/phone updated',
        )
        flash(f'@{username} details saved. Hierarchy refreshed on next load.', 'success')
        return redir()


    @app.route('/admin/org-tree/day1-routing-toggle', methods=['POST'])
    @admin_required
    def admin_org_tree_day1_routing_toggle():
        """Toggle Day 1 auto-routing for a leader's downline enrollments."""
        is_ajax = request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        if is_ajax:
            data = request.get_json(silent=True) or {}
            leader_un = (data.get('leader_username') or '').strip()
        else:
            leader_un = (request.form.get('leader_username') or '').strip()
        db = get_db()
        row = db.execute(
            "SELECT username, role, status, day1_routing_on FROM users "
            "WHERE username=? AND role='leader' AND status='approved'",
            (leader_un,),
        ).fetchone()
        if not row:
            if is_ajax:
                return jsonify({'ok': False, 'error': f'@{leader_un} is not a valid approved leader.'}), 400
            flash(f'@{leader_un} is not a valid approved leader.', 'danger')
            return redirect(url_for('admin_org_tree'))
        current_val = int(row['day1_routing_on'] or 0)
        new_val = 0 if current_val else 1
        db.execute(
            "UPDATE users SET day1_routing_on=? WHERE username=?",
            (new_val, leader_un),
        )
        db.commit()
        msg = f'Day 1 routing {"ON" if new_val else "OFF"} for @{leader_un}'
        _log_activity(db, acting_username(), 'day1_routing_toggle', msg)
        try:
            current_app.logger.info(
                'day1_routing_toggle actor=%r leader=%r %s->%s',
                acting_username(),
                leader_un,
                current_val,
                new_val,
            )
        except Exception:
            pass
        if is_ajax:
            return jsonify({'ok': True, 'new_val': new_val, 'leader': leader_un, 'message': msg})
        flash(msg, 'success' if new_val else 'warning')
        return redirect(url_for('admin_org_tree'))

    @app.route('/admin/approvals/<int:user_id>/delete', methods=['POST'])
    @admin_required
    def delete_user(user_id):
        db   = get_db()
        user = db.execute("SELECT username, status FROM users WHERE id=?", (user_id,)).fetchone()
        if user:
            if user['status'] == 'approved':
                flash('Cannot delete an approved user. Reject them first.', 'danger')
            else:
                db.execute("DELETE FROM users WHERE id=?", (user_id,))
                db.commit()
                flash(f'User "{user["username"]}" has been permanently deleted.', 'success')
        return redirect(url_for('admin_approvals', filter=request.form.get('current_filter', 'all')))
