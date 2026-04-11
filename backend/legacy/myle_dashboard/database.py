import logging
import os
import re
import secrets
import sqlite3
from contextlib import contextmanager
from werkzeug.security import generate_password_hash, check_password_hash

# On Render: set DATABASE_PATH=/var/data/leads.db (persistent disk)
# Locally: falls back to leads.db in project folder
DATABASE = os.environ.get(
    'DATABASE_PATH',
    os.path.join(os.path.dirname(__file__), 'leads.db')
)


def _open_raw_db():
    """Open a fresh SQLite connection (no Flask context)."""
    conn = sqlite3.connect(DATABASE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA cache_size=-4000")
    return conn


class _RequestScopedConn:
    """Thin wrapper: delegates everything to the real connection but makes .close() a no-op.
    The teardown handler calls .real_close() to actually close."""
    __slots__ = ('_conn',)

    def __init__(self, conn):
        object.__setattr__(self, '_conn', conn)

    def close(self):
        pass

    def real_close(self):
        self._conn.close()

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def __enter__(self):
        return self._conn.__enter__()

    def __exit__(self, *args):
        return self._conn.__exit__(*args)


def get_db():
    """Return the request-scoped DB connection (reused via Flask g).
    Inside a request: returns a wrapper where .close() is a no-op (teardown handles it).
    Outside a request (CLI, bg threads, tests): returns a raw connection."""
    try:
        from flask import g
        if 'db' not in g:
            g.db = _RequestScopedConn(_open_raw_db())
        return g.db
    except RuntimeError:
        return _open_raw_db()


def close_db(e=None):
    """Teardown handler: actually close the request-scoped connection."""
    try:
        from flask import g
        db = g.pop('db', None)
        if db is not None:
            db.real_close()
    except RuntimeError:
        pass


@contextmanager
def sqlite_connection():
    """Open a SQLite connection and always close (for non-Flask callers, e.g. FastAPI)."""
    conn = _open_raw_db()
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    conn = get_db()
    cursor = conn.cursor()

    # Leads table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS leads (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            name           TEXT    NOT NULL,
            phone          TEXT    NOT NULL,
            email          TEXT,
            referred_by    TEXT,
            assigned_to    TEXT    NOT NULL DEFAULT '',
            assigned_user_id INTEGER,
            source         TEXT    NOT NULL DEFAULT '',
            status         TEXT    NOT NULL DEFAULT 'New',
            payment_done   INTEGER NOT NULL DEFAULT 0,
            payment_amount REAL    NOT NULL DEFAULT 0.0,
            revenue        REAL    NOT NULL DEFAULT 0.0,
            day1_done      INTEGER NOT NULL DEFAULT 0,
            day2_done      INTEGER NOT NULL DEFAULT 0,
            interview_done INTEGER NOT NULL DEFAULT 0,
            follow_up_date TEXT    NOT NULL DEFAULT '',
            call_result    TEXT    NOT NULL DEFAULT '',
            notes          TEXT,
            city           TEXT    NOT NULL DEFAULT '',
            deleted_at     TEXT    NOT NULL DEFAULT '',
            in_pool        INTEGER NOT NULL DEFAULT 0,
            pool_price     REAL    NOT NULL DEFAULT 0.0,
            claimed_at     TEXT    DEFAULT NULL,
            last_contacted TEXT    NOT NULL DEFAULT '',
            contact_count  INTEGER NOT NULL DEFAULT 0,
            created_at     TEXT    NOT NULL DEFAULT (datetime('now', '+5 hours', '+30 minutes')),
            updated_at     TEXT    NOT NULL DEFAULT (datetime('now', '+5 hours', '+30 minutes')),
            d1_morning     INTEGER NOT NULL DEFAULT 0,
            d1_afternoon   INTEGER NOT NULL DEFAULT 0,
            d1_evening     INTEGER NOT NULL DEFAULT 0,
            d2_morning     INTEGER NOT NULL DEFAULT 0,
            d2_afternoon   INTEGER NOT NULL DEFAULT 0,
            d2_evening     INTEGER NOT NULL DEFAULT 0,
            working_date        TEXT    NOT NULL DEFAULT '',
            daily_score         INTEGER NOT NULL DEFAULT 0,
            pipeline_entered_at TEXT    NOT NULL DEFAULT '',
            flow_started_at     TEXT    NOT NULL DEFAULT '',
            payment_proof_path  TEXT    NOT NULL DEFAULT '',
            enrolled_at         TEXT    NOT NULL DEFAULT '',
            enrolled_by         TEXT    NOT NULL DEFAULT '',
            CHECK ((in_pool = 1) OR (assigned_user_id IS NOT NULL AND assigned_user_id != 0))
        )
    """)

    # Daily Reports table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_reports (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            username         TEXT    NOT NULL,
            upline_name      TEXT    NOT NULL DEFAULT '',
            report_date      TEXT    NOT NULL,
            total_calling    INTEGER NOT NULL DEFAULT 0,
            pdf_covered      INTEGER NOT NULL DEFAULT 0,
            calls_picked     INTEGER NOT NULL DEFAULT 0,
            wrong_numbers    INTEGER NOT NULL DEFAULT 0,
            enrollments_done INTEGER NOT NULL DEFAULT 0,
            pending_enroll   INTEGER NOT NULL DEFAULT 0,
            underage         INTEGER NOT NULL DEFAULT 0,
            leads_educated   TEXT    NOT NULL DEFAULT '',
            plan_2cc         INTEGER NOT NULL DEFAULT 0,
            seat_holdings    INTEGER NOT NULL DEFAULT 0,
            remarks          TEXT,
            submitted_at     TEXT    NOT NULL DEFAULT (datetime('now', '+5 hours', '+30 minutes')),
            UNIQUE(username, report_date)
        )
    """)

    # Team members table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS team_members (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT    NOT NULL UNIQUE,
            phone       TEXT,
            joined_at   TEXT    NOT NULL DEFAULT (datetime('now', '+5 hours', '+30 minutes'))
        )
    """)

    # Users table (authentication)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id                    INTEGER PRIMARY KEY AUTOINCREMENT,
            username              TEXT    NOT NULL UNIQUE,
            password              TEXT    NOT NULL,
            role                  TEXT    NOT NULL DEFAULT 'team',
            fbo_id                TEXT    NOT NULL DEFAULT '',
            upline_name           TEXT    NOT NULL DEFAULT '',
            phone                 TEXT    NOT NULL DEFAULT '',
            email                 TEXT    NOT NULL DEFAULT '',
            status                TEXT    NOT NULL DEFAULT 'pending',
            display_picture       TEXT    NOT NULL DEFAULT '',
            calling_reminder_time TEXT    NOT NULL DEFAULT '',
            training_required     INTEGER NOT NULL DEFAULT 0,
            training_status       TEXT    NOT NULL DEFAULT 'not_required',
            joining_date          TEXT    NOT NULL DEFAULT '',
            certificate_path      TEXT    NOT NULL DEFAULT '',
            certificate_blob      TEXT    NOT NULL DEFAULT '',
            badges_json           TEXT    NOT NULL DEFAULT '[]',
            upline_username       TEXT    NOT NULL DEFAULT '',
            upline_fbo_id         TEXT    NOT NULL DEFAULT '',
            total_points          INTEGER NOT NULL DEFAULT 0,
            user_stage            TEXT    NOT NULL DEFAULT 'day1',
            last_activity_at      TEXT    NOT NULL DEFAULT '',
            created_at            TEXT    NOT NULL DEFAULT (datetime('now', '+5 hours', '+30 minutes'))
        )
    """)

    # App settings (key-value store)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS app_settings (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL DEFAULT ''
        )
    """)

    # Wallet recharge requests
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS wallet_recharges (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            username     TEXT    NOT NULL,
            amount       REAL    NOT NULL,
            utr_number   TEXT    NOT NULL DEFAULT '',
            status       TEXT    NOT NULL DEFAULT 'pending',
            requested_at TEXT    NOT NULL DEFAULT (datetime('now', '+5 hours', '+30 minutes')),
            processed_at TEXT    NOT NULL DEFAULT '',
            admin_note   TEXT    NOT NULL DEFAULT ''
        )
    """)

    # Admin announcements (notice board)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS announcements (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            message    TEXT    NOT NULL,
            created_by TEXT    NOT NULL DEFAULT 'admin',
            pin        INTEGER NOT NULL DEFAULT 0,
            created_at TEXT    NOT NULL DEFAULT (datetime('now', '+5 hours', '+30 minutes'))
        )
    """)

    # Lead notes / timeline
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS lead_notes (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id    INTEGER NOT NULL,
            username   TEXT    NOT NULL,
            note       TEXT    NOT NULL,
            created_at TEXT    NOT NULL DEFAULT (datetime('now', '+5 hours', '+30 minutes'))
        )
    """)

    # Web Push subscriptions (VAPID)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS push_subscriptions (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            username   TEXT    NOT NULL,
            endpoint   TEXT    NOT NULL UNIQUE,
            auth       TEXT    NOT NULL DEFAULT '',
            p256dh     TEXT    NOT NULL DEFAULT '',
            created_at TEXT    NOT NULL DEFAULT (datetime('now', '+5 hours', '+30 minutes'))
        )
    """)

    # Password reset tokens
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS password_reset_tokens (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            username   TEXT    NOT NULL,
            token      TEXT    NOT NULL UNIQUE,
            expires_at TEXT    NOT NULL,
            used       INTEGER NOT NULL DEFAULT 0,
            created_at TEXT    NOT NULL DEFAULT (datetime('now', '+5 hours', '+30 minutes'))
        )
    """)

    # Activity / Punch Log
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS activity_log (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            username   TEXT    NOT NULL,
            event_type TEXT    NOT NULL,
            details    TEXT    NOT NULL DEFAULT '',
            ip_address TEXT    NOT NULL DEFAULT '',
            created_at TEXT    NOT NULL DEFAULT (datetime('now', '+5 hours', '+30 minutes'))
        )
    """)

    # Training videos (one per day, 7 days)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS training_videos (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            day_number  INTEGER NOT NULL UNIQUE,
            title       TEXT    NOT NULL DEFAULT '',
            youtube_url TEXT    NOT NULL DEFAULT '',
            podcast_url TEXT    NOT NULL DEFAULT '',
            pdf_url     TEXT    NOT NULL DEFAULT '',
            podcast_blob TEXT   NOT NULL DEFAULT '',
            pdf_blob    TEXT    NOT NULL DEFAULT '',
            description TEXT    NOT NULL DEFAULT '',
            created_at  TEXT    NOT NULL DEFAULT (datetime('now', '+5 hours', '+30 minutes'))
        )
    """)

    # Training progress per user per day
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS training_progress (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            username     TEXT    NOT NULL,
            day_number   INTEGER NOT NULL,
            completed    INTEGER NOT NULL DEFAULT 0,
            completed_at TEXT    NOT NULL DEFAULT '',
            UNIQUE(username, day_number)
        )
    """)

    # Monthly targets per member
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS targets (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            username     TEXT NOT NULL,
            metric       TEXT NOT NULL,
            target_value REAL NOT NULL DEFAULT 0,
            month        TEXT NOT NULL,
            created_by   TEXT NOT NULL DEFAULT 'admin',
            created_at   TEXT NOT NULL DEFAULT (datetime('now', '+5 hours', '+30 minutes')),
            UNIQUE(username, metric, month)
        )
    """)

    # User achievement badges
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_badges (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            username    TEXT NOT NULL,
            badge_key   TEXT NOT NULL,
            unlocked_at TEXT NOT NULL DEFAULT (datetime('now', '+5 hours', '+30 minutes')),
            UNIQUE(username, badge_key)
        )
    """)

    # Training test questions (MCQ)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS training_questions (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            question       TEXT    NOT NULL,
            option_a       TEXT    NOT NULL DEFAULT '',
            option_b       TEXT    NOT NULL DEFAULT '',
            option_c       TEXT    NOT NULL DEFAULT '',
            option_d       TEXT    NOT NULL DEFAULT '',
            correct_answer TEXT    NOT NULL DEFAULT 'a',
            sort_order     INTEGER NOT NULL DEFAULT 0,
            created_at     TEXT    NOT NULL DEFAULT (datetime('now', '+5 hours', '+30 minutes'))
        )
    """)

    # Training test attempt history
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS training_test_attempts (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            username        TEXT    NOT NULL,
            score           INTEGER NOT NULL DEFAULT 0,
            total_questions INTEGER NOT NULL DEFAULT 0,
            passed          INTEGER NOT NULL DEFAULT 0,
            attempted_at    TEXT    NOT NULL DEFAULT (datetime('now', '+5 hours', '+30 minutes'))
        )
    """)

    # Bonus/additional videos
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bonus_videos (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            title       TEXT    NOT NULL DEFAULT '',
            youtube_url TEXT    NOT NULL DEFAULT '',
            description TEXT    NOT NULL DEFAULT '',
            sort_order  INTEGER NOT NULL DEFAULT 0,
            created_at  TEXT    NOT NULL DEFAULT (datetime('now', '+5 hours', '+30 minutes'))
        )
    """)

    conn.commit()
    conn.close()


