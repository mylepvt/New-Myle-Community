import os
import io
import csv
import base64
import hashlib
import hmac
import json
import secrets
import datetime
import calendar
import smtplib
import ssl
import threading
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from urllib.parse import quote as _url_quote
from flask import (Flask, render_template, request, redirect, url_for,
                   flash, session, g, Response, make_response, abort, send_from_directory,
                   send_file, jsonify)
from types import SimpleNamespace
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.exceptions import HTTPException
from database import (
    get_db,
    close_db,
    init_db,
    migrate_db,
    seed_users,
    seed_training_questions,
    startup_invariant_scan,
)
from auth_context import AUTH_SESSION_VERSION, acting_username, acting_user_id, refresh_session_user
from reliability import ensure_request_id, request_id
from pathlib import Path
from services.wallet_ledger import count_buyer_claimed_leads, sum_pool_spent_for_buyer
from helpers import (  # noqa: F401 — shared constants & utility functions
    STATUSES, STATUS_TO_STAGE, PIPELINE_AUTO_EXPIRE_STATUSES, SLA_SOFT_WATCH_EXCLUDE,
    CALL_STATUS_VALUES, TEAM_CALL_STATUS_VALUES, TRACKS,
    WORKING_SIDE_PIPELINE_STATUSES, WORKING_BOARD_HOME_STATUSES,
    ADMIN_PIPELINE_BUCKET_ENROLLMENT, ADMIN_PIPELINE_BUCKET_TRAINING, ADMIN_PIPELINE_BUCKET_CLOSING,
    CALL_RESULT_TAGS, RETARGET_TAGS, FOLLOWUP_TAGS, SOURCES,
    TEAM_FORBIDDEN_STATUSES, TEAM_ALLOWED_STATUSES,
    BADGE_DEFS, PAYMENT_AMOUNT, BADGE_META, STAGE_TO_DEFAULT_STATUS,
    _now_ist, _today_ist, SQLITE_NOW_IST,
    payment_columns_mark_paid,
    repair_lead_payment_invariants,
    _log_activity, _log_lead_event,
    _get_setting, _set_setting,
    _get_wallet, _get_metrics,
    _get_downline_usernames, _get_network_usernames,
    _get_admin_username, _get_leader_for_user,
    _calculate_priority, _leads_with_priority,
    _calculate_heat_score, _get_next_action, _generate_ai_tip,
    _enrich_lead, _enrich_leads,
    _transition_stage, _trigger_training_unlock, _check_seat_hold_expiry,
    _auto_expire_pipeline_leads, _auto_expire_pipeline_leads_batch,
    _expire_all_pipeline_leads,
    _check_and_award_badges, _check_and_award_badges_inner,
    _get_user_badges_emoji,
    _upsert_daily_score, _get_today_score, _get_actual_daily_counts,
    INACTIVITY_BLOCK_CLAIM_HOURS,
    INACTIVITY_LOCK_HOURS,
    INACTIVITY_WARN_HOURS,
    user_inactivity_hours,
    followup_discipline_process_overdue,
    _penalize_missed_followups,
    user_id_for_username,
    user_ids_for_usernames,
    _assignee_username_for_lead,
    daily_call_target, DAILY_CALL_ENFORCE_START_HOUR_IST,
    get_performance_ui_state,
    inactivity_escalation_days,
    compute_step8_team_coach_for_user,
    compute_step8_leader_coach,
    build_step8_admin_ai_lines,
    build_step8_evening_summary_line,
    sql_ts_calendar_day,
    get_today_metrics,
    LEAD_SQL_CALL_LOGGED,
    layout_metrics_cache_get,
    layout_metrics_cache_set,
)

# Optional QR code support
try:
    import qrcode
    QR_AVAILABLE = True
except ImportError:
    QR_AVAILABLE = False

# Optional PDF support
try:
    import pdfplumber
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

# Optional Web Push support (pywebpush + cryptography)
try:
    from pywebpush import webpush, WebPushException
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives import serialization as _crypto_serial
    PUSH_AVAILABLE = True
except ImportError:
    PUSH_AVAILABLE = False

# Optional APScheduler for daily reminder push notifications
try:
    from apscheduler.schedulers.background import BackgroundScheduler
    import atexit
    SCHEDULER_AVAILABLE = True
except ImportError:
    SCHEDULER_AVAILABLE = False

# Optional Anthropic AI (Maya assistant — fallback)
try:
    import anthropic as _anthropic_lib
    ANTHROPIC_AVAILABLE = True
except ImportError:
    _anthropic_lib = None
    ANTHROPIC_AVAILABLE = False

# Optional Google Gemini AI (Maya assistant — primary, free tier)
try:
    import google.generativeai as _gemini_lib
    import PIL.Image as _PIL_Image
    import io as _io_lib
    GEMINI_AVAILABLE = True
except ImportError:
    _gemini_lib  = None
    _PIL_Image   = None
    GEMINI_AVAILABLE = False

app = Flask(__name__)
app.teardown_appcontext(close_db)

app.config['TEMPLATES_AUTO_RELOAD'] = True
# Cap upload size (payment proofs, imports, etc.)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# ── Structured logging ───────────────────────────────────────
import logging as _logging
_log_level = _logging.DEBUG if os.environ.get('FLASK_DEBUG') else _logging.INFO
_log_fmt = _logging.Formatter(
    '[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
_stream_handler = _logging.StreamHandler()
_stream_handler.setFormatter(_log_fmt)
_stream_handler.setLevel(_log_level)
app.logger.handlers.clear()
app.logger.addHandler(_stream_handler)
app.logger.setLevel(_log_level)

# ── Secret key & cookie security ─────────────────────────────
_env_secret = os.environ.get('SECRET_KEY')
if _env_secret:
    app.secret_key = _env_secret
else:
    # IMPORTANT (multi-worker): secret MUST be identical in every Gunicorn worker process.
    # Using secrets.token_hex(32) here caused a *different* key per worker → session cookies
    # signed on worker A failed on worker B → users randomly "logged out".
    # Stable shared fallback keeps sessions valid until SECRET_KEY is set in the environment.
    import sys as _sys

    app.secret_key = os.environ.get(
        'FLASK_DEV_SECRET_FALLBACK',
        'myle_community_secret_2024_local',
    )
    print(
        '[SECURITY WARNING] SECRET_KEY env var not set — using shared dev fallback '
        '(set SECRET_KEY on Render for strong signing + consistent sessions across deploys).',
        file=_sys.stderr,
    )

app.config['SESSION_PERMANENT'] = True                                    # every session permanent by default
app.config['PERMANENT_SESSION_LIFETIME'] = datetime.timedelta(days=30)    # 30-day rolling sessions
# SESSION_TYPE is intentionally NOT set to filesystem/redis:
# Render's disk is ephemeral — server-side filesystem sessions are wiped on every deploy.
# Flask's default client-side signed cookies survive deploys as long as SECRET_KEY is stable.
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_HTTPONLY'] = True


def _use_secure_cookies():
    """True when app is served over HTTPS (Render, explicit env, or legacy SECRET_KEY signal)."""
    override = (os.environ.get('SESSION_COOKIE_SECURE') or '').strip().lower()
    if override in ('0', 'false', 'no'):
        return False
    if override in ('1', 'true', 'yes'):
        return True
    if (os.environ.get('RENDER') or '').lower() == 'true':
        return True
    if (os.environ.get('FLASK_ENV') or '').lower() == 'production':
        return True
    return bool(_env_secret)


app.config['SESSION_COOKIE_SECURE'] = _use_secure_cookies()


@app.before_request
def _perf_request_start():
    """Cheap timer for optional slow-request logging (SLOW_REQUEST_MS). Skips static assets."""
    ensure_request_id()
    if request.path.startswith('/static'):
        return
    g._req_t0 = time.perf_counter()


@app.after_request
def _perf_log_slow_request(response):
    """Set SLOW_REQUEST_MS=500 (etc.) to log slow HTML/API calls — use to find heavy routes."""
    try:
        thr = float((os.environ.get('SLOW_REQUEST_MS') or '0').strip() or 0)
    except ValueError:
        thr = 0
    if thr <= 0:
        return response
    t0 = getattr(g, '_req_t0', None)
    if t0 is None:
        return response
    elapsed_ms = (time.perf_counter() - t0) * 1000
    if elapsed_ms >= thr:
        app.logger.warning(
            'slow_request rid=%s path=%s method=%s ms=%.0f',
            request_id(),
            request.path,
            request.method,
            elapsed_ms,
        )
    return response


def myle_ai_features_enabled() -> bool:
    """
    Sidebar «AI Intelligence» + floating Maya chat + /api/chat.
    Off by default. Set MYLE_AI_FEATURES=1 (or legacy MAYA_CHAT_ENABLED=1) to enable.
    """
    a = (os.environ.get('MYLE_AI_FEATURES') or '').strip().lower()
    if a in ('1', 'true', 'yes', 'on'):
        return True
    m = (os.environ.get('MAYA_CHAT_ENABLED') or '').strip().lower()
    return m in ('1', 'true', 'yes', 'on')


def maya_chat_enabled() -> bool:
    """Alias for /api/chat gating."""
    return myle_ai_features_enabled()


@app.context_processor
def inject_myle_ai_flags():
    en = myle_ai_features_enabled()
    return {'myle_ai_features_enabled': en, 'maya_chat_enabled': en}


@app.context_processor
def inject_db_user():
    """Navbar/header user chip — session only (no per-request users row fetch)."""
    if not session.get('user_id'):
        return {'db_user': None, 'display_name': ''}
    un = (session.get('username') or '').strip()
    dn = (session.get('display_name') or '').strip() or un
    fb = (session.get('fbo_id') or '').strip()
    return {
        'db_user': SimpleNamespace(username=un, display_name=dn, fbo_id=fb) if un else None,
        'display_name': dn,
    }


@app.after_request
def _security_headers(response):
    """Baseline security headers for HTML/API responses (disable with SECURITY_HEADERS=0)."""
    if (os.environ.get('SECURITY_HEADERS') or '1').strip().lower() in ('0', 'false', 'no'):
        return response
    # Do not override if something else already set (e.g. future middleware)
    response.headers.setdefault('X-Content-Type-Options', 'nosniff')
    response.headers.setdefault('X-Frame-Options', 'SAMEORIGIN')
    response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
    response.headers.setdefault(
        'Permissions-Policy',
        'accelerometer=(), camera=(), geolocation=(), gyroscope=(), magnetometer=(), '
        'microphone=(), payment=(), usb=()'
    )
    if _use_secure_cookies():
        response.headers.setdefault('Strict-Transport-Security', 'max-age=31536000')
    response.headers.setdefault('X-Request-ID', request_id())
    return response

# Persistent upload root: set UPLOAD_ROOT to a persistent path (e.g. /data on Render) so
# PDF/audio uploads survive restarts; default is project directory (ephemeral on Render).
def _upload_root():
    return os.environ.get('UPLOAD_ROOT') or os.path.abspath(os.path.dirname(__file__))


_upload_root_warned = False


def _warn_upload_root_once():
    global _upload_root_warned
    if _upload_root_warned:
        return
    if os.environ.get('SECRET_KEY') and not os.environ.get('UPLOAD_ROOT'):
        _upload_root_warned = True
        import sys
        print('[UPLOAD] UPLOAD_ROOT is not set in production — training PDF/audio may be lost after restart. '
              'Mount a persistent disk (e.g. /data) and set UPLOAD_ROOT=/data.', file=sys.stderr)

# ── Maya AI System Prompt ─────────────────────────────────────
MAYA_SYSTEM_PROMPT = """You are Maya — the AI assistant for Myle Community, a network marketing team management platform.

You help team members (and admins) with:
1. WhatsApp scripts for inviting prospects
2. Objection handling — professional, empathetic responses to common objections
3. Lead management and follow-up advice
4. Training guidance (7-day program, test prep)
5. App usage help (leads, wallet, daily reports, training)
6. Network marketing Q&A and motivation

## About Myle Community
- Network marketing business based on product sales (Forever Living)
- Members invite prospects and guide them through a conversion journey
- 3 investment tracks: Slow Track (₹8,000), Medium Track (₹18,000), Fast Track (₹38,000)
- ₹196 initial payment gives prospect access to a presentation video
- 3-day enrollment window after video to commit to a track
- Seat Hold deposit collected before full track payment

## About the App
- **Leads page**: Add prospects, track them by status (New Lead → Contacted → Invited → Video Sent → Video Watched → Paid ₹196 → Day 1 → Day 2 → Interview → Track Selected → Seat Hold Confirmed → Fully Converted)
- **Wallet**: Team members recharge via UPI QR code, spend on claiming leads from pool
- **Training**: 7-day video training + MCQ test (60/100 pass mark) → certificate → app unlocked
- **Daily Reports**: Submit daily KPIs every day
- **Lead Pool**: Admin imports or adds leads; team claims them by spending wallet balance

## WhatsApp Scripts

### First Approach
"Hey [Name]! 👋 I wanted to share a business opportunity that might fit you. Do you have 10 minutes for a quick call? I’ll explain properly — no pressure, just a conversation."

### After Adding to Leads / Sending Video
"Hey [Name]! I’ve sent a short presentation — about 20–25 minutes. Watch it when you can. You’ll have a 3-day window to decide next steps. If anything is unclear, message me anytime. 😊"

### 24-Hour Follow-up
"Hey [Name]! Just checking in — did you get a chance to watch the presentation? Any questions? I’m here. 🙏"

### 3-Day Follow-up
"Hey [Name]! Any thoughts on the presentation? Today is the last day of the window. No pressure — just let me know either way. 👍"

### After Video Watched — Invitation
"Hey! What did you think of the video? I want to make sure you really understand the model — when works for a 15-minute call? I can clear up any doubts. 🎯"

## Common Objections & Answers

### "I don't have time"
"I hear you — everyone’s busy. That’s exactly why this model works on your schedule. You can start part-time; even 1–2 focused hours a day is enough at first. Can we book 15 minutes so I can show you the full picture?"

### "Is this fraud / MLM / a pyramid?"
"That’s a fair question. Legal direct selling is different from illegal pyramid schemes: real products are sold, income comes from sales, not from recruiting alone. Our industry is regulated (e.g. IDSA in India). Want a simple comparison so you can judge for yourself?"

### "It’s too expensive / I don’t have money"
"I understand. Think of it as a small startup investment — many offline businesses need lakhs to begin; here the entry is much lower. If someone works the system seriously, many recover it in a few months. Want to walk through the numbers once?"

### "I’ll think and tell you"
"Of course — decisions matter. What’s the one main thing you’re thinking about? If you share it, I can address it directly — that usually saves you time."

### "I don’t have a network"
"Very common myth. This isn’t only friends and family — with digital outreach, people also build with new contacts. Our training covers how to start conversations ethically. In practice, you only need a small group of serious people to begin."

### "I tried another company and it didn’t work"
"Thanks for being open. In any business, results depend on the system and mentorship. Here we have structured daily training, guidance, and follow-up. Want to know what’s different this time?"

### "Only people at the top earn"
"I get why it feels that way. In a fair plan, earnings track team performance and personal work — not just who joined first. I can explain with a simple example if you like."

## Communication Style
- Reply in clear, professional English — warm and conversational, suitable for SaaS / business context
- Be encouraging, empathetic, and solution-focused
- Keep answers concise unless a full script is requested
- When the user shares a screenshot, analyze it and give specific, actionable advice
- Use emojis sparingly to stay friendly, not gimmicky
- Address the emotional side of objections before the logical rebuttal"""





# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
#  Auth Decorators (see decorators.py)
# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

from decorators import admin_required, login_required, safe_route

# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
#  Helpers
# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

# Drill-down metric config
DRILL_LEAD_METRICS = {
    'total':          ('Total Leads',    'bi bi-people-fill',              'primary', None),
    'claimed':        ('Claimed Leads',  'bi bi-hand-index-fill',          'primary', "claimed_at IS NOT NULL AND TRIM(COALESCE(l.claimed_at,''))!=''"),
    'enrolled':       ('Enrolled Leads', 'bi bi-person-check-fill',        'success', "enrolled_at IS NOT NULL AND TRIM(COALESCE(l.enrolled_at,''))!='' AND LOWER(COALESCE(l.payment_proof_approval_status,''))='approved'"),
    'converted':      ('Converted',      'bi bi-check-circle-fill',        'success', "status IN ('Converted','Fully Converted')"),
    'paid':           ('Payments ₹196',  'bi bi-credit-card-2-front-fill', 'info',    'payment_done=1'),
    'day1':           ('Day 1 Done',     'bi bi-1-circle-fill',            'info',    'day1_done=1'),
    'day2':           ('Day 2 Done',     'bi bi-2-circle-fill',            'warning', 'day2_done=1'),
    'interview':      ('Interview Done', 'bi bi-mic-fill',                 'danger',  'interview_done=1'),
    'revenue':        ('Total Revenue',  'bi bi-currency-rupee',           'warning', 'payment_done=1'),
    'track_selected': ('Track Selected', 'bi bi-bookmark-check-fill',      'info',    "status='Track Selected'"),
    'seat_hold':      ('Seat Hold',      'bi bi-shield-check-fill',        'purple',  "status='Seat Hold Confirmed'"),
    'fully_converted':('Fully Converted','bi bi-trophy-fill',              'success', "status='Fully Converted'"),
}

DRILL_REPORT_METRICS = {
    'total_calling':    ('Total Calls',   'bi bi-telephone-fill',         'primary'),
    'pdf_covered':      ('Leads Claimed', 'bi bi-people-fill',            'danger'),
    'calls_picked':     ('Calls Picked',  'bi bi-telephone-inbound-fill', 'success'),
    'enrollments_done': ('Enrollments',   'bi bi-person-check-fill',      'success'),
    'plan_2cc':         ('2CC Plan',      'bi bi-star-fill',              'warning'),
}


_qr_cache: dict = {}   # {upi_id: (bytes, b64_str)}

def _generate_upi_qr_bytes(upi_id):
    """Generate UPI QR code PNG bytes. Returns None if qrcode not available."""
    if not QR_AVAILABLE or not upi_id:
        return None
    if upi_id in _qr_cache:
        return _qr_cache[upi_id][0]
    upi_string = f"upi://pay?pa={_url_quote(upi_id)}&pn=Myle+Community&cu=INR"
    qr = qrcode.QRCode(version=1, box_size=8, border=4)
    qr.add_data(upi_string)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    data = buf.getvalue()
    b64 = base64.b64encode(data).decode('utf-8')
    _qr_cache[upi_id] = (data, b64)
    return data


def _generate_upi_qr_base64(upi_id):
    """Generate UPI QR as base64 string (cached)."""
    if not QR_AVAILABLE or not upi_id:
        return None
    if upi_id in _qr_cache:
        return _qr_cache[upi_id][1]
    _generate_upi_qr_bytes(upi_id)   # populates cache
    return _qr_cache.get(upi_id, (None, None))[1]


import re as _re
_PHONE_RE = _re.compile(r'(?:(?:\+|0{0,2})91[-\s]?)?([6-9]\d{9})\b')


def _extract_leads_from_pdf(file_stream):
    """
    Extract (name, phone, email) rows from a PDF file stream.
    Returns (list_of_dicts, error_string).  error_string is None on success.
    """
    if not PDF_AVAILABLE:
        return None, "PDF parsing library not installed. Run: pip install pdfplumber"

    leads = []
    try:
        with pdfplumber.open(file_stream) as pdf:
            for page in pdf.pages:
                # \u2500\u2500 Try table extraction first \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
                tables = page.extract_tables()
                if tables:
                    for table in tables:
                        if not table:
                            continue
                        header_row = [str(c or '').lower().strip() for c in table[0]]
                        name_col  = next((i for i, h in enumerate(header_row)
                                          if 'name' in h), None)
                        phone_col = next((i for i, h in enumerate(header_row)
                                          if any(k in h for k in ('phone', 'mobile', 'contact', 'number'))), None)
                        email_col = next((i for i, h in enumerate(header_row)
                                          if 'email' in h or 'mail' in h), None)
                        city_col  = next((i for i, h in enumerate(header_row)
                                          if 'city' in h or 'location' in h), None)
                        # skip header row if we detected column labels
                        start = 1 if (name_col is not None or phone_col is not None) else 0
                        for row in table[start:]:
                            if not row:
                                continue
                            cells = [str(c or '').strip() for c in row]
                            safe  = lambda i: cells[i] if i is not None and i < len(cells) else ''
                            name  = safe(name_col)
                            phone = safe(phone_col)
                            email = safe(email_col)
                            city  = safe(city_col)
                            # normalize phone
                            m = _PHONE_RE.search(phone)
                            if m:
                                phone = m.group(1)
                            if name or phone:
                                leads.append({'name': name, 'phone': phone,
                                              'email': email, 'city': city})
                else:
                    # \u2500\u2500 Fall back to line-by-line text scan \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
                    text = page.extract_text() or ''
                    for line in text.split('\n'):
                        m = _PHONE_RE.search(line)
                        if not m:
                            continue
                        phone = m.group(1)
                        # strip phone (and +91 prefix) from line \u2192 remaining text = name
                        name = _PHONE_RE.sub('', line).strip(' -|,;:\t')
                        leads.append({'name': name, 'phone': phone,
                                      'email': '', 'city': ''})
    except Exception as exc:
        return None, f"Could not parse PDF: {exc}"

    return leads, None


def _get_or_create_vapid_keys(db):
    """
    Return (private_scalar_b64url, public_b64url).
    Stores the raw 32-byte private key scalar as base64url — the format
    pywebpush accepts unconditionally across all versions.
    Any old PEM-based key is wiped and regenerated automatically.
    """
    if not PUSH_AVAILABLE:
        return None, None

    private_scalar = _get_setting(db, 'vapid_private_pem', '')   # reuse same DB key name
    public_b64     = _get_setting(db, 'vapid_public_key',  '')

    if private_scalar and public_b64:
        # If it looks like a PEM block (old format), wipe and regenerate
        if '-----' in private_scalar:
            app.logger.warning('[Push] Old PEM VAPID key detected — regenerating as raw scalar.')
            private_scalar = ''
            public_b64     = ''
            _set_setting(db, 'vapid_private_pem', '')
            _set_setting(db, 'vapid_public_key',  '')
            db.commit()
        else:
            return private_scalar, public_b64

    # Generate new P-256 key pair and store as raw base64url scalars
    private_key = ec.generate_private_key(ec.SECP256R1())

    # Private scalar: raw 32 bytes of the private key integer
    private_numbers = private_key.private_numbers()
    private_bytes_raw = private_numbers.private_value.to_bytes(32, 'big')
    private_scalar = base64.urlsafe_b64encode(private_bytes_raw).rstrip(b'=').decode()

    # Public key: uncompressed point (65 bytes), base64url-encoded
    pub_raw = private_key.public_key().public_bytes(
        _crypto_serial.Encoding.X962,
        _crypto_serial.PublicFormat.UncompressedPoint
    )
    public_b64 = base64.urlsafe_b64encode(pub_raw).rstrip(b'=').decode()

    _set_setting(db, 'vapid_private_pem', private_scalar)
    _set_setting(db, 'vapid_public_key',  public_b64)
    db.commit()
    app.logger.info('[Push] New VAPID key pair generated.')
    return private_scalar, public_b64


def _push_to_users(db, usernames, title, body, url='/'):
    """
    Send a Web Push notification to all subscriptions of the given usernames.
    Automatically removes dead (410/404) subscriptions.
    Fails silently \u2014 never breaks the calling route.
    """
    if not PUSH_AVAILABLE:
        return

    private_pem, _ = _get_or_create_vapid_keys(db)
    if not private_pem:
        return

    if isinstance(usernames, str):
        usernames = [usernames]

    payload   = json.dumps({'title': title, 'body': body, 'url': url})
    dead_ids  = []

    for username in usernames:
        subs = db.execute(
            "SELECT id, endpoint, auth, p256dh FROM push_subscriptions WHERE username=?",
            (username,)
        ).fetchall()
        for sub in subs:
            sub_info = {
                'endpoint': sub['endpoint'],
                'keys': {'auth': sub['auth'], 'p256dh': sub['p256dh']}
            }
            try:
                webpush(
                    subscription_info=sub_info,
                    data=payload,
                    vapid_private_key=private_pem,
                    vapid_claims={'sub': 'mailto:' + (_get_setting(db, 'smtp_user') or 'admin@mylecommunity.com')}
                )
            except Exception as exc:
                # 410 Gone / 404 Not Found \u2192 subscription expired, clean up
                resp = getattr(exc, 'response', None)
                if resp is not None and getattr(resp, 'status_code', 0) in (404, 410):
                    dead_ids.append(sub['id'])
                else:
                    app.logger.error(f'[Push] Send failed: {exc}')

    if dead_ids:
        ph = ','.join('?' for _ in dead_ids)
        db.execute(f"DELETE FROM push_subscriptions WHERE id IN ({ph})", dead_ids)
        db.commit()


def _push_all_team(db, title, body, url='/'):
    """Push to every approved team member."""
    rows = db.execute(
        "SELECT username FROM users WHERE role='team' AND status='approved'"
    ).fetchall()
    _push_to_users(db, [r['username'] for r in rows], title, body, url)


def _push_all_approved_users(db, title, body, url='/'):
    """Push to every approved user (admin, team, leader) who has registered browser subscriptions."""
    rows = db.execute(
        "SELECT username FROM users WHERE status='approved'"
    ).fetchall()
    _push_to_users(db, [r['username'] for r in rows], title, body, url)


def _send_welcome_email(user_email, username, login_url):
    """Send welcome email when a team member is approved. Silently skips if SMTP not configured."""
    db = get_db()
    smtp_host     = _get_setting(db, 'smtp_host', '')
    smtp_port     = int(_get_setting(db, 'smtp_port', '587') or 587)
    smtp_user     = _get_setting(db, 'smtp_user', '')
    smtp_password = _get_setting(db, 'smtp_password', '')
    from_name     = _get_setting(db, 'smtp_from_name', 'Myle Community')
    db.close()

    if not smtp_host or not smtp_user or not smtp_password or not user_email:
        return  # SMTP not configured, skip silently

    subject = 'Welcome to Myle Community \u2013 Account Approved!'

    html_body = f"""
    <div style="font-family:Arial,sans-serif;max-width:520px;margin:0 auto;background:#fff;border-radius:12px;overflow:hidden;border:1px solid #e0e0e0;">
      <div style="background:linear-gradient(135deg,#1a1a2e,#0f3460);padding:32px;text-align:center;">
        <h2 style="color:#fff;margin:0;font-size:22px;">Myle Community</h2>
        <p style="color:rgba(255,255,255,0.7);margin:8px 0 0;font-size:14px;">Team Dashboard</p>
      </div>
      <div style="padding:32px;">
        <h3 style="color:#1a1a2e;margin-top:0;">Hi {username}, your account is approved! \U0001f389</h3>
        <p style="color:#555;line-height:1.6;">
          Great news! Your registration request for <strong>Myle Community</strong> has been approved by the admin.
          You can now log in and access your dashboard.
        </p>
        <div style="background:#f0f4ff;border-radius:8px;padding:16px;margin:20px 0;border-left:4px solid #6366f1;">
          <p style="margin:0;color:#333;font-size:14px;"><strong>Username:</strong> {username}</p>
        </div>
        <div style="text-align:center;margin:28px 0;">
          <a href="{login_url}"
             style="background:linear-gradient(135deg,#6366f1,#8b5cf6);color:#fff;padding:14px 32px;border-radius:8px;text-decoration:none;font-weight:600;font-size:15px;display:inline-block;">
            Login to Dashboard &rarr;
          </a>
        </div>
        <p style="color:#888;font-size:13px;line-height:1.6;">
          From your dashboard you can:<br>
          &bull; View and manage your leads<br>
          &bull; Submit daily reports<br>
          &bull; Recharge wallet &amp; claim leads from pool
        </p>
      </div>
      <div style="background:#f8f9fa;padding:16px;text-align:center;border-top:1px solid #e0e0e0;">
        <p style="color:#aaa;font-size:12px;margin:0;">Myle Community &mdash; Internal Team Portal</p>
      </div>
    </div>
    """

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From']    = f'{from_name} <{smtp_user}>'
    msg['To']      = user_email
    msg.attach(MIMEText(html_body, 'html'))

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.ehlo()
            server.starttls(context=context)
            server.login(smtp_user, smtp_password)
            server.sendmail(smtp_user, user_email, msg.as_string())
        return True
    except Exception as e:
        app.logger.error(f'[Email] Welcome email failed: {e}')
        return False  # Don't break approval flow if email fails


def _send_password_reset_email(user_email, username, reset_url):
    """Send password reset link email. Silently skips if SMTP not configured."""
    db = get_db()
    smtp_host     = _get_setting(db, 'smtp_host', '')
    smtp_port     = int(_get_setting(db, 'smtp_port', '587') or 587)
    smtp_user     = _get_setting(db, 'smtp_user', '')
    smtp_password = _get_setting(db, 'smtp_password', '')
    from_name     = _get_setting(db, 'smtp_from_name', 'Myle Community')
    db.close()

    if not smtp_host or not smtp_user or not smtp_password or not user_email:
        return False  # SMTP not configured

    subject   = 'Myle Community \u2013 Password Reset Request'
    html_body = f"""
    <div style="font-family:Arial,sans-serif;max-width:520px;margin:auto;padding:24px;background:#f8f9fa;border-radius:12px;">
      <div style="background:linear-gradient(135deg,#6366f1,#8b5cf6);border-radius:8px;padding:20px;text-align:center;margin-bottom:24px;">
        <h2 style="color:#fff;margin:0;">\U0001f510 Password Reset</h2>
      </div>
      <p style="color:#333;">Hello <strong>{username}</strong>,</p>
      <p style="color:#555;">We received a request to reset your Myle Community dashboard password.
      Click the button below to set a new password. This link expires in <strong>1 hour</strong>.</p>
      <div style="text-align:center;margin:28px 0;">
        <a href="{reset_url}" style="background:linear-gradient(135deg,#6366f1,#8b5cf6);color:#fff;
           padding:12px 32px;border-radius:8px;text-decoration:none;font-weight:600;font-size:15px;">
          Reset My Password
        </a>
      </div>
      <p style="color:#999;font-size:0.8rem;">If you did not request this, you can safely ignore this email.
      Your password will not change.</p>
      <p style="color:#999;font-size:0.8rem;">Or copy this link: {reset_url}</p>
    </div>
    """

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From']    = f'{from_name} <{smtp_user}>'
    msg['To']      = user_email
    msg.attach(MIMEText(html_body, 'html'))

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.ehlo()
            server.starttls(context=context)
            server.login(smtp_user, smtp_password)
            server.sendmail(smtp_user, user_email, msg.as_string())
        return True
    except Exception as e:
        app.logger.error(f'[Email] Password reset email failed: {e}')
        return False




# ─────────────────────────────────────────────────
#  Enrollment / Watch routes (see routes/enrollment_routes.py)
# ─────────────────────────────────────────────────

# Shared helpers used by enrollment routes AND other parts of app.py
def _youtube_embed_url(raw_url):
    """Extract YouTube video ID from any common URL and return embed URL. Returns '' if not valid."""
    if not raw_url or not isinstance(raw_url, str):
        return ''
    s = raw_url.strip()
    # Support: watch?v=, youtu.be/, embed/, shorts/
    m = _re.search(
        # Also supports live stream URLs: youtube.com/live/<id>
        r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/|youtube\.com/shorts/|youtube\.com/live/)([a-zA-Z0-9_-]{11})',
        s
    )
    if m:
        vid = m.group(1)
        return 'https://www.youtube-nocookie.com/embed/' + vid + '?rel=0&modestbranding=1&playsinline=1'
    return ''


