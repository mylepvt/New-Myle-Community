"""
Announcements, leaderboard, and live-session routes.

Registered via register_social_routes(app) at the end of app.py load so helpers
on the app module are available without circular import at import time.
"""
from __future__ import annotations

import datetime

from flask import (
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from database import get_db
from auth_context import acting_username


def register_social_routes(app):
    """Attach social/community URL rules to the Flask app (preserves endpoint names)."""
    from app import _push_all_team  # noqa: PLC0415 — late import
    from decorators import admin_required, login_required
    from helpers import (
        _get_network_usernames,
        _get_setting,
        _set_setting,
        _get_user_badges_emoji,
        _today_ist,
    )

    @app.route('/announcements', methods=['GET'])
    @login_required
    def announcements():
        db   = get_db()
        rows = db.execute(
            "SELECT * FROM announcements ORDER BY pin DESC, created_at DESC LIMIT 20"
        ).fetchall()
        return render_template('announcements.html', announcements=rows)

    @app.route('/announcements/post', methods=['POST'])
    @admin_required
    def post_announcement():
        msg = request.form.get('message', '').strip()
        pin = 1 if request.form.get('pin') else 0
        if not msg:
            flash('Message cannot be empty.', 'danger')
            return redirect(url_for('announcements'))
        db = get_db()
        db.execute(
            "INSERT INTO announcements (message, created_by, pin) VALUES (?, ?, ?)",
            (msg, acting_username(), pin)
        )
        db.commit()
        preview = msg[:80] + ('\u2026' if len(msg) > 80 else '')
        _push_all_team(db, '\U0001f4e2 New Announcement', preview, url_for('announcements'))
        flash('Announcement posted!', 'success')
        return redirect(url_for('announcements'))

    @app.route('/announcements/<int:ann_id>/delete', methods=['POST'])
    @admin_required
    def delete_announcement(ann_id):
        db = get_db()
        db.execute("DELETE FROM announcements WHERE id=?", (ann_id,))
        db.commit()
        flash('Announcement deleted.', 'warning')
        return redirect(url_for('announcements'))

    @app.route('/announcements/<int:ann_id>/toggle-pin', methods=['POST'])
    @admin_required
    def toggle_pin(ann_id):
        db  = get_db()
        ann = db.execute("SELECT pin FROM announcements WHERE id=?", (ann_id,)).fetchone()
        if ann:
            db.execute("UPDATE announcements SET pin=? WHERE id=?",
                       (0 if ann['pin'] else 1, ann_id))
            db.commit()
        return redirect(url_for('announcements'))

    @app.route('/leaderboard')
    @login_required
    def leaderboard():
        db       = get_db()
        username = acting_username()

        NETWORK_TREE_SQL = """
            WITH RECURSIVE tree(uname, level, mfbo, parent_uname) AS (
                SELECT :me, 0,
                    (SELECT NULLIF(TRIM(COALESCE(fbo_id, '')), '') FROM users WHERE username = :me),
                    NULL
                UNION ALL
                SELECT u.username, t.level + 1, NULLIF(TRIM(COALESCE(u.fbo_id, '')), ''), t.uname
                FROM users u JOIN tree t ON u.status='approved'
                AND u.role IN ('team', 'leader')
                AND (
                    u.upline_name = t.uname OR u.upline_username = t.uname
                    OR (
                        t.mfbo IS NOT NULL
                        AND TRIM(COALESCE(u.upline_fbo_id, '')) != ''
                        AND TRIM(u.upline_fbo_id) = t.mfbo
                    )
                )
            )
            SELECT t.uname, t.level, t.parent_uname,
                   (SELECT COALESCE(NULLIF(TRIM(fbo_id), ''), '')
                    FROM users pu WHERE pu.username = t.parent_uname LIMIT 1) AS parent_fbo,
                   u.display_picture,
                   COUNT(l.id)                                                                AS total,
                   SUM(CASE WHEN l.status IN ('Converted','Fully Converted') THEN 1 ELSE 0 END) AS converted,
                   SUM(CASE WHEN l.payment_done=1 THEN 1 ELSE 0 END)                            AS paid,
                   ROUND(CAST(SUM(CASE WHEN l.payment_done=1 THEN 1 ELSE 0 END) AS REAL)
                         / NULLIF(COUNT(l.id),0)*100, 1)                                        AS paid_pct,
                   COALESCE(SUM(COALESCE(l.payment_amount,0)+COALESCE(l.revenue,0)),0)          AS revenue,
                   SUM(CASE WHEN l.status='Seat Hold Confirmed' THEN 1 ELSE 0 END)             AS seat_holds,
                   SUM(CASE WHEN l.status='Fully Converted'     THEN 1 ELSE 0 END)             AS fully_conv
            FROM tree t
            JOIN users u ON u.username = t.uname
            LEFT JOIN leads l ON l.assigned_user_id = u.id AND l.in_pool=0 AND l.deleted_at=''
            WHERE t.uname != :me
            GROUP BY t.uname, t.level, t.parent_uname, u.display_picture, u.id
            ORDER BY t.level, paid DESC, converted DESC
        """

        # ── Debug: count team membership ─────────────────────────
        import logging as _logging
        _lb_log = _logging.getLogger('leaderboard')
        counts = db.execute("""
            SELECT
                COUNT(CASE WHEN role='team' THEN 1 END)                        AS total_team,
                COUNT(CASE WHEN role='team' AND status='approved' THEN 1 END)  AS approved_team
            FROM users
        """).fetchone()
        total_team    = counts['total_team']    or 0
        approved_team = counts['approved_team'] or 0
        is_fallback   = approved_team == 0
        _lb_log.info(
            "leaderboard: total_team=%d  approved_team=%d  is_fallback=%s  viewer=%s",
            total_team, approved_team, is_fallback, username
        )

        # Primary filter: real approved team members.
        # Fallback (dev/empty DB): all approved users so the board is never blank.
        user_where = "u.status='approved'" if is_fallback else "u.role='team' AND u.status='approved'"

        # Network tree — run for both admin (full org) and team (own downline)
        tree_rows = db.execute(NETWORK_TREE_SQL, {'me': username}).fetchall()
        network_by_gen = {}
        for r in tree_rows:
            network_by_gen.setdefault(r['level'], []).append(r)
        net_summary = {
            'total':   len(tree_rows),
            'direct':  len(network_by_gen.get(1, [])),
            'revenue': sum(r['revenue'] or 0 for r in tree_rows),
        }

        # Network growth by month
        if tree_rows:
            member_names = [r['uname'] for r in tree_rows]
            placeholders_g = ','.join('?' for _ in member_names)
            growth_rows = db.execute(f"""
                SELECT strftime('%Y-%m', CASE WHEN joining_date!='' THEN joining_date ELSE created_at END) as month,
                       COUNT(*) as new_members
                FROM users
                WHERE username IN ({placeholders_g})
                  AND {user_where.replace('u.', '')}
                GROUP BY month ORDER BY month ASC LIMIT 12
            """, member_names).fetchall()
            growth_data = [{'month': r['month'], 'count': r['new_members']} for r in growth_rows]
        else:
            growth_data = []

        # Weekly gamification scores
        monday_str = (_today_ist() - datetime.timedelta(days=_today_ist().weekday())).strftime('%Y-%m-%d')
        last_mon   = (_today_ist() - datetime.timedelta(days=_today_ist().weekday()+7)).strftime('%Y-%m-%d')

        weekly_rows = db.execute(f"""
            SELECT u.username, u.display_picture, u.total_points AS all_time_pts, u.user_stage,
                   COALESCE(SUM(CASE WHEN ds.score_date >= ? THEN ds.total_points ELSE 0 END),0) AS week_pts,
                   COALESCE(SUM(CASE WHEN ds.score_date >= ? AND ds.score_date < ? THEN ds.total_points ELSE 0 END),0) AS last_week_pts,
                   COALESCE(MAX(ds.streak_days),0) AS streak
            FROM users u
            LEFT JOIN daily_scores ds ON ds.username = u.username
            WHERE {user_where}
            GROUP BY u.username, u.display_picture, u.total_points, u.user_stage
            ORDER BY week_pts DESC, all_time_pts DESC
        """, (monday_str, last_mon, monday_str)).fetchall()

        # Attach badges
        weekly_board = []
        for r in weekly_rows:
            d = dict(r)
            badges_emoji = _get_user_badges_emoji(db, r['username'])
            d['badges']  = badges_emoji
            d['trend']   = (d['week_pts'] or 0) - (d['last_week_pts'] or 0)
            weekly_board.append(d)

        # Current user rank in weekly board
        weekly_usernames = [w['username'] for w in weekly_board]
        current_user_rank = (weekly_usernames.index(username) + 1) if username in weekly_usernames else None

        # Today's comparison board
        today_str = _today_ist().strftime('%Y-%m-%d')
        today_rows = db.execute(f"""
            SELECT u.username, u.display_picture,
                   COALESCE(ds.total_points,   0) AS today_pts,
                   COALESCE(ds.calls_made,     0) AS calls,
                   COALESCE(ds.batches_marked, 0) AS batches,
                   COALESCE(ds.videos_sent,    0) AS videos,
                   COALESCE(ds.streak_days,    0) AS streak
            FROM users u
            LEFT JOIN daily_scores ds ON ds.username = u.username AND ds.score_date = ?
            WHERE {user_where}
            ORDER BY today_pts DESC
        """, (today_str,)).fetchall()

        today_board = []
        for r in today_rows:
            d = dict(r)
            d['badges'] = _get_user_badges_emoji(db, r['username'])
            today_board.append(d)

        DAILY_TARGETS = {'calls': 5, 'batches': 3, 'videos': 3}

        # All-time points leaderboard — top 20 by lifetime total_points
        points_rows = db.execute(f"""
            SELECT u.username, u.display_picture,
                   u.total_points                        AS lifetime_points,
                   COALESCE(ds.total_points, 0)          AS today_score
            FROM users u
            LEFT JOIN daily_scores ds
                   ON ds.username = u.username AND ds.score_date = ?
            WHERE {user_where}
            ORDER BY u.total_points DESC, today_score DESC
            LIMIT 20
        """, (today_str,)).fetchall()
        points_board = [dict(r) for r in points_rows]
        points_user_rank = next(
            (i + 1 for i, r in enumerate(points_board) if r['username'] == username),
            None
        )

        return render_template('leaderboard.html',
                               current_user=username,
                               role=session.get('role'),
                               network_by_gen=network_by_gen,
                               net_summary=net_summary,
                               growth_data=growth_data,
                               weekly_board=weekly_board,
                               current_user_rank=current_user_rank,
                               today_board=today_board,
                               daily_targets=DAILY_TARGETS,
                               points_board=points_board,
                               points_user_rank=points_user_rank,
                               total_team=total_team,
                               approved_team=approved_team,
                               is_fallback=is_fallback)

    @app.route('/admin/leaderboard-summary')
    @admin_required
    def admin_leaderboard_summary():
        """View saved daily leaderboard summaries (history)."""
        import json as _json
        db   = get_db()
        rows = db.execute(
            "SELECT summary_date, message, top3_json, bottom5_json, created_at "
            "FROM leaderboard_summaries ORDER BY summary_date DESC LIMIT 30"
        ).fetchall()
        summaries = []
        for r in rows:
            summaries.append({
                'date':       r['summary_date'],
                'message':    r['message'],
                'top3':       _json.loads(r['top3_json']    or '[]'),
                'bottom5':    _json.loads(r['bottom5_json'] or '[]'),
                'created_at': r['created_at'],
            })
        return render_template('admin_leaderboard_summary.html', summaries=summaries)

    @app.route('/admin/leaderboard-summary/run', methods=['POST'])
    @admin_required
    def admin_run_leaderboard_summary():
        """Manually trigger the leaderboard summary job (admin only)."""
        from app import job_leaderboard_summary as _run_summary  # noqa: PLC0415 — deferred, avoids circular init
        _run_summary()
        flash('Leaderboard summary generated.', 'success')
        return redirect(url_for('admin_leaderboard_summary'))

    @app.route('/live-session')
    @login_required
    def live_session():
        db    = get_db()
        link       = _get_setting(db, 'zoom_link',       '')
        title      = _get_setting(db, 'zoom_title',      "Today's Live Session")
        time_      = _get_setting(db, 'zoom_time',        '2:00 PM')
        paper_plan = _get_setting(db, 'paper_plan_link', '')
        return render_template('live_session.html',
                               zoom_link=link, zoom_title=title, zoom_time=time_,
                               paper_plan_link=paper_plan)