def _rebuild_leads_nullable_claimed_at(cursor, conn):
    """Recreate `leads` with nullable claimed_at when sqlite_master hacks are blocked."""
    row = cursor.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='leads'"
    ).fetchone()
    if not row or not row[0]:
        raise RuntimeError("leads table SQL missing")
    old_sql = row[0].strip()
    new_sql = re.sub(
        r"claimed_at\s+TEXT\s+NOT\s+NULL\s+DEFAULT\s+''",
        "claimed_at     TEXT    DEFAULT NULL",
        old_sql,
        count=1,
        flags=re.IGNORECASE,
    )
    if new_sql == old_sql:
        new_sql = re.sub(
            r'claimed_at\s+TEXT\s+NOT\s+NULL\s+DEFAULT\s+""',
            "claimed_at     TEXT    DEFAULT NULL",
            old_sql,
            count=1,
            flags=re.IGNORECASE,
        )
    if new_sql == old_sql:
        raise RuntimeError("could not relax claimed_at in CREATE TABLE sql")
    tmp = "leads__mig_claimed_at"
    ddl = re.sub(
        r"(?i)CREATE\s+TABLE\s+leads\b",
        f"CREATE TABLE {tmp}",
        new_sql,
        count=1,
    )
    if ddl == new_sql:
        raise RuntimeError("could not rename leads table in DDL")
    log = logging.getLogger("database")
    cursor.execute("BEGIN IMMEDIATE")
    try:
        cursor.execute(ddl)
        cursor.execute(f"INSERT INTO {tmp} SELECT * FROM leads")
        cursor.execute("DROP TABLE leads")
        cursor.execute(f"ALTER TABLE {tmp} RENAME TO leads")
        cursor.execute("UPDATE leads SET claimed_at=NULL WHERE claimed_at=''")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    log.info("leads table rebuilt: claimed_at is nullable; '' values cleared to NULL")


def check_claimed_at_empty_string_invariant(cursor, conn):
    """Daily / boot discipline: ``SELECT COUNT(*) FROM leads WHERE claimed_at=''`` must be 0.

    Empty string is legacy; normalized to NULL. After a best-effort UPDATE, logs CRITICAL if
    any rows remain (usually means claimed_at is still NOT NULL in schema).
    """
    log = logging.getLogger("database")
    try:
        cursor.execute("UPDATE leads SET claimed_at=NULL WHERE claimed_at=''")
    except Exception as e:
        log.error("claimed_at discipline: UPDATE … SET claimed_at=NULL WHERE claimed_at='' failed: %s", e)
        return
    try:
        n = cursor.execute("SELECT COUNT(*) FROM leads WHERE claimed_at=''").fetchone()[0]
    except Exception as e:
        log.error("claimed_at discipline: COUNT(*) WHERE claimed_at='' failed: %s", e)
        return
    if n:
        rows = cursor.execute(
            "SELECT id, phone, in_pool, assigned_to FROM leads WHERE claimed_at='' LIMIT 5"
        ).fetchall()
        sample = [dict(r) for r in rows]
        log.critical(
            "claimed_at discipline VIOLATION: expected 0 rows with claimed_at='', found %s. "
            "Sample: %s. Fix schema/migration so NULL is allowed on claimed_at.",
            n,
            sample,
        )


def _fbo_id_signature_for_dedupe(value: str) -> str:
    """Digits-only signature: #910…, dashed FBOs, and plain numeric ids compare equal."""
    return re.sub(r'\D', '', (value or ''))


def migration_align_upline_fbo_with_resolved_parent(cursor) -> int:
    """
    When upline_username / upline_name resolves to parent P but upline_fbo_id does not
    match P.fbo_id, the downline CTE attaches the user under BOTH P (via name) and
    whoever owns the stale FBO digit (often a upline leader). Align upline_fbo_id + upline_id.
    Returns number of users updated.
    """
    updated = 0
    rows = cursor.execute(
        """
        SELECT username, upline_username, upline_name, upline_fbo_id
        FROM users
        WHERE status = 'approved' AND role IN ('team', 'leader')
        """
    ).fetchall()
    for r in rows:
        child_un = (r['username'] or '').strip()
        pun = (r['upline_username'] or '').strip() or (r['upline_name'] or '').strip()
        if not child_un or not pun:
            continue
        parent = cursor.execute(
            "SELECT id, username, TRIM(COALESCE(fbo_id,'')) AS fbo FROM users WHERE username=? AND status='approved' LIMIT 1",
            (pun,),
        ).fetchone()
        if not parent:
            continue
        want_fbo = (parent['fbo'] or '').strip()
        if not want_fbo:
            continue
        cur_sig = _fbo_id_signature_for_dedupe(r['upline_fbo_id'])
        want_sig = _fbo_id_signature_for_dedupe(want_fbo)
        if cur_sig == want_sig:
            continue
        pid = int(parent['id'])
        cursor.execute(
            "UPDATE users SET upline_fbo_id=?, upline_id=? WHERE username=?",
            (want_fbo, pid, child_un),
        )
        if cursor.rowcount:
            updated += int(cursor.rowcount)
    return updated


def _merge_loser_into_winner_users_row(cursor, winner_id: int, loser_id: int, winner_un: str, loser_un: str) -> None:
    """Re-point foreign username/id references from loser to winner; then delete loser."""
    log = logging.getLogger("database")

    def _del_conflicting_daily_reports():
        for row in cursor.execute(
            "SELECT id, report_date FROM daily_reports WHERE username=?",
            (loser_un,),
        ).fetchall():
            ex = cursor.execute(
                "SELECT 1 FROM daily_reports WHERE username=? AND report_date=? LIMIT 1",
                (winner_un, row['report_date']),
            ).fetchone()
            if ex:
                cursor.execute("DELETE FROM daily_reports WHERE id=?", (row['id'],))
            else:
                cursor.execute(
                    "UPDATE daily_reports SET username=? WHERE id=?",
                    (winner_un, row['id']),
                )

    def _reassign_unique_table(table: str, key_cols) -> None:
        rows_sub = cursor.execute(
            f"SELECT * FROM {table} WHERE username=?",
            (loser_un,),
        ).fetchall()
        for row in rows_sub:
            pk = row['id']
            where = " AND ".join("{}=?".format(c) for c in key_cols)
            vals = tuple(row[c] for c in key_cols)
            conflict = cursor.execute(
                f"SELECT 1 FROM {table} WHERE username=? AND {where} LIMIT 1",
                (winner_un,) + vals,
            ).fetchone()
            if conflict:
                cursor.execute(f"DELETE FROM {table} WHERE id=?", (pk,))
            else:
                cursor.execute(f"UPDATE {table} SET username=? WHERE id=?", (winner_un, pk))

    try:
        cursor.execute(
            "UPDATE leads SET assigned_user_id=? WHERE assigned_user_id=?",
            (winner_id, loser_id),
        )
        for col in (
            'current_owner',
            'enrolled_by',
            'referred_by',
            'assigned_to',
            'stale_worker',
            'stale_worker_by',
            'retarget_assigned_by',
            'payment_proof_reviewed_by',
        ):
            try:
                cursor.execute(
                    f"UPDATE leads SET {col}=? WHERE TRIM(COALESCE({col},''))=?",
                    (winner_un, loser_un),
                )
            except Exception as e:
                log.warning("merge users: leads.%s repoint failed: %s", col, e)

        cursor.execute(
            "UPDATE users SET upline_username=?, upline_name=? "
            "WHERE TRIM(COALESCE(upline_username,''))=? OR TRIM(COALESCE(upline_name,''))=?",
            (winner_un, winner_un, loser_un, loser_un),
        )

        _del_conflicting_daily_reports()

        for tbl in (
            'wallet_recharges',
            'point_history',
            'activity_log',
            'training_test_attempts',
        ):
            try:
                cursor.execute(f"UPDATE {tbl} SET username=? WHERE username=?", (winner_un, loser_un))
            except Exception as e:
                log.warning("merge users: %s bulk username update failed: %s", tbl, e)

        try:
            cursor.execute(
                "UPDATE push_subscriptions SET username=? WHERE username=?",
                (winner_un, loser_un),
            )
        except Exception:
            pass
        try:
            cursor.execute(
                "UPDATE password_reset_tokens SET username=? WHERE username=?",
                (winner_un, loser_un),
            )
        except Exception:
            pass

        for tbl, keys in (
            ('training_progress', ('day_number',)),
            ('user_badges', ('badge_key',)),
            ('targets', ('metric', 'month')),
            ('daily_scores', ('score_date',)),
        ):
            try:
                _reassign_unique_table(tbl, keys)
            except Exception as e:
                log.warning("merge users: %s: %s", tbl, e)

        lw = cursor.execute(
            "SELECT COALESCE(total_points,0) FROM users WHERE id=?",
            (loser_id,),
        ).fetchone()
        loser_pts = int(lw[0] or 0) if lw else 0
        if loser_pts:
            cursor.execute(
                "UPDATE users SET total_points = COALESCE(total_points,0) + ? WHERE id=?",
                (loser_pts, winner_id),
            )

        cursor.execute("DELETE FROM users WHERE id=?", (loser_id,))
    except Exception:
        log.exception("merge users failed winner=%s loser=%s", winner_un, loser_un)
        raise


def migration_dedupe_case_variant_same_fbo_users(cursor) -> int:
    """
    Merge rows that are almost certainly the same person:
    identical LOWER(username) + same FBO digit signature (handles # prefix / punctuation).

    Keeps the row with more lead ownership signals (assigned + current_owner).
    """
    log = logging.getLogger("database")
    groups = cursor.execute(
        """
        SELECT LOWER(TRIM(username)) AS lu,
               REPLACE(REPLACE(REPLACE(TRIM(COALESCE(fbo_id,'')),'#',''),'-',''),' ','') AS sig,
               COUNT(*) AS c
        FROM users
        WHERE TRIM(COALESCE(fbo_id,'')) != ''
        GROUP BY lu, sig
        HAVING c > 1 AND LENGTH(sig) >= 6
        """
    ).fetchall()
    merged = 0
    for g in groups:
        lu = g['lu']
        sig = g['sig']
        rows = cursor.execute(
            """
            SELECT id, username, role
            FROM users
            WHERE LOWER(TRIM(username)) = ?
              AND REPLACE(REPLACE(REPLACE(TRIM(COALESCE(fbo_id,'')),'#',''),'-',''),' ','') = ?
            ORDER BY id ASC
            """,
            (lu, sig),
        ).fetchall()
        if len(rows) < 2:
            continue
        scored = []
        for r in rows:
            uid = int(r['id'])
            sun = (r['username'] or '').strip()
            na = cursor.execute(
                "SELECT COUNT(*) FROM leads WHERE assigned_user_id=?",
                (uid,),
            ).fetchone()[0] or 0
            nb = cursor.execute(
                "SELECT COUNT(*) FROM leads WHERE TRIM(COALESCE(current_owner,''))=?",
                (sun,),
            ).fetchone()[0] or 0
            scored.append((int(na) + int(nb), uid, sun))
        scored.sort(key=lambda t: (-t[0], -t[1]))
        winner_score, winner_id, winner_un = scored[0]
        del scored[0]
        for _, loser_id, loser_un in scored:
            if winner_id == loser_id:
                continue
            log.info(
                "migration dedupe user: merge %r (id=%d) -> %r (id=%d) sig=%s",
                loser_un,
                loser_id,
                winner_un,
                winner_id,
                sig,
            )
            _merge_loser_into_winner_users_row(cursor, winner_id, loser_id, winner_un, loser_un)
            merged += 1
    return merged


