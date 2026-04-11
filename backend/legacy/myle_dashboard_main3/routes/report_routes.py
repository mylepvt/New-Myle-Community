"""
Report routes (team daily report submission, admin reports view, leader team reports).

Registered via register_report_routes(app) at the end of app.py load so helpers
on the app module are available without circular import at import time.
"""
from __future__ import annotations

import re
import datetime
from collections import defaultdict

from flask import (
    flash, jsonify, redirect, render_template, request, session, url_for,
)

from database import get_db
from auth_context import acting_username
from services.wallet_ledger import sum_pool_spent_for_buyer
from helpers import (
    LEAD_SQL_CALL_LOGGED,
    _get_actual_daily_counts,
    get_today_metrics,
    get_performance_ui_state,
    sql_ts_calendar_day,
    user_id_for_username,
)

_CALLING_STATUSES = frozenset({
    'Called - Interested', 'Called - No Answer',
    'Called - Follow Up',  'Called - Not Interested',
    'Called - Switch Off', 'Called - Busy',
    'Call Back',           'Wrong Number',
})
_LEAD_ID_RE = re.compile(r'Lead #(\d+)')
_STATUS_RE  = re.compile(r'call_status=(.+)$')


def register_report_routes(app):
    """Attach report-related URL rules to the Flask app (preserves endpoint names)."""
    from app import (  # noqa: PLC0415 — late import after app module is populated
        admin_required,
        login_required,
        safe_route,
        _get_setting,
        _set_setting,
        _log_activity,
        _now_ist,
        _today_ist,
        _upsert_daily_score,
        _check_and_award_badges,
        _get_network_usernames,
    )

    # ─────────────────────────────────────────────────────────────
    #  Daily Reports – Submit (team member)
    # ─────────────────────────────────────────────────────────────

    @app.route('/reports/submit', methods=['GET', 'POST'])
    @login_required
    @safe_route
    def report_submit():
        username = acting_username()
        today    = _today_ist().isoformat()
        db       = get_db()

        existing = db.execute(
            "SELECT * FROM daily_reports WHERE username=? AND report_date=?",
            (username, today)
        ).fetchone()

        actual_counts = _get_actual_daily_counts(db, username)

        if request.method == 'POST':
            report_date = request.form.get('report_date', today)
            upline_name = request.form.get('upline_name', '').strip()

            # ── All fields from user (manual report) ─────────────────
            try:
                total_calling    = int(request.form.get('total_calling') or 0)
                calls_picked     = int(request.form.get('calls_picked') or 0)
                wrong_numbers    = int(request.form.get('wrong_numbers') or 0)
                enrollments_done = int(request.form.get('enrollments_done') or 0)
                pending_enroll   = int(request.form.get('pending_enroll') or 0)
                underage         = int(request.form.get('underage') or 0)
                plan_2cc         = int(request.form.get('plan_2cc') or 0)
                seat_holdings    = int(request.form.get('seat_holdings') or 0)
            except ValueError:
                flash('Please enter valid numbers.', 'danger')
                return render_template('report_form.html', existing=existing, today=today,
                                       username=username, actual_counts=actual_counts)

            calls_not_picked = max(total_calling - calls_picked - wrong_numbers, 0)
            leads_educated   = request.form.get('leads_educated', '')
            remarks          = request.form.get('remarks', '').strip()

            # ── System counts for cross-check (stored in *_actual columns) ──
            sys_counts       = _get_actual_daily_counts(db, username, date=report_date)
            leads_claimed    = int(request.form.get('leads_claimed') or 0) if request.form.get('leads_claimed') else sys_counts['leads_claimed']

            now_ts = _now_ist().strftime('%Y-%m-%d %H:%M:%S')

            # *_actual columns store system-tracked values for admin cross-check
            sys_calls_made = sys_counts['total_calling']
            sys_leads_claimed = sys_counts['leads_claimed']
            sys_enrollments = sys_counts['enrollments_done']

            db.execute("""
                INSERT INTO daily_reports
                    (username, upline_name, report_date,
                     total_calling, calls_picked, calls_not_picked, wrong_numbers,
                     leads_claimed, enrollments_done,
                     pending_enroll, underage, leads_educated, plan_2cc, seat_holdings,
                     remarks, submitted_at, pdf_covered,
                     videos_sent_actual, calls_made_actual, payments_actual, system_verified)
                VALUES (?, ?, ?,
                        ?, ?, ?, ?,
                        ?, ?,
                        ?, ?, ?, ?, ?,
                        ?, ?, 0,
                        ?, ?, ?, 1)
                ON CONFLICT(username, report_date) DO UPDATE SET
                    upline_name=excluded.upline_name,
                    total_calling=excluded.total_calling,
                    calls_picked=excluded.calls_picked,
                    calls_not_picked=excluded.calls_not_picked,
                    wrong_numbers=excluded.wrong_numbers,
                    leads_claimed=excluded.leads_claimed,
                    enrollments_done=excluded.enrollments_done,
                    pending_enroll=excluded.pending_enroll,
                    underage=excluded.underage,
                    leads_educated=excluded.leads_educated,
                    plan_2cc=excluded.plan_2cc,
                    seat_holdings=excluded.seat_holdings,
                    remarks=excluded.remarks,
                    submitted_at=excluded.submitted_at,
                    videos_sent_actual=excluded.videos_sent_actual,
                    calls_made_actual=excluded.calls_made_actual,
                    payments_actual=excluded.payments_actual,
                    system_verified=1
            """, (username, upline_name, report_date,
                  total_calling, calls_picked, calls_not_picked, wrong_numbers,
                  leads_claimed, enrollments_done,
                  pending_enroll, underage, leads_educated, plan_2cc, seat_holdings,
                  remarks, now_ts,
                  sys_leads_claimed, sys_calls_made, sys_enrollments))
            _upsert_daily_score(db, username, 20)
            new_badges = _check_and_award_badges(db, username)
            db.commit()
            _log_activity(db, username, 'report_submit', f"Date: {report_date}")
            flash('Daily report submitted successfully!', 'success')
            return redirect(url_for('team_dashboard'))

        return render_template('report_form.html', existing=existing, today=today,
                               username=username, actual_counts=actual_counts)

    # ─────────────────────────────────────────────────────────────
    #  Daily Reports – Admin View
    # ─────────────────────────────────────────────────────────────

    @app.route('/reports')
    @admin_required
    @safe_route
    def reports_admin():
        db          = get_db()
        filter_date = request.args.get('date', '')
        filter_user = request.args.get('user', '')
        view        = request.args.get('view', 'daily')  # 'daily' or 'monthly'

        query  = "SELECT * FROM daily_reports WHERE 1=1"
        params = []
        if view == 'daily':
            if filter_date:
                query += " AND report_date=?"
                params.append(filter_date)
        if filter_user:
            query += " AND username=?"
            params.append(filter_user)
        query += " ORDER BY report_date DESC, submitted_at DESC"

        reports = db.execute(query, params).fetchall()

        totals = db.execute(f"""
            SELECT
                COUNT(DISTINCT username || report_date) AS total_reports,
                SUM(total_calling)    AS total_calling,
                SUM(COALESCE(leads_claimed, pdf_covered)) AS leads_claimed,
                SUM(calls_picked)     AS calls_picked,
                SUM(enrollments_done) AS enrollments_done,
                SUM(plan_2cc)         AS plan_2cc
            FROM daily_reports WHERE 1=1
            {'AND report_date=?' if (view == 'daily' and filter_date) else ''}
            {'AND username=?' if filter_user else ''}
        """, params).fetchone()

        members = db.execute(
            "SELECT DISTINCT username FROM daily_reports ORDER BY username"
        ).fetchall()

        today = _today_ist().isoformat()
        submitted_today = [r['username'] for r in db.execute(
            "SELECT username FROM daily_reports WHERE report_date=?", (today,)
        ).fetchall()]
        approved_team = [u['username'] for u in db.execute(
            "SELECT username FROM users WHERE role='team' AND status='approved'"
        ).fetchall()]
        missing_today = [u for u in approved_team if u not in submitted_today]

        user_filter_sql = 'AND username=?' if filter_user else ''
        user_filter_params = [filter_user] if filter_user else []

        if view == 'monthly':
            trend = db.execute(f"""
                SELECT strftime('%Y-%m', report_date) AS report_date,
                       COUNT(DISTINCT username)        AS reporters,
                       SUM(total_calling)              AS calling,
                       SUM(enrollments_done)           AS enrolments
                FROM daily_reports
                WHERE report_date >= date('now', '-365 days')
                {user_filter_sql}
                GROUP BY strftime('%Y-%m', report_date)
                ORDER BY report_date ASC
            """, user_filter_params).fetchall()

            monthly_reports = db.execute(f"""
                SELECT strftime('%Y-%m', report_date) AS month,
                       username,
                       SUM(total_calling)    AS total_calling,
                       SUM(pdf_covered)      AS pdf_covered,
                       SUM(calls_picked)     AS calls_picked,
                       SUM(enrollments_done) AS enrollments_done,
                       SUM(plan_2cc)         AS plan_2cc,
                       COUNT(*)              AS days_reported
                FROM daily_reports
                WHERE 1=1 {user_filter_sql}
                GROUP BY month, username
                ORDER BY month DESC, username
            """, user_filter_params).fetchall()
        else:
            trend = db.execute("""
                SELECT report_date,
                       COUNT(DISTINCT username)  AS reporters,
                       SUM(total_calling)        AS calling,
                       SUM(enrollments_done)     AS enrolments
                FROM daily_reports
                WHERE report_date >= date('now', '-13 days')
                GROUP BY report_date
                ORDER BY report_date ASC
            """).fetchall()
            monthly_reports = []

        return render_template('reports_admin.html',
                               reports=reports,
                               totals=totals,
                               members=members,
                               submitted_today=submitted_today,
                               missing_today=missing_today,
                               trend=trend,
                               monthly_reports=monthly_reports,
                               filter_date=filter_date,
                               filter_user=filter_user,
                               view=view,
                               today=today)

    # ─────────────────────────────────────────────────────────────
    #  Leader – Team Reports (read-only)
    # ─────────────────────────────────────────────────────────────

    @app.route('/leader/team-reports')
    @login_required
    @safe_route
    def leader_team_reports():
        """Leader sees daily reports for their downline — read only."""
        if session.get('role') not in ('leader', 'admin'):
            flash('Access denied.', 'danger')
            return redirect(url_for('team_dashboard'))

        username = acting_username()
        db = get_db()

        # Get downline
        if session.get('role') == 'admin':
            members = [r['username'] for r in db.execute(
                "SELECT username FROM users WHERE role IN ('team','leader') AND status='approved'"
            ).fetchall()]
        else:
            try:
                members = _get_network_usernames(db, username)
            except Exception:
                members = []
            members = [m for m in members if m != username]

        # Date filter from query param, default today
        date_filter = request.args.get('date', _today_ist().isoformat())

        reports = []
        if members:
            ph = ','.join('?' * len(members))
            reports = db.execute(f"""
                SELECT dr.*, u.phone as member_phone
                FROM daily_reports dr
                LEFT JOIN users u ON u.username = dr.username
                WHERE dr.username IN ({ph}) AND dr.report_date=?
                ORDER BY dr.submitted_at DESC
            """, members + [date_filter]).fetchall()

        # Who hasn't submitted
        submitted_set = {r['username'] for r in reports}
        missing = [m for m in members if m not in submitted_set]

        # Summary totals
        def _safe_sum(key):
            """Sum a column that might not exist in old rows."""
            total = 0
            for r in reports:
                try:
                    total += (r[key] or 0)
                except (IndexError, KeyError):
                    pass
            return total

        summary = {
            'total_calling':    _safe_sum('total_calling'),
            'leads_claimed':    _safe_sum('leads_claimed') or _safe_sum('pdf_covered'),
            'calls_picked':     _safe_sum('calls_picked'),
            'enrollments_done': _safe_sum('enrollments_done'),
            'plan_2cc':         _safe_sum('plan_2cc'),
            'seat_holdings':    _safe_sum('seat_holdings'),
        }

        # ── Live aggregation from leads table (always up-to-date) ──
        live_summary = {
            'leads_claimed_today': 0,
            'calls_made_today':    0,
            'enrolled_today':      0,
            'day1_total':          0,
            'day2_total':          0,
            'converted_total':     0,
        }
        if members:
            member_ids = [user_id_for_username(db, m) for m in members]
            member_ids = [i for i in member_ids if i is not None]
            today_str = date_filter
            if member_ids:
                ph = ','.join('?' * len(member_ids))
                _today_m = get_today_metrics(db, day_iso=today_str, user_ids=member_ids)
                lc = _today_m['claimed']
                cm = _today_m['calls']
                en = _today_m['enrolled']
                d1 = db.execute(
                    f"SELECT COUNT(*) FROM leads WHERE assigned_user_id IN ({ph}) AND in_pool=0 "
                    f"AND deleted_at='' AND status='Day 1'",
                    (*member_ids,),
                ).fetchone()[0]
                d2 = db.execute(
                    f"SELECT COUNT(*) FROM leads WHERE assigned_user_id IN ({ph}) AND in_pool=0 "
                    f"AND deleted_at='' AND status='Day 2'",
                    (*member_ids,),
                ).fetchone()[0]
                cv = db.execute(
                    f"SELECT COUNT(*) FROM leads WHERE assigned_user_id IN ({ph}) AND in_pool=0 "
                    f"AND deleted_at='' AND status IN ('Converted','Fully Converted')",
                    (*member_ids,),
                ).fetchone()[0]
                live_summary = {
                    'leads_claimed_today': lc,
                    'calls_made_today':    cm,
                    'enrolled_today':      en,
                    'day1_total':          d1,
                    'day2_total':          d2,
                    'converted_total':     cv,
                }

        perf_state = None
        if session.get('role') == 'leader':
            perf_state = get_performance_ui_state(db, username)
            db.commit()

        d2_eval_rows = []
        if members:
            _d2_ids = [user_id_for_username(db, m) for m in members]
            _d2_ids = [i for i in _d2_ids if i is not None]
            if _d2_ids:
                ph = ','.join('?' * len(_d2_ids))
                d2_eval_rows = db.execute(
                    f"""
                    SELECT l.id, l.name, COALESCE(u.username, '') AS assigned_to, l.status,
                           l.test_status, l.test_score, l.test_attempts, l.test_completed_at
                    FROM leads l
                    LEFT JOIN users u ON u.id = l.assigned_user_id
                    WHERE l.in_pool=0 AND l.deleted_at='' AND l.assigned_user_id IN ({ph})
                      AND (
                        l.status='Day 2'
                        OR COALESCE(l.test_attempts,0) > 0
                        OR LOWER(COALESCE(l.test_status,'')) IN ('passed','failed','retry')
                      )
                    ORDER BY u.username, l.id
                    """,
                    _d2_ids,
                ).fetchall()

        # ── Pending ₹196 proof screenshots for this leader's downline ──
        pending_proofs = []
        if members:
            _proof_ids = [user_id_for_username(db, m) for m in members]
            _proof_ids = [i for i in _proof_ids if i is not None]
            if _proof_ids:
                ph = ','.join('?' * len(_proof_ids))
                pending_proofs = db.execute(
                    f"""
                    SELECT l.id, l.name, l.phone, l.payment_proof_path,
                           l.payment_proof_approval_status, l.updated_at,
                           COALESCE(u.username, '') AS assigned_to
                    FROM leads l
                    LEFT JOIN users u ON u.id = l.assigned_user_id
                    WHERE l.in_pool=0 AND l.deleted_at=''
                      AND l.assigned_user_id IN ({ph})
                      AND LOWER(COALESCE(l.payment_proof_approval_status,'')) = 'pending'
                      AND TRIM(COALESCE(l.payment_proof_path,'')) != ''
                    ORDER BY l.updated_at DESC
                    """,
                    _proof_ids,
                ).fetchall()

        return render_template('leader_team_reports.html',
                               reports=reports,
                               missing=missing,
                               members=members,
                               summary=summary,
                               live_summary=live_summary,
                               date_filter=date_filter,
                               today=_today_ist().isoformat(),
                               perf_state=perf_state or {},
                               d2_eval_rows=d2_eval_rows,
                               pending_proofs=pending_proofs,
                               csrf_token=session.get('_csrf_token', ''))

    @app.route('/enrollment-approvals')
    @login_required
    @safe_route
    def enrollment_approvals():
        """Dedicated ₹196 screenshot approval queue for leader/admin."""
        role = session.get('role')
        if role not in ('leader', 'admin'):
            flash('Access denied.', 'danger')
            return redirect(url_for('team_dashboard'))

        username = acting_username()
        db = get_db()
        pending_proofs = []
        member_ids: list[int] = []

        _today_iso = _today_ist().isoformat()
        _hd_raw = (request.args.get('history_date') or '').strip()[:10]
        if len(_hd_raw) == 10 and _hd_raw[4] == '-' and _hd_raw[7] == '-':
            history_date = _hd_raw
        else:
            history_date = _today_iso

        if role == 'admin':
            pending_proofs = db.execute(
                """
                SELECT l.id, l.name, l.phone, l.payment_proof_path,
                       l.payment_proof_approval_status, l.updated_at,
                       COALESCE(u.username, '') AS assigned_to,
                       COALESCE(u.role, '') AS assigned_role
                FROM leads l
                LEFT JOIN users u ON u.id = l.assigned_user_id
                WHERE l.in_pool=0 AND l.deleted_at=''
                  AND LOWER(COALESCE(l.payment_proof_approval_status,''))='pending'
                  AND TRIM(COALESCE(l.payment_proof_path,''))!=''
                ORDER BY l.updated_at DESC
                """
            ).fetchall()
        else:
            try:
                members = _get_network_usernames(db, username)
            except Exception:
                members = []
            members = [m for m in members if m != username]
            member_ids = [user_id_for_username(db, m) for m in members]
            member_ids = [i for i in member_ids if i is not None]
            if member_ids:
                ph = ','.join('?' * len(member_ids))
                pending_proofs = db.execute(
                    f"""
                    SELECT l.id, l.name, l.phone, l.payment_proof_path,
                           l.payment_proof_approval_status, l.updated_at,
                           COALESCE(u.username, '') AS assigned_to,
                           COALESCE(u.role, '') AS assigned_role
                    FROM leads l
                    LEFT JOIN users u ON u.id = l.assigned_user_id
                    WHERE l.in_pool=0 AND l.deleted_at=''
                      AND l.assigned_user_id IN ({ph})
                      AND LOWER(COALESCE(l.payment_proof_approval_status,''))='pending'
                      AND TRIM(COALESCE(l.payment_proof_path,''))!=''
                    ORDER BY l.updated_at DESC
                    """,
                    member_ids,
                ).fetchall()

        # ── Calendar day history: approved / rejected ₹196 proofs (review timestamp) ──
        proof_history = []
        history_approved_n = 0
        history_rejected_n = 0
        _hist_sql = """
            SELECT l.id, l.name, l.phone, l.payment_proof_path,
                   l.payment_proof_approval_status AS appr_status,
                   l.payment_proof_reviewed_at, l.payment_proof_reviewed_by,
                   l.payment_proof_reject_note,
                   COALESCE(u.username, '') AS assigned_to,
                   COALESCE(u.role, '') AS assigned_role,
                   COALESCE(u.upline_username, '') AS leader_username,
                   TRIM(COALESCE(ul.name, '')) AS leader_name
            FROM leads l
            LEFT JOIN users u ON u.id = l.assigned_user_id
            LEFT JOIN users ul ON ul.username = u.upline_username
            WHERE l.in_pool=0 AND l.deleted_at=''
              AND TRIM(COALESCE(l.payment_proof_reviewed_at,''))!=''
              AND date(substr(trim(l.payment_proof_reviewed_at), 1, 10)) = date(?)
              AND LOWER(TRIM(COALESCE(l.payment_proof_approval_status,''))) IN ('approved','rejected')
        """
        if role == 'admin':
            proof_history = db.execute(
                _hist_sql + " ORDER BY l.payment_proof_reviewed_at DESC",
                (history_date,),
            ).fetchall()
        elif member_ids:
            ph2 = ','.join('?' * len(member_ids))
            proof_history = db.execute(
                _hist_sql + f" AND l.assigned_user_id IN ({ph2}) ORDER BY l.payment_proof_reviewed_at DESC",
                (history_date, *member_ids),
            ).fetchall()
        for _h in proof_history:
            _st = (str(_h['appr_status'] or '')).lower()
            if _st == 'approved':
                history_approved_n += 1
            elif _st == 'rejected':
                history_rejected_n += 1

        return render_template(
            'enrollment_approvals.html',
            pending_proofs=pending_proofs,
            role=role,
            history_date=history_date,
            proof_history=proof_history,
            history_approved_n=history_approved_n,
            history_rejected_n=history_rejected_n,
            today_iso=_today_iso,
            csrf_token=session.get('_csrf_token', ''),
        )

    @app.route('/admin/stabilization/watch')
    @admin_required
    @safe_route
    def admin_stabilization_watch():
        """
        Production watchlist endpoint for stabilization window.
        Returns current counters for top 5 risk signals.
        """
        db = get_db()
        today = _today_ist().isoformat()
        now_24h = (_now_ist() - datetime.timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')

        dup_phone_rows = db.execute(
            """
            SELECT COUNT(*) FROM (
              SELECT phone
              FROM leads
              WHERE in_pool=0 AND deleted_at='' AND TRIM(COALESCE(phone,''))!=''
              GROUP BY phone
              HAVING COUNT(*) > 1
            ) t
            """
        ).fetchone()[0] or 0

        status_skip_today = db.execute(
            """
            SELECT COUNT(*) FROM activity_log
            WHERE event_type='status_skip_blocked' AND DATE(created_at)=DATE(?)
            """,
            (today,),
        ).fetchone()[0] or 0
        rel_claim_fail_today = db.execute(
            """
            SELECT COUNT(*) FROM activity_log
            WHERE event_type='reliability_claim_failure' AND DATE(created_at)=DATE(?)
            """,
            (today,),
        ).fetchone()[0] or 0
        rel_invalid_review_today = db.execute(
            """
            SELECT COUNT(*) FROM activity_log
            WHERE event_type='reliability_invalid_review_action' AND DATE(created_at)=DATE(?)
            """,
            (today,),
        ).fetchone()[0] or 0
        rel_forbidden_review_today = db.execute(
            """
            SELECT COUNT(*) FROM activity_log
            WHERE event_type='reliability_review_forbidden' AND DATE(created_at)=DATE(?)
            """,
            (today,),
        ).fetchone()[0] or 0
        status_update_blocked_today = db.execute(
            """
            SELECT COUNT(*) FROM activity_log
            WHERE event_type='status_update_blocked' AND DATE(created_at)=DATE(?)
            """,
            (today,),
        ).fetchone()[0] or 0

        stuck_24h = db.execute(
            """
            SELECT COUNT(*) FROM leads
            WHERE in_pool=0 AND deleted_at=''
              AND status NOT IN ('Fully Converted','Converted','Lost')
              AND updated_at <= ?
            """,
            (now_24h,),
        ).fetchone()[0] or 0

        approved_rows = db.execute(
            "SELECT id, username FROM users WHERE role IN ('team','leader') AND status='approved'"
        ).fetchall()
        approved_ids = [r['id'] for r in approved_rows if r['id'] is not None]

        admin_m = get_today_metrics(db, day_iso=today, approved_only=True)
        agg_m = get_today_metrics(db, day_iso=today, user_ids=approved_ids) if approved_ids else {
            'claimed': 0, 'enrolled': 0, 'calls': 0
        }
        enroll_mismatch = int(
            (admin_m['claimed'] != agg_m['claimed']) or (admin_m['enrolled'] != agg_m['enrolled'])
        )

        wallet_mismatch_users = []
        for r in approved_rows:
            _run = (r['username'] or '').strip()
            spent_sql = sum_pool_spent_for_buyer(db, _run)
            # Wallet helper logic equivalent here for safety/readability.
            recharged = db.execute(
                """
                SELECT COALESCE(SUM(amount),0) FROM wallet_recharges
                WHERE username=? AND status='approved'
                """,
                (r['username'],),
            ).fetchone()[0] or 0
            balance = float(recharged) - float(spent_sql)
            if balance < -0.01:
                wallet_mismatch_users.append(r['username'])

        payload = {
            'ok': True,
            'watchlist': {
                'duplicate_lead_assignment': int(dup_phone_rows),
                'wallet_mismatch_users': len(wallet_mismatch_users),
                'status_skip_attempts_today': int(status_skip_today),
                'status_update_blocked_today': int(status_update_blocked_today),
                'reliability_claim_failures_today': int(rel_claim_fail_today),
                'reliability_invalid_review_actions_today': int(rel_invalid_review_today),
                'reliability_forbidden_review_actions_today': int(rel_forbidden_review_today),
                'stuck_leads_24h_plus': int(stuck_24h),
                'enrollment_count_mismatch': int(enroll_mismatch),
            },
            'metrics_snapshot': {
                'admin_ssot': admin_m,
                'aggregate_ssot': agg_m,
            },
            'feature_flags': {
                'strict_flow_guard_enabled': (_get_setting(db, 'strict_flow_guard_enabled', '1') or '1'),
                'maintenance_mode': (_get_setting(db, 'maintenance_mode', '0') or '0'),
            },
        }
        return jsonify(payload)

    @app.route('/admin/stabilization/toggle', methods=['POST'])
    @admin_required
    @safe_route
    def admin_stabilization_toggle():
        """Instant rollback/feature control for stabilization flags."""
        data = request.get_json(silent=True) or {}
        key = ((request.form.get('key') or data.get('key') or '')).strip()
        value = ((request.form.get('value') or data.get('value') or '')).strip()
        if key not in ('strict_flow_guard_enabled', 'maintenance_mode'):
            return jsonify({'ok': False, 'error': 'Unsupported key'}), 400
        if value.lower() not in ('0', '1', 'true', 'false', 'on', 'off', 'yes', 'no'):
            return jsonify({'ok': False, 'error': 'Invalid value'}), 400
        db = get_db()
        _set_setting(db, key, value)
        _log_activity(db, acting_username(), 'stabilization_toggle', f'{key}={value}')
        db.commit()
        return jsonify({'ok': True, 'key': key, 'value': value})

    @app.route('/admin/reliability/reconcile', methods=['GET'])
    @admin_required
    @safe_route
    def admin_reliability_reconcile():
        """
        Source-of-truth reconciliation snapshot for critical KPIs + owner invariants.
        """
        db = get_db()
        today = _today_ist().isoformat()
        approved_rows = db.execute(
            "SELECT id, username FROM users WHERE role IN ('team','leader') AND status='approved'"
        ).fetchall()
        approved_ids = [r['id'] for r in approved_rows if r['id'] is not None]

        admin_m = get_today_metrics(db, day_iso=today, approved_only=True)
        agg_m = get_today_metrics(db, day_iso=today, user_ids=approved_ids) if approved_ids else {
            'claimed': 0, 'enrolled': 0, 'calls': 0
        }

        orphan_off_pool = db.execute(
            "SELECT COUNT(*) FROM leads WHERE in_pool=0 AND (assigned_user_id IS NULL OR assigned_user_id=0)"
        ).fetchone()[0] or 0
        pool_owner_not_null = db.execute(
            "SELECT COUNT(*) FROM leads WHERE in_pool=1 AND COALESCE(assigned_user_id,0)!=0"
        ).fetchone()[0] or 0

        mismatches = {
            'claimed_today': int(admin_m.get('claimed', 0) or 0) - int(agg_m.get('claimed', 0) or 0),
            'enrolled_today': int(admin_m.get('enrolled', 0) or 0) - int(agg_m.get('enrolled', 0) or 0),
            'calls_today': int(admin_m.get('calls', 0) or 0) - int(agg_m.get('calls', 0) or 0),
            'off_pool_owner_missing': int(orphan_off_pool),
            'pool_owner_not_null': int(pool_owner_not_null),
        }
        ok = all(v == 0 for v in mismatches.values())
        payload = {
            'ok': ok,
            'date': today,
            'mismatches': mismatches,
            'admin_ssot': admin_m,
            'aggregate_ssot': agg_m,
        }
        return jsonify(payload), (200 if ok else 409)

    # ─────────────────────────────────────────────────────────────
    #  Admin – Backfill calls_made from activity_log (one-time fix)
    # ─────────────────────────────────────────────────────────────

    @app.route('/admin/backfill-calls-made', methods=['POST'])
    @admin_required
    @safe_route
    def admin_backfill_calls_made():
        """
        Rebuild daily_scores.calls_made for ALL users from activity_log.
        Counts unique lead IDs per (user, date) that had any calling-type
        call_status update.  Falls back to leads table when log is empty.
        Safe to run multiple times (idempotent).
        """
        db = get_db()

        # ── Read activity_log ──────────────────────────────────────────────
        log_rows = db.execute("""
            SELECT username,
                   DATE(created_at) AS log_date,
                   details
            FROM   activity_log
            WHERE  event_type = 'call_status_update'
            ORDER  BY created_at
        """).fetchall()

        calls_per_day: dict = defaultdict(lambda: defaultdict(set))

        for row in log_rows:
            details = row['details'] or ''
            m_id     = _LEAD_ID_RE.search(details)
            m_status = _STATUS_RE.search(details)
            if not m_id or not m_status:
                continue
            status = m_status.group(1).strip()
            if status in _CALLING_STATUSES:
                calls_per_day[row['username']][row['log_date']].add(int(m_id.group(1)))

        source = 'activity_log'

        # ── Fallback: use leads table when log has no data ─────────────────
        if not calls_per_day:
            source = 'leads_table'
            _upd_b = sql_ts_calendar_day("l.updated_at")
            lead_rows = db.execute(f"""
                SELECT u.username AS username,
                       {_upd_b} AS upd_date,
                       l.id
                FROM   leads l
                INNER JOIN users u ON u.id = l.assigned_user_id
                WHERE  l.call_status IN (
                           'Called - Interested', 'Called - No Answer',
                           'Called - Follow Up',  'Called - Not Interested',
                           'Called - Switch Off',  'Called - Busy',
                           'Call Back',            'Wrong Number'
                       )
                  AND  l.deleted_at = ''
                  AND  l.in_pool    = 0
                  AND  l.assigned_user_id IS NOT NULL
            """).fetchall()
            for r in lead_rows:
                if r['username'] and r['upd_date']:
                    calls_per_day[r['username']][r['upd_date']].add(r['id'])

        # ── Apply updates ──────────────────────────────────────────────────
        updated = 0
        inserted = 0
        for username, dates in calls_per_day.items():
            for date, lead_ids in dates.items():
                new_count = len(lead_ids)
                existing = db.execute(
                    "SELECT id FROM daily_scores WHERE username=? AND score_date=?",
                    (username, date)
                ).fetchone()
                if existing:
                    db.execute(
                        "UPDATE daily_scores SET calls_made=? WHERE username=? AND score_date=?",
                        (new_count, username, date),
                    )
                    updated += 1
                else:
                    db.execute("""
                        INSERT OR IGNORE INTO daily_scores
                            (username, score_date, calls_made, videos_sent, batches_marked,
                             payments_collected, total_points, streak_days)
                        VALUES (?, ?, ?, 0, 0, 0, 0, 1)
                    """, (username, date, new_count))
                    inserted += 1

        db.commit()

        # Sync users.total_points from daily_scores to prevent divergence
        user_totals = db.execute(
            "SELECT username, SUM(total_points) AS tp FROM daily_scores GROUP BY username"
        ).fetchall()
        for _row in user_totals:
            db.execute(
                "UPDATE users SET total_points=? WHERE LOWER(username)=LOWER(?)",
                (int(_row['tp'] or 0), _row['username']),
            )
        db.commit()

        return jsonify({
            'ok': True,
            'source': source,
            'users_processed': len(calls_per_day),
            'rows_updated': updated,
            'rows_inserted': inserted,
            'message': f'Backfill complete — {updated} updated, {inserted} inserted (source: {source})',
        })