def _public_external_url(endpoint, **values):
    """Build stable absolute URLs behind proxies (Render/Cloudflare/Nginx)."""
    path = url_for(endpoint, _external=False, **values)
    try:
        proto = (request.headers.get('X-Forwarded-Proto') or request.scheme or 'https').split(',')[0].strip()
        host = (request.headers.get('X-Forwarded-Host') or request.host or '').split(',')[0].strip()
        if host:
            return f"{proto}://{host}{path}"
    except RuntimeError:
        pass
    return url_for(endpoint, _external=True, **values)


_BATCH_SLOTS = ('d1_morning', 'd1_afternoon', 'd1_evening', 'd2_morning', 'd2_afternoon', 'd2_evening')
_BATCH_LABELS = {
    'd1_morning': 'Day 1 — Morning Batch', 'd1_afternoon': 'Day 1 — Afternoon Batch', 'd1_evening': 'Day 1 — Evening Batch',
    'd2_morning': 'Day 2 — Morning Batch', 'd2_afternoon': 'Day 2 — Afternoon Batch', 'd2_evening': 'Day 2 — Evening Batch',
}


def _batch_watch_urls():
    """In-app watch URLs for each batch slot (v1, v2). Prospect opens our page, not YouTube."""
    return {
        slot: {'v1': _public_external_url('watch_batch', slot=slot, v=1),
               'v2': _public_external_url('watch_batch', slot=slot, v=2)}
        for slot in _BATCH_SLOTS
    }

# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
#  Template Filters
# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

@app.template_filter('wa_phone')
def wa_phone_filter(phone):
    """Clean phone number for WhatsApp wa.me link."""
    import re
    digits = re.sub(r'[^\d]', '', str(phone))
    if len(digits) == 10 and digits[0] in '6789':
        digits = '91' + digits          # Indian mobile \u2013 prepend country code
    elif digits.startswith('0') and len(digits) == 11:
        digits = '91' + digits[1:]      # 0XXXXXXXXXX \u2192 91XXXXXXXXXX
    return digits


@app.template_filter('team_status_opts')
def team_status_opts_filter(cur):
    """Per-lead status dropdown options for team (same list as Retarget)."""
    from helpers import team_status_dropdown_choices
    return team_status_dropdown_choices(cur or '')


@app.template_filter('team_status_selected')
def team_status_selected_filter(option, lead_status):
    """Selected state for team status <option> (New vs New Lead alias)."""
    from helpers import team_status_option_selected
    return team_status_option_selected(option or '', lead_status or '')


@app.template_filter('team_pipeline_readonly')
def team_pipeline_readonly_filter(st: str) -> bool:
    from helpers import team_my_leads_status_readonly
    return team_my_leads_status_readonly(st or '')


@app.template_filter('payment_proof_status')
def payment_proof_status_filter(row):
    """Same normalization as payment_proof_approval_status_value() — templates must match upload guard."""
    from helpers import payment_proof_approval_status_value
    if row is None:
        return 'pending'
    return payment_proof_approval_status_value(row)


def format_rupee_amount(value) -> str:
    """Format INR for UI/messages without integer rounding (%.0f turns 16.6 into 17)."""
    try:
        x = float(value if value is not None else 0)
    except (TypeError, ValueError):
        return '0'
    if abs(x - round(x)) < 1e-9:
        return str(int(round(x)))
    return f'{x:.2f}'.rstrip('0').rstrip('.')


@app.template_filter('rupee')
def rupee_filter(value):
    return format_rupee_amount(value)


# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
#  Context processor \u2013 inject counts for nav badges
# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

@app.context_processor
def inject_global_data():
    """
    Nav badges, header scores, and team/leader inactivity — one DB round-trip per render.

    Keep context processors minimal: do not load dashboard-sized datasets here; add route-level
    data instead. Optional burst cache: set MYLE_LAYOUT_CACHE_SEC=4 to repeat navigations.
    """
    empty = {
        'pending_count': 0,
        'wallet_pending': 0,
        'has_pending_work': False,
        'lost_count': 0,
        'lifetime_points': 0,
        'today_score': 0,
        'followup_count': 0,
    }
    if (
        request.path.startswith('/api/')
        or request.path.startswith('/static/')
        or request.is_json
    ):
        return empty
    uname = acting_username()
    role = session.get('role')
    if not uname:
        return empty

    try:
        _layout_ttl = float((os.environ.get('MYLE_LAYOUT_CACHE_SEC') or '0').strip() or 0)
    except ValueError:
        _layout_ttl = 0.0
    _layout_ck = (session.get('user_id'), role, uname)
    if _layout_ttl > 0:
        _cached = layout_metrics_cache_get(_layout_ck, _layout_ttl)
        if _cached is not None:
            return _cached

    db = get_db()
    try:
        inactivity_ctx = {}
        if 'user_id' in session and role in ('team', 'leader'):
            h = user_inactivity_hours(db, uname)
            esc = inactivity_escalation_days(db, uname)
            _uid = session.get('user_id')
            _active_leads = db.execute(
                """SELECT COUNT(*) FROM leads
                   WHERE (assigned_user_id=? OR current_owner=?) AND in_pool=0 AND deleted_at=''
                     AND status NOT IN ('Converted','Fully Converted','Lost','Retarget')""",
                (_uid, uname),
            ).fetchone()[0] or 0
            _can_pause = h >= INACTIVITY_BLOCK_CLAIM_HOURS and _active_leads > 0
            inactivity_ctx = {
                'user_inactivity_hours': round(h, 1),
                'inactivity_escalation_days': esc,
                'inactivity_show_warning': INACTIVITY_WARN_HOURS <= h < INACTIVITY_BLOCK_CLAIM_HOURS and _active_leads > 0,
                'inactivity_claim_blocked': INACTIVITY_BLOCK_CLAIM_HOURS <= h < INACTIVITY_LOCK_HOURS and _active_leads > 0,
                'inactivity_strong_warning': h >= INACTIVITY_LOCK_HOURS and _active_leads > 0,
                'inactivity_pool_claim_paused': _can_pause,
                'INACTIVITY_WARN_HOURS': INACTIVITY_WARN_HOURS,
                'INACTIVITY_BLOCK_CLAIM_HOURS': INACTIVITY_BLOCK_CLAIM_HOURS,
                'INACTIVITY_LOCK_HOURS': INACTIVITY_LOCK_HOURS,
            }

        user_row = db.execute("SELECT total_points FROM users WHERE username=?", (uname,)).fetchone()
        lifetime = user_row['total_points'] if user_row else 0

        today_date = _today_ist().isoformat()
        score_row = db.execute(
            "SELECT total_points FROM daily_scores WHERE username=? AND score_date=?",
            (uname, today_date),
        ).fetchone()
        t_score = score_row['total_points'] if score_row else 0

        pending_count = 0
        wallet_pending = 0
        has_pending_work = False
        lost_count = 0

        if role == 'admin':
            row = db.execute("""
                SELECT
                  (SELECT COUNT(*) FROM users           WHERE status='pending') as pu,
                  (SELECT COUNT(*) FROM wallet_recharges WHERE status='pending') as wp,
                  (SELECT COUNT(*) FROM leads WHERE in_pool=0 AND deleted_at='' AND status='Lost') as lc
            """).fetchone()
            pending_count = row['pu']
            wallet_pending = row['wp']
            lost_count = row['lc']
        else:
            _g_uid = user_id_for_username(db, uname)
            has_pending_work = (
                db.execute(
                    "SELECT COUNT(*) FROM leads "
                    "WHERE in_pool=0 AND deleted_at='' AND assigned_user_id=? AND status IN ('Day 1','Paid ₹196') AND d1_morning=0",
                    (_g_uid,),
                ).fetchone()[0]
                > 0
                if _g_uid is not None
                else False
            )

            if role == 'leader':
                downline = _get_downline_usernames(db, uname)
                if downline:
                    id_map = user_ids_for_usernames(db, downline)
                    dl_ids = [id_map[d] for d in downline if d in id_map]
                    if dl_ids:
                        ph = ','.join('?' * len(dl_ids))
                        lost_count = db.execute(
                            f"SELECT COUNT(*) FROM leads WHERE in_pool=0 AND deleted_at='' AND status='Lost' AND assigned_user_id IN ({ph})",
                            dl_ids,
                        ).fetchone()[0]
                    else:
                        lost_count = 0
            else:
                lost_count = (
                    db.execute(
                        "SELECT COUNT(*) FROM leads WHERE in_pool=0 AND deleted_at='' AND assigned_user_id=? AND status='Lost'",
                        (_g_uid,),
                    ).fetchone()[0]
                    if _g_uid is not None
                    else 0
                )

        now_date_ist_nav = _now_ist().strftime('%Y-%m-%d')
        followup_count_nav = 0
        if role == 'admin':
            # Only date-based overdue — call_result tags inflate count (every unanswered call
            # would count permanently until cleared, which is not actionable for admin)
            followup_count_nav = db.execute("""
                SELECT COUNT(*) FROM leads
                WHERE in_pool=0 AND deleted_at=''
                  AND status NOT IN ('Converted','Fully Converted','Lost','Retarget','Inactive')
                  AND follow_up_date != ''
                  AND DATE(follow_up_date) <= ?
            """, [now_date_ist_nav]).fetchone()[0]
        elif role in ('team', 'leader') and _g_uid is not None:
            # Same per-assignee overdue window as leaders: team must see their own follow-ups in nav.
            followup_count_nav = db.execute("""
                SELECT COUNT(*) FROM leads
                WHERE in_pool=0 AND deleted_at=''
                  AND assigned_user_id=?
                  AND status NOT IN ('Converted','Fully Converted','Lost','Retarget','Inactive')
                  AND follow_up_date != ''
                  AND DATE(follow_up_date) <= ?
            """, [_g_uid, now_date_ist_nav]).fetchone()[0]

        out = {
            'pending_count': pending_count,
            'wallet_pending': wallet_pending,
            'has_pending_work': has_pending_work,
            'lost_count': lost_count,
            'lifetime_points': lifetime,
            'today_score': t_score,
            'followup_count': int(followup_count_nav or 0),
        }
        out.update(inactivity_ctx)
        if _layout_ttl > 0:
            layout_metrics_cache_set(_layout_ck, out, _layout_ttl)
        return out
    except Exception as e:
        app.logger.error(f"inject_global_data() failed: {e}")
        return empty
    finally:
        db.close()


# ──────────────────────────────────────────────────────────────
#  CSRF Protection
# ──────────────────────────────────────────────────────────────

# Routes exempt from CSRF:
#   - /login, /register  → standalone pages (don't extend base.html, so the
#                          auto-inject JS never runs → form has no csrf_token)
_CSRF_EXEMPT_PREFIXES = ('/login', '/register')

# Local dev: bypass login — set DEV_BYPASS_AUTH=1 and open app → auto admin session
_DEV_BYPASS_AUTH = os.environ.get('DEV_BYPASS_AUTH', '').lower() in ('1', 'true', 'yes')


def _dev_bypass_blocked_on_hosting():
    """Never honor DEV_BYPASS_AUTH on known PaaS / prod-style runtimes (misconfig safety)."""
    return bool(
        os.environ.get('RENDER')
        or os.environ.get('DYNO')  # Heroku
        or os.environ.get('VERCEL')
        or os.environ.get('RAILWAY_ENVIRONMENT')
        or os.environ.get('K_SERVICE')  # Google Cloud Run
        or os.environ.get('AWS_EXECUTION_ENV')  # Lambda / some AWS hosts
    )


@app.before_request
def dev_bypass_auth():
    """Allow auth bypass only for localhost development."""
    if not _DEV_BYPASS_AUTH or session.get('user_id'):
        return
    if _dev_bypass_blocked_on_hosting():
        return
    _dbg = (os.environ.get('FLASK_DEBUG') or '').lower() in ('1', 'true', 'yes')
    is_dev = os.environ.get('FLASK_ENV', '').lower() == 'development' or _dbg
    remote = (request.remote_addr or '').strip()
    if not is_dev or remote not in ('127.0.0.1', '::1'):
        return
    if request.path.startswith('/static') or request.path.startswith('/watch/'):
        return
    db = get_db()
    try:
        row = db.execute(
            """SELECT id, username, fbo_id, role, display_picture, training_status,
                      COALESCE(NULLIF(TRIM(name), ''), username) AS display_name
               FROM users WHERE role='admin' ORDER BY id LIMIT 1"""
        ).fetchone()
        if not row:
            return
        session.clear()
        session.permanent = True
        session['user_id'] = row['id']
        session['username'] = row['username']
        session['fbo_id'] = (row['fbo_id'] or '').strip() or (row['username'] or '').strip()
        session['role'] = row['role']
        session['has_dp'] = bool(row['display_picture']) if 'display_picture' in row.keys() else False
        _k = row.keys()
        session['training_status'] = (
            row['training_status'] if 'training_status' in _k else 'not_required'
        )
        session['display_name'] = row['display_name'] if 'display_name' in _k else row['username']
        session['auth_version'] = AUTH_SESSION_VERSION
        session['_csrf_token'] = secrets.token_hex(32)
    finally:
        db.close()


@app.before_request
def csrf_protect():
    """Generate a CSRF token for the session and validate it on unsafe methods."""
    # Always ensure a token exists in the session
    if '_csrf_token' not in session:
        session['_csrf_token'] = secrets.token_hex(32)

    # Only validate on state-changing methods
    if request.method in ('GET', 'HEAD', 'OPTIONS', 'TRACE'):
        return

    # Exempt external webhook endpoints (they use their own HMAC signature)
    if any(request.path.startswith(p) for p in _CSRF_EXEMPT_PREFIXES):
        return

    submitted = (
        request.form.get('csrf_token') or
        request.headers.get('X-CSRF-Token')
    )
    if not submitted or not hmac.compare_digest(submitted, session.get('_csrf_token', '')):
        abort(403, description='CSRF token missing or invalid. Please refresh and try again.')


@app.before_request
def maintenance_mode_guard():
    """
    Maintenance safety: block state writes for claim/update/payment routes.
    View routes remain available.
    """
    if request.method in ('GET', 'HEAD', 'OPTIONS', 'TRACE'):
        return
    if request.path.startswith('/static'):
        return
    if session.get('role') == 'admin':
        return
    db = get_db()
    try:
        mm = (_get_setting(db, 'maintenance_mode', '0') or '').strip().lower()
    finally:
        db.close()
    if mm not in ('1', 'true', 'on', 'yes'):
        return
    blocked = (
        request.path.startswith('/lead-pool/claim')
        or request.path.startswith('/leads/')
        or request.path.startswith('/wallet/request-recharge')
    )
    if not blocked:
        return
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'ok': False, 'error': 'Maintenance mode: write actions are temporarily disabled.'}), 503
    flash('Maintenance mode active: claim/update/payment actions are temporarily disabled.', 'warning')
    return redirect(request.referrer or url_for('team_dashboard'))


@app.context_processor
def inject_csrf_token():
    """Make csrf_token available to every template."""
    return {'csrf_token': session.get('_csrf_token', '')}


# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
#  Global Error Handlers
# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

@app.errorhandler(403)
def handle_403(e):
    """CSRF / forbidden — keep session; stale tabs often trigger CSRF mismatch."""
    desc = (getattr(e, 'description', None) or str(e) or '').strip()
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
        return {'ok': False, 'error': desc or 'Forbidden'}, 403
    if 'csrf' in desc.lower():
        flash(
            'Session / form out of date. Refresh this page (pull down or F5), then try again.',
            'warning',
        )
    else:
        flash(desc or 'This action was blocked. Refresh and try again.', 'danger')
    role = session.get('role')
    ref = request.referrer
    if role == 'leader' and ref:
        return redirect(ref)
    if role == 'leader':
        return redirect(url_for('leader_dashboard'))
    if role == 'admin' and ref:
        return redirect(ref)
    if role == 'admin':
        return redirect(url_for('admin_dashboard'))
    if role in ('team',) and ref:
        return redirect(ref)
    if role == 'team':
        return redirect(url_for('team_dashboard'))
    return redirect(url_for('login'))


@app.errorhandler(404)
def handle_404(e):
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
        return {'ok': False, 'error': 'Page not found'}, 404
    flash('Page not found.', 'warning')
    role = session.get('role')
    if role == 'leader':
        return redirect(url_for('leader_dashboard'))
    elif role == 'team':
        return redirect(url_for('team_dashboard'))
    elif role == 'admin':
        return redirect(url_for('admin_dashboard'))
    return redirect(url_for('login'))


@app.errorhandler(500)
def internal_error(error):
    import traceback as _tb
    app.logger.error(f"500 Error: {error}\n{_tb.format_exc()}")
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
        return {'ok': False, 'error': 'Server error, please try again'}, 500
    return render_template('500.html'), 500


@app.errorhandler(Exception)
def unhandled_exception(error):
    if isinstance(error, HTTPException):
        return error
    import traceback as _tb
    app.logger.error(f"Unhandled exception: {error}\n{_tb.format_exc()}")
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
        return {'ok': False, 'error': 'Something went wrong'}, 500
    return render_template('500.html'), 500


# ──────────────────────────────────────────────────────────────────────────
#  Register / Login / Logout / Password reset (see routes/auth_routes.py)
# ──────────────────────────────────────────────────────────────────────────

from routes.auth_routes import register_auth_routes

register_auth_routes(app)

from routes.webhook_routes import register_webhook_routes
from routes.misc_routes import register_misc_routes
from routes.profile_routes import register_profile_routes
from routes.social_routes import register_social_routes
from routes.wallet_routes import register_wallet_routes
from routes.enrollment_routes import register_enrollment_routes
from routes.training_routes import register_training_routes
from routes.report_routes import register_report_routes
from routes.tasks_routes import register_tasks_routes
from routes.ai_routes import register_ai_routes
from routes.approvals_routes import register_approvals_routes
from routes.team_routes import register_team_routes
from routes.lead_routes import register_lead_routes
from routes.lead_pool_routes import register_lead_pool_routes
from routes.progression_routes import register_progression_routes
from routes.day2_test_routes import register_day2_test_routes

register_webhook_routes(app)
register_misc_routes(app)
register_profile_routes(app)
register_social_routes(app)
register_wallet_routes(app)
register_enrollment_routes(app)
register_training_routes(app)
register_report_routes(app)
register_tasks_routes(app)
register_ai_routes(app)
register_approvals_routes(app)
register_team_routes(app)
register_lead_routes(app)
register_lead_pool_routes(app)
register_progression_routes(app)
register_day2_test_routes(app)
@app.route('/leader/home')
@login_required
def leader_dashboard():
    """Safe fallback for leader — no @safe_route so it cannot self-loop."""
    if session.get('role') not in ('leader', 'admin'):
        return redirect(url_for('team_dashboard'))
    # Downline control + pipeline lives on main dashboard (execution-first).
    return redirect(url_for('team_dashboard'))


@app.route('/')
@login_required
def index():
    if session.get('role') == 'admin':
        return redirect(url_for('admin_dashboard'))
    if session.get('role') == 'leader':
        return redirect(url_for('leader_dashboard'))
    return redirect(url_for('team_dashboard'))


# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
#  Admin Dashboard
# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

