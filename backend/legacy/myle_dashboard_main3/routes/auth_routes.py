"""
Authentication routes (register, login, logout, password reset).

Registered via register_auth_routes(app) at the end of app.py load so helpers
on the app module are available without circular import at import time.
"""
from __future__ import annotations

import datetime
import re
import secrets

from flask import flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from auth_context import AUTH_SESSION_VERSION
from database import get_db
from helpers import validate_upline_assignment_roles
from helpers import ensure_upline_fields_for_user


def _normalize_registration_fbo(raw: str) -> str:
    """Strip whitespace and a single leading # so #910… and 910… match DB lookups."""
    return (raw or '').strip().lstrip('#').strip()


def _fbo_digits_for_uniqueness(raw: str) -> str:
    """Digits-only key — prevents duplicate accounts for #FBO vs FBO and dashed variants."""
    return re.sub(r'\D', '', (raw or ''))


def register_auth_routes(app):
    """Attach auth-related URL rules to the Flask app (preserves endpoint names)."""
    from app import (  # noqa: PLC0415 — late import after app module is populated
        _log_activity,
        _now_ist,
        _send_password_reset_email,
        _today_ist,
    )

    @app.route('/register', methods=['GET', 'POST'])
    def register():
        if 'user_id' in session:
            return redirect(url_for('index'))

        if request.method == 'POST':
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '').strip()
            email = request.form.get('email', '').strip()
            fbo_id = _normalize_registration_fbo(request.form.get('fbo_id', ''))
            upline_fbo_id = _normalize_registration_fbo(request.form.get('upline_fbo_id', ''))
            phone = request.form.get('phone', '').strip()

            if not username or not password or not email or not fbo_id or not upline_fbo_id:
                flash('Username, Password, Email, FBO ID, and Upline FBO ID are required.', 'danger')
                return render_template('register.html')

            db = get_db()

            if db.execute(
                "SELECT id FROM users WHERE LOWER(TRIM(username)) = LOWER(TRIM(?))",
                (username,),
            ).fetchone():
                flash('That username is already taken. Please choose another.', 'danger')
                return render_template('register.html')

            _fbo_sig = _fbo_digits_for_uniqueness(fbo_id)
            if _fbo_sig and db.execute(
                """
                SELECT id FROM users
                WHERE REPLACE(REPLACE(REPLACE(TRIM(COALESCE(fbo_id,'')),'#',''),'-',''),' ','') = ?
                  AND TRIM(COALESCE(fbo_id,'')) != ''
                LIMIT 1
                """,
                (_fbo_sig,),
            ).fetchone():
                flash('That FBO ID is already registered. Each FBO ID must be unique.', 'danger')
                return render_template('register.html')

            if phone and db.execute("SELECT id FROM users WHERE phone=? AND phone!=''", (phone,)).fetchone():
                flash('That mobile number is already registered. Please use a different number.', 'danger')
                return render_template('register.html')

            # Priority: exact FBO match → digit-signature match → upline keyed by username
            upline_user = db.execute(
                """
                SELECT username, role, TRIM(COALESCE(fbo_id,'')) AS fbo_id
                FROM users
                WHERE TRIM(fbo_id)=? AND TRIM(COALESCE(fbo_id,''))!=''
                LIMIT 1
                """,
                (upline_fbo_id,),
            ).fetchone()
            if not upline_user:
                _usig = _fbo_digits_for_uniqueness(upline_fbo_id)
                if _usig:
                    upline_user = db.execute(
                        """
                        SELECT username, role, TRIM(COALESCE(fbo_id,'')) AS fbo_id
                        FROM users
                        WHERE REPLACE(REPLACE(REPLACE(TRIM(COALESCE(fbo_id,'')),'#',''),'-',''),' ','') = ?
                          AND TRIM(COALESCE(fbo_id,'')) != ''
                          AND status = 'approved'
                        LIMIT 1
                        """,
                        (_usig,),
                    ).fetchone()
            if not upline_user:
                upline_user = db.execute(
                    """
                    SELECT username, role, TRIM(COALESCE(fbo_id,'')) AS fbo_id
                    FROM users WHERE username=?
                    LIMIT 1
                    """,
                    (upline_fbo_id,),
                ).fetchone()
            if not upline_user:
                flash(
                    f'Upline not found for "{upline_fbo_id}". '
                    f'Please enter your leader\'s or admin FBO ID or username.',
                    'danger',
                )
                return render_template('register.html')
            _ok, _msg = validate_upline_assignment_roles('team', (upline_user['role'] or '').strip())
            if not _ok:
                flash(f'{_msg} Please enter a valid upline FBO ID.', 'danger')
                return render_template('register.html')
            upline_name = upline_user['username']
            upline_fbo_stored = (upline_user['fbo_id'] or '').strip() or upline_fbo_id

            is_new = 1 if request.form.get('is_new_joining') else 0
            joining_dt = request.form.get('joining_date', '').strip()
            t_status = 'pending' if is_new else 'not_required'

            db.execute(
                "INSERT INTO users (username, password, role, fbo_id, upline_name, upline_username, upline_fbo_id, "
                "phone, email, status, "
                "training_required, training_status, joining_date, name) "
                "VALUES (?, ?, 'team', ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?)",
                (
                    username,
                    generate_password_hash(password, method='pbkdf2:sha256'),
                    fbo_id,
                    upline_name,
                    upline_name,
                    upline_fbo_stored,
                    phone,
                    email,
                    is_new,
                    t_status,
                    joining_dt,
                    username,
                ),
            )
            db.commit()
            flash('Registration submitted! Your account is pending admin approval.', 'success')
            return redirect(url_for('login'))

        today = _today_ist().isoformat()
        return render_template('register.html', today=today)

    @app.route('/api/lookup-upline-fbo', methods=['GET'])
    def lookup_upline_fbo():
        """
        Public endpoint used by the registration page to validate an upline FBO ID
        before form submission. Returns only the minimum needed: display name + whether
        the FBO belongs to an approved leader or admin. No sensitive data exposed.

        ``is_leader`` is true whenever registration under this FBO is allowed (leader or
        admin). Older clients only read ``is_leader``; ``is_valid_upline`` is the same
        gate for newer UIs.
        """
        from flask import jsonify  # noqa: PLC0415
        fbo_id = (request.args.get('fbo_id') or '').strip()
        if not fbo_id:
            return jsonify({
                'found': False,
                'is_leader': False,
                'is_valid_upline': False,
                'message': 'Enter an FBO ID.',
            })

        db = get_db()
        row = db.execute(
            "SELECT username, role, status FROM users WHERE TRIM(fbo_id)=? AND TRIM(COALESCE(fbo_id,''))!=''",
            (fbo_id,),
        ).fetchone()

        if not row:
            return jsonify({
                'found': False,
                'is_leader': False,
                'is_valid_upline': False,
                'message': 'FBO ID not found. Check the ID with your leader or admin.',
            })

        role   = (row['role']   or '').strip().lower()
        status = (row['status'] or '').strip().lower()
        name   = (row['username'] or '').strip()

        if role == 'team':
            return jsonify({
                'found': True,
                'is_leader': False,
                'is_valid_upline': False,
                'message': 'This FBO ID belongs to a team member, not a leader or admin. '
                           'Please enter your upline\'s FBO ID.',
            })
        if role not in ('leader', 'admin'):
            return jsonify({
                'found': True,
                'is_leader': False,
                'is_valid_upline': False,
                'message': 'This FBO ID cannot be used as an upline for registration.',
            })
        if status != 'approved':
            return jsonify({
                'found': True,
                'is_leader': role == 'leader',
                'is_valid_upline': False,
                'message': 'This account is not yet active. Please contact admin.',
            })

        _label = 'Leader' if role == 'leader' else 'Admin'
        return jsonify({
            'found': True,
            # Legacy/mobile: many clients gate submit on is_leader only; must be true for admin too.
            'is_leader': True,
            'is_valid_upline': True,
            'upline_role': role,
            'name': name,
            'message': f'{_label} verified: {name}',
        })

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if 'user_id' in session:
            return redirect(url_for('index'))

        if request.method == 'POST':
            fbo_or_legacy = (request.form.get('fbo_id') or request.form.get('username') or '').strip()
            password = request.form.get('password', '').strip()

            if not fbo_or_legacy or not password:
                flash('FBO ID and password are required.', 'danger')
                return render_template('login.html')

            db = get_db()
            user = db.execute(
                "SELECT * FROM users WHERE TRIM(fbo_id) = ? AND TRIM(COALESCE(fbo_id,'')) != ''",
                (fbo_or_legacy,),
            ).fetchone()
            if not user:
                user = db.execute(
                    "SELECT * FROM users WHERE username=?",
                    (fbo_or_legacy,),
                ).fetchone()

            password_ok = False
            if user:
                stored = user['password']
                if stored.startswith(('pbkdf2:', 'scrypt:', 'argon2:')):
                    password_ok = check_password_hash(stored, password)
                else:
                    password_ok = stored == password
                    if password_ok:
                        db.execute(
                            "UPDATE users SET password=? WHERE id=?",
                            (generate_password_hash(password, method='pbkdf2:sha256'), user['id']),
                        )
                        db.commit()

            if user and password_ok:
                _keys = user.keys() if hasattr(user, 'keys') else []
                if user['role'] in ('team', 'leader'):
                    _blk = int(user['access_blocked'] or 0) if 'access_blocked' in _keys else 0
                    _ds = (user['discipline_status'] or '').strip() if 'discipline_status' in _keys else ''
                    if _blk or _ds == 'removed':
                        flash(
                            'System se remove kiya gaya due to non-performance. Admin se contact karein.',
                            'danger',
                        )
                        return render_template('login.html')

                if user['status'] == 'pending':
                    flash('Your account is pending admin approval. Please check back soon.', 'warning')
                    return render_template('login.html')
                if user['status'] == 'rejected':
                    flash('Your registration request was rejected. Contact the admin for help.', 'danger')
                    return render_template('login.html')

                if user['role'] in ('team', 'leader') and user['status'] == 'approved':
                    ensure_upline_fields_for_user(db, user['username'])
                    db.commit()
                    user = db.execute("SELECT * FROM users WHERE id=?", (user['id'],)).fetchone()

                session.clear()
                session.permanent = True
                session['user_id'] = user['id']
                session['username'] = user['username']
                session['fbo_id'] = (user['fbo_id'] or '').strip() or (user['username'] or '').strip()
                session['role'] = user['role']
                session['has_dp'] = bool(user['display_picture'])
                keys = user.keys() if hasattr(user, 'keys') else []
                session['training_status'] = user['training_status'] if 'training_status' in keys else 'not_required'
                session['auth_version'] = AUTH_SESSION_VERSION
                # session.clear() dropped the pre-login CSRF token; issue a fresh one for the next POST
                session['_csrf_token'] = secrets.token_hex(32)
                _nm = (user['name'] if 'name' in keys and (user['name'] or '').strip() else '') or user['username']
                session['display_name'] = _nm
                _log_activity(db, user['username'], 'login', f"Role: {user['role']}")
                flash(f'Welcome back, {_nm}!', 'success')
                if user['role'] == 'admin':
                    return redirect(url_for('admin_dashboard'))
                if user['role'] == 'leader':
                    return redirect(url_for('leader_dashboard'))
                return redirect(url_for('team_dashboard'))
            flash('Invalid FBO ID or password.', 'danger')

        return render_template('login.html')

    @app.route('/forgot-password', methods=['GET', 'POST'])
    def forgot_password():
        if 'user_id' in session:
            return redirect(url_for('index'))

        email_sent = False
        if request.method == 'POST':
            email = request.form.get('email', '').strip().lower()
            if email:
                db = get_db()
                user = db.execute(
                    "SELECT username, email FROM users WHERE LOWER(email)=? AND status='approved'",
                    (email,),
                ).fetchone()
                if user:
                    token = secrets.token_urlsafe(32)
                    expires_at = (_now_ist() + datetime.timedelta(hours=1)).strftime('%Y-%m-%d %H:%M:%S')
                    db.execute(
                        "INSERT INTO password_reset_tokens (username, token, expires_at) VALUES (?,?,?)",
                        (user['username'], token, expires_at),
                    )
                    db.commit()
                    reset_url = url_for('reset_password', token=token, _external=True)
                    sent = _send_password_reset_email(user['email'], user['username'], reset_url)
                    if not sent:
                        flash(f'SMTP not configured. Reset link (share manually): {reset_url}', 'warning')
            email_sent = True

        return render_template('forgot_password.html', email_sent=email_sent)

    @app.route('/reset-password/<token>', methods=['GET', 'POST'])
    def reset_password(token):
        if 'user_id' in session:
            return redirect(url_for('index'))

        db = get_db()
        row = db.execute(
            "SELECT * FROM password_reset_tokens WHERE token=? AND used=0",
            (token,),
        ).fetchone()

        if not row:
            flash('This password reset link is invalid or has already been used.', 'danger')
            return redirect(url_for('login'))

        expires_at = datetime.datetime.strptime(row['expires_at'], '%Y-%m-%d %H:%M:%S')
        if _now_ist() > expires_at:
            flash('This password reset link has expired. Please request a new one.', 'danger')
            return redirect(url_for('forgot_password'))

        if request.method == 'POST':
            new_password = request.form.get('password', '').strip()
            confirm = request.form.get('confirm_password', '').strip()
            if not new_password or len(new_password) < 6:
                flash('Password must be at least 6 characters.', 'danger')
                return render_template('reset_password.html', token=token)
            if new_password != confirm:
                flash('Passwords do not match.', 'danger')
                return render_template('reset_password.html', token=token)

            db.execute(
                "UPDATE users SET password=? WHERE username=?",
                (generate_password_hash(new_password, method='pbkdf2:sha256'), row['username']),
            )
            db.execute("UPDATE password_reset_tokens SET used=1 WHERE id=?", (row['id'],))
            db.commit()
            flash('Password updated successfully! Please sign in.', 'success')
            return redirect(url_for('login'))

        return render_template('reset_password.html', token=token)

    @app.route('/logout')
    def logout():
        uid = session.get('user_id')
        if uid:
            db = get_db()
            row = db.execute('SELECT username FROM users WHERE id=?', (int(uid),)).fetchone()
            if row:
                _log_activity(db, row['username'], 'logout', '')
                db.commit()
        session.clear()
        flash('You have been logged out.', 'info')
        return redirect(url_for('login'))
