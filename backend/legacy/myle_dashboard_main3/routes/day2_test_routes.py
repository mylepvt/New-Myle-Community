"""Day 2 business evaluation test — POST /test/start, /test/submit; gate to Interview."""
from __future__ import annotations

import os
import random
import secrets
import time
from datetime import timedelta

from flask import Response, flash, jsonify, redirect, render_template, request, session, url_for

from database import get_db
from decorators import admin_required, login_required, safe_route
from auth_context import acting_username
from helpers import (
    DAY2_BUSINESS_TEST_MAX_ATTEMPTS,
    DAY2_BUSINESS_TEST_PASS_MARK,
    DAY2_BUSINESS_TEST_TOTAL_Q,
    _get_network_usernames,
    _now_ist,
    user_id_for_username,
    day2_test_token_expired,
    format_day2_certificate_display_date,
    lead_day2_business_test_exhausted,
    lead_day2_business_test_passed,
    lead_day2_certificate_eligible,
    phones_match_for_lead_verification,
    _lead_row_value,
    _enrich_leads,
)
from services.day2_certificate_pdf import build_day2_business_certificate_pdf

from routes import day2_eval_questions as _day2_eval_mod

DAY2_EVAL_QUESTIONS = _day2_eval_mod.DAY2_EVAL_QUESTIONS
DAY2_EVAL_BY_ID = _day2_eval_mod.DAY2_EVAL_BY_ID


def _session_key(lead_id: int) -> str:
    return f"d2biz_{lead_id}"


def _can_view_lead_test(db, lead, username: str, role: str) -> bool:
    if not lead:
        return False
    if role == "admin":
        return True
    keys = lead.keys() if hasattr(lead, "keys") else []
    aid = None
    if "assigned_user_id" in keys and lead["assigned_user_id"] is not None:
        try:
            aid = int(lead["assigned_user_id"])
        except (TypeError, ValueError, KeyError):
            aid = None
    viewer_id = user_id_for_username(db, username)
    if viewer_id is not None and aid is not None and aid == viewer_id:
        return True
    if role == "leader" and aid is not None:
        try:
            row = db.execute("SELECT username FROM users WHERE id=?", (aid,)).fetchone()
            assignee_u = (row["username"] or "").strip() if row else ""
            down = set(_get_network_usernames(db, username))
            return assignee_u in down
        except Exception:
            return False
    return False


def _day2_certificate_fields(lead):
    cert_date = (_lead_row_value(lead, "test_completed_at") or "")[:10] or _now_ist().strftime("%Y-%m-%d")
    cert_date_display = format_day2_certificate_display_date(cert_date)
    try:
        score = int(_lead_row_value(lead, "test_score") or 0)
    except (TypeError, ValueError):
        score = 0
    return cert_date, cert_date_display, score


def _day2_batches_complete(lead) -> bool:
    try:
        return bool(
            lead["d2_morning"] and lead["d2_afternoon"] and lead["d2_evening"]
        )
    except (KeyError, TypeError):
        return False


def _build_shuffle_payload():
    q_order = [q["id"] for q in DAY2_EVAL_QUESTIONS]
    random.shuffle(q_order)
    slots = ["A", "B", "C", "D"]
    per_q = {}
    for qid in q_order:
        q = DAY2_EVAL_BY_ID[qid]
        letters = ["A", "B", "C", "D"]
        random.shuffle(letters)
        cor_orig = q["correct"]
        cor_i = letters.index(cor_orig)
        correct_display = slots[cor_i]
        ordered_opts = [(slots[i], q["options"][letters[i]]) for i in range(4)]
        per_q[str(qid)] = {
            "options": ordered_opts,
            "correct": correct_display,
            "qtext": q["q"],
        }
    return {"q_order": q_order, "per_q": per_q, "t0": time.time()}