@app.route('/admin')
@admin_required
@safe_route
def admin_dashboard():
    db      = get_db()

    # Check seat hold expiry for all team/leader members
    seat_hold_users = db.execute(
        "SELECT username FROM users WHERE role IN ('team','leader') AND status='approved'"
    ).fetchall()
    for u in seat_hold_users:
        _check_seat_hold_expiry(db, u['username'])

    metrics = _get_metrics(db)
    _today_d = _today_ist()
    today   = _today_d.isoformat()
    cur_ym = _today_d.strftime('%Y-%m')
    _rm_raw = (request.args.get('report_month') or '').strip()
    if len(_rm_raw) == 7 and _rm_raw[4] == '-' and _rm_raw[:4].isdigit() and _rm_raw[5:7].isdigit():
        try:
            _ry, _rmm = int(_rm_raw[:4]), int(_rm_raw[5:7])
            report_month = f'{_ry:04d}-{_rmm:02d}' if 1 <= _rmm <= 12 else cur_ym
        except ValueError:
            report_month = cur_ym
    else:
        report_month = cur_ym
    if report_month > cur_ym:
        report_month = cur_ym
    _rym = int(report_month[:4])
    _rmm = int(report_month[5:7])
    ms_start = f'{_rym:04d}-{_rmm:02d}-01'
    _ms_last = calendar.monthrange(_rym, _rmm)[1]
    ms_end = today if report_month == cur_ym else f'{_rym:04d}-{_rmm:02d}-{_ms_last:02d}'
    month_label = datetime.date(_rym, _rmm, 1).strftime('%B %Y')
    month_options = []
    _oy, _om = _today_d.year, _today_d.month
    for _ in range(24):
        month_options.append(f'{_oy:04d}-{_om:02d}')
        _om -= 1
        if _om < 1:
            _om = 12
            _oy -= 1
    # Read-only dashboard: single base filter for pipeline buckets + today metrics (display only)
    _base_w = "deleted_at='' AND in_pool=0"

    # ── 1. Live Pipeline Funnel (current leads at each stage) ────────
    pipeline = db.execute(f"""
        SELECT
            SUM(CASE WHEN status IN ('New Lead','New','Contacted','Invited',
                         'Video Sent','Video Watched') THEN 1 ELSE 0 END) AS prospecting,
            SUM(CASE WHEN status='Paid \u20b9196' THEN 1 ELSE 0 END) AS enrolled,
            SUM(CASE WHEN status='Day 1'       THEN 1 ELSE 0 END) AS day1,
            SUM(CASE WHEN status='Day 2'       THEN 1 ELSE 0 END) AS day2,
            SUM(CASE WHEN status IN ('Interview','Track Selected') THEN 1 ELSE 0 END) AS day3,
            SUM(CASE WHEN status='2cc Plan'    THEN 1 ELSE 0 END) AS plan_2cc,
            SUM(CASE WHEN status='Seat Hold Confirmed' THEN 1 ELSE 0 END) AS seat_hold,
            SUM(CASE WHEN status='Pending'     THEN 1 ELSE 0 END) AS pending_as,
            SUM(CASE WHEN status='Level Up'    THEN 1 ELSE 0 END) AS level_up,
            SUM(CASE WHEN status IN ('Fully Converted','Converted') THEN 1 ELSE 0 END) AS converted
        FROM leads WHERE {_base_w}
    """).fetchone()
    pipeline = dict(pipeline) if pipeline else {}
    for k in ('prospecting','enrolled','day1','day2','day3','plan_2cc','seat_hold','pending_as','level_up','converted'):
        pipeline[k] = pipeline.get(k) or 0

    # IST calendar day from stored wall-clock datetimes (must match _now_ist() writes)
    _ts = sql_ts_calendar_day()
    _ts_l = sql_ts_calendar_day("l.updated_at")
    _ts_claim = sql_ts_calendar_day("l.claimed_at")
    _ts_claimed_at = sql_ts_calendar_day("claimed_at")
    _trend_start = (_today_d - datetime.timedelta(days=6)).isoformat()

    _approved_team = (
        "EXISTS (SELECT 1 FROM users u WHERE u.id = l.assigned_user_id "
        "AND u.role IN ('team','leader') AND u.status='approved')"
    )

    # ── Daily core KPIs (SSOT via get_today_metrics)
    _today_m = get_today_metrics(db, day_iso=today, approved_only=True)
    kpi_today_claimed = _today_m['claimed']
    kpi_today_enrolled = _today_m['enrolled']
    kpi_today_enrolled_amount = db.execute(
        f"""
        SELECT COALESCE(SUM(COALESCE(payment_amount, 0)), 0) FROM leads l
        WHERE {_base_w}
          AND TRIM(COALESCE(l.enrolled_at,'')) != ''
          AND date(substr(trim(COALESCE(l.enrolled_at,'')),1,10)) = date(?)
          AND TRIM(COALESCE(l.payment_proof_path,'')) != ''
          AND LOWER(COALESCE(l.payment_proof_approval_status,'')) = 'approved'
          AND {_approved_team}
        """,
        (today,),
    ).fetchone()[0] or 0

    _base_l = "l.deleted_at='' AND l.in_pool=0"
    admin_month_claimed = db.execute(
        f"""
        SELECT COUNT(*) FROM leads l
        WHERE {_base_l}
          AND l.claimed_at IS NOT NULL AND TRIM(COALESCE(l.claimed_at,''))!=''
          AND {_ts_claim} >= date(?) AND {_ts_claim} <= date(?)
          AND {_approved_team}
        """,
        (ms_start, ms_end),
    ).fetchone()[0] or 0
    admin_month_enrolled = db.execute(
        f"""
        SELECT COUNT(*) FROM leads l
        WHERE {_base_l}
          AND TRIM(COALESCE(l.enrolled_at,'')) != ''
          AND date(substr(trim(COALESCE(l.enrolled_at,'')),1,10)) >= date(?)
          AND date(substr(trim(COALESCE(l.enrolled_at,'')),1,10)) <= date(?)
          AND TRIM(COALESCE(l.payment_proof_path,'')) != ''
          AND LOWER(COALESCE(l.payment_proof_approval_status,'')) = 'approved'
          AND {_approved_team}
        """,
        (ms_start, ms_end),
    ).fetchone()[0] or 0

    # Read-only month-end summary (wallet + pipeline snapshot + stage history counts)
    month_wallet_recharged = db.execute(
        """
        SELECT COALESCE(SUM(w.amount), 0) FROM wallet_recharges w
        INNER JOIN users u ON u.username = w.username
        WHERE w.status = 'approved'
          AND TRIM(COALESCE(w.processed_at,'')) != ''
          AND u.role IN ('team', 'leader') AND u.status = 'approved'
          AND strftime('%Y-%m', w.processed_at) = ?
        """,
        (report_month,),
    ).fetchone()[0] or 0
    month_pipeline_budget = db.execute(
        """
        SELECT COALESCE(SUM(
            CASE
                WHEN l.pipeline_stage IN ('closing', 'complete') THEN COALESCE(l.track_price, 0)
                WHEN l.pipeline_stage IN ('seat_hold', 'pending', 'level_up')
                    THEN COALESCE(l.seat_hold_amount, 0)
                ELSE 0
            END
        ), 0)
        FROM leads l
        INNER JOIN users u ON u.id = l.assigned_user_id
        WHERE l.deleted_at = '' AND l.in_pool = 0
          AND u.role IN ('team', 'leader') AND u.status = 'approved'
          AND substr(trim(COALESCE(l.updated_at,'')), 1, 7) = ?
        """,
        (report_month,),
    ).fetchone()[0] or 0
    _hist = db.execute(
        f"""
        SELECT
            COUNT(DISTINCT CASE WHEN lsh.stage = 'day1' THEN lsh.lead_id END) AS h_day1,
            COUNT(DISTINCT CASE WHEN lsh.stage = 'day2' THEN lsh.lead_id END) AS h_day2,
            COUNT(DISTINCT CASE WHEN lsh.stage IN ('seat_hold', 'plan_2cc') THEN lsh.lead_id END) AS h_seat_track,
            COUNT(DISTINCT CASE WHEN lsh.stage IN ('closing', 'complete') THEN lsh.lead_id END) AS h_final
        FROM lead_stage_history lsh
        INNER JOIN leads l ON l.id = lsh.lead_id AND l.deleted_at = '' AND l.in_pool = 0
        INNER JOIN users u ON u.id = l.assigned_user_id
            AND u.role IN ('team', 'leader') AND u.status = 'approved'
        WHERE date(lsh.created_at) >= date(?) AND date(lsh.created_at) <= date(?)
        """,
        (ms_start, ms_end),
    ).fetchone()
    month_stage_history = {
        'day1': (_hist['h_day1'] or 0) if _hist else 0,
        'day2': (_hist['h_day2'] or 0) if _hist else 0,
        'seat_track': (_hist['h_seat_track'] or 0) if _hist else 0,
        'final_close': (_hist['h_final'] or 0) if _hist else 0,
    }

    _ph_en = ','.join('?' * len(ADMIN_PIPELINE_BUCKET_ENROLLMENT))
    _ph_tr = ','.join('?' * len(ADMIN_PIPELINE_BUCKET_TRAINING))
    _ph_cl = ','.join('?' * len(ADMIN_PIPELINE_BUCKET_CLOSING))
    _pb_row = db.execute(
        f"""
        SELECT
            SUM(CASE WHEN status IN ({_ph_en}) THEN 1 ELSE 0 END) AS bucket_enrollment,
            SUM(CASE WHEN status IN ({_ph_tr}) THEN 1 ELSE 0 END) AS bucket_training,
            SUM(CASE WHEN status IN ({_ph_cl}) THEN 1 ELSE 0 END) AS bucket_closing
        FROM leads WHERE {_base_w}
        """,
        (*ADMIN_PIPELINE_BUCKET_ENROLLMENT, *ADMIN_PIPELINE_BUCKET_TRAINING, *ADMIN_PIPELINE_BUCKET_CLOSING),
    ).fetchone()
    pipeline_buckets = {
        'enrollment': (_pb_row['bucket_enrollment'] or 0) if _pb_row else 0,
        'training': (_pb_row['bucket_training'] or 0) if _pb_row else 0,
        'closing': (_pb_row['bucket_closing'] or 0) if _pb_row else 0,
    }

    pipeline_value = db.execute(
        f"SELECT COALESCE(SUM(track_price),0) FROM leads WHERE {_base_w} "
        "AND status IN ('Seat Hold Confirmed','Track Selected')"
    ).fetchone()[0] or 0

    # ── 2. Today's Pulse ─────────────────────────────────────────────
    approved_members = db.execute(
        "SELECT username, fbo_id FROM users WHERE role IN ('team','leader') AND status='approved' "
        "AND IFNULL(idle_hidden, 0) = 0 ORDER BY username"
    ).fetchall()
    today_reports = db.execute(
        "SELECT * FROM daily_reports WHERE report_date=? ORDER BY submitted_at DESC",
        (today,)
    ).fetchall()
    submitted_set   = {r['username'] for r in today_reports}
    missing_reports = [u['username'] for u in approved_members
                       if u['username'] not in submitted_set]

    _d1_total = db.execute(f"SELECT COUNT(*) FROM leads WHERE {_base_w} AND status='Day 1'").fetchone()[0] or 0
    _d1_done  = db.execute(f"SELECT COUNT(*) FROM leads WHERE {_base_w} AND status='Day 1' AND d1_morning=1 AND d1_afternoon=1 AND d1_evening=1").fetchone()[0] or 0
    _d2_total = db.execute(f"SELECT COUNT(*) FROM leads WHERE {_base_w} AND status='Day 2'").fetchone()[0] or 0
    _d2_done  = db.execute(f"SELECT COUNT(*) FROM leads WHERE {_base_w} AND status='Day 2' AND d2_morning=1 AND d2_afternoon=1 AND d2_evening=1").fetchone()[0] or 0

    stale_cutoff = (_now_ist() - datetime.timedelta(hours=48)).strftime('%Y-%m-%d %H:%M:%S')
    _stale_w = _base_w.replace("deleted_at", "l.deleted_at").replace("in_pool", "l.in_pool")
    stale_leads = db.execute(
        f"""
        SELECT l.id, l.name, l.phone, l.status, l.updated_at,
               COALESCE(NULLIF(TRIM(u.name),''), u.username, '') AS assignee_display
        FROM leads l
        LEFT JOIN users u ON u.id = l.assigned_user_id
        WHERE {_stale_w}
        AND l.assigned_user_id IS NOT NULL
        AND l.status NOT IN ('Fully Converted','Converted','Lost','Seat Hold Confirmed')
        AND l.updated_at < ? ORDER BY l.updated_at ASC LIMIT 20
        """,
        (stale_cutoff,),
    ).fetchall()

    pulse = {
        'reports_done':    len(today_reports),
        'reports_total':   len(approved_members),
        # distinct leads with a valid call_status logged today (per get_today_metrics SSOT)
        'total_calls':     _today_m['calls'],
        'payments_count':  kpi_today_enrolled,
        'payments_amount': kpi_today_enrolled_amount,
        'batch_d1_done':   _d1_done, 'batch_d1_total': _d1_total,
        'batch_d1_pct':    round(_d1_done / _d1_total * 100) if _d1_total else 0,
        'batch_d2_done':   _d2_done, 'batch_d2_total': _d2_total,
        'batch_d2_pct':    round(_d2_done / _d2_total * 100) if _d2_total else 0,
        'stale_count':     len(stale_leads),
    }

    # ── 3. Team Leaderboard ──────────────────────────────────────────
    _verif_rows = db.execute(f"""
        SELECT COALESCE(u.username, '') AS username, COUNT(*) as cnt
        FROM leads l
        LEFT JOIN users u ON u.id = l.assigned_user_id
        WHERE COALESCE(l.payment_done,0)=1
          AND l.status = 'Paid \u20b9196'
          AND {_ts_l} = date(?) AND l.deleted_at='' AND l.in_pool=0
        GROUP BY l.assigned_user_id, u.username
    """, (today,)).fetchall()
    report_verification = {r['username']: r['cnt'] for r in _verif_rows if r['username']}

    _s1_ph = ','.join('?' * len(STAGE1_STATUSES))
    team_board = []
    _tb_unames = [m['username'] for m in approved_members]
    _tb_id_map = user_ids_for_usernames(db, _tb_unames) if _tb_unames else {}
    _tb_uids = [_tb_id_map[u] for u in _tb_unames if u in _tb_id_map]

    _tb_score = {}
    _tb_streak = {}
    if _tb_unames:
        _tb_ph = ','.join('?' * len(_tb_unames))
        for _sr in db.execute(
            f"SELECT username, total_points, streak_days FROM daily_scores "
            f"WHERE score_date=? AND username IN ({_tb_ph})",
            (today, *_tb_unames),
        ).fetchall():
            _tb_score[_sr['username']] = int(_sr['total_points'] or 0)
            _tb_streak[_sr['username']] = int(_sr['streak_days'] or 1)

    _tb_counts_by_uid = {}
    if _tb_uids:
        _tb_uid_ph = ','.join('?' * len(_tb_uids))
        _tb_agg = f"""
            SELECT assigned_user_id,
                SUM(CASE WHEN status IN ({_s1_ph}) THEN 1 ELSE 0 END) AS stage1,
                SUM(CASE WHEN status='Day 1' THEN 1 ELSE 0 END) AS day1,
                SUM(CASE WHEN status='Day 2' THEN 1 ELSE 0 END) AS day2,
                SUM(CASE WHEN status IN ('Interview','Track Selected') THEN 1 ELSE 0 END) AS day3,
                SUM(CASE WHEN status='Seat Hold Confirmed' THEN 1 ELSE 0 END) AS pending,
                SUM(CASE WHEN status IN ('Fully Converted','Converted') THEN 1 ELSE 0 END) AS converted,
                COUNT(*) AS total,
                SUM(CASE WHEN status='Day 1' AND d1_morning=1 AND d1_afternoon=1 AND d1_evening=1
                    THEN 1 ELSE 0 END) AS d1_done,
                SUM(CASE WHEN status='Day 2' AND d2_morning=1 AND d2_afternoon=1 AND d2_evening=1
                    THEN 1 ELSE 0 END) AS d2_done
            FROM leads
            WHERE assigned_user_id IN ({_tb_uid_ph}) AND {_base_w}
            GROUP BY assigned_user_id
        """
        for _cr in db.execute(_tb_agg, (*STAGE1_STATUSES, *_tb_uids)).fetchall():
            _tb_counts_by_uid[int(_cr['assigned_user_id'])] = _cr

    for m in approved_members:
        uname = m['username']
        if uname not in _tb_id_map:
            continue
        _abm_uid = _tb_id_map[uname]
        score_pts = _tb_score.get(uname, 0)
        streak = _tb_streak.get(uname, 1)
        _cr = _tb_counts_by_uid.get(int(_abm_uid))
        if _cr:
            _m_d1_total = int(_cr['day1'] or 0)
            _m_d2_total = int(_cr['day2'] or 0)
            _m_d1_done = int(_cr['d1_done'] or 0)
            _m_d2_done = int(_cr['d2_done'] or 0)
            _m_batch_total = _m_d1_total + _m_d2_total
            _m_batch_done = _m_d1_done + _m_d2_done
            batch_pct = round(_m_batch_done / _m_batch_total * 100) if _m_batch_total else -1
            team_board.append({
                'username': uname, 'fbo_id': m['fbo_id'] or '',
                'score': score_pts, 'streak': streak,
                'stage1': int(_cr['stage1'] or 0), 'day1': _m_d1_total, 'day2': _m_d2_total,
                'day3': int(_cr['day3'] or 0),
                'pending': int(_cr['pending'] or 0), 'converted': int(_cr['converted'] or 0),
                'total': int(_cr['total'] or 0),
                'batch_pct': batch_pct,
                'report_done': uname in submitted_set,
            })
        else:
            team_board.append({
                'username': uname, 'fbo_id': m['fbo_id'] or '',
                'score': score_pts, 'streak': streak,
                'stage1': 0, 'day1': 0, 'day2': 0, 'day3': 0,
                'pending': 0, 'converted': 0, 'total': 0,
                'batch_pct': -1,
                'report_done': uname in submitted_set,
            })
    team_board.sort(key=lambda x: x['score'], reverse=True)

    # ── 4. Recent Live Activity ───────────────────────────────────────
    _stage_acts = db.execute(f"""
        SELECT lsh.created_at, 'stage' AS type,
               COALESCE(l.name,'Unknown') AS lead_name, lsh.lead_id,
               lsh.stage, lsh.triggered_by AS actor
        FROM lead_stage_history lsh
        LEFT JOIN leads l ON l.id = lsh.lead_id
        WHERE lsh.lead_id IN (SELECT id FROM leads WHERE {_base_w})
        ORDER BY lsh.created_at DESC LIMIT 12
    """).fetchall()
    _new_acts = db.execute(f"""
        SELECT l.created_at, 'new_lead' AS type,
               COALESCE(l.name,'Unknown') AS lead_name, l.id AS lead_id,
               l.status AS stage,
               COALESCE(NULLIF(TRIM(u.name),''), u.username, '') AS actor
        FROM leads l
        LEFT JOIN users u ON u.id = l.assigned_user_id
        WHERE l.deleted_at='' AND l.in_pool=0
        AND l.created_at >= datetime('now', '+5 hours', '+30 minutes', '-7 days')
        ORDER BY l.created_at DESC LIMIT 6
    """).fetchall()
    _pay_acts = db.execute(f"""
        SELECT l.updated_at AS created_at, 'payment' AS type,
               COALESCE(l.name,'Unknown') AS lead_name, l.id AS lead_id,
               l.status AS stage,
               COALESCE(NULLIF(TRIM(u.name),''), u.username, '') AS actor
        FROM leads l
        LEFT JOIN users u ON u.id = l.assigned_user_id
        WHERE l.deleted_at='' AND l.in_pool=0 AND l.payment_done=1
        AND l.updated_at >= datetime('now', '+5 hours', '+30 minutes', '-7 days')
        ORDER BY l.updated_at DESC LIMIT 6
    """).fetchall()
    _all_acts = [dict(r) for r in list(_stage_acts) + list(_new_acts) + list(_pay_acts)]
    _all_acts.sort(key=lambda x: x.get('created_at') or '', reverse=True)
    recent_activity = _all_acts[:12]

    _sc = db.execute(
        f"SELECT status, COUNT(*) as c FROM leads WHERE {_base_w} GROUP BY status"
    ).fetchall()
    status_data = {s: 0 for s in STATUSES}
    for row in _sc:
        if row['status'] in status_data:
            status_data[row['status']] = row['c']

    monthly = db.execute(f"""
        SELECT strftime('%Y-%m', created_at) as month,
               SUM(payment_amount) as total
        FROM leads
        WHERE payment_done=1 AND {_base_w}
        GROUP BY month ORDER BY month DESC LIMIT 6
    """).fetchall()

    pending_users = db.execute(
        "SELECT * FROM users WHERE status='pending' ORDER BY created_at DESC"
    ).fetchall()

    wallet_pending_count = db.execute(
        "SELECT COUNT(*) FROM wallet_recharges WHERE status='pending'"
    ).fetchone()[0]

    pending_proof_count = db.execute(
        """
        SELECT COUNT(*) FROM leads l
        JOIN users u ON u.id = l.assigned_user_id
        WHERE l.in_pool=0 AND l.deleted_at=''
          AND LOWER(COALESCE(l.payment_proof_approval_status,''))='pending'
          AND TRIM(COALESCE(l.payment_proof_path,''))!=''
          AND u.status='approved'
        """
    ).fetchone()[0]

    pool_count = db.execute("SELECT COUNT(*) FROM leads WHERE in_pool=1").fetchone()[0]

    # ── 5. Daily conversion trend (7 days) ───────────────────────────
    daily_trend = db.execute(f"""
        SELECT {_ts} AS d,
               SUM(CASE WHEN status IN ('Converted','Fully Converted') THEN 1 ELSE 0 END) AS conversions,
               SUM(CASE WHEN payment_done=1 THEN 1 ELSE 0 END) AS payments
        FROM leads WHERE {_base_w} AND {_ts} >= date(?)
        GROUP BY d ORDER BY d
    """, (_trend_start,)).fetchall()

    step7_pressure = None
    try:
        _s7 = _get_setting(db, 'step7_daily_pressure_json', '')
        if _s7:
            step7_pressure = json.loads(_s7)
    except Exception:
        step7_pressure = None
    system_auto_actions = db.execute(
        """
        SELECT event_type, target_username, reason, created_at
        FROM system_auto_actions
        ORDER BY id DESC
        LIMIT 15
        """
    ).fetchall()

    step8_admin_ai_lines = build_step8_admin_ai_lines(db, today)
    _now_loc_ad = _now_ist().replace(tzinfo=None)
    step8_admin_evening = ''
    if _now_loc_ad.hour >= 21:
        step8_admin_evening = (
            f'Evening snapshot date {today}: review REMOVE/CRITICAL rows below — human executes.'
        )

    _today_iso_dh = _today_ist().isoformat()
    data_health = {
        'bad_payment': db.execute(
            """SELECT COUNT(*) FROM leads WHERE deleted_at='' AND in_pool=0
               AND payment_done=1 AND (payment_amount IS NULL OR payment_amount <= 0)"""
        ).fetchone()[0]
        or 0,
        'updated_not_today': db.execute(
            """SELECT COUNT(*) FROM leads WHERE deleted_at='' AND in_pool=0
               AND (updated_at IS NULL OR TRIM(COALESCE(updated_at,''))=''
                    OR substr(updated_at,1,10) != ?)""",
            (_today_iso_dh,),
        ).fetchone()[0]
        or 0,
        'bad_seat': db.execute(
            """SELECT COUNT(*) FROM leads WHERE deleted_at='' AND in_pool=0
               AND status='Seat Hold Confirmed' AND COALESCE(seat_hold_amount,0) <= 0"""
        ).fetchone()[0]
        or 0,
        'bad_track': db.execute(
            """SELECT COUNT(*) FROM leads WHERE deleted_at='' AND in_pool=0
               AND status='Fully Converted' AND COALESCE(track_price,0) <= 0"""
        ).fetchone()[0]
        or 0,
    }

    db.close()
    resp = make_response(render_template('admin.html',
                           metrics=metrics,
                           pipeline=pipeline,
                           pipeline_buckets=pipeline_buckets,
                           kpi_today_claimed=kpi_today_claimed,
                           kpi_today_enrolled=kpi_today_enrolled,
                           kpi_today_enrolled_amount=kpi_today_enrolled_amount,
                           admin_month_claimed=admin_month_claimed,
                           admin_month_enrolled=admin_month_enrolled,
                           month_label=month_label,
                           report_month=report_month,
                           month_options=month_options,
                           month_wallet_recharged=month_wallet_recharged,
                           month_pipeline_budget=month_pipeline_budget,
                           month_stage_history=month_stage_history,
                           month_range_end=ms_end,
                           ms_start=ms_start,
                           report_month_is_current=(report_month == cur_ym),
                           pipeline_value=pipeline_value,
                           pulse=pulse,
                           team_board=team_board,
                           stale_leads=stale_leads,
                           recent_activity=recent_activity,
                           status_data=status_data,
                           monthly=monthly,
                           daily_trend=daily_trend,
                           pending_users=pending_users,
                           payment_amount=PAYMENT_AMOUNT,
                           today_reports=today_reports,
                           missing_reports=missing_reports,
                           report_verification=report_verification,
                           today=today,
                           pending_proof_count=pending_proof_count,
                           wallet_pending_count=wallet_pending_count,
                           pool_count=pool_count,
                           step7_pressure=step7_pressure,
                           system_auto_actions=system_auto_actions,
                           data_health=data_health,
                           step8_admin_ai_lines=step8_admin_ai_lines,
                           step8_admin_evening=step8_admin_evening))
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate'
    return resp


@app.route('/admin/at-risk-leads')
@admin_required
@safe_route
def admin_at_risk_leads():
    """48h+ stale active leads — assignee, leader, proof state, days stuck."""
    from execution_enforcement import admin_at_risk_leads as _at_risk

    db = get_db()
    rows = _at_risk(db, stale_hours=48, limit=500)
    db.close()
    return render_template(
        'admin_at_risk_leads.html',
        rows=rows,
        today=_today_ist().isoformat(),
        csrf_token=session.get('_csrf_token', ''),
    )


@app.route('/admin/stale-leads')
@admin_required
@safe_route
def admin_stale_leads():
    """Admin: stale leads (48h+ no update) with stale_worker assignment panel."""
    from execution_enforcement import admin_at_risk_leads as _at_risk
    db = get_db()
    rows = _at_risk(db, stale_hours=48, limit=500)
    # stale_worker fields are now included in the _at_risk() query — no extra queries needed
    # Top 5 team members by all-time points (for display)
    top5 = db.execute(
        """SELECT username, total_points FROM users
           WHERE role='team' AND status='approved' AND IFNULL(idle_hidden,0)=0
           ORDER BY total_points DESC LIMIT 5"""
    ).fetchall()
    # Manual dropdown — same eligibility as auto pool (team-only, non-hidden)
    all_team = db.execute(
        "SELECT username FROM users WHERE role='team' AND status='approved' AND IFNULL(idle_hidden,0)=0 ORDER BY username"
    ).fetchall()
    db.close()
    return render_template(
        'admin_stale_leads.html',
        rows=rows,
        top5=[dict(r) for r in top5],
        all_team=[r['username'] for r in all_team],
        today=_today_ist().isoformat(),
        csrf_token=session.get('_csrf_token', ''),
    )


@app.route('/api/admin/stale-redistribute', methods=['POST'])
@admin_required
def api_admin_stale_redistribute():
    """Admin manual trigger: redistribute stale leads to top-5 with optional limit."""
    from execution_enforcement import stale_redistribute
    data = request.get_json(silent=True) or {}
    try:
        limit = int(data.get('limit', 50))
        if limit < 1 or limit > 1000:
            return {'ok': False, 'error': 'limit must be between 1 and 1000'}, 400
    except (TypeError, ValueError):
        return {'ok': False, 'error': 'limit must be an integer'}, 400

    db = get_db()
    try:
        result = stale_redistribute(
            db, stale_hours=48, top_n=5,
            actor=session.get('username') or 'admin',
            limit=limit,
        )
        return {'ok': True, 'assigned': result['assigned'], 'skipped': result['skipped']}
    except Exception as e:
        app.logger.error('[stale-redistribute] Error: %s', e, exc_info=True)
        return {'ok': False, 'error': str(e)}, 500
    finally:
        db.close()


@app.route('/api/admin/stale-bulk-assign', methods=['POST'])
@admin_required
def api_admin_stale_bulk_assign():
    """Admin bulk-assigns selected stale leads to one person."""
    data = request.get_json(silent=True) or {}
    assign_to = (data.get('assign_to') or '').strip()
    if not assign_to:
        return {'ok': False, 'error': 'assign_to required'}, 400

    raw_ids = data.get('lead_ids', [])
    if not raw_ids:
        return {'ok': False, 'error': 'lead_ids required'}, 400
    try:
        lead_ids = [int(i) for i in raw_ids if int(i) > 0]
    except (TypeError, ValueError):
        return {'ok': False, 'error': 'Invalid lead_ids'}, 400
    if not lead_ids:
        return {'ok': False, 'error': 'No valid lead_ids'}, 400
    if len(lead_ids) > 500:
        return {'ok': False, 'error': 'Max 500 leads per bulk assign'}, 400

    actor = session.get('username')
    if not actor:
        return {'ok': False, 'error': 'Session expired'}, 401

    db = get_db()
    try:
        user = db.execute(
            "SELECT username FROM users WHERE username=? AND status='approved' AND role='team'",
            (assign_to,)
        ).fetchone()
        if not user:
            return {'ok': False, 'error': 'User not found or not eligible'}, 404

        now_str = _now_ist().strftime('%Y-%m-%d %H:%M:%S')
        ph = ','.join('?' * len(lead_ids))
        cur = db.execute(
            f"""UPDATE leads SET stale_worker=?, stale_worker_since=?, stale_worker_by=?
                WHERE id IN ({ph}) AND in_pool=0 AND deleted_at=''
                  AND status NOT IN ('Lost','Converted','Fully Converted','Retarget','Inactive','Seat Hold Confirmed')""",
            [assign_to, now_str, actor] + lead_ids,
        )
        # Log to lead_assignments for audit trail
        _new_uid2 = db.execute("SELECT id FROM users WHERE username=?", (assign_to,)).fetchone()
        _new_uid_val2 = int(_new_uid2['id']) if _new_uid2 else None
        if _new_uid_val2 and cur.rowcount > 0:
            _now2 = _now_ist().strftime('%Y-%m-%d %H:%M:%S')
            for _lid in lead_ids:
                try:
                    db.execute(
                        "INSERT OR IGNORE INTO lead_assignments (lead_id, assigned_to, previous_assigned_to, assigned_by, assign_type, reason, created_at) VALUES (?,?,NULL,?,?,?,?)",
                        (_lid, _new_uid_val2, actor, 'bulk_stale', f'admin bulk assign by {actor}', _now2),
                    )
                except Exception:
                    pass
        db.commit()
        _assigned_count = cur.rowcount
        # Push notification to assigned user (one summary push)
        if _assigned_count > 0:
            def _bg_push_bulk(u, cnt, by):
                _db = get_db()
                try:
                    _push_to_users(_db, u, '📋 Leads assigned to you',
                                   f'{cnt} lead{"s" if cnt != 1 else ""} assigned to you by {by}.',
                                   '/leads')
                finally:
                    _db.close()
            threading.Thread(target=_bg_push_bulk, args=(assign_to, _assigned_count, actor), daemon=True).start()
        return {'ok': True, 'assigned': _assigned_count}
    except Exception as e:
        return {'ok': False, 'error': str(e)}, 500
    finally:
        db.close()


@app.route('/api/admin/stale-assign-lead', methods=['POST'])
@admin_required
def api_admin_stale_assign_lead():
    """Admin manually assigns one stale lead to a specific person."""
    data     = request.get_json(silent=True) or {}
    try:
        lead_id = int(data.get('lead_id'))
        if lead_id <= 0:
            raise ValueError()
    except (TypeError, ValueError):
        return {'ok': False, 'error': 'lead_id must be a positive integer'}, 400

    assign_to = (data.get('assign_to') or '').strip()
    if not assign_to:
        return {'ok': False, 'error': 'assign_to required'}, 400

    actor = session.get('username')
    if not actor:
        return {'ok': False, 'error': 'Session expired'}, 401

    db = get_db()
    try:
        user = db.execute(
            "SELECT username FROM users WHERE username=? AND status='approved' AND role IN ('team','leader')",
            (assign_to,)
        ).fetchone()
        if not user:
            return {'ok': False, 'error': 'User not found or not eligible'}, 404
        now_str = _now_ist().strftime('%Y-%m-%d %H:%M:%S')
        cur = db.execute(
            """UPDATE leads SET stale_worker=?, stale_worker_since=?, stale_worker_by=?
               WHERE id=? AND in_pool=0 AND deleted_at=''
                 AND status NOT IN ('Lost','Converted','Fully Converted','Retarget','Inactive','Seat Hold Confirmed')""",
            (assign_to, now_str, actor, lead_id),
        )
        if cur.rowcount == 0:
            return {'ok': False, 'error': 'Lead not found or not eligible for stale assignment'}, 404
        # Also log to lead_assignments for audit trail
        _prev_uid = db.execute("SELECT assigned_user_id FROM leads WHERE id=?", (lead_id,)).fetchone()
        _prev = int(_prev_uid['assigned_user_id']) if _prev_uid and _prev_uid['assigned_user_id'] else None
        _new_uid = db.execute("SELECT id FROM users WHERE username=?", (assign_to,)).fetchone()
        _new_uid_val = int(_new_uid['id']) if _new_uid else None
        if _new_uid_val:
            _now2 = _now_ist().strftime('%Y-%m-%d %H:%M:%S')
            try:
                db.execute(
                    "INSERT OR IGNORE INTO lead_assignments (lead_id, assigned_to, previous_assigned_to, assigned_by, assign_type, reason, created_at) VALUES (?,?,?,?,?,?,?)",
                    (lead_id, _new_uid_val, _prev, actor, 'manual_stale', f'admin manual assign by {actor}', _now2),
                )
            except Exception:
                pass
        db.commit()
        # Push notification to assigned user
        _lead_row = db.execute("SELECT name, phone FROM leads WHERE id=?", (lead_id,)).fetchone()
        _lead_name = (_lead_row['name'] if _lead_row and _lead_row['name'] else f'Lead #{lead_id}')
        def _bg_push_assign(u, lname, by):
            _db = get_db()
            try:
                _push_to_users(_db, u, '📋 Lead assigned to you',
                               f'{lname} has been assigned to you by {by}.',
                               '/leads')
            finally:
                _db.close()
        threading.Thread(target=_bg_push_assign, args=(assign_to, _lead_name, actor), daemon=True).start()
        return {'ok': True}
    except Exception as e:
        return {'ok': False, 'error': str(e)}, 500
    finally:
        db.close()


@app.route('/admin/weak-members')
@admin_required
@safe_route
def admin_weak_members():
    """Lowest conversion first — weak people surface."""
    from execution_enforcement import admin_weak_members as _weak

    db = get_db()
    today = _today_ist().isoformat()
    rows = _weak(db, today_iso=today, limit=300)
    db.close()
    return render_template(
        'admin_weak_members.html',
        rows=rows,
        today=today,
        csrf_token=session.get('_csrf_token', ''),
    )


@app.route('/admin/leak-map')
@admin_required
@safe_route
def admin_leak_map():
    """Where volume sits + enrollment-path drop hints."""
    from execution_enforcement import admin_leak_map as _leak

    db = get_db()
    hist, drops = _leak(db)
    db.close()
    return render_template(
        'admin_leak_map.html',
        histogram=hist,
        funnel_drops=drops,
        today=_today_ist().isoformat(),
        csrf_token=session.get('_csrf_token', ''),
    )


