"""
Wallet, Lead Pool, and Calling Reminder routes.

Registered via register_wallet_routes(app) at the end of app.py load so helpers
on the app module are available without circular import at import time.
"""
from __future__ import annotations

import datetime
import re

from flask import flash, redirect, render_template, request, session, url_for

from database import get_db
from decorators import login_required, safe_route
from auth_context import acting_username, acting_user_id
from reliability import emit_event, incident_code, safe_user_error
from app import format_rupee_amount
from services.wallet_ledger import (
    count_buyer_claimed_leads,
    count_buyer_claims_on_local_date,
    recent_buyer_claimed_leads,
    sum_pool_spent_for_buyer,
)
from helpers import (
    PIPELINE_AUTO_EXPIRE_STATUSES,
    STATUS_TO_STAGE,
    assert_lead_owner_invariant,
    claim_hard_gate_message,
    get_performance_ui_state,
    maybe_auto_seed_claim_discipline_start,
    submit_performance_grace_request,
    user_inactivity_hours,
)


def register_wallet_routes(app):
    """Attach wallet / lead-pool / calling-reminder URL rules to the Flask app."""
    from app import (  # noqa: PLC0415 — late import after app module is populated
        _generate_upi_qr_base64,
        _get_setting,
        _get_wallet,
        _log_activity,
        _now_ist,
    )

    def _team_claim_gate_message(db, username: str, user_id: int) -> str | None:
        """Team-only simplified gates: proof block, stale-lead block. No circular blocks."""
        now = _now_ist()

        active_count = db.execute(
            """
            SELECT COUNT(*) FROM leads
            WHERE (assigned_user_id=? OR current_owner=?) AND in_pool=0 AND deleted_at=''
              AND status NOT IN ('Converted','Fully Converted','Lost','Retarget')
            """,
            (user_id, username),
        ).fetchone()[0] or 0
        if active_count == 0:
            return None

        recent_cutoff = (now - datetime.timedelta(days=10)).strftime('%Y-%m-%d %H:%M:%S')

        proof_missing = db.execute(
            """
            SELECT COUNT(*) FROM leads
            WHERE assigned_user_id=? AND in_pool=0 AND deleted_at=''
              AND (
                (claimed_at IS NOT NULL AND claimed_at >= ?)
                OR ((claimed_at IS NULL OR TRIM(COALESCE(claimed_at,''))='') AND created_at >= ?)
              )
              AND status='Paid ₹196'
              AND TRIM(COALESCE(payment_proof_path,''))=''
            """,
            (user_id, recent_cutoff, recent_cutoff),
        ).fetchone()[0] or 0
        if proof_missing > 0:
            return 'Claim blocked: ₹196 leads without screenshot proof found.'

        interested_cutoff = (now - datetime.timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')
        interested_stale = db.execute(
            """
            SELECT COUNT(*) FROM leads
            WHERE assigned_user_id=? AND in_pool=0 AND deleted_at=''
              AND (
                (claimed_at IS NOT NULL AND claimed_at >= ?)
                OR ((claimed_at IS NULL OR TRIM(COALESCE(claimed_at,''))='') AND created_at >= ?)
              )
              AND status IN ('Video Watched')
              AND updated_at <= ?
            """,
            (user_id, recent_cutoff, recent_cutoff, interested_cutoff),
        ).fetchone()[0] or 0
        if interested_stale > 0:
            return 'Claim blocked: Video Watched leads are pending action for 24h+.'

        return None

    # ─────────────────────────────────────────────────
    #  Team – Wallet
    # ─────────────────────────────────────────────────

    @app.route('/wallet')
    @login_required
    @safe_route
    def wallet():
        username = acting_username()
        db       = get_db()

        wallet_stats = _get_wallet(db, username)

        recharges = db.execute(
            "SELECT * FROM wallet_recharges WHERE username=? ORDER BY requested_at DESC LIMIT 20",
            (username,)
        ).fetchall()

        claimed_leads = recent_buyer_claimed_leads(db, username, limit=20)

        upi_id     = _get_setting(db, 'upi_id')
        upi_qr_b64 = _generate_upi_qr_base64(upi_id) if upi_id else None

        pending_mine = db.execute(
            "SELECT COUNT(*) FROM wallet_recharges WHERE username=? AND status='pending'",
            (username,)
        ).fetchone()[0]

        return render_template('wallet.html',
                               wallet=wallet_stats,
                               recharges=recharges,
                               claimed_leads=claimed_leads,
                               upi_id=upi_id,
                               upi_qr_b64=upi_qr_b64,
                               pending_mine=pending_mine)


    @app.route('/wallet/request-recharge', methods=['POST'])
    @login_required
    @safe_route
    def request_recharge():
        username = acting_username()
        db       = get_db()

        try:
            amount = float(request.form.get('amount') or 0)
        except ValueError:
            amount = 0

        utr = (request.form.get('utr_number') or '').strip()

        if amount <= 0:
            flash('Please enter a valid amount greater than 0.', 'danger')
            return redirect(url_for('wallet'))

        if not utr:
            flash('UTR / Transaction number is required.', 'danger')
            return redirect(url_for('wallet'))

        existing = db.execute(
            "SELECT id FROM wallet_recharges WHERE utr_number=?", (utr,)
        ).fetchone()
        if existing:
            flash('This UTR number has already been submitted. Contact admin if this is an error.', 'danger')
            return redirect(url_for('wallet'))

        try:
            db.execute(
                "INSERT INTO wallet_recharges (username, amount, utr_number, status) "
                "VALUES (?, ?, ?, 'pending')",
                (username, amount, utr)
            )
            db.commit()
        except Exception as _e:
            app.logger.error(f"wallet recharge INSERT failed for {username}: {_e}")
            try: db.execute("ROLLBACK")
            except Exception: pass
            flash('Could not save your request. Please try again or contact admin.', 'danger')
            return redirect(url_for('wallet'))

        flash(f'Recharge request of \u20b9{amount:.0f} submitted! UTR: {utr}. '
              f'Admin will credit your wallet within 24 hours.', 'success')
        return redirect(url_for('wallet'))


    # ─────────────────────────────────────────────────
    #  Team – Lead Pool (Claim Leads)
    # ─────────────────────────────────────────────────

    @app.route('/lead-pool')
    @login_required
    def lead_pool():
        username = acting_username()
        user_id  = acting_user_id()
        db       = get_db()

        wallet_stats = _get_wallet(db, username)

        pool_count = db.execute(
            "SELECT COUNT(*) FROM leads WHERE in_pool=1"
        ).fetchone()[0]

        price_info = db.execute(
            "SELECT MIN(pool_price) as min_p, MAX(pool_price) as max_p, "
            "AVG(pool_price) as avg_p FROM leads WHERE in_pool=1"
        ).fetchone()

        avg_price  = price_info['avg_p'] or 0
        if pool_count == 0:
            can_claim = 0
        elif avg_price > 0:
            can_claim = min(int(wallet_stats['balance'] // avg_price), pool_count)
        else:
            can_claim = pool_count

        my_claims = count_buyer_claimed_leads(db, username)

        upi_id = _get_setting(db, 'upi_id', '')
        role = session.get('role', 'team')
        claim_gate_message = None
        perf_state = None
        if role == 'team':
            claim_gate_message = _team_claim_gate_message(db, username, int(user_id))
        elif role == 'leader':
            claim_gate_message = claim_hard_gate_message(db, username)
            perf_state = get_performance_ui_state(db, username)
            db.commit()

        return render_template('lead_pool.html',
                               wallet=wallet_stats,
                               pool_count=pool_count,
                               price_info=price_info,
                               can_claim=can_claim,
                               my_claims=my_claims,
                               upi_id=upi_id,
                               claim_gate_message=claim_gate_message,
                               perf_state=perf_state or {},
                               csrf_token=session.get('_csrf_token', ''))


    @app.route('/calling-reminder/set', methods=['POST'])
    @login_required
    def set_calling_reminder():
        """Team member sets their personal calling reminder time (HH:MM or blank to clear)."""
        time_val = request.form.get('reminder_time', '').strip()
        if time_val and not re.match(r'^\d{2}:\d{2}$', time_val):
            flash('Invalid time format.', 'danger')
            return redirect(url_for('team_dashboard'))
        db = get_db()
        db.execute(
            "UPDATE users SET calling_reminder_time=? WHERE username=?",
            (time_val, acting_username())
        )
        db.commit()
        if time_val:
            flash(f'Calling reminder set for {time_val} every day.', 'success')
        else:
            flash('Calling reminder cleared.', 'success')
        return redirect(url_for('team_dashboard'))


    @app.route('/performance/grace-request', methods=['POST'])
    @login_required
    @safe_route
    def request_performance_grace():
        if session.get('role') not in ('team', 'leader'):
            flash('Grace request sirf team / leader ke liye.', 'danger')
            return redirect(url_for('team_dashboard'))
        username = acting_username()
        reason = request.form.get('reason_text', '')
        ret = request.form.get('expected_return_date', '')
        db = get_db()
        ok, msg = submit_performance_grace_request(db, username, reason, ret)
        if ok:
            db.commit()
            flash(msg, 'success')
        else:
            db.commit()
            flash(msg, 'danger')
        return redirect(request.referrer or url_for('lead_pool'))


    @app.route('/lead-pool/claim', methods=['POST'])
    @login_required
    def claim_leads():
        username = acting_username()
        user_id  = acting_user_id()
        db       = get_db()

        try:
            count = int(request.form.get('count') or 1)
            count = max(1, min(count, 50))
        except ValueError:
            count = 1

        maybe_auto_seed_claim_discipline_start(db)
        db.commit()

        try:
            db.execute("BEGIN IMMEDIATE")

            wallet_stats = _get_wallet(db, username)
            now_dt = _now_ist()
            now = now_dt.strftime('%Y-%m-%d %H:%M:%S')

            role = session.get('role', 'team')
            if role == 'team':
                gate_msg = _team_claim_gate_message(db, username, int(user_id))
                if gate_msg:
                    if gate_msg.lower().startswith('warning:'):
                        flash(gate_msg, 'warning')
                    else:
                        db.execute("ROLLBACK")
                        flash(gate_msg, 'danger')
                        return redirect(url_for('lead_pool'))
                # Team claim cap and cooldown
                max_claim_day = int((_get_setting(db, 'team_max_claim_per_day', '999') or '999').strip() or '999')
                cooldown_min = int((_get_setting(db, 'team_claim_cooldown_minutes', '0') or '0').strip() or '0')
                today_claimed = count_buyer_claims_on_local_date(db, username, now)
                if today_claimed >= max_claim_day:
                    db.execute("ROLLBACK")
                    flash(f'Claim blocked: daily max {max_claim_day} reached.', 'danger')
                    return redirect(url_for('lead_pool'))
                last_claim = db.execute(
                    "SELECT MAX(created_at) FROM activity_log WHERE username=? AND event_type='lead_claim'",
                    (username,),
                ).fetchone()[0]
                if cooldown_min > 0 and last_claim:
                    try:
                        last_dt = datetime.datetime.strptime(last_claim[:19], '%Y-%m-%d %H:%M:%S')
                        wait_till = last_dt + datetime.timedelta(minutes=cooldown_min)
                        if now_dt < wait_till:
                            db.execute("ROLLBACK")
                            flash(f'Claim cooldown active: wait {cooldown_min} min between claims.', 'danger')
                            return redirect(url_for('lead_pool'))
                    except Exception:
                        pass
            elif role == 'leader':
                gate_msg = claim_hard_gate_message(db, username)
                if gate_msg:
                    db.execute("ROLLBACK")
                    flash(gate_msg, 'danger')
                    return redirect(url_for('lead_pool'))

            # Tie-break on id so bulk-inserted pool rows (same created_at second) claim in stable FIFO order.
            available = db.execute(
                "SELECT id, pool_price, status, pipeline_stage FROM leads WHERE in_pool=1 AND assigned_user_id IS NULL "
                "ORDER BY created_at ASC, id ASC LIMIT ?",
                (count,),
            ).fetchall()

            if not available:
                db.execute("ROLLBACK")
                flash('No leads available in pool right now. Check back later.', 'warning')
                return redirect(url_for('lead_pool'))

            total_cost = sum((r['pool_price'] or 0) for r in available)

            if total_cost > wallet_stats['balance']:
                db.execute("ROLLBACK")
                flash(
                    f'Insufficient balance! Need \u20b9{format_rupee_amount(total_cost)} but you have '
                    f'\u20b9{format_rupee_amount(wallet_stats["balance"])}. '
                    f'Please recharge your wallet.',
                    'danger',
                )
                return redirect(url_for('lead_pool'))

            claimed_rows = 0
            for row in available:
                # Resolve effective status & stage to keep them consistent
                cur_status = row['status'] or ''
                cur_stage  = row['pipeline_stage'] or ''
                eff_status = cur_status if cur_status else 'New Lead'
                eff_stage  = STATUS_TO_STAGE.get(eff_status, 'prospecting') if not cur_stage else cur_stage
                # Set pipeline_entered_at so auto-expire scheduler can track claimed leads
                eff_pipe_entered = now if eff_status in PIPELINE_AUTO_EXPIRE_STATUSES else ''
                _res = db.execute(
                    "UPDATE leads SET assigned_user_id=?, assigned_to='', in_pool=0, claimed_at=?, "
                    "current_owner=?, pipeline_stage=?, status=?, pipeline_entered_at=?, "
                    "updated_at=? WHERE id=? AND in_pool=1 AND assigned_user_id IS NULL",
                    (user_id, now, username, eff_stage, eff_status, eff_pipe_entered, now, row['id']),
                )
                if (_res.rowcount or 0) > 0:
                    claimed_rows += 1
                    db.execute(
                        """
                        INSERT INTO lead_assignments
                            (lead_id, assigned_to, previous_assigned_to, assigned_by, assign_type, reason, created_at)
                        VALUES (?, ?, NULL, ?, 'pool_claim', 'lead pool purchase', ?)
                        """,
                        (row['id'], user_id, username, now),
                    )
                    assert_lead_owner_invariant(db, lead_id=int(row['id']), context='claim_leads_success')
                    _log_activity(
                        db,
                        username,
                        'lead_claim_row',
                        f"user_id={user_id} lead_id={row['id']} ts={now} success=1",
                    )
                else:
                    _log_activity(
                        db,
                        username,
                        'lead_claim_row',
                        f"user_id={user_id} lead_id={row['id']} ts={now} success=0",
                    )
                    app.logger.warning(
                        "[STABILIZATION] duplicate_claim_prevented user=%s lead_id=%s",
                        username, row['id']
                    )

            if claimed_rows == 0:
                db.execute("ROLLBACK")
                flash('No leads were claimed (already taken by another request). Please retry.', 'warning')
                return redirect(url_for('lead_pool'))

            db.execute("UPDATE users SET idle_hidden=0 WHERE username=?", (username,))
            db.commit()
            _log_activity(db, username, 'lead_claim', f"Claimed {claimed_rows} leads")
            try:
                wallet_after = _get_wallet(db, username)
                spent_sql = sum_pool_spent_for_buyer(db, username)
                if abs(float(wallet_after['spent']) - float(spent_sql)) > 0.01:
                    app.logger.warning(
                        "[STABILIZATION] wallet_mismatch user=%s wallet_spent=%.2f sql_spent=%.2f",
                        username, float(wallet_after['spent']), float(spent_sql)
                    )
            except Exception:
                pass
            flash(
                f'Successfully claimed {claimed_rows} leads for \u20b9{format_rupee_amount(total_cost)}! '
                f'Check "My Leads" to view them.',
                'success',
            )
            return redirect(url_for('leads'))

        except Exception as e:
            import traceback, sys
            code = incident_code("REL-CLM")
            emit_event(
                app.logger,
                "claim_failed",
                code=code,
                username=username,
                user_id=user_id,
                error=str(e),
            )
            try:
                _log_activity(
                    db,
                    username,
                    "reliability_claim_failure",
                    f"code={code} error={str(e)[:180]}",
                )
            except Exception:
                pass
            print(f"[CLAIM ERROR] user={username} error={e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            try:
                db.execute("ROLLBACK")
            except Exception:
                pass
            flash(safe_user_error('Something went wrong while claiming leads. Please try again.', code), 'danger')
            return redirect(url_for('lead_pool'))
