"""
Admin lead-pool and wallet-recharge routes.

Registered via register_lead_pool_routes(app) at the end of app.py load so helpers
on the app module are available without circular import at import time.
"""
from __future__ import annotations

import csv
import io
import secrets
import threading

from flask import flash, redirect, render_template, request, session, url_for

from database import get_db
from decorators import admin_required
from helpers import _get_setting, _log_activity, _now_ist


def register_lead_pool_routes(app):
    """Attach admin lead-pool and wallet URL rules to the Flask app."""
    from app import (  # noqa: PLC0415 — late import after app module is populated
        PDF_AVAILABLE,
        _extract_leads_from_pdf,
        _get_wallet,
        _push_all_approved_users,
        _push_to_users,
    )

    @app.route('/admin/lead-pool/duplicate-cleanup')
    @admin_required
    def pool_duplicate_cleanup():
        """Show pool leads whose phone numbers already exist as active leads."""
        db = get_db()
        dupes = db.execute("""
            SELECT p.id, p.name, p.phone, p.city, p.source, p.created_at,
                   a.name AS active_name, COALESCE(u.username, '') AS active_owner, a.status AS active_status
            FROM leads p
            JOIN leads a ON a.phone = p.phone
            LEFT JOIN users u ON u.id = a.assigned_user_id
            WHERE p.in_pool = 1
              AND p.deleted_at = ''
              AND a.in_pool = 0
              AND a.deleted_at = ''
            ORDER BY p.phone
        """).fetchall()
        return render_template('pool_duplicate_cleanup.html', dupes=dupes)


    @app.route('/admin/lead-pool/duplicate-cleanup/delete', methods=['POST'])
    @admin_required
    def pool_duplicate_cleanup_delete():
        """Delete selected pool duplicate leads."""
        ids = request.form.getlist('lead_ids')
        if not ids:
            flash('Select at least one lead.', 'warning')
            return redirect(url_for('pool_duplicate_cleanup'))
        db = get_db()
        placeholders = ','.join('?' * len(ids))
        deleted = db.execute(
            f"DELETE FROM leads WHERE id IN ({placeholders}) AND in_pool=1",
            ids
        ).rowcount
        db.commit()
        flash(f'{deleted} duplicate pool lead(s) safely deleted.', 'success')
        return redirect(url_for('pool_duplicate_cleanup'))


    @app.route('/admin/lead-pool')
    @admin_required
    def admin_lead_pool():
        db = get_db()
        page     = request.args.get('page', 1, type=int)
        per_page = 50
        offset   = (page - 1) * per_page

        total_in_pool = db.execute(
            "SELECT COUNT(*) FROM leads WHERE in_pool=1"
        ).fetchone()[0]
        total_claimed = db.execute(
            "SELECT COUNT(*) FROM leads WHERE in_pool=0 AND claimed_at IS NOT NULL"
        ).fetchone()[0]

        pool_leads = db.execute(
            "SELECT * FROM leads WHERE in_pool=1 ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (per_page, offset)
        ).fetchall()

        default_price = _get_setting(db, 'default_lead_price', '50')
        return render_template('lead_pool_admin.html',
                               pool_leads=pool_leads,
                               total_in_pool=total_in_pool,
                               total_claimed=total_claimed,
                               default_price=default_price,
                               page=page,
                               per_page=per_page)


    @app.route('/admin/lead-pool/import-csv', methods=['POST'])
    @admin_required
    def import_lead_pool_csv():
        """Import Meta Lead Ads CSV into the lead pool."""
        db             = get_db()
        price_per_lead = float(request.form.get('price_per_lead') or 50)
        source_tag     = request.form.get('source_tag', 'Meta').strip() or 'Meta'

        if 'csv_file' not in request.files:
            flash('No file uploaded.', 'danger')
            return redirect(url_for('admin_lead_pool'))

        f = request.files['csv_file']
        if not f.filename.lower().endswith('.csv'):
            flash('Please upload a .csv file.', 'danger')
            return redirect(url_for('admin_lead_pool'))

        # Reject oversized uploads before reading into memory (5 MB hard limit)
        _CSV_MAX_BYTES = 5 * 1024 * 1024  # 5 MB
        f.seek(0, 2)           # seek to end
        _file_size = f.tell()
        f.seek(0)              # rewind
        if _file_size > _CSV_MAX_BYTES:
            flash(f'CSV file too large ({_file_size // 1024} KB). Maximum allowed is 5 MB.', 'danger')
            return redirect(url_for('admin_lead_pool'))

        try:
            content = f.read().decode('utf-8-sig', errors='replace')
            reader  = csv.DictReader(io.StringIO(content))
            rows_list = list(reader)
        except Exception as e:
            flash(f'Could not parse CSV: {e}', 'danger')
            return redirect(url_for('admin_lead_pool'))

        existing_phones = {
            r[0] for r in db.execute(
                "SELECT phone FROM leads WHERE deleted_at=''"
            ).fetchall()
        }

        imported = 0
        skipped  = 0

        for row in rows_list:
            _fn = (row.get('First Name') or row.get('first_name') or '').strip()
            _ln = (row.get('Last Name') or row.get('last_name') or '').strip()
            name  = (row.get('Full Name') or row.get('full_name') or
                     row.get('name') or row.get('Name') or
                     ((_fn + ' ' + _ln).strip() if _fn or _ln else '') or '').strip()
            phone = (row.get('Phone Number (Calling Number)') or
                     row.get('phone_number') or row.get('phone') or
                     row.get('Phone') or row.get('Phone Number') or '').strip()
            email = (row.get('email') or row.get('Email') or
                     row.get('email_address') or '').strip()

            age         = (row.get('Age') or row.get('age') or '').strip()
            gender      = (row.get('Gender') or row.get('gender') or '').strip()
            city        = (row.get('Your City Name') or row.get('city') or
                           row.get('City') or '').strip()
            ad_name     = (row.get('Ad Name') or row.get('ad_name') or '').strip()
            submit_time = (row.get('Submit Time') or row.get('submit_time') or '').strip()

            lead_source = ad_name if ad_name else source_tag

            extra_parts = []
            if age:         extra_parts.append(f'Age: {age}')
            if gender:      extra_parts.append(f'Gender: {gender}')
            if submit_time: extra_parts.append(f'Submit Time: {submit_time}')
            notes_str = ' | '.join(extra_parts) if extra_parts else ''

            if not name and not phone:
                skipped += 1
                continue
            if not name:
                name = phone
            if not phone:
                phone = 'N/A'
            if phone in existing_phones:
                skipped += 1
                continue
            existing_phones.add(phone)

            db.execute("""
                INSERT INTO leads
                    (name, phone, email, assigned_to, source, status,
                     in_pool, pool_price, claimed_at, city, notes)
                VALUES (?, ?, ?, '', ?, 'New', 1, ?, NULL, ?, ?)
            """, (name, phone, email, lead_source, price_per_lead, city, notes_str))
            imported += 1

        db.commit()
        if imported > 0:
            _count = imported
            _body = (
                f'{_count} new leads available. Claim your leads now!'
                if _count != 1
                else '1 new lead available. Claim your leads now!'
            )

            def _bg_push_csv():
                _db = get_db()
                try:
                    _push_all_approved_users(
                        _db,
                        'New leads in the pool',
                        _body,
                        '/lead-pool'
                    )
                    _db.commit()
                finally:
                    _db.close()
            threading.Thread(target=_bg_push_csv, daemon=True).start()
        flash(f'Imported {imported} leads into pool. Skipped {skipped} (duplicates/empty).', 'success')
        return redirect(url_for('admin_lead_pool'))


    @app.route('/admin/lead-pool/import-pdf', methods=['POST'])
    @admin_required
    def import_lead_pool_pdf():
        """Import leads from PDF into the lead pool."""
        db             = get_db()
        price_per_lead = float(request.form.get('price_per_lead') or 50)
        source_tag     = request.form.get('source_tag', 'PDF').strip() or 'PDF'

        if 'pdf_file' not in request.files:
            flash('No file uploaded.', 'danger')
            return redirect(url_for('admin_lead_pool'))

        f = request.files['pdf_file']
        if not f.filename.lower().endswith('.pdf'):
            flash('Please upload a .pdf file.', 'danger')
            return redirect(url_for('admin_lead_pool'))

        rows_list, err = _extract_leads_from_pdf(f.stream)
        if err:
            flash(err, 'danger')
            return redirect(url_for('admin_lead_pool'))

        existing_phones = {
            r[0] for r in db.execute("SELECT phone FROM leads WHERE deleted_at=''").fetchall()
        }

        imported = skipped = 0
        for row in rows_list:
            name  = row.get('name', '').strip()
            phone = row.get('phone', '').strip()
            email = row.get('email', '').strip()
            city  = row.get('city', '').strip()

            if not name and not phone:
                skipped += 1
                continue
            if not name:
                name = phone
            if not phone:
                phone = 'N/A'
            if phone in existing_phones:
                skipped += 1
                continue
            existing_phones.add(phone)

            db.execute("""
                INSERT INTO leads
                    (name, phone, email, assigned_to, source, status,
                     in_pool, pool_price, claimed_at, city, notes)
                VALUES (?, ?, ?, '', ?, 'New', 1, ?, NULL, ?, '')
            """, (name, phone, email, source_tag, price_per_lead, city))
            imported += 1

        db.commit()
        if imported > 0:
            _count = imported
            _body_pdf = (
                f'{_count} new leads available. Claim your leads now!'
                if _count != 1
                else '1 new lead available. Claim your leads now!'
            )

            def _bg_push_pdf():
                _db = get_db()
                try:
                    _push_all_approved_users(
                        _db,
                        'New leads in the pool',
                        _body_pdf,
                        '/lead-pool'
                    )
                    _db.commit()
                finally:
                    _db.close()
            threading.Thread(target=_bg_push_pdf, daemon=True).start()
        flash(f'PDF import: {imported} leads added to pool. Skipped {skipped} (duplicates/empty).', 'success')
        return redirect(url_for('admin_lead_pool'))


    @app.route('/admin/lead-pool/add-single', methods=['POST'])
    @admin_required
    def add_to_pool():
        """Admin manually adds a single lead to the pool."""
        db     = get_db()
        name   = request.form.get('name', '').strip()
        phone  = request.form.get('phone', '').strip()
        email  = request.form.get('email', '').strip()
        price  = float(request.form.get('price') or 50)
        source = request.form.get('source', 'Other').strip()

        if not name or not phone:
            flash('Name and phone are required.', 'danger')
            return redirect(url_for('admin_lead_pool'))

        db.execute("""
            INSERT INTO leads
                (name, phone, email, assigned_to, source, status,
                 in_pool, pool_price, claimed_at)
            VALUES (?, ?, ?, '', ?, 'New', 1, ?, NULL)
        """, (name, phone, email, source, price))
        db.commit()
        def _bg_push_single():
            _db = get_db()
            try:
                _push_all_approved_users(
                    _db,
                    'New leads in the pool',
                    '1 new lead available. Claim your leads now!',
                    '/lead-pool'
                )
                _db.commit()
            finally:
                _db.close()
        threading.Thread(target=_bg_push_single, daemon=True).start()
        flash(f'Lead "{name}" added to pool.', 'success')
        return redirect(url_for('admin_lead_pool'))


    @app.route('/admin/lead-pool/<int:lead_id>/remove', methods=['POST'])
    @admin_required
    def remove_from_pool(lead_id):
        db = get_db()
        db.execute("DELETE FROM leads WHERE id=? AND in_pool=1", (lead_id,))
        db.commit()
        flash('Lead removed from pool.', 'warning')
        return redirect(url_for('admin_lead_pool'))


    @app.route('/admin/wallet-requests')
    @admin_required
    def admin_wallet_requests():
        db            = get_db()
        filter_status = request.args.get('status', 'pending')

        query  = ("SELECT wr.*, u.phone as user_phone "
                  "FROM wallet_recharges wr "
                  "LEFT JOIN users u ON wr.username=u.username "
                  "WHERE 1=1")
        params = []
        if filter_status in ('pending', 'approved', 'rejected'):
            query += " AND wr.status=?"
            params.append(filter_status)
        query += " ORDER BY wr.requested_at DESC"

        requests_list = db.execute(query, params).fetchall()

        pending_count = db.execute(
            "SELECT COUNT(*) FROM wallet_recharges WHERE status='pending'"
        ).fetchone()[0]

        return render_template('wallet_requests_admin.html',
                               requests=requests_list,
                               filter_status=filter_status,
                               pending_count=pending_count)


    @app.route('/admin/wallet-requests/<int:req_id>/approve', methods=['POST'])
    @admin_required
    def approve_recharge(req_id):
        db      = get_db()
        recharge = db.execute(
            "SELECT * FROM wallet_recharges WHERE id=?", (req_id,)
        ).fetchone()
        if recharge:
            db.execute(
                "UPDATE wallet_recharges SET status='approved', "
                "processed_at=? WHERE id=?",
                (_now_ist().strftime('%Y-%m-%d %H:%M:%S'), req_id)
            )
            db.commit()
            flash(f'Recharge of \u20b9{recharge["amount"]:.0f} for @{recharge["username"]} approved!', 'success')
            _username = recharge['username']
            _amount   = recharge['amount']
            def _bg_push_recharge(u, amt):
                _db = get_db()
                try:
                    _push_to_users(_db, u, '\u2705 Wallet Recharged!',
                                   f'\u20b9{amt:.0f} has been added to your wallet.',
                                   '/wallet')
                finally:
                    _db.close()
            threading.Thread(target=_bg_push_recharge, args=(_username, _amount), daemon=True).start()
        return redirect(url_for('admin_wallet_requests', status='pending'))


    @app.route('/admin/wallet-requests/<int:req_id>/reject', methods=['POST'])
    @admin_required
    def reject_recharge(req_id):
        admin_note = request.form.get('admin_note', '').strip()
        db         = get_db()
        recharge   = db.execute(
            "SELECT * FROM wallet_recharges WHERE id=?", (req_id,)
        ).fetchone()
        if recharge:
            db.execute(
                "UPDATE wallet_recharges SET status='rejected', "
                "processed_at=?, admin_note=? WHERE id=?",
                (_now_ist().strftime('%Y-%m-%d %H:%M:%S'), admin_note, req_id)
            )
            db.commit()
            flash(f'Recharge request from @{recharge["username"]} rejected.', 'warning')
        return redirect(url_for('admin_wallet_requests', status='pending'))


    @app.route('/admin/members/<username>/wallet-adjust', methods=['POST'])
    @admin_required
    def admin_wallet_adjust(username):
        amount = request.form.get('amount', '').strip()
        note   = request.form.get('note', '').strip() or 'Manual adjustment by admin'
        try:
            amount = float(amount)
            if amount == 0:
                flash('Amount cannot be zero.', 'warning')
                return redirect(url_for('member_detail', username=username))
        except ValueError:
            flash('Invalid amount.', 'danger')
            return redirect(url_for('member_detail', username=username))

        db = get_db()
        exists = db.execute("SELECT username FROM users WHERE username=?", (username,)).fetchone()
        if not exists:
            flash('Member not found.', 'danger')
            return redirect(url_for('admin_members'))

        ts = _now_ist().strftime('%Y-%m-%d %H:%M:%S')
        # One row per adjustment (distinct UTR) so history/reconciliation stays clear.
        utr = 'ADMIN-ADJUST-' + ts.replace(' ', 'T').replace(':', '') + '-' + secrets.token_hex(4)

        db.execute(
            "INSERT INTO wallet_recharges (username, amount, utr_number, status, "
            "requested_at, processed_at, admin_note) "
            "VALUES (?, ?, ?, 'approved', ?, ?, ?)",
            (username, amount, utr, ts, ts, note),
        )
        actor = (session.get('username') or '').strip() or 'admin'
        _log_activity(
            db,
            actor,
            'wallet_admin_adjust',
            f'target={username} amount={amount:g} note={note}',
        )
        db.commit()

        wstat = _get_wallet(db, username)
        action = 'credited to' if amount > 0 else 'debited from'
        flash(
            f'\u20b9{abs(amount):.0f} {action} @{username}\'s wallet. '
            f'Available now \u20b9{wstat["balance"]:.0f} '
            f'(credits \u20b9{wstat["recharged"]:.0f}, pool spend \u20b9{wstat["spent"]:.0f}). '
            f'Note: {note}',
            'success',
        )

        def _bg_push_adjust(u: str, amt: float):
            _db = get_db()
            try:
                if amt > 0:
                    _push_to_users(
                        _db,
                        u,
                        '\u2705 Wallet adjusted',
                        f'\u20b9{amt:.0f} credited by admin. Open Wallet for details.',
                        '/wallet',
                    )
                else:
                    _push_to_users(
                        _db,
                        u,
                        '\u26a0\ufe0f Wallet adjusted',
                        f'\u20b9{abs(amt):.0f} debited by admin. Open Wallet for details.',
                        '/wallet',
                    )
            finally:
                _db.close()

        threading.Thread(target=_bg_push_adjust, args=(username, amount), daemon=True).start()
        return redirect(url_for('member_detail', username=username))