@app.route('/admin/lead-ledger')
@admin_required
@safe_route
def admin_lead_ledger():
    """Full audit trail of every lead assignment + stage transition."""
    db = get_db()
    page = max(1, int(request.args.get('page', 1)))
    q = (request.args.get('q') or '').strip()
    per_page = 50

    # Build filter
    where = "WHERE l.in_pool=0 AND l.deleted_at=''"
    params = []
    if q:
        where += " AND (l.name LIKE ? OR l.phone LIKE ? OR u.username LIKE ?)"
        params += [f'%{q}%', f'%{q}%', f'%{q}%']

    total = db.execute(
        f"SELECT COUNT(DISTINCT l.id) FROM leads l LEFT JOIN users u ON u.id=l.assigned_user_id {where}",
        params
    ).fetchone()[0] or 0

    leads_page = db.execute(
        f"""SELECT l.id, l.name, l.phone, l.status, l.pipeline_stage, l.current_owner,
                   COALESCE(u.username,'') AS assignee, l.created_at, l.updated_at,
                   l.stale_worker, l.stale_worker_by, l.stale_worker_since,
                   l.claimed_at
            FROM leads l LEFT JOIN users u ON u.id=l.assigned_user_id
            {where}
            ORDER BY l.updated_at DESC
            LIMIT ? OFFSET ?""",
        params + [per_page, (page - 1) * per_page]
    ).fetchall()

    lead_ids = [r['id'] for r in leads_page]
    ph = ','.join('?' * len(lead_ids)) if lead_ids else '0'

    # Fetch assignment history for these leads
    assign_hist = db.execute(
        f"""SELECT la.lead_id, la.assign_type, la.assigned_by, la.reason, la.created_at,
                   COALESCE(u_new.username, '') AS assigned_to_name,
                   COALESCE(u_old.username, '') AS prev_assigned_name
            FROM lead_assignments la
            LEFT JOIN users u_new ON u_new.id = la.assigned_to
            LEFT JOIN users u_old ON u_old.id = la.previous_assigned_to
            WHERE la.lead_id IN ({ph})
            ORDER BY la.lead_id, la.created_at DESC""",
        lead_ids
    ).fetchall() if lead_ids else []

    # Fetch stage transition history for these leads
    stage_hist = db.execute(
        f"""SELECT lead_id, stage, owner, triggered_by, created_at
            FROM lead_stage_history
            WHERE lead_id IN ({ph})
            ORDER BY lead_id, created_at DESC""",
        lead_ids
    ).fetchall() if lead_ids else []

    # Group by lead_id
    from collections import defaultdict
    assign_by_lead = defaultdict(list)
    for r in assign_hist:
        assign_by_lead[r['lead_id']].append(dict(r))
    stage_by_lead = defaultdict(list)
    for r in stage_hist:
        stage_by_lead[r['lead_id']].append(dict(r))

    leads_data = []
    for r in leads_page:
        leads_data.append({
            **dict(r),
            'assignments': assign_by_lead[r['id']],
            'stages': stage_by_lead[r['id']],
        })

    db.close()
    return render_template('admin_lead_ledger.html',
                           leads=leads_data,
                           page=page,
                           per_page=per_page,
                           total=total,
                           total_pages=max(1, (total + per_page - 1) // per_page),
                           q=q,
                           csrf_token=session.get('_csrf_token', ''))


@app.route('/admin/kpi-detail')
@admin_required
@safe_route
def admin_kpi_detail():
    kpi_type = (request.args.get('type') or '').strip()
    if kpi_type not in ('claimed', 'enrolled'):
        return {'ok': False, 'error': 'Invalid type'}, 400
    db = get_db()
    today = _today_ist().isoformat()
    _base_w = "l.deleted_at='' AND l.in_pool=0"
    _approved_team = (
        "EXISTS (SELECT 1 FROM users u2 WHERE u2.id=l.assigned_user_id "
        "AND u2.role IN ('team','leader') AND u2.status='approved')"
    )
    if kpi_type == 'claimed':
        _ts = sql_ts_calendar_day("l.claimed_at")
        rows = db.execute(
            f"""
            SELECT l.id, l.name, l.phone, l.claimed_at,
                   COALESCE(u.username, '') AS assigned_to,
                   COALESCE(u.fbo_id, '') AS fbo_id
            FROM leads l
            LEFT JOIN users u ON u.id = l.assigned_user_id
            WHERE {_base_w}
              AND l.claimed_at IS NOT NULL AND TRIM(COALESCE(l.claimed_at,''))!=''
              AND {_ts} = date(?)
              AND {_approved_team}
            ORDER BY l.claimed_at DESC
            """,
            (today,),
        ).fetchall()
        db.close()
        return {
            'ok': True,
            'type': 'claimed',
            'title': f'Claimed Leads \u2014 {today}',
            'columns': ['Name', 'Phone', 'Assigned To', 'Claimed At'],
            'rows': [
                {
                    'name': r['name'],
                    'phone': r['phone'] or '',
                    'assigned_to': r['assigned_to'],
                    'fbo_id': r['fbo_id'],
                    'claimed_at': r['claimed_at'] or '',
                }
                for r in rows
            ],
        }
    else:
        _ts_enroll = sql_ts_calendar_day("l.enrolled_at")
        rows = db.execute(
            f"""
            SELECT l.id, l.name, l.phone, l.status, l.payment_amount,
                   l.enrolled_at, l.payment_proof_approval_status,
                   COALESCE(u.username, '') AS assigned_to,
                   COALESCE(u.fbo_id, '') AS fbo_id
            FROM leads l
            LEFT JOIN users u ON u.id = l.assigned_user_id
            WHERE {_base_w}
              AND TRIM(COALESCE(l.enrolled_at,'')) != ''
              AND {_ts_enroll} = date(?)
              AND TRIM(COALESCE(l.payment_proof_path,'')) != ''
              AND LOWER(COALESCE(l.payment_proof_approval_status,'')) = 'approved'
              AND {_approved_team}
            ORDER BY l.enrolled_at DESC
            """,
            (today,),
        ).fetchall()
        db.close()
        return {
            'ok': True,
            'type': 'enrolled',
            'title': f'Enrollments (\u20b9196) \u2014 {today}',
            'columns': ['Name', 'Phone', 'Assigned To', 'Amount', 'Date'],
            'rows': [
                {
                    'name': r['name'],
                    'phone': r['phone'] or '',
                    'assigned_to': r['assigned_to'],
                    'fbo_id': r['fbo_id'],
                    'amount': float(r['payment_amount'] or 0),
                    'status': r['status'],
                    'enrolled_at': r['enrolled_at'] or '',
                }
                for r in rows
            ],
        }


# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
#  Team Dashboard  (scoped to logged-in user)
# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500


@app.route('/dashboard')
@login_required
@safe_route
def team_dashboard():
    username = acting_username()
    user_id  = acting_user_id()
    db       = get_db()
    team_execution_funnel = None
    team_followup_attack = []
    team_enrollment_pressure = None

    # Check seat_hold expiry and auto-expire 24hr-old pipeline leads on every dashboard load
    _check_seat_hold_expiry(db, username)
    _auto_expire_pipeline_leads(db, username)
    # Follow-up auto-discipline + 2h slot penalties: leader only (team skips — same as claim Rules 2/8)
    if session.get('role') == 'leader':
        if (_get_setting(db, 'gate_followup_discipline_enabled', '1') or '1') == '1':
            followup_discipline_process_overdue(db, username)
            _penalize_missed_followups(db, username)

    tracking_start = _get_setting(db, 'tracking_start_date', '')
    metrics  = _get_metrics(db, username=username, since=tracking_start or None)
    wallet   = _get_wallet(db, username)

    recent = db.execute(
        "SELECT * FROM leads WHERE assigned_user_id=? AND in_pool=0 ORDER BY created_at DESC LIMIT 5",
        (user_id,),
    ).fetchall()

    _sc = db.execute(
        "SELECT status, COUNT(*) as c FROM leads WHERE assigned_user_id=? AND in_pool=0 AND deleted_at='' GROUP BY status",
        (user_id,),
    ).fetchall()
    status_data = {s: 0 for s in STATUSES}
    for row in _sc:
        if row['status'] in status_data:
            status_data[row['status']] = row['c']

    monthly = db.execute("""
        SELECT strftime('%Y-%m', created_at) as month,
               SUM(payment_amount) as total
        FROM leads
        WHERE payment_done=1 AND assigned_user_id=? AND in_pool=0
        GROUP BY month
        ORDER BY month DESC
        LIMIT 6
    """, (user_id,)).fetchall()

    today = _today_ist().isoformat()
    today_report = db.execute(
        "SELECT * FROM daily_reports WHERE username=? AND report_date=?",
        (username, today)
    ).fetchone()

    pool_count = db.execute("SELECT COUNT(*) FROM leads WHERE in_pool=1").fetchone()[0]

    _rt_ph = ','.join('?' * len(RETARGET_TAGS))
    retarget_count = db.execute(
        f"SELECT COUNT(*) FROM leads WHERE in_pool=0 AND deleted_at='' "
        f"AND assigned_user_id=? AND status NOT IN ('Converted','Fully Converted','Lost') "
        f"AND (call_result IN ({_rt_ph}) OR status='Retarget')",
        (user_id, *RETARGET_TAGS),
    ).fetchone()[0]

    zoom_link  = _get_setting(db, 'zoom_link', '')
    zoom_title = _get_setting(db, 'zoom_title', "Today's Live Session")
    zoom_time  = _get_setting(db, 'zoom_time', '2:00 PM')

    _ud_team = sql_ts_calendar_day()
    _today_stats = db.execute(f"""
        SELECT COUNT(*) as cnt, COALESCE(SUM(payment_amount),0) as total
        FROM leads
        WHERE assigned_user_id=? AND status='Paid \u20b9196' AND in_pool=0 AND deleted_at=''
          AND {_ud_team} = date(?)
    """, (user_id, today)).fetchone()
    today_paid     = _today_stats['cnt'] or 0
    today_earnings = _today_stats['total'] or 0
    _team_today_m = get_today_metrics(db, day_iso=today, user_ids=[user_id], usernames=[username], proof_approved_only=False)
    team_today_claimed = _team_today_m['claimed']
    team_today_calls = _team_today_m['calls']
    team_today_enrolled = _team_today_m['enrolled']
    team_today_stats = {
        'claimed_today': int(team_today_claimed),
        'calls_today': int(team_today_calls),
        'enrolled_today': int(team_today_enrolled),
    }

    if session.get('role') == 'team':
        followups = []
    else:
        followups = db.execute("""
            SELECT id, name, phone, follow_up_date FROM leads
            WHERE assigned_user_id=? AND in_pool=0 AND deleted_at=''
              AND follow_up_date != ''
              AND follow_up_date <= ?
              AND status NOT IN ('Converted','Fully Converted','Lost','Retarget','Inactive')
            ORDER BY follow_up_date ASC LIMIT 10
        """, (user_id, today)).fetchall()

    notices = db.execute(
        "SELECT * FROM announcements ORDER BY pin DESC, created_at DESC LIMIT 5"
    ).fetchall()

    _cr_row = db.execute(
        "SELECT calling_reminder_time FROM users WHERE username=?", (username,)
    ).fetchone()
    calling_reminder_time = _cr_row['calling_reminder_time'] if _cr_row else ''

    funnel_leads = {}
    for _mk, _cond in [
        ('day1',      'day1_done=1'),
        ('day2',      'day2_done=1'),
        ('interview', 'interview_done=1'),
        ('converted', "status IN ('Converted','Fully Converted')"),
    ]:
        _rows = db.execute(
            f"SELECT name FROM leads "
            f"WHERE in_pool=0 AND deleted_at='' AND assigned_user_id=? AND {_cond} "
            f"ORDER BY updated_at DESC LIMIT 5",
            (user_id,),
        ).fetchall()
        funnel_leads[_mk] = [r['name'] for r in _rows]

    # Follow-up queue count (IST date so no timezone mismatch)
    now_date_ist = _now_ist().strftime('%Y-%m-%d')
    if session.get('role') == 'team':
        followup_count = 0
    else:
        fu_placeholders = ','.join('?' * len(FOLLOWUP_TAGS))
        followup_count = db.execute(f"""
            SELECT COUNT(*) FROM leads
            WHERE in_pool=0 AND deleted_at=''
              AND assigned_user_id=?
              AND status NOT IN ('Converted','Fully Converted','Lost','Retarget','Inactive')
              AND (
                (follow_up_date != '' AND DATE(follow_up_date) <= ?)
                OR call_result IN ({fu_placeholders})
              )
        """, [user_id, now_date_ist] + list(FOLLOWUP_TAGS)).fetchone()[0]

    # My Leads Progress: strict personal ownership + canonical stage mapping.
    # Important: claimed_at can be empty-string in legacy rows, so we must trim-check.
    _progress_params = []
    if session.get('role') == 'team':
        _progress_owner_sql = "TRIM(COALESCE(current_owner,'')) = ?"
        _progress_params.append(username)
    else:
        _progress_owner_sql = "(assigned_user_id=? OR TRIM(COALESCE(current_owner,''))=?)"
        _progress_params.extend([user_id, username])

    my_progress_rows_full = db.execute(
        "SELECT * FROM leads "
        "WHERE in_pool=0 AND deleted_at='' "
        f"AND {_progress_owner_sql} "
        "AND TRIM(COALESCE(claimed_at,'')) != '' "
        "AND LOWER(COALESCE(payment_proof_approval_status,'')) != 'rejected' "
        "AND status NOT IN ('Lost','Retarget','Inactive','Converted','Fully Converted') "
        "ORDER BY updated_at DESC "
        "LIMIT 60",
        tuple(_progress_params),
    ).fetchall()
    my_progress_leads = _enrich_leads(my_progress_rows_full, db=db) if my_progress_rows_full else []

    _progress_stage_meta = {
        'prospecting': {'label': 'Prospecting', 'color': '#6b7280', 'step': 1},
        'enrollment': {'label': 'Enrollment', 'color': '#6b7280', 'step': 1},
        'enrolled': {'label': 'Paid ₹196', 'color': '#2563eb', 'step': 2},
        'day1': {'label': 'Day 1', 'color': '#0284c7', 'step': 3},
        'day2': {'label': 'Day 2', 'color': '#d97706', 'step': 4},
        'day3': {'label': 'Interview / Track', 'color': '#dc2626', 'step': 5},
        'plan_2cc': {'label': '2cc Plan', 'color': '#7c3aed', 'step': 6},
        'seat_hold': {'label': 'Seat Hold', 'color': '#6d28d9', 'step': 7},
        'pending': {'label': 'Pending', 'color': '#0f766e', 'step': 8},
        'level_up': {'label': 'Level Up', 'color': '#0ea5e9', 'step': 9},
        'closing': {'label': 'Closing', 'color': '#16a34a', 'step': 10},
        'training': {'label': 'Training', 'color': '#4338ca', 'step': 11},
    }
    _progress_steps_total = 11
    for d in my_progress_leads:
        _st = (d.get('status') or '').strip()
        _stage = (d.get('pipeline_stage') or '').strip() or STATUS_TO_STAGE.get(_st, 'prospecting')
        _meta = _progress_stage_meta.get(_stage, _progress_stage_meta['prospecting'])
        d['pipeline_stage'] = _stage
        d['stage_label'] = _meta['label']
        d['stage_color'] = _meta['color']
        d['stage_step'] = int(_meta['step'])
        d['stage_total'] = _progress_steps_total
        _stotal = max(1, int(_progress_steps_total))
        d['progress_pct'] = int(min(100, max(0, round((d['stage_step'] / _stotal) * 100))))

    _s1_ph = ','.join('?' * len(STAGE1_STATUSES))
    if session.get('role') == 'leader':
        stage1_leads, day1_leads_db, day2_leads_db, day3_leads, pending_leads = (
            _leader_dashboard_merged_pipeline(db, username)
        )
    else:
        stage1_leads = db.execute(
            f"SELECT * FROM leads WHERE assigned_user_id=? AND in_pool=0 AND deleted_at='' AND status IN ({_s1_ph}) ORDER BY updated_at ASC",
            (user_id, *STAGE1_STATUSES),
        ).fetchall()
        day1_leads_db = db.execute(
            "SELECT * FROM leads WHERE assigned_user_id=? AND in_pool=0 AND deleted_at='' AND status='Day 1' ORDER BY updated_at ASC",
            (user_id,),
        ).fetchall()
        day2_leads_db = db.execute(
            "SELECT * FROM leads WHERE assigned_user_id=? AND in_pool=0 AND deleted_at='' AND status='Day 2' ORDER BY updated_at ASC",
            (user_id,),
        ).fetchall()
        day3_leads = db.execute(
            "SELECT * FROM leads WHERE assigned_user_id=? AND in_pool=0 AND deleted_at='' AND status IN ('Interview','Track Selected') ORDER BY updated_at ASC",
            (user_id,),
        ).fetchall()
        pending_leads = db.execute(
            "SELECT * FROM leads WHERE assigned_user_id=? AND in_pool=0 AND deleted_at='' AND status='Seat Hold Confirmed' ORDER BY updated_at ASC",
            (user_id,),
        ).fetchall()
    score_row = db.execute(
        "SELECT * FROM daily_scores WHERE username=? AND score_date=?",
        (username, today)
    ).fetchone()
    today_score  = score_row['total_points'] if score_row else 0
    today_streak = score_row['streak_days']  if score_row else 0
    pending_batches = (
        sum(1 for l in day1_leads_db if not (l['d1_morning'] and l['d1_afternoon'] and l['d1_evening'])) +
        sum(1 for l in day2_leads_db if not (l['d2_morning'] and l['d2_afternoon'] and l['d2_evening']))
    )
    # Counts derived from lists
    stage1_count         = len(stage1_leads)
    day1_count           = len(day1_leads_db)
    day2_count           = len(day2_leads_db)
    day3_count           = len(day3_leads)
    pending_count_pipeline = len(pending_leads)

    # Monthly goals + actuals
    current_month = _now_ist().strftime('%Y-%m')
    target_rows = db.execute(
        "SELECT metric, target_value FROM targets WHERE username=? AND month=?",
        (username, current_month)
    ).fetchall()
    m = _get_metrics(db, username, since=tracking_start or None)
    metric_actuals = {
        'leads':       m.get('total', 0),
        'payments':    m.get('paid', 0),
        'conversions': m.get('converted', 0),
        'revenue':     m.get('revenue', 0),
    }
    metric_labels = {'leads': 'Leads Added', 'payments': '₹196 Payments',
                     'conversions': 'Conversions', 'revenue': 'Revenue ₹'}
    targets_data = []
    for tr in target_rows:
        key    = tr['metric']
        target = tr['target_value']
        actual = metric_actuals.get(key, 0)
        pct    = round(actual / target * 100, 1) if target else 0
        targets_data.append({'label': metric_labels.get(key, key),
                              'actual': actual, 'target': int(target), 'pct': pct})

    if session.get('role') == 'team':
        from execution_enforcement import team_personal_funnel, team_followup_attack_rows

        team_execution_funnel = team_personal_funnel(db, user_id)
        team_followup_attack = team_followup_attack_rows(db, user_id, today, limit=20)
        pay_tgt = 0
        for tr in target_rows:
            if tr['metric'] == 'payments':
                pay_tgt = int(tr['target_value'] or 0)
        team_enrollment_pressure = {
            'enrolled_today': int(team_today_stats['enrolled_today']),
            'claimed_today': int(team_today_stats['claimed_today']),
            'month_payments_target': pay_tgt,
            'month_payments_actual': int(metric_actuals.get('payments', 0)),
        }

    # Build batch_videos BEFORE closing database
    batch_videos = {
        'd1_morning_v1':   _get_setting(db, 'batch_d1_morning_v1', ''),
        'd1_morning_v2':   _get_setting(db, 'batch_d1_morning_v2', ''),
        'd1_afternoon_v1': _get_setting(db, 'batch_d1_afternoon_v1', ''),
        'd1_afternoon_v2': _get_setting(db, 'batch_d1_afternoon_v2', ''),
        'd1_evening_v1':   _get_setting(db, 'batch_d1_evening_v1', ''),
        'd1_evening_v2':   _get_setting(db, 'batch_d1_evening_v2', ''),
        'd2_morning_v1':   _get_setting(db, 'batch_d2_morning_v1', ''),
        'd2_morning_v2':   _get_setting(db, 'batch_d2_morning_v2', ''),
        'd2_afternoon_v1': _get_setting(db, 'batch_d2_afternoon_v1', ''),
        'd2_afternoon_v2': _get_setting(db, 'batch_d2_afternoon_v2', ''),
        'd2_evening_v1':   _get_setting(db, 'batch_d2_evening_v1', ''),
        'd2_evening_v2':   _get_setting(db, 'batch_d2_evening_v2', ''),
    }
    enrollment_video_url   = _get_setting(db, 'enrollment_video_url', '')
    enrollment_video_title  = _get_setting(db, 'enrollment_video_title', 'Enrollment Video')

    # Enrich leads with heat + next_action
    stage1_leads_e  = _enrich_leads(stage1_leads)
    day1_leads_e    = _enrich_leads(day1_leads_db)
    day2_leads_e    = _enrich_leads(day2_leads_db)
    day3_leads_e    = _enrich_leads(day3_leads)
    pending_leads_e = _enrich_leads(pending_leads)
    recent_e        = _enrich_leads(recent)

    # Leader-specific: team snapshot data (downline pipeline + report compliance)
    show_day1_batches = session.get('role') in ('leader', 'admin')
    team_snapshot = []
    leader_report_stats = {}
    downline_missing_reports = []
    downline_usernames = []
    _dl_uids = []
    leader_today_stats = {'leads_today': 0, 'calls_today': 0, 'enrolled_today': 0, 'conv_rate': 0}
    leader_alerts = {'stuck': [], 'no_calls': []}
    if session.get('role') == 'leader':
        # Get all direct + recursive downline usernames (excluding self)
        try:
            downline_usernames = _get_network_usernames(db, username)
        except Exception:
            downline_usernames = []
        downline_usernames = [u for u in downline_usernames if u != username]

        stage_ph = ','.join('?' * len(STAGE1_STATUSES))
        _dl_id_map = user_ids_for_usernames(db, downline_usernames) if downline_usernames else {}
        _dl_members_ok = [m for m in downline_usernames if m in _dl_id_map]
        _dl_uids = [_dl_id_map[m] for m in _dl_members_ok]
        _uid_to_dl_uname = {int(v): k for k, v in _dl_id_map.items()}

        _dl_counts_by_uid = {}
        if _dl_uids:
            _dl_uid_ph = ','.join('?' * len(_dl_uids))
            _dl_agg_sql = f"""
                SELECT assigned_user_id,
                    SUM(CASE WHEN status IN ({stage_ph}) THEN 1 ELSE 0 END) as stage1,
                    SUM(CASE WHEN status='Day 1' THEN 1 ELSE 0 END) as day1,
                    SUM(CASE WHEN status='Day 2' THEN 1 ELSE 0 END) as day2,
                    SUM(CASE WHEN status IN ('Interview','Track Selected')
                        THEN 1 ELSE 0 END) as day3,
                    SUM(CASE WHEN status='Seat Hold Confirmed' THEN 1 ELSE 0 END) as pending,
                    SUM(CASE WHEN status IN ('Fully Converted','Converted')
                        THEN 1 ELSE 0 END) as converted
                FROM leads
                WHERE assigned_user_id IN ({_dl_uid_ph}) AND in_pool=0 AND deleted_at=''
                GROUP BY assigned_user_id
            """
            for _dr in db.execute(_dl_agg_sql, (*STAGE1_STATUSES, *_dl_uids)).fetchall():
                _dl_counts_by_uid[int(_dr['assigned_user_id'])] = _dr

        _dl_score_pts = {}
        _dl_calls_map = {}
        _dl_m_ph = ''
        if _dl_members_ok:
            _dl_m_ph = ','.join('?' * len(_dl_members_ok))
            for _sr in db.execute(
                f"SELECT username, total_points, COALESCE(calls_made,0) AS calls_made "
                f"FROM daily_scores WHERE score_date=? AND username IN ({_dl_m_ph})",
                (today, *_dl_members_ok),
            ).fetchall():
                _dl_score_pts[_sr['username']] = int(_sr['total_points'] or 0)
                _dl_calls_map[_sr['username']] = int(_sr['calls_made'] or 0)

        _dl_reports_submitted = set()
        if _dl_members_ok:
            for _rr in db.execute(
                f"SELECT username FROM daily_reports WHERE report_date=? AND username IN ({_dl_m_ph})",
                (today, *_dl_members_ok),
            ).fetchall():
                _dl_reports_submitted.add(_rr['username'])

        for member in downline_usernames:
            if member not in _dl_id_map:
                continue
            _mid = _dl_id_map[member]
            _cr = _dl_counts_by_uid.get(int(_mid))
            counts = _cr if _cr else None
            today_pts = _dl_score_pts.get(member, 0)
            report_done = member in _dl_reports_submitted
            team_snapshot.append({
                'username':    member,
                'stage1':      int(counts['stage1'] or 0) if counts else 0,
                'day1':        int(counts['day1'] or 0) if counts else 0,
                'day2':        int(counts['day2'] or 0) if counts else 0,
                'day3':        int(counts['day3'] or 0) if counts else 0,
                'pending':     int(counts['pending'] or 0) if counts else 0,
                'converted':   int(counts['converted'] or 0) if counts else 0,
                'score':       today_pts,
                'report_done': report_done,
            })
            if not report_done:
                downline_missing_reports.append(member)

        leader_report_stats = {
            'total':     len(downline_usernames),
            'submitted': len([m for m in team_snapshot if m['report_done']]),
            'missing':   downline_missing_reports,
        }

        if downline_usernames:
            _dl_ids = list(_dl_uids)
            _ts_ld_claim = sql_ts_calendar_day("claimed_at")
            _ts_ld_upd = sql_ts_calendar_day("updated_at")
            if _dl_ids:
                _ph = ','.join('?' * len(_dl_ids))
                _mem = tuple(_dl_ids)
                _m_today = get_today_metrics(db, day_iso=today, user_ids=_dl_ids, proof_approved_only=False)
                _lc = _m_today['claimed']
                _cm = _m_today['calls']
                _en = _m_today['enrolled']
                _tot = db.execute(
                    f"SELECT COUNT(*) FROM leads WHERE assigned_user_id IN ({_ph}) AND in_pool=0 "
                    f"AND deleted_at='' AND status NOT IN ('Lost','Retarget')",
                    _mem,
                ).fetchone()[0]
                _conv = db.execute(
                    f"SELECT COUNT(*) FROM leads WHERE assigned_user_id IN ({_ph}) AND in_pool=0 "
                    f"AND deleted_at='' AND status IN ('Converted','Fully Converted')",
                    _mem,
                ).fetchone()[0]
            else:
                _lc = _cm = _en = _tot = _conv = 0
            leader_today_stats = {
                'leads_today': int(_lc or 0),
                'calls_today': int(_cm or 0),
                'enrolled_today': int(_en or 0),
                'conv_rate': round(100.0 * int(_conv or 0) / max(1, int(_tot or 0)), 1),
            }

            _stale = (_now_ist().replace(tzinfo=None) - datetime.timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')
            _stuck = []
            _nocall = []
            _gate_alerts = []
            if _dl_uids:
                _dl_uid_ph2 = ','.join('?' * len(_dl_uids))
                for _sr in db.execute(
                    f"""
                    SELECT assigned_user_id, COUNT(*) AS c FROM leads
                    WHERE assigned_user_id IN ({_dl_uid_ph2}) AND in_pool=0 AND deleted_at=''
                      AND status NOT IN ('Converted','Fully Converted','Lost','Retarget')
                      AND (TRIM(COALESCE(updated_at,''))='' OR TRIM(updated_at) < ?)
                    GROUP BY assigned_user_id
                    """,
                    (*_dl_uids, _stale),
                ).fetchall():
                    _c = int(_sr['c'] or 0)
                    if _c > 0:
                        _uid = int(_sr['assigned_user_id'])
                        _un = _uid_to_dl_uname.get(_uid)
                        if _un:
                            _stuck.append({'username': _un, 'count': _c})
                for _m in _dl_members_ok:
                    if _dl_calls_map.get(_m, 0) == 0:
                        _nocall.append(_m)
            if _dl_ids:
                _g1 = db.execute(
                    f"SELECT COUNT(*) FROM leads WHERE assigned_user_id IN ({_ph}) AND in_pool=0 AND deleted_at='' "
                    "AND status='Day 1' AND updated_at < ?",
                    (*_mem, _stale),
                ).fetchone()[0] or 0
                _g2 = db.execute(
                    f"SELECT COUNT(*) FROM leads WHERE assigned_user_id IN ({_ph}) AND in_pool=0 AND deleted_at='' "
                    "AND status='Day 2' AND updated_at < ?",
                    (*_mem, _stale),
                ).fetchone()[0] or 0
                _g3 = db.execute(
                    f"SELECT COUNT(*) FROM leads WHERE assigned_user_id IN ({_ph}) AND in_pool=0 AND deleted_at='' "
                    "AND status='Day 2' AND LOWER(COALESCE(test_status,'')) != 'passed' AND updated_at < ?",
                    (*_mem, _stale),
                ).fetchone()[0] or 0
                _g4 = db.execute(
                    f"SELECT COUNT(*) FROM leads WHERE assigned_user_id IN ({_ph}) AND in_pool=0 AND deleted_at='' "
                    "AND status='Interview' AND updated_at < ?",
                    (*_mem, _stale),
                ).fetchone()[0] or 0
                _g5 = db.execute(
                    f"SELECT COUNT(*) FROM leads WHERE assigned_user_id IN ({_ph}) AND in_pool=0 AND deleted_at='' "
                    "AND status='Interview' AND (track_selected IS NULL OR TRIM(COALESCE(track_selected,''))='') "
                    "AND updated_at < ?",
                    (*_mem, _stale),
                ).fetchone()[0] or 0
                _g6 = db.execute(
                    f"SELECT COUNT(*) FROM leads WHERE assigned_user_id IN ({_ph}) AND in_pool=0 AND deleted_at='' "
                    "AND status='Track Selected' AND updated_at < ?",
                    (*_mem, _stale),
                ).fetchone()[0] or 0
                _g7 = db.execute(
                    f"SELECT COUNT(*) FROM leads WHERE assigned_user_id IN ({_ph}) AND in_pool=0 AND deleted_at='' "
                    "AND status IN ('Day 1','Day 2','Interview','Track Selected','Seat Hold Confirmed') "
                    "AND TRIM(COALESCE(follow_up_date,''))='' AND updated_at < ?",
                    (*_mem, _stale),
                ).fetchone()[0] or 0
                _gate_alerts = [
                    {'code': 'G1', 'label': 'Day 1 delay', 'count': int(_g1)},
                    {'code': 'G2', 'label': 'Day 2 delay', 'count': int(_g2)},
                    {'code': 'G3', 'label': 'Test not done', 'count': int(_g3)},
                    {'code': 'G4', 'label': 'Interview delay', 'count': int(_g4)},
                    {'code': 'G5', 'label': 'Track not selected', 'count': int(_g5)},
                    {'code': 'G6', 'label': 'Seat hold delay', 'count': int(_g6)},
                    {'code': 'G7', 'label': 'Follow-up missed', 'count': int(_g7)},
                ]
            leader_alerts = {'stuck': _stuck, 'no_calls': _nocall, 'gates': _gate_alerts}

            if team_snapshot and _dl_uids:
                from execution_enforcement import (
                    downline_member_execution_stats,
                    bottleneck_tags_for_member,
                )
                _ex_map = downline_member_execution_stats(db, _dl_uids, today)
                for row in team_snapshot:
                    un = row['username']
                    _uid = _dl_id_map.get(un)
                    st = _ex_map.get(int(_uid)) if _uid else None
                    if st is None and _uid:
                        st = {
                            'total_active': 0,
                            'enrollments': 0,
                            'proof_pend': 0,
                            'fu_due': 0,
                            'conv_pct': 0.0,
                        }
                    elif st is None:
                        st = {
                            'total_active': 0,
                            'enrollments': 0,
                            'proof_pend': 0,
                            'fu_due': 0,
                            'conv_pct': 0.0,
                        }
                    row['ex'] = st
                    row['bottlenecks'] = bottleneck_tags_for_member(st, _dl_calls_map.get(un, 0))
                team_snapshot.sort(
                    key=lambda x: (
                        x['ex']['conv_pct'],
                        -x['ex']['proof_pend'],
                        -x['ex']['fu_due'],
                        x['username'],
                    )
                )

    perf_state = None
    if session.get('role') in ('team', 'leader'):
        perf_state = get_performance_ui_state(db, username)
        db.commit()

    step8_coach = None
    step8_leader_ai = None
    step8_evening_line = ''
    if session.get('role') in ('team', 'leader'):
        step8_coach = compute_step8_team_coach_for_user(db, username)
        _now_loc = _now_ist().replace(tzinfo=None)
        step8_evening_line = build_step8_evening_summary_line(step8_coach, today, _now_loc)
        if session.get('role') == 'leader' and downline_usernames:
            step8_leader_ai = compute_step8_leader_coach(db, downline_usernames, today, _now_loc)

    # Gate assistant checklist (team + leader): clear pending items before blocks happen.
    gate_assistant = {}
    if session.get('role') in ('team', 'leader'):
        role_now = session.get('role', 'team')
        call_target = int(daily_call_target(db) or 0)
        report_done = bool(today_report)
        overdue_count = 0
        if role_now != 'team':
            overdue_count = db.execute(
                """
                SELECT COUNT(*) FROM leads
                WHERE assigned_user_id=? AND in_pool=0 AND deleted_at=''
                  AND status NOT IN ('Converted','Fully Converted','Lost','Retarget')
                  AND TRIM(COALESCE(follow_up_date,''))!=''
                  AND date(substr(trim(follow_up_date),1,10)) < date(?)
                """,
                (user_id, today),
            ).fetchone()[0] or 0
        # Team members do not own follow-up scheduling; skip this checklist item for them.
        interested_no_fu = 0
        if role_now == 'leader':
            interested_no_fu = db.execute(
                """
                SELECT COUNT(*) FROM leads
                WHERE assigned_user_id=? AND in_pool=0 AND deleted_at=''
                  AND status NOT IN ('Converted','Fully Converted','Lost','Retarget')
                  AND (
                    call_status IN ('Called - Interested','Called - Follow Up','Call Back')
                    OR status IN ('Video Sent','Video Watched','Paid ₹196')
                  )
                  AND TRIM(COALESCE(follow_up_date,''))=''
                """,
                (user_id,),
            ).fetchone()[0] or 0
        # Use get_today_metrics SSOT (distinct fresh leads actually called after claiming) so
        # gate_assistant and stat tiles show the same number. daily_scores.calls_made can
        # double-count the same lead called multiple times in one day.
        calls_today_logged = int(team_today_calls)
        active_assigned = db.execute(
            """
            SELECT COUNT(*) FROM leads
            WHERE assigned_user_id=? AND in_pool=0 AND deleted_at=''
              AND status NOT IN ('Converted','Fully Converted','Lost','Retarget')
            """,
            (user_id,),
        ).fetchone()[0] or 0
        effective_target = call_target if active_assigned > 0 else 0

        if role_now == 'leader':
            if _dl_uids:
                _ph_pf = ','.join('?' * len(_dl_uids))
                pending_proof_count = db.execute(
                    f"""
                    SELECT COUNT(*) FROM leads
                    WHERE in_pool=0 AND deleted_at=''
                      AND assigned_user_id IN ({_ph_pf})
                      AND LOWER(COALESCE(payment_proof_approval_status,''))='pending'
                      AND TRIM(COALESCE(payment_proof_path,''))!=''
                    """,
                    _dl_uids,
                ).fetchone()[0] or 0
            else:
                pending_proof_count = 0
        else:
            pending_proof_count = db.execute(
                """
                SELECT COUNT(*) FROM leads
                WHERE assigned_user_id=? AND in_pool=0 AND deleted_at=''
                  AND LOWER(COALESCE(payment_proof_approval_status,''))='pending'
                  AND TRIM(COALESCE(payment_proof_path,''))!=''
                """,
                (user_id,),
            ).fetchone()[0] or 0

        _ga_evening = _now_ist().hour >= DAILY_CALL_ENFORCE_START_HOUR_IST
        _calls_ok = int(calls_today_logged) >= int(effective_target) or not _ga_evening
        checks = [('Daily report sent', report_done)]
        if role_now != 'team':
            checks.append(('Old follow-up dates fixed', int(overdue_count) == 0))
        checks.extend(
            [
                ('Enough calls logged today' if _ga_evening else 'Calls for today (in progress)', _calls_ok),
                ('No Rs 196 proof waiting', int(pending_proof_count) == 0),
            ]
        )
        done_checks = len([1 for _, ok in checks if ok])
        total_checks = len(checks)
        progress_pct = int(round((done_checks * 100.0) / max(1, total_checks)))
        if role_now == 'leader' and int(interested_no_fu) > 0:
            _tomorrow = (_now_ist() + datetime.timedelta(days=1)).strftime('%Y-%m-%d')
            db.execute(
                """
                UPDATE leads SET follow_up_date=?, updated_at=?
                WHERE assigned_user_id=? AND in_pool=0 AND deleted_at=''
                  AND status NOT IN ('Converted','Fully Converted','Lost','Retarget')
                  AND (
                    call_status IN ('Called - Interested','Called - Follow Up','Call Back')
                    OR status IN ('Video Sent','Video Watched','Paid ₹196')
                  )
                  AND TRIM(COALESCE(follow_up_date,''))=''
                """,
                (_tomorrow, _now_ist().strftime('%Y-%m-%d %H:%M:%S'), user_id),
            )
            db.commit()
            interested_no_fu = 0

        _is_evening_risk = _now_ist().hour >= DAILY_CALL_ENFORCE_START_HOUR_IST
        risk_level = 'green'
        next_action = 'Good — main tasks for today are done.'
        next_action_link = ''
        if int(overdue_count) > 0:
            risk_level = 'red'
            next_action = f'First fix old follow-up dates ({int(overdue_count)} leads).'
            next_action_link = url_for('follow_up_queue')
        elif not report_done:
            risk_level = 'yellow'
            next_action = 'Send your daily report.'
            next_action_link = url_for('report_submit')
        elif int(calls_today_logged) < int(effective_target) and _is_evening_risk:
            risk_level = 'yellow'
            left = max(0, int(effective_target) - int(calls_today_logged))
            next_action = f'Log {left} more call(s) before the day ends.'
            next_action_link = url_for('leads')
        elif int(calls_today_logged) < int(effective_target):
            left = max(0, int(effective_target) - int(calls_today_logged))
            next_action = f'{left} call(s) left. You still have time today.'
            next_action_link = url_for('leads')
        elif int(pending_proof_count) > 0:
            risk_level = 'yellow'
            next_action = f'Check Rs 196 payment proofs ({int(pending_proof_count)} waiting).'
            next_action_link = url_for('enrollment_approvals')
        _is_evening = _now_ist().hour >= DAILY_CALL_ENFORCE_START_HOUR_IST
        gate_assistant = {
            'checks': checks,
            'done': done_checks,
            'total': total_checks,
            'progress_pct': progress_pct,
            'report_done': report_done,
            'overdue_count': int(overdue_count),
            'interested_no_fu': int(interested_no_fu),
            'calls_today': int(calls_today_logged),
            'call_target': int(effective_target),
            'pending_proof_count': int(pending_proof_count),
            'role': role_now,
            'risk_level': risk_level,
            'next_action': next_action,
            'next_action_link': next_action_link,
            'is_evening': _is_evening,
        }

    db.close()
    resp = make_response(render_template('dashboard.html',
                           metrics=metrics,
                           wallet=wallet,
                           recent=recent_e,
                           status_data=status_data,
                           monthly=monthly,
                           payment_amount=PAYMENT_AMOUNT,
                           today_report=today_report,
                           today=today,
                           pool_count=pool_count,
                           today_paid=today_paid,
                           today_earnings=today_earnings,
                           followups=followups,
                           notices=notices,
                           calling_reminder_time=calling_reminder_time,
                           retarget_count=retarget_count,
                           followup_count=followup_count,
                           targets_data=targets_data,
                           zoom_link=zoom_link,
                           zoom_title=zoom_title,
                           zoom_time=zoom_time,
                           funnel_leads=funnel_leads,
                           stage1_count=stage1_count,
                           day1_count=day1_count,
                           day2_count=day2_count,
                           day3_count=day3_count,
                           pending_count_pipeline=pending_count_pipeline,
                           stage1_leads=stage1_leads_e,
                           day1_leads=day1_leads_e,
                           day2_leads=day2_leads_e,
                           day3_leads=day3_leads_e,
                           pending_leads=pending_leads_e,
                           today_score=today_score,
                           today_streak=today_streak,
                           pending_batches=pending_batches,
                           batch_videos=batch_videos,
                           batch_watch_urls=_batch_watch_urls(),
                           enrollment_video_url=enrollment_video_url,
                           enrollment_watch_url=url_for('watch_enrollment', _external=True) if enrollment_video_url else '',
                           enrollment_video_title=enrollment_video_title,
                           show_day1_batches=show_day1_batches,
                           user_role=session.get('role', 'team'),
                           team_snapshot=team_snapshot,
                           leader_report_stats=leader_report_stats,
                           downline_missing_reports=downline_missing_reports,
                           call_status_values=CALL_STATUS_VALUES,
                           team_call_status_values=TEAM_CALL_STATUS_VALUES,
                           tracking_start=tracking_start,
                           my_progress_leads=my_progress_leads,
                           pipeline_auto_expire_statuses=PIPELINE_AUTO_EXPIRE_STATUSES,
                           sla_soft_watch_exclude=SLA_SOFT_WATCH_EXCLUDE,
                           csrf_token=session.get('_csrf_token', ''),
                           perf_state=perf_state or {},
                           step8_coach=step8_coach,
                           step8_leader_ai=step8_leader_ai,
                           step8_evening_line=step8_evening_line,
                           leader_today_stats=leader_today_stats,
                           leader_alerts=leader_alerts,
                           team_today_stats=team_today_stats,
                           gate_assistant=gate_assistant,
                           team_execution_funnel=team_execution_funnel,
                           team_followup_attack=team_followup_attack,
                           team_enrollment_pressure=team_enrollment_pressure))
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate'
    return resp




# ─────────────────────────────────────────────
#  My Lead Flow – status movement ledger for team / leader
# ─────────────────────────────────────────────

@app.route('/my/lead-flow')
@login_required
@safe_route
def my_lead_flow():
    """Status movement ledger: team sees own leads, leader sees own + downline."""
    role     = session.get('role')
    if role not in ('team', 'leader', 'admin'):
        return redirect(url_for('team_dashboard'))

    username = acting_username()
    user_id  = acting_user_id()
    db       = get_db()

    page    = max(1, int(request.args.get('page', 1)))
    q       = (request.args.get('q') or '').strip()
    per_page = 40

    # Build the set of user IDs whose leads we'll show
    if role == 'admin':
        uid_filter_sql = "l.in_pool=0 AND l.deleted_at=''"
        uid_params: list = []
    elif role == 'leader':
        try:
            downline = _get_network_usernames(db, username)
        except Exception:
            downline = [username]
        id_map = user_ids_for_usernames(db, downline) if downline else {}
        all_uids = list({user_id} | set(id_map.values()))
        ph = ','.join('?' * len(all_uids))
        uid_filter_sql = f"l.in_pool=0 AND l.deleted_at='' AND l.assigned_user_id IN ({ph})"
        uid_params = all_uids
    else:
        uid_filter_sql = "l.in_pool=0 AND l.deleted_at='' AND l.assigned_user_id=?"
        uid_params = [user_id]

    q_filter = ""
    q_params: list = []
    if q:
        q_filter = " AND (l.name LIKE ? OR l.phone LIKE ?)"
        q_params = [f'%{q}%', f'%{q}%']

    where = f"WHERE {uid_filter_sql}{q_filter}"
    all_params = uid_params + q_params

    total = db.execute(
        f"SELECT COUNT(DISTINCT l.id) FROM leads l {where}", all_params
    ).fetchone()[0] or 0

    leads_page = db.execute(
        f"""SELECT l.id, l.name, l.phone, l.status, l.pipeline_stage,
                   l.current_owner, l.updated_at,
                   COALESCE(u.username,'') AS assignee
            FROM leads l LEFT JOIN users u ON u.id=l.assigned_user_id
            {where}
            ORDER BY l.updated_at DESC
            LIMIT ? OFFSET ?""",
        all_params + [per_page, (page - 1) * per_page]
    ).fetchall()

    lead_ids = [r['id'] for r in leads_page]
    ph2 = ','.join('?' * len(lead_ids)) if lead_ids else '0'

    # Status-change events from lead_notes
    notes_hist = db.execute(
        f"""SELECT ln.lead_id, ln.username, ln.note, ln.created_at
            FROM lead_notes ln
            WHERE ln.lead_id IN ({ph2})
              AND (ln.note LIKE 'Status to%' OR ln.note LIKE 'Status →%'
                   OR ln.note LIKE '[Bulk] Status%' OR ln.note LIKE '%Status → %')
            ORDER BY ln.lead_id, ln.created_at DESC""",
        lead_ids
    ).fetchall() if lead_ids else []

    # Stage-transition history
    stage_hist = db.execute(
        f"""SELECT lead_id, stage, owner, triggered_by, created_at
            FROM lead_stage_history
            WHERE lead_id IN ({ph2})
            ORDER BY lead_id, created_at DESC""",
        lead_ids
    ).fetchall() if lead_ids else []

    from collections import defaultdict
    notes_by_lead: dict = defaultdict(list)
    for r in notes_hist:
        notes_by_lead[r['lead_id']].append(dict(r))
    stage_by_lead: dict = defaultdict(list)
    for r in stage_hist:
        stage_by_lead[r['lead_id']].append(dict(r))

    leads_data = []
    for r in leads_page:
        leads_data.append({
            **dict(r),
            'status_events': notes_by_lead[r['id']],
            'stage_events':  stage_by_lead[r['id']],
        })

    db.close()
    return render_template(
        'my_lead_flow.html',
        leads=leads_data,
        page=page,
        per_page=per_page,
        total=total,
        total_pages=max(1, (total + per_page - 1) // per_page),
        q=q,
        role=role,
        csrf_token=session.get('_csrf_token', ''),
    )


# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
#  Leads \u2013 List
# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

# ─────────────────────────────────────────────────────────────
#  Old Leads – Lost leads archive (can be restored / retargeted)
# ─────────────────────────────────────────────────────────────







# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
#  Leads \u2013 Quick status toggle
# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500




# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
#  Leads \u2013 Delete
# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500




# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
#  Team  (Admin only)
# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

# Report routes extracted to routes/report_routes.py

# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
#  Admin \u2013 Settings
# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

@app.route('/admin/settings', methods=['GET', 'POST'])
@admin_required
def admin_settings():
    db = get_db()
    if request.method == 'POST':
        upi_id           = request.form.get('upi_id', '').strip()
        lead_price       = request.form.get('lead_price', '50').strip()
        smtp_host        = request.form.get('smtp_host', '').strip()
        smtp_port        = request.form.get('smtp_port', '587').strip()
        smtp_user        = request.form.get('smtp_user', '').strip()
        smtp_from_name   = request.form.get('smtp_from_name', 'Myle Community').strip()
        smtp_password    = request.form.get('smtp_password', '').strip()
        anthropic_key    = request.form.get('anthropic_api_key', '').strip()
        gate_claim_discipline_enabled = '1' if request.form.get('gate_claim_discipline_enabled') else '0'
        gate_followup_discipline_enabled = '1' if request.form.get('gate_followup_discipline_enabled') else '0'
        gate_performance_discipline_enabled = '1' if request.form.get('gate_performance_discipline_enabled') else '0'
        gate_rupees_196_enabled = '1' if request.form.get('gate_rupees_196_enabled') else '0'
        strict_flow_guard_enabled = '1' if request.form.get('strict_flow_guard_enabled') else '0'

        _qr_cache.clear()
        _set_setting(db, 'upi_id', upi_id)
        _set_setting(db, 'default_lead_price', lead_price)
        _set_setting(db, 'smtp_host', smtp_host)
        _set_setting(db, 'smtp_port', smtp_port)
        _set_setting(db, 'smtp_user', smtp_user)
        _set_setting(db, 'smtp_from_name', smtp_from_name)
        _set_setting(db, 'gate_claim_discipline_enabled', gate_claim_discipline_enabled)
        _set_setting(db, 'gate_followup_discipline_enabled', gate_followup_discipline_enabled)
        _set_setting(db, 'gate_performance_discipline_enabled', gate_performance_discipline_enabled)
        _set_setting(db, 'gate_rupees_196_enabled', gate_rupees_196_enabled)
        _set_setting(db, 'strict_flow_guard_enabled', strict_flow_guard_enabled)
        if smtp_password:
            _set_setting(db, 'smtp_password', smtp_password)
        if anthropic_key:
            _set_setting(db, 'anthropic_api_key', anthropic_key)

        # ── Batch Video Links (12 new settings) ────────────────────
        batch_video_keys = [
            'batch_d1_morning_v1', 'batch_d1_morning_v2',
            'batch_d1_afternoon_v1', 'batch_d1_afternoon_v2',
            'batch_d1_evening_v1', 'batch_d1_evening_v2',
            'batch_d2_morning_v1', 'batch_d2_morning_v2',
            'batch_d2_afternoon_v1', 'batch_d2_afternoon_v2',
            'batch_d2_evening_v1', 'batch_d2_evening_v2',
        ]
        for key in batch_video_keys:
            val = request.form.get(key, '').strip()
            _set_setting(db, key, val)

        # Enrollment video (Stage 1 — visible to team + leader)
        _set_setting(db, 'enrollment_video_url', request.form.get('enrollment_video_url', '').strip())
        _set_setting(db, 'enrollment_video_title', request.form.get('enrollment_video_title', '').strip())

        # App tutorial link (sent to fully converted leads by leader)
        _set_setting(db, 'app_tutorial_link', request.form.get('app_tutorial_link', '').strip())

        # ── Call Scripts ────────────────────────────────────────────
        for _sk in ('script_opening', 'script_qualification', 'script_pitch', 'script_closing'):
            _set_setting(db, _sk, request.form.get(_sk, '').strip())

        _pdf = request.files.get('script_pdf')
        if _pdf and _pdf.filename:
            import os as _os
            _pdf_dir = _os.path.join('static', 'uploads')
            _os.makedirs(_pdf_dir, exist_ok=True)
            _safe_name = 'call_script_training.pdf'
            _pdf.save(_os.path.join(_pdf_dir, _safe_name))
            _set_setting(db, 'script_pdf_name', _safe_name)

        db.commit()
        db.close()
        flash('Settings saved successfully.', 'success')
        return redirect(url_for('admin_settings'))

    settings = {
        'upi_id':               _get_setting(db, 'upi_id'),
        'default_lead_price':   _get_setting(db, 'default_lead_price', '50'),
        'smtp_host':            _get_setting(db, 'smtp_host', 'smtp.gmail.com'),
        'smtp_port':            _get_setting(db, 'smtp_port', '587'),
        'smtp_user':            _get_setting(db, 'smtp_user'),
        'smtp_from_name':       _get_setting(db, 'smtp_from_name', 'Myle Community'),
        'smtp_password_set':     bool(_get_setting(db, 'smtp_password')),
        'anthropic_api_key_set': bool(_get_setting(db, 'anthropic_api_key') or os.environ.get('ANTHROPIC_API_KEY')),
        'gate_claim_discipline_enabled': (_get_setting(db, 'gate_claim_discipline_enabled', '1') or '1') == '1',
        'gate_followup_discipline_enabled': (_get_setting(db, 'gate_followup_discipline_enabled', '1') or '1') == '1',
        'gate_performance_discipline_enabled': (_get_setting(db, 'gate_performance_discipline_enabled', '1') or '1') == '1',
        'gate_rupees_196_enabled': (_get_setting(db, 'gate_rupees_196_enabled', '1') or '1') == '1',
        'strict_flow_guard_enabled': (_get_setting(db, 'strict_flow_guard_enabled', '1') or '1') == '1',
    }

    # ── Enrollment Video (Stage 1) ────────────────────────────────
    enrollment_video_url   = _get_setting(db, 'enrollment_video_url', '')
    enrollment_video_title = _get_setting(db, 'enrollment_video_title', 'Enrollment Video')
    app_tutorial_link      = _get_setting(db, 'app_tutorial_link', '')

    # ── Batch Video Links ────────────────────────────────────────
    batch_videos = {
        'd1_morning_v1':   _get_setting(db, 'batch_d1_morning_v1', ''),
        'd1_morning_v2':   _get_setting(db, 'batch_d1_morning_v2', ''),
        'd1_afternoon_v1': _get_setting(db, 'batch_d1_afternoon_v1', ''),
        'd1_afternoon_v2': _get_setting(db, 'batch_d1_afternoon_v2', ''),
        'd1_evening_v1':   _get_setting(db, 'batch_d1_evening_v1', ''),
        'd1_evening_v2':   _get_setting(db, 'batch_d1_evening_v2', ''),
        'd2_morning_v1':   _get_setting(db, 'batch_d2_morning_v1', ''),
        'd2_morning_v2':   _get_setting(db, 'batch_d2_morning_v2', ''),
        'd2_afternoon_v1': _get_setting(db, 'batch_d2_afternoon_v1', ''),
        'd2_afternoon_v2': _get_setting(db, 'batch_d2_afternoon_v2', ''),
        'd2_evening_v1':   _get_setting(db, 'batch_d2_evening_v1', ''),
        'd2_evening_v2':   _get_setting(db, 'batch_d2_evening_v2', ''),
    }

    call_scripts = {
        'script_opening':       _get_setting(db, 'script_opening',       ''),
        'script_qualification': _get_setting(db, 'script_qualification', ''),
        'script_pitch':         _get_setting(db, 'script_pitch',         ''),
        'script_closing':       _get_setting(db, 'script_closing',       ''),
        'pdf_name':             _get_setting(db, 'script_pdf_name',      ''),
    }

    db.close()
    return render_template('admin_settings.html', settings=settings, batch_videos=batch_videos,
                           enrollment_video_url=enrollment_video_url, enrollment_video_title=enrollment_video_title,
                           app_tutorial_link=app_tutorial_link, call_scripts=call_scripts)


# ──────────────────────────────────────────────────────────────
#  Admin – Test Email
# ──────────────────────────────────────────────────────────────

@app.route('/admin/settings/test-email', methods=['POST'])
@admin_required
def admin_test_email():
    """Send a test email to verify SMTP configuration."""
    db = get_db()
    smtp_host     = _get_setting(db, 'smtp_host', '')
    smtp_port     = int(_get_setting(db, 'smtp_port', '465') or 465)
    smtp_user     = _get_setting(db, 'smtp_user', '')
    smtp_password = _get_setting(db, 'smtp_password', '')
    from_name     = _get_setting(db, 'smtp_from_name', 'Myle Community')
    db.close()

    test_to = request.form.get('test_email', '').strip()
    if not test_to:
        flash('Please enter a recipient email address.', 'danger')
        return redirect(url_for('admin_settings'))
    if not smtp_host or not smtp_user or not smtp_password:
        flash('SMTP is not fully configured. Please fill in host, user, and password.', 'danger')
        return redirect(url_for('admin_settings'))

    html_body = f"""
    <div style="font-family:Arial,sans-serif;max-width:480px;margin:0 auto;padding:24px;background:#f8f9fa;border-radius:12px;">
      <div style="background:linear-gradient(135deg,#6366f1,#8b5cf6);border-radius:8px;padding:20px;text-align:center;margin-bottom:24px;">
        <h2 style="color:#fff;margin:0;">✅ SMTP Test</h2>
      </div>
      <p style="color:#333;">This is a test email from <strong>{from_name}</strong>.</p>
      <p style="color:#555;">If you received this, your SMTP configuration is working correctly!</p>
      <p style="color:#888;font-size:12px;">Sent via: {smtp_host}:{smtp_port} as {smtp_user}</p>
    </div>
    """
    msg = MIMEMultipart('alternative')
    msg['Subject'] = f'[{from_name}] SMTP Test Email'
    msg['From']    = f'{from_name} <{smtp_user}>'
    msg['To']      = test_to
    msg.attach(MIMEText(html_body, 'html'))

    try:
        import ssl as _ssl
        context = _ssl.create_default_context()
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.ehlo()
            server.starttls(context=context)
            server.login(smtp_user, smtp_password)
            server.sendmail(smtp_user, test_to, msg.as_string())
        flash(f'✅ Test email sent successfully to {test_to}!', 'success')
    except Exception as e:
        flash(f'❌ SMTP Error: {e}', 'danger')
    return redirect(url_for('admin_settings'))


# ──────────────────────────────────────────────────────────────
#  Admin – Test Push Notification
# ──────────────────────────────────────────────────────────────

@app.route('/admin/settings/reset-vapid', methods=['POST'])
@admin_required
def admin_reset_vapid():
    """Wipe VAPID keys AND all push subscriptions so everything starts fresh."""
    db = get_db()
    _set_setting(db, 'vapid_private_pem', '')
    _set_setting(db, 'vapid_public_key', '')
    sub_count = db.execute('SELECT COUNT(*) FROM push_subscriptions').fetchone()[0]
    db.execute('DELETE FROM push_subscriptions')
    db.commit()
    # Immediately generate a fresh key pair so the new public key is ready
    _get_or_create_vapid_keys(db)
    db.close()
    flash(f'VAPID keys reset and {sub_count} old subscription(s) cleared. '
          'All users must refresh their browser once to re-subscribe — notifications will work after that.',
          'warning')
    return redirect(url_for('admin_settings'))


@app.route('/admin/settings/test-push', methods=['POST'])
@admin_required
def admin_test_push():
    """Send a test push notification to the current admin user."""
    if not PUSH_AVAILABLE:
        flash('Push notifications are not available (pywebpush not installed).', 'danger')
        return redirect(url_for('admin_settings'))
    db = get_db()
    username = acting_username()
    subs = db.execute(
        "SELECT id FROM push_subscriptions WHERE username=?", (username,)
    ).fetchall()
    if not subs:
        db.close()
        flash('No push subscription found for your account. Please click the bell icon to enable notifications first.', 'warning')
        return redirect(url_for('admin_settings'))
    _push_to_users(db, username,
                   title='✅ Push Test Successful!',
                   body='Push notifications are working correctly on your Myle Dashboard.',
                   url='/admin/settings')
    db.commit()
    db.close()
    flash('Test push notification sent! Check your browser/device notifications.', 'success')
    return redirect(url_for('admin_settings'))


@app.route('/admin/settings/test-calling-reminder', methods=['POST'])
@admin_required
def admin_test_calling_reminder():
    """Trigger the calling reminder job immediately for debugging."""
    if not SCHEDULER_AVAILABLE:
        flash('Scheduler (APScheduler) is not available — calling reminders cannot run.', 'danger')
        return redirect(url_for('admin_settings'))
    if not PUSH_AVAILABLE:
        flash('Push notifications are not available (pywebpush not installed).', 'danger')
        return redirect(url_for('admin_settings'))
    try:
        job_calling_reminder()
        ist_now = _now_ist()
        flash(
            f'Calling reminder job executed at {ist_now.strftime("%H:%M")} IST. '
            'If any users had this time set as their reminder, they received a notification.',
            'success'
        )
    except Exception as ex:
        flash(f'Calling reminder job error: {ex}', 'danger')
    return redirect(url_for('admin_settings'))


# ──────────────────────────────────────────────────────────────
#  Admin – Edit Member (username / email) + Permanent Delete
# ──────────────────────────────────────────────────────────────

@app.route('/admin/members/<username>/edit', methods=['POST'])
@admin_required
def admin_edit_member(username):
    """Change a member's username and/or email address."""
    db = get_db()
    member = db.execute("SELECT id, username, email FROM users WHERE username=?", (username,)).fetchone()
    if not member:
        db.close()
        flash('Member not found.', 'danger')
        return redirect(url_for('admin_members'))

    new_username = request.form.get('new_username', '').strip().lower()
    new_email    = request.form.get('new_email', '').strip().lower()

    errors = []

    if new_username and new_username != username:
        # Check uniqueness
        existing = db.execute("SELECT id FROM users WHERE username=? AND id!=?", (new_username, member['id'])).fetchone()
        if existing:
            errors.append(f'Username @{new_username} is already taken.')
        elif len(new_username) < 3:
            errors.append('Username must be at least 3 characters.')
        else:
            # Leads use assigned_user_id (FK); username change is users row only.
            try:
                db.execute("UPDATE leads SET added_by=? WHERE added_by=?", (new_username, username))
            except Exception:
                pass
            db.execute("UPDATE wallet_recharges SET username=? WHERE username=?", (new_username, username))
            db.execute("UPDATE push_subscriptions SET username=? WHERE username=?", (new_username, username))
            db.execute("UPDATE daily_reports SET username=? WHERE username=?", (new_username, username))
            try:
                db.execute("UPDATE lead_notes SET username=? WHERE username=?", (new_username, username))
            except Exception:
                pass
            try:
                db.execute("UPDATE activity_log SET username=? WHERE username=?", (new_username, username))
            except Exception:
                pass
            db.execute("UPDATE users SET username=? WHERE id=?", (new_username, member['id']))
            flash(f'Username changed from @{username} to @{new_username}.', 'success')
            username = new_username  # use new username for redirect

    if new_email:
        # Check uniqueness
        existing = db.execute("SELECT id FROM users WHERE LOWER(email)=? AND id!=?", (new_email, member['id'])).fetchone()
        if existing:
            errors.append(f'Email {new_email} is already in use by another account.')
        else:
            db.execute("UPDATE users SET email=? WHERE id=?", (new_email, member['id']))
            flash(f'Email updated to {new_email}.', 'success')

    for err in errors:
        flash(err, 'danger')

    db.commit()
    _mid = int(member['id'])
    if session.get('user_id') is not None and int(session['user_id']) == _mid:
        refresh_session_user(_mid)
    db.close()
    return redirect(url_for('member_detail', username=username))


@app.route('/admin/members/<username>/delete', methods=['POST'])
@admin_required
def admin_delete_member(username):
    """Permanently delete a member and all their data from the database."""
    db = get_db()
    member = db.execute("SELECT id, username FROM users WHERE username=? AND role='team'", (username,)).fetchone()
    if not member:
        db.close()
        flash('Member not found or cannot delete admin accounts.', 'danger')
        return redirect(url_for('admin_members'))

    confirm = request.form.get('confirm_username', '').strip()
    if confirm != username:
        db.close()
        flash('Confirmation username did not match. Member was NOT deleted.', 'danger')
        return redirect(url_for('member_detail', username=username))

    owned_lead_count = db.execute(
        """
        SELECT COUNT(*) FROM leads
        WHERE in_pool=0 AND deleted_at=''
          AND (
              assigned_user_id=?
              OR TRIM(COALESCE(current_owner,''))=?
          )
        """,
        (member['id'], username),
    ).fetchone()[0] or 0
    if owned_lead_count:
        db.close()
        flash(
            f'Cannot delete @{username}. They still own active claimed leads, and claimed leads can never return to the pool.',
            'danger',
        )
        return redirect(url_for('member_detail', username=username))

    # Delete all member data
    db.execute("DELETE FROM wallet_recharges WHERE username=?", (username,))
    db.execute("DELETE FROM push_subscriptions WHERE username=?", (username,))
    db.execute("DELETE FROM daily_reports WHERE username=?", (username,))
    try:
        db.execute("DELETE FROM activity_log WHERE username=?", (username,))
    except Exception:
        pass
    db.execute("DELETE FROM users WHERE id=?", (member['id'],))
    db.commit()
    db.close()
    flash(f'Member @{username} has been permanently deleted.', 'success')
    return redirect(url_for('admin_members'))


# ──────────────────────────────────────────────────────────────
#  Admin – Monthly Targets
# ──────────────────────────────────────────────────────────────

@app.route('/admin/targets', methods=['GET', 'POST'])
@admin_required
def admin_targets():
    db    = get_db()
    month = request.args.get('month', _now_ist().strftime('%Y-%m'))

    if request.method == 'POST':
        month_p = request.form.get('month', month)
        members = db.execute(
            "SELECT username FROM users WHERE role='team' AND status='approved' ORDER BY username"
        ).fetchall()
        for m in members:
            uname = m['username']
            for metric in ('leads', 'payments', 'conversions', 'revenue'):
                val = request.form.get(f'{uname}_{metric}', '').strip()
                if val:
                    try:
                        db.execute("""
                            INSERT INTO targets (username, metric, target_value, month, created_by)
                            VALUES (?,?,?,?,?)
                            ON CONFLICT(username, metric, month)
                            DO UPDATE SET target_value=excluded.target_value
                        """, (uname, metric, float(val), month_p, acting_username()))
                    except Exception:
                        pass
        db.commit()
        flash('Targets saved!', 'success')
        db.close()
        return redirect(url_for('admin_targets', month=month_p))

    members = db.execute(
        "SELECT username FROM users WHERE role='team' AND status='approved' ORDER BY username"
    ).fetchall()
    targets_map = {}
    rows = db.execute(
        "SELECT username, metric, target_value FROM targets WHERE month=?", (month,)
    ).fetchall()
    for r in rows:
        targets_map[(r['username'], r['metric'])] = r['target_value']

    db.close()
    return render_template('admin_targets.html',
                           members=members,
                           targets_map=targets_map,
                           month=month)


# ──────────────────────────────────────────────────────────────
#  Admin – Budget Summary Export (CSV)
# ──────────────────────────────────────────────────────────────

@app.route('/admin/budget-export')
@admin_required
def admin_budget_export():
    """Export wallet/lead budget summary for all members as CSV with optional date range."""
    import csv, io as _io
    # If no download param, show the filter page
    if not request.args.get('download'):
        db = get_db()
        member_count = db.execute("SELECT COUNT(*) FROM users WHERE role='team' AND status='approved'").fetchone()[0]
        db.close()
        return render_template(
            'budget_export.html',
            member_count=member_count,
            ist_today=_today_ist().isoformat(),
        )
    db = get_db()

    date_from = request.args.get('date_from', '')
    date_to   = request.args.get('date_to', '')

    recharge_filter = "status='approved'"
    recharge_params = []

    if date_from:
        recharge_filter += " AND processed_at >= ?"
        recharge_params.append(date_from)
    if date_to:
        recharge_filter += " AND processed_at <= ?"
        recharge_params.append(date_to + ' 23:59:59')

    _claimed_max = (date_to + ' 23:59:59') if date_to else None

    members = db.execute(
        "SELECT username, email, fbo_id, phone FROM users WHERE role='team' AND status='approved' ORDER BY username"
    ).fetchall()

    output = _io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        'Username', 'Email', 'FBO ID', 'Phone',
        'Total Recharged (₹)', 'Total Spent on Leads (₹)', 'Wallet Balance (₹)',
        'Leads Claimed (count)', 'Admin Adjustments (₹)',
        'Date From', 'Date To'
    ])

    for m in members:
        uname = m['username']

        # Total wallet recharged (approved, excluding admin manual rows — UTR prefix ADMIN-ADJUST…)
        total_recharged = db.execute(
            f"SELECT COALESCE(SUM(amount),0) FROM wallet_recharges WHERE username=? AND {recharge_filter} "
            f"AND utr_number NOT LIKE 'ADMIN-ADJUST%'",
            [uname] + recharge_params
        ).fetchone()[0] or 0.0

        # Admin adjustments separately (manual rows use ADMIN-ADJUST or ADMIN-ADJUST-<timestamp>-…)
        admin_adj = db.execute(
            f"SELECT COALESCE(SUM(amount),0) FROM wallet_recharges WHERE username=? AND status='approved' "
            f"AND utr_number LIKE 'ADMIN-ADJUST%'",
            [uname]
        ).fetchone()[0] or 0.0

        total_spent = sum_pool_spent_for_buyer(
            db, uname, claimed_at_min=date_from or None, claimed_at_max=_claimed_max
        )
        leads_count = count_buyer_claimed_leads(
            db, uname, claimed_at_min=date_from or None, claimed_at_max=_claimed_max
        )

        # Current wallet balance (always full, not date-filtered)
        wallet = _get_wallet(db, uname)
        balance = wallet['balance']

        writer.writerow([
            uname, m['email'] or '', m['fbo_id'] or '', m['phone'] or '',
            f"{total_recharged:.2f}", f"{total_spent:.2f}", f"{balance:.2f}",
            leads_count, f"{admin_adj:.2f}",
            date_from or 'All time', date_to or 'All time'
        ])

    db.close()
    output.seek(0)
    from flask import Response
    filename = f"budget_summary_{date_from or 'all'}_{date_to or 'all'}.csv"
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'}
    )


