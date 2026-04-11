from __future__ import annotations
import csv, io, datetime, json, logging, os, re, secrets, threading, urllib.request as _urllib_req

from flask import flash, redirect, render_template, request, session, url_for, jsonify, Response

from database import get_db
from decorators import login_required, admin_required, safe_route
from auth_context import acting_username, acting_user_id
from reliability import emit_event, incident_code, safe_user_error
from services.hierarchy_lead_sync import nearest_approved_leader_username
from helpers import (
    WORKING_BOARD_HOME_STATUSES,
    sqlite_row_get,
    user_id_for_username,
    network_user_ids_for_username,
    _assignee_username_for_lead,
    _get_setting,
    _now_ist,
    _today_ist,
    _get_downline_usernames,
    _enrich_leads,
    _get_network_usernames,
    apply_call_outcome_discipline,
    followup_discipline_process_overdue,
    compute_step8_quick_feedback_for_assignee,
    lead_day2_business_test_passed,
    call_result_allowed,
    payment_amount_when_marking_paid,
    payment_fields_after_status_change,
    normalize_lead_payment_row,
    apply_leads_update,
    validate_lead_business_rules,
    payment_columns_mark_paid,
    touch_lead_updated_at,
    _get_admin_username,
    is_valid_forward_status_transition,
    leader_own_assigned_lead,
    payment_proof_approval_status_value,
    rupees_196_execution_blocked_for_role,
    can_review_rupees_196_proof,
    assert_lead_owner_invariant,
    team_status_dropdown_choices,
    actor_may_use_assignee_execution_routes,
    _auto_expire_pipeline_leads,
    _auto_expire_pipeline_leads_batch,
    _expire_all_pipeline_leads,
)

_ROUTE_LOG = logging.getLogger(__name__)


def _ntfy_day2_contact(db, lead):
    """POST lead name+phone to ntfy.sh so iPhone Shortcut auto-saves contact."""
    try:
        topic = (_get_setting(db, 'ntfy_day2_topic', '') or '').strip()
        if not topic:
            return
        name  = (lead['name']  or '').strip()
        phone = (lead['phone'] or '').strip()
        payload = json.dumps({'name': name, 'phone': phone}).encode()
        req = _urllib_req.Request(
            f'https://ntfy.sh/{topic}',
            data=payload,
            headers={
                'Content-Type': 'application/json',
                'Title': f'Day 2 Contact: {name}',
                'Tags': 'iphone,busts_in_silhouette',
                'Priority': 'default',
            },
            method='POST',
        )
        _urllib_req.urlopen(req, timeout=5)
    except Exception:
        pass  # never block the main flow