def _build_shuffle_payload_compact():
    """Compact shuffle for cookie session (question text loaded from bank at render)."""
    q_order = [q["id"] for q in DAY2_EVAL_QUESTIONS]
    random.shuffle(q_order)
    slots_display = ["A", "B", "C", "D"]
    per_q = {}
    for qid in q_order:
        q = DAY2_EVAL_BY_ID[qid]
        letters = ["A", "B", "C", "D"]
        random.shuffle(letters)
        correct_orig = q["correct"]
        ci = letters.index(correct_orig)
        correct_display = slots_display[ci]
        perm = "".join(letters)
        per_q[str(qid)] = {"perm": perm, "cor": correct_display}
    return {"q_order": q_order, "per_q": per_q, "t0": time.time(), "compact": True}


def _expand_compact_question_rows(payload):
    rows = []
    for qid in payload["q_order"]:
        meta = payload["per_q"][str(qid)]
        q = DAY2_EVAL_BY_ID[qid]
        perm = meta["perm"]
        opts = [
            ("A", q["options"][perm[0]]),
            ("B", q["options"][perm[1]]),
            ("C", q["options"][perm[2]]),
            ("D", q["options"][perm[3]]),
        ]
        rows.append({"id": qid, "qtext": q["q"], "options": opts})
    return rows


def _public_payload_session_key(token: str) -> str:
    return f"d2pub_pl_{token}"


def _fetch_lead_by_test_token(db, token: str):
    if not token or len(token) < 12:
        return None
    return db.execute(
        "SELECT * FROM leads WHERE test_token=? AND in_pool=0 AND deleted_at='' LIMIT 1",
        (token,),
    ).fetchone()


def _absolute_public_test_url(token: str) -> str:
    root = (os.environ.get("PUBLIC_BASE_URL") or "").strip().rstrip("/")
    path = url_for("day2_test_public_entry", token=token)
    if not path.startswith("/"):
        path = "/" + path
    if root:
        return f"{root}{path}"
    return url_for("day2_test_public_entry", token=token, _external=True)


def _session_ok_for_public_token(token: str, lead_id: int) -> bool:
    try:
        lid = int(session.get("d2pub_verified_lead_id") or 0)
    except (TypeError, ValueError):
        lid = 0
    return session.get("d2pub_verified_token") == token and lid == int(lead_id)