@app.route('/admin/upi-qr-preview')
@admin_required
def admin_upi_qr_preview():
    """Serve UPI QR code PNG for admin settings preview."""
    db     = get_db()
    upi_id = _get_setting(db, 'upi_id', '')
    db.close()
    img_bytes = _generate_upi_qr_bytes(upi_id)
    if not img_bytes:
        return 'QR not available', 404
    return Response(img_bytes, mimetype='image/png')



# ─────────────────────────────────────────────────
#  Team – Wallet / Lead Pool / Calling Reminder (see routes/wallet_routes.py)
# ─────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────
#  Profile / password / help / earnings (see routes/profile_routes.py)
# ─────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────
#  CSV Export
# ─────────────────────────────────────────────




# ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
#  Leads – Bulk Import (CSV / PDF)
# ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────


@app.route('/admin/users/<int:user_id>/reset-password', methods=['POST'])
@admin_required
def admin_reset_password(user_id):
    new_pw = request.form.get('new_password', '').strip()
    if len(new_pw) < 6:
        flash('Password must be at least 6 characters.', 'danger')
        return redirect(url_for('admin_approvals'))
    db   = get_db()
    user = db.execute("SELECT username FROM users WHERE id=?", (user_id,)).fetchone()
    if user:
        db.execute("UPDATE users SET password=? WHERE id=?",
                   (generate_password_hash(new_pw, method='pbkdf2:sha256'), user_id))
        db.commit()
        flash(f'Password for @{user["username"]} reset successfully.', 'success')
    db.close()
    return redirect(url_for('admin_approvals'))


# ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
#  Lead Notes / Timeline
# ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────







# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
#  Bulk Actions on Leads
# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500



# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
#  Push Notification API
# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500





# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
#  Scheduled Reminder Jobs
# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