def migrate_db():
    """Safely add new columns to an existing database without data loss."""
    conn = get_db()
    cursor = conn.cursor()

    # --- leads table columns ---
    for col, definition in [
        # Core fields (may be missing from very old DBs)
        ("email",          "TEXT NOT NULL DEFAULT ''"),
        ("referred_by",    "TEXT NOT NULL DEFAULT ''"),
        ("assigned_to",    "TEXT NOT NULL DEFAULT ''"),
        ("source",         "TEXT NOT NULL DEFAULT ''"),
        ("payment_done",   "INTEGER NOT NULL DEFAULT 0"),
        ("payment_amount", "REAL NOT NULL DEFAULT 0.0"),
        ("revenue",        "REAL NOT NULL DEFAULT 0.0"),
        ("notes",          "TEXT NOT NULL DEFAULT ''"),
        ("updated_at",     "TEXT NOT NULL DEFAULT (datetime('now', '+5 hours', '+30 minutes'))"),
        # 3-day funnel flags
        ("day1_done",      "INTEGER NOT NULL DEFAULT 0"),
        ("day2_done",      "INTEGER NOT NULL DEFAULT 0"),
        ("interview_done", "INTEGER NOT NULL DEFAULT 0"),
        # Filtering / routing
        ("follow_up_date", "TEXT NOT NULL DEFAULT ''"),
        ("call_result",    "TEXT NOT NULL DEFAULT ''"),
        ("city",           "TEXT NOT NULL DEFAULT ''"),
        ("deleted_at",     "TEXT NOT NULL DEFAULT ''"),
        # Pool system
        ("in_pool",        "INTEGER NOT NULL DEFAULT 0"),
        ("pool_price",     "REAL NOT NULL DEFAULT 0.0"),
        ("claimed_at",     "TEXT DEFAULT NULL"),
        # Extended funnel fields
        ("track_selected",   "TEXT NOT NULL DEFAULT ''"),
        ("track_price",      "REAL NOT NULL DEFAULT 0.0"),
        ("seat_hold_amount", "REAL NOT NULL DEFAULT 0.0"),
        ("pending_amount",   "REAL NOT NULL DEFAULT 0.0"),
        # Contact tracking
        ("last_contacted",   "TEXT NOT NULL DEFAULT ''"),
        ("contact_count",    "INTEGER NOT NULL DEFAULT 0"),
        ("follow_up_time",   "TEXT NOT NULL DEFAULT ''"),
        # Batch tracking (which batch within each day)
        ("day1_batch",       "TEXT NOT NULL DEFAULT ''"),
        ("day2_batch",       "TEXT NOT NULL DEFAULT ''"),
        ("day3_batch",       "TEXT NOT NULL DEFAULT ''"),
        # 3-Day process batch checkboxes
        ("d1_morning",       "INTEGER NOT NULL DEFAULT 0"),
        ("d1_afternoon",     "INTEGER NOT NULL DEFAULT 0"),
        ("d1_evening",       "INTEGER NOT NULL DEFAULT 0"),
        ("d2_morning",       "INTEGER NOT NULL DEFAULT 0"),
        ("d2_afternoon",     "INTEGER NOT NULL DEFAULT 0"),
        ("d2_evening",       "INTEGER NOT NULL DEFAULT 0"),
        # Working section metadata
        ("working_date",     "TEXT NOT NULL DEFAULT ''"),
        ("daily_score",      "INTEGER NOT NULL DEFAULT 0"),
        # Pipeline system (Part 2)
        ("pipeline_stage",   "TEXT NOT NULL DEFAULT 'enrollment'"),
        ("current_owner",    "TEXT NOT NULL DEFAULT ''"),
        ("call_status",      "TEXT NOT NULL DEFAULT 'Not Called Yet'"),
        ("priority_score",   "INTEGER NOT NULL DEFAULT 0"),
        ("seat_hold_expiry",    "TEXT NOT NULL DEFAULT ''"),
        # Pipeline auto-expiry: timestamp when lead entered active pipeline stage
        ("pipeline_entered_at", "TEXT NOT NULL DEFAULT ''"),
        # Funnel start anchor from first ₹196 execution
        ("flow_started_at", "TEXT NOT NULL DEFAULT ''"),
        # Retarget: set when a leader shares their retarget lead to a team member
        ("retarget_assigned_by", "TEXT NOT NULL DEFAULT ''"),
        # Follow-up discipline (Step 3): missed cycles + no-response strikes
        ("follow_up_missed_count", "INTEGER NOT NULL DEFAULT 0"),
        ("no_response_attempt_count", "INTEGER NOT NULL DEFAULT 0"),
        ("follow_up_miss_logged_for", "TEXT NOT NULL DEFAULT ''"),
        # Day 2 business evaluation (30 Q, gate to Interview / Day 3)
        ("test_status", "TEXT DEFAULT 'pending'"),
        ("test_score", "INTEGER DEFAULT 0"),
        ("test_attempts", "INTEGER DEFAULT 0"),
        ("test_completed_at", "TEXT DEFAULT NULL"),
        ("test_time_taken", "INTEGER DEFAULT 0"),
        ("interview_status", "TEXT DEFAULT ''"),
        ("test_token", "TEXT DEFAULT ''"),
        ("token_expiry", "TEXT DEFAULT ''"),
        # Team ₹196 proof upload (mandatory before handoff to leader)
        ("payment_proof_path", "TEXT NOT NULL DEFAULT ''"),
        # Permanent enrollment timestamp + who enrolled — set once, never overwritten
        ("enrolled_at", "TEXT NOT NULL DEFAULT ''"),
        ("enrolled_by", "TEXT NOT NULL DEFAULT ''"),
        # Leader ₹196 screenshot: admin must approve before Paid / Payment Done (own-assigned leads only)
        ("payment_proof_approval_status", "TEXT NOT NULL DEFAULT 'approved'"),
        ("payment_proof_reviewed_by", "TEXT NOT NULL DEFAULT ''"),
        ("payment_proof_reviewed_at", "TEXT NOT NULL DEFAULT ''"),
        ("payment_proof_reject_note", "TEXT NOT NULL DEFAULT ''"),
        # Stale redistribution — zero-risk working assignment (assigned_user_id never changes)
        ("stale_worker",       "TEXT NOT NULL DEFAULT ''"),
        ("stale_worker_since", "TEXT NOT NULL DEFAULT ''"),
        ("stale_worker_by",    "TEXT NOT NULL DEFAULT ''"),
    ]:
        try:
            cursor.execute(f"ALTER TABLE leads ADD COLUMN {col} {definition}")
        except Exception:
            pass  # column already exists

    # Backfill enrolled_at for leads that already completed enrollment before this column existed
    try:
        cursor.execute(
            """
            UPDATE leads SET enrolled_at = CASE
                WHEN pipeline_stage = 'day1' AND TRIM(COALESCE(pipeline_entered_at,'')) != ''
                    THEN pipeline_entered_at
                ELSE updated_at
            END
            WHERE TRIM(COALESCE(enrolled_at,'')) = ''
              AND (
                  status IN ('Paid ₹196')
                  OR pipeline_stage IN (
                      'day1','day2','day3','plan_2cc','seat_hold',
                      'pending','level_up','closing','training','complete'
                  )
              )
              AND in_pool=0 AND deleted_at=''
            """
        )
        conn.commit()
    except Exception:
        pass

    # Grandfather: leads already past Day 2 should not be blocked by new gate
    try:
        cursor.execute(
            """
            UPDATE leads SET test_status = 'passed'
            WHERE status IN (
                'Interview', 'Track Selected', 'Seat Hold Confirmed', 'Fully Converted',
                'Pending', 'Level Up', 'Training', 'Converted'
            )
            AND (COALESCE(test_status, '') IN ('', 'pending') OR test_status IS NULL)
            """
        )
        cursor.execute(
            """
            UPDATE leads SET interview_status = 'cleared'
            WHERE interview_done = 1
              AND (COALESCE(interview_status, '') = '' OR interview_status IS NULL)
            """
        )
        conn.commit()
    except Exception:
        pass

    # --- Backfill: clear follow-up fields for Lost/Retarget leads ---
    try:
        cursor.execute(
            """
            UPDATE leads
               SET follow_up_date = '',
                   follow_up_time = ''
             WHERE status IN ('Lost', 'Retarget')
               AND (follow_up_date != '' OR follow_up_time != '')
               AND deleted_at = ''
            """
        )
        conn.commit()
    except Exception:
        pass

    # --- claimed_at NULL migration ---
    # Prefer writable_schema; on modern SQLite that often fails ("sqlite_master may not be
    # modified"), rebuild the table with nullable claimed_at, then normalize '' → NULL.
    _dblog = logging.getLogger("database")
    col_meta = {}
    try:
        col_meta = {c[1]: c[3] for c in cursor.execute("PRAGMA table_info(leads)").fetchall()}
    except Exception as _e:
        _dblog.warning("claimed_at migration: PRAGMA table_info(leads) failed: %s", _e)

    if col_meta.get("claimed_at") == 1:
        schema_patched = False
        try:
            schema_row = cursor.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='leads'"
            ).fetchone()
            if schema_row and schema_row[0] and "claimed_at     TEXT    NOT NULL DEFAULT ''" in schema_row[0]:
                new_sql = schema_row[0].replace(
                    "claimed_at     TEXT    NOT NULL DEFAULT ''",
                    "claimed_at     TEXT    DEFAULT NULL",
                )
                schema_ver = cursor.execute("PRAGMA schema_version").fetchone()[0]
                cursor.execute("PRAGMA writable_schema = ON")
                cursor.execute(
                    "UPDATE sqlite_master SET sql=? WHERE type='table' AND name='leads'",
                    (new_sql,),
                )
                cursor.execute(f"PRAGMA schema_version = {schema_ver + 1}")
                cursor.execute("PRAGMA writable_schema = OFF")
                conn.commit()
                schema_patched = True
        except Exception as _e:
            _dblog.warning("claimed_at writable_schema migration failed: %s", _e)

        if not schema_patched:
            try:
                _rebuild_leads_nullable_claimed_at(cursor, conn)
            except Exception as _e:
                _dblog.warning("claimed_at table rebuild failed: %s", _e)

    try:
        cursor.execute("UPDATE leads SET claimed_at=NULL WHERE claimed_at=''")
        conn.commit()
    except Exception as _e:
        _dblog.warning("claimed_at empty-string cleanup: %s", _e)

    # --- users table ---
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                username     TEXT    NOT NULL UNIQUE,
                password     TEXT    NOT NULL,
                role         TEXT    NOT NULL DEFAULT 'team',
                fbo_id       TEXT    NOT NULL DEFAULT '',
                upline_name  TEXT    NOT NULL DEFAULT '',
                phone        TEXT    NOT NULL DEFAULT '',
                status       TEXT    NOT NULL DEFAULT 'pending',
                created_at   TEXT    NOT NULL DEFAULT (datetime('now', '+5 hours', '+30 minutes'))
            )
        """)
    except Exception:
        pass

    for col, definition in [
        ("fbo_id",                "TEXT NOT NULL DEFAULT ''"),
        ("upline_name",           "TEXT NOT NULL DEFAULT ''"),
        ("phone",                 "TEXT NOT NULL DEFAULT ''"),
        ("email",                 "TEXT NOT NULL DEFAULT ''"),
        ("status",                "TEXT NOT NULL DEFAULT 'pending'"),
        ("display_picture",       "TEXT NOT NULL DEFAULT ''"),
        ("calling_reminder_time", "TEXT NOT NULL DEFAULT ''"),
        # Training system
        ("training_required",     "INTEGER NOT NULL DEFAULT 0"),
        ("training_status",       "TEXT NOT NULL DEFAULT 'not_required'"),
        ("joining_date",          "TEXT NOT NULL DEFAULT ''"),
        ("certificate_path",      "TEXT NOT NULL DEFAULT ''"),
        # Badges
        ("badges_json",           "TEXT NOT NULL DEFAULT '[]'"),
        ("test_score",            "INTEGER NOT NULL DEFAULT -1"),
        ("test_attempts",         "INTEGER NOT NULL DEFAULT 0"),
        # Certificate stored as base64 so it persists on ephemeral filesystems (Render)
        ("certificate_blob",      "TEXT NOT NULL DEFAULT ''"),
        # Pipeline role system (Part 2)
        ("upline_username",       "TEXT NOT NULL DEFAULT ''"),
        # Upline primary link from registration / admin (leader’s FBO ID)
        ("upline_fbo_id",         "TEXT NOT NULL DEFAULT ''"),
        # Growth Engine (Batch 3)
        ("total_points",          "INTEGER NOT NULL DEFAULT 0"),
        ("user_stage",            "TEXT NOT NULL DEFAULT 'day1'"),
        # Inactivity discipline: updated on each _log_activity for team/leader
        ("last_activity_at",      "TEXT NOT NULL DEFAULT ''"),
        # Step 4 — performance discipline, grace, removal
        ("discipline_status",     "TEXT NOT NULL DEFAULT ''"),
        ("grace_reason",          "TEXT NOT NULL DEFAULT ''"),
        ("grace_return_date",     "TEXT NOT NULL DEFAULT ''"),
        ("grace_started_at",      "TEXT NOT NULL DEFAULT ''"),
        ("low_performance_days",  "INTEGER NOT NULL DEFAULT 0"),
        ("low_perf_tracked_date", "TEXT NOT NULL DEFAULT ''"),
        ("access_blocked",        "INTEGER NOT NULL DEFAULT 0"),
        ("performance_flagged",   "INTEGER NOT NULL DEFAULT 0"),
        ("low_effort_days",       "INTEGER NOT NULL DEFAULT 0"),
        ("low_effort_tracked_date", "TEXT NOT NULL DEFAULT ''"),
        ("final_warning_given",   "INTEGER NOT NULL DEFAULT 0"),
        ("idle_hidden",           "INTEGER NOT NULL DEFAULT 0"),
        # Step 1.1 — first IST date user hit 72h+ work inactivity (login/logout excluded)
        ("inactivity_72h_start_date", "TEXT NOT NULL DEFAULT ''"),
        ("day1_routing_on",       "INTEGER NOT NULL DEFAULT 0"),
    ]:
        try:
            cursor.execute(f"ALTER TABLE users ADD COLUMN {col} {definition}")
        except Exception:
            pass

    # Explicit safety ensure for legacy DBs where looped ALTER may have been skipped.
    try:
        _u_cols = [r[1] for r in cursor.execute("PRAGMA table_info(users)").fetchall()]
        if "upline_fbo_id" not in _u_cols:
            cursor.execute("ALTER TABLE users ADD COLUMN upline_fbo_id TEXT NOT NULL DEFAULT ''")
            conn.commit()
        _dblog.info("upline_fbo_id ensured")
    except Exception as _e:
        _dblog.warning("upline_fbo_id ensure failed: %s", _e)

    try:
        cursor.execute("""
            UPDATE users SET last_activity_at = (
                SELECT MAX(a.created_at) FROM activity_log a WHERE a.username = users.username
            )
            WHERE (last_activity_at IS NULL OR last_activity_at = '')
              AND EXISTS (SELECT 1 FROM activity_log a WHERE a.username = users.username)
        """)
        conn.commit()
    except Exception:
        pass

    # --- daily_reports table ---
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_reports (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                username         TEXT    NOT NULL,
                upline_name      TEXT    NOT NULL DEFAULT '',
                report_date      TEXT    NOT NULL,
                total_calling    INTEGER NOT NULL DEFAULT 0,
                pdf_covered      INTEGER NOT NULL DEFAULT 0,
                calls_picked     INTEGER NOT NULL DEFAULT 0,
                wrong_numbers    INTEGER NOT NULL DEFAULT 0,
                enrollments_done INTEGER NOT NULL DEFAULT 0,
                pending_enroll   INTEGER NOT NULL DEFAULT 0,
                underage         INTEGER NOT NULL DEFAULT 0,
                leads_educated   TEXT    NOT NULL DEFAULT '',
                plan_2cc         INTEGER NOT NULL DEFAULT 0,
                seat_holdings    INTEGER NOT NULL DEFAULT 0,
                remarks          TEXT,
                submitted_at     TEXT    NOT NULL DEFAULT (datetime('now', '+5 hours', '+30 minutes')),
                UNIQUE(username, report_date)
            )
        """)
    except Exception:
        pass

    # --- app_settings table ---
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS app_settings (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL DEFAULT ''
            )
        """)
    except Exception:
        pass

    # --- wallet_recharges table ---
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS wallet_recharges (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                username     TEXT    NOT NULL,
                amount       REAL    NOT NULL,
                utr_number   TEXT    NOT NULL DEFAULT '',
                status       TEXT    NOT NULL DEFAULT 'pending',
                requested_at TEXT    NOT NULL DEFAULT (datetime('now', '+5 hours', '+30 minutes')),
                processed_at TEXT    NOT NULL DEFAULT '',
                admin_note   TEXT    NOT NULL DEFAULT ''
            )
        """)
    except Exception:
        pass

    # --- new tables (safe if already exist) ---
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS announcements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message TEXT NOT NULL,
                created_by TEXT NOT NULL DEFAULT 'admin',
                pin INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now', '+5 hours', '+30 minutes'))
            )
        """)
    except Exception:
        pass

    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS lead_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lead_id INTEGER NOT NULL,
                username TEXT NOT NULL,
                note TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now', '+5 hours', '+30 minutes'))
            )
        """)
    except Exception:
        pass

    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS push_subscriptions (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                username   TEXT    NOT NULL,
                endpoint   TEXT    NOT NULL UNIQUE,
                auth       TEXT    NOT NULL DEFAULT '',
                p256dh     TEXT    NOT NULL DEFAULT '',
                created_at TEXT    NOT NULL DEFAULT (datetime('now', '+5 hours', '+30 minutes'))
            )
        """)
    except Exception:
        pass

    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS password_reset_tokens (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                username   TEXT    NOT NULL,
                token      TEXT    NOT NULL UNIQUE,
                expires_at TEXT    NOT NULL,
                used       INTEGER NOT NULL DEFAULT 0,
                created_at TEXT    NOT NULL DEFAULT (datetime('now', '+5 hours', '+30 minutes'))
            )
        """)
    except Exception:
        pass

    # --- activity_log table ---
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS activity_log (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                username   TEXT    NOT NULL,
                event_type TEXT    NOT NULL,
                details    TEXT    NOT NULL DEFAULT '',
                ip_address TEXT    NOT NULL DEFAULT '',
                created_at TEXT    NOT NULL DEFAULT (datetime('now', '+5 hours', '+30 minutes'))
            )
        """)
    except Exception:
        pass

    # --- training_videos table ---
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS training_videos (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                day_number  INTEGER NOT NULL UNIQUE,
                title       TEXT    NOT NULL DEFAULT '',
                youtube_url TEXT    NOT NULL DEFAULT '',
                podcast_url TEXT    NOT NULL DEFAULT '',
                pdf_url     TEXT    NOT NULL DEFAULT '',
                podcast_blob TEXT   NOT NULL DEFAULT '',
                pdf_blob    TEXT    NOT NULL DEFAULT '',
                description TEXT    NOT NULL DEFAULT '',
                created_at  TEXT    NOT NULL DEFAULT (datetime('now', '+5 hours', '+30 minutes'))
            )
        """)
    except Exception:
        pass

    # Add podcast_url / pdf_url / blobs to existing training_videos rows
    for col, definition in [
        ("podcast_url", "TEXT NOT NULL DEFAULT ''"),
        ("pdf_url",     "TEXT NOT NULL DEFAULT ''"),
        ("podcast_blob", "TEXT NOT NULL DEFAULT ''"),
        ("pdf_blob",    "TEXT NOT NULL DEFAULT ''"),
    ]:
        try:
            cursor.execute(f"ALTER TABLE training_videos ADD COLUMN {col} {definition}")
        except Exception:
            pass

    # Clear only *placeholder* seed paths (same shape as real uploads) when no blob was ever stored.
    # Never wipe rows where admin uploaded a file — those have non-empty podcast_blob / pdf_blob.
    cursor.execute(
        "UPDATE training_videos SET podcast_url='' WHERE podcast_url LIKE 'audio/day%_podcast.%' "
        "AND TRIM(COALESCE(podcast_blob,''))=''"
    )
    cursor.execute(
        "UPDATE training_videos SET pdf_url='' WHERE pdf_url LIKE 'pdf/day%_resource.pdf' "
        "AND TRIM(COALESCE(pdf_blob,''))=''"
    )

    # --- training_progress table ---
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS training_progress (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                username     TEXT    NOT NULL,
                day_number   INTEGER NOT NULL,
                completed    INTEGER NOT NULL DEFAULT 0,
                completed_at TEXT    NOT NULL DEFAULT '',
                UNIQUE(username, day_number)
            )
        """)
    except Exception:
        pass

    # --- targets table ---
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS targets (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                username     TEXT NOT NULL,
                metric       TEXT NOT NULL,
                target_value REAL NOT NULL DEFAULT 0,
                month        TEXT NOT NULL,
                created_by   TEXT NOT NULL DEFAULT 'admin',
                created_at   TEXT NOT NULL DEFAULT (datetime('now', '+5 hours', '+30 minutes')),
                UNIQUE(username, metric, month)
            )
        """)
    except Exception:
        pass

    # --- user_badges table ---
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_badges (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                username    TEXT NOT NULL,
                badge_key   TEXT NOT NULL,
                unlocked_at TEXT NOT NULL DEFAULT (datetime('now', '+5 hours', '+30 minutes')),
                UNIQUE(username, badge_key)
            )
        """)
    except Exception:
        pass

    # --- point_history table ---
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS point_history (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                username     TEXT    NOT NULL,
                action_type  TEXT    NOT NULL,
                points       INTEGER NOT NULL,
                description  TEXT    NOT NULL DEFAULT '',
                lead_id      INTEGER NOT NULL DEFAULT 0,
                created_at   TEXT    NOT NULL DEFAULT (datetime('now', '+5 hours', '+30 minutes'))
            )
        """)
    except Exception:
        pass
    # Add lead_id column to existing point_history tables (safe migration)
    try:
        cursor.execute("ALTER TABLE point_history ADD COLUMN lead_id INTEGER NOT NULL DEFAULT 0")
    except Exception:
        pass  # column already exists

    # Unique indexes for atomic idempotency — prevents race-condition double-awards
    # Per-lead-per-day: one award per action per lead per calendar day
    try:
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS ux_ph_idem_day
            ON point_history(username, action_type, lead_id, DATE(created_at))
            WHERE lead_id > 0
        """)
    except Exception:
        pass
    # Per-lead lifetime: CONVERSION can only be awarded once ever per lead
    try:
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS ux_ph_idem_lifetime
            ON point_history(username, action_type, lead_id)
            WHERE lead_id > 0 AND action_type = 'CONVERSION'
        """)
    except Exception:
        pass

    # --- training_questions table ---
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS training_questions (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                question       TEXT    NOT NULL,
                option_a       TEXT    NOT NULL DEFAULT '',
                option_b       TEXT    NOT NULL DEFAULT '',
                option_c       TEXT    NOT NULL DEFAULT '',
                option_d       TEXT    NOT NULL DEFAULT '',
                correct_answer TEXT    NOT NULL DEFAULT 'a',
                sort_order     INTEGER NOT NULL DEFAULT 0,
                created_at     TEXT    NOT NULL DEFAULT (datetime('now', '+5 hours', '+30 minutes'))
            )
        """)
    except Exception:
        pass

    # --- training_test_attempts table ---
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS training_test_attempts (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                username        TEXT    NOT NULL,
                score           INTEGER NOT NULL DEFAULT 0,
                total_questions INTEGER NOT NULL DEFAULT 0,
                passed          INTEGER NOT NULL DEFAULT 0,
                attempted_at    TEXT    NOT NULL DEFAULT (datetime('now', '+5 hours', '+30 minutes'))
            )
        """)
    except Exception:
        pass

    # --- day2_questions table (Progression Engine) ---
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS day2_questions (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                question_text  TEXT    NOT NULL,
                option_a       TEXT    NOT NULL,
                option_b       TEXT    NOT NULL,
                option_c       TEXT    NOT NULL,
                option_d       TEXT    NOT NULL,
                correct_option TEXT    NOT NULL,
                created_at     TEXT    NOT NULL DEFAULT (datetime('now', '+5 hours', '+30 minutes'))
            )
        """)
    except Exception:
        pass

    # --- Seed Day 2 Questions if empty ---
    try:
        cnt = cursor.execute("SELECT COUNT(*) as c FROM day2_questions").fetchone()['c']
        if cnt == 0:
            default_qs = [
                ("What is the first step when a prospect says they don't have money to start?", "Argue with them", "Relate using Feel-Felt-Found method", "Ignore the message", "Block them", "B"),
                ("How many points are awarded for a completed follow-up?", "5 points", "10 points", "25 points", "50 points", "C"),
                ("What is the main goal of the Day 1 call?", "Selling the premium track", "Creating urgency", "Building mindset and trust", "Getting referrals", "C"),
                ("If a prospect doesn't pick up the phone, what is the correct system action?", "Leave it forever", "Mark as 'Called - No Answer' and set follow-up", "Delete the lead", "Spam WhatsApp messages", "B"),
                ("Which training track offers the highest value and fastest growth in our system?", "Slow Track", "Medium Track", "Fast Track", "No Track", "C")
            ]
            cursor.executemany("""
                INSERT INTO day2_questions (question_text, option_a, option_b, option_c, option_d, correct_option)
                VALUES (?, ?, ?, ?, ?, ?)
            """, default_qs)
    except Exception:
        pass

    # --- daily_scores table ---
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_scores (
                id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                username           TEXT    NOT NULL,
                score_date         TEXT    NOT NULL,
                calls_made         INTEGER NOT NULL DEFAULT 0,
                videos_sent        INTEGER NOT NULL DEFAULT 0,
                batches_marked     INTEGER NOT NULL DEFAULT 0,
                payments_collected INTEGER NOT NULL DEFAULT 0,
                total_points       INTEGER NOT NULL DEFAULT 0,
                streak_days        INTEGER NOT NULL DEFAULT 1,
                created_at         TEXT    NOT NULL DEFAULT (datetime('now', '+5 hours', '+30 minutes')),
                UNIQUE(username, score_date)
            )
        """)
    except Exception:
        pass

    # Add index for daily_scores lookups
    try:
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_daily_scores_user_date ON daily_scores(username, score_date)")
    except Exception:
        pass

    # Pipeline sync: new columns on daily_scores
    for col, definition in [
        ("enroll_links_sent", "INTEGER NOT NULL DEFAULT 0"),
        ("prospect_views", "INTEGER NOT NULL DEFAULT 0"),
    ]:
        try:
            cursor.execute(f"ALTER TABLE daily_scores ADD COLUMN {col} {definition}")
        except Exception:
            pass

    # Pipeline sync: new columns on daily_reports (actual system counts + verified flag)
    for col, definition in [
        ("videos_sent_actual", "INTEGER NOT NULL DEFAULT -1"),
        ("calls_made_actual", "INTEGER NOT NULL DEFAULT -1"),
        ("payments_actual", "INTEGER NOT NULL DEFAULT -1"),
        ("system_verified", "INTEGER NOT NULL DEFAULT 0"),
        # Foolproof report: additional system-verified columns
        ("calls_not_picked",  "INTEGER NOT NULL DEFAULT 0"),
        ("leads_claimed",     "INTEGER NOT NULL DEFAULT 0"),
    ]:
        try:
            cursor.execute(f"ALTER TABLE daily_reports ADD COLUMN {col} {definition}")
        except Exception:
            pass

    # --- enroll_content table (for Enroll To share — video titles) ---
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS enroll_content (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                curiosity_title TEXT NOT NULL DEFAULT '',
                title          TEXT NOT NULL DEFAULT '',
                created_at     TEXT NOT NULL DEFAULT (datetime('now', '+5 hours', '+30 minutes'))
            )
        """)
    except Exception:
        pass

    # Add columns required by leader Working / Enroll To (is_active, day_number, sort_order)
    for col, definition in [
        ("is_active", "INTEGER NOT NULL DEFAULT 1"),
        ("day_number", "INTEGER NOT NULL DEFAULT 1"),
        ("sort_order", "INTEGER NOT NULL DEFAULT 0"),
    ]:
        try:
            cursor.execute(f"ALTER TABLE enroll_content ADD COLUMN {col} {definition}")
        except Exception:
            pass

    # --- enroll_pdfs table (Enroll To — PDFs for leaders) ---
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS enroll_pdfs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                title       TEXT NOT NULL DEFAULT '',
                url         TEXT NOT NULL DEFAULT '',
                is_active   INTEGER NOT NULL DEFAULT 1,
                sort_order  INTEGER NOT NULL DEFAULT 0,
                created_at  TEXT NOT NULL DEFAULT (datetime('now', '+5 hours', '+30 minutes'))
            )
        """)
    except Exception:
        pass

    # --- enroll_share_links table (Enroll To share link → lead sync) ---
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS enroll_share_links (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                token      TEXT NOT NULL UNIQUE,
                lead_id    INTEGER,
                content_id INTEGER,
                shared_by  TEXT NOT NULL DEFAULT '',
                view_count INTEGER NOT NULL DEFAULT 0,
                lead_status_before TEXT NOT NULL DEFAULT '',
                synced_to_lead INTEGER NOT NULL DEFAULT 0,
                watch_synced INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now', '+5 hours', '+30 minutes'))
            )
        """)
    except Exception:
        pass

    for col, definition in [
        ("lead_status_before", "TEXT NOT NULL DEFAULT ''"),
        ("synced_to_lead", "INTEGER NOT NULL DEFAULT 0"),
        ("watch_synced", "INTEGER NOT NULL DEFAULT 0"),
    ]:
        try:
            cursor.execute(f"ALTER TABLE enroll_share_links ADD COLUMN {col} {definition}")
        except Exception:
            pass

    # --- batch_share_links: token per (lead_id, slot) so prospect open = auto-mark batch ---
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS batch_share_links (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                token      TEXT NOT NULL UNIQUE,
                lead_id    INTEGER NOT NULL,
                slot       TEXT NOT NULL,
                used       INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now', '+5 hours', '+30 minutes'))
            )
        """)
    except Exception:
        pass

    # --- bonus_videos table ---
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bonus_videos (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                title       TEXT    NOT NULL DEFAULT '',
                youtube_url TEXT    NOT NULL DEFAULT '',
                description TEXT    NOT NULL DEFAULT '',
                sort_order  INTEGER NOT NULL DEFAULT 0,
                created_at  TEXT    NOT NULL DEFAULT (datetime('now', '+5 hours', '+30 minutes'))
            )
        """)
    except Exception:
        pass

    # --- lead_stage_history table (pipeline transitions log) ---
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS lead_stage_history (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                lead_id      INTEGER NOT NULL,
                stage        TEXT    NOT NULL,
                owner        TEXT    NOT NULL DEFAULT '',
                triggered_by TEXT    NOT NULL DEFAULT '',
                created_at   TEXT    NOT NULL DEFAULT (datetime('now', '+5 hours', '+30 minutes'))
            )
        """)
    except Exception:
        pass

    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS lead_assignments (
                id                   INTEGER PRIMARY KEY AUTOINCREMENT,
                lead_id              INTEGER NOT NULL,
                assigned_to          INTEGER,
                previous_assigned_to INTEGER,
                assigned_by          TEXT    NOT NULL DEFAULT '',
                assign_type          TEXT    NOT NULL DEFAULT '',
                reason               TEXT    NOT NULL DEFAULT '',
                created_at           TEXT    NOT NULL DEFAULT (datetime('now', '+5 hours', '+30 minutes'))
            )
        """)
    except Exception:
        pass

    # --- Performance indexes ---
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_stage_history_lead ON lead_stage_history(lead_id)",
        "CREATE INDEX IF NOT EXISTS idx_lead_assignments_lead_id ON lead_assignments(lead_id)",
        "CREATE INDEX IF NOT EXISTS idx_lead_assignments_lead_id_id ON lead_assignments(lead_id, id DESC)",
        "CREATE INDEX IF NOT EXISTS idx_lead_assignments_assigned_to ON lead_assignments(assigned_to)",
        "CREATE INDEX IF NOT EXISTS idx_lead_assignments_created_at ON lead_assignments(created_at)",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_lead_assignment ON lead_assignments "
        "(lead_id, COALESCE(assigned_to, -1), assign_type, created_at)",
        "CREATE INDEX IF NOT EXISTS idx_leads_pipeline ON leads(pipeline_stage, current_owner)",
        "CREATE INDEX IF NOT EXISTS idx_leads_pool_assigned  ON leads(in_pool, assigned_to)",
        "CREATE INDEX IF NOT EXISTS idx_leads_pool_status    ON leads(in_pool, status)",
        "CREATE INDEX IF NOT EXISTS idx_leads_payment        ON leads(payment_done, in_pool)",
        "CREATE INDEX IF NOT EXISTS idx_leads_updated        ON leads(updated_at)",
        "CREATE INDEX IF NOT EXISTS idx_leads_phone          ON leads(phone)",
        "CREATE INDEX IF NOT EXISTS idx_wallet_user_status   ON wallet_recharges(username, status)",
        "CREATE INDEX IF NOT EXISTS idx_reports_user_date    ON daily_reports(username, report_date)",
        "CREATE INDEX IF NOT EXISTS idx_leads_call_result ON leads(call_result, in_pool, deleted_at)",
        "CREATE INDEX IF NOT EXISTS idx_activity_user_time ON activity_log(username, created_at)",
        "CREATE INDEX IF NOT EXISTS idx_targets_user_month ON targets(username, month)",
        "CREATE INDEX IF NOT EXISTS idx_lead_notes_lead ON lead_notes(lead_id, created_at)",
        "CREATE INDEX IF NOT EXISTS idx_leads_followup ON leads(follow_up_date, assigned_to)",
        "CREATE INDEX IF NOT EXISTS idx_leads_contacted ON leads(last_contacted, assigned_to)",
        "CREATE INDEX IF NOT EXISTS idx_leads_created ON leads(created_at)",
        "CREATE INDEX IF NOT EXISTS idx_leads_deleted_pool ON leads(in_pool, deleted_at, assigned_to, created_at)",
        # Seat-hold expiry check: pipeline_stage + current_owner + expiry for fast scan
        "CREATE INDEX IF NOT EXISTS idx_leads_seat_hold ON leads(pipeline_stage, current_owner, seat_hold_expiry)",
        # Stage-advance lookups by assigned_to + pipeline_stage
        "CREATE INDEX IF NOT EXISTS idx_leads_stage_assigned ON leads(assigned_to, pipeline_stage, in_pool, deleted_at)",
        # Dashboard / My Leads hot paths (partial: active rows only)
        "CREATE INDEX IF NOT EXISTS idx_leads_active_uid_status ON leads(assigned_user_id, status, updated_at) "
        "WHERE in_pool=0 AND deleted_at=''",
        "CREATE INDEX IF NOT EXISTS idx_leads_active_claimed ON leads(assigned_user_id, claimed_at) "
        "WHERE in_pool=0 AND deleted_at=''",
        "CREATE INDEX IF NOT EXISTS idx_leads_pool_list ON leads(in_pool, updated_at) WHERE in_pool=1",
        # Admin / approvals
        "CREATE INDEX IF NOT EXISTS idx_users_status ON users(status)",
        # Day 2 test token lookup
        "CREATE INDEX IF NOT EXISTS idx_leads_test_token ON leads(test_token) "
        "WHERE TRIM(COALESCE(test_token,'')) != ''",
        # Fresh-lead filter: claimed_at date for points/call-count gating
        "CREATE INDEX IF NOT EXISTS idx_leads_claimed_date ON leads(assigned_user_id, claimed_at) "
        "WHERE in_pool=0 AND deleted_at=''",
        # Upline tree walk (CTE downline query)
        "CREATE INDEX IF NOT EXISTS idx_users_upline ON users(upline_username, status)",
    ]
    for idx in indexes:
        try:
            cursor.execute(idx)
        except Exception:
            pass

    # --- admin_tasks table (admin → team task broadcast) ---
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS admin_tasks (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                title       TEXT    NOT NULL,
                body        TEXT    DEFAULT '',
                created_by  TEXT    NOT NULL,
                target      TEXT    DEFAULT 'all',
                priority    TEXT    DEFAULT 'normal',
                is_done     INTEGER DEFAULT 0,
                due_date    TEXT    DEFAULT '',
                created_at  TEXT    NOT NULL DEFAULT (datetime('now', '+5 hours', '+30 minutes'))
            )
        """)
    except Exception:
        pass
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS admin_task_done (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id    INTEGER NOT NULL,
                username   TEXT    NOT NULL,
                done_at    TEXT    NOT NULL DEFAULT (datetime('now', '+5 hours', '+30 minutes')),
                UNIQUE(task_id, username)
            )
        """)
    except Exception:
        pass
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_grace_history (
                id                     INTEGER PRIMARY KEY AUTOINCREMENT,
                username               TEXT    NOT NULL,
                reason_normalized      TEXT    NOT NULL,
                reason_text            TEXT    NOT NULL,
                expected_return_date   TEXT    NOT NULL,
                outcome                TEXT    NOT NULL DEFAULT '',
                created_at             TEXT    NOT NULL DEFAULT (datetime('now', '+5 hours', '+30 minutes'))
            )
        """)
    except Exception:
        pass

    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS admin_decision_snapshots (
                snapshot_date   TEXT    NOT NULL,
                username        TEXT    NOT NULL,
                decision_class  TEXT    NOT NULL,
                detail          TEXT    NOT NULL DEFAULT '',
                metrics_json    TEXT    NOT NULL DEFAULT '{}',
                created_at      TEXT    NOT NULL DEFAULT (datetime('now', '+5 hours', '+30 minutes')),
                PRIMARY KEY (snapshot_date, username)
            )
        """)
    except Exception:
        pass

    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS system_auto_actions (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type       TEXT    NOT NULL,
                target_username  TEXT    NOT NULL DEFAULT '',
                reason           TEXT    NOT NULL DEFAULT '',
                created_at       TEXT    NOT NULL DEFAULT (datetime('now', '+5 hours', '+30 minutes'))
            )
        """)
    except Exception:
        pass

    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS leaderboard_summaries (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                summary_date TEXT    NOT NULL UNIQUE,
                message      TEXT    NOT NULL,
                top3_json    TEXT    NOT NULL DEFAULT '[]',
                bottom5_json TEXT    NOT NULL DEFAULT '[]',
                created_at   TEXT    NOT NULL DEFAULT (datetime('now', '+5 hours', '+30 minutes'))
            )
        """)
    except Exception:
        pass

    # ── FBO ID fix: 910900367506 is Karanveer Singh (admin) ──────────────────
    try:
        cursor.execute("""
            UPDATE users SET fbo_id = '910900367506'
            WHERE role = 'admin' AND (fbo_id IS NULL OR fbo_id = '' OR fbo_id = '910900367506')
        """)
        cursor.execute("""
            UPDATE users
            SET    fbo_id          = '',
                   upline_name     = COALESCE((SELECT username FROM users WHERE role='admin' LIMIT 1), 'admin'),
                   upline_username = COALESCE((SELECT username FROM users WHERE role='admin' LIMIT 1), 'admin')
            WHERE  fbo_id = '910900367506'
              AND  role   != 'admin'
        """)
        cursor.execute("""
            UPDATE users
            SET    upline_name     = COALESCE((SELECT username FROM users WHERE role='admin' LIMIT 1), 'admin'),
                   upline_username = COALESCE((SELECT username FROM users WHERE role='admin' LIMIT 1), 'admin')
            WHERE  LOWER(upline_name) LIKE '%karanveer%'
              AND  role != 'admin'
        """)
    except Exception as e:
        logging.getLogger("database").warning("legacy FBO/upline cleanup skipped: %s", e)

    # ── Identity: users.name, users.upline_id, leads.assigned_user_id, FBO backfill ──
    _idlog = logging.getLogger("database")
    for col, definition in (
        ("name", "TEXT NOT NULL DEFAULT ''"),
        ("upline_id", "INTEGER"),
    ):
        try:
            cursor.execute(f"ALTER TABLE users ADD COLUMN {col} {definition}")
        except Exception:
            pass
    try:
        cursor.execute("UPDATE users SET name = username WHERE TRIM(COALESCE(name, '')) = ''")
    except Exception as e:
        _idlog.warning("users.name backfill: %s", e)
    try:
        cursor.execute(
            """
            UPDATE users SET upline_id = (
                SELECT id FROM users u2
                WHERE TRIM(u2.username) = TRIM(users.upline_username)
                  AND TRIM(COALESCE(users.upline_username, '')) != ''
                LIMIT 1
            )
            WHERE upline_id IS NULL
            """
        )
        cursor.execute(
            """
            UPDATE users SET upline_id = (
                SELECT id FROM users u2
                WHERE TRIM(u2.username) = TRIM(users.upline_name)
                  AND TRIM(COALESCE(users.upline_name, '')) != ''
                LIMIT 1
            )
            WHERE upline_id IS NULL
              AND TRIM(COALESCE(users.upline_username, '')) = ''
            """
        )
    except Exception as e:
        _idlog.warning("users.upline_id backfill: %s", e)

    # upline_id from upline_fbo_id when username fields missing
    try:
        cursor.execute(
            """
            UPDATE users SET upline_id = (
                SELECT id FROM users u2
                WHERE TRIM(u2.fbo_id) = TRIM(users.upline_fbo_id)
                  AND TRIM(COALESCE(users.upline_fbo_id, '')) != ''
                LIMIT 1
            )
            WHERE upline_id IS NULL
              AND TRIM(COALESCE(upline_fbo_id, '')) != ''
            """
        )
    except Exception as e:
        _idlog.warning("users.upline_id from upline_fbo_id backfill: %s", e)

    # Keep upline_fbo_id in sync with assigned upline username (for tree / proof gates).
    try:
        cursor.execute(
            """
            UPDATE users SET upline_fbo_id = (
                SELECT COALESCE(NULLIF(TRIM(u2.fbo_id), ''), '')
                FROM users u2
                WHERE TRIM(u2.username) = TRIM(users.upline_username)
                  AND TRIM(COALESCE(users.upline_username, '')) != ''
                LIMIT 1
            )
            WHERE TRIM(COALESCE(upline_username, '')) != ''
              AND TRIM(COALESCE(upline_fbo_id, '')) = ''
            """
        )
    except Exception as e:
        _idlog.warning("users.upline_fbo_id backfill from upline_username: %s", e)

    # Resolve upline username/name when only FBO was stored (orphan / partial rows).
    try:
        cursor.execute(
            """
            UPDATE users SET
                upline_username = (
                    SELECT u2.username FROM users u2
                    WHERE TRIM(u2.fbo_id) = TRIM(users.upline_fbo_id)
                      AND u2.status = 'approved'
                    LIMIT 1
                ),
                upline_name = (
                    SELECT u2.username FROM users u2
                    WHERE TRIM(u2.fbo_id) = TRIM(users.upline_fbo_id)
                      AND u2.status = 'approved'
                    LIMIT 1
                )
            WHERE role IN ('team', 'leader')
              AND status = 'approved'
              AND TRIM(COALESCE(upline_username, '')) = ''
              AND TRIM(COALESCE(upline_fbo_id, '')) != ''
            """
        )
    except Exception as e:
        _idlog.warning("users upline username/name from upline_fbo_id: %s", e)

    try:
        cursor.execute("ALTER TABLE leads ADD COLUMN assigned_user_id INTEGER")
    except Exception:
        pass
    try:
        cursor.execute(
            """
            UPDATE leads SET assigned_user_id = (
                SELECT id FROM users u
                WHERE u.username = leads.assigned_to
                  AND TRIM(COALESCE(leads.assigned_to, '')) != ''
                LIMIT 1
            )
            WHERE TRIM(COALESCE(assigned_to, '')) != ''
              AND (assigned_user_id IS NULL OR assigned_user_id = 0)
            """
        )
    except Exception as e:
        _idlog.warning("leads.assigned_user_id backfill: %s", e)
    try:
        _orph = cursor.execute(
            """
            SELECT id, assigned_to FROM leads
            WHERE TRIM(COALESCE(assigned_to, '')) != ''
              AND (assigned_user_id IS NULL OR assigned_user_id = 0)
            LIMIT 30
            """
        ).fetchall()
        if _orph:
            _idlog.warning(
                "leads with unmapped assigned_to (no users.id); fix manually: %s",
                [dict(o) for o in _orph],
            )
    except Exception as e:
        _idlog.warning("orphan assigned_to check: %s", e)

    # Pool rows should be claimable only when assigned_user_id is NULL.
    try:
        cursor.execute("UPDATE leads SET assigned_user_id=NULL WHERE in_pool=1 AND assigned_user_id=0")
    except Exception as e:
        _idlog.warning("normalize pool assigned_user_id=0 -> NULL: %s", e)

    # Claimed leads must permanently remember their original buyer/current_owner.
    try:
        cursor.execute("DROP TRIGGER IF EXISTS trg_leads_claim_owner_immutable")
    except Exception as e:
        _idlog.warning("drop claim owner trigger before backfill: %s", e)
    try:
        _owner_fix = cursor.execute(
            "SELECT value FROM app_settings WHERE key='migration_claim_owner_lock_v2'"
        ).fetchone()
        if not _owner_fix or (_owner_fix[0] or '') != 'done':
            cursor.execute(
                """
                UPDATE leads
                   SET current_owner = (
                       SELECT wr.username
                       FROM wallet_recharges wr
                       WHERE wr.status='approved'
                         AND wr.amount < 0
                         AND (
                             wr.utr_number = 'LEAD-CLAIM-' || leads.id
                             OR wr.utr_number LIKE 'LEAD-CLAIM-' || leads.id || '-%'
                         )
                       ORDER BY wr.id ASC
                       LIMIT 1
                   )
                 WHERE in_pool=0
                   AND TRIM(COALESCE(claimed_at,'')) != ''
                   AND EXISTS (
                       SELECT 1
                       FROM wallet_recharges wr
                       WHERE wr.status='approved'
                         AND wr.amount < 0
                         AND (
                             wr.utr_number = 'LEAD-CLAIM-' || leads.id
                             OR wr.utr_number LIKE 'LEAD-CLAIM-' || leads.id || '-%'
                         )
                   )
                """
            )
            cursor.execute(
                """
                WITH claim_log_candidates AS (
                    SELECT
                        TRIM(COALESCE(created_at, '')) AS claim_ts,
                        TRIM(COALESCE(username, '')) AS claimer
                    FROM activity_log
                    WHERE event_type='lead_claim'
                      AND TRIM(COALESCE(created_at, '')) != ''
                      AND TRIM(COALESCE(username, '')) != ''
                    UNION ALL
                    SELECT
                        TRIM(SUBSTR(details, INSTR(details, 'ts=') + 3)) AS claim_ts,
                        TRIM(COALESCE(username, '')) AS claimer
                    FROM activity_log
                    WHERE event_type='lead_claim'
                      AND INSTR(details, 'ts=') > 0
                      AND TRIM(COALESCE(username, '')) != ''
                ),
                claim_log_map AS (
                    SELECT claim_ts, MIN(claimer) AS claimer
                    FROM claim_log_candidates
                    WHERE claim_ts != ''
                    GROUP BY claim_ts
                    HAVING COUNT(DISTINCT claimer) = 1
                )
                UPDATE leads
                   SET current_owner = (
                       SELECT clm.claimer
                       FROM claim_log_map clm
                       WHERE clm.claim_ts = leads.claimed_at
                       LIMIT 1
                   )
                 WHERE in_pool=0
                   AND TRIM(COALESCE(claimed_at,'')) != ''
                   AND EXISTS (
                       SELECT 1
                       FROM claim_log_map clm
                       WHERE clm.claim_ts = leads.claimed_at
                   )
                   AND TRIM(COALESCE((
                       SELECT clm.claimer
                       FROM claim_log_map clm
                       WHERE clm.claim_ts = leads.claimed_at
                       LIMIT 1
                   ), '')) != TRIM(COALESCE(current_owner, ''))
                """
            )
            cursor.execute(
                """
                UPDATE leads
                   SET current_owner = (
                       SELECT username FROM users u
                       WHERE u.id = leads.assigned_user_id
                       LIMIT 1
                   )
                 WHERE in_pool=0
                   AND TRIM(COALESCE(claimed_at,'')) != ''
                   AND TRIM(COALESCE(current_owner,'')) = ''
                   AND assigned_user_id IS NOT NULL
                """
            )
            cursor.execute(
                "INSERT OR REPLACE INTO app_settings (key, value) VALUES (?, ?)",
                ('migration_claim_owner_lock_v2', 'done'),
            )
    except Exception as e:
        _idlog.warning("claim-owner lock backfill: %s", e)

    try:
        cursor.execute(
            """
            UPDATE users SET fbo_id = username
            WHERE TRIM(COALESCE(fbo_id, '')) = ''
              AND TRIM(COALESCE(username, '')) != ''
            """
        )
    except Exception as e:
        _idlog.warning("fbo_id default from username: %s", e)

    for _idx in (
        "CREATE INDEX IF NOT EXISTS idx_leads_assigned_user_id ON leads(assigned_user_id)",
        "CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(status)",
    ):
        try:
            cursor.execute(_idx)
        except Exception:
            pass

    # ── One-time: orphan FK → clear leads.assigned_to (text no longer authoritative) ──
    try:
        _clr = cursor.execute(
            "SELECT value FROM app_settings WHERE key='migration_leads_assigned_to_cleared_v1'"
        ).fetchone()
        if not _clr or (_clr[0] or '') != 'done':
            cursor.execute(
                """
                UPDATE leads SET assigned_user_id = (
                    SELECT u.id FROM users u WHERE u.username = leads.assigned_to LIMIT 1
                )
                WHERE assigned_user_id IS NULL
                """
            )
            _pending_all = cursor.execute(
                "SELECT COUNT(*) AS c FROM leads WHERE assigned_user_id IS NULL"
            ).fetchone()[0]
            _idlog.info(
                "pre-clear assigned_to: COUNT(*) WHERE assigned_user_id IS NULL = %s",
                _pending_all,
            )
            _pending_str = cursor.execute(
                """
                SELECT COUNT(*) FROM leads
                WHERE assigned_user_id IS NULL AND TRIM(COALESCE(assigned_to,'')) != ''
                """
            ).fetchone()[0]
            if _pending_str:
                _idlog.warning(
                    "orphan assigned_to text with no users.id match (%s rows); clearing text only",
                    _pending_str,
                )
                cursor.execute(
                    """
                    UPDATE leads SET assigned_to = ''
                    WHERE assigned_user_id IS NULL AND TRIM(COALESCE(assigned_to,'')) != ''
                    """
                )
            cursor.execute("UPDATE leads SET assigned_to = ''")
            _chk = cursor.execute(
                "SELECT COUNT(*) FROM leads WHERE TRIM(COALESCE(assigned_to,'')) != ''"
            ).fetchone()[0]
            if _chk:
                _idlog.error("FINAL CHECK: expected 0 non-empty assigned_to, got %s", _chk)
            cursor.execute(
                "INSERT OR REPLACE INTO app_settings (key, value) VALUES (?, ?)",
                ("migration_leads_assigned_to_cleared_v1", "done"),
            )
    except Exception as e:
        _idlog.warning("migration_leads_assigned_to_cleared_v1: %s", e)

    # ── Owner consistency hardening (no off-pool lead without owner) ──
    try:
        _admin_id_row = cursor.execute(
            """
            SELECT id FROM users
            WHERE role='admin' AND status='approved'
            ORDER BY id ASC LIMIT 1
            """
        ).fetchone()
        if not _admin_id_row:
            _admin_id_row = cursor.execute(
                "SELECT id FROM users WHERE role='admin' ORDER BY id ASC LIMIT 1"
            ).fetchone()
        if _admin_id_row:
            _admin_id = int(_admin_id_row[0])
            _fixed = cursor.execute(
                """
                UPDATE leads
                SET assigned_user_id = ?
                WHERE in_pool = 0 AND (assigned_user_id IS NULL OR assigned_user_id = 0)
                """,
                (_admin_id,),
            ).rowcount or 0
            if _fixed:
                _idlog.warning(
                    "owner cleanup: assigned admin(id=%s) to %s orphan off-pool lead(s)",
                    _admin_id,
                    _fixed,
                )
        else:
            _idlog.critical("owner cleanup skipped: no admin user found")
    except Exception as e:
        _idlog.warning("owner cleanup migration: %s", e)

    # DB-level lock: reject writes that produce off-pool leads without owner.
    for _tr in (
        """
        CREATE TRIGGER IF NOT EXISTS trg_leads_owner_required_insert
        BEFORE INSERT ON leads
        FOR EACH ROW
        WHEN NEW.in_pool = 0 AND (NEW.assigned_user_id IS NULL OR NEW.assigned_user_id = 0)
        BEGIN
            SELECT RAISE(ABORT, 'owner invariant failed: off-pool lead requires assigned_user_id');
        END
        """,
        """
        CREATE TRIGGER IF NOT EXISTS trg_leads_owner_required_update
        BEFORE UPDATE OF in_pool, assigned_user_id ON leads
        FOR EACH ROW
        WHEN NEW.in_pool = 0 AND (NEW.assigned_user_id IS NULL OR NEW.assigned_user_id = 0)
        BEGIN
            SELECT RAISE(ABORT, 'owner invariant failed: off-pool lead requires assigned_user_id');
        END
        """,
    ):
        try:
            cursor.execute(_tr)
        except Exception as e:
            _idlog.warning("owner invariant trigger ensure: %s", e)

    # Claimed leads are permanent: no auto-refund, no pool return, no owner mutation.
    try:
        cursor.execute("DROP TRIGGER IF EXISTS leads_refund_on_return_to_pool")
    except Exception as e:
        _idlog.warning("drop legacy pool-refund trigger: %s", e)

    for _tr in (
        """
        CREATE TRIGGER IF NOT EXISTS trg_leads_claim_requires_current_owner
        BEFORE UPDATE OF in_pool ON leads
        FOR EACH ROW
        WHEN OLD.in_pool = 1
         AND NEW.in_pool = 0
         AND TRIM(COALESCE(NEW.current_owner, '')) = ''
        BEGIN
            SELECT RAISE(ABORT, 'claim lock failed: current_owner required when claiming lead');
        END
        """,
        """
        CREATE TRIGGER IF NOT EXISTS trg_leads_claim_no_pool_return
        BEFORE UPDATE OF in_pool, claimed_at ON leads
        FOR EACH ROW
        WHEN OLD.in_pool = 0
         AND TRIM(COALESCE(OLD.claimed_at, '')) != ''
         AND (
             COALESCE(NEW.in_pool, 0) != 0
             OR TRIM(COALESCE(NEW.claimed_at, '')) = ''
         )
        BEGIN
            SELECT RAISE(ABORT, 'claim lock failed: claimed lead can never return to pool');
        END
        """,
        """
        CREATE TRIGGER IF NOT EXISTS trg_leads_claim_owner_immutable
        BEFORE UPDATE OF current_owner ON leads
        FOR EACH ROW
        WHEN OLD.in_pool = 0
         AND TRIM(COALESCE(OLD.claimed_at, '')) != ''
         AND TRIM(COALESCE(NEW.current_owner, '')) != TRIM(COALESCE(OLD.current_owner, ''))
        BEGIN
            SELECT RAISE(ABORT, 'claim lock failed: current_owner is immutable after claim');
        END
        """,
        """
        CREATE TRIGGER IF NOT EXISTS trg_leads_claim_pool_price_immutable
        BEFORE UPDATE OF pool_price ON leads
        FOR EACH ROW
        WHEN OLD.in_pool = 0
         AND TRIM(COALESCE(OLD.claimed_at, '')) != ''
         AND COALESCE(NEW.pool_price, 0) != COALESCE(OLD.pool_price, 0)
        BEGIN
            SELECT RAISE(ABORT, 'claim lock failed: pool_price is immutable after claim');
        END
        """,
    ):
        try:
            cursor.execute(_tr)
        except Exception as e:
            _idlog.warning("claim lock trigger ensure: %s", e)

    try:
        _orph_leads = cursor.execute(
            "SELECT COUNT(*) FROM leads WHERE in_pool=0 AND (assigned_user_id IS NULL OR assigned_user_id=0)"
        ).fetchone()[0]
        if _orph_leads:
            _idlog.critical(
                "owner invariant failed after migration: off-pool leads without owner=%s",
                _orph_leads,
            )
            raise RuntimeError("Owner invariant failed: off-pool leads without owner remain")
    except Exception as e:
        conn.rollback()
        conn.close()
        raise

    # ── Fix NULL values in nullable leads columns (prevents AttributeError crashes) ──
    for col in ('email', 'referred_by', 'notes', 'call_result', 'city'):
        try:
            cursor.execute(f"UPDATE leads SET {col}='' WHERE {col} IS NULL")
        except Exception:
            pass
    try:
        cursor.execute("UPDATE daily_reports SET remarks='' WHERE remarks IS NULL")
    except Exception:
        pass

    # ── One-time: normalize payment_amount vs payment_done (historical bad rows) ──
    try:
        _mig = cursor.execute(
            "SELECT value FROM app_settings WHERE key='migration_payment_amount_normalize_v1'"
        ).fetchone()
        if not _mig or (_mig[0] or '') != 'done':
            cursor.execute("""
                UPDATE leads SET payment_amount = 196
                WHERE payment_done = 1
                  AND (payment_amount IS NULL OR payment_amount <= 0)
                  AND status = 'Paid ₹196'
            """)
            cursor.execute("""
                UPDATE leads SET payment_amount = seat_hold_amount
                WHERE payment_done = 1
                  AND (payment_amount IS NULL OR payment_amount <= 0)
                  AND status = 'Seat Hold Confirmed'
                  AND COALESCE(seat_hold_amount, 0) > 0
            """)
            cursor.execute("""
                UPDATE leads SET payment_amount = track_price
                WHERE payment_done = 1
                  AND (payment_amount IS NULL OR payment_amount <= 0)
                  AND status = 'Fully Converted'
                  AND COALESCE(track_price, 0) > 0
            """)
            cursor.execute("""
                UPDATE leads SET payment_amount = 196
                WHERE payment_done = 1
                  AND (payment_amount IS NULL OR payment_amount <= 0)
            """)
            cursor.execute("""
                UPDATE leads SET payment_amount = 0
                WHERE payment_done = 0
                  AND COALESCE(payment_amount, 0) != 0
            """)
            cursor.execute(
                "INSERT OR REPLACE INTO app_settings (key, value) VALUES (?, ?)",
                ('migration_payment_amount_normalize_v1', 'done'),
            )
    except Exception:
        pass

    # ── One-time: ₹196 proof history — backfill reviewed_at / reviewer from 2026-04-01 (IST date on stored ts) ──
    try:
        _mig_pf = cursor.execute(
            "SELECT value FROM app_settings WHERE key='migration_proof_reviewed_backfill_2026_04'"
        ).fetchone()
        if not _mig_pf or (_mig_pf[0] or '') != 'done':
            cursor.execute(
                """
                UPDATE leads
                SET
                  payment_proof_reviewed_at = CASE
                    WHEN TRIM(COALESCE(enrolled_at,'')) != '' THEN enrolled_at
                    ELSE COALESCE(updated_at, created_at)
                  END,
                  payment_proof_reviewed_by = CASE
                    WHEN TRIM(COALESCE(payment_proof_reviewed_by,'')) != ''
                      THEN payment_proof_reviewed_by
                    WHEN TRIM(COALESCE(enrolled_by,'')) != ''
                      THEN enrolled_by
                    ELSE COALESCE(NULLIF(TRIM(assigned_to),''), 'legacy')
                  END
                WHERE in_pool=0 AND deleted_at=''
                  AND TRIM(COALESCE(payment_proof_path,'')) != ''
                  AND LOWER(TRIM(COALESCE(payment_proof_approval_status,''))) IN ('approved','rejected')
                  AND (payment_proof_reviewed_at IS NULL OR TRIM(COALESCE(payment_proof_reviewed_at,''))='')
                  AND date(substr(
                    COALESCE(
                      NULLIF(TRIM(enrolled_at), ''),
                      updated_at,
                      created_at
                    ), 1, 10
                  )) >= date('2026-04-01')
                """
            )
            cursor.execute(
                "INSERT OR REPLACE INTO app_settings (key, value) VALUES (?, ?)",
                ('migration_proof_reviewed_backfill_2026_04', 'done'),
            )
    except Exception:
        pass

    # ── One-time: migrate legacy 'Mindset Lock' leads → 'Paid ₹196' ──
    try:
        _ml_done = cursor.execute(
            "SELECT value FROM app_settings WHERE key='migration_mindset_lock_removed_v1'"
        ).fetchone()
        if not _ml_done or (_ml_done[0] or '') != 'done':
            cursor.execute("""
                UPDATE leads SET status='Paid \u20b9196', pipeline_stage='enrolled'
                WHERE status='Mindset Lock'
            """)
            cursor.execute(
                "INSERT OR REPLACE INTO app_settings (key, value) VALUES (?, ?)",
                ('migration_mindset_lock_removed_v1', 'done'),
            )
    except Exception:
        pass

    # ── One-time: upline_fbo_id drift — text upline says parent P but FBO still pointed at another node
    #    (downline CTE joins on upline_fbo_id match → member appears under two leaders).
    try:
        _mig_u = cursor.execute(
            "SELECT value FROM app_settings WHERE key='migration_upline_fbo_align_parent_v1'"
        ).fetchone()
        if not _mig_u or (_mig_u[0] or '') != 'done':
            nfix = migration_align_upline_fbo_with_resolved_parent(cursor)
            logging.getLogger("database").info(
                "migration_upline_fbo_align_parent_v1: updated %d user row(s)", nfix
            )
            cursor.execute(
                "INSERT OR REPLACE INTO app_settings (key, value) VALUES (?, ?)",
                ('migration_upline_fbo_align_parent_v1', 'done'),
            )
    except Exception:
        logging.getLogger("database").warning(
            "migration_upline_fbo_align_parent_v1 failed", exc_info=True
        )

    # ── One-time: merge duplicate accounts — same person (LOWER(username)+same FBO digits, #/dash variants)
    try:
        _mig_d = cursor.execute(
            "SELECT value FROM app_settings WHERE key='migration_dedupe_same_fbo_username_v1'"
        ).fetchone()
        if not _mig_d or (_mig_d[0] or '') != 'done':
            nmer = migration_dedupe_case_variant_same_fbo_users(cursor)
            logging.getLogger("database").info(
                "migration_dedupe_same_fbo_username_v1: merged %d duplicate user row(s)", nmer
            )
            cursor.execute(
                "INSERT OR REPLACE INTO app_settings (key, value) VALUES (?, ?)",
                ('migration_dedupe_same_fbo_username_v1', 'done'),
            )
    except Exception:
        logging.getLogger("database").warning(
            "migration_dedupe_same_fbo_username_v1 failed", exc_info=True
        )

    check_claimed_at_empty_string_invariant(cursor, conn)
    conn.commit()
    conn.close()


def startup_invariant_scan(*, fail_fast: bool = False):
    """
    Runtime data integrity scan executed on boot.
    Logs CRITICAL when violations exist; optionally raises when fail_fast=True.
    """
    log = logging.getLogger("database")
    conn = get_db()
    cur = conn.cursor()
    violations = {}
    try:
        violations["off_pool_owner_missing"] = cur.execute(
            "SELECT COUNT(*) FROM leads WHERE in_pool=0 AND (assigned_user_id IS NULL OR assigned_user_id=0)"
        ).fetchone()[0] or 0
        violations["pool_owner_not_null"] = cur.execute(
            "SELECT COUNT(*) FROM leads WHERE in_pool=1 AND COALESCE(assigned_user_id, 0) != 0"
        ).fetchone()[0] or 0
        violations["paid_without_proof"] = cur.execute(
            """
            SELECT COUNT(*) FROM leads
            WHERE in_pool=0 AND deleted_at=''
              AND status='Paid ₹196'
              AND TRIM(COALESCE(payment_proof_path,''))=''
            """
        ).fetchone()[0] or 0
        violations["proof_pending_without_file"] = cur.execute(
            """
            SELECT COUNT(*) FROM leads
            WHERE in_pool=0 AND deleted_at=''
              AND LOWER(COALESCE(payment_proof_approval_status,''))='pending'
              AND TRIM(COALESCE(payment_proof_path,''))=''
            """
        ).fetchone()[0] or 0
    finally:
        conn.close()

    bad = {k: int(v) for k, v in violations.items() if int(v) > 0}
    if bad:
        log.critical("startup_invariant_scan violations=%s", bad)
        if fail_fast:
            raise RuntimeError(f"Startup invariant scan failed: {bad}")
    else:
        log.info("startup_invariant_scan ok")
    return {"ok": not bool(bad), "violations": violations}


def seed_users():
    """Create a default admin account if no users exist yet.
       Also auto-upgrades any legacy plain-text passwords to hashed."""
    conn = get_db()
    cursor = conn.cursor()
    count = cursor.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if count == 0:
        bootstrap_password = os.environ.get('BOOTSTRAP_ADMIN_PASSWORD') or secrets.token_urlsafe(12)
        cursor.execute(
            "INSERT INTO users (username, password, role, status, name, fbo_id) VALUES (?, ?, ?, ?, ?, ?)",
            (
                'admin',
                generate_password_hash(bootstrap_password, method='pbkdf2:sha256'),
                'admin',
                'approved',
                'admin',
                '910900367506',
            ),
        )
        if not os.environ.get('BOOTSTRAP_ADMIN_PASSWORD'):
            print(
                f"[SECURITY WARNING] Seeded admin password: {bootstrap_password} "
                "(set BOOTSTRAP_ADMIN_PASSWORD to control this value)."
            )
        conn.commit()
    else:
        cursor.execute("UPDATE users SET status='approved' WHERE role='admin'")

        users = cursor.execute("SELECT id, password FROM users").fetchall()
        for u in users:
            pwd = u[1]
            if not pwd.startswith(('pbkdf2:', 'scrypt:', 'argon2:')):
                cursor.execute("UPDATE users SET password=? WHERE id=?",
                               (generate_password_hash(pwd, method='pbkdf2:sha256'), u[0]))

        conn.commit()
    conn.close()


def seed_training_questions():
    """Insert the 20 MCQ training test questions if none exist yet."""
    conn = get_db()
    cursor = conn.cursor()
    count = cursor.execute("SELECT COUNT(*) FROM training_questions").fetchone()[0]
    if count > 0:
        conn.close()
        return

    questions = [
        {
            "q": "How do you tell if your WHY is genuinely powerful versus only sounding good when you say it?",
            "a": "When it works like a weapon — even on hard days it pulls you back up (that is the mark of a strong WHY)",
            "b": "When it sounds inspiring and motivates others",
            "c": "When it can be expressed clearly and logically",
            "d": "When it is based on realistic, achievable goals",
            "ans": "a",
        },
        {
            "q": "In an invitation call, what is wrong with saying “please watch when you can” — explain the psychology.",
            "a": "It sounds weak and less professional",
            "b": "The prospect assumes you are desperate and do not believe in the business",
            "c": "It is a “beggar” mindset — do not beg for attention; lead with value. Act as a selector — offer the opportunity only to serious people",
            "d": "It puts too much pressure on the prospect",
            "ans": "c",
        },
        {
            "q": "The prospect says “I’ll tell you a bit later.” Step by step, what should you do per training?",
            "a": "Remind once after 24 hours, then drop it",
            "b": "Run two follow-ups — next day, then 2–3 days later; if still no move, move on",
            "c": "Follow up every day until they answer",
            "d": "Ask for a yes/no decision in one shot",
            "ans": "b",
        },
        {
            "q": "By the law of averages, after 10 invites only one payment came in — is that failure? Justify with numbers.",
            "a": "Yes — you should improve; aim for 1 in 3–4",
            "b": "It depends — invite quality matters more than quantity",
            "c": "No — early on, 1 in 10 is common. That is normal; the law of averages is working",
            "d": "No, but you should still improve — target 1 in 5",
            "ans": "c",
        },
        {
            "q": "Ten invites sent, nine said no, your partner says “today was wasted.” How do you respond using the Colonel Sanders story?",
            "a": "Colonel Sanders struggled too — we will keep trying and results will come",
            "b": "One positive lead is enough — he also started from one chance",
            "c": "His story was a different situation — we will use a smarter approach",
            "d": "He faced over a thousand rejections. Nine “no” answers are not failure — rejection is statistical, not personal. Nine nos complete steps; your average is building",
            "ans": "d",
        },
        {
            "q": "After a ₹196 payment, within how many hours should you call — and what goes wrong if you wait too long?",
            "a": "Within 24 hours — the prospect needs time to settle",
            "b": "Within 12 hours — same day",
            "c": "Within 2 hours — excitement peaks right after payment; long delays kill momentum",
            "d": "There is no fixed limit — call whenever it is convenient",
            "ans": "c",
        },
        {
            "q": "On the Day 1 call, why take three verbal “yes” responses? Isn’t one “yes” enough?",
            "a": "Three agreements feel like a formal contract",
            "b": "Three “yes” moments build psychological ownership — commitment runs deeper than a single yes",
            "c": "The senior needs proof the prospect is genuinely ready",
            "d": "It is only a formality before Day 2",
            "ans": "b",
        },
        {
            "q": "After Day 1 the prospect did not send the “Day 1 Ready” message — what exactly do you do? Still no reply after one reminder?",
            "a": "Send one reminder. If still nothing — treat them as not serious, log it, and move on",
            "b": "Call immediately and ask why they did not message",
            "c": "Remind 2–3 times — they might be busy",
            "d": "Skip messaging and connect them straight to a senior on Day 2",
            "ans": "a",
        },
        {
            "q": "On Day 2 the senior leads — what is still your one critical job?",
            "a": "Keep hyping the prospect and staying positive",
            "b": "Prepare the brief — exactly three beats: your journey, results, and belief. A weak or long brief weakens the Day 3 close",
            "c": "Take notes and prep questions for Day 3",
            "d": "Confirm payment and Day 3 timing",
            "ans": "b",
        },
        {
            "q": "On Day 3 the senior’s third question is: “What one result do you want in the first 30 days?” Why?",
            "a": "To understand short-term goals and customize training",
            "b": "To test seriousness and readiness",
            "c": "To align with the training plan’s targets",
            "d": "A concrete target plus the senior’s confirmation — at closing, the senior ties back to that exact outcome so commitment is real",
            "ans": "d",
        },
        {
            "q": "During seat-hold the prospect hesitates — what will the senior ask, and how does it link to Day 2?",
            "a": "“Is it about money?” — go straight to the money objection",
            "b": "“Are you serious or not?” — a blunt commitment check",
            "c": "Revisit what they shared on Day 2 — “You said you wanted [X] — is that still important?”",
            "d": "“Why are you hesitating?” — open objection mining",
            "ans": "c",
        },
        {
            "q": "“Whoever speaks first loses” — when exactly does that apply? If the prospect stays silent for three minutes, what should you do?",
            "a": "Always — staying quiet wins every conversation",
            "b": "After naming the seat-hold amount — stay silent. Even three minutes: do not talk. The silence pressures them, not you",
            "c": "Only in objection handling",
            "d": "When they seem confused, silence is always best",
            "ans": "b",
        },
        {
            "q": "The prospect says a genuine “no” on Day 3 — what do you say, and why not “close the door” forever?",
            "a": "Try one more hard close — a last attempt is mandatory",
            "b": "Ask directly what the real problem is",
            "c": "“Totally fine — no worries. The door stays open.” Great partners often said no first — slamming the door shut is permanent loss",
            "d": "Let the senior take over — they have more experience",
            "ans": "c",
        },
        {
            "q": "The prospect says “I don’t have money.” Using the trained question flow, how should the conversation run?",
            "a": "Sequence: “Where does income come from?” → “What amount feels enough?” → “What is a first-30-day plan?” — they surface their own solution",
            "b": "Offer EMI or installments to remove the money block",
            "c": "Show sympathy — “Okay, we will talk when you are ready”",
            "d": "“If you had the money, what would you do?” — unlock aspiration only",
            "ans": "a",
        },
        {
            "q": "“My family won’t agree” — why is it wrong to make family the villain? What is the better frame?",
            "a": "It damages family trust and makes them defensive",
            "b": "Do not villainize family — they can motivate. Frame: “They want what is best for you — if this also helps them, they will usually support it”",
            "c": "Involving family always lowers confidence",
            "d": "It turns the talk negative — change the topic",
            "ans": "b",
        },
        {
            "q": "In objection handling there is one rule that also applies beyond objections — what is it?",
            "a": "Acknowledge first, then counter — empathy leads",
            "b": "“Whoever speaks first loses” — it applies in seat-hold silence and on the Day 3 close",
            "c": "After three objections, stop — more pressure backfires",
            "d": "Agree first, then softly reframe",
            "ans": "b",
        },
        {
            "q": "What is the psychological purpose of three types of social posts in the prospect’s mind?",
            "a": "More variety automatically means more reach",
            "b": "Algorithms need variety — single-format reach drops",
            "c": "Journey = relatability; Value = trust; Proof = FOMO — together they build belief",
            "d": "Different posts attract different people — each type targets another segment",
            "ans": "c",
        },
        {
            "q": "Day 12, only one join, 30-day goal is ten — against the 300-invite model, what is likely wrong?",
            "a": "Follow-up is weak — follow up harder",
            "b": "By day 12 you should have ~120 invites, ~36 watches, ~12 serious. If not, volume is too low. Hit ~10 invites daily and the math self-corrects",
            "c": "Improve invite quality — stop random blasts",
            "d": "The goal is unrealistic — lower the 10-join target",
            "ans": "b",
        },
        {
            "q": "“Not in the mood today, I’ll do it tomorrow” — what does training recommend, and why does it work?",
            "a": "Rest — forced work underperforms; mood-driven work wins",
            "b": "Watch a motivation video first",
            "c": "Talk to your partner or upline for accountability",
            "d": "Consistency is not perfection — take one small action today. One step keeps the chain alive, and mood often follows action",
            "ans": "d",
        },
        {
            "q": "What is the full chain of this training — if one link breaks, the system fails?",
            "a": "Invite → Law of averages → 3-day flow (Day 1, Day 2 with senior, Day 3 close) → objections → social media → tracker. Each link depends on the last",
            "b": "Product knowledge → confidence → invite → follow-up → objections → close",
            "c": "Mindset → WHY → invite → payment → training → certificate",
            "d": "WHY → goals → daily action → law of averages → result → duplication",
            "ans": "a",
        },
    ]

    for i, q in enumerate(questions, start=1):
        cursor.execute(
            """INSERT INTO training_questions
               (question, option_a, option_b, option_c, option_d, correct_answer, sort_order)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (q["q"], q["a"], q["b"], q["c"], q["d"], q["ans"], i)
        )
    conn.commit()
    conn.close()