def register_lead_routes(app):
    from app import (
        _push_to_users, _upsert_daily_score, _log_activity, _log_lead_event,
        STATUSES, CALL_RESULT_TAGS, CALL_STATUS_VALUES, TEAM_CALL_STATUS_VALUES, SOURCES, PAYMENT_AMOUNT,
        STATUS_TO_STAGE, TRACKS, PIPELINE_AUTO_EXPIRE_STATUSES, SLA_SOFT_WATCH_EXCLUDE,
        _transition_stage,
        FOLLOWUP_TAGS, _check_and_award_badges, BADGE_DEFS, RETARGET_TAGS,
        _public_external_url, _extract_leads_from_pdf, _push_all_team, _BATCH_SLOTS,
        _get_today_score, _get_wallet, _set_setting,
        TEAM_FORBIDDEN_STATUSES, TEAM_ALLOWED_STATUSES,
    )

    from services.scoring_service import add_points

    def _is_fresh_lead(lead_row) -> bool:
        """A lead qualifies for points/call-count if claimed today OR created today (personal add/upload)."""
        today = _today_ist().isoformat()
        claimed = (sqlite_row_get(lead_row, 'claimed_at') or '').strip()
        if claimed and claimed[:10] == today:
            return True
        created = (sqlite_row_get(lead_row, 'created_at') or '').strip()
        if created and created[:10] == today and not claimed:
            return True
        return False

    def _leader_day1_routing_on(db, leader_username: str) -> bool:
        """Check if Day 1 auto-routing is allowed for this execution owner.

        Leaders use the admin-toggle `day1_routing_on`. When execution falls back to
        admin (no upline leader), proof-approve auto Day 1 must not fail the leader-only
        lookup — otherwise approved leads stay on Paid ₹196 and never appear on Day 1.

        Set env ``DAY1_ROUTING_DEBUG=1`` to log each decision at INFO (owner username → bool).
        """
        if not leader_username:
            out = False
        else:
            row = db.execute(
                "SELECT day1_routing_on, role FROM users WHERE username=? LIMIT 1",
                (leader_username,),
            ).fetchone()
            if not row:
                out = False
            else:
                role = ((row["role"] or "") or "").strip().lower()
                if role == "admin":
                    out = True
                elif role != "leader":
                    out = False
                else:
                    out = bool(int(row["day1_routing_on"] or 0))
        if (os.environ.get("DAY1_ROUTING_DEBUG") or "").strip().lower() in (
            "1",
            "true",
            "yes",
        ):
            app.logger.info("day1_routing_check username=%r -> %s", leader_username, out)
        return out

    def _team_handoff_to_leader(db, lead_id: int, lead_row, now_str: str) -> bool:
        """After team records ₹196, route execution to leader but keep buyer owner locked."""
        owner_team = (acting_username() or "").strip()
        leader_un = (nearest_approved_leader_username(db, owner_team) or "").strip()
        if not leader_un:
            db.execute(
                "UPDATE leads SET enrolled_at=?, enrolled_by=?, updated_at=? "
                "WHERE id=? AND TRIM(COALESCE(enrolled_at,''))=''",
                (now_str, owner_team, now_str, lead_id),
            )
            _log_activity(
                db,
                owner_team,
                "team_enroll_196_held",
                f"Lead #{lead_id} paid ₹196 → no approved leader in upline; execution stays on team",
            )
            return False
        leader_uid = user_id_for_username(db, leader_un)
        if not _leader_day1_routing_on(db, leader_un):
            db.execute(
                "UPDATE leads SET enrolled_at=?, enrolled_by=?, updated_at=? "
                "WHERE id=? AND TRIM(COALESCE(enrolled_at,''))=''",
                (now_str, owner_team, now_str, lead_id),
            )
            _log_activity(db, owner_team, "team_enroll_196_held",
                          f"Lead #{lead_id} paid ₹196 → execution held for @{leader_un} (Day 1 routing OFF)")
            return False
        upd = {
            "status": "Day 1",
            "pipeline_stage": "day1",
            "flow_started_at": now_str,
            "updated_at": now_str,
            "pipeline_entered_at": now_str,
        }
        if leader_uid:
            upd["assigned_user_id"] = leader_uid
        apply_leads_update(
            db,
            upd,
            where_sql="id=? AND in_pool=0 AND deleted_at=''",
            where_params=(lead_id,),
            log_context="team_paid196_handoff",
        )
        db.execute(
            "UPDATE leads SET enrolled_at=?, enrolled_by=? WHERE id=? AND TRIM(COALESCE(enrolled_at,''))=''",
            (now_str, owner_team, lead_id),
        )
        _log_activity(
            db,
            owner_team,
            "team_enroll_196",
            f"Lead #{lead_id} paid ₹196 and execution routed to @{leader_un}",
        )
        return True

    def _role_owns_status(role: str, status: str) -> bool:
        s = (status or '').strip()
        if s in ('Day 1',):
            return role in ('leader', 'admin')
        if s in ('Day 2',):
            return role in ('leader', 'admin')
        if s in ('Interview', 'Track Selected', 'Seat Hold Confirmed', 'Fully Converted'):
            return role in ('leader', 'admin')
        return True

    def _strict_flow_guard_enabled(db) -> bool:
        raw = (_get_setting(db, 'strict_flow_guard_enabled', '1') or '').strip().lower()
        return raw not in ('0', 'false', 'off', 'no')

    def _rupees_196_gate_enabled(db) -> bool:
        raw = (_get_setting(db, 'gate_rupees_196_enabled', '1') or '').strip().lower()
        return raw not in ('0', 'false', 'off', 'no')

    @app.route('/leads')
    @login_required
    @safe_route
    def leads():
        import traceback as _tb
        try:
            return _leads_inner()
        except Exception as e:
            app.logger.error(f"leads() CRASH: {e}\n{_tb.format_exc()}")
            flash(f'Leads page error: {e}', 'danger')
            if session.get('role') == 'admin':
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('team_dashboard'))

    def _leads_inner():
        from datetime import timedelta as _td
        db     = get_db()
        role_leads = session.get('role')
        uname_leads = acting_username()
        # Same pipeline 24h → Inactive pass as Working / Dashboard (lists stay fresh)
        try:
            if role_leads == 'admin':
                _expire_all_pipeline_leads(db)
            elif role_leads == 'leader':
                try:
                    _dl = [u for u in _get_network_usernames(db, uname_leads) if u != uname_leads]
                except Exception:
                    _dl = []
                try:
                    _auto_expire_pipeline_leads_batch(db, [uname_leads] + list(_dl))
                except Exception:
                    pass
            elif role_leads:
                try:
                    _auto_expire_pipeline_leads(db, uname_leads)
                except Exception:
                    pass
        except Exception:
            pass

        status = request.args.get('status', '')
        search = request.args.get('q', '').strip()
        page   = max(1, int(request.args.get('page', 1)))
        today      = _today_ist().isoformat()
        today_lo   = today + ' 00:00:00'
        tomorrow_lo = (_today_ist() + _td(days=1)).isoformat() + ' 00:00:00'

        # Retarget stays active on assignee — show in My Leads/History (Lost remains archive-only).
        base   = "SELECT * FROM leads WHERE in_pool=0 AND deleted_at='' AND status != 'Lost'"
        role   = role_leads
        uname  = uname_leads

        # Today = claimed today only (claimed_at = today)
        # History = everything else (not claimed today, or never claimed)
        today_cond = "(claimed_at IS NOT NULL AND claimed_at >= ? AND claimed_at < ?)"

        def _apply_filters(base_q, base_p, extra_cond, extra_p):
            q = base_q + f" AND {extra_cond}"
            p = list(base_p) + list(extra_p)
            if status:
                q += " AND status=?"; p.append(status)
            if search:
                if role == 'admin':
                    q += (" AND (name LIKE ? OR phone LIKE ? OR email LIKE ? OR EXISTS ("
                          "SELECT 1 FROM users u WHERE u.id = leads.assigned_user_id "
                          "AND (u.username LIKE ? OR u.name LIKE ? OR u.fbo_id LIKE ?)))")
                    p += [f'%{search}%', f'%{search}%', f'%{search}%',
                          f'%{search}%', f'%{search}%', f'%{search}%']
                else:
                    q += " AND (name LIKE ? OR phone LIKE ? OR email LIKE ?)"
                    p += [f'%{search}%', f'%{search}%', f'%{search}%']
            return q, p

        base_params = []
        if role != 'admin':
            if role == 'leader':
                # Leaders see execution (assigned_user_id / stale_worker) and pool rows they bought
                # (current_owner = self). Handoff only moves assigned_user_id; current_owner never follows.
                base_params = [int(session['user_id']), uname, uname]
                base += " AND (assigned_user_id=? OR stale_worker=? OR current_owner=?)"
            else:
                base_params = [int(session['user_id']), uname]
                base += " AND (assigned_user_id=? OR stale_worker=?)"

        today_q, today_p = _apply_filters(
            base, base_params,
            today_cond, [today_lo, tomorrow_lo]
        )
        hist_q, hist_p = _apply_filters(
            base, base_params,
            f"NOT {today_cond}", [today_lo, tomorrow_lo]
        )

        _today_limit = 60
        _hist_limit  = 80
        _hist_offset = (page - 1) * _hist_limit
        try:
            today_leads_raw = db.execute(
                today_q + " ORDER BY created_at DESC LIMIT " + str(_today_limit), today_p
            ).fetchall()
            hist_leads_raw  = db.execute(
                hist_q  + " ORDER BY created_at DESC LIMIT ? OFFSET ?",
                hist_p + [_hist_limit + 1, _hist_offset]
            ).fetchall()
        except Exception as e:
            app.logger.error(f"leads() query failed: {e}")
            today_leads_raw, hist_leads_raw = [], []
        has_more_hist = len(hist_leads_raw) > _hist_limit
        if has_more_hist:
            hist_leads_raw = hist_leads_raw[:_hist_limit]
        # Use actual usernames from users table so assigned_to matches acting_username()
        team            = db.execute(
            "SELECT username AS name FROM users "
            "WHERE role IN ('team','leader') AND status='approved' ORDER BY username"
        ).fetchall()

        call_scripts = {
            'opening':       _get_setting(db, 'script_opening',       ''),
            'qualification': _get_setting(db, 'script_qualification', ''),
            'pitch':         _get_setting(db, 'script_pitch',         ''),
            'closing':       _get_setting(db, 'script_closing',       ''),
        }
        try:
            call_target = int(_get_setting(db, 'call_target_daily', '50') or 50)
        except (ValueError, TypeError):
            call_target = 50

        # Enrich with heat + next_action
        try:
            today_leads = _enrich_leads(today_leads_raw)
            hist_leads  = _enrich_leads(hist_leads_raw)
        except Exception as e:
            app.logger.error(f"leads() enrichment failed: {e}")
            today_leads = [dict(l) for l in today_leads_raw]
            hist_leads  = [dict(l) for l in hist_leads_raw]

        # Team view: hide leader-bought rows unless this user is still assignee
        # (e.g. leader claimed → current_owner=leader, execution assigned_user_id=team — still "My Leads").
        if role == 'team':
            _me = (uname or '').strip().lower()
            _my_id = acting_user_id()

            def _team_sees_in_my_leads(ln: dict) -> bool:
                co = (ln.get('current_owner') or '').strip().lower()
                if co in ('', _me):
                    return True
                if _my_id is None:
                    return False
                try:
                    aid = int(ln.get('assigned_user_id') or 0)
                except (TypeError, ValueError):
                    aid = 0
                if aid == _my_id:
                    return True
                # Also show leads stale-assigned to this user
                sw = (ln.get('stale_worker') or '').strip().lower()
                return sw == _me

            today_leads = [l for l in today_leads if _team_sees_in_my_leads(l)]
            hist_leads = [l for l in hist_leads if _team_sees_in_my_leads(l)]

        # Split today_leads by tab
        _enrolled_statuses = {'Paid ₹196'}
        _converted_status  = 'Converted'

        enrolled_leads       = [l for l in today_leads if l.get('status') in _enrolled_statuses]
        hist_enrolled_leads  = [l for l in hist_leads  if l.get('status') in _enrolled_statuses]
        converted_leads      = [l for l in today_leads if l.get('status') == _converted_status]
        hist_converted_leads = [l for l in hist_leads  if l.get('status') == _converted_status]

        _excluded = {*_enrolled_statuses, _converted_status}

        # Day 1 / 2 / Interview tabs — same bucketing for team & leader so a status edit
        # moves the card out of Active and into the matching stage tab (team had empty lists before).
        day1_leads   = [l for l in today_leads if l.get('status') == 'Day 1']
        day2_leads   = [l for l in today_leads if l.get('status') == 'Day 2']
        day3_leads   = [l for l in today_leads if l.get('status') == 'Interview']
        hist_day1_leads = [l for l in hist_leads if l.get('status') == 'Day 1']
        hist_day2_leads = [l for l in hist_leads if l.get('status') == 'Day 2']
        hist_day3_leads = [l for l in hist_leads if l.get('status') == 'Interview']

        if role == 'team':
            active_leads      = [l for l in today_leads
                                  if l.get('status') not in _excluded
                                  and l.get('status') not in ('Day 1', 'Day 2', 'Interview')]
            hist_active_leads = [l for l in hist_leads
                                  if l.get('status') not in _excluded
                                  and l.get('status') not in ('Day 1', 'Day 2', 'Interview')]
        else:
            active_leads = [l for l in today_leads
                            if l.get('status') not in ('Day 1', 'Day 2', 'Interview')
                            and l.get('status') not in _excluded]
            hist_active_leads = [l for l in hist_leads
                                  if l.get('status') not in ('Day 1', 'Day 2', 'Interview')
                                  and l.get('status') not in _excluded]

        return render_template('leads.html',
                               leads=hist_leads,
                               today_leads=today_leads,
                               hist_leads=hist_leads,
                               day1_leads=day1_leads,
                               day2_leads=day2_leads,
                               day3_leads=day3_leads,
                               active_leads=active_leads,
                               hist_active_leads=hist_active_leads,
                               hist_day1_leads=hist_day1_leads,
                               hist_day2_leads=hist_day2_leads,
                               hist_day3_leads=hist_day3_leads,
                               enrolled_leads=enrolled_leads,
                               hist_enrolled_leads=hist_enrolled_leads,
                               converted_leads=converted_leads,
                               hist_converted_leads=hist_converted_leads,
                               pipeline_auto_expire_statuses=PIPELINE_AUTO_EXPIRE_STATUSES,
                               sla_soft_watch_exclude=SLA_SOFT_WATCH_EXCLUDE,
                               team_allowed_statuses=TEAM_ALLOWED_STATUSES,
                               statuses=STATUSES,
                               call_result_tags=CALL_RESULT_TAGS,
                               call_status_values=CALL_STATUS_VALUES,
                               team_call_status_values=TEAM_CALL_STATUS_VALUES,
                               user_role=session.get('role', 'team'),
                               sources=SOURCES,
                               selected_status=status,
                               search=search,
                               team=team,
                               page=page,
                               has_more_hist=has_more_hist,
                               call_scripts=call_scripts,
                               call_target=call_target)


    # \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
    #  Leads \u2013 Add
    # \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500



    # ─────────────────────────────────────────────────────────────────
    @app.route('/leads/add', methods=['GET', 'POST'])
    @login_required
    @safe_route
    def add_lead():
        db   = get_db()
        team = db.execute(
            "SELECT username AS name FROM users "
            "WHERE role IN ('team','leader') AND status='approved' ORDER BY username"
        ).fetchall()
        ist_today = _today_ist().isoformat()

        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

        if request.method == 'POST':
            name           = request.form.get('name', '').strip()
            phone          = request.form.get('phone', '').strip()
            email          = request.form.get('email', '').strip()
            referred_by    = request.form.get('referred_by', '').strip()
            source         = request.form.get('source', '').strip()
            status         = request.form.get('status', 'New')
            payment_done   = 1 if request.form.get('payment_done') else 0
            payment_amount = PAYMENT_AMOUNT if payment_done else 0.0
            try:
                revenue = float(request.form.get('revenue') or 0)
            except ValueError:
                revenue = 0.0
            follow_up_date = request.form.get('follow_up_date', '').strip()
            if session.get('role') == 'team':
                follow_up_date = ''
            call_result    = request.form.get('call_result', '').strip()
            if not call_result_allowed(call_result):
                call_result = ''
            notes          = request.form.get('notes', '').strip()
            city           = request.form.get('city', '').strip()

            if session.get('role') == 'admin':
                _aun = request.form.get('assigned_to', '').strip()
                if _aun:
                    assigned_uid = user_id_for_username(db, _aun)
                    _ow = db.execute(
                        "SELECT username FROM users WHERE id=?", (assigned_uid,)
                    ).fetchone() if assigned_uid else None
                    owner_u = (_ow['username'] if _ow else '') or ''
                else:
                    assigned_uid = int(session['user_id'])
                    owner_u = acting_username() or ''
            else:
                assigned_uid = int(session['user_id'])
                owner_u = acting_username() or ''

            if not name or not phone:
                if is_ajax:
                    return {'ok': False, 'error': 'Name and Phone are required.'}, 400
                flash('Name and Phone are required.', 'danger')
                return render_template('add_lead.html',
                                       statuses=STATUSES, sources=SOURCES, team=team,
                                       call_result_tags=CALL_RESULT_TAGS,
                                       ist_today=ist_today)

            dup = db.execute(
                "SELECT name, in_pool FROM leads WHERE phone=? AND deleted_at=''", (phone,)
            ).fetchone()
            if dup:
                loc = 'Lead Pool' if dup['in_pool'] else 'Leads'
                msg = f'A lead with phone {phone} already exists ({dup["name"]}) in {loc}.'
                if is_ajax:
                    return {'ok': False, 'error': msg}, 409
                flash(msg + ' Duplicate entries are not allowed.', 'danger')
                return render_template('add_lead.html',
                                       statuses=STATUSES, sources=SOURCES, team=team,
                                       call_result_tags=CALL_RESULT_TAGS,
                                       ist_today=ist_today)

            if status not in STATUSES:
                status = 'New'

            _merge_add = {
                'status': status,
                'payment_done': payment_done,
                'payment_amount': float(payment_amount or 0),
                'seat_hold_amount': 0.0,
                'track_price': 0.0,
            }
            payment_done, payment_amount = normalize_lead_payment_row(_merge_add)
            _okv, _errv = validate_lead_business_rules(
                status, payment_done, payment_amount, 0.0, 0.0,
            )
            if not _okv:
                app.logger.warning('add_lead blocked: %s', _errv)
                if is_ajax:
                    return {'ok': False, 'error': _errv}, 400
                flash(_errv, 'danger')
                return render_template(
                    'add_lead.html',
                    statuses=STATUSES,
                    sources=SOURCES,
                    team=team,
                    call_result_tags=CALL_RESULT_TAGS,
                    ist_today=ist_today,
                )

            pipeline_stage = STATUS_TO_STAGE.get(status, 'prospecting')
            db.execute("""
                INSERT INTO leads
                    (name, phone, email, referred_by, assigned_to, assigned_user_id, source,
                     status, payment_done, payment_amount, revenue,
                     follow_up_date, call_result, notes, city, in_pool, pool_price, claimed_at,
                     pipeline_stage, current_owner)
                VALUES (?, ?, ?, ?, '', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, NULL, ?, ?)
            """, (
                name, phone, email, referred_by, assigned_uid, source,
                status, payment_done, payment_amount, revenue,
                follow_up_date, call_result, notes, city,
                pipeline_stage, owner_u or '',
            ))
            new_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
            db.commit()

            if is_ajax:
                return {'ok': True, 'id': new_id, 'name': name, 'phone': phone,
                        'city': city, 'status': status, 'source': source}

            flash(f'Lead "{name}" added successfully.', 'success')
            return redirect(url_for('leads'))

        return render_template('add_lead.html',
                               statuses=STATUSES, sources=SOURCES, team=team,
                               call_result_tags=CALL_RESULT_TAGS,
                               ist_today=ist_today)

    @app.route('/leads/<int:lead_id>/payment-proof', methods=['POST'])
    @login_required
    def upload_payment_proof(lead_id):
        """Upload ₹196 payment screenshot proof for team execution."""
        db = get_db()
        lead = db.execute(
            "SELECT * FROM leads WHERE id=? AND in_pool=0 AND deleted_at=''",
            (lead_id,),
        ).fetchone()
        if not lead:
            flash('Lead not found.', 'danger')
            return redirect(url_for('leads'))

        role = session.get('role', 'team')
        if not actor_may_use_assignee_execution_routes(
            db,
            lead,
            role=role,
            acting_uid=acting_user_id(),
            acting_un=acting_username() or '',
        ):
            flash('Access denied.', 'danger')
            return redirect(url_for('leads'))

        path_ok = (sqlite_row_get(lead, 'payment_proof_path') or '').strip()
        apv = payment_proof_approval_status_value(lead)
        # One-time proof for every role: block replace unless rejected (no path or reject → allow).
        if path_ok and apv != 'rejected':
            if apv == 'approved':
                flash('₹196 proof pehle se approve hai — dubara upload ki zaroorat nahi.', 'info')
            else:
                flash('Proof already uploaded — leader/admin approval pending.', 'info')
            return redirect(url_for('edit_lead', lead_id=lead_id))

        f = request.files.get('payment_proof')
        if not f or not (f.filename or '').strip():
            flash('Please choose a screenshot file.', 'danger')
            return redirect(url_for('edit_lead', lead_id=lead_id))

        _fname = (f.filename or '').lower()
        if not _fname.endswith(('.png', '.jpg', '.jpeg', '.webp')):
            flash('Only PNG/JPG/WEBP screenshots are allowed.', 'danger')
            return redirect(url_for('edit_lead', lead_id=lead_id))

        _ALLOWED_MIMES = {'image/png', 'image/jpeg', 'image/webp'}
        if f.content_type and f.content_type not in _ALLOWED_MIMES:
            flash('Invalid file type. Only image files (PNG/JPG/WEBP) are accepted.', 'danger')
            return redirect(url_for('edit_lead', lead_id=lead_id))

        save_dir = os.path.join('static', 'uploads', 'payment_proofs')
        os.makedirs(save_dir, exist_ok=True)
        ext = '.jpg'
        if _fname.endswith('.png'):
            ext = '.png'
        elif _fname.endswith('.jpeg'):
            ext = '.jpeg'
        elif _fname.endswith('.webp'):
            ext = '.webp'
        token = secrets.token_hex(8)
        file_name = f"proof_{lead_id}_{token}{ext}"
        abs_path = os.path.join(save_dir, file_name)
        f.save(abs_path)
        rel_path = "/" + os.path.join(save_dir, file_name).replace("\\", "/")
        now_str = _now_ist().strftime('%Y-%m-%d %H:%M:%S')

        _approval = 'approved'
        _reviewer = ''
        _reviewed_at = ''
        _reject_note = ''
        if role == 'team':
            _approval = 'pending'
        elif role == 'leader' and leader_own_assigned_lead(lead, acting_user_id()):
            _approval = 'pending'

        db.execute(
            """
            UPDATE leads SET payment_proof_path=?,
                payment_proof_approval_status=?,
                payment_proof_reviewed_by=?,
                payment_proof_reviewed_at=?,
                payment_proof_reject_note=?,
                updated_at=?
            WHERE id=? AND in_pool=0 AND deleted_at=''
            """,
            (rel_path, _approval, _reviewer, _reviewed_at, _reject_note, now_str, lead_id),
        )
        _lead_nm = (sqlite_row_get(lead, 'name') or '').strip() or f'#{lead_id}'
        if _approval == 'pending':
            try:
                if role == 'team':
                    _lu = (nearest_approved_leader_username(db, acting_username() or '') or '').strip()
                    if _lu and _lu.lower() != (acting_username() or '').strip().lower():
                        _review_url = _public_external_url('edit_lead', lead_id=lead_id)
                        _push_to_users(
                            db,
                            _lu,
                            '₹196 proof — verify karo',
                            f'{acting_username()} · {_lead_nm} (lead #{lead_id}) — screenshot upload hua. '
                            'Edit lead par open karke Approve / Reject karein.',
                            _review_url,
                        )
                    try:
                        _log_activity(
                            db,
                            acting_username() or '',
                            'payment_proof_pending_review',
                            f'Lead #{lead_id} ₹196 proof uploaded; notified leader {_lu or "?"} for review',
                        )
                    except Exception:
                        pass
                elif role == 'leader' and leader_own_assigned_lead(lead, acting_user_id()):
                    _adm = (_get_admin_username(db) or '').strip()
                    if _adm and _adm.lower() != (acting_username() or '').strip().lower():
                        _push_to_users(
                            db,
                            _adm,
                            '₹196 proof — leader upload',
                            f'{acting_username()} · {_lead_nm} (lead #{lead_id}) — leader ne proof dala. Admin verify karein.',
                            _public_external_url('edit_lead', lead_id=lead_id),
                        )
                    try:
                        _log_activity(
                            db,
                            acting_username() or '',
                            'payment_proof_pending_review',
                            f'Lead #{lead_id} leader ₹196 proof pending admin review',
                        )
                    except Exception:
                        pass
            except Exception:
                pass
        db.commit()
        if _approval == 'pending':
            flash(
                '₹196 proof upload ho gaya — team member: apne leader se approval lo. '
                'Leader (apni claim/import/quick-add lead): admin se approval.',
                'warning',
            )
        else:
            flash('₹196 payment proof uploaded.', 'success')
        return redirect(url_for('edit_lead', lead_id=lead_id))

    @app.route('/leads/<int:lead_id>/payment-proof-review', methods=['POST'])
    @login_required
    def review_payment_proof(lead_id):
        """Approve/reject ₹196 screenshot: admin (any), or leader (downline team leads only)."""
        raw_action = (
            request.form.get('action')
            or request.form.get('review_action')
            or request.form.get('proof_action')
            or ''
        ).strip().lower()
        action_alias = {
            'approve': 'approve',
            'approved': 'approve',
            'accept': 'approve',
            'ok': 'approve',
            'yes': 'approve',
            'reject': 'reject',
            'rejected': 'reject',
            'deny': 'reject',
            'no': 'reject',
        }
        action = action_alias.get(raw_action, '')
        note = (request.form.get('note') or '').strip()
        next_url = (request.form.get('next') or '').strip()
        if not next_url.startswith('/'):
            next_url = ''

        def _review_redirect():
            if next_url:
                return redirect(next_url)
            return redirect(url_for('edit_lead', lead_id=lead_id))

        if action not in ('approve', 'reject'):
            code = incident_code("REL-APR")
            emit_event(
                app.logger,
                "payment_proof_review_invalid_action",
                code=code,
                actor=acting_username(),
                lead_id=lead_id,
                raw_action=raw_action,
            )
            db = get_db()
            _log_activity(
                db,
                acting_username() or '',
                'reliability_invalid_review_action',
                f'lead={lead_id} raw={raw_action} code={code}',
            )
            db.commit()
            app.logger.warning(
                "payment_proof_review invalid action: raw=%r user=%s lead_id=%s form_keys=%s",
                raw_action,
                acting_username(),
                lead_id,
                sorted(list(request.form.keys())),
            )
            flash(safe_user_error('Invalid review action.', code), 'danger')
            return _review_redirect()
        db = get_db()
        lead = db.execute(
            "SELECT * FROM leads WHERE id=? AND in_pool=0 AND deleted_at=''",
            (lead_id,),
        ).fetchone()
        if not lead:
            flash('Lead not found.', 'danger')
            return _review_redirect()
        _role = session.get('role', 'team')
        if not can_review_rupees_196_proof(
            db, acting_username() or '', _role, dict(lead),
        ):
            code = incident_code("REL-APR")
            emit_event(
                app.logger,
                "payment_proof_review_forbidden",
                code=code,
                actor=acting_username(),
                actor_role=_role,
                lead_id=lead_id,
            )
            try:
                _log_activity(
                    db,
                    acting_username() or '',
                    'reliability_review_forbidden',
                    f'lead={lead_id} role={_role} code={code}',
                )
            except Exception:
                pass
            flash(
                safe_user_error(
                    'Leader sirf apni poori team/downline ke assignees ka ₹196 approve kar sakta hai '
                    '(khud ko assign lead nahi). Admin kisi bhi lead ka approve/reject kar sakta hai.',
                    code,
                ),
                'danger',
            )
            return _review_redirect()
        if not (sqlite_row_get(lead, 'payment_proof_path') or '').strip():
            flash('Pehle proof upload hona chahiye.', 'warning')
            return _review_redirect()
        now_str = _now_ist().strftime('%Y-%m-%d %H:%M:%S')
        admin_un = acting_username() or 'admin'
        if action == 'approve':
            db.execute(
                """
                UPDATE leads SET payment_proof_approval_status='approved',
                    payment_proof_reviewed_by=?, payment_proof_reviewed_at=?,
                    payment_proof_reject_note='', payment_done=1, updated_at=?
                WHERE id=? AND in_pool=0 AND deleted_at=''
                """,
                (admin_un, now_str, now_str, lead_id),
            )
            try:
                _log_lead_event(db, lead_id, admin_un, '₹196 proof APPROVED by admin')
            except Exception:
                pass
            # Auto Day 1: if lead is in ₹196-paid/enrolled state, push to Day 1 automatically
            _refreshed = db.execute(
                "SELECT * FROM leads WHERE id=? AND in_pool=0 AND deleted_at=''",
                (lead_id,),
            ).fetchone()
            _auto_msg = ''
            if _refreshed:
                _cur_status = (sqlite_row_get(_refreshed, 'status') or '').strip()
                _cur_stage = (sqlite_row_get(_refreshed, 'pipeline_stage') or '').strip()
                _post_day1_stages = {'day1', 'day2', 'day3', 'seat_hold', 'closing', 'training', 'complete', 'lost'}
                if _cur_stage not in _post_day1_stages:
                    assignee_un = (_assignee_username_for_lead(db, _refreshed) or '').strip()
                    assignee_row = db.execute(
                        "SELECT role FROM users WHERE username=? LIMIT 1", (assignee_un,)
                    ).fetchone()
                    assignee_role = ((assignee_row['role'] if assignee_row else '') or '').strip()
                    if assignee_role in ('leader', 'admin'):
                        day1_owner = assignee_un
                    else:
                        day1_owner = nearest_approved_leader_username(db, assignee_un) or admin_un
                    if not _leader_day1_routing_on(db, day1_owner):
                        _auto_msg = f' Lead stays at ₹196 (Day 1 routing OFF for @{day1_owner}).'
                        flash('₹196 payment proof approved.' + _auto_msg, 'success')
                        db.commit()
                        return redirect(url_for('edit_lead', lead_id=lead_id))
                    _d1_upd = {
                        'status': 'Day 1',
                        'pipeline_stage': 'day1',
                        'flow_started_at': now_str,
                        'updated_at': now_str,
                        'pipeline_entered_at': now_str,
                    }
                    _d1_uid = user_id_for_username(db, day1_owner)
                    if _d1_uid:
                        _d1_upd['assigned_user_id'] = _d1_uid
                    apply_leads_update(
                        db,
                        _d1_upd,
                        where_sql="id=? AND in_pool=0 AND deleted_at=''",
                        where_params=(lead_id,),
                        log_context='auto_day1_on_proof_approve',
                    )
                    db.execute(
                        "UPDATE leads SET enrolled_at=?, enrolled_by=? WHERE id=? AND TRIM(COALESCE(enrolled_at,''))=''",
                        (now_str, assignee_un, lead_id),
                    )
                    try:
                        _log_lead_event(db, lead_id, admin_un,
                            f'Auto Day 1: proof approved → execution @{day1_owner}')
                    except Exception:
                        pass
                    _auto_msg = f' Lead auto-moved to Day 1 (execution: @{day1_owner}).'
            flash('₹196 payment proof approved.' + _auto_msg, 'success')
        else:
            db.execute(
                """
                UPDATE leads SET payment_proof_approval_status='rejected',
                    payment_proof_reviewed_by=?, payment_proof_reviewed_at=?,
                    payment_proof_reject_note=?, updated_at=?
                WHERE id=? AND in_pool=0 AND deleted_at=''
                """,
                (admin_un, now_str, note[:500], now_str, lead_id),
            )
            try:
                _log_lead_event(
                    db, lead_id, admin_un,
                    f'₹196 proof REJECTED by admin{f": {note}" if note else ""}',
                )
            except Exception:
                pass
            flash('Proof reject kar diya. Leader naya screenshot upload kar sakta hai.', 'warning')
        try:
            _log_activity(
                db, admin_un, 'payment_proof_review',
                f'Lead #{lead_id} proof {action} by {admin_un}',
            )
        except Exception:
            pass
        db.commit()
        return _review_redirect()

    # \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
    #  Leads \u2013 Edit / Update
    # \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

    @app.route('/leads/<int:lead_id>/edit', methods=['GET', 'POST'])
    @login_required
    @safe_route
    def edit_lead(lead_id):
        db   = get_db()
        team = db.execute(
            "SELECT username AS name FROM users "
            "WHERE role IN ('team','leader') AND status='approved' ORDER BY username"
        ).fetchall()

        if session.get('role') == 'admin':
            lead = db.execute(
                "SELECT * FROM leads WHERE id=? AND in_pool=0 AND deleted_at=''", (lead_id,)
            ).fetchone()
        else:
            lead = db.execute(
                "SELECT * FROM leads WHERE id=? AND in_pool=0 AND deleted_at=''", (lead_id,)
            ).fetchone()
            if lead:
                _my = acting_user_id()
                _un = acting_username() or ''
                role = session.get('role', 'team')
                if _my is None or role not in ('team', 'leader'):
                    lead = None
                elif not actor_may_use_assignee_execution_routes(
                    db,
                    lead,
                    role=role,
                    acting_uid=_my,
                    acting_un=_un,
                ):
                    lead = None

        if not lead:
            flash('Lead not found or access denied.', 'danger')
            return redirect(url_for('leads'))

        lead = _enrich_leads([dict(lead)])[0]

        def _edit_lead_status_choices(ln: dict):
            if session.get('role') != 'team':
                return STATUSES
            return team_status_dropdown_choices(ln.get('status') or '')

        def _edit_lead_can_review_proof():
            if session.get('role') not in ('admin', 'leader'):
                return False
            dbb = get_db()
            try:
                return can_review_rupees_196_proof(
                    dbb, acting_username() or '', session.get('role', ''), lead
                )
            finally:
                dbb.close()

        if request.method == 'POST':
            name           = request.form.get('name', '').strip()
            phone          = request.form.get('phone', '').strip()
            email          = request.form.get('email', '').strip()
            referred_by    = request.form.get('referred_by', '').strip()
            status         = request.form.get('status', lead['status'])
            _requested_status = status  # Used for Bundle 1 normalization decisions
            payment_done   = 1 if request.form.get('payment_done') else 0
            payment_amount = float(PAYMENT_AMOUNT) if payment_done else 0.0
            day1_done      = 1 if request.form.get('day1_done') else 0
            day2_done      = 1 if request.form.get('day2_done') else 0
            interview_done = 1 if request.form.get('interview_done') else 0
            notes          = request.form.get('notes', '').strip()
            follow_up_date = request.form.get('follow_up_date', '').strip()
            if session.get('role') == 'team':
                _fk0 = lead.keys()
                follow_up_date = (lead['follow_up_date'] if 'follow_up_date' in _fk0 else '') or ''
                # Funnel / track / seat — leader & admin; team only pre–₹196 prospecting + proof
                day1_done = 1 if sqlite_row_get(lead, 'day1_done') else 0
                day2_done = 1 if sqlite_row_get(lead, 'day2_done') else 0
                interview_done = 1 if sqlite_row_get(lead, 'interview_done') else 0
            call_result    = request.form.get('call_result', lead['call_result'] if 'call_result' in lead.keys() else '').strip()
            if not call_result_allowed(call_result):
                call_result = (lead['call_result'] if 'call_result' in lead.keys() else '') or ''
            city           = request.form.get('city', '').strip()

            _lead_keys = lead.keys()
            track_selected_val   = request.form.get('track_selected', (lead['track_selected'] if 'track_selected' in _lead_keys else '') or '').strip()
            track_price_val      = float(request.form.get('track_price', (lead['track_price'] if 'track_price' in _lead_keys else 0) or 0) or 0)
            seat_hold_amount_val = float(request.form.get('seat_hold_amount', (lead['seat_hold_amount'] if 'seat_hold_amount' in _lead_keys else 0) or 0) or 0)
            seat_hold_received   = bool(request.form.get('seat_hold_received'))
            final_payment_received = bool(request.form.get('final_payment_received'))
            if session.get('role') == 'team':
                track_selected_val = ((lead['track_selected'] if 'track_selected' in _lead_keys else '') or '').strip()
                track_price_val = float(lead['track_price'] if 'track_price' in _lead_keys and lead['track_price'] else 0) or 0.0
                seat_hold_amount_val = float(lead['seat_hold_amount'] if 'seat_hold_amount' in _lead_keys and lead['seat_hold_amount'] else 0) or 0.0
                seat_hold_received = lead['status'] in ('Seat Hold Confirmed', 'Fully Converted')
                final_payment_received = lead['status'] == 'Fully Converted'

            # Auto-fill from track defaults if track just selected (NEW selection only)
            old_track = (lead['track_selected'] if 'track_selected' in _lead_keys and lead['track_selected'] else '')
            track_just_picked = track_selected_val and track_selected_val in TRACKS and track_selected_val != old_track
            if track_selected_val and track_selected_val in TRACKS:
                if not track_price_val:
                    track_price_val = TRACKS[track_selected_val]['price']
                if not seat_hold_amount_val:
                    seat_hold_amount_val = TRACKS[track_selected_val]['seat_hold']
                # Only force 'Track Selected' status when user NEWLY picks a track
                if track_just_picked and status not in ('Seat Hold Confirmed', 'Fully Converted'):
                    status = 'Track Selected'

            pending_amount_val = max(0.0, track_price_val - seat_hold_amount_val)

            if session.get('role') in ('team', 'leader') and _requested_status == 'Paid ₹196':
                _blocked, _msg = rupees_196_execution_blocked_for_role(
                    lead,
                    role=session.get('role', 'team'),
                    acting_user_id=acting_user_id(),
                    current_status=(lead.get('status') or '').strip(),
                    is_transition_to_paid_196_funnel=True,
                    gate_enabled=_rupees_196_gate_enabled(db),
                )
                if _blocked:
                    flash(_msg, 'danger')
                    lead_notes_rows = db.execute(
                        "SELECT * FROM lead_notes WHERE lead_id=? ORDER BY created_at ASC",
                        (lead_id,),
                    ).fetchall()
                    return render_template(
                        'edit_lead.html',
                        lead=lead,
                        statuses=_edit_lead_status_choices(lead),
                        team=team,
                        payment_amount=PAYMENT_AMOUNT,
                        lead_notes=lead_notes_rows,
                        call_result_tags=CALL_RESULT_TAGS,
                        can_review_rupees_proof=_edit_lead_can_review_proof(),
                    )

            # ── Checkbox-driven status (checkboxes override dropdown) — leader/admin only ──
            if session.get('role') == 'team':
                pass
            elif final_payment_received and not seat_hold_received:
                # ❌ Cannot be Fully Converted without Seat Hold
                flash('Confirm Seat Hold first — “Fully converted” is only available when Seat Hold Received is also checked.', 'danger')
                lead_notes_rows = db.execute(
                    "SELECT * FROM lead_notes WHERE lead_id=? ORDER BY created_at ASC",
                    (lead_id,)
                ).fetchall()
                return render_template('edit_lead.html',
                                       lead=lead, statuses=_edit_lead_status_choices(lead),
                                       team=team, payment_amount=PAYMENT_AMOUNT,
                                       lead_notes=lead_notes_rows,
                                       call_result_tags=CALL_RESULT_TAGS,
                                       can_review_rupees_proof=_edit_lead_can_review_proof())
            elif final_payment_received:
                # Both seat_hold + final_payment checked
                status = 'Fully Converted'
                pending_amount_val = 0.0
            elif seat_hold_received:
                status = 'Seat Hold Confirmed'
            else:
                # Both unchecked — only revert if user EXPLICITLY unchecked
                # (i.e. lead previously had one of these statuses)
                was_seat_or_converted = lead['status'] in ('Seat Hold Confirmed', 'Fully Converted')
                if was_seat_or_converted and status in ('Seat Hold Confirmed', 'Fully Converted'):
                    status = 'Track Selected' if track_selected_val else 'Interview'
                # Clear seat hold amount & recalculate pending only if was previously set
                if was_seat_or_converted:
                    seat_hold_amount_val = 0.0
                    pending_amount_val   = track_price_val

            if not name or not phone:
                flash('Name and Phone are required.', 'danger')
                lead_notes_rows = db.execute(
                    "SELECT * FROM lead_notes WHERE lead_id=? ORDER BY created_at ASC",
                    (lead_id,)
                ).fetchall()
                return render_template('edit_lead.html',
                                       lead=lead, statuses=_edit_lead_status_choices(lead),
                                       team=team, payment_amount=PAYMENT_AMOUNT,
                                       lead_notes=lead_notes_rows,
                                       call_result_tags=CALL_RESULT_TAGS,
                                       can_review_rupees_proof=_edit_lead_can_review_proof())

            dup = db.execute(
                "SELECT name, in_pool FROM leads WHERE phone=? AND id!=? AND deleted_at=''",
                (phone, lead_id)
            ).fetchone()
            if dup:
                loc = 'Lead Pool' if dup['in_pool'] else 'Leads'
                flash(f'Another lead with phone {phone} already exists ({dup["name"]}) in {loc}. Duplicate entries are not allowed.', 'danger')
                lead_notes_rows = db.execute(
                    "SELECT * FROM lead_notes WHERE lead_id=? ORDER BY created_at ASC",
                    (lead_id,)
                ).fetchall()
                return render_template('edit_lead.html',
                                       lead=lead, statuses=_edit_lead_status_choices(lead),
                                       team=team, payment_amount=PAYMENT_AMOUNT,
                                       lead_notes=lead_notes_rows,
                                       call_result_tags=CALL_RESULT_TAGS,
                                       can_review_rupees_proof=_edit_lead_can_review_proof())

            if status not in STATUSES:
                status = lead['status']

            if not _role_owns_status(session.get('role', 'team'), status):
                flash(
                    f"Role '{session.get('role', 'team')}' cannot set status '{status}'.",
                    'danger',
                )
                lead_notes_rows = db.execute(
                    "SELECT * FROM lead_notes WHERE lead_id=? ORDER BY created_at ASC",
                    (lead_id,),
                ).fetchall()
                return render_template(
                    'edit_lead.html',
                    lead=lead,
                    statuses=_edit_lead_status_choices(lead),
                    team=team,
                    payment_amount=PAYMENT_AMOUNT,
                    lead_notes=lead_notes_rows,
                    call_result_tags=CALL_RESULT_TAGS,
                    can_review_rupees_proof=_edit_lead_can_review_proof(),
                )

            _cur_status = (lead['status'] or '').strip()
            _post_196_statuses = {'Paid ₹196', 'Day 1', 'Day 2', 'Interview', 'Track Selected', 'Seat Hold Confirmed', 'Fully Converted'}
            if (
                _strict_flow_guard_enabled(db)
                and session.get('role') not in ('admin', 'leader')
                and not (
                    session.get('role') == 'team'
                    and _cur_status not in _post_196_statuses
                )
                and not is_valid_forward_status_transition(
                    lead['status'], status, for_team=(session.get('role') == 'team')
                )
            ):
                _log_activity(
                    db, acting_username(), 'status_skip_blocked',
                    f"Lead #{lead_id}: {lead['status']} -> {status}"
                )
                flash(
                    f"Invalid jump: '{lead['status']}' -> '{status}' is not allowed.",
                    'danger',
                )
                lead_notes_rows = db.execute(
                    "SELECT * FROM lead_notes WHERE lead_id=? ORDER BY created_at ASC",
                    (lead_id,),
                ).fetchall()
                return render_template(
                    'edit_lead.html',
                    lead=lead,
                    statuses=_edit_lead_status_choices(lead),
                    team=team,
                    payment_amount=PAYMENT_AMOUNT,
                    lead_notes=lead_notes_rows,
                    call_result_tags=CALL_RESULT_TAGS,
                    can_review_rupees_proof=_edit_lead_can_review_proof(),
                )

            if session.get('role') == 'team':
                _prev_s = (sqlite_row_get(lead, 'status') or '').strip()
                if status in TEAM_FORBIDDEN_STATUSES and status != _prev_s:
                    flash(
                        'Team role Day 1/Day 2/Interview/Closing statuses set nahi kar sakti.',
                        'danger',
                    )
                    lead_notes_rows = db.execute(
                        "SELECT * FROM lead_notes WHERE lead_id=? ORDER BY created_at ASC",
                        (lead_id,),
                    ).fetchall()
                    return render_template(
                        'edit_lead.html',
                        lead=lead,
                        statuses=_edit_lead_status_choices(lead),
                        team=team,
                        payment_amount=PAYMENT_AMOUNT,
                        lead_notes=lead_notes_rows,
                        call_result_tags=CALL_RESULT_TAGS,
                        can_review_rupees_proof=_edit_lead_can_review_proof(),
                    )

            # Team convenience: checking ₹196 payment in edit form should not hard-block save.
            if session.get('role') == 'team' and payment_done and status != 'Paid ₹196':
                status = 'Paid ₹196'

            # ₹196 paid → auto-advance to Day 1 if routing is ON
            _edit_d1_routed = False
            if status == 'Paid ₹196' and session.get('role') == 'admin':
                status = 'Day 1'
            elif status == 'Paid ₹196' and session.get('role') == 'leader':
                if _leader_day1_routing_on(db, acting_username()):
                    status = 'Day 1'
                    _edit_d1_routed = True

            if session.get('role') == 'admin':
                _au = (request.form.get('assigned_to') or '').strip()
                if _au:
                    assigned_uid = user_id_for_username(db, _au)
                else:
                    try:
                        assigned_uid = int(lead['assigned_user_id']) if sqlite_row_get(lead, 'assigned_user_id') else None
                    except (TypeError, ValueError):
                        assigned_uid = None
            else:
                try:
                    assigned_uid = int(lead['assigned_user_id'])
                except (TypeError, ValueError):
                    assigned_uid = int(session['user_id'])

            if _edit_d1_routed:
                _leader_uid_edit = user_id_for_username(db, acting_username())
                if _leader_uid_edit:
                    assigned_uid = _leader_uid_edit

            # Sync pipeline_stage from status (one status -> one pipeline_stage)
            new_pipeline_stage = STATUS_TO_STAGE.get(status, 'prospecting')
            lead_pipeline_stage = lead['pipeline_stage'] if 'pipeline_stage' in lead.keys() else 'prospecting'
            stage_changed = new_pipeline_stage != lead_pipeline_stage
            _updated_at = _now_ist().strftime('%Y-%m-%d %H:%M:%S')

            _interview_status = 'cleared' if interview_done else ''

            if (
                lead_pipeline_stage == 'day2'
                and new_pipeline_stage == 'day3'
                and not lead_day2_business_test_passed(lead)
            ):
                flash('Day 2 business test pass (≥18/30) required before Interview / Day 3.', 'danger')
                lead_notes_rows = db.execute(
                    "SELECT * FROM lead_notes WHERE lead_id=? ORDER BY created_at ASC",
                    (lead_id,),
                ).fetchall()
                return render_template(
                    'edit_lead.html',
                    lead=lead,
                    statuses=_edit_lead_status_choices(lead),
                    team=team,
                    payment_amount=PAYMENT_AMOUNT,
                    lead_notes=lead_notes_rows,
                    call_result_tags=CALL_RESULT_TAGS,
                    can_review_rupees_proof=_edit_lead_can_review_proof(),
                )

            # ── Check for Growth Engine points (fresh leads only) ──────
            _was_paid = lead['payment_done'] if 'payment_done' in lead.keys() else 0
            if _is_fresh_lead(lead):
                if payment_done and not _was_paid:
                    add_points(acting_username(), 'CONVERSION', f"Converted lead #{lead_id} (Paid ₹196)", lead_id=lead_id)
                _old_call_result = lead['call_result'] if 'call_result' in lead.keys() else ''
                if call_result in ('Connected', 'Spoke to lead', 'Hot Lead') and call_result != _old_call_result:
                    add_points(acting_username(), 'CONNECTED_CALL', f"Connected with lead #{lead_id}", lead_id=lead_id)

            _merge = {k: lead[k] for k in lead.keys()}
            _merge['status'] = status
            _merge['track_price'] = track_price_val
            _merge['seat_hold_amount'] = seat_hold_amount_val
            _merge['payment_done'] = payment_done
            _merge['payment_amount'] = float(payment_amount or 0)
            payment_done, payment_amount = normalize_lead_payment_row(_merge)
            _okv, _errv = validate_lead_business_rules(
                status,
                payment_done,
                payment_amount,
                seat_hold_amount_val,
                track_price_val,
            )
            if not _okv:
                app.logger.warning('edit_lead blocked: %s', _errv)
                lead_notes_rows = db.execute(
                    "SELECT * FROM lead_notes WHERE lead_id=? ORDER BY created_at ASC",
                    (lead_id,),
                ).fetchall()
                flash(_errv, 'danger')
                return render_template(
                    'edit_lead.html',
                    lead=lead,
                    statuses=_edit_lead_status_choices(lead),
                    team=team,
                    payment_amount=PAYMENT_AMOUNT,
                    lead_notes=lead_notes_rows,
                    call_result_tags=CALL_RESULT_TAGS,
                    can_review_rupees_proof=_edit_lead_can_review_proof(),
                )

            # After validation: stage transition must run before the big UPDATE so stage/state
            # stays aligned while permanent owner remains locked.
            if stage_changed:
                try:
                    _transition_stage(db, lead_id, new_pipeline_stage, acting_username(), status_override=status)
                    db.commit()
                except Exception as e:
                    import sys
                    print(f"[STAGE TRANSITION ERROR] lead={lead_id} error={e}", file=sys.stderr)
                _sync = db.execute(
                    "SELECT pipeline_stage, status, pipeline_entered_at FROM leads WHERE id=?",
                    (lead_id,),
                ).fetchone()
                if _sync:
                    new_pipeline_stage = _sync['pipeline_stage'] or new_pipeline_stage
                    status = _sync['status'] or status
                    _pipeline_entered_at_val = _sync['pipeline_entered_at'] or ''
                else:
                    _pipeline_entered_at_val = ''
            else:
                _entering_pipeline = status in PIPELINE_AUTO_EXPIRE_STATUSES
                _pipeline_entered_at_val = _updated_at if _entering_pipeline else ''

            # Single UPDATE: always set status and pipeline_stage together
            db.execute("""
                UPDATE leads
                SET name=?, phone=?, email=?, referred_by=?, assigned_to='', assigned_user_id=?, status=?,
                    payment_done=?, payment_amount=?,
                    day1_done=?, day2_done=?, interview_done=?,
                    follow_up_date=?, call_result=?, notes=?, city=?,
                    track_selected=?, track_price=?, seat_hold_amount=?, pending_amount=?,
                    pipeline_stage=?,
                    interview_status=?,
                    updated_at=?,
                    pipeline_entered_at=?
                WHERE id=?
            """, (name, phone, email, referred_by, assigned_uid, status,
                  payment_done, payment_amount,
                  day1_done, day2_done, interview_done,
                  follow_up_date, call_result, notes, city,
                  track_selected_val, track_price_val, seat_hold_amount_val, pending_amount_val,
                  new_pipeline_stage,
                  _interview_status,
                  _updated_at,
                  _pipeline_entered_at_val,
                  lead_id))
            if session.get('role') == 'team' and status == 'Paid ₹196':
                _handoff_row = db.execute(
                    "SELECT * FROM leads WHERE id=? AND in_pool=0 AND deleted_at=''",
                    (lead_id,),
                ).fetchone()
                if _handoff_row:
                    _advanced = _team_handoff_to_leader(db, lead_id, _handoff_row, _updated_at)
                    if _advanced:
                        status = 'Day 1'
                        new_pipeline_stage = 'day1'
            elif session.get('role') == 'leader' and status == 'Paid ₹196':
                _leader_un = acting_username()
                _leader_uid = user_id_for_username(db, _leader_un)
                if _leader_day1_routing_on(db, _leader_un):
                    status = 'Day 1'
                    new_pipeline_stage = 'day1'
                    _d1_sql = (
                        "UPDATE leads SET status='Day 1', pipeline_stage='day1',"
                        " assigned_user_id=COALESCE(?,assigned_user_id),"
                        " enrolled_at=?, enrolled_by=?, updated_at=?"
                        " WHERE id=?"
                    )
                    db.execute(_d1_sql, (_leader_uid, _updated_at, _leader_un, _updated_at, lead_id))
                else:
                    db.execute(
                        "UPDATE leads SET enrolled_at=?, enrolled_by=?"
                        " WHERE id=? AND TRIM(COALESCE(enrolled_at,''))=''",
                        (_updated_at, _leader_un, lead_id),
                    )
            # Stamp enrolled_at + enrolled_by for admin paths (team/leader handled above)
            if status in ('Paid ₹196', 'Day 1') and session.get('role') == 'admin':
                db.execute(
                    "UPDATE leads SET enrolled_at=?, enrolled_by=? WHERE id=? AND TRIM(COALESCE(enrolled_at,''))=''",
                    (_updated_at, acting_username(), lead_id),
                )
            db.commit()

            try:
                _log_activity(db, acting_username(), 'lead_update',
                              f"Lead #{lead_id} updated to status: {status} stage: {new_pipeline_stage}")
            except Exception:
                pass  # Non-fatal: commit already succeeded
            _ai_fb = ''
            try:
                _asg_un = _assignee_username_for_lead(db, {'assigned_user_id': assigned_uid})
                _ai_fb = compute_step8_quick_feedback_for_assignee(
                    db, (_asg_un or '').strip() or (acting_username() or '')
                )
            except Exception:
                pass
            flash(f'Lead "{name}" updated.', 'success')
            if _ai_fb:
                flash(_ai_fb, 'info')
            return redirect(url_for('leads'))

        lead_notes_rows = db.execute(
            "SELECT * FROM lead_notes WHERE lead_id=? ORDER BY created_at ASC",
            (lead_id,)
        ).fetchall()
        timeline = db.execute(
            "SELECT * FROM lead_notes WHERE lead_id=? ORDER BY created_at DESC LIMIT 50",
            (lead_id,)
        ).fetchall()
        return render_template('edit_lead.html',
                               lead=lead,
                               statuses=_edit_lead_status_choices(lead),
                               team=team,
                               payment_amount=PAYMENT_AMOUNT,
                               lead_notes=lead_notes_rows,
                               timeline=timeline,
                               call_result_tags=CALL_RESULT_TAGS,
                               can_review_rupees_proof=_edit_lead_can_review_proof())


    # \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
    #  Retarget List
    # \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

    @app.route('/follow-up')
    @login_required
    def follow_up_queue():
        if session.get('role') == 'team':
            flash('Follow-up queue is for leaders and admins. Use My Leads and Retarget for your work.', 'info')
            return redirect(url_for('leads'))
        db   = get_db()
        role = session.get('role')
        now_date = _now_ist().strftime('%Y-%m-%d')   # IST so user/server timezone match
        now_time = _now_ist().strftime('%H:%M')
        fu_placeholders = ','.join('?' * len(FOLLOWUP_TAGS))
        query = f"""
            SELECT * FROM leads
            WHERE in_pool=0 AND deleted_at=''
              AND status NOT IN ('Converted','Fully Converted','Lost','Retarget','Inactive')
              AND (
                (follow_up_date != '' AND DATE(follow_up_date) <= ?)
                OR call_result IN ({fu_placeholders})
              )
        """
        params = [now_date] + list(FOLLOWUP_TAGS)
        if role != 'admin':
            query += " AND assigned_user_id=?"
            params.append(acting_user_id())
        query += """
            ORDER BY
              CASE WHEN follow_up_date != '' AND DATE(follow_up_date) = ? THEN 0 ELSE 1 END,
              follow_up_date ASC,
              last_contacted ASC
        """
        params.append(now_date)
        leads_list = db.execute(query, params).fetchall()
        today_count    = sum(1 for l in leads_list
                             if l['follow_up_date'] and l['follow_up_date'][:10] == now_date)
        overdue_count  = sum(1 for l in leads_list
                             if l['follow_up_date'] and l['follow_up_date'][:10] < now_date)

        return render_template('follow_up.html',
                               leads=leads_list,
                               today_count=today_count,
                               overdue_count=overdue_count,
                               now_date=now_date,
                               now_time=now_time,
                               statuses=STATUSES,
                               call_result_tags=CALL_RESULT_TAGS)


    @app.route('/leads/<int:lead_id>/call-script')
    @login_required
    def get_call_script(lead_id):
        """Return processed, variable-filled script steps as JSON."""
        db = get_db()
        lead = db.execute(
            "SELECT * FROM leads WHERE id=? AND in_pool=0 AND deleted_at=''", (lead_id,)
        ).fetchone()
        if not lead:
            return jsonify({'ok': False, 'error': 'Not found'}), 404
        role = session.get('role', 'team')
        if not actor_may_use_assignee_execution_routes(
            db,
            lead,
            role=role,
            acting_uid=acting_user_id(),
            acting_un=acting_username() or '',
        ):
            return jsonify({'ok': False, 'error': 'Forbidden'}), 403

        lead_keys = lead.keys() if hasattr(lead, 'keys') else []

        # Resolve referrer display name
        referrer_name = ''
        referred_by = lead['referred_by'] if 'referred_by' in lead_keys else ''
        if referred_by:
            ref_user = db.execute(
                "SELECT username FROM users WHERE username=?", (referred_by,)
            ).fetchone()
            if ref_user:
                referrer_name = ref_user['username'] or referred_by

        agent_name = (acting_username() or '')

        vars_map = {
            'name':          (lead['name'] or '').strip(),
            'city':          (lead['city'] or '').strip() if 'city' in lead_keys else '',
            'phone':         (lead['phone'] or '').strip(),
            'source':        (lead['source'] or '').strip() if 'source' in lead_keys else '',
            'referrer_name': referrer_name,
            'agent_name':    agent_name,
        }
        source_lower = vars_map['source'].lower()

        sections = [
            ('opening',       '🙏', 'Opening'),
            ('qualification', '🔍', 'Qualification'),
            ('pitch',         '🎯', 'Pitch'),
            ('closing',       '✅', 'Closing'),
        ]

        steps = []
        for key, icon, label in sections:
            raw = _get_setting(db, f'script_{key}', '')
            if not raw:
                steps.append({'key': key, 'icon': icon, 'label': label, 'content': ''})
                continue

            # Variable substitution — support both {{name}} and [Name] styles
            content = raw
            for var, val in vars_map.items():
                content = content.replace('{{' + var + '}}', val)
            # Bracket-style placeholders (case-insensitive)
            _bracket_map = {
                'name':       vars_map['name'],
                'city':       vars_map['city'],
                'agent_name': vars_map['agent_name'],
                'aapka naam': vars_map['agent_name'],
                'your name':  vars_map['agent_name'],
                'phone':      vars_map['phone'],
                'source':     vars_map['source'],
            }
            for placeholder, val in _bracket_map.items():
                content = re.sub(
                    r'\[' + re.escape(placeholder) + r'\]',
                    val, content, flags=re.IGNORECASE,
                )

            # Line-level processing
            lines_out = []
            for line in content.split('\n'):
                # Conditional: [if:instagram]...[/if]
                if '[if:instagram]' in line:
                    if source_lower in ('instagram', 'instagram ad', 'ig'):
                        line = line.replace('[if:instagram]', '').replace('[/if]', '').strip()
                    else:
                        continue
                # Conditional: [if:referral]...[/if]
                if '[if:referral]' in line:
                    if referrer_name:
                        line = line.replace('[if:referral]', '').replace('[/if]', '').strip()
                    else:
                        continue
                # Drop lines with still-unfilled variables
                if '{{' in line and '}}' in line:
                    continue
                lines_out.append(line)

            # Collapse consecutive blank lines
            cleaned = []
            prev_blank = False
            for ln in lines_out:
                blank = not ln.strip()
                if blank and prev_blank:
                    continue
                cleaned.append(ln)
                prev_blank = blank

            steps.append({
                'key':     key,
                'icon':    icon,
                'label':   label,
                'content': '\n'.join(cleaned).strip(),
            })

        return jsonify({'ok': True, 'steps': steps, 'vars': vars_map})


    @app.route('/leads/<int:lead_id>/mark-called', methods=['POST'])
    @login_required
    def mark_called(lead_id):
        db   = get_db()
        lead = db.execute("SELECT * FROM leads WHERE id=? AND in_pool=0 AND deleted_at=''", (lead_id,)).fetchone()
        if not lead:
            return {'ok': False, 'error': 'not found'}, 404
        role = session.get('role', 'team')
        if not actor_may_use_assignee_execution_routes(
            db,
            lead,
            role=role,
            acting_uid=acting_user_id(),
            acting_un=acting_username() or '',
        ):
            return {'ok': False, 'error': 'forbidden'}, 403

        now = _now_ist().strftime('%Y-%m-%d %H:%M:%S')
        _had_followup = bool(lead['follow_up_date'] if 'follow_up_date' in lead.keys() else False)

        db.execute("""
            UPDATE leads SET last_contacted=?, contact_count=contact_count+1, updated_at=?,
                             follow_up_date='', follow_up_time=''
            WHERE id=?
        """, (now, now, lead_id))
        _log_lead_event(db, lead_id, acting_username(), 'Called / contacted')
        
        if _is_fresh_lead(lead):
            add_points(acting_username(), 'CALL_ATTEMPT', f"Dialed lead #{lead_id}", db=db, lead_id=lead_id, delta_calls=1)
            if _had_followup:
                add_points(acting_username(), 'FOLLOWUP_COMPLETED', f"Completed scheduled follow-up for lead #{lead_id}", db=db, lead_id=lead_id)

        # Auto-advance status to "Contacted" if currently below
        _STATUS_ORDER_MC = [
            'New Lead', 'New', 'Contacted', 'Invited',
            'Video Sent', 'Video Watched', 'Paid ₹196',
        ]
        lead_status = lead['status'] or 'New'
        if lead_status in ('New Lead', 'New'):
            db.execute(
                "UPDATE leads SET status='Contacted', updated_at=? WHERE id=?",
                (now, lead_id)
            )
        db.commit()
        return {'ok': True}


    @app.route('/leads/<int:lead_id>/follow-up-time', methods=['POST'])
    @login_required
    def set_follow_up_time(lead_id):
        """Set follow-up reminder time (HH:MM). Accepts key 'time' or 'reminder_time'. Persists and shows in Follow-up Queue."""
        if session.get('role') == 'team':
            return {'ok': False, 'error': 'Team members do not use follow-up scheduling.'}, 403
        data = request.get_json(silent=True) or {}
        reminder_time = (data.get('reminder_time') or data.get('time') or '').strip()

        # Validate: allow empty to clear; if non-empty, expect HH:MM (optional strict check)
        if reminder_time:
            import re
            if not re.match(r'^([01]?\d|2[0-3]):[0-5]\d$', reminder_time):
                return {'ok': False, 'error': 'Use HH:MM format (e.g. 09:30)'}, 400

        db = get_db()
        lead = db.execute("SELECT * FROM leads WHERE id=? AND in_pool=0 AND deleted_at=''", (lead_id,)).fetchone()
        if not lead:
            return {'ok': False, 'error': 'Not found'}, 404

        role = session.get('role', 'team')
        username = acting_username() or ''
        _lid_u = _assignee_username_for_lead(db, lead)
        if role == 'admin':
            pass
        elif role == 'leader':
            downline = _get_network_usernames(db, username)
            if _lid_u != username and _lid_u not in downline:
                return {'ok': False, 'error': 'You can only set reminder for your own or downline leads'}, 403
        else:
            if sqlite_row_get(lead, 'assigned_user_id') != acting_user_id():
                return {'ok': False, 'error': 'Forbidden'}, 403

        now_str = _now_ist().strftime('%Y-%m-%d %H:%M:%S')
        # If setting a time and lead has no follow_up_date, set to today so it appears in Follow-up Queue
        lead_keys = lead.keys()
        follow_up_date = (lead['follow_up_date'] if 'follow_up_date' in lead_keys else '') or ''
        if reminder_time and not (follow_up_date and follow_up_date.strip()):
            follow_up_date = _now_ist().strftime('%Y-%m-%d')
            db.execute(
                "UPDATE leads SET follow_up_time=?, follow_up_date=?, updated_at=? WHERE id=?",
                (reminder_time, follow_up_date, now_str, lead_id)
            )
            if _is_fresh_lead(lead):
                add_points(username, 'FOLLOWUP_SET', f"Set follow-up for lead #{lead_id} at {reminder_time}", lead_id=lead_id)
        elif reminder_time:
            db.execute(
                "UPDATE leads SET follow_up_time=?, updated_at=? WHERE id=?",
                (reminder_time, now_str, lead_id)
            )
            if _is_fresh_lead(lead):
                add_points(username, 'FOLLOWUP_SET', f"Updated follow-up for lead #{lead_id} at {reminder_time}", lead_id=lead_id)
        else:
            db.execute(
                "UPDATE leads SET follow_up_time=?, updated_at=? WHERE id=?",
                ('', now_str, lead_id)
            )
        db.commit()
        return {'ok': True}



    @app.route('/retarget')
    @login_required
    def retarget():
        db = get_db()
        role = session.get('role', 'team')
        username = acting_username()
        rt_placeholders = ','.join('?' * len(RETARGET_TAGS))
        query  = f"""SELECT * FROM leads
                    WHERE in_pool=0 AND deleted_at=''
                    AND status NOT IN ('Converted','Fully Converted','Lost')
                    AND (call_result IN ({rt_placeholders}) OR status='Retarget')"""
        params = list(RETARGET_TAGS)

        if role == 'admin':
            pass  # sees all
        elif role == 'leader':
            mem_ids = list(network_user_ids_for_username(db, username))
            if not mem_ids:
                query += " AND 1=0"
            else:
                phm = ",".join("?" * len(mem_ids))
                query += f" AND assigned_user_id IN ({phm})"
                params.extend(mem_ids)
        else:
            query += " AND assigned_user_id=?"
            params.append(acting_user_id())

        query += " ORDER BY updated_at DESC"
        leads_list = db.execute(query, params).fetchall()
        leads_list = _enrich_leads([dict(r) for r in leads_list])
        for L in leads_list:
            if role == 'team':
                L['retarget_status_opts'] = team_status_dropdown_choices(L.get('status'))
            else:
                L['retarget_status_opts'] = STATUSES

        # For leader/admin: fetch members for assign dropdown
        downline_members = []
        if role in ('leader', 'admin'):
            if role == 'leader':
                try:
                    dl = _get_network_usernames(db, username)
                    members = [u for u in dl if u != username]
                except Exception:
                    members = []
                if not members:
                    # Fallback: show all approved team/leader members
                    rows = db.execute(
                        "SELECT username FROM users WHERE role IN ('team','leader') AND status='approved' AND username!=? ORDER BY username",
                        (username,)
                    ).fetchall()
                    members = [r['username'] for r in rows]
                downline_members = members
            else:
                rows = db.execute(
                    "SELECT username FROM users WHERE role IN ('team','leader') AND status='approved' ORDER BY username"
                ).fetchall()
                downline_members = [r['username'] for r in rows]

        return render_template('retarget.html',
                               leads=leads_list,
                               call_result_tags=CALL_RESULT_TAGS,
                               statuses=STATUSES,
                               user_role=role,
                               downline_members=downline_members,
                               csrf_token=session.get('_csrf_token', ''))




    @app.route('/old-leads')
    @login_required
    @safe_route
    def old_leads():
        db     = get_db()
        search = request.args.get('q', '').strip()
        role   = session.get('role')

        # Lost / Pending (classic archive) + blank / unknown statuses (safety net so nothing “vanishes”)
        _home_list = sorted(WORKING_BOARD_HOME_STATUSES)
        _home_ph = ','.join('?' * len(_home_list))
        _arch_cond = (
            "(status IN ('Lost','Pending') OR TRIM(COALESCE(status,'')) = '' "
            "OR status NOT IN (" + _home_ph + "))"
        )
        base = "SELECT * FROM leads WHERE in_pool=0 AND deleted_at='' AND " + _arch_cond
        params = list(_home_list)

        if role != 'admin':
            base = (
                "SELECT * FROM leads WHERE in_pool=0 AND deleted_at='' "
                "AND assigned_user_id=? AND " + _arch_cond
            )
            params = [acting_user_id()] + list(_home_list)

        if search:
            if role == 'admin':
                base  += (
                    " AND (name LIKE ? OR phone LIKE ? OR email LIKE ? OR EXISTS ("
                    "SELECT 1 FROM users u WHERE u.id = leads.assigned_user_id "
                    "AND (u.username LIKE ? OR u.name LIKE ? OR u.fbo_id LIKE ?))"
                )
                params += [f'%{search}%', f'%{search}%', f'%{search}%',
                             f'%{search}%', f'%{search}%', f'%{search}%']
            else:
                base  += " AND (name LIKE ? OR phone LIKE ? OR email LIKE ?)"
                params += [f'%{search}%', f'%{search}%', f'%{search}%']

        base += " ORDER BY updated_at DESC"
        leads_list = db.execute(base, params).fetchall()
        return render_template('old_leads.html', leads=leads_list, search=search, role=role)



    @app.route('/leads/<int:lead_id>/status', methods=['POST'])
    @login_required
    def update_status(lead_id):
        new_status = request.form.get('status')
        source_bucket = (request.form.get('source_bucket') or '').strip().lower()
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        actor = acting_username() or ''

        if new_status not in STATUSES:
            code = incident_code("REL-STS")
            emit_event(
                app.logger,
                "status_update_invalid_status",
                code=code,
                actor=actor,
                lead_id=lead_id,
                new_status=new_status,
            )
            if is_ajax:
                return {'ok': False, 'error': safe_user_error('Invalid status', code)}, 400
            flash(safe_user_error('Invalid status.', code), 'danger')
            return redirect(url_for('leads'))

        db = get_db()

        def _status_block(msg: str, http_code: int = 403, family: str = 'REL-STS'):
            code = incident_code(family)
            emit_event(
                app.logger,
                "status_update_blocked",
                code=code,
                actor=actor,
                lead_id=lead_id,
                current_status=(lead['status'] if lead else ''),
                requested_status=new_status,
                reason=msg,
            )
            try:
                _log_activity(
                    db,
                    actor,
                    'status_update_blocked',
                    f'lead={lead_id} to={new_status} reason={msg} code={code}',
                )
            except Exception:
                pass
            if is_ajax:
                return {'ok': False, 'error': safe_user_error(msg, code)}, http_code
            flash(safe_user_error(msg, code), 'danger')
            return redirect(request.referrer or url_for('leads'))

        lead = db.execute("SELECT * FROM leads WHERE id=? AND in_pool=0 AND deleted_at=''", (lead_id,)).fetchone()
        if not lead:
            return _status_block('Lead not found.', 404, 'REL-STS')

        if session.get('role') != 'admin':
            _my = acting_user_id()
            _un = acting_username() or ''
            if _my is None:
                return _status_block('Access denied.', 403, 'REL-AUTH')
            if session.get('role') in ('team', 'leader'):
                if not actor_may_use_assignee_execution_routes(
                    db,
                    lead,
                    role=session.get('role', 'team'),
                    acting_uid=_my,
                    acting_un=_un,
                ):
                    return _status_block('Access denied.', 403, 'REL-AUTH')

        # --- TEAM ROLE RESTRICTIONS ---
        if session.get('role') == 'team':
            # Block forbidden statuses (Day 1/2/3, Closing, etc.) — use ready-for-day1 route instead
            if new_status in TEAM_FORBIDDEN_STATUSES:
                msg = f"Team members cannot set status to '{new_status}'."
                return _status_block(msg, 403, 'REL-STS')

        if new_status == 'Paid ₹196' and session.get('role') in ('team', 'leader'):
            _blocked, msg = rupees_196_execution_blocked_for_role(
                lead,
                role=session.get('role', 'team'),
                acting_user_id=acting_user_id(),
                current_status=(lead['status'] or '').strip(),
                is_transition_to_paid_196_funnel=True,
                gate_enabled=_rupees_196_gate_enabled(db),
            )
            if _blocked:
                return _status_block(msg, 422, 'REL-STS')

        if not _role_owns_status(session.get('role', 'team'), new_status):
            msg = f"Role '{session.get('role', 'team')}' cannot set status '{new_status}'."
            return _status_block(msg, 403, 'REL-AUTH')

        if new_status == 'Day 1' and session.get('role') == 'leader':
            _lk0 = lead.keys()
            _pipe0 = lead['pipeline_stage'] if 'pipeline_stage' in _lk0 else 'prospecting'
            _st0 = (lead['status'] or '').strip()
            is_enrolled = _pipe0 == 'enrolled' or _st0 == 'Paid ₹196'
            if not is_enrolled:
                return _status_block(
                    'Lead must be in Enrolled stage (Paid ₹196) before moving to Day 1.',
                    422,
                    'REL-STS',
                )

        _cur_status = (lead['status'] or '').strip()
        _post_196_statuses = {'Paid ₹196', 'Day 1', 'Day 2', 'Interview', 'Track Selected', 'Seat Hold Confirmed', 'Fully Converted'}
        if (
            _strict_flow_guard_enabled(db)
            and session.get('role') not in ('admin', 'leader')
            and not (
                session.get('role') == 'team'
                and _cur_status not in _post_196_statuses
            )
            and not is_valid_forward_status_transition(
                lead['status'], new_status, for_team=(session.get('role') == 'team')
            )
        ):
            _log_activity(
                db, acting_username(), 'status_skip_blocked',
                f"Lead #{lead_id}: {lead['status']} -> {new_status}"
            )
            msg = f"Invalid jump: '{lead['status']}' -> '{new_status}' is not allowed."
            return _status_block(msg, 422, 'REL-STS')

        # Duplicate check: prevent same phone/name from being pushed to Day 1/2/3 twice
        if new_status in ('Day 1', 'Day 2', 'Interview') and lead['phone']:
            dup = db.execute(
                "SELECT name, status FROM leads WHERE phone=? AND id!=? AND status=? AND in_pool=0 AND deleted_at=''",
                (lead['phone'], lead_id, new_status)
            ).fetchone()
            if dup:
                msg = f"Duplicate! {dup['name']} already exists in {new_status} with same phone number."
                return _status_block(msg, 409, 'REL-STS')

        # Duplicate check: prevent same phone from appearing in Enrolled twice
        if new_status == 'Paid ₹196' and lead['phone']:
            dup_enrolled = db.execute(
                "SELECT name, status FROM leads "
                "WHERE phone=? AND id!=? AND status='Paid \u20b9196' "
                "AND in_pool=0 AND deleted_at=''",
                (lead['phone'], lead_id)
            ).fetchone()
            if dup_enrolled:
                msg = (f"Duplicate! {dup_enrolled['name']} already exists in Enrolled "
                       f"({dup_enrolled['status']}) with same phone number.")
                return _status_block(msg, 409, 'REL-STS')

        new_pipeline_stage = STATUS_TO_STAGE.get(new_status, 'prospecting')
        lead_pipeline_stage = lead['pipeline_stage'] if 'pipeline_stage' in lead.keys() else 'prospecting'
        stage_changed = new_pipeline_stage != lead_pipeline_stage
        now_str = _now_ist().strftime('%Y-%m-%d %H:%M:%S')

        _lk = lead.keys()
        _sh = float(lead['seat_hold_amount'] or 0) if 'seat_hold_amount' in _lk else 0.0
        _tp = float(lead['track_price'] or 0) if 'track_price' in _lk else 0.0
        if new_status == 'Seat Hold Confirmed' and _sh <= 0:
            msg = 'Seat Hold Confirmed requires seat_hold_amount > 0.'
            return _status_block(msg, 400, 'REL-STS')
        if new_status == 'Fully Converted' and _tp <= 0:
            msg = 'Fully Converted requires track_price > 0.'
            return _status_block(msg, 400, 'REL-STS')

        if stage_changed:
            _transition_stage(db, lead_id, new_pipeline_stage, acting_username(), status_override=new_status)
            lead2 = db.execute(
                "SELECT * FROM leads WHERE id=? AND in_pool=0 AND deleted_at=''", (lead_id,)
            ).fetchone()
            if lead2:
                _pd, _pa = payment_fields_after_status_change(lead2, new_status)
                _sh2 = float(lead2['seat_hold_amount'] or 0) if 'seat_hold_amount' in lead2.keys() else 0.0
                _tp2 = float(lead2['track_price'] or 0) if 'track_price' in lead2.keys() else 0.0
                _okv, _errv = validate_lead_business_rules(new_status, _pd, _pa, _sh2, _tp2)
                if not _okv:
                    app.logger.warning('update_status blocked: %s', _errv)
                    return _status_block(_errv, 400, 'REL-STS')
                apply_leads_update(
                    db,
                    {'payment_done': _pd, 'payment_amount': _pa},
                    where_sql="id=? AND in_pool=0 AND deleted_at=''",
                    where_params=(lead_id,),
                    log_context='update_status stage_changed payment',
                )
            if new_status == 'Day 1' and _is_fresh_lead(lead):
                _was_paid = lead['payment_done'] if 'payment_done' in lead.keys() else 0
                if not _was_paid:
                    add_points(acting_username(), 'CONVERSION', f"Converted lead #{lead_id} (Paid ₹196 via dropdown)", db=db, lead_id=lead_id)
        else:
            _entering_pipeline = new_status in PIPELINE_AUTO_EXPIRE_STATUSES
            _pipe_entered = now_str if _entering_pipeline else ''
            _pd, _pamt = payment_fields_after_status_change(lead, new_status)
            _okv, _errv = validate_lead_business_rules(new_status, _pd, _pamt, _sh, _tp)
            if not _okv:
                app.logger.warning('update_status blocked: %s', _errv)
                return _status_block(_errv, 400, 'REL-STS')
            apply_leads_update(
                db,
                {
                    'status': new_status,
                    'pipeline_stage': new_pipeline_stage,
                    'pipeline_entered_at': _pipe_entered,
                    'payment_done': _pd,
                    'payment_amount': _pamt,
                },
                where_sql="id=? AND in_pool=0 AND deleted_at=''",
                where_params=(lead_id,),
                log_context='update_status same-stage',
            )

        # Clear follow-up when lead is Lost or Retarget — no more reminders/penalties
        if new_status in ('Lost', 'Retarget'):
            db.execute(
                "UPDATE leads SET follow_up_date='', follow_up_time='', updated_at=? WHERE id=?",
                (now_str, lead_id),
            )

        _log_lead_event(db, lead_id, acting_username(), f'Status to {new_status}')
        _log_activity(db, acting_username(), 'lead_status_change',
                      f'{lead["name"]} to {new_status}')

        if session.get('role') == 'team' and new_status == 'Paid ₹196':
            advanced = _team_handoff_to_leader(db, lead_id, lead, now_str)
            if advanced:
                new_status = 'Day 1'
                new_pipeline_stage = 'day1'
                stage_changed = True
        elif session.get('role') == 'leader' and new_status == 'Paid ₹196':
            _leader_un = acting_username()
            _leader_uid = user_id_for_username(db, _leader_un)
            if _leader_day1_routing_on(db, _leader_un):
                new_status = 'Day 1'
                new_pipeline_stage = 'day1'
                stage_changed = True
                _d1_fields = {}
                if _leader_uid:
                    _d1_fields["assigned_user_id"] = _leader_uid
                if _d1_fields:
                    apply_leads_update(
                        db, _d1_fields,
                        where_sql="id=? AND in_pool=0 AND deleted_at=''",
                        where_params=(lead_id,),
                        log_context="leader_196_day1_assign",
                    )
            db.execute(
                "UPDATE leads SET enrolled_at=?, enrolled_by=? WHERE id=? AND TRIM(COALESCE(enrolled_at,''))=''",
                (now_str, _leader_un, lead_id),
            )
        # Stamp enrolled_at + enrolled_by for admin Paid ₹196
        elif new_status == 'Paid ₹196' and session.get('role') == 'admin':
            db.execute(
                "UPDATE leads SET enrolled_at=?, enrolled_by=? WHERE id=? AND TRIM(COALESCE(enrolled_at,''))=''",
                (now_str, acting_username(), lead_id),
            )

        # History tab: bump claimed_at for today/history bucketing and updated_at so SLA watch anchor matches this action.
        if source_bucket == 'history':
            db.execute(
                "UPDATE leads SET claimed_at=?, updated_at=? WHERE id=? AND in_pool=0 AND deleted_at=''",
                (now_str, now_str, lead_id),
            )

        new_badges = _check_and_award_badges(db, _assignee_username_for_lead(db, lead))
        lead_after = None
        try:
            lead_after = db.execute(
                "SELECT status, pipeline_stage, claimed_at FROM leads WHERE id=?",
                (lead_id,),
            ).fetchone()
        except Exception:
            lead_after = None

        db.commit()

        if is_ajax:
            return {'ok': True, 'status': new_status,
                    'stage_changed': stage_changed,
                    'new_stage': new_pipeline_stage if stage_changed else None,
                    'new_badges': [BADGE_DEFS[k]['label'] for k in new_badges if k in BADGE_DEFS]}

        flash('Status updated.', 'success')
        return redirect(request.referrer or url_for('leads'))


    @app.route('/leads/<int:lead_id>/ready-for-day1', methods=['POST'])
    @login_required
    def ready_for_day1(lead_id):
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        db = get_db()
        lead = db.execute(
            "SELECT * FROM leads WHERE id=? AND in_pool=0 AND deleted_at=''", (lead_id,)
        ).fetchone()
        if not lead:
            if is_ajax:
                return {'ok': False, 'error': 'Not found'}, 404
            flash('Lead not found.', 'danger')
            return redirect(url_for('leads'))

        # Team cannot push beyond ₹196. Day 1 transitions are leader/admin only.
        if session.get('role') == 'team':
            if is_ajax:
                return {'ok': False, 'error': 'Team cannot move leads to Day 1'}, 403
            flash('Team cannot move leads to Day 1.', 'danger')
            return redirect(url_for('leads'))

        # Leader (own/downline assignee) or admin can trigger this
        role = session.get('role', 'team')
        if role == 'admin':
            pass
        elif role == 'leader':
            if not actor_may_use_assignee_execution_routes(
                db,
                lead,
                role='leader',
                acting_uid=acting_user_id(),
                acting_un=acting_username() or '',
            ):
                if is_ajax:
                    return {'ok': False, 'error': 'Access denied'}, 403
                flash('Access denied.', 'danger')
                return redirect(url_for('leads'))
        else:
            if is_ajax:
                return {'ok': False, 'error': 'Access denied'}, 403
            flash('Access denied.', 'danger')
            return redirect(url_for('leads'))

        # Idempotent: already in Day 1
        if lead['status'] == 'Day 1':
            if is_ajax:
                return {'ok': True, 'status': 'Day 1', 'note': 'already moved'}
            flash('Lead is already in Day 1.', 'info')
            return redirect(url_for('leads'))

        # Flexible check: either pipeline_stage or status confirms enrolled
        is_enrolled = (
            lead['pipeline_stage'] == 'enrolled'
            or lead['status'] == 'Paid ₹196'
        )
        if not is_enrolled:
            msg = 'Lead must be in Enrolled stage (Paid ₹196) before moving to Day 1.'
            if is_ajax:
                return {'ok': False, 'error': msg}, 422
            flash(msg, 'danger')
            return redirect(url_for('leads'))

        # Duplicate check: same phone already in Day 1?
        if lead['phone']:
            dup = db.execute(
                "SELECT name FROM leads WHERE phone=? AND id!=? AND status='Day 1' "
                "AND in_pool=0 AND deleted_at=''",
                (lead['phone'], lead_id)
            ).fetchone()
            if dup:
                msg = f"Duplicate! {dup['name']} already exists in Day 1."
                if is_ajax:
                    return {'ok': False, 'error': msg}, 409
                flash(msg, 'danger')
                return redirect(url_for('leads'))

        now_str = _now_ist().strftime('%Y-%m-%d %H:%M:%S')
        _transition_stage(db, lead_id, 'day1', acting_username(), status_override='Day 1')
        lead2 = db.execute(
            "SELECT * FROM leads WHERE id=? AND in_pool=0 AND deleted_at=''", (lead_id,)
        ).fetchone()
        if lead2:
            _pd, _pa = payment_fields_after_status_change(lead2, 'Day 1')
            _okv, _errv = validate_lead_business_rules(
                'Day 1', _pd, _pa,
                float(lead2['seat_hold_amount'] or 0) if 'seat_hold_amount' in lead2.keys() else 0.0,
                float(lead2['track_price'] or 0) if 'track_price' in lead2.keys() else 0.0,
            )
            if not _okv:
                app.logger.warning('ready_for_day1 blocked: %s', _errv)
                if is_ajax:
                    return {'ok': False, 'error': _errv}, 400
                flash(_errv, 'danger')
                return redirect(url_for('leads'))
            apply_leads_update(
                db,
                {
                    'pipeline_stage': 'day1',
                    'status': 'Day 1',
                    'payment_done': _pd,
                    'payment_amount': _pa,
                },
                where_sql="id=? AND in_pool=0 AND deleted_at=''",
                where_params=(lead_id,),
                log_context='ready_for_day1',
            )
        _was_paid = lead['payment_done'] if 'payment_done' in lead.keys() else 0
        if not _was_paid and _is_fresh_lead(lead):
            add_points(acting_username(), 'CONVERSION',
                       f"Converted lead #{lead_id} (Ready for Day 1)", db=db, lead_id=lead_id)
        _log_lead_event(db, lead_id, acting_username(), 'Status to Day 1 (Ready for Day 1)')
        _log_activity(db, acting_username(), 'lead_status_change',
                      f'{lead["name"]} to Day 1')
        _check_and_award_badges(db, _assignee_username_for_lead(db, lead))
        db.commit()

        if is_ajax:
            return {'ok': True, 'status': 'Day 1'}
        flash('Lead moved to Day 1!', 'success')
        return redirect(url_for('leads'))


    @app.route('/leads/<int:lead_id>/call-result', methods=['POST'])
    @login_required
    def update_call_result(lead_id):
        tag = request.form.get('call_result', '').strip()
        if not call_result_allowed(tag):
            return {'ok': False, 'error': 'Invalid tag'}, 400
        db = get_db()
        lead = db.execute(
            "SELECT * FROM leads WHERE id=? AND in_pool=0 AND deleted_at=''",
            (lead_id,),
        ).fetchone()
        if not lead:
            return {'ok': False, 'error': 'Not found'}, 404
        role = session.get('role', 'team')
        if not actor_may_use_assignee_execution_routes(
            db,
            lead,
            role=role,
            acting_uid=acting_user_id(),
            acting_un=acting_username() or '',
        ):
            return {'ok': False, 'error': 'Access denied'}, 403

        old_call_result = lead['call_result'] or ''
        if _is_fresh_lead(lead) and tag in ('Connected', 'Spoke to lead', 'Hot Lead') and old_call_result not in ('Connected', 'Spoke to lead', 'Hot Lead'):
            add_points(acting_username(), 'CONNECTED_CALL', f"Connected with lead #{lead_id} (Quick Action)", db=db)

        now_str = _now_ist().strftime('%Y-%m-%d %H:%M:%S')
        today_d = _today_ist().strftime('%Y-%m-%d')
        fu = (lead['follow_up_date'] or '').strip() if lead['follow_up_date'] is not None else ''
        cs = (lead['call_status'] or '').strip() if lead['call_status'] is not None else ''
        new_fu, new_cs = fu, cs
        # Pool claim Rule 8 needs follow_up_date + calling status for "interested" rows; quick panel
        # only saved call_result before, leaving follow_up_date empty.
        # Team members do not own follow-up scheduling — never auto-set follow_up_date for them.
        if tag in ('Hot Lead', 'Call Later', 'Follow-up Needed'):
            if session.get('role') != 'team' and not fu:
                new_fu = today_d
            if tag == 'Hot Lead':
                new_cs = 'Called - Interested'
            else:
                new_cs = 'Called - Follow Up'
        elif tag == 'Not Interested':
            # SSOT daily call counts use call_status (see LEAD_SQL_CALL_LOGGED); without this,
            # panel saves counted in UI but not in get_today_metrics / gate assistant.
            new_cs = 'Called - Not Interested'

        db.execute(
            "UPDATE leads SET call_result=?, updated_at=?, follow_up_date=?, call_status=? WHERE id=? AND in_pool=0",
            (tag, now_str, new_fu, new_cs, lead_id),
        )
        db.commit()
        return {'ok': True, 'call_result': tag}

    @app.route('/leads/<int:lead_id>/delete', methods=['GET', 'POST'])
    @login_required
    def delete_lead(lead_id):
        """Soft-delete: move to recycle bin."""
        db = get_db()
        if session.get('role') == 'admin':
            lead = db.execute(
                "SELECT name FROM leads WHERE id=? AND in_pool=0 AND deleted_at=''", (lead_id,)
            ).fetchone()
        else:
            lead = db.execute(
                "SELECT name FROM leads WHERE id=? AND assigned_user_id=? AND in_pool=0 AND deleted_at=''",
                (lead_id, acting_user_id()),
            ).fetchone()

        is_ajax = request.is_json or request.headers.get('Content-Type', '').startswith('application/json')

        if lead:
            if session.get('role') == 'admin':
                owner_gap = db.execute(
                    "SELECT id FROM leads WHERE id=? AND in_pool=0 AND (assigned_user_id IS NULL OR assigned_user_id=0)",
                    (lead_id,),
                ).fetchone()
                if owner_gap:
                    app.logger.critical(
                        "archive_blocked_owner_missing lead_id=%s actor=%s",
                        lead_id,
                        acting_username(),
                    )
                    if is_ajax:
                        return jsonify({'ok': False, 'error': 'Owner missing. Lead flagged to admin; archive blocked.'}), 409
                    flash('Owner missing for this lead. Archive blocked and flagged to admin.', 'danger')
                    return redirect(url_for('leads'))
            db.execute(
                "UPDATE leads SET deleted_at=? WHERE id=?", (_now_ist().strftime('%Y-%m-%d %H:%M:%S'), lead_id)
            )
            assert_lead_owner_invariant(db, context='delete_lead_archive_guard')
            db.commit()
            if is_ajax:
                return jsonify({'ok': True})
            flash(f'Lead "{lead["name"]}" moved to Recycle Bin.', 'warning')
        else:
            if is_ajax:
                return jsonify({'ok': False, 'error': 'Lead not found or access denied.'})
            flash('Lead not found or access denied.', 'danger')
        return redirect(url_for('leads'))

    @app.route('/leads/recycle-bin')
    @login_required
    def recycle_bin():
        db = get_db()
        if session.get('role') == 'admin':
            deleted_leads = db.execute(
                "SELECT * FROM leads WHERE in_pool=0 AND deleted_at!='' ORDER BY deleted_at DESC"
            ).fetchall()
        else:
            deleted_leads = db.execute(
                "SELECT * FROM leads WHERE in_pool=0 AND deleted_at!='' AND assigned_user_id=? ORDER BY deleted_at DESC",
                (acting_user_id(),),
            ).fetchall()
        return render_template('recycle_bin.html', leads=deleted_leads)

    @app.route('/leads/<int:lead_id>/restore', methods=['POST'])
    @login_required
    def restore_lead(lead_id):
        db = get_db()
        if session.get('role') == 'admin':
            lead = db.execute(
                "SELECT name FROM leads WHERE id=? AND deleted_at!=''", (lead_id,)
            ).fetchone()
        else:
            lead = db.execute(
                "SELECT name FROM leads WHERE id=? AND assigned_user_id=? AND deleted_at!=''",
                (lead_id, acting_user_id()),
            ).fetchone()

        if lead:
            db.execute("UPDATE leads SET deleted_at='' WHERE id=?", (lead_id,))
            db.commit()
            flash(f'Lead "{lead["name"]}" restored successfully.', 'success')
        else:
            flash('Lead not found or access denied.', 'danger')
        return redirect(url_for('recycle_bin'))

    @app.route('/leads/<int:lead_id>/permanent-delete', methods=['POST'])
    @admin_required
    def permanent_delete_lead(lead_id):
        db   = get_db()
        lead = db.execute(
            "SELECT name FROM leads WHERE id=? AND deleted_at!=''", (lead_id,)
        ).fetchone()
        if lead:
            db.execute("DELETE FROM lead_notes WHERE lead_id=?", (lead_id,))
            db.execute("DELETE FROM leads WHERE id=?", (lead_id,))
            db.commit()
            flash(f'Lead "{lead["name"]}" permanently deleted.', 'danger')
        else:
            flash('Lead not found in recycle bin.', 'danger')
        return redirect(url_for('recycle_bin'))

    @app.route('/leads/export')
    @login_required
    def export_leads():
        db     = get_db()
        username = acting_username()
        if session.get('role') == 'admin':
            rows = db.execute(
                "SELECT * FROM leads WHERE in_pool=0 AND deleted_at='' ORDER BY created_at DESC"
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT * FROM leads WHERE assigned_user_id=? AND in_pool=0 AND deleted_at='' ORDER BY created_at DESC",
                (acting_user_id(),),
            ).fetchall()
        buf = io.StringIO()
        cols = ['id','name','phone','email','city','referred_by','assigned_user_id','source',
                'status','payment_done','payment_amount','revenue','day1_done','day2_done',
                'interview_done','follow_up_date','notes','created_at','updated_at']
        writer = csv.writer(buf)
        writer.writerow(cols)
        for r in rows:
            writer.writerow([r[c] for c in cols])
        buf.seek(0)
        fname = f"leads_{_today_ist().isoformat()}.csv"
        return Response(buf.getvalue(), mimetype='application/octet-stream',
                        headers={'Content-Disposition': f'attachment; filename="{fname}"'})

    @app.route('/leads/import', methods=['POST'])
    @login_required
    def import_leads():
        db          = get_db()
        username    = acting_username()
        is_admin    = session.get('role') == 'admin'
        file_type   = request.form.get('import_type', 'csv')
        source_tag  = request.form.get('source_tag', 'Import').strip() or 'Import'
        if is_admin:
            _aun = request.form.get('assigned_to', '').strip() or username
            import_owner_uid = user_id_for_username(db, _aun) or acting_user_id()
        else:
            import_owner_uid = acting_user_id()
        rows_list = []
        if file_type == 'pdf':
            f = request.files.get('import_file')
            if not f or not f.filename:
                flash('No file uploaded.', 'danger'); return redirect(url_for('leads'))
            rows_list, err = _extract_leads_from_pdf(f.stream)
            if err:
                flash(err, 'danger'); return redirect(url_for('leads'))
        else:  # csv
            f = request.files.get('import_file')
            if not f or not f.filename:
                flash('No file uploaded.', 'danger'); return redirect(url_for('leads'))
            try:
                content   = f.read().decode('utf-8-sig', errors='replace')
                reader    = csv.DictReader(io.StringIO(content))
                raw_rows  = list(reader)
                for row in raw_rows:
                    _fnn = (row.get('First Name') or row.get('first_name') or '').strip()
                    _lnn = (row.get('Last Name') or row.get('last_name') or '').strip()
                    name  = (row.get('Full Name') or row.get('full_name') or row.get('name') or row.get('Name') or ((_fnn + ' ' + _lnn).strip() if _fnn or _lnn else '') or '').strip()
                    phone = (row.get('Phone Number (Calling Number)') or row.get('phone_number') or row.get('phone') or row.get('Phone') or row.get('Phone Number') or '').strip()
                    email = (row.get('email') or row.get('Email') or row.get('email_address') or '').strip()
                    city  = (row.get('Your City Name') or row.get('city') or row.get('City') or '').strip()
                    src   = (row.get('source') or row.get('Source') or '').strip()
                    rows_list.append({'name': name, 'phone': phone, 'email': email, 'city': city, 'source': src})
            except Exception as e:
                flash(f'Could not parse CSV: {e}', 'danger'); return redirect(url_for('leads'))
        
        # Batch processing
        existing_phones = {r[0] for r in db.execute("SELECT phone FROM leads WHERE deleted_at=''").fetchall()}
        imported = skipped = 0
        batch_values = []
        for row in rows_list:
            name, phone = row.get('name', '').strip(), row.get('phone', '').strip()
            if (not name and not phone) or (phone in existing_phones):
                skipped += 1; continue
            existing_phones.add(phone)
            batch_values.append((name, phone, row.get('email', '').strip(), import_owner_uid, row.get('source', '').strip() or source_tag, row.get('city', '').strip()))
            imported += 1
        
        _BATCH_SZ = 50
        for i in range(0, len(batch_values), _BATCH_SZ):
            db.executemany(
                "INSERT INTO leads (name, phone, email, assigned_to, assigned_user_id, source, status, in_pool, pool_price, claimed_at, city, notes) "
                "VALUES (?, ?, ?, '', ?, ?, 'New', 0, 0, NULL, ?, '')",
                batch_values[i:i + _BATCH_SZ],
            )
            db.commit()
        flash(f'Import complete: {imported} added, {skipped} skipped.', 'success')
        return redirect(url_for('leads'))

    @app.route('/leads/bulk-action', methods=['POST'])
    @login_required
    def bulk_action():
        action, lead_ids = request.form.get('bulk_action', ''), request.form.getlist('lead_ids')
        if not lead_ids: flash('No leads selected.', 'warning'); return redirect(url_for('leads'))
        lead_ids = [int(i) for i in lead_ids if i.isdigit()]
        db = get_db()
        ph = ','.join('?' for _ in lead_ids)
        if session.get('role') == 'admin':
            where, params = f"id IN ({ph}) AND in_pool=0", lead_ids
        else:
            where, params = f"id IN ({ph}) AND assigned_user_id=? AND in_pool=0", lead_ids + [acting_user_id()]

        if action == 'delete':
            db.execute(f"UPDATE leads SET deleted_at=? WHERE {where}", [_now_ist().strftime('%Y-%m-%d %H:%M:%S')] + params)
            flash(f'Moved {len(lead_ids)} leads to Recycle Bin.', 'warning')
        elif action.startswith('status:'):
            original_ns = action.split(':', 1)[1]
            ns = original_ns
            if session.get('role') == 'team' and original_ns not in set(TEAM_ALLOWED_STATUSES):
                flash('That bulk status is not available for team members.', 'danger')
                return redirect(url_for('leads'))
            # Team/leader: Paid ₹196 bulk → Day 1 + paid; same gates as single-lead (proof + leader admin OK).
            if session.get('role') in ('team', 'leader') and original_ns == 'Paid ₹196':
                ns = 'Day 1'

            if original_ns in STATUSES:
                _pstage = STATUS_TO_STAGE.get(ns, 'prospecting')
                _n_ok = 0
                _skipped_no_proof = 0
                _skipped_wrong_stage = 0
                _skipped_pending_approval = 0
                _bulk_leader_ids = None
                if session.get('role') == 'leader':
                    _bulk_leader_ids = network_user_ids_for_username(
                        db, acting_username() or ''
                    )
                for lid in lead_ids:
                    if session.get('role') == 'admin':
                        _row = db.execute(
                            "SELECT * FROM leads WHERE id=? AND in_pool=0 AND deleted_at=''",
                            (lid,),
                        ).fetchone()
                    elif session.get('role') == 'leader':
                        _row = db.execute(
                            "SELECT * FROM leads WHERE id=? AND in_pool=0 AND deleted_at=''",
                            (lid,),
                        ).fetchone()
                        if _row:
                            try:
                                _au_b = int(
                                    sqlite_row_get(_row, 'assigned_user_id') or 0
                                )
                            except (TypeError, ValueError):
                                _au_b = 0
                            if _bulk_leader_ids is not None and _au_b not in _bulk_leader_ids:
                                _row = None
                    else:
                        _row = db.execute(
                            "SELECT * FROM leads WHERE id=? AND assigned_user_id=? AND in_pool=0 AND deleted_at=''",
                            (lid, acting_user_id()),
                        ).fetchone()
                    if not _row:
                        continue
                    if session.get('role') in ('team', 'leader') and original_ns == 'Paid ₹196':
                        _blocked_b, _bulk_msg = rupees_196_execution_blocked_for_role(
                            _row,
                            role=session.get('role', 'team'),
                            acting_user_id=acting_user_id(),
                            current_status=(sqlite_row_get(_row, 'status') or '').strip(),
                            is_transition_to_paid_196_funnel=True,
                            gate_enabled=_rupees_196_gate_enabled(db),
                        )
                        if _blocked_b:
                            _proof_b = (sqlite_row_get(_row, 'payment_proof_path') or '').strip()
                            _ap_b = payment_proof_approval_status_value(_row)
                            if not (_proof_b or '').strip():
                                _skipped_no_proof += 1
                            elif _ap_b in ('pending', 'rejected') and (
                                session.get('role') == 'team'
                                or (
                                    session.get('role') == 'leader'
                                    and leader_own_assigned_lead(_row, acting_user_id())
                                )
                            ):
                                _skipped_pending_approval += 1
                            else:
                                _skipped_wrong_stage += 1
                            app.logger.warning(
                                'bulk Paid→Day1 skipped lead %s: %s',
                                lid,
                                _bulk_msg,
                            )
                            continue
                    _pd_b, _pa_b = payment_fields_after_status_change(_row, ns)
                    _rk = _row.keys()
                    _okv, _errv = validate_lead_business_rules(
                        ns,
                        _pd_b,
                        _pa_b,
                        float(_row['seat_hold_amount'] or 0) if 'seat_hold_amount' in _rk else 0.0,
                        float(_row['track_price'] or 0) if 'track_price' in _rk else 0.0,
                    )
                    if not _okv:
                        app.logger.warning('bulk status skipped lead %s: %s', lid, _errv)
                        continue
                    apply_leads_update(
                        db,
                        {
                            'status': ns,
                            'pipeline_stage': _pstage,
                            'payment_done': _pd_b,
                            'payment_amount': _pa_b,
                        },
                        where_sql="id=? AND in_pool=0 AND deleted_at=''",
                        where_params=(lid,),
                        log_context='bulk status',
                    )
                    # Stamp enrolled_at + enrolled_by for any enrollment-path bulk action
                    if original_ns == 'Paid ₹196':
                        _now_bulk = _now_ist().strftime('%Y-%m-%d %H:%M:%S')
                        db.execute(
                            "UPDATE leads SET enrolled_at=?, enrolled_by=? WHERE id=? AND TRIM(COALESCE(enrolled_at,''))=''",
                            (_now_bulk, acting_username(), lid),
                        )
                    _n_ok += 1
                _msg = f'Status updated to "{ns}" for {_n_ok} lead(s).'
                if _skipped_no_proof:
                    _msg += (
                        f' Skipped {_skipped_no_proof} lead(s) without ₹196 payment proof '
                        '(upload proof on each lead first, same as single edit).'
                    )
                if _skipped_wrong_stage:
                    _msg += (
                        f' Skipped {_skipped_wrong_stage} lead(s) — ₹196 gate (proof / approval).'
                    )
                if _skipped_pending_approval:
                    _msg += (
                        f' Skipped {_skipped_pending_approval} lead(s) — leader ₹196 proof admin se pending/rejected hai.'
                    )
                flash(_msg, 'success')
                _ROUTE_LOG.info(
                    'bulk status ns=%s updated=%s skipped_no_proof=%s skipped_wrong_stage=%s skipped_pending_approval=%s',
                    ns,
                    _n_ok,
                    _skipped_no_proof,
                    _skipped_wrong_stage,
                    _skipped_pending_approval,
                )
        elif action == 'mark_paid':
            _marked = 0
            _mp_leader_ids = None
            if session.get('role') == 'leader':
                _mp_leader_ids = network_user_ids_for_username(
                    db, acting_username() or ''
                )
            for lid in lead_ids:
                if session.get('role') == 'admin':
                    row = db.execute(
                        "SELECT * FROM leads WHERE id=? AND in_pool=0 AND deleted_at=''",
                        (lid,),
                    ).fetchone()
                elif session.get('role') == 'leader':
                    row = db.execute(
                        "SELECT * FROM leads WHERE id=? AND in_pool=0 AND deleted_at=''",
                        (lid,),
                    ).fetchone()
                    if row:
                        try:
                            _au_m = int(sqlite_row_get(row, 'assigned_user_id') or 0)
                        except (TypeError, ValueError):
                            _au_m = 0
                        if _mp_leader_ids is not None and _au_m not in _mp_leader_ids:
                            row = None
                else:
                    row = db.execute(
                        "SELECT * FROM leads WHERE id=? AND assigned_user_id=? AND in_pool=0 AND deleted_at=''",
                        (lid, acting_user_id()),
                    ).fetchone()
                if not row or int(row['payment_done'] or 0) == 1:
                    continue
                _rrole = session.get('role', 'team')
                if _rrole in ('team', 'leader'):
                    _mb, _mm = rupees_196_execution_blocked_for_role(
                        row,
                        role=_rrole,
                        acting_user_id=acting_user_id(),
                        current_status=(row['status'] or '').strip(),
                        is_transition_to_paid_196_funnel=True,
                        gate_enabled=_rupees_196_gate_enabled(db),
                    )
                    if _mb:
                        app.logger.warning('bulk mark_paid skipped lead %s: %s', lid, _mm)
                        continue
                _pd, _pa = payment_columns_mark_paid(row)
                _rk = row.keys()
                _okv, _errv = validate_lead_business_rules(
                    row['status'],
                    _pd,
                    _pa,
                    float(row['seat_hold_amount'] or 0) if 'seat_hold_amount' in _rk else 0.0,
                    float(row['track_price'] or 0) if 'track_price' in _rk else 0.0,
                )
                if not _okv:
                    app.logger.warning('bulk mark_paid blocked lead %s: %s', lid, _errv)
                    continue
                apply_leads_update(
                    db,
                    {'payment_done': _pd, 'payment_amount': _pa},
                    where_sql="id=? AND in_pool=0 AND deleted_at=''",
                    where_params=(lid,),
                    log_context='bulk mark_paid',
                )
                add_points(_assignee_username_for_lead(db, row), 'CONVERSION', f"Converted lead #{lid} (Bulk)", db=db, lead_id=lid)
                _marked += 1
            _ROUTE_LOG.info('bulk mark_paid: marked %s lead(s)', _marked)
            flash(f'Marked {_marked} as paid.', 'success')
        db.commit()
        return redirect(url_for('leads'))

    @app.route('/leads/<int:lead_id>/batch-toggle', methods=['POST'])
    @login_required
    def batch_toggle(lead_id):
        data = request.get_json(silent=True) or {}
        batch = data.get('batch', '')
        force_mark = bool(data.get('force_mark', False))
        if batch not in ('d1_morning', 'd1_afternoon', 'd1_evening', 'd2_morning', 'd2_afternoon', 'd2_evening'):
            return {'ok': False, 'error': 'Invalid batch'}, 400
        db = get_db()
        row = db.execute("SELECT * FROM leads WHERE id=? AND in_pool=0 AND deleted_at=''", (lead_id,)).fetchone()
        if not row: return {'ok': False, 'error': 'Not found'}, 404
        role  = session.get('role', 'team')
        owner = _assignee_username_for_lead(db, row)

        if batch.startswith('d1_'):
            if role not in ('leader', 'admin'):
                return {'ok': False, 'error': 'Only leader/admin can mark Day 1 batches'}, 403
            if role == 'leader':
                downline = _get_network_usernames(db, acting_username())
                if owner != acting_username() and owner not in downline:
                    return {'ok': False, 'error': 'Forbidden'}, 403
        elif batch.startswith('d2_'):
            if role != 'admin':
                return {'ok': False, 'error': 'Only admin can mark Day 2 batches'}, 403
        else:
            if role != 'admin' and owner != acting_username():
                return {'ok': False, 'error': 'Forbidden'}, 403

        now_str = _now_ist().strftime('%Y-%m-%d %H:%M:%S')
        if force_mark:
            db.execute(
                f"UPDATE leads SET {batch}=1, updated_at=? WHERE id=?",
                (now_str, lead_id),
            )
        else:
            db.execute(
                f"UPDATE leads SET {batch} = CASE WHEN {batch}=1 THEN 0 ELSE 1 END, updated_at=? WHERE id=?",
                (now_str, lead_id),
            )
        updated_row = db.execute(f"SELECT {batch}, d1_morning, d1_afternoon, d1_evening, d2_morning, d2_afternoon, d2_evening FROM leads WHERE id=?", (lead_id,)).fetchone()
        new_val = updated_row[batch]

        day_prefix = batch[:2]
        if day_prefix == 'd1':
            all_done = bool(updated_row['d1_morning'] and updated_row['d1_afternoon'] and updated_row['d1_evening'])
        else:
            all_done = bool(updated_row['d2_morning'] and updated_row['d2_afternoon'] and updated_row['d2_evening'])

        # Use batch-specific action_type so idempotency is per-batch-per-lead-per-day
        add_points(owner, f'BATCH_MARKED_{batch.upper()}', f"Marked {batch} done", db=db, lead_id=lead_id, delta_batches=(1 if new_val else -1))

        today_score, _ = _get_today_score(db, owner)
        user_row = db.execute("SELECT total_points FROM users WHERE LOWER(username)=LOWER(?)", (owner,)).fetchone()
        lifetime_points = user_row['total_points'] if user_row else 0
        db.commit()
        return {
            'ok': True,
            'new_val': new_val,
            'all_done': all_done,
            'points': 15 if new_val else 0,
            'today_score': today_score,
            'lifetime_points': lifetime_points,
        }

    @app.route('/leads/<int:lead_id>/stage-advance', methods=['POST'])
    @login_required
    def stage_advance(lead_id):
        data = request.get_json(silent=True) or {}

        action = data.get('action', '')
        role = session.get('role', 'team')
        username = acting_username()
        ACTION_MAP = {
            'enroll_complete':   (['admin'], 'day1'),
            'day1_complete':     (['leader', 'admin'],           'day2'),
            'day2_complete':     (['admin'],                     'day3'),
            'interview_done':    (['leader', 'admin'],          'day3'),
            'seat_hold_done':    (['leader', 'admin'],          'seat_hold'),
            'fully_converted':   (['admin'],                    'closing'),
            'training_complete': (['admin'],                    'complete'),
            'mark_lost':         (['team', 'leader', 'admin'],  'lost'),
        }
        if action not in ACTION_MAP: return {'ok': False, 'error': 'Invalid action'}, 400
        allowed_roles, new_stage = ACTION_MAP[action]
        if role not in allowed_roles: return {'ok': False, 'error': 'Permission denied'}, 403
        db = get_db()
        lead = db.execute("SELECT * FROM leads WHERE id=? AND in_pool=0 AND deleted_at=''", (lead_id,)).fetchone()
        if not lead: return {'ok': False, 'error': 'Lead not found'}, 404

        if action == 'day2_complete':
            d2_ok = (
                lead['d2_morning'] and lead['d2_afternoon'] and lead['d2_evening']
                if 'd2_morning' in lead.keys()
                else False
            )
            if not d2_ok:
                return {'ok': False, 'error': 'Complete all Day 2 batches first'}, 400
            if not lead_day2_business_test_passed(lead):
                return {
                    'ok': False,
                    'error': 'Day 2 business test pass required (≥18/30) before Interview.',
                }, 400
        
        if role in ('team', 'leader'):
            if not actor_may_use_assignee_execution_routes(
                db,
                lead,
                role=role,
                acting_uid=acting_user_id(),
                acting_un=username,
            ):
                if role == 'team':
                    return {'ok': False, 'error': 'You can only advance your assigned pre-Day 1 leads'}, 403
                return {'ok': False, 'error': 'You can only advance your own or downline assigned leads'}, 403

        new_stage_result, new_owner = _transition_stage(db, lead_id, new_stage, username)
        _log_activity(db, username, 'stage_advance', f'Lead #{lead_id} {action} to {new_stage_result}')
        
        # Scoring logic for stage advancement? 
        # Usually stage transitions might add points. Let's ensure we return the latest points anyway.
        today_score, _ = _get_today_score(db, username)
        user_row = db.execute("SELECT total_points FROM users WHERE LOWER(username)=LOWER(?)", (username,)).fetchone()
        lifetime_points = user_row['total_points'] if user_row else 0
        
        db.commit()

        # iPhone contact auto-save via ntfy.sh (only on Day 1 → Day 2 push)
        if action == 'day1_complete':
            _ntfy_day2_contact(db, lead)

        return {
            'ok': True,
            'new_stage': new_stage_result,
            'new_owner': new_owner,
            'today_score': today_score,
            'lifetime_points': lifetime_points
        }

    @app.route('/leads/<int:lead_id>/timeline')
    @login_required
    @safe_route
    def lead_timeline(lead_id):
        db, role, username = get_db(), session.get('role', 'team'), acting_username()
        lead = db.execute("SELECT * FROM leads WHERE id=? AND in_pool=0 AND deleted_at=''", (lead_id,)).fetchone()
        if not lead: return jsonify({'ok': False, 'error': 'Lead not found'}), 404
        if not actor_may_use_assignee_execution_routes(
            db,
            lead,
            role=role,
            acting_uid=acting_user_id(),
            acting_un=username or '',
        ):
            return jsonify({'ok': False, 'error': 'Access denied'}), 403

        notes = db.execute("SELECT * FROM lead_notes WHERE lead_id=? ORDER BY created_at DESC", (lead_id,)).fetchall()
        return jsonify({'ok': True, 'notes': [dict(n) for n in notes]})

    @app.route('/retarget/bulk-assign', methods=['POST'])
    @login_required
    def retarget_bulk_assign():
        """Leader/admin bulk-reassign retarget leads to a team member."""
        role     = session.get('role', 'team')
        username = acting_username()

        if role not in ('leader', 'admin'):
            return {'ok': False, 'error': 'Only leader/admin can reassign leads'}, 403

        data      = request.get_json(silent=True) or {}
        lead_ids  = data.get('lead_ids', [])
        assign_to = (data.get('assign_to') or '').strip()

        if not lead_ids or not assign_to:
            return {'ok': False, 'error': 'lead_ids and assign_to are required'}, 400

        # Validate lead_ids are all ints
        try:
            lead_ids = [int(i) for i in lead_ids]
        except (TypeError, ValueError):
            return {'ok': False, 'error': 'Invalid lead_ids'}, 400

        db = get_db()

        # Validate assign_to exists and is approved
        target_user = db.execute(
            "SELECT id, username, role FROM users WHERE username=? AND status='approved'", (assign_to,)
        ).fetchone()
        if not target_user:
            return {'ok': False, 'error': f'User "{assign_to}" not found or not approved'}, 404

        # Leader scope: assign_to must be in downline
        if role == 'leader':
            downline = _get_network_usernames(db, username)
            if assign_to not in downline:
                return {'ok': False, 'error': 'You can only assign to your downline members'}, 403

        now_str = _now_ist().strftime('%Y-%m-%d %H:%M:%S')
        count = 0
        _leader_scope_ids = (
            network_user_ids_for_username(db, username) if role == 'leader' else None
        )
        for lid in lead_ids:
            lead = db.execute(
                "SELECT id, assigned_user_id FROM leads WHERE id=? AND in_pool=0 AND deleted_at=''", (lid,)
            ).fetchone()
            if not lead:
                continue
            if role == 'leader':
                try:
                    _au = int(sqlite_row_get(lead, 'assigned_user_id') or 0)
                except (TypeError, ValueError):
                    _au = 0
                if _leader_scope_ids is not None and _au not in _leader_scope_ids:
                    continue
            db.execute(
                "UPDATE leads SET assigned_user_id=?, assigned_to='', updated_at=?, retarget_assigned_by=? WHERE id=?",
                (int(target_user['id']), now_str, username, lid)
            )
            _log_activity(db, username, 'retarget_assign',
                          f'Lead #{lid} reassigned to {assign_to}')
            count += 1

        db.commit()
        return {'ok': True, 'count': count,
                'message': f'{count} lead(s) assigned to {assign_to}'}

    @app.route('/leads/<int:lead_id>/restore-from-lost', methods=['POST'])
    @login_required
    @safe_route
    def restore_from_lost(lead_id):
        """Move a Lost lead back to Retarget so it can be worked again."""
        db   = get_db()
        lead = db.execute(
            "SELECT * FROM leads WHERE id=? AND in_pool=0 AND deleted_at=''", (lead_id,)
        ).fetchone()

        if not lead:
            flash('Lead not found.', 'danger')
            return redirect(url_for('old_leads'))

        role = session.get('role')
        if role not in ('admin', 'leader') and sqlite_row_get(lead, 'assigned_user_id') != acting_user_id():
            flash('Access denied.', 'danger')
            return redirect(url_for('old_leads'))

        if lead['status'] not in ('Lost', 'Pending'):
            flash('Only Lost or Pending leads can be restored.', 'warning')
            return redirect(url_for('old_leads'))

        now_str = _now_ist().strftime('%Y-%m-%d %H:%M:%S')
        db.execute(
            """UPDATE leads
                  SET status='Retarget',
                      pipeline_stage='prospecting',
                      pipeline_entered_at=?,
                      updated_at=?
                WHERE id=?""",
            (now_str, now_str, lead_id)
        )
        db.commit()

        flash(f'✅ "{lead["name"]}" restored to Retarget list.', 'success')
        return redirect(url_for('old_leads'))

    @app.route('/leads/<int:lead_id>/notes', methods=['POST'])
    @login_required
    def add_lead_note(lead_id):
        note = request.form.get('note', '').strip()
        if not note:
            flash('Note cannot be empty.', 'danger')
            return redirect(url_for('edit_lead', lead_id=lead_id))

        db = get_db()
        role = session.get('role', 'team')
        lead = db.execute(
            "SELECT * FROM leads WHERE id=? AND in_pool=0 AND deleted_at=''",
            (lead_id,),
        ).fetchone()
        if not lead:
            flash('Lead not found.', 'danger')
            return redirect(url_for('leads'))
        if role != 'admin' and not actor_may_use_assignee_execution_routes(
            db,
            lead,
            role=role,
            acting_uid=acting_user_id(),
            acting_un=acting_username() or '',
        ):
            flash('Access denied.', 'danger')
            return redirect(url_for('leads'))

        db.execute(
            "INSERT INTO lead_notes (lead_id, username, note) VALUES (?, ?, ?)",
            (lead_id, acting_username(), note)
        )
        db.commit()
        flash('Note added.', 'success')
        return redirect(url_for('edit_lead', lead_id=lead_id))

    @app.route('/leads/<int:lead_id>/notes/<int:note_id>/delete', methods=['POST'])
    @login_required
    def delete_lead_note(lead_id, note_id):
        db   = get_db()
        note = db.execute("SELECT username FROM lead_notes WHERE id=?", (note_id,)).fetchone()
        if note and (note['username'] == acting_username() or session.get('role') == 'admin'):
            db.execute("DELETE FROM lead_notes WHERE id=?", (note_id,))
            db.commit()
        return redirect(url_for('edit_lead', lead_id=lead_id))

    @app.route('/leads/bulk-update', methods=['POST'])
    @login_required
    def bulk_update_leads():
        data       = request.get_json() or {}
        ids        = data.get('ids', [])
        new_status = data.get('status', '').strip()
        if not ids or new_status not in STATUSES:
            return {'ok': False, 'error': 'invalid'}, 400

        db       = get_db()
        username = acting_username()
        role     = session.get('role')
        updated  = 0

        for lead_id in ids:
            lead = db.execute(
                "SELECT * FROM leads WHERE id=? AND in_pool=0 AND deleted_at=''", (lead_id,)
            ).fetchone()
            if not lead:
                continue
            if role != 'admin' and not actor_may_use_assignee_execution_routes(
                db,
                lead,
                role=role or 'team',
                acting_uid=acting_user_id(),
                acting_un=username or '',
            ):
                continue
            new_stage = STATUS_TO_STAGE.get(new_status, 'prospecting')
            _pd_b, _pa_b = payment_fields_after_status_change(lead, new_status)
            _lk = lead.keys()
            _okv, _errv = validate_lead_business_rules(
                new_status,
                _pd_b,
                _pa_b,
                float(lead['seat_hold_amount'] or 0) if 'seat_hold_amount' in _lk else 0.0,
                float(lead['track_price'] or 0) if 'track_price' in _lk else 0.0,
            )
            if not _okv:
                app.logger.warning('bulk_update JSON skipped lead %s: %s', lead_id, _errv)
                continue
            apply_leads_update(
                db,
                {
                    'status': new_status,
                    'pipeline_stage': new_stage,
                    'payment_done': _pd_b,
                    'payment_amount': _pa_b,
                },
                where_sql="id=? AND in_pool=0 AND deleted_at=''",
                where_params=(lead_id,),
                log_context='bulk_update JSON',
            )
            _log_lead_event(db, lead_id, username, f'[Bulk] Status → {new_status}')
            
            # Award points if moving to a paid status
            if new_status in ('Paid ₹196', 'Seat Hold Confirmed', 'Fully Converted'):
                add_points(_assignee_username_for_lead(db, lead), 'CONVERSION', f"Converted lead #{lead_id} (Bulk → {new_status})", db=db, lead_id=lead_id)
            
            updated += 1

        _check_and_award_badges(db, username)
        db.commit()
        
        # Scoring refresh for bulk update
        today_score, _ = _get_today_score(db, username)
        user_row = db.execute("SELECT total_points FROM users WHERE LOWER(username)=LOWER(?)", (username,)).fetchone()
        lifetime_points = user_row['total_points'] if user_row else 0
        
        return {
            'ok': True, 
            'updated': updated,
            'today_score': today_score,
            'lifetime_points': lifetime_points
        }

    @app.route('/leads/<int:lead_id>/batch-share-url', methods=['POST'])
    @login_required
    def batch_share_url(lead_id):
        """Get tokenized watch URLs for this lead+slot. When prospect opens link, batch is auto-marked. No WhatsApp check needed."""
        data = request.get_json(silent=True) or {}
        slot = (data.get('slot') or '').strip()
        if slot not in _BATCH_SLOTS:
            return {'ok': False, 'error': 'Invalid slot'}, 400
        db = get_db()
        row = db.execute(
            "SELECT * FROM leads WHERE id=? AND in_pool=0 AND deleted_at=''", (lead_id,)
        ).fetchone()
        if not row:
            return {'ok': False, 'error': 'Not found'}, 404
        role = session.get('role', 'team')
        owner = _assignee_username_for_lead(db, row)
        if slot.startswith('d1_'):
            if role not in ('leader', 'admin'):
                return {'ok': False, 'error': 'Only leader/admin can share Day 1 batch links'}, 403
            if role == 'leader':
                downline = _get_network_usernames(db, acting_username())
                if owner != acting_username() and owner not in downline:
                    return {'ok': False, 'error': 'Forbidden'}, 403
        else:  # d2_ slots
            if role != 'admin':
                return {'ok': False, 'error': 'Only admin can share Day 2 batch links'}, 403
        existing = db.execute(
            "SELECT token FROM batch_share_links WHERE lead_id=? AND slot=? AND used=0", (lead_id, slot)
        ).fetchone()
        if existing:
            token = existing['token']
        else:
            token = secrets.token_urlsafe(16)
            db.execute(
                "INSERT INTO batch_share_links (token, lead_id, slot) VALUES (?, ?, ?)",
                (token, lead_id, slot)
            )
            db.commit()
        watch_url_v1 = _public_external_url('watch_batch', slot=slot, v=1) + '?token=' + token
        watch_url_v2 = _public_external_url('watch_batch', slot=slot, v=2) + '?token=' + token
        return {'ok': True, 'watch_url_v1': watch_url_v1, 'watch_url_v2': watch_url_v2}

    @app.route('/leads/<int:lead_id>/quick-advance', methods=['POST'])
    @login_required
    def quick_advance(lead_id):
        db  = get_db()
        row = db.execute(
            "SELECT * FROM leads WHERE id=? AND in_pool=0 AND deleted_at=''", (lead_id,)
        ).fetchone()
        if not row:
            return {'ok': False, 'error': 'Not found'}, 404

        owner = _assignee_username_for_lead(db, row)
        _role = session.get('role', 'team')
        if not actor_may_use_assignee_execution_routes(
            db,
            row,
            role=_role,
            acting_uid=acting_user_id(),
            acting_un=acting_username() or '',
        ):
            return {'ok': False, 'error': 'Forbidden'}, 403

        current  = row['status']
        new_status = None
        score_delta = 0

        # Stage advancement map
        if current == 'Paid ₹196':
            new_status = 'Day 1'
        elif current == 'Day 1':
            if row['d1_morning'] and row['d1_afternoon'] and row['d1_evening']:
                new_status = 'Day 2'
            else:
                return {'ok': False, 'error': 'Complete all Day 1 batches first'}, 400
        elif current == 'Day 2':
            if row['d2_morning'] and row['d2_afternoon'] and row['d2_evening']:
                if not lead_day2_business_test_passed(row):
                    return {
                        'ok': False,
                        'error': 'Day 2 business test pass required (≥18/30) before Interview.',
                    }, 400
                new_status = 'Interview'
            else:
                return {'ok': False, 'error': 'Complete all Day 2 batches first'}, 400
        elif current == 'Interview':
            new_status = 'Track Selected'
        elif current == 'Track Selected':
            new_status = 'Seat Hold Confirmed'
            add_points(owner, 'DAY1_COMPLETE', 'Quick Advance: Seat Hold Confirmed', db=db, delta_payments=1)
        elif current == 'Seat Hold Confirmed':
            new_status = 'Fully Converted'
            add_points(owner, 'DAY2_COMPLETE', 'Quick Advance: Fully Converted', db=db)
        else:
            return {'ok': False, 'error': f'No advance rule for status: {current}'}, 400

        if not _role_owns_status(session.get('role', 'team'), new_status):
            return {'ok': False, 'error': f"Role '{session.get('role', 'team')}' cannot move to {new_status}"}, 403

        _pdq0, _paq0 = payment_fields_after_status_change(row, new_status)
        _rk0 = row.keys()
        _okv, _errv = validate_lead_business_rules(
            new_status,
            _pdq0,
            _paq0,
            float(row['seat_hold_amount'] or 0) if 'seat_hold_amount' in _rk0 else 0.0,
            float(row['track_price'] or 0) if 'track_price' in _rk0 else 0.0,
        )
        if not _okv:
            app.logger.warning('quick_advance blocked: %s', _errv)
            return {'ok': False, 'error': _errv}, 400

        now_str = _now_ist().strftime('%Y-%m-%d %H:%M:%S')
        db.execute(
            "UPDATE leads SET status=?, updated_at=? WHERE id=?",
            (new_status, now_str, lead_id)
        )
        # status → stage mapping
        if new_status == 'Day 1':
            new_stage = 'day1'
        elif new_status == 'Day 2':
            new_stage = 'day2'
        elif new_status in ('Interview', 'Track Selected'):
            new_stage = 'day3'
        elif new_status == 'Seat Hold Confirmed':
            new_stage = 'seat_hold'
        elif new_status == 'Fully Converted':
            new_stage = 'closing'
        else:
            new_stage = None

        if new_stage:
            _transition_stage(db, lead_id, new_stage, acting_username(), status_override=new_status)
        row2 = db.execute(
            "SELECT * FROM leads WHERE id=? AND in_pool=0 AND deleted_at=''", (lead_id,)
        ).fetchone()
        if row2:
            _pdq, _paq = payment_fields_after_status_change(row2, new_status)
            apply_leads_update(
                db,
                {'payment_done': _pdq, 'payment_amount': _paq},
                where_sql="id=? AND in_pool=0 AND deleted_at=''",
                where_params=(lead_id,),
                log_context='quick_advance payment',
            )
        _log_lead_event(db, lead_id, acting_username(), f'Status → {new_status} (quick advance)')
        _log_activity(db, acting_username(), 'quick_advance',
                      f'{row["name"]} → {new_status}')

        db.commit()
        
        # Scoring refresh
        new_badges = _check_and_award_badges(db, owner)
        today_score, _ = _get_today_score(db, owner)
        user_row = db.execute("SELECT total_points FROM users WHERE LOWER(username)=LOWER(?)", (owner,)).fetchone()
        lifetime_points = user_row['total_points'] if user_row else 0

        return {
            'ok': True,
            'new_status': new_status,
            'new_stage': new_stage,
            'today_score': today_score,
            'lifetime_points': lifetime_points,
            'badges': new_badges,
            'new_badges': new_badges,
        }

    @app.route('/leads/<int:lead_id>/call-status', methods=['POST'])
    @login_required
    def update_call_status(lead_id):
        """Update call_status. Team/leader can update own or downline leads; admin can update any."""
        data = request.get_json(silent=True) or {}
        call_status = (data.get('call_status') or '').strip()

        if not call_status:
            return {'ok': False, 'error': 'Invalid or missing call_status'}, 400

        db = get_db()
        lead = db.execute("SELECT * FROM leads WHERE id=? AND in_pool=0 AND deleted_at=''", (lead_id,)).fetchone()
        if not lead:
            return {'ok': False, 'error': 'Not found'}, 404

        role = session.get('role', 'team')
        username = acting_username()

        # Team: dial outcomes only (pipeline = Lead Status). Leader/admin: full list.
        _allowed_call = CALL_STATUS_VALUES if role in ('leader', 'admin') else TEAM_CALL_STATUS_VALUES
        if call_status not in _allowed_call:
            return {'ok': False, 'error': 'Invalid call_status for your role'}, 400

        # Admin: any lead. Team: only assigned user self. Leader: self or downline.
        _lu = _assignee_username_for_lead(db, lead)
        if role == 'admin':
            pass
        elif role == 'leader':
            downline = _get_network_usernames(db, username)
            if _lu != username and _lu not in downline:
                return {'ok': False, 'error': 'You can only update call status for your own or downline leads'}, 403
        else:
            if not actor_may_use_assignee_execution_routes(
                db,
                lead,
                role='team',
                acting_uid=acting_user_id(),
                acting_un=username or '',
            ):
                return {'ok': False, 'error': 'Only the assigned member can update call status'}, 403

        _had_followup = bool(lead['follow_up_date'] if 'follow_up_date' in lead.keys() else False)

        followup_discipline_process_overdue(db, _lu or username)
        lead = db.execute(
            "SELECT * FROM leads WHERE id=? AND in_pool=0 AND deleted_at=''", (lead_id,)
        ).fetchone()
        if not lead:
            return {'ok': False, 'error': 'Not found'}, 404

        # ₹196 barrier: proof + approval (one-time); no Video Watched prerequisite.
        if call_status == 'Payment Done':
            _lead_st = (lead['status'] or '').strip()
            _blocked, _pmsg = rupees_196_execution_blocked_for_role(
                lead,
                role=role,
                acting_user_id=acting_user_id(),
                current_status=_lead_st,
                is_transition_to_paid_196_funnel=True,
                gate_enabled=_rupees_196_gate_enabled(db),
            )
            if _blocked:
                return {'ok': False, 'error': _pmsg}, 422

        apply_call_outcome_discipline(db, lead, call_status, triggered_by=username)
        lead = db.execute(
            "SELECT * FROM leads WHERE id=? AND in_pool=0 AND deleted_at=''", (lead_id,)
        ).fetchone()
        # Fresh wall clock for any follow-up UPDATEs (avoid stale request-start time).
        now_str = _now_ist().strftime('%Y-%m-%d %H:%M:%S')

        _log_activity(db, username, 'call_status_update', f'Lead #{lead_id} call_status={call_status}')

        # Growth Engine: Evaluate if call connected
        _connected_statuses = [
            'Called - Interested', 'Called - Not Interested', 'Called - Follow Up',
            'Call Back', 'Video Sent', 'Video Watched', 'Payment Done'
        ]
        
        # ── AUTO STATUS UPDATE based on call_status ──────────────
        # Only move status FORWARD — never backward (skip terminal Lost/Retarget)
        _STATUS_ORDER = [
            'New Lead', 'New', 'Contacted', 'Invited',
            'Video Sent', 'Video Watched', 'Paid ₹196',
            'Day 1', 'Day 2', 'Interview', 'Track Selected',
            'Seat Hold Confirmed', 'Fully Converted', 'Training', 'Converted'
        ]
        current_status = lead['status'] or 'New'
        cur_idx = _STATUS_ORDER.index(current_status) if current_status in _STATUS_ORDER else 0
        _call_to_status = {
            'Called - No Answer':    'Contacted',
            'Called - Interested':   'Contacted',
            'Called - Follow Up':    'Contacted',
            'Called - Not Interested': None,
            'Video Sent':            'Video Sent',
            'Video Watched':         'Video Watched',
            'Payment Done':          'Paid ₹196',
        }
        new_auto_status = _call_to_status.get(call_status)
        if (
            new_auto_status
            and current_status not in ('Lost', 'Retarget')
        ):
            new_idx = _STATUS_ORDER.index(new_auto_status) if new_auto_status in _STATUS_ORDER else 0
            if new_idx > cur_idx:
                # Sync pipeline_stage alongside status to keep them consistent
                new_auto_stage = STATUS_TO_STAGE.get(new_auto_status, 'prospecting')
                db.execute(
                    "UPDATE leads SET status=?, pipeline_stage=?, updated_at=? WHERE id=?",
                    (new_auto_status, new_auto_stage, now_str, lead_id)
                )
                # Audit: log auto-advance to stage history and activity log
                _auto_owner = lead['current_owner'] if 'current_owner' in lead.keys() else ''
                db.execute(
                    "INSERT INTO lead_stage_history (lead_id, stage, owner, triggered_by, created_at) VALUES (?,?,?,?,?)",
                    (lead_id, new_auto_stage, _auto_owner, username, now_str)
                )
                _log_activity(db, username, 'auto_status_advance',
                              f"Lead #{lead_id} auto-advanced to {new_auto_status} via call_status: {call_status}")

        # Gamification: award points only for fresh leads (claimed today or added today)
        _ALL_CALLING = frozenset({
            'Called - Interested', 'Called - No Answer',
            'Called - Follow Up',  'Called - Not Interested',
            'Called - Switch Off', 'Called - Busy',
            'Call Back',           'Wrong Number',
        })
        _fresh = _is_fresh_lead(lead)

        if _fresh and _had_followup:
            add_points(username, 'FOLLOWUP_COMPLETED', f"Completed scheduled follow-up for lead #{lead_id}", db=db, lead_id=lead_id)

        if _fresh:
            if call_status == 'Payment Done':
                add_points(username, 'PAYMENT_DONE', f"Payment Done for Lead #{lead_id}", db=db, lead_id=lead_id, delta_calls=1, delta_payments=1)
            elif call_status == 'Video Sent':
                add_points(username, 'VIDEO_SENT', f"Video Sent for Lead #{lead_id}", db=db, lead_id=lead_id, delta_calls=1, delta_videos=1)
            elif call_status in _connected_statuses:
                add_points(username, 'CONNECTED_CALL', f"Connected with Lead #{lead_id}", db=db, lead_id=lead_id, delta_calls=1)
            elif call_status in _ALL_CALLING:
                add_points(username, 'CALL_ATTEMPT', f"Dialed Lead #{lead_id}", db=db, lead_id=lead_id, delta_calls=1)

        # Auto-advance enrollment → day1 when "Payment Done" is set
        stage_advanced = False
        if call_status == 'Payment Done':
            lead = db.execute(
                "SELECT * FROM leads WHERE id=? AND in_pool=0 AND deleted_at=''", (lead_id,)
            ).fetchone()
            if not lead:
                db.commit()
                return {'ok': False, 'error': 'Not found'}, 404
            if not lead['payment_done']:
                _pd, _pa = payment_columns_mark_paid(lead)
                _rk = lead.keys()
                _okv, _errv = validate_lead_business_rules(
                    lead['status'],
                    _pd,
                    _pa,
                    float(lead['seat_hold_amount'] or 0) if 'seat_hold_amount' in _rk else 0.0,
                    float(lead['track_price'] or 0) if 'track_price' in _rk else 0.0,
                )
                if not _okv:
                    app.logger.warning('Payment Done blocked: %s', _errv)
                    db.commit()
                    return {'ok': False, 'error': _errv}, 400
                apply_leads_update(
                    db,
                    {'payment_done': _pd, 'payment_amount': _pa},
                    where_sql="id=? AND in_pool=0 AND deleted_at=''",
                    where_params=(lead_id,),
                    log_context='call_status Payment Done',
                )

            lead_stage = lead['pipeline_stage'] if 'pipeline_stage' in lead.keys() else 'prospecting'
            if lead_stage in ('prospecting', 'enrolled', 'enrollment'):
                _new_stg, _new_owner = _transition_stage(db, lead_id, 'day1', username, status_override='Day 1')
                stage_advanced = True
                # Day-1 routing: execution may move to leader via assigned_user_id only; current_owner unchanged
                _d1_uid = user_id_for_username(db, _new_owner) if _new_owner else None
                _now_s = _now_ist().strftime('%Y-%m-%d %H:%M:%S')
                if _d1_uid:
                    db.execute(
                        "UPDATE leads SET assigned_user_id=? WHERE id=? AND in_pool=0 AND deleted_at=''",
                        (_d1_uid, lead_id),
                    )
                db.execute(
                    "UPDATE leads SET enrolled_at=?, enrolled_by=? WHERE id=? AND TRIM(COALESCE(enrolled_at,''))=''",
                    (_now_s, username, lead_id),
                )

        # Today Calls / Today Enrollment both key off updated_at IST date — always bump last.
        touch_lead_updated_at(db, lead_id, log_context='update_call_status')

        db.commit()
        
        # Scoring refresh
        today_score, _ = _get_today_score(db, username)
        user_row = db.execute("SELECT total_points FROM users WHERE LOWER(username)=LOWER(?)", (username,)).fetchone()
        lifetime_points = user_row['total_points'] if user_row else 0
        assignee = (_assignee_username_for_lead(db, lead) or username).strip() or username
        ai_feedback = ''
        try:
            ai_feedback = compute_step8_quick_feedback_for_assignee(db, assignee)
        except Exception:
            pass
        
        # Defer badge check after closing main connection
        def _defer_badges():
            try:
                _db = get_db()
                _check_and_award_badges(_db, username)
                _db.commit()
                _db.close()
            except Exception: pass
        threading.Thread(target=_defer_badges, daemon=True).start()

        return {
            'ok': True, 
            'call_status': call_status, 
            'stage_advanced': stage_advanced,
            'today_score': today_score,
            'lifetime_points': lifetime_points,
            'ai_feedback': ai_feedback,
        }