def _reminder_lock(db, key):
    today = _today_ist().isoformat()   # IST date
    lock_key = f'{key}_{today}'
    cur = db.execute(
        "INSERT OR IGNORE INTO app_settings (key, value) VALUES (?, 'sent')",
        (lock_key,)
    )
    db.commit()
    return cur.rowcount == 1


def job_followup_reminders():
    """Push individual follow-up reminders to each team member at 9 AM IST."""
    db = get_db()
    try:
        if not _reminder_lock(db, 'followup_reminder'):
            return
        today = _today_ist().isoformat()
        rows = db.execute("""
            SELECT u.username AS assignee_username, COUNT(*) as cnt
            FROM leads l
            JOIN users u ON u.id = l.assigned_user_id
            WHERE l.in_pool=0
              AND l.follow_up_date=?
              AND l.follow_up_date != ''
              AND l.status NOT IN ('Converted','Fully Converted','Lost','Retarget','Inactive')
            GROUP BY u.username
        """, (today,)).fetchall()
        for row in rows:
            cnt = row['cnt']
            un = (row['assignee_username'] or '').strip()
            if not un:
                continue
            _push_to_users(db, un,
                           '\U0001f4c5 Follow-up Reminder',
                           f'{cnt} lead{"s" if cnt > 1 else ""} due for follow-up today!',
                           '/dashboard')
        db.commit()
    finally:
        db.close()


def job_calling_reminder():
    """
    Minutely job: push calling reminder to each user whose calling_reminder_time
    matches the current HH:MM (IST). Per-user per-day lock prevents duplicates.
    """
    ist_now  = _now_ist()
    now_hhmm = ist_now.strftime('%H:%M')
    today    = _today_ist().isoformat()   # IST date — must match IST time, not server UTC
    db = get_db()
    try:
        users = db.execute(
            "SELECT username FROM users WHERE role='team' AND status='approved'"
            " AND calling_reminder_time=?", (now_hhmm,)
        ).fetchall()
        for u in users:
            lock_key = f'call_reminder_{u["username"]}_{today}'
            cur = db.execute(
                "INSERT OR IGNORE INTO app_settings (key, value) VALUES (?, 'sent')",
                (lock_key,)
            )
            db.commit()
            if cur.rowcount == 1:
                app.logger.info(f'[Scheduler] Calling reminder sent @{u["username"]} at {now_hhmm} IST')
                _push_to_users(db, u['username'],
                               '\U0001f4de Calling Reminder',
                               'Time to start your calls! Don\'t forget your daily report.',
                               '/reports/submit')
                db.commit()
    finally:
        db.close()


# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
#  Boot \u2013 runs on every startup
# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500



def migrate_pipeline_stages(db):
    """One-time startup migration: sync pipeline_stage while preserving permanent owner."""
    leads = db.execute("""
        SELECT id, status, assigned_user_id, pipeline_stage, current_owner, claimed_at
        FROM leads WHERE in_pool=0 AND deleted_at=''
    """).fetchall()
    _mig_now = _now_ist().strftime('%Y-%m-%d %H:%M:%S')
    for lead in leads:
        # Legacy normalization: "Paid ₹196" is now treated as Day 1 everywhere
        # (older data may still have the old status value).
        if lead['status'] == 'Paid ₹196':
            try:
                full = db.execute("SELECT * FROM leads WHERE id=?", (lead['id'],)).fetchone()
                if full:
                    _pd, _pa = payment_columns_mark_paid(full)
                    db.execute(
                        "UPDATE leads SET status='Day 1', payment_done=?, payment_amount=?, updated_at=? WHERE id=?",
                        (_pd, _pa, _mig_now, lead['id']),
                    )
            except Exception:
                pass
        current_stage = lead['pipeline_stage'] if 'pipeline_stage' in lead.keys() else ''
        # If we normalized status above, re-read expected stage accordingly
        expected_status = 'Day 1' if lead['status'] == 'Paid ₹196' else lead['status']
        expected_stage = STATUS_TO_STAGE.get(expected_status, 'prospecting')
        needs_update = (not current_stage or current_stage == '' or current_stage != expected_stage)
        if needs_update:
            stage = expected_stage
            owner = lead['current_owner'] if 'current_owner' in lead.keys() else ''
            _au = _assignee_username_for_lead(db, lead)
            claimed_at = (lead['claimed_at'] if 'claimed_at' in lead.keys() else '') or ''
            if not owner and not str(claimed_at).strip():
                owner = _au or _get_admin_username(db) or ''
            if owner:
                db.execute(
                    "UPDATE leads SET pipeline_stage=?, current_owner=?, updated_at=? WHERE id=?",
                    (stage, owner, _mig_now, lead['id']),
                )
            else:
                db.execute(
                    "UPDATE leads SET pipeline_stage=?, updated_at=? WHERE id=?",
                    (stage, _mig_now, lead['id']),
                )
    db.commit()

init_db()
migrate_db()
seed_users()
seed_training_questions()
try:
    _ff = (os.environ.get('STARTUP_FAIL_FAST') or '').strip().lower() in ('1', 'true', 'yes', 'on')
    startup_invariant_scan(fail_fast=_ff)
except Exception as _e:
    import sys
    print(f'[Startup] invariant scan failed: {_e}', file=sys.stderr)
    if (os.environ.get('STARTUP_FAIL_FAST') or '').strip().lower() in ('1', 'true', 'yes', 'on'):
        raise

# Sync existing leads to pipeline stages
try:
    _boot_db = get_db()
    migrate_pipeline_stages(_boot_db)
    _boot_db.close()
except Exception as _e:
    import sys
    print(f'[Pipeline] migrate_pipeline_stages failed: {_e}', file=sys.stderr)

# ── One-time data fix: repair stuck leads ────────────────────────────────
try:
    _fix_db = get_db()
    _fix_now = _now_ist().strftime('%Y-%m-%d %H:%M:%S')

    # Fix 1: Leads with Paid ₹196 status + approved proof but NOT in Day 1
    _stuck_paid = _fix_db.execute("""
        SELECT l.id, l.assigned_user_id, COALESCE(u.username,'') AS assignee_un,
               COALESCE(u.role,'') AS assignee_role
        FROM leads l
        LEFT JOIN users u ON u.id = l.assigned_user_id
        WHERE l.in_pool=0 AND l.deleted_at=''
          AND l.status = 'Paid ₹196'
          AND l.pipeline_stage != 'day1'
          AND TRIM(COALESCE(l.payment_proof_path,'')) != ''
          AND LOWER(COALESCE(l.payment_proof_approval_status,'')) = 'approved'
    """).fetchall()
    for _sl in _stuck_paid:
        _aun = (_sl['assignee_un'] or '').strip()
        _fix_db.execute("""
            UPDATE leads SET status='Day 1', pipeline_stage='day1',
                updated_at=?, pipeline_entered_at=?
            WHERE id=?
        """, (_fix_now, _fix_now, _sl['id']))
        _fix_db.execute(
            "UPDATE leads SET enrolled_at=?, enrolled_by=? WHERE id=? AND TRIM(COALESCE(enrolled_at,''))=''",
            (_fix_now, _aun, _sl['id']),
        )

    # Fix 2: Day 1 leads with all 3 batches done but still status='Day 1'
    _stuck_d1 = _fix_db.execute("""
        SELECT l.id FROM leads l
        WHERE l.in_pool=0 AND l.deleted_at=''
          AND l.status = 'Day 1'
          AND l.d1_morning = 1 AND l.d1_afternoon = 1 AND l.d1_evening = 1
          AND l.pipeline_stage = 'day1'
    """).fetchall()
    for _sd in _stuck_d1:
        _fix_db.execute("""
            UPDATE leads SET status='Day 2', pipeline_stage='day2',
                updated_at=?, pipeline_entered_at=?
            WHERE id=?
        """, (_fix_now, _fix_now, _sd['id']))

    _fix_db.commit()
    _fc = len(_stuck_paid) + len(_stuck_d1)
    if _fc:
        print(f'[DataFix] Repaired {len(_stuck_paid)} stuck paid leads → Day 1, '
              f'{len(_stuck_d1)} stuck Day 1 leads → Day 2', file=sys.stderr)
    _fix_db.close()
except Exception as _e:
    import sys
    print(f'[DataFix] startup data fix failed: {_e}', file=sys.stderr)

# ── Global pipeline expiry job ───────────────────────────────────────────────