def register_day2_test_routes(app):
    # ── WhatsApp / public token flow (register specific paths before /test/<token>) ──
    @app.route("/test/generate-link/<int:lead_id>", methods=["POST"])
    @login_required
    def day2_test_generate_link(lead_id):
        db = get_db()
        lead = db.execute(
            "SELECT * FROM leads WHERE id=? AND in_pool=0 AND deleted_at=''",
            (lead_id,),
        ).fetchone()
        role = session.get("role", "team")
        uname = acting_username() or ""
        if not lead or not _can_view_lead_test(db, lead, uname, role):
            return jsonify({"ok": False, "error": "Lead not found or access denied"}), 404
        if (lead["status"] or "") != "Day 2" or not _day2_batches_complete(lead):
            return jsonify({"ok": False, "error": "Day 2 batches must be complete first"}), 400
        if lead_day2_business_test_passed(lead):
            return jsonify({"ok": False, "error": "Test already passed"}), 400
        if lead_day2_business_test_exhausted(lead):
            return jsonify({"ok": False, "error": "No attempts remaining"}), 400

        tok = secrets.token_urlsafe(32)
        exp = (_now_ist() + timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
        now_str = _now_ist().strftime("%Y-%m-%d %H:%M:%S")
        db.execute(
            "UPDATE leads SET test_token=?, token_expiry=?, updated_at=? WHERE id=?",
            (tok, exp, now_str, lead_id),
        )
        db.commit()
        return jsonify({"ok": True, "test_url": _absolute_public_test_url(tok)})

    @app.route("/test/<token>/verify", methods=["POST"])
    def day2_test_public_verify(token):
        db = get_db()
        lead = _fetch_lead_by_test_token(db, token)
        if not lead:
            flash("Invalid link.", "danger")
            return redirect(url_for("day2_test_public_entry", token=token))
        if day2_test_token_expired(_lead_row_value(lead, "token_expiry") or ""):
            flash("This link has expired. Ask your coordinator for a new link.", "danger")
            return redirect(url_for("day2_test_public_entry", token=token))
        if lead_day2_business_test_exhausted(lead) and not lead_day2_business_test_passed(lead):
            flash("This test link is no longer available.", "danger")
            return redirect(url_for("day2_test_public_entry", token=token))
        if not lead_day2_business_test_passed(lead):
            try:
                att = int(_lead_row_value(lead, "test_attempts") or 0)
            except (TypeError, ValueError):
                att = 0
            if att >= DAY2_BUSINESS_TEST_MAX_ATTEMPTS:
                flash("Maximum attempts reached.", "danger")
                return redirect(url_for("day2_test_public_entry", token=token))

        entered = (request.form.get("phone") or "").strip()
        if not phones_match_for_lead_verification(entered, lead["phone"] or ""):
            flash("Phone number does not match our records.", "danger")
            return redirect(url_for("day2_test_public_entry", token=token))

        session["d2pub_verified_token"] = token
        session["d2pub_verified_lead_id"] = int(lead["id"])
        session.modified = True
        return redirect(url_for("day2_test_public_entry", token=token))

    @app.route("/test/<token>/start", methods=["POST"])
    def day2_test_public_start(token):
        db = get_db()
        lead = _fetch_lead_by_test_token(db, token)
        if not lead or not _session_ok_for_public_token(token, int(lead["id"])):
            flash("Please verify your phone number first.", "danger")
            return redirect(url_for("day2_test_public_entry", token=token))
        if day2_test_token_expired(_lead_row_value(lead, "token_expiry") or ""):
            flash("This link has expired.", "danger")
            return redirect(url_for("day2_test_public_entry", token=token))
        if (lead["status"] or "") != "Day 2" or not _day2_batches_complete(lead):
            flash("Test is not available.", "danger")
            return redirect(url_for("day2_test_public_entry", token=token))
        if lead_day2_business_test_passed(lead) or lead_day2_business_test_exhausted(lead):
            return redirect(url_for("day2_test_public_entry", token=token))
        try:
            att = int(_lead_row_value(lead, "test_attempts") or 0)
        except (TypeError, ValueError):
            att = 0
        if att >= DAY2_BUSINESS_TEST_MAX_ATTEMPTS:
            return redirect(url_for("day2_test_public_entry", token=token))

        session[_public_payload_session_key(token)] = _build_shuffle_payload_compact()
        session.modified = True
        return redirect(url_for("day2_test_public_entry", token=token))

    @app.route("/test/<token>/submit", methods=["POST"])
    def day2_test_public_submit(token):
        db = get_db()
        lead = _fetch_lead_by_test_token(db, token)
        sk = _public_payload_session_key(token)
        payload = session.pop(sk, None)
        session.modified = True

        if not lead or not _session_ok_for_public_token(token, int(lead["id"])):
            flash("Session expired. Open your link again and verify your phone.", "danger")
            return redirect(url_for("day2_test_public_entry", token=token))
        if day2_test_token_expired(_lead_row_value(lead, "token_expiry") or ""):
            flash("This link has expired.", "danger")
            return redirect(url_for("day2_test_public_entry", token=token))
        if not payload or "per_q" not in payload:
            flash("Test session expired — start again.", "warning")
            return redirect(url_for("day2_test_public_entry", token=token))

        if (lead["status"] or "") != "Day 2" or not _day2_batches_complete(lead):
            flash("Invalid state.", "danger")
            return redirect(url_for("day2_test_public_entry", token=token))
        if lead_day2_business_test_passed(lead) or lead_day2_business_test_exhausted(lead):
            return redirect(url_for("day2_test_public_entry", token=token))

        score = 0
        for qid_str, meta in payload["per_q"].items():
            picked = (request.form.get(f"q_{qid_str}") or "").strip().upper()
            if picked == (meta.get("cor") or ""):
                score += 1

        t1 = time.time()
        t0 = float(payload.get("t0") or t1)
        elapsed = max(0, int(t1 - t0))

        try:
            prev_att = int(_lead_row_value(lead, "test_attempts") or 0)
        except (TypeError, ValueError):
            prev_att = 0
        new_att = prev_att + 1
        now_str = _now_ist().strftime("%Y-%m-%d %H:%M:%S")

        if score >= DAY2_BUSINESS_TEST_PASS_MARK:
            new_status = "passed"
        elif new_att >= DAY2_BUSINESS_TEST_MAX_ATTEMPTS:
            new_status = "failed"
        else:
            new_status = "retry"

        db.execute(
            """
            UPDATE leads SET test_score=?, test_attempts=?, test_status=?,
                 test_completed_at=?, test_time_taken=?, updated_at=?
            WHERE id=?
            """,
            (score, new_att, new_status, now_str, elapsed, now_str, int(lead["id"])),
        )
        db.commit()

        if new_status == "passed":
            flash(f"Passed — {score}/{DAY2_BUSINESS_TEST_TOTAL_Q}. Thank you!", "success")
        elif new_status == "failed":
            flash(f"Not passed. Maximum attempts used.", "danger")
        else:
            flash(f"Score {score}/{DAY2_BUSINESS_TEST_TOTAL_Q} — you have one more attempt.", "warning")
        return redirect(url_for("day2_test_public_entry", token=token))

    @app.route("/test/<token>/certificate", methods=["GET"])
    def day2_test_public_certificate(token):
        """Printable certificate — same WhatsApp link + phone verify; Day 2 test pass only."""
        db = get_db()
        lead = _fetch_lead_by_test_token(db, token)
        if not lead:
            flash("Invalid link.", "danger")
            return redirect(url_for("day2_test_public_entry", token=token))
        if day2_test_token_expired(_lead_row_value(lead, "token_expiry") or ""):
            flash("This link has expired — ask your coordinator for a new link.", "danger")
            return redirect(url_for("day2_test_public_entry", token=token))
        if not _session_ok_for_public_token(token, int(lead["id"])):
            flash("Verify your mobile number with this link first.", "warning")
            return redirect(url_for("day2_test_public_entry", token=token))
        if not lead_day2_certificate_eligible(lead):
            flash("The certificate is available only after you pass the Day 2 test.", "info")
            return redirect(url_for("day2_test_public_entry", token=token))
        cert_date, cert_date_display, score = _day2_certificate_fields(lead)
        return render_template(
            "lead_day2_certificate_public.html",
            lead=lead,
            token=token,
            cert_date=cert_date,
            cert_date_display=cert_date_display,
            score_display=score,
            total_q=DAY2_BUSINESS_TEST_TOTAL_Q,
        )

    @app.route("/test/<token>/certificate.pdf", methods=["GET"])
    def day2_test_public_certificate_pdf(token):
        db = get_db()
        lead = _fetch_lead_by_test_token(db, token)
        if not lead:
            flash("Invalid link.", "danger")
            return redirect(url_for("day2_test_public_entry", token=token))
        if day2_test_token_expired(_lead_row_value(lead, "token_expiry") or ""):
            flash("This link has expired — ask your coordinator for a new link.", "danger")
            return redirect(url_for("day2_test_public_entry", token=token))
        if not _session_ok_for_public_token(token, int(lead["id"])):
            flash("Verify your mobile number with this link first.", "warning")
            return redirect(url_for("day2_test_public_entry", token=token))
        if not lead_day2_certificate_eligible(lead):
            flash("The certificate is available only after you pass the Day 2 test.", "info")
            return redirect(url_for("day2_test_public_entry", token=token))
        lead_id = int(lead["id"])
        name = lead["name"] or "Participant"
        _, cert_date_display, score = _day2_certificate_fields(lead)
        pdf = build_day2_business_certificate_pdf(
            name, score, DAY2_BUSINESS_TEST_TOTAL_Q, cert_date_display
        )
        fn = f"myle-day2-certificate-{lead_id}.pdf"
        return Response(
            pdf,
            mimetype="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{fn}"',
                "Cache-Control": "private, no-store",
            },
        )

    @app.route("/test/<token>", methods=["GET"])
    def day2_test_public_entry(token):
        db = get_db()
        lead = _fetch_lead_by_test_token(db, token)

        csrf = session.get("_csrf_token", "")
        common = {
            "token": token,
            "csrf_token": csrf,
            "total_q": DAY2_BUSINESS_TEST_TOTAL_Q,
            "pass_mark": DAY2_BUSINESS_TEST_PASS_MARK,
        }

        if not lead:
            return render_template(
                "day2_test_public.html",
                block_reason="This link is invalid or no longer active.",
                step="blocked",
                **common,
            )

        if day2_test_token_expired(_lead_row_value(lead, "token_expiry") or ""):
            return render_template(
                "day2_test_public.html",
                block_reason="This link has expired (24 hours). Ask your coordinator for a new link.",
                step="blocked",
                **common,
            )

        if lead_day2_business_test_passed(lead):
            if not _session_ok_for_public_token(token, int(lead["id"])):
                return render_template(
                    "day2_test_public.html",
                    step="verify",
                    lead_name="",
                    **common,
                )
            return render_template(
                "day2_test_public.html",
                step="landing",
                lead_name=(lead["name"] or "").split()[0] if lead["name"] else "",
                lead=lead,
                test_status="passed",
                **common,
            )

        if lead_day2_business_test_exhausted(lead):
            return render_template(
                "day2_test_public.html",
                block_reason="Maximum attempts reached for this evaluation.",
                step="blocked",
                **common,
            )

        try:
            att = int(_lead_row_value(lead, "test_attempts") or 0)
        except (TypeError, ValueError):
            att = 0
        if att >= DAY2_BUSINESS_TEST_MAX_ATTEMPTS:
            return render_template(
                "day2_test_public.html",
                block_reason="Maximum attempts reached.",
                step="blocked",
                **common,
            )

        if (lead["status"] or "") != "Day 2" or not _day2_batches_complete(lead):
            return render_template(
                "day2_test_public.html",
                block_reason="This evaluation is not open yet.",
                step="blocked",
                **common,
            )

        if not _session_ok_for_public_token(token, int(lead["id"])):
            return render_template(
                "day2_test_public.html",
                step="verify",
                lead_name="",
                **common,
            )

        pl = session.get(_public_payload_session_key(token))
        if pl and pl.get("per_q"):
            rows = _expand_compact_question_rows(pl)
            return render_template(
                "day2_test_public.html",
                step="questions",
                question_rows=rows,
                lead_name=(lead["name"] or "").split()[0] if lead["name"] else "",
                **common,
            )

        ts = (_lead_row_value(lead, "test_status") or "pending").strip().lower()
        return render_template(
            "day2_test_public.html",
            step="landing",
            lead_name=(lead["name"] or "").split()[0] if lead["name"] else "",
            lead=lead,
            test_status=ts,
            **common,
        )

    @app.route("/test/day2/<int:lead_id>", methods=["GET"])
    @login_required
    @safe_route
    def day2_business_test_page(lead_id):
        db = get_db()
        lead = db.execute(
            "SELECT * FROM leads WHERE id=? AND in_pool=0 AND deleted_at=''",
            (lead_id,),
        ).fetchone()
        role = session.get("role", "team")
        uname = acting_username() or ""
        if not lead or not _can_view_lead_test(db, lead, uname, role):
            flash("Lead not found or access denied.", "danger")
            return redirect(url_for("leads"))
        if (lead["status"] or "") != "Day 2" or not _day2_batches_complete(lead):
            flash("Complete all Day 2 batches before starting the test.", "warning")
            return redirect(url_for("working"))

        sk = _session_key(lead_id)
        payload = session.get(sk)
        lead = _enrich_leads([dict(lead)])[0]
        return render_template(
            "day2_business_test.html",
            lead=lead,
            payload=payload,
            total_q=DAY2_BUSINESS_TEST_TOTAL_Q,
            pass_mark=DAY2_BUSINESS_TEST_PASS_MARK,
            csrf_token=session.get("_csrf_token", ""),
        )

    @app.route("/test/start/<int:lead_id>", methods=["POST"])
    @login_required
    @safe_route
    def day2_business_test_start(lead_id):
        db = get_db()
        lead = db.execute(
            "SELECT * FROM leads WHERE id=? AND in_pool=0 AND deleted_at=''",
            (lead_id,),
        ).fetchone()
        role = session.get("role", "team")
        uname = acting_username() or ""
        if not lead or not _can_view_lead_test(db, lead, uname, role):
            flash("Lead not found or access denied.", "danger")
            return redirect(url_for("leads"))
        if (lead["status"] or "") != "Day 2" or not _day2_batches_complete(lead):
            flash("Finish all Day 2 batches first.", "warning")
            return redirect(url_for("day2_business_test_page", lead_id=lead_id))

        if lead_day2_business_test_passed(lead):
            flash("Test already passed.", "info")
            return redirect(url_for("day2_business_test_page", lead_id=lead_id))
        if lead_day2_business_test_exhausted(lead):
            flash("Max attempts used — test locked.", "danger")
            return redirect(url_for("day2_business_test_page", lead_id=lead_id))

        session[_session_key(lead_id)] = _build_shuffle_payload()
        session.modified = True
        return redirect(url_for("day2_business_test_page", lead_id=lead_id))

    @app.route("/test/submit/<int:lead_id>", methods=["POST"])
    @login_required
    @safe_route
    def day2_business_test_submit(lead_id):
        db = get_db()
        lead = db.execute(
            "SELECT * FROM leads WHERE id=? AND in_pool=0 AND deleted_at=''",
            (lead_id,),
        ).fetchone()
        role = session.get("role", "team")
        uname = acting_username() or ""
        if not lead or not _can_view_lead_test(db, lead, uname, role):
            flash("Lead not found or access denied.", "danger")
            return redirect(url_for("leads"))

        sk = _session_key(lead_id)
        payload = session.pop(sk, None)
        session.modified = True

        if not payload or "per_q" not in payload:
            flash("Session expired — start the test again.", "warning")
            return redirect(url_for("day2_business_test_page", lead_id=lead_id))

        if (lead["status"] or "") != "Day 2" or not _day2_batches_complete(lead):
            flash("Invalid state for test submit.", "danger")
            return redirect(url_for("working"))

        if lead_day2_business_test_passed(lead) or lead_day2_business_test_exhausted(lead):
            flash("No further attempts.", "warning")
            return redirect(url_for("day2_business_test_page", lead_id=lead_id))

        score = 0
        for qid_str, meta in payload["per_q"].items():
            picked = (request.form.get(f"q_{qid_str}") or "").strip().upper()
            if picked == (meta.get("correct") or ""):
                score += 1

        t1 = time.time()
        t0 = float(payload.get("t0") or t1)
        elapsed = max(0, int(t1 - t0))

        try:
            prev_att = int(_lead_row_value(lead, "test_attempts") or 0)
        except (TypeError, ValueError):
            prev_att = 0
        new_att = prev_att + 1
        now_str = _now_ist().strftime("%Y-%m-%d %H:%M:%S")

        if score >= DAY2_BUSINESS_TEST_PASS_MARK:
            new_status = "passed"
        elif new_att >= DAY2_BUSINESS_TEST_MAX_ATTEMPTS:
            new_status = "failed"
        else:
            new_status = "retry"

        db.execute(
            """
            UPDATE leads SET test_score=?, test_attempts=?, test_status=?,
                 test_completed_at=?, test_time_taken=?, updated_at=?
            WHERE id=?
            """,
            (
                score,
                new_att,
                new_status,
                now_str,
                elapsed,
                now_str,
                lead_id,
            ),
        )
        db.commit()

        if new_status == "passed":
            flash(f"Passed — {score}/{DAY2_BUSINESS_TEST_TOTAL_Q}. Interview stage unlock.", "success")
        elif new_status == "failed":
            flash(f"Not passed ({score}/{DAY2_BUSINESS_TEST_TOTAL_Q}). Max attempts reached.", "danger")
        else:
            flash(f"Score {score}/{DAY2_BUSINESS_TEST_TOTAL_Q} — one attempt remaining.", "warning")
        return redirect(url_for("day2_business_test_page", lead_id=lead_id))

    @app.route("/leads/<int:lead_id>/day2-certificate")
    @login_required
    @safe_route
    def lead_day2_certificate(lead_id):
        db = get_db()
        lead = db.execute(
            "SELECT * FROM leads WHERE id=? AND in_pool=0 AND deleted_at=''",
            (lead_id,),
        ).fetchone()
        role = session.get("role", "team")
        uname = acting_username() or ""
        if not lead or not _can_view_lead_test(db, lead, uname, role):
            flash("Lead not found or access denied.", "danger")
            return redirect(url_for("leads"))
        if not lead_day2_certificate_eligible(lead):
            flash("Certificate is issued only after the Day 2 business test is passed.", "warning")
            return redirect(url_for("edit_lead", lead_id=lead_id))
        cert_date, cert_date_display, score = _day2_certificate_fields(lead)
        return render_template(
            "lead_day2_certificate.html",
            lead=lead,
            cert_date=cert_date,
            cert_date_display=cert_date_display,
            score_display=score,
            total_q=DAY2_BUSINESS_TEST_TOTAL_Q,
        )

    @app.route("/leads/<int:lead_id>/day2-certificate.pdf")
    @login_required
    @safe_route
    def lead_day2_certificate_pdf(lead_id):
        db = get_db()
        lead = db.execute(
            "SELECT * FROM leads WHERE id=? AND in_pool=0 AND deleted_at=''",
            (lead_id,),
        ).fetchone()
        role = session.get("role", "team")
        uname = acting_username() or ""
        if not lead or not _can_view_lead_test(db, lead, uname, role):
            flash("Lead not found or access denied.", "danger")
            return redirect(url_for("leads"))
        if not lead_day2_certificate_eligible(lead):
            flash("Certificate is issued only after the Day 2 business test is passed.", "warning")
            return redirect(url_for("edit_lead", lead_id=lead_id))
        name = lead["name"] or "Participant"
        _, cert_date_display, score = _day2_certificate_fields(lead)
        pdf = build_day2_business_certificate_pdf(
            name, score, DAY2_BUSINESS_TEST_TOTAL_Q, cert_date_display
        )
        fn = f"myle-day2-certificate-{lead_id}.pdf"
        return Response(
            pdf,
            mimetype="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{fn}"',
                "Cache-Control": "private, no-store",
            },
        )

    @app.route("/admin/day2-business-test-report")
    @admin_required
    @safe_route
    def admin_day2_business_test_report():
        db = get_db()
        rows = db.execute(
            """
            SELECT l.id, l.name, l.phone, COALESCE(u.username, '') AS assigned_to, l.status, l.test_status, l.test_score,
                   l.test_attempts, l.test_completed_at, l.test_time_taken, l.interview_done, l.interview_status
            FROM leads l
            LEFT JOIN users u ON u.id = l.assigned_user_id
            WHERE l.in_pool=0 AND l.deleted_at=''
              AND (
                COALESCE(l.test_attempts,0) > 0
                OR LOWER(COALESCE(l.test_status,'')) IN ('passed','failed','retry')
              )
            ORDER BY l.test_completed_at DESC, l.id DESC
            """
        ).fetchall()
        return render_template(
            "admin_day2_test_report.html",
            rows=rows,
            total_q=DAY2_BUSINESS_TEST_TOTAL_Q,
            pass_mark=DAY2_BUSINESS_TEST_PASS_MARK,
        )
