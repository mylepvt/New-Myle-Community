"""
Team management routes (/team CRUD) and Day 2 progress board.

Registered via register_team_routes(app) at the end of app.py load.
"""
from __future__ import annotations
import datetime

from flask import flash, redirect, render_template, request, session, url_for

from database import get_db
from decorators import admin_required, login_required, safe_route
from helpers import (
    _enrich_leads,
    _get_downline_usernames,
    _get_setting,
    _now_ist,
    _today_ist,
    user_id_for_username,
    count_distinct_valid_calls_on_date,
)
from auth_context import acting_username


def register_team_routes(app):
    """Attach team-related URL rules to the Flask app."""

    @app.route('/team')
    @admin_required
    def team():
        db      = get_db()
        members = db.execute("SELECT * FROM team_members ORDER BY name").fetchall()

        _rows = db.execute("""
            SELECT
                referred_by,
                COUNT(*) as total,
                SUM(CASE WHEN status IN ('Converted','Fully Converted') THEN 1 ELSE 0 END) as converted,
                SUM(CASE WHEN payment_done=1              THEN 1 ELSE 0 END) as paid,
                SUM(payment_amount)                                           as revenue,
                SUM(CASE WHEN day1_done=1                 THEN 1 ELSE 0 END) as day1,
                SUM(CASE WHEN day2_done=1                 THEN 1 ELSE 0 END) as day2,
                SUM(CASE WHEN interview_done=1            THEN 1 ELSE 0 END) as interviews,
                SUM(CASE WHEN status='Seat Hold Confirmed' THEN 1 ELSE 0 END) as seat_holds,
                SUM(CASE WHEN status='Fully Converted'    THEN 1 ELSE 0 END) as fully_conv
            FROM leads WHERE in_pool=0 GROUP BY referred_by
        """).fetchall()
        _stats_map = {r['referred_by']: r for r in _rows}
        stats = [{'member': m, 'stats': _stats_map.get(m['name'])} for m in members]

        return render_template('team.html', stats=stats)


    @app.route('/team/add', methods=['POST'])
    @admin_required
    def add_team_member():
        name  = request.form.get('name', '').strip()
        phone = request.form.get('phone', '').strip()
        if not name:
            flash('Member name is required.', 'danger')
            return redirect(url_for('team'))
        db = get_db()
        try:
            db.execute("INSERT INTO team_members (name, phone) VALUES (?, ?)", (name, phone))
            db.commit()
            flash(f'Team member "{name}" added.', 'success')
        except Exception:
            flash(f'Member "{name}" already exists.', 'warning')
        return redirect(url_for('team'))


    @app.route('/team/<int:member_id>/delete', methods=['POST'])
    @admin_required
    def delete_team_member(member_id):
        db = get_db()
        member = db.execute("SELECT name FROM team_members WHERE id=?", (member_id,)).fetchone()
        if member:
            db.execute("DELETE FROM team_members WHERE id=?", (member_id,))
            db.commit()
            flash(f'Member "{member["name"]}" removed.', 'warning')
        return redirect(url_for('team'))


    @app.route('/team/day2-progress')
    @login_required
    def day2_progress():
        if session.get('role') != 'admin':
            flash('Access denied. Day 2 Board is admin only.', 'danger')
            return redirect(url_for('team_dashboard'))
        db = get_db()
        now = _now_ist()

        # All Day 2 leads visible to admin
        day2_leads = db.execute("""
            SELECT l.*,
                   CAST((julianday('now', '+5 hours', '+30 minutes') - julianday(l.updated_at)) * 24 AS INTEGER) AS hours_since_update
            FROM leads l
            WHERE l.in_pool=0 AND l.deleted_at='' AND l.status='Day 2'
            ORDER BY (l.d2_morning + l.d2_afternoon + l.d2_evening) DESC, l.updated_at ASC
        """).fetchall()

        day2_leads = _enrich_leads([dict(r) for r in day2_leads])

        # Summary counts
        complete_count    = sum(1 for l in day2_leads if l['d2_morning'] and l['d2_afternoon'] and l['d2_evening'])
        in_progress_count = sum(1 for l in day2_leads if 0 < (l['d2_morning']+l['d2_afternoon']+l['d2_evening']) < 3)
        not_started_count = sum(1 for l in day2_leads if (l['d2_morning']+l['d2_afternoon']+l['d2_evening']) == 0)

        can_edit = session.get('role') == 'admin'
        username = acting_username()

        # Build leader map: assignee username → upline_name (for admin view)
        leader_map = {}
        if can_edit and day2_leads:
            usernames_list = list(
                set(l.get('assignee_username') or '' for l in day2_leads if l.get('assignee_username'))
            )
            if usernames_list:
                ph = ','.join('?' * len(usernames_list))
                urows = db.execute(
                    f"SELECT username, upline_username, upline_name FROM users WHERE username IN ({ph})",
                    usernames_list
                ).fetchall()
                for r in urows:
                    leader_map[r['username']] = r['upline_username'] or r['upline_name'] or '—'

        # Day 2 batch videos for quick access
        d2_videos = {
            'morning_v1':   _get_setting(db, 'batch_d2_morning_v1', ''),
            'morning_v2':   _get_setting(db, 'batch_d2_morning_v2', ''),
            'afternoon_v1': _get_setting(db, 'batch_d2_afternoon_v1', ''),
            'afternoon_v2': _get_setting(db, 'batch_d2_afternoon_v2', ''),
            'evening_v1':   _get_setting(db, 'batch_d2_evening_v1', ''),
            'evening_v2':   _get_setting(db, 'batch_d2_evening_v2', ''),
        }

        return render_template('day2_progress.html',
            day2_leads=day2_leads,
            complete_count=complete_count,
            in_progress_count=in_progress_count,
            not_started_count=not_started_count,
            can_edit=can_edit,
            current_user=username,
            leader_map=leader_map,
            d2_videos=d2_videos,
            csrf_token=session.get('_csrf_token', ''),
        )

    @app.route('/leader/coaching')
    @login_required
    @safe_route
    def leader_coaching():
        """Coaching panel: each downline member's pipeline state + stuck leads."""
        role     = session.get('role', 'team')
        username = acting_username()

        if role not in ('leader', 'admin'):
            flash('Access denied.', 'danger')
            return redirect(url_for('team_dashboard'))

        db    = get_db()
        today = _today_ist().strftime('%Y-%m-%d')
        stale24_cutoff = (_now_ist() - datetime.timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')

        # Which leaders to show coaching cards for
        if role == 'admin':
            leader_rows = db.execute(
                "SELECT username FROM users WHERE role='leader' AND status='approved' ORDER BY username"
            ).fetchall()
            leaders_to_show = [r['username'] for r in leader_rows]
        else:
            leaders_to_show = [username]

        coaching_cards = []
        for leader_uname in leaders_to_show:
            downline_all = _get_downline_usernames(db, leader_uname)
            members      = [u for u in downline_all if u != leader_uname]

            for member in members:
                _muid = user_id_for_username(db, member)
                if _muid is None:
                    continue
                m_leads = db.execute("""
                    SELECT id, name, pipeline_stage, updated_at,
                           d1_morning, d1_afternoon, d1_evening,
                           d2_morning, d2_afternoon, d2_evening
                    FROM leads
                    WHERE assigned_user_id=? AND in_pool=0 AND deleted_at=''
                      AND pipeline_stage NOT IN ('complete','lost')
                """, (_muid,)).fetchall()

                active_count = len(m_leads)
                stuck_leads  = [dict(l) for l in m_leads
                                if (l['updated_at'] or '') < stale24_cutoff]
                stuck_count  = len(stuck_leads)

                # Batch completion %
                d1_leads = [l for l in m_leads if l['pipeline_stage'] == 'day1']
                d2_leads = [l for l in m_leads if l['pipeline_stage'] == 'day2']
                total_possible = (len(d1_leads) + len(d2_leads)) * 3
                batches_done = (
                    sum((l['d1_morning'] or 0) + (l['d1_afternoon'] or 0) + (l['d1_evening'] or 0)
                        for l in d1_leads) +
                    sum((l['d2_morning'] or 0) + (l['d2_afternoon'] or 0) + (l['d2_evening'] or 0)
                        for l in d2_leads)
                )
                batch_pct = round(batches_done / total_possible * 100) if total_possible else 100

                # Today's calls — use SSOT (distinct fresh leads called, not daily_scores which can double-count)
                score_row = db.execute(
                    "SELECT total_points, streak_days FROM daily_scores "
                    "WHERE username=? AND score_date=?", (member, today)
                ).fetchone()
                calls_today = count_distinct_valid_calls_on_date(db, member, today)
                pts_today   = score_row['total_points'] if score_row else 0

                # Stage breakdown
                stage_counts = {}
                for l in m_leads:
                    s = l['pipeline_stage'] or 'prospecting'
                    stage_counts[s] = stage_counts.get(s, 0) + 1

                coaching_cards.append({
                    'username':     member,
                    'upline':       leader_uname,
                    'active_count': active_count,
                    'stuck_count':  stuck_count,
                    'stuck_leads':  stuck_leads[:3],
                    'batch_pct':    batch_pct,
                    'calls_today':  calls_today,
                    'pts_today':    pts_today,
                    'stage_counts': stage_counts,
                })

        # Sort: most stuck first, then most active
        coaching_cards.sort(key=lambda c: (-c['stuck_count'], -c['active_count']))

        # Summary totals
        total_active = sum(c['active_count'] for c in coaching_cards)
        total_stuck  = sum(c['stuck_count']  for c in coaching_cards)

        # ── Monthly Pipeline Summary for leader (their team only) ────────
        if role == 'leader':
            my_downline = _get_downline_usernames(db, username)
        else:
            my_downline = []

        ldr_monthly_pipeline = []
        member_monthly = {}
        if role == 'leader' and my_downline:
            _dl_uids = [user_id_for_username(db, u) for u in my_downline]
            _dl_uids = [i for i in _dl_uids if i is not None]
            if not _dl_uids:
                pass
            else:
                _ph_uid = ','.join('?' * len(_dl_uids))
                ldr_monthly_pipeline = db.execute(f"""
                SELECT
                    strftime('%Y-%m', created_at) AS month,
                    COUNT(*) AS total_leads,
                    SUM(CASE WHEN pipeline_stage NOT IN ('prospecting','inactive','lost','') THEN 1 ELSE 0 END) AS enrolled_count,
                    SUM(CASE WHEN pipeline_stage IN ('day1','day2','day3','plan_2cc',
                        'seat_hold','pending','level_up','closing','complete','training') THEN 1 ELSE 0 END) AS reached_working,
                    SUM(CASE WHEN pipeline_stage IN ('seat_hold','pending','level_up',
                        'closing','complete','training') THEN 1 ELSE 0 END) AS reached_seat_hold,
                    SUM(CASE WHEN pipeline_stage IN ('closing','complete') THEN 1 ELSE 0 END) AS converted,
                    SUM(CASE WHEN pipeline_stage IN ('closing','complete') THEN track_price ELSE 0 END) AS revenue,
                    SUM(CASE WHEN pipeline_stage IN ('seat_hold','pending','level_up',
                        'closing','complete') THEN seat_hold_amount ELSE 0 END) AS seat_hold_budget,
                    SUM(CASE WHEN pipeline_stage IN ('closing','complete') THEN track_price
                             WHEN pipeline_stage IN ('seat_hold','pending','level_up') THEN seat_hold_amount
                             ELSE 0 END) AS total_budget
                FROM leads WHERE in_pool=0 AND deleted_at='' AND assigned_user_id IN ({_ph_uid})
                GROUP BY month ORDER BY month DESC LIMIT 6
                """, _dl_uids).fetchall()
                ldr_monthly_pipeline = [dict(r) for r in ldr_monthly_pipeline]
                for m in ldr_monthly_pipeline:
                    base = m['enrolled_count'] or 1
                    m['conv_pct']      = round(m['converted'] / base * 100, 1) if m['enrolled_count'] else 0
                    m['working_pct']   = round(m['reached_working'] / base * 100, 1) if m['enrolled_count'] else 0
                    m['seat_hold_pct'] = round(m['reached_seat_hold'] / base * 100, 1) if m['enrolled_count'] else 0

                for card in coaching_cards:
                    mem = card['username']
                    _cuid = user_id_for_username(db, mem)
                    if _cuid is None:
                        continue
                    rows = db.execute("""
                        SELECT
                            strftime('%Y-%m', created_at) AS month,
                            COUNT(*) AS total_leads,
                            SUM(CASE WHEN pipeline_stage IN ('closing','complete') THEN 1 ELSE 0 END) AS converted,
                            SUM(CASE WHEN pipeline_stage IN ('closing','complete') THEN track_price ELSE 0 END) AS revenue,
                            SUM(CASE WHEN pipeline_stage IN ('seat_hold','pending','level_up',
                                'closing','complete') THEN seat_hold_amount ELSE 0 END) AS seat_hold_budget,
                            SUM(CASE WHEN pipeline_stage IN ('closing','complete') THEN track_price
                                     WHEN pipeline_stage IN ('seat_hold','pending','level_up') THEN seat_hold_amount
                                     ELSE 0 END) AS total_budget
                        FROM leads WHERE in_pool=0 AND deleted_at='' AND assigned_user_id=?
                        GROUP BY month ORDER BY month DESC LIMIT 3
                    """, (_cuid,)).fetchall()
                    if rows:
                        member_monthly[mem] = [dict(r) for r in rows]

        return render_template('leader_coaching.html',
            coaching_cards=coaching_cards,
            role=role,
            total_active=total_active,
            total_stuck=total_stuck,
            ldr_monthly_pipeline=ldr_monthly_pipeline,
            member_monthly=member_monthly,
            csrf_token=session.get('_csrf_token', ''),
        )