def job_pipeline_expire():
    """
    Hourly scheduled job: auto-expire ALL leads that have been stuck at any
    active pipeline stage for 24+ hours, across EVERY user.
    Leads in terminal stages (Converted/Fully Converted/Lost/Inactive/Pending)
    are never touched.
    """
    from helpers import PIPELINE_AUTO_EXPIRE_STATUSES, _now_ist, _log_activity
    from datetime import timedelta
    db = get_db()
    try:
        cutoff = (_now_ist() - timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')
        placeholders = ','.join('?' * len(PIPELINE_AUTO_EXPIRE_STATUSES))
        expired = db.execute(f"""
            SELECT l.id, l.name, COALESCE(u.username, '') AS assignee_username
            FROM leads l
            LEFT JOIN users u ON u.id = l.assigned_user_id
            WHERE l.in_pool=0 AND l.deleted_at=''
            AND l.status IN ({placeholders})
            AND COALESCE(NULLIF(TRIM(l.pipeline_entered_at),''), l.updated_at) < ?
        """, (*PIPELINE_AUTO_EXPIRE_STATUSES, cutoff)).fetchall()

        now_str = _now_ist().strftime('%Y-%m-%d %H:%M:%S')
        count = 0
        for lead in expired:
            db.execute("""
                UPDATE leads
                SET status='Inactive', pipeline_stage='inactive', updated_at=?
                WHERE id=?
            """, (now_str, lead['id']))
            _log_activity(db, 'system', 'pipeline_expired',
                          f'Lead #{lead["id"]} ({lead["name"]}) → Inactive '
                          f'after 24h at stage (owner: {lead["assignee_username"]})')
            # Also log under the assignee so they can see it in their own activity feed
            if lead['assignee_username']:
                _log_activity(db, lead['assignee_username'], 'pipeline_expired',
                              f'Lead "{lead["name"]}" (#{lead["id"]}) was auto-moved to Inactive '
                              f'after 24h without a status update.')
            count += 1

        if count:
            db.commit()
            app.logger.info(f'[pipeline_expire] Moved {count} stale leads → Inactive')
    except Exception as e:
        app.logger.error(f'[pipeline_expire] Error: {e}')
    finally:
        db.close()


def job_payment_health_repair():
    """Daily: fix payment_done=1 with invalid payment_amount (safe normalize)."""
    db = get_db()
    try:
        r = repair_lead_payment_invariants(db)
        db.commit()
        if r.get('payment_rows_repaired'):
            app.logger.info('[payment_health] Repaired %s row(s)', r['payment_rows_repaired'])
    except Exception as e:
        app.logger.error('[payment_health] Error: %s', e)
    finally:
        db.close()


# ── Daily leaderboard pressure summary (9 PM IST) ───────────────────────────

DAILY_TARGETS = {'calls': 5, 'batches': 3, 'videos': 3}

def _build_leaderboard_message(rows: list, today_str: str):
    """
    Build a WhatsApp-style leaderboard summary string from ordered daily rows.
    rows must be sorted by today_pts DESC (best first).
    Returns (message_text, top3_list, bottom5_list).
    """
    total = len(rows)
    medals = ['🥇', '🥈', '🥉']

    lines = [
        f"📊 *Daily Leaderboard — {today_str}*",
        "",
        "🏆 *Top Performers*",
    ]

    top3    = [rows[i] for i in range(min(3, total))]
    bottom5 = [rows[i] for i in range(max(0, total - 5), total)]
    bottom5_names = {r['username'] for r in bottom5}

    for i, r in enumerate(top3):
        medal   = medals[i] if i < 3 else f"{i+1}."
        pts     = r['today_pts']
        calls   = r['calls']
        batches = r['batches']
        videos  = r['videos']

        # Target check
        hits   = sum([calls >= DAILY_TARGETS['calls'],
                      batches >= DAILY_TARGETS['batches'],
                      videos >= DAILY_TARGETS['videos']])
        status = "✅ Target Achieved" if hits == 3 else f"🔥 {hits}/3 targets hit"

        lines.append(
            f"{medal} *{r['username']}* — {pts} pts | "
            f"📞 {calls}/5  📦 {batches}/3  🎥 {videos}/3 | {status}"
        )

    lines += ["", "📉 *Needs Improvement*"]

    top3_names   = {r['username'] for r in top3}
    shown_bottom = [r for r in rows
                    if r['username'] in bottom5_names
                    and r['username'] not in top3_names]
    if not shown_bottom:
        shown_bottom = bottom5  # tiny team overlap

    for r in shown_bottom:
        pts     = r['today_pts']
        calls   = r['calls']
        batches = r['batches']
        videos  = r['videos']
        below   = []
        if calls   < DAILY_TARGETS['calls']:    below.append(f"Calls {calls}/{DAILY_TARGETS['calls']}")
        if batches < DAILY_TARGETS['batches']:  below.append(f"Batches {batches}/{DAILY_TARGETS['batches']}")
        if videos  < DAILY_TARGETS['videos']:   below.append(f"Videos {videos}/{DAILY_TARGETS['videos']}")
        tag = "⚠️ Below Target → " + " | ".join(below) if below else "✅ Target Achieved"
        lines.append(f"🔴 *{r['username']}* — {pts} pts | {tag}")

    lines += [
        "",
        f"👥 Active team: {total}",
        "💪 Keep pushing! Tomorrow is a new chance.",
        "— Myle Team 🚀",
    ]

    top3_out    = [{'username': r['username'], 'today_pts': r['today_pts'], 'tag': 'Top Performer'}    for r in top3]
    bottom5_out = [{'username': r['username'], 'today_pts': r['today_pts'], 'tag': 'Needs Improvement'} for r in shown_bottom]
    return "\n".join(lines), top3_out, bottom5_out


def job_leaderboard_summary():
    """
    9 PM IST daily job:
    - Queries today's scores for all approved team members
    - Builds a WhatsApp-style pressure message
    - Saves to leaderboard_summaries table
    - Pushes top-3 'Top Performer' and bottom-5 'Needs Improvement' notifications
    """
    import json as _json
    from helpers import _today_ist

    db = get_db()
    try:
        if not _reminder_lock(db, 'leaderboard_summary'):
            return

        today_str = _today_ist().isoformat()

        rows = db.execute("""
            SELECT u.username,
                   COALESCE(ds.total_points,   0) AS today_pts,
                   COALESCE(ds.calls_made,     0) AS calls,
                   COALESCE(ds.batches_marked, 0) AS batches,
                   COALESCE(ds.videos_sent,    0) AS videos,
                   COALESCE(ds.streak_days,    0) AS streak
            FROM users u
            LEFT JOIN daily_scores ds
                   ON ds.username = u.username AND ds.score_date = ?
            WHERE u.role='team' AND u.status='approved'
              AND IFNULL(u.idle_hidden, 0) = 0
            ORDER BY today_pts DESC
        """, (today_str,)).fetchall()

        if not rows:
            app.logger.info('[leaderboard_summary] No team members — skipping.')
            return

        rows = [dict(r) for r in rows]
        message, top3, bottom5 = _build_leaderboard_message(rows, today_str)

        # Save to DB (upsert by date)
        db.execute(f"""
            INSERT INTO leaderboard_summaries (summary_date, message, top3_json, bottom5_json)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(summary_date) DO UPDATE
              SET message=excluded.message,
                  top3_json=excluded.top3_json,
                  bottom5_json=excluded.bottom5_json,
                  created_at={SQLITE_NOW_IST}
        """, (today_str, message, _json.dumps(top3), _json.dumps(bottom5)))
        db.commit()

        # Push notifications — top 3
        for r in top3:
            _push_to_users(db, r['username'],
                           '🏆 Top Performer Today!',
                           f"You ranked in the top 3 today with {r['today_pts']} pts. Keep it up!",
                           '/leaderboard')

        # Push notifications — bottom 5 (skip if same user as top3 on tiny teams)
        top3_names = {r['username'] for r in top3}
        for r in bottom5:
            if r['username'] not in top3_names:
                _push_to_users(db, r['username'],
                               '📉 Needs Improvement',
                               f"Today's score: {r['today_pts']} pts. You can do better — let's go!",
                               '/leaderboard')

        app.logger.info(
            f'[leaderboard_summary] Summary saved for {today_str}. '
            f'Top3={[r["username"] for r in top3]}  '
            f'Bottom5={[r["username"] for r in bottom5]}'
        )
    except Exception as e:
        app.logger.error(f'[leaderboard_summary] Error: {e}')
    finally:
        db.close()


def job_admin_decision_engine():
    """
    9:05 PM IST daily (after leaderboard job):
    Step 6 — decision snapshot per user.
    Step 7 — auto-remove, final-warning streak, idle_hidden, pressure digest + audit log.
    """
    import json as _json
    from collections import defaultdict

    from helpers import (
        build_step7_pressure_digest,
        classify_admin_decision,
        compute_admin_decision_metrics,
        log_system_auto_action,
        step7_apply_idle_hidden_flags,
        _set_setting,
        _today_ist,
    )

    db = get_db()
    try:
        if not _reminder_lock(db, 'admin_decision_engine'):
            return
        today_str = _today_ist().isoformat()
        yest = (_today_ist() - datetime.timedelta(days=1)).isoformat()

        users = db.execute(
            "SELECT username FROM users WHERE role IN ('team','leader') AND status='approved'"
        ).fetchall()
        buckets: dict = defaultdict(list)

        for r in users:
            uname = r['username']
            m = compute_admin_decision_metrics(db, uname)
            cls, det = classify_admin_decision(m)
            payload = dict(m)
            payload['decision_class'] = cls
            payload['detail'] = det
            buckets[cls].append(payload)

            db.execute(
                f"""
                INSERT INTO admin_decision_snapshots
                    (snapshot_date, username, decision_class, detail, metrics_json)
                VALUES (?,?,?,?,?)
                ON CONFLICT(snapshot_date, username) DO UPDATE SET
                    decision_class=excluded.decision_class,
                    detail=excluded.detail,
                    metrics_json=excluded.metrics_json,
                    created_at={SQLITE_NOW_IST}
                """,
                (today_str, uname, cls, det, _json.dumps(payload, default=str)),
            )

            if cls == 'remove' and not m.get('in_grace'):
                cur = db.execute(
                    "SELECT access_blocked, discipline_status FROM users WHERE username=?",
                    (uname,),
                ).fetchone()
                ds_cur = (cur['discipline_status'] or '').strip() if cur else ''
                if ds_cur == 'grace':
                    pass
                else:
                    already = bool(cur and (
                        int(cur['access_blocked'] or 0) != 0 or ds_cur == 'removed'
                    ))
                    db.execute(
                        """
                        UPDATE users SET access_blocked=1, discipline_status='removed'
                        WHERE username=?
                          AND IFNULL(TRIM(discipline_status), '') != 'grace'
                        """,
                        (uname,),
                    )
                    if not already:
                        log_system_auto_action(db, 'auto_removed_by_system', uname, det)

            prev = db.execute(
                """
                SELECT decision_class FROM admin_decision_snapshots
                WHERE username=? AND snapshot_date=?
                """,
                (uname, yest),
            ).fetchone()
            prev_cls = (prev['decision_class'] if prev else '') or ''

            if cls == 'critical' and prev_cls == 'critical':
                fw_row = db.execute(
                    "SELECT COALESCE(final_warning_given, 0) AS f FROM users WHERE username=?",
                    (uname,),
                ).fetchone()
                if fw_row and int(fw_row['f'] or 0) == 0:
                    db.execute(
                        "UPDATE users SET final_warning_given=1 WHERE username=?",
                        (uname,),
                    )
                    log_system_auto_action(
                        db, 'final_warning_given', uname, '2 consecutive CRITICAL classes',
                    )
                    try:
                        _push_to_users(
                            db,
                            uname,
                            'Final warning',
                            '24 hours to improve — fix activity and follow-ups.',
                            '/dashboard',
                        )
                    except Exception:
                        pass
            elif cls != 'critical':
                db.execute(
                    "UPDATE users SET final_warning_given=0 WHERE username=?",
                    (uname,),
                )

        step7_apply_idle_hidden_flags(db)

        pressure = build_step7_pressure_digest(dict(buckets), today_str)
        _set_setting(db, 'step7_daily_pressure_json', _json.dumps(pressure, ensure_ascii=False))
        log_system_auto_action(db, 'daily_pressure_generated', '', f'date={today_str}')

        db.commit()
        app.logger.info(
            '[admin_decision_engine] Step 6+7 done for %s (%s users)', today_str, len(users)
        )
    except Exception as e:
        app.logger.error('[admin_decision_engine] Error: %s', e)
    finally:
        db.close()


def job_stale_lead_redistribution():
    """
    Every 24h: auto-assign stale leads (24h+ no update) to top-5 team members
    by all-time points. Zero-risk — assigned_user_id is never touched.
    """
    from execution_enforcement import stale_redistribute
    db = get_db()
    try:
        result = stale_redistribute(db, stale_hours=24, top_n=5, actor='auto')
        app.logger.info(
            '[stale_redistrib] assigned=%s skipped=%s',
            result['assigned'], result['skipped']
        )
        # Log to original owner's activity feed so they know a helper was assigned
        for lead_id, owner_username, stale_worker in result.get('assignments', []):
            if owner_username:
                _log_activity(
                    db, owner_username, 'stale_worker_assigned',
                    f'Lead #{lead_id} was idle 48h+ — @{stale_worker} assigned to assist. '
                    f'Update this lead to reclaim full ownership.',
                )
        if result.get('assignments'):
            db.commit()
        # Push notification to each worker who received leads
        for _worker, _cnt in (result.get('worker_counts') or {}).items():
            def _bg_auto_push(u, cnt):
                _db = get_db()
                try:
                    _push_to_users(_db, u, 'Leads assigned to you',
                                   f'{cnt} lead{"s" if cnt != 1 else ""} auto-assigned to you. Check My Leads.',
                                   '/leads')
                finally:
                    _db.close()
            threading.Thread(target=_bg_auto_push, args=(_worker, _cnt), daemon=True).start()
    except Exception as e:
        app.logger.error('[stale_redistrib] Error: %s', e, exc_info=True)
    finally:
        db.close()


# ── Scheduler startup ───────────────────────────────────────────────────────
# start_scheduler() uses a file lock so exactly ONE worker process runs it.
# gunicorn.conf.py post_fork hook calls this after each fork.

_scheduler = None


def start_scheduler():
    """Start APScheduler (idempotent, file-lock guarded for multi-worker gunicorn)."""
    global _scheduler
    if not SCHEDULER_AVAILABLE:
        app.logger.warning('[Scheduler] APScheduler not available — reminders disabled.')
        return
    if _scheduler is not None and _scheduler.running:
        return

    import fcntl
    lock_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.scheduler.lock')
    try:
        lock_fd = open(lock_path, 'w')
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        lock_fd.write(str(os.getpid()))
        lock_fd.flush()
    except OSError:
        app.logger.info('[Scheduler] Another worker owns the scheduler lock — skipping.')
        return

    _scheduler = BackgroundScheduler(timezone='Asia/Kolkata')
    _scheduler.add_job(job_followup_reminders, 'cron', hour=9, minute=0,
                       id='followup_reminders', replace_existing=True)
    _scheduler.add_job(job_calling_reminder, 'interval', minutes=1,
                       id='calling_reminder', replace_existing=True)
    _scheduler.add_job(job_pipeline_expire, 'interval', hours=1,
                       id='pipeline_expire', replace_existing=True)
    _scheduler.add_job(job_leaderboard_summary, 'cron', hour=21, minute=0,
                       id='leaderboard_summary', replace_existing=True)
    _scheduler.add_job(job_admin_decision_engine, 'cron', hour=21, minute=5,
                       id='admin_decision_engine', replace_existing=True)
    _scheduler.add_job(job_payment_health_repair, 'cron', hour=3, minute=30,
                       id='payment_health_repair', replace_existing=True)
    _scheduler.add_job(job_stale_lead_redistribution, 'interval', hours=24,
                       id='stale_lead_redistrib', replace_existing=True)
    _scheduler.start()
    app.logger.info(f'[Scheduler] Started in PID {os.getpid()}')

    def _shutdown():
        try:
            _scheduler.shutdown(wait=False)
        except Exception:
            pass
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            lock_fd.close()
            os.unlink(lock_path)
        except Exception:
            pass

    atexit.register(_shutdown)


# Auto-start for Flask dev server / single-worker gunicorn.
# Multi-worker gunicorn uses gunicorn.conf.py post_fork hook instead.
if not os.environ.get('GUNICORN_MULTI_WORKER'):
    start_scheduler()



# ─────────────────────────────────────────────────────────────
#  Live Session (team) (see routes/social_routes.py)
# ─────────────────────────────────────────────────────────────

@app.route('/admin/live-session', methods=['GET', 'POST'])
@admin_required
def admin_live_session():
    db = get_db()
    if request.method == 'POST':
        link       = request.form.get('zoom_link', '').strip()
        title      = request.form.get('zoom_title', '').strip() or "Today's Live Session"
        time_      = request.form.get('zoom_time', '').strip() or '2:00 PM'
        paper_plan = request.form.get('paper_plan_link', '').strip()
        _set_setting(db, 'zoom_link',       link)
        _set_setting(db, 'zoom_title',      title)
        _set_setting(db, 'zoom_time',       time_)
        _set_setting(db, 'paper_plan_link', paper_plan)
        db.commit()
        db.close()
        flash('Live session updated.', 'success')
        return redirect(url_for('admin_live_session'))
    link       = _get_setting(db, 'zoom_link',       '')
    title      = _get_setting(db, 'zoom_title',      "Today's Live Session")
    time_      = _get_setting(db, 'zoom_time',        '2:00 PM')
    paper_plan = _get_setting(db, 'paper_plan_link', '')
    db.close()
    return render_template('live_session_admin.html',
                           zoom_link=link, zoom_title=title, zoom_time=time_,
                           paper_plan_link=paper_plan)


# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
#  Admin \u2013 All Members List + Individual Activity
# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

@app.route('/admin/members')
@admin_required
@safe_route
def admin_members():
    db = get_db()
    # Include team AND leader roles (admin manages both)
    users = db.execute(
        "SELECT * FROM users WHERE role IN ('team','leader') ORDER BY role, status, created_at DESC"
    ).fetchall()

    _rows = db.execute("""
        SELECT COALESCE(u.username, '') AS assigned_to,
            COUNT(*) as total_leads,
            SUM(CASE WHEN l.status IN ('Converted','Fully Converted') THEN 1 ELSE 0 END) as converted,
            SUM(CASE WHEN l.payment_done=1 THEN 1 ELSE 0 END) as paid
        FROM leads l
        LEFT JOIN users u ON u.id = l.assigned_user_id
        WHERE l.in_pool=0
        GROUP BY l.assigned_user_id
    """).fetchall()
    stats_map = {r['assigned_to']: r for r in _rows}

    _rep_rows = db.execute(
        "SELECT username, COUNT(*) as report_count FROM daily_reports GROUP BY username"
    ).fetchall()
    report_map = {r['username']: r['report_count'] for r in _rep_rows}

    # Leader metrics: for each leader, count day1, seat_hold, converted in their downline
    leader_metrics = {}
    for u in users:
        if u['role'] == 'leader':
            uname = u['username']
            downline = _get_downline_usernames(db, uname)
            dl_ids = [user_id_for_username(db, x) for x in downline]
            dl_ids = [i for i in dl_ids if i is not None]
            dl_ph = ','.join('?' * len(dl_ids)) if dl_ids else ''
            leader_uid = user_id_for_username(db, uname)
            day1_c = db.execute(
                f"SELECT COUNT(*) FROM leads WHERE pipeline_stage='day1' AND assigned_user_id IN ({dl_ph}) AND in_pool=0",
                dl_ids
            ).fetchone()[0] if dl_ids else 0
            seat_c = db.execute(
                "SELECT COUNT(*) FROM leads WHERE pipeline_stage='seat_hold' AND assigned_user_id=? AND in_pool=0",
                (leader_uid,),
            ).fetchone()[0] if leader_uid is not None else 0
            conv_c = db.execute(
                f"SELECT COUNT(*) FROM leads WHERE pipeline_stage='complete' AND assigned_user_id IN ({dl_ph}) AND in_pool=0",
                dl_ids
            ).fetchone()[0] if dl_ids else 0
            conv_pct = round(conv_c / day1_c * 100, 1) if day1_c > 0 else 0
            leader_metrics[uname] = {
                'downline_count': len(downline),
                'day1_leads': day1_c,
                'seat_holds': seat_c,
                'converted': conv_c,
                'conv_pct': conv_pct,
            }

    leaders = db.execute(
        "SELECT username FROM users WHERE role='leader' AND status='approved' ORDER BY username"
    ).fetchall()

    # Leader wallet overview + combined history (admin /all-members)
    leader_wallet_summaries = []
    for u in users:
        if u['role'] != 'leader':
            continue
        uname = u['username']
        w = _get_wallet(db, uname)
        pending_c = db.execute(
            "SELECT COUNT(*) FROM wallet_recharges WHERE username=? AND status='pending'",
            (uname,),
        ).fetchone()[0] or 0
        leader_wallet_summaries.append({
            'username': uname,
            'status': u['status'],
            'wallet': w,
            'pending_count': int(pending_c),
        })
    leader_wallet_summaries.sort(key=lambda x: x['username'].lower())

    leader_wallet_history = db.execute(
        """
        SELECT wr.id, wr.username, wr.amount, wr.utr_number, wr.status, wr.requested_at,
               wr.processed_at, wr.admin_note
        FROM wallet_recharges wr
        INNER JOIN users u ON u.username = wr.username AND u.role = 'leader'
        ORDER BY wr.requested_at DESC
        LIMIT 120
        """
    ).fetchall()

    leader_pool_claims_recent = db.execute(
        """
        SELECT l.name, l.phone, l.pool_price, l.claimed_at, l.current_owner
        FROM leads l
        INNER JOIN users u ON u.username = l.current_owner AND u.role = 'leader'
        WHERE l.in_pool = 0 AND TRIM(COALESCE(l.deleted_at, '')) = ''
          AND TRIM(COALESCE(l.claimed_at, '')) != ''
        ORDER BY l.claimed_at DESC
        LIMIT 60
        """
    ).fetchall()

    db.close()
    return render_template('all_members.html',
                           users=users,
                           stats_map=stats_map,
                           report_map=report_map,
                           leader_metrics=leader_metrics,
                           leaders=leaders,
                           leader_wallet_summaries=leader_wallet_summaries,
                           leader_wallet_history=leader_wallet_history,
                           leader_pool_claims_recent=leader_pool_claims_recent)


@app.route('/admin/decision-engine')
@admin_required
@safe_route
def admin_decision_engine():
    """Step 6 — daily admin triage: default = today snapshot; ?live=1 = read-only recompute."""
    import json as _json
    from collections import defaultdict

    from helpers import (
        admin_decision_action_hint,
        admin_decision_semantic_color,
        build_admin_decision_report,
        _today_ist,
    )

    today_str = _today_ist().isoformat()
    live = (request.args.get('live') or '').strip() == '1'
    db = get_db()
    source = 'live'
    buckets = None
    if not live:
        snap = db.execute(
            "SELECT username, decision_class, detail, metrics_json FROM admin_decision_snapshots "
            "WHERE snapshot_date=? ORDER BY username",
            (today_str,),
        ).fetchall()
        if snap:
            source = 'snapshot'
            buckets = defaultdict(list)
            for row in snap:
                try:
                    mj = _json.loads(row['metrics_json'])
                except Exception:
                    mj = {'username': row['username']}
                mj['decision_class'] = row['decision_class']
                mj['detail'] = row['detail']
                buckets[row['decision_class']].append(mj)
            buckets = dict(buckets)
    if buckets is None:
        buckets = build_admin_decision_report(db)
    db.close()

    display_order = [
        ('top', 'TOP', admin_decision_semantic_color('top')),
        ('good', 'GOOD', admin_decision_semantic_color('good')),
        ('warning', 'WARNING', admin_decision_semantic_color('warning')),
        ('critical', 'CRITICAL', admin_decision_semantic_color('critical')),
        ('remove', 'REMOVE', admin_decision_semantic_color('remove')),
        ('grace', 'GRACE', admin_decision_semantic_color('grace')),
        ('new_idle', 'NEW / IDLE', admin_decision_semantic_color('new_idle')),
    ]
    return render_template(
        'admin_decision_engine.html',
        today_str=today_str,
        source=source,
        buckets=buckets,
        display_order=display_order,
        admin_decision_action_hint=admin_decision_action_hint,
    )


@app.route('/admin/members/<username>')
@admin_required
def member_detail(username):
    db   = get_db()
    user = db.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    if not user:
        flash('Member not found.', 'danger')
        db.close()
        return redirect(url_for('admin_members'))

    metrics = _get_metrics(db, username=username)
    wallet  = _get_wallet(db, username)

    _mem_uid = user_id_for_username(db, username)
    recent_leads = db.execute(
        "SELECT * FROM leads WHERE assigned_user_id=? AND in_pool=0 ORDER BY created_at DESC LIMIT 20",
        (_mem_uid,),
    ).fetchall() if _mem_uid else []

    recent_reports = db.execute(
        "SELECT * FROM daily_reports WHERE username=? ORDER BY report_date DESC LIMIT 10",
        (username,)
    ).fetchall()

    _sc = db.execute(
        "SELECT status, COUNT(*) as c FROM leads WHERE assigned_user_id=? AND in_pool=0 AND deleted_at='' GROUP BY status",
        (_mem_uid,),
    ).fetchall() if _mem_uid else []
    status_data = {s: 0 for s in STATUSES}
    for row in _sc:
        if row['status'] in status_data:
            status_data[row['status']] = row['c']

    _mfbo_row = db.execute(
        "SELECT NULLIF(TRIM(COALESCE(fbo_id, '')), '') AS fb FROM users WHERE username=?",
        (username,),
    ).fetchone()
    _mfb = (_mfbo_row["fb"] or "") if _mfbo_row else ""
    if _mfb:
        downlines = db.execute(
            """
            SELECT username, status FROM users
            WHERE upline_name=? OR upline_username=? OR TRIM(COALESCE(upline_fbo_id,''))=?
            ORDER BY username
            """,
            (username, username, _mfb),
        ).fetchall()
    else:
        downlines = db.execute(
            """
            SELECT username, status FROM users
            WHERE upline_name=? OR upline_username=?
            ORDER BY username
            """,
            (username, username),
        ).fetchall()

    inactivity_hours = None
    if user['role'] in ('team', 'leader') and user['status'] == 'approved':
        inactivity_hours = round(user_inactivity_hours(db, username), 1)

    db.close()
    return render_template('member_detail.html',
                           member=user,
                           metrics=metrics,
                           wallet=wallet,
                           recent_leads=recent_leads,
                           recent_reports=recent_reports,
                           status_data=status_data,
                           downlines=downlines,
                           statuses=STATUSES,
                           payment_amount=PAYMENT_AMOUNT,
                           member_inactivity_hours=inactivity_hours)


@app.route('/admin/members/<username>/reset-inactivity', methods=['POST'])
@admin_required
def admin_reset_member_inactivity(username):
    """Clear 48h/72h inactivity discipline by bumping last_activity_at to now."""
    db = get_db()
    subject = db.execute("SELECT username, role FROM users WHERE username=?", (username,)).fetchone()
    if not subject:
        db.close()
        flash('Member not found.', 'danger')
        return redirect(url_for('admin_members'))
    if subject['role'] not in ('team', 'leader'):
        db.close()
        flash('Only team/leader accounts use the activity clock.', 'warning')
        return redirect(url_for('member_detail', username=username))
    now_s = _now_ist().strftime('%Y-%m-%d %H:%M:%S')
    db.execute(
        "UPDATE users SET last_activity_at=?, inactivity_72h_start_date='' WHERE username=?",
        (now_s, username),
    )
    db.commit()
    _log_activity(db, username, 'activity_clock_reset', f'Admin reset inactivity for {username}')
    _log_activity(db, acting_username(), 'admin_reset_inactivity', f"Reset activity clock for {username}")
    db.commit()
    db.close()
    flash(f'Activity clock reset for @{username}.', 'success')
    return redirect(url_for('member_detail', username=username))


@app.route('/admin/members/<username>/restore-discipline', methods=['POST'])
@admin_required
def admin_restore_member_discipline(username):
    """Step 7 Rule 5 — clear removal flags and reset performance streak counters (re-entry)."""
    from helpers import log_system_auto_action, reset_user_reentry_discipline

    db = get_db()
    subject = db.execute(
        "SELECT username, role FROM users WHERE username=?", (username,)
    ).fetchone()
    if not subject or subject['role'] not in ('team', 'leader'):
        db.close()
        flash('Member not found or not team/leader.', 'danger')
        return redirect(url_for('admin_members'))
    reset_user_reentry_discipline(db, username)
    log_system_auto_action(
        db,
        'admin_restore_reentry',
        username,
        f"by_admin={(acting_username() or '')}",
    )
    db.commit()
    _log_activity(db, acting_username(), 'admin_restore_discipline', f"Re-entry reset for {username}")
    db.close()
    flash(f'@{username} discipline reset — treat as fresh start for streaks.', 'success')
    return redirect(url_for('member_detail', username=username))


@app.route('/admin/activity')
@admin_required
def admin_activity():
    db = get_db()

    try:
        page = int(request.args.get('page', 1))
    except (TypeError, ValueError):
        page = 1
    page = max(1, page)
    per_pg  = 50
    offset  = (page - 1) * per_pg
    filter_user  = request.args.get('user', '')
    filter_event = request.args.get('event', '')

    where, params = ['1=1'], []
    if filter_user:
        where.append('username=?')
        params.append(filter_user)
    if filter_event:
        if filter_event == 'lead_claim':
            where.append("(event_type IN ('lead_claim','lead_claim_row'))")
        else:
            where.append('event_type=?')
            params.append(filter_event)

    total = db.execute(
        f"SELECT COUNT(*) FROM activity_log WHERE {' AND '.join(where)}", params
    ).fetchone()[0]

    logs = db.execute(
        f"SELECT * FROM activity_log WHERE {' AND '.join(where)} ORDER BY created_at DESC LIMIT ? OFFSET ?",
        params + [per_pg, offset]
    ).fetchall()

    # Last seen — approved team + leaders (pool claims, etc. show for both)
    last_seen_rows = db.execute("""
        SELECT u.username, u.display_picture,
               a.event_type, a.created_at
        FROM users u
        LEFT JOIN activity_log a
            ON a.username = u.username
            AND a.created_at = (
                SELECT MAX(a2.created_at) FROM activity_log a2
                WHERE a2.username = u.username
            )
        WHERE u.role IN ('team', 'leader') AND u.status = 'approved'
        ORDER BY a.created_at DESC
    """).fetchall()

    team_members = db.execute(
        "SELECT username, role FROM users WHERE role IN ('team', 'leader') "
        "AND status='approved' ORDER BY role, username"
    ).fetchall()

    db.close()

    total_pages = max(1, (total + per_pg - 1) // per_pg)
    return render_template('activity_log.html',
                           logs=logs, total=total, page=page,
                           total_pages=total_pages,
                           last_seen=last_seen_rows,
                           team_members=team_members,
                           filter_user=filter_user,
                           filter_event=filter_event,
                           event_types=[
                               'login', 'logout', 'lead_update', 'report_submit',
                               'lead_claim', 'lead_claim_row',
                           ])


# ─────────────────────────────────────────────
#  Drill-Down Analytics
# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

@app.route('/drill-down/<metric>')
@login_required
def drilldown(metric):
    db = get_db()
    is_admin = session.get('role') == 'admin'

    if metric not in DRILL_LEAD_METRICS and metric not in DRILL_REPORT_METRICS:
        db.close()
        return redirect(url_for('admin_dashboard' if is_admin else 'team_dashboard'))

    if is_admin:
        network = None
    else:
        network = _get_downline_usernames(db, acting_username())

    fmt  = request.args.get('format', '')
    view = request.args.get('view', 'daily')  # 'daily' or 'monthly'

    # \u2500\u2500 Lead metrics \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
    if metric in DRILL_LEAD_METRICS:
        label, icon, color, condition = DRILL_LEAD_METRICS[metric]

        if network is not None:
            net_ids = [user_id_for_username(db, u) for u in network]
            net_ids = [i for i in net_ids if i is not None]
            if net_ids:
                ph = ','.join('?' * len(net_ids))
                base = f"l.in_pool=0 AND l.deleted_at='' AND l.assigned_user_id IN ({ph})"
                base_params = net_ids
            else:
                base = "l.in_pool=0 AND l.deleted_at='' AND 1=0"
                base_params = []
        else:
            base = "l.in_pool=0 AND l.deleted_at=''"
            base_params = []

        extra = f" AND l.{condition}" if condition else ''

        leads_rows = db.execute(
            f"SELECT l.id, l.name, l.phone, l.status, l.payment_done, l.payment_amount, l.revenue, "
            f"l.created_at, l.updated_at, COALESCE(u.username, '') AS assigned_to "
            f"FROM leads l "
            f"LEFT JOIN users u ON u.id = l.assigned_user_id "
            f"WHERE {base}{extra} ORDER BY l.created_at DESC LIMIT 500",
            base_params
        ).fetchall()

        breakdown = db.execute(
            f"SELECT COALESCE(u.username, '') AS assigned_to, COUNT(*) as cnt FROM leads l "
            f"LEFT JOIN users u ON u.id = l.assigned_user_id "
            f"WHERE {base}{extra} "
            f"GROUP BY l.assigned_user_id ORDER BY cnt DESC",
            base_params
        ).fetchall()

        if view == 'monthly':
            trend_rows = db.execute(
                f"SELECT strftime('%Y-%m', l.created_at) as d, COUNT(*) as cnt FROM leads l "
                f"WHERE {base}{extra} AND date(l.created_at) >= date('now','-365 days') "
                f"GROUP BY d ORDER BY d",
                base_params
            ).fetchall()
        else:
            trend_rows = db.execute(
                f"SELECT date(l.created_at) as d, COUNT(*) as cnt FROM leads l "
                f"WHERE {base}{extra} AND date(l.created_at) >= date('now','-30 days') "
                f"GROUP BY d ORDER BY d",
                base_params
            ).fetchall()
        trend = [{'d': r['d'], 'cnt': r['cnt']} for r in trend_rows]

        if fmt == 'csv':
            db.close()
            out = io.StringIO()
            w = csv.writer(out)
            w.writerow(['Name', 'Phone', 'Status', 'Payment Done', 'Amount', 'Assigned To', 'Added', 'Updated'])
            for r in leads_rows:
                w.writerow([r['name'], r['phone'], r['status'],
                            'Yes' if r['payment_done'] else 'No',
                            r['payment_amount'] or 0,
                            r['assigned_to'], r['created_at'][:10], r['updated_at'][:10]])
            return Response(out.getvalue(), mimetype='text/csv',
                            headers={'Content-Disposition': f'attachment;filename=drill_{metric}.csv'})

        db.close()
        return render_template('drill_down.html',
                               metric=metric, label=label, icon=icon, color=color,
                               leads=leads_rows, report_rows=None,
                               breakdown=breakdown, trend=trend,
                               is_report=False, is_admin=is_admin, view=view)

    # \u2500\u2500 Report metrics \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
    else:
        label, icon, color = DRILL_REPORT_METRICS[metric]
        col = metric

        if network is not None:
            ph = ','.join('?' * len(network))
            where = f"username IN ({ph})"
            where_params = list(network)
        else:
            where = '1=1'
            where_params = []

        report_rows = db.execute(
            f"SELECT username, report_date, {col} as val, remarks "
            f"FROM daily_reports WHERE {where} AND {col} > 0 "
            f"ORDER BY report_date DESC, username LIMIT 500",
            where_params
        ).fetchall()

        breakdown = db.execute(
            f"SELECT username as assigned_to, SUM({col}) as cnt "
            f"FROM daily_reports WHERE {where} GROUP BY username ORDER BY cnt DESC",
            where_params
        ).fetchall()

        if view == 'monthly':
            trend_rows = db.execute(
                f"SELECT strftime('%Y-%m', report_date) as d, SUM({col}) as cnt FROM daily_reports "
                f"WHERE {where} AND report_date >= date('now','-365 days') "
                f"GROUP BY d ORDER BY d",
                where_params
            ).fetchall()
        else:
            trend_rows = db.execute(
                f"SELECT report_date as d, SUM({col}) as cnt FROM daily_reports "
                f"WHERE {where} AND report_date >= date('now','-30 days') "
                f"GROUP BY report_date ORDER BY report_date",
                where_params
            ).fetchall()
        trend = [{'d': r['d'], 'cnt': r['cnt']} for r in trend_rows]

        if fmt == 'csv':
            db.close()
            out = io.StringIO()
            w = csv.writer(out)
            w.writerow(['Member', 'Date', label, 'Remarks'])
            for r in report_rows:
                w.writerow([r['username'], r['report_date'], r['val'], r['remarks'] or ''])
            return Response(out.getvalue(), mimetype='text/csv',
                            headers={'Content-Disposition': f'attachment;filename=drill_{metric}.csv'})

        db.close()
        return render_template('drill_down.html',
                               metric=metric, label=label, icon=icon, color=color,
                               leads=None, report_rows=report_rows,
                               breakdown=breakdown, trend=trend,
                               is_report=True, is_admin=is_admin, view=view)


# ─────────────────────────────────────────────────────────────
#  Training Gate (before_request)
# ─────────────────────────────────────────────────────────────

_TRAINING_EXEMPT = (
    '/static', '/training', '/profile/dp',
    '/login', '/register', '/logout', '/health',
    '/manifest.json', '/sw.js', '/forgot-password',
    '/reset-password', '/push', '/calling-reminder',
    '/admin/training/signature-preview',
)

@app.before_request
def refresh_session_role():
    """Auto-sync session role from DB periodically (not every request)."""
    if 'username' not in session:
        return
    if request.path.startswith('/static'):
        return
    import time
    last_check = session.get('_role_checked', 0)
    if time.time() - last_check < 60:
        return
    try:
        db = get_db()
        row = db.execute(
            "SELECT role FROM users WHERE username=? AND status='approved'",
            (acting_username(),)
        ).fetchone()
        db.close()
        session['_role_checked'] = time.time()
        if row and row['role'] != session.get('role'):
            session['role'] = row['role']
    except Exception:
        pass


@app.before_request
def training_gate():
    if any(request.path.startswith(p) for p in _TRAINING_EXEMPT):
        return
    if 'username' not in session:
        return
    if session.get('role') == 'admin':
        return
    ts = session.get('training_status', 'not_required')
    if ts not in ('not_required', 'unlocked'):
        return redirect(url_for('training_home'))

# ─────────────────────────────────────────────────────────────────
#  Working Section
# ─────────────────────────────────────────────────────────────────

# Working section Stage 1 = only leads ready for Day 1
STAGE1_STATUSES = ('Paid ₹196',)

# My Leads prospecting statuses (pre-enrollment leads) — keep aligned with helpers.WORKING_ENROLLMENT_STATUSES
ENROLLMENT_STATUSES = ('New Lead', 'New', 'Contacted', 'Invited',
                       'Video Sent', 'Video Watched')

# Enrolled = paid ₹196
ENROLLED_STATUSES = ('Paid ₹196',)

PAST_STATUSES   = ('Fully Converted', 'Converted', 'Lost')

# Leader /working: cap each status bucket (recent first) so large downlines stay responsive.
LEADER_WORK_BUCKET_LIMIT = 120
LEADER_WORK_PAST_LIMIT_OWN = 20
LEADER_WORK_PAST_LIMIT_TEAM = 50


def _leader_merge_workboard_columns(own_list, team_list):
    """Unified leader workboard: own + downline rows, newest first; tag scope for template."""
    merged = []
    for L in own_list or []:
        d = dict(L)
        d['_wk_scope'] = 'own'
        merged.append(d)
    for L in team_list or []:
        d = dict(L)
        d['_wk_scope'] = 'team'
        merged.append(d)
    merged.sort(key=lambda x: str(x.get('updated_at') or ''), reverse=True)
    return merged


def _leader_dashboard_merged_pipeline(db, username):
    """
    Leader /dashboard pipeline cards: same lead scope as /working (own + downline assignees),
    not only rows where assigned_user_id is the leader. Without this, team Day 1/2/3 updates
    never appear on the dashboard during the day.
    """
    _own_where, _own_params = _working_assigned_where(db, 'leader', username, 'own')
    try:
        _downline_only = [u for u in _get_network_usernames(db, username) if u != username]
    except Exception:
        _downline_only = []
    _team_where, _team_params = _working_assigned_where(db, 'leader', username, 'downline', _downline_only)
    _w_own = "SELECT * FROM leads WHERE in_pool=0 AND deleted_at='' " + _own_where
    _lim = LEADER_WORK_BUCKET_LIMIT
    _s1_ph = ','.join('?' * len(STAGE1_STATUSES))

    own_stage1 = db.execute(
        _w_own + f" AND status IN ({_s1_ph}) ORDER BY updated_at DESC LIMIT ?",
        _own_params + list(STAGE1_STATUSES) + [_lim],
    ).fetchall()
    own_day1 = db.execute(
        _w_own + " AND status='Day 1' ORDER BY updated_at DESC LIMIT ?",
        _own_params + [_lim],
    ).fetchall()
    own_day2 = db.execute(
        _w_own + " AND status='Day 2' ORDER BY updated_at DESC LIMIT ?",
        _own_params + [_lim],
    ).fetchall()
    own_day3 = db.execute(
        _w_own + " AND status IN ('Interview','Track Selected') ORDER BY updated_at DESC LIMIT ?",
        _own_params + [_lim],
    ).fetchall()
    own_pending = db.execute(
        _w_own + " AND status='Seat Hold Confirmed' ORDER BY updated_at DESC LIMIT ?",
        _own_params + [_lim],
    ).fetchall()

    if _team_params:
        _t_ph = ','.join('?' * len(_team_params))
        _w_tm = (
            f"SELECT l.* FROM leads l WHERE l.in_pool=0 AND l.deleted_at='' "
            f"AND l.assigned_user_id IN ({_t_ph}) "
        )
        team_stage1 = db.execute(
            _w_tm + f"AND l.status IN ({_s1_ph}) ORDER BY l.updated_at DESC LIMIT ?",
            _team_params + list(STAGE1_STATUSES) + [_lim],
        ).fetchall()
        team_day1 = db.execute(
            _w_tm + "AND l.status='Day 1' ORDER BY l.updated_at DESC LIMIT ?",
            _team_params + [_lim],
        ).fetchall()
        team_day2 = db.execute(
            _w_tm + "AND l.status='Day 2' ORDER BY l.updated_at DESC LIMIT ?",
            _team_params + [_lim],
        ).fetchall()
        team_day3 = db.execute(
            _w_tm + "AND l.status IN ('Interview','Track Selected') ORDER BY l.updated_at DESC LIMIT ?",
            _team_params + [_lim],
        ).fetchall()
        team_pending = db.execute(
            _w_tm + "AND l.status='Seat Hold Confirmed' ORDER BY l.updated_at DESC LIMIT ?",
            _team_params + [_lim],
        ).fetchall()
    else:
        team_stage1 = team_day1 = team_day2 = team_day3 = team_pending = []

    def _merge(own_rows, team_rows):
        return _leader_merge_workboard_columns(
            list(own_rows) if own_rows else [],
            list(team_rows) if team_rows else [],
        )

    return (
        _merge(own_stage1, team_stage1),
        _merge(own_day1, team_day1),
        _merge(own_day2, team_day2),
        _merge(own_day3, team_day3),
        _merge(own_pending, team_pending),
    )


def _working_assigned_where(db, role, username, scope='all', downline_usernames=None):
    """
    Returns (sql_fragment, params) for WHERE clause in working() lead queries.
    scope: 'all' = admin sees all assigned leads (assigned_user_id IS NOT NULL);
           'own' = leader/team own leads; 'downline' = leader sees downline (excludes self).
    downline_usernames: optional pre-fetched list for scope='downline' to avoid refetch.
    """
    if role == 'admin':
        return "AND assigned_user_id IS NOT NULL", [] if scope == 'all' else (None, None)
    if role == 'leader':
        if scope == 'own':
            uid = user_id_for_username(db, username)
            if uid is None:
                return "AND 1=0", []
            # Own scope: execution assignee OR leads this user permanently bought (current_owner).
            # Team → leader handoff changes assigned_user_id only; current_owner stays the buyer.
            return "AND (assigned_user_id=? OR current_owner=?)", [uid, username]
        if scope == 'downline':
            usernames = downline_usernames if downline_usernames is not None else [
                u for u in _get_network_usernames(db, username) if u != username
            ]
            if not usernames:
                return "AND 1=0", []
            ids = [user_id_for_username(db, u) for u in usernames]
            ids = [i for i in ids if i is not None]
            if not ids:
                return "AND 1=0", []
            ph = ','.join('?' * len(ids))
            return f"AND assigned_user_id IN ({ph})", ids
    # team
    uid = user_id_for_username(db, username)
    if uid is None:
        return "AND 1=0", []
    return "AND assigned_user_id=?", [uid]


@app.route('/working')
@login_required
@safe_route
def working():
    db       = get_db()
    username = acting_username()
    today    = _today_ist().strftime('%Y-%m-%d')

    # Always fetch fresh role from DB so promotions take effect without re-login
    fresh_user = db.execute("SELECT role FROM users WHERE username=?", (username,)).fetchone()
    role = fresh_user['role'] if fresh_user else session.get('role', 'team')
    if role != session.get('role'):
        session['role'] = role   # sync session silently

    # Check seat_hold expiry
    _check_seat_hold_expiry(db, username)

    if role == 'admin':
        # Run global pipeline expiry first so stale Day-1/2/3 leads are cleaned
        # before the workboard queries — prevents dead leads from showing up
        try:
            _expire_all_pipeline_leads(db)
        except Exception:
            pass
        # ── Admin view (all leads with assignee FK set) ─────────────
        _admin_where, _admin_params = _working_assigned_where(db, 'admin', username, 'all')
        _admin_base = "FROM leads WHERE in_pool=0 AND deleted_at='' " + _admin_where + " "
        stage_placeholders = ','.join('?' * len(STAGE1_STATUSES))
        enroll_placeholders = ','.join('?' * len(ENROLLMENT_STATUSES))

        stage_counts = db.execute(
            "SELECT "
            "SUM(CASE WHEN status IN (" + enroll_placeholders + ") THEN 1 ELSE 0 END) AS prospecting, "
            "SUM(CASE WHEN status IN (" + stage_placeholders + ") THEN 1 ELSE 0 END) AS stage1, "
            "SUM(CASE WHEN status='Day 1' THEN 1 ELSE 0 END) AS day1, "
            "SUM(CASE WHEN status='Day 2' THEN 1 ELSE 0 END) AS day2, "
            "SUM(CASE WHEN status IN ('Interview','Track Selected') THEN 1 ELSE 0 END) AS day3, "
            "SUM(CASE WHEN status='Seat Hold Confirmed' THEN 1 ELSE 0 END) AS pending, "
            "SUM(CASE WHEN status IN ('Fully Converted','Converted') THEN 1 ELSE 0 END) AS converted "
            + _admin_base,
            list(ENROLLMENT_STATUSES) + list(STAGE1_STATUSES) + _admin_params
        ).fetchone()

        total_pipeline_value = db.execute(
            "SELECT COALESCE(SUM(track_price), 0) " + _admin_base + "AND status IN ('Seat Hold Confirmed','Track Selected')",
            _admin_params
        ).fetchone()[0] or 0

        # Team pipeline per member (single query instead of N+1)
        members = db.execute(
            "SELECT username, fbo_id FROM users WHERE role IN ('team','leader') AND status='approved' ORDER BY username"
        ).fetchall()
        _member_fbo = {m['username']: m['fbo_id'] or '' for m in members}

        _pipeline_rows = db.execute(f"""
            SELECT u.username AS assigned_to,
                SUM(CASE WHEN l.status IN ({stage_placeholders}) THEN 1 ELSE 0 END) AS stage1,
                SUM(CASE WHEN l.status='Day 1' THEN 1 ELSE 0 END) AS day1,
                SUM(CASE WHEN l.status='Day 2' THEN 1 ELSE 0 END) AS day2,
                SUM(CASE WHEN l.status IN ('Interview','Track Selected') THEN 1 ELSE 0 END) AS day3,
                SUM(CASE WHEN l.status='Seat Hold Confirmed' THEN 1 ELSE 0 END) AS pending,
                SUM(CASE WHEN l.status IN ('Fully Converted','Converted') THEN 1 ELSE 0 END) AS converted
            FROM leads l
            JOIN users u ON u.id = l.assigned_user_id
            WHERE l.in_pool=0 AND l.deleted_at=''
            GROUP BY u.username
        """, list(STAGE1_STATUSES)).fetchall()
        _pipeline_by_user = {r['assigned_to']: r for r in _pipeline_rows}

        team_pipeline = {}
        for uname in _member_fbo:
            row = _pipeline_by_user.get(uname)
            score_pts, streak = _get_today_score(db, uname)
            team_pipeline[uname] = {
                'stage1': (row['stage1'] or 0) if row else 0,
                'day1':   (row['day1']   or 0) if row else 0,
                'day2':   (row['day2']   or 0) if row else 0,
                'day3':   (row['day3']   or 0) if row else 0,
                'pending': (row['pending'] or 0) if row else 0,
                'converted': (row['converted'] or 0) if row else 0,
                'score': score_pts,
                'fbo_id': _member_fbo[uname],
            }

        # Stale leads (not updated in 48h, not closed/lost)
        stale_cutoff = (_now_ist() - datetime.timedelta(hours=48)).strftime('%Y-%m-%d %H:%M:%S')
        stale_leads  = db.execute(
            "SELECT * "
            + _admin_base + "AND status NOT IN ('Fully Converted','Converted','Lost','Seat Hold Confirmed') AND updated_at < ? ORDER BY updated_at ASC",
            _admin_params + [stale_cutoff]
        ).fetchall()
        stale_leads = _enrich_leads([dict(x) for x in stale_leads], db=db)

        # Day 1/2 batch completion rate
        d1_total = db.execute(
            "SELECT COUNT(*) " + _admin_base + "AND status='Day 1'",
            _admin_params
        ).fetchone()[0] or 0
        d1_done  = db.execute(
            "SELECT COUNT(*) " + _admin_base + "AND status='Day 1' AND d1_morning=1 AND d1_afternoon=1 AND d1_evening=1",
            _admin_params
        ).fetchone()[0] or 0
        d2_total = db.execute(
            "SELECT COUNT(*) " + _admin_base + "AND status='Day 2'",
            _admin_params
        ).fetchone()[0] or 0
        d2_done  = db.execute(
            "SELECT COUNT(*) " + _admin_base + "AND status='Day 2' AND d2_morning=1 AND d2_afternoon=1 AND d2_evening=1",
            _admin_params
        ).fetchone()[0] or 0

        batch_completion = {
            'd1_total': d1_total, 'd1_done': d1_done,
            'd1_pct': round(d1_done / d1_total * 100) if d1_total else 0,
            'd2_total': d2_total, 'd2_done': d2_done,
            'd2_pct': round(d2_done / d2_total * 100) if d2_total else 0,
        }

        # ── Admin Day 1 / Day 2 / Day 3 lead lists ──────────────
        admin_day1_leads = db.execute("""
            SELECT l.*,
                   CAST((julianday('now', '+5 hours', '+30 minutes') - julianday(l.updated_at)) * 24 AS INTEGER) AS hours_since_update
            FROM leads l
            WHERE l.in_pool=0 AND l.deleted_at='' AND l.status='Day 1'
            ORDER BY (l.d1_morning + l.d1_afternoon + l.d1_evening) ASC, l.updated_at ASC
        """).fetchall()
        admin_day2_leads = db.execute("""
            SELECT l.*,
                   CAST((julianday('now', '+5 hours', '+30 minutes') - julianday(l.updated_at)) * 24 AS INTEGER) AS hours_since_update
            FROM leads l
            WHERE l.in_pool=0 AND l.deleted_at='' AND l.status='Day 2'
            ORDER BY (l.d2_morning + l.d2_afternoon + l.d2_evening) DESC, l.updated_at ASC
        """).fetchall()
        admin_day3_leads = db.execute("""
            SELECT l.*,
                   CAST((julianday('now', '+5 hours', '+30 minutes') - julianday(l.updated_at)) * 24 AS INTEGER) AS hours_since_update
            FROM leads l
            WHERE l.in_pool=0 AND l.deleted_at='' AND l.status IN ('Interview','Track Selected','Seat Hold Confirmed')
            ORDER BY l.updated_at ASC
        """).fetchall()

        admin_day1_leads = _enrich_leads([dict(x) for x in admin_day1_leads], db=db)
        admin_day2_leads = _enrich_leads([dict(x) for x in admin_day2_leads], db=db)
        admin_day3_leads = _enrich_leads([dict(x) for x in admin_day3_leads], db=db)

        # Leader map for Day 2/3: assignee username → upline
        _all_usernames = list(set(
            [l.get('assignee_username') or '' for l in admin_day2_leads if l.get('assignee_username')] +
            [l.get('assignee_username') or '' for l in admin_day3_leads if l.get('assignee_username')]
        ))
        admin_leader_map = {}
        if _all_usernames:
            _ph = ','.join('?' * len(_all_usernames))
            _urows = db.execute(
                f"SELECT username, upline_username, upline_name FROM users WHERE username IN ({_ph})",
                _all_usernames
            ).fetchall()
            for r in _urows:
                admin_leader_map[r['username']] = r['upline_username'] or r['upline_name'] or '—'

        # ── Admin tasks ──────────────────────────────────────────
        admin_tasks = db.execute("""
            SELECT t.*, GROUP_CONCAT(d.username) as done_by_list
            FROM admin_tasks t
            LEFT JOIN admin_task_done d ON d.task_id = t.id
            WHERE t.is_done = 0
            GROUP BY t.id
            ORDER BY t.priority='urgent' DESC, t.created_at DESC
        """).fetchall()

        # D2 summary counts for inline board
        admin_d2_complete    = sum(1 for l in admin_day2_leads if l['d2_morning'] and l['d2_afternoon'] and l['d2_evening'])
        admin_d2_in_progress = sum(1 for l in admin_day2_leads if 0 < (l['d2_morning']+l['d2_afternoon']+l['d2_evening']) < 3)
        admin_d2_not_started = sum(1 for l in admin_day2_leads if (l['d2_morning']+l['d2_afternoon']+l['d2_evening']) == 0)

        # Build batch_videos BEFORE closing database
        admin_batch_videos = {
            'd1_morning_v1': _get_setting(db, 'batch_d1_morning_v1', ''),
            'd1_morning_v2': _get_setting(db, 'batch_d1_morning_v2', ''),
            'd1_afternoon_v1': _get_setting(db, 'batch_d1_afternoon_v1', ''),
            'd1_afternoon_v2': _get_setting(db, 'batch_d1_afternoon_v2', ''),
            'd1_evening_v1': _get_setting(db, 'batch_d1_evening_v1', ''),
            'd1_evening_v2': _get_setting(db, 'batch_d1_evening_v2', ''),
            'd2_morning_v1': _get_setting(db, 'batch_d2_morning_v1', ''),
            'd2_morning_v2': _get_setting(db, 'batch_d2_morning_v2', ''),
            'd2_afternoon_v1': _get_setting(db, 'batch_d2_afternoon_v1', ''),
            'd2_afternoon_v2': _get_setting(db, 'batch_d2_afternoon_v2', ''),
            'd2_evening_v1': _get_setting(db, 'batch_d2_evening_v1', ''),
            'd2_evening_v2': _get_setting(db, 'batch_d2_evening_v2', ''),
        }
        enrollment_video_url   = _get_setting(db, 'enrollment_video_url', '')
        enrollment_video_title = _get_setting(db, 'enrollment_video_title', 'Enrollment Video')

        # ── Today's pipeline summary (leads claimed TODAY from pool) ──
        today_str = _today_ist().isoformat()
        _today_stage_rows = db.execute("""
            SELECT status, COUNT(*) as cnt FROM leads
            WHERE in_pool=0 AND deleted_at=''
            AND claimed_at IS NOT NULL
            AND date(claimed_at) = ?
            GROUP BY status
        """, (today_str,)).fetchall()
        today_pipeline_summary = {row['status']: row['cnt'] for row in _today_stage_rows}
        today_total_claimed   = sum(today_pipeline_summary.values())
        today_prospecting     = sum(today_pipeline_summary.get(s, 0) for s in ENROLLMENT_STATUSES)
        today_enrolled        = sum(today_pipeline_summary.get(s, 0) for s in ENROLLED_STATUSES)
        today_day1            = today_pipeline_summary.get('Day 1', 0)
        today_day2            = today_pipeline_summary.get('Day 2', 0)
        today_day3            = (today_pipeline_summary.get('Interview', 0)
                                 + today_pipeline_summary.get('Track Selected', 0))
        today_seat_hold       = today_pipeline_summary.get('Seat Hold Confirmed', 0)
        today_converted       = (today_pipeline_summary.get('Converted', 0)
                                 + today_pipeline_summary.get('Fully Converted', 0))

        db.close()
        return render_template('working.html',
            is_admin=True,
            pipeline_auto_expire_statuses=PIPELINE_AUTO_EXPIRE_STATUSES,
            sla_soft_watch_exclude=SLA_SOFT_WATCH_EXCLUDE,
            team_pipeline=team_pipeline,
            stage_counts=stage_counts,
            total_pipeline_value=total_pipeline_value,
            stale_leads=stale_leads,
            batch_completion=batch_completion,
            tracks=TRACKS,
            batch_videos=admin_batch_videos,
            batch_watch_urls=_batch_watch_urls(),
            enrollment_video_url=enrollment_video_url,
            enrollment_watch_url=url_for('watch_enrollment', _external=True) if enrollment_video_url else '',
            enrollment_video_title=enrollment_video_title,
            show_day1_batches=True,
            user_role='admin',
            call_status_values=CALL_STATUS_VALUES,
            team_call_status_values=TEAM_CALL_STATUS_VALUES,
            csrf_token=session.get('_csrf_token', ''),
            admin_day1_leads=admin_day1_leads,
            admin_day2_leads=admin_day2_leads,
            admin_day3_leads=admin_day3_leads,
            admin_leader_map=admin_leader_map,
            admin_tasks=admin_tasks,
            admin_d2_complete=admin_d2_complete,
            admin_d2_in_progress=admin_d2_in_progress,
            admin_d2_not_started=admin_d2_not_started,
            today_total_claimed=today_total_claimed,
            today_prospecting=today_prospecting,
            today_enrolled=today_enrolled,
            today_day1=today_day1,
            today_day2=today_day2,
            today_day3=today_day3,
            today_seat_hold=today_seat_hold,
            today_converted=today_converted,
            workboard_poll_ms=60_000,
        )

    if role == 'leader':
        # Assigned filter: own = leader's leads, downline = team's leads (excludes self)
        _own_where, _own_params = _working_assigned_where(db, 'leader', username, 'own')
        try:
            _downline_only = [u for u in _get_network_usernames(db, username) if u != username]
        except Exception:
            _downline_only = []
        try:
            _auto_expire_pipeline_leads_batch(db, [username] + list(_downline_only))
        except Exception:
            pass
        _team_where, _team_params = _working_assigned_where(db, 'leader', username, 'downline', _downline_only)

        # ── OWN + TEAM LEADS: one query per bucket (LIMIT) — avoids loading entire downline in one SELECT *
        _w_own = "SELECT * FROM leads WHERE in_pool=0 AND deleted_at='' " + _own_where
        _e_ph = ','.join('?' * len(ENROLLMENT_STATUSES))
        _enr_ph = ','.join('?' * len(ENROLLED_STATUSES))
        _side_ph = ','.join('?' * len(WORKING_SIDE_PIPELINE_STATUSES))
        _lim = LEADER_WORK_BUCKET_LIMIT

        # Leader My Work: enrollment + on-hold live on /leads (calling / prospecting). Workboard = Day 1+ only.
        own_stage1, own_side = [], []
        own_day1 = db.execute(
            _w_own + " AND status='Day 1' ORDER BY updated_at DESC LIMIT ?",
            _own_params + [_lim],
        ).fetchall()
        own_day2 = db.execute(
            _w_own.replace(
                "SELECT * FROM leads",
                "SELECT *, CAST((julianday('now', '+5 hours', '+30 minutes') - julianday(updated_at)) * 24 AS INTEGER) AS hours_since_update FROM leads",
                1,
            )
            + " AND status='Day 2' ORDER BY updated_at DESC LIMIT ?",
            _own_params + [_lim],
        ).fetchall()
        own_day3 = db.execute(
            _w_own + " AND status IN ('Interview','Track Selected') ORDER BY updated_at DESC LIMIT ?",
            _own_params + [_lim],
        ).fetchall()
        own_pending = db.execute(
            _w_own + " AND status='Seat Hold Confirmed' ORDER BY updated_at DESC LIMIT ?",
            _own_params + [_lim],
        ).fetchall()
        own_closing = db.execute(
            _w_own + " AND status='Fully Converted' ORDER BY updated_at DESC LIMIT ?",
            _own_params + [_lim],
        ).fetchall()
        own_past = db.execute(
            _w_own + " AND status IN ('Converted','Lost') ORDER BY updated_at DESC LIMIT ?",
            _own_params + [LEADER_WORK_PAST_LIMIT_OWN],
        ).fetchall()

        if _team_params:
            _t_ph = ','.join('?' * len(_team_params))
            _w_tm = (
                f"SELECT l.* FROM leads l WHERE l.in_pool=0 AND l.deleted_at='' "
                f"AND l.assigned_user_id IN ({_t_ph}) "
            )
            team_stage1 = db.execute(
                _w_tm + f"AND (l.status IN ({_e_ph}) OR l.status IN ({_enr_ph})) ORDER BY l.updated_at DESC LIMIT ?",
                _team_params + list(ENROLLMENT_STATUSES) + list(ENROLLED_STATUSES) + [_lim],
            ).fetchall()
            team_side = db.execute(
                _w_tm + f"AND l.status IN ({_side_ph}) ORDER BY l.updated_at DESC LIMIT ?",
                _team_params + list(WORKING_SIDE_PIPELINE_STATUSES) + [_lim],
            ).fetchall()
            team_day1 = db.execute(
                _w_tm + "AND l.status='Day 1' ORDER BY l.updated_at DESC LIMIT ?",
                _team_params + [_lim],
            ).fetchall()
            _w_tm_d2 = _w_tm.replace(
                "SELECT l.* FROM leads l",
                "SELECT l.*, CAST((julianday('now', '+5 hours', '+30 minutes') - julianday(l.updated_at)) * 24 AS INTEGER) AS hours_since_update FROM leads l",
                1,
            )
            team_day2 = db.execute(
                _w_tm_d2 + "AND l.status='Day 2' ORDER BY l.updated_at DESC LIMIT ?",
                _team_params + [_lim],
            ).fetchall()
            team_day3 = db.execute(
                _w_tm + "AND l.status IN ('Interview','Track Selected') ORDER BY l.updated_at DESC LIMIT ?",
                _team_params + [_lim],
            ).fetchall()
            team_pending = db.execute(
                _w_tm + "AND l.status='Seat Hold Confirmed' ORDER BY l.updated_at DESC LIMIT ?",
                _team_params + [_lim],
            ).fetchall()
            team_closing = db.execute(
                _w_tm + "AND l.status='Fully Converted' ORDER BY l.updated_at DESC LIMIT ?",
                _team_params + [_lim],
            ).fetchall()
            team_past = db.execute(
                _w_tm + "AND l.status IN ('Converted','Lost') ORDER BY l.updated_at DESC LIMIT ?",
                _team_params + [LEADER_WORK_PAST_LIMIT_TEAM],
            ).fetchall()
            _d_phs = ','.join('?' * len(_downline_only))
            downline_members = db.execute(
                f"SELECT username, fbo_id FROM users WHERE username IN ({_d_phs}) AND status='approved' ORDER BY username",
                _downline_only
            ).fetchall()
        else:
            team_stage1 = team_side = team_day1 = team_day2 = team_day3 = []
            team_pending = team_closing = team_past = []
            downline_members = []

        # ── Pending action counts: not shown on leader workboard (enrollment calls → /leads) ──
        def _row_val(r, key, default=None):
            try:
                return r[key] if key in r.keys() else default
            except Exception:
                return default
        own_pending_calls = 0
        team_pending_calls = 0
        own_batches_due = (
            sum(1 for l in own_day1 if not (_row_val(l, 'd1_morning') and _row_val(l, 'd1_afternoon') and _row_val(l, 'd1_evening'))) +
            sum(1 for l in own_day2 if not (_row_val(l, 'd2_morning') and _row_val(l, 'd2_afternoon') and _row_val(l, 'd2_evening')))
        )
        team_batches_due = (
            sum(1 for l in team_day1 if not (_row_val(l, 'd1_morning') and _row_val(l, 'd1_afternoon') and _row_val(l, 'd1_evening'))) +
            sum(1 for l in team_day2 if not (_row_val(l, 'd2_morning') and _row_val(l, 'd2_afternoon') and _row_val(l, 'd2_evening')))
        )

        own_videos_to_send = 0
        own_closings_due = len(own_day3) + len(own_pending)
        team_closings_due = len(team_day3) + len(team_pending)
        leader_today_actions = {
            'pending_calls':  0,
            'videos_to_send': 0,
            'batches_due':    own_batches_due + team_batches_due,
            'closings_due':   own_closings_due + team_closings_due,
        }

        # ── Enrich all lists (reuse open db) ──────────────────────
        own_stage1   = _enrich_leads(own_stage1, db=db)
        own_side     = _enrich_leads(own_side, db=db)
        own_day1     = _enrich_leads(own_day1, db=db)
        own_day2     = _enrich_leads(own_day2, db=db)
        own_day3     = _enrich_leads(own_day3, db=db)
        own_pending  = _enrich_leads(own_pending, db=db)
        own_closing  = _enrich_leads(own_closing, db=db)
        team_stage1  = _enrich_leads(team_stage1, db=db)
        team_side    = _enrich_leads(team_side, db=db)
        team_day1    = _enrich_leads(team_day1, db=db)
        team_day2    = _enrich_leads(team_day2, db=db)
        team_day3    = _enrich_leads(team_day3, db=db)
        team_pending = _enrich_leads(team_pending, db=db)
        team_closing = _enrich_leads(team_closing, db=db)

        leader_day1_work = _leader_merge_workboard_columns(own_day1, team_day1)
        leader_day2_work = _leader_merge_workboard_columns(own_day2, team_day2)
        leader_day3_work = _leader_merge_workboard_columns(own_day3, team_day3)
        leader_pending_work = _leader_merge_workboard_columns(own_pending, team_pending)
        leader_closing_work = _leader_merge_workboard_columns(own_closing, team_closing)

        _d2_assignee_names = sorted(
            {
                (l.get('assignee_username') or '').strip()
                for l in leader_day2_work
                if (l.get('assignee_username') or '').strip()
            }
        )
        leader_d2_upline = {}
        if _d2_assignee_names:
            _ph_d2u = ','.join('?' * len(_d2_assignee_names))
            for _ur in db.execute(
                f"SELECT username, upline_username, upline_name FROM users WHERE username IN ({_ph_d2u})",
                _d2_assignee_names,
            ).fetchall():
                leader_d2_upline[_ur['username']] = (
                    (_ur['upline_username'] or _ur['upline_name'] or '').strip() or '—'
                )

        today_score, streak = _get_today_score(db, username)

        # ── Batch videos (single query instead of 12) ──────────
        _bv_keys = [
            'batch_d1_morning_v1', 'batch_d1_morning_v2',
            'batch_d1_afternoon_v1', 'batch_d1_afternoon_v2',
            'batch_d1_evening_v1', 'batch_d1_evening_v2',
            'batch_d2_morning_v1', 'batch_d2_morning_v2',
            'batch_d2_afternoon_v1', 'batch_d2_afternoon_v2',
            'batch_d2_evening_v1', 'batch_d2_evening_v2',
        ]
        _bv_ph = ','.join('?' * len(_bv_keys))
        _bv_map = {}
        for _bvr in db.execute(f"SELECT key, value FROM app_settings WHERE key IN ({_bv_ph})", _bv_keys).fetchall():
            _bv_map[_bvr['key']] = _bvr['value'] or ''
        leader_batch_videos = {k.replace('batch_', ''): _bv_map.get(k, '') for k in _bv_keys}

        # ── Enroll To data (guarded so old DB or missing tables never crash leader view) ──
        enroll_days = {}
        enroll_pdfs = []
        recent_shares = []
        team_leads_for_enroll = []
        try:
            _ec_rows = db.execute(
                "SELECT * FROM enroll_content WHERE is_active=1 ORDER BY day_number, sort_order"
            ).fetchall()
            for _r in _ec_rows:
                _row_d = dict(_r)
                _d = _row_d.get('day_number', 1) or 1
                if _d not in enroll_days:
                    enroll_days[_d] = []
                enroll_days[_d].append(_row_d)

            enroll_pdfs = db.execute(
                "SELECT * FROM enroll_pdfs WHERE is_active=1 ORDER BY sort_order"
            ).fetchall()

            recent_shares = db.execute("""
                SELECT esl.*, ec.curiosity_title as video_title, ec.day_number as video_day
                FROM enroll_share_links esl
                JOIN enroll_content ec ON ec.id = esl.content_id
                WHERE esl.shared_by=?
                ORDER BY esl.created_at DESC LIMIT 15
            """, (username,)).fetchall()

            _enroll_ids = [user_id_for_username(db, x) for x in [username] + list(_downline_only)]
            _enroll_ids = [i for i in _enroll_ids if i is not None]
            _all_leader_leads_phs = ','.join('?' * len(_enroll_ids))
            team_leads_for_enroll = db.execute(f"""
                SELECT l.id, l.name, l.phone, COALESCE(u.username, '') AS assigned_to FROM leads l
                JOIN users u ON u.id = l.assigned_user_id
                WHERE l.assigned_user_id IN ({_all_leader_leads_phs})
                  AND l.in_pool=0 AND l.deleted_at=''
                  AND l.status NOT IN ('Lost','Converted','Fully Converted')
                ORDER BY u.username, l.name
            """, _enroll_ids).fetchall() if _enroll_ids else []
        except Exception:
            pass

        enrollment_video_url   = _get_setting(db, 'enrollment_video_url', '')
        enrollment_video_title = _get_setting(db, 'enrollment_video_title', 'Enrollment Video')

        # Tutorial / onboarding data for fully converted leads
        app_tutorial_link = _get_setting(db, 'app_tutorial_link', '')
        _leader_row = db.execute("SELECT fbo_id FROM users WHERE username=?", (username,)).fetchone()
        leader_fbo_id = (_leader_row['fbo_id'] if _leader_row and _leader_row['fbo_id'] else '')

        # Tasks for leader (target='all' or 'leader' or their username)
        leader_tasks = db.execute("""
            SELECT t.id, t.title, t.body, t.priority, t.due_date, t.created_at,
                   d.done_at
            FROM admin_tasks t
            LEFT JOIN admin_task_done d ON d.task_id=t.id AND d.username=?
            WHERE t.is_done=0
              AND (t.target='all' OR t.target='leader' OR t.target=?)
            ORDER BY t.priority='urgent' DESC, t.created_at DESC
        """, (username, username)).fetchall()

        db.close()
        app_register_url = url_for('register', _external=True)

        return render_template('working.html',
            is_admin=False,
            is_leader=True,
            pipeline_auto_expire_statuses=PIPELINE_AUTO_EXPIRE_STATUSES,
            sla_soft_watch_exclude=SLA_SOFT_WATCH_EXCLUDE,

            # Own leads
            own_stage1=own_stage1,
            own_side_pipeline=own_side,
            own_day1=own_day1,
            own_day2=own_day2,
            own_day3=own_day3,
            own_pending=own_pending,
            own_closing=own_closing,
            own_past=own_past,

            # Team leads
            team_stage1=team_stage1,
            team_side_pipeline=team_side,
            team_day1=team_day1,
            team_day2=team_day2,
            team_day3=team_day3,
            team_pending=team_pending,
            team_closing=team_closing,
            team_past=team_past,

            leader_day1_work=leader_day1_work,
            leader_day2_work=leader_day2_work,
            leader_day3_work=leader_day3_work,
            leader_pending_work=leader_pending_work,
            leader_closing_work=leader_closing_work,
            leader_d2_upline=leader_d2_upline,

            # Tutorial onboarding
            leader_fbo_id=leader_fbo_id,
            app_register_url=app_register_url,
            app_tutorial_link=app_tutorial_link,

            # Counts
            own_pending_calls=own_pending_calls,
            team_pending_calls=team_pending_calls,
            own_batches_due=own_batches_due,
            team_batches_due=team_batches_due,

            # Downline info
            downline_members=downline_members,
            has_team=bool(_downline_only),

            # Backward compatibility (some template parts may use these)
            stage1_leads=own_stage1 + team_stage1,
            day1_leads=own_day1 + team_day1,
            day2_leads=own_day2 + team_day2,
            day3_leads=own_day3 + team_day3,
            pending_leads=own_pending + team_pending,
            past_leads=own_past,

            today_score=today_score,
            streak=streak,
            today_actions=leader_today_actions,
            tracks=TRACKS,
            statuses=STATUSES,
            batch_videos=leader_batch_videos,
            user_role='leader',
            call_status_values=CALL_STATUS_VALUES,
            team_call_status_values=TEAM_CALL_STATUS_VALUES,
            csrf_token=session.get('_csrf_token', ''),
            enroll_days=enroll_days,
            enroll_pdfs=enroll_pdfs,
            recent_shares=recent_shares,
            team_leads=team_leads_for_enroll,
            batch_watch_urls=_batch_watch_urls(),
            enrollment_video_url=enrollment_video_url,
            enrollment_watch_url=url_for('watch_enrollment', _external=True) if enrollment_video_url else '',
            enrollment_video_title=enrollment_video_title,
            show_day1_batches=True,
            leader_tasks=leader_tasks,
            workboard_poll_ms=60_000,
        )

    # ── Team member view (own leads only) ───────────────────────────
    _tw, _tp = _working_assigned_where(db, 'team', username, 'own')
    _base_team = "SELECT * FROM leads WHERE in_pool=0 AND deleted_at='' " + _tw + " "
    _e_ph = ','.join('?' * len(ENROLLMENT_STATUSES))
    _enr_ph = ','.join('?' * len(ENROLLED_STATUSES))
    _side_ph = ','.join('?' * len(WORKING_SIDE_PIPELINE_STATUSES))

    # Enrollment column: prospecting + paid-before-Day-1 only (not Retarget / on-hold)
    stage1_leads = db.execute(
        _base_team + f"AND (status IN ({_e_ph}) OR status IN ({_enr_ph})) ORDER BY updated_at DESC",
        _tp + list(ENROLLMENT_STATUSES) + list(ENROLLED_STATUSES),
    ).fetchall()
    side_pipeline_leads = db.execute(
        _base_team + f"AND status IN ({_side_ph}) ORDER BY updated_at DESC",
        _tp + list(WORKING_SIDE_PIPELINE_STATUSES),
    ).fetchall()
    day1_leads = db.execute(
        _base_team + "AND status='Day 1' ORDER BY updated_at DESC",
        _tp
    ).fetchall()
    day2_leads = db.execute(
        _base_team + "AND status='Day 2' ORDER BY updated_at DESC",
        _tp
    ).fetchall()
    day3_leads = db.execute(
        _base_team + "AND status IN ('Interview','Track Selected') ORDER BY updated_at DESC",
        _tp
    ).fetchall()
    pending_leads = db.execute(
        _base_team + "AND status='Seat Hold Confirmed' ORDER BY updated_at DESC",
        _tp
    ).fetchall()
    past_leads = db.execute(
        _base_team + "AND status IN ('Fully Converted','Converted','Lost') ORDER BY updated_at DESC LIMIT 30",
        _tp
    ).fetchall()

    today_score, streak = _get_today_score(db, username)

    # Pending action counts (same assigned_user_id filter)
    _count_base = "SELECT COUNT(*) FROM leads WHERE in_pool=0 AND deleted_at='' " + _tw + " "
    pending_calls = db.execute(
        _count_base + f"AND status IN ({_e_ph}) AND (call_result='' OR call_result IN ('Call Later','Follow-up Needed','Follow Up Later','Callback Requested'))",
        _tp + list(ENROLLMENT_STATUSES)
    ).fetchone()[0] or 0
    # Pre–Video Sent funnel: rely on Lead Status (not call_status — team uses dial-only call_status)
    videos_to_send = db.execute(
        _count_base + "AND status IN ('New Lead','New','Contacted','Invited')",
        _tp
    ).fetchone()[0] or 0
    # Team: ₹196 ke baad leader par handoff — Day1+/closing counts unke kaam, yahan nahi
    batches_due = 0
    closings_due = 0

    today_actions = {
        'pending_calls':  pending_calls,
        'videos_to_send': videos_to_send,
        'batches_due':    batches_due,
        'closings_due':   closings_due,
    }

    # Build batch_videos BEFORE closing database
    team_batch_videos = {
        'd1_morning_v1': _get_setting(db, 'batch_d1_morning_v1', ''),
        'd1_morning_v2': _get_setting(db, 'batch_d1_morning_v2', ''),
        'd1_afternoon_v1': _get_setting(db, 'batch_d1_afternoon_v1', ''),
        'd1_afternoon_v2': _get_setting(db, 'batch_d1_afternoon_v2', ''),
        'd1_evening_v1': _get_setting(db, 'batch_d1_evening_v1', ''),
        'd1_evening_v2': _get_setting(db, 'batch_d1_evening_v2', ''),
        'd2_morning_v1': _get_setting(db, 'batch_d2_morning_v1', ''),
        'd2_morning_v2': _get_setting(db, 'batch_d2_morning_v2', ''),
        'd2_afternoon_v1': _get_setting(db, 'batch_d2_afternoon_v1', ''),
        'd2_afternoon_v2': _get_setting(db, 'batch_d2_afternoon_v2', ''),
        'd2_evening_v1': _get_setting(db, 'batch_d2_evening_v1', ''),
        'd2_evening_v2': _get_setting(db, 'batch_d2_evening_v2', ''),
    }
    enrollment_video_url   = _get_setting(db, 'enrollment_video_url', '')
    enrollment_video_title = _get_setting(db, 'enrollment_video_title', 'Enrollment Video')
    show_day1_batches     = True  # all roles can see batch status (only leader/admin can toggle)

    # Tasks for team member
    team_tasks = db.execute("""
        SELECT t.id, t.title, t.body, t.priority, t.due_date, t.created_at,
               d.done_at
        FROM admin_tasks t
        LEFT JOIN admin_task_done d ON d.task_id=t.id AND d.username=?
        WHERE t.is_done=0
          AND (t.target='all' OR t.target='team' OR t.target=?)
        ORDER BY t.priority='urgent' DESC, t.created_at DESC
    """, (username, username)).fetchall()

    # Enrich team view leads with heat + next_action
    stage1_leads  = _enrich_leads(stage1_leads)
    side_pipeline_leads = _enrich_leads(side_pipeline_leads)
    day1_leads    = _enrich_leads(day1_leads)
    day2_leads    = _enrich_leads(day2_leads)
    day3_leads    = _enrich_leads(day3_leads)
    pending_leads = _enrich_leads(pending_leads)
    db.close()
    return render_template('working.html',
        is_admin=False,
        pipeline_auto_expire_statuses=PIPELINE_AUTO_EXPIRE_STATUSES,
        sla_soft_watch_exclude=SLA_SOFT_WATCH_EXCLUDE,
        stage1_leads=stage1_leads,
        side_pipeline_leads=side_pipeline_leads,
        day1_leads=day1_leads,
        day2_leads=day2_leads,
        day3_leads=day3_leads,
        pending_leads=pending_leads,
        past_leads=past_leads,
        today_score=today_score,
        streak=streak,
        today_actions=today_actions,
        tracks=TRACKS,
        statuses=STATUSES,
        team_allowed_statuses=TEAM_ALLOWED_STATUSES,
        batch_videos=team_batch_videos,
        batch_watch_urls=_batch_watch_urls(),
        enrollment_video_url=enrollment_video_url,
        enrollment_watch_url=url_for('watch_enrollment', _external=True) if enrollment_video_url else '',
        enrollment_video_title=enrollment_video_title,
        show_day1_batches=show_day1_batches,
        user_role=role or 'team',
        call_status_values=CALL_STATUS_VALUES,
        team_call_status_values=TEAM_CALL_STATUS_VALUES,
        csrf_token=session.get('_csrf_token', ''),
        leader_tasks=team_tasks,
        workboard_poll_ms=0,
    )












# ──────────────────────────────────────────────────────────────────────
#  Pipeline Stage Advance (Part 5)
# ──────────────────────────────────────────────────────────────────────







@app.route('/admin/members/<username>/promote-leader', methods=['POST'])
@admin_required
def admin_promote_leader(username):
    """Toggle a team member between team and leader roles."""
    db = get_db()
    user = db.execute("SELECT role FROM users WHERE username=?", (username,)).fetchone()
    if not user:
        db.close()
        flash('Member not found.', 'danger')
        return redirect(url_for('admin_members'))

    current_role = user['role']
    if current_role == 'team':
        new_role = 'leader'
        msg = f'{username} promoted to Leader.'
    elif current_role == 'leader':
        new_role = 'team'
        msg = f'{username} demoted back to Team.'
    else:
        db.close()
        flash('Only team/leader roles can be toggled.', 'warning')
        return redirect(url_for('admin_members'))

    db.execute("UPDATE users SET role=? WHERE username=?", (new_role, username))
    db.commit()
    _log_activity(db, acting_username(), 'role_change', f'{username}: {current_role} to {new_role}')
    db.close()
    flash(msg, 'success')
    return redirect(url_for('admin_members'))


@app.route('/admin/members/<username>/set-upline', methods=['POST'])
@admin_required
def admin_set_upline(username):
    """Admin assigns an upline leader to a team member (by leader username or leader FBO ID)."""
    upline_username = request.form.get('upline_username', '').strip()
    upline_fbo_in = request.form.get('upline_fbo_id', '').strip()
    db = get_db()
    user = db.execute("SELECT role FROM users WHERE username=?", (username,)).fetchone()
    if not user or user['role'] not in ('team', 'leader'):
        db.close()
        flash('Member not found or invalid role.', 'danger')
        return redirect(url_for('admin_members'))

    from helpers import validate_upline_assignment_roles

    child_role = (user['role'] or '').strip()
    if not upline_fbo_in and not upline_username:
        db.close()
        flash('Upline is required. Team must map to Leader, Leader must map to Admin.', 'danger')
        return redirect(url_for('admin_members'))

    resolved_un = ''
    upline_fbo_id = ''
    parent_role = ''
    if upline_fbo_in:
        parent = db.execute(
            "SELECT username, COALESCE(NULLIF(TRIM(fbo_id),''), '') AS fb "
            "FROM users WHERE TRIM(fbo_id)=? AND status='approved'",
            (upline_fbo_in,),
        ).fetchone()
        if not parent:
            db.close()
            flash(f'Upline with FBO ID "{upline_fbo_in}" not found or not approved.', 'danger')
            return redirect(url_for('admin_members'))
        prow = db.execute(
            "SELECT role FROM users WHERE username=?",
            ((parent['username'] or '').strip(),),
        ).fetchone()
        parent_role = (prow['role'] or '').strip() if prow else ''
        resolved_un = (parent['username'] or '').strip()
        upline_fbo_id = (parent['fb'] or upline_fbo_in).strip()
    elif upline_username:
        parent = db.execute(
            "SELECT username, COALESCE(NULLIF(TRIM(fbo_id),''), '') AS fb "
            "FROM users WHERE username=? AND status='approved'",
            (upline_username,),
        ).fetchone()
        if not parent:
            db.close()
            flash(f'Upline "{upline_username}" not found or not approved.', 'danger')
            return redirect(url_for('admin_members'))
        prow = db.execute(
            "SELECT role FROM users WHERE username=?",
            ((parent['username'] or '').strip(),),
        ).fetchone()
        parent_role = (prow['role'] or '').strip() if prow else ''
        resolved_un = (parent['username'] or '').strip()
        upline_fbo_id = (parent['fb'] or '').strip()

    if resolved_un:
        ok, msg = validate_upline_assignment_roles(child_role, parent_role)
        if not ok:
            db.close()
            flash(f'{msg} Selected: @{resolved_un} ({parent_role}).', 'danger')
            return redirect(url_for('admin_members'))

    db.execute(
        "UPDATE users SET upline_username=?, upline_name=?, upline_fbo_id=?, "
        "upline_id=(SELECT id FROM users WHERE username=? LIMIT 1) "
        "WHERE username=?",
        (resolved_un, resolved_un, upline_fbo_id, resolved_un, username),
    )
    if child_role in ('team', 'leader') and resolved_un:
        from services.hierarchy_lead_sync import sync_member_under_parent
        sync_member_under_parent(db, username, resolved_un)
    db.commit()
    _log_activity(
        db,
        acting_username(),
        'set_upline',
        f'{username} upline → {resolved_un or "(none)"} fbo={upline_fbo_id or "-"}',
    )
    db.close()
    flash(f'Upline for @{username} set to @{resolved_un or "none"}', 'success')
    return redirect(url_for('admin_members'))



# ─────────────────────────────────────────────────────────────────
#  Module 1 — Prospect Timeline (JSON endpoint)
# ─────────────────────────────────────────────────────────────────




# ─────────────────────────────────────────────────────────────────
#  Module 3 — Leader Coaching Panel
# ─────────────────────────────────────────────────────────────────



if __name__ == '__main__':
    _debug = os.environ.get('FLASK_DEBUG', '').lower() in ('1', 'true', 'yes')
    app.run(debug=_debug, host='0.0.0.0', port=int(os.environ.get('PORT', 5003)))
