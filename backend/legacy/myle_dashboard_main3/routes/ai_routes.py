"""
AI / Intelligence routes: Maya chat, lead intelligence dashboard, today-score API.

Registered via register_ai_routes(app) at the end of app.py load.
"""
from __future__ import annotations

import os

from flask import flash, jsonify, redirect, render_template, request, session, url_for

from database import get_db
from decorators import login_required, safe_route
from auth_context import acting_user_id, acting_username
from helpers import (
    BADGE_META,
    _enrich_leads,
    _generate_ai_tip,
    _get_network_usernames,
    _get_setting,
    _get_today_score,
    network_user_ids_for_username,
)


def register_ai_routes(app):
    """Attach AI/intelligence URL rules to the Flask app."""
    from app import (  # noqa: PLC0415
        ANTHROPIC_AVAILABLE,
        MAYA_SYSTEM_PROMPT,
        _anthropic_lib,
    )

    @app.route('/intelligence')
    @login_required
    @safe_route
    def intelligence():
        from app import myle_ai_features_enabled  # noqa: PLC0415

        if not myle_ai_features_enabled():
            flash('AI Intelligence is disabled.', 'info')
            if session.get('role') == 'admin':
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('team_dashboard'))

        db       = get_db()
        username = acting_username()
        role     = session.get('role', 'team')

        try:
            if role == 'admin':
                raw_leads = db.execute(
                    "SELECT * FROM leads WHERE in_pool=0 AND deleted_at='' ORDER BY updated_at DESC LIMIT 150"
                ).fetchall()
            elif role == 'leader':
                dl_ids = network_user_ids_for_username(db, username or '')
                if dl_ids:
                    phs = ','.join('?' for _ in dl_ids)
                    raw_leads = db.execute(
                        f"SELECT * FROM leads WHERE in_pool=0 AND deleted_at='' AND assigned_user_id IN ({phs}) ORDER BY updated_at DESC",
                        tuple(dl_ids),
                    ).fetchall()
                else:
                    raw_leads = []
            else:
                _uid = acting_user_id()
                raw_leads = (
                    db.execute(
                        "SELECT * FROM leads WHERE assigned_user_id=? AND in_pool=0 AND deleted_at='' ORDER BY updated_at DESC",
                        (_uid,),
                    ).fetchall()
                    if _uid is not None
                    else []
                )
        except Exception as e:
            app.logger.error(f"intelligence() leads query failed: {e}")
            raw_leads = []

        # ── Leaderboard data (weekly scores) ──
        try:
            lb_rows = db.execute("""
                SELECT u.username,
                       COALESCE(SUM(ds.total_points), 0)   AS week_pts,
                       COALESCE(SUM(ds.batches_marked), 0) AS batches,
                       MAX(ds.streak_days)                 AS streak
                FROM users u
                LEFT JOIN daily_scores ds
                       ON ds.username = u.username
                      AND ds.score_date >= date('now', '-6 days')
                WHERE u.role IN ('team','leader') AND u.status='approved'
                GROUP BY u.username
                ORDER BY week_pts DESC
                LIMIT 10
            """).fetchall()
            lb_board = [dict(r) for r in lb_rows]
        except Exception:
            lb_board = []


        try:
            enriched = _enrich_leads(raw_leads)
        except Exception as e:
            app.logger.error(f"intelligence() enrichment failed: {e}")
            enriched = []
        for d in enriched:
            try:
                d['ai_tip'] = _generate_ai_tip(d)
            except Exception:
                d['ai_tip'] = ''
        enriched.sort(key=lambda x: (
            {'urgent': 0, 'today': 1, 'followup': 2, 'cold': 3}.get(x.get('next_action_type', 'cold'), 9),
            -x.get('heat', 0),
        ))

        urgent_count = sum(1 for l in enriched if l.get('next_action_type') == 'urgent')
        hot_count    = sum(1 for l in enriched if l.get('heat', 0) >= 75)

        return render_template('intelligence.html',
                               leads=enriched,
                               urgent_count=urgent_count,
                               hot_count=hot_count,
                               user_role=role,
                               badge_meta=BADGE_META,
                               lb_board=lb_board,
                               current_user=username)


    @app.route('/ai/lead-intelligence')
    @login_required
    def ai_lead_intelligence():
        from app import myle_ai_features_enabled  # noqa: PLC0415

        if not myle_ai_features_enabled():
            return jsonify({'error': 'AI features disabled'}), 404

        db       = get_db()
        username = acting_username()
        role     = session.get('role')

        if role == 'admin':
            raw_leads = db.execute(
                "SELECT * FROM leads WHERE in_pool=0 AND deleted_at='' ORDER BY updated_at DESC LIMIT 150"
            ).fetchall()
        elif role == 'leader':
            dl_ids = network_user_ids_for_username(db, username or '')
            if dl_ids:
                phs = ','.join('?' for _ in dl_ids)
                raw_leads = db.execute(
                    f"SELECT * FROM leads WHERE in_pool=0 AND deleted_at='' AND assigned_user_id IN ({phs}) "
                    "ORDER BY updated_at DESC LIMIT 150",
                    tuple(dl_ids),
                ).fetchall()
            else:
                raw_leads = []
        else:
            _uid = acting_user_id()
            raw_leads = (
                db.execute(
                    "SELECT * FROM leads WHERE assigned_user_id=? AND in_pool=0 AND deleted_at='' ORDER BY updated_at DESC LIMIT 150",
                    (_uid,),
                ).fetchall()
                if _uid is not None
                else []
            )


        enriched = _enrich_leads(raw_leads)
        for d in enriched:
            d['ai_tip'] = _generate_ai_tip(d)

        enriched.sort(key=lambda x: (
            {'urgent': 0, 'today': 1, 'followup': 2, 'cold': 3}.get(x.get('next_action_type', 'cold'), 9),
            -x.get('heat', 0),
        ))

        urgent_count = sum(1 for l in enriched if l.get('next_action_type') == 'urgent')
        hot_count    = sum(1 for l in enriched if l.get('heat', 0) >= 75)

        return jsonify({
            'leads': [{
                'id':               l.get('id'),
                'name':             l.get('name', ''),
                'stage':            l.get('pipeline_stage', 'prospecting'),
                'heat':             l.get('heat', 0),
                'next_action':      l.get('next_action', ''),
                'next_action_type': l.get('next_action_type', 'followup'),
                'call_status':      l.get('call_status', ''),
                'ai_tip':           l.get('ai_tip', ''),
                'owner':            l.get('assignee_username', ''),
            } for l in enriched],
            'urgent_count': urgent_count,
            'hot_count':    hot_count,
        })


    @app.route('/api/chat', methods=['POST'])
    @login_required
    def api_chat():
        from app import maya_chat_enabled  # noqa: PLC0415

        if not maya_chat_enabled():
            return {'error': 'AI assistant is disabled.'}, 503

        data = request.get_json(silent=True) or {}
        message    = (data.get('message') or '').strip()
        image_data = data.get('image')   # base64 data URL

        if not message and not image_data:
            return {'error': 'Empty message.'}, 400

        # ── Resolve Anthropic API key ───────────────────────────────────
        db            = get_db()
        anthropic_key = (_get_setting(db, 'anthropic_api_key', '') or '').strip() or os.environ.get('ANTHROPIC_API_KEY', '').strip()

        if not anthropic_key or not ANTHROPIC_AVAILABLE:
            return {'error': 'AI assistant not configured. Add Anthropic API key in Admin → Settings.'}, 503

        # ── Conversation history from session ──────────────────────────
        history = list(session.get('maya_history', []))

        # ── Decode image if provided ────────────────────────────────────
        b64_data   = None
        media_type = 'image/jpeg'
        if image_data:
            if ',' in image_data:
                header, b64_data = image_data.split(',', 1)
                media_type = header.split(';')[0].split(':')[1] if ':' in header else 'image/jpeg'
            else:
                b64_data = image_data

        text_for_ai = message or 'Is screenshot ko dekho aur specific, actionable advice do.'

        # ── Call Anthropic ───────────────────────────────────────────────
        reply    = None
        last_err = ''

        try:
            content = []
            if b64_data:
                content.append({'type': 'image', 'source': {
                    'type': 'base64', 'media_type': media_type, 'data': b64_data}})
            content.append({'type': 'text', 'text': text_for_ai})

            ant_history = []
            for h in history:
                ant_history.append({'role': h['role'], 'content': h['content']})
            ant_history.append({'role': 'user', 'content': content})
            if len(ant_history) > 16:
                ant_history = ant_history[-16:]

            client   = _anthropic_lib.Anthropic(api_key=anthropic_key)
            response = client.messages.create(
                model='claude-haiku-4-5-20251001', max_tokens=1024,
                system=MAYA_SYSTEM_PROMPT, messages=ant_history
            )
            reply = response.content[0].text
        except Exception as e:
            last_err = str(e)

        # ── Failed ───────────────────────────────────────────────────────
        if reply is None:
            if '401' in last_err or '403' in last_err or 'api_key' in last_err.lower():
                return {'error': 'AI key is invalid — contact Admin.'}, 401
            return {'error': 'Maya is not available right now. Try again in a moment.'}, 503

        # ── Save history (text only) ────────────────────────────────────
        if image_data and not message:
            user_hist = '📸 [Screenshot shared]'
        elif image_data:
            user_hist = f'📸 {message}'
        else:
            user_hist = message

        history.append({'role': 'user',      'content': user_hist})
        history.append({'role': 'assistant', 'content': reply})
        if len(history) > 16:
            history = history[-16:]
        session['maya_history'] = history
        session.modified = True

        return {'reply': reply}


    @app.route('/api/chat/clear', methods=['POST'])
    @login_required
    def api_chat_clear():
        from app import maya_chat_enabled  # noqa: PLC0415

        if not maya_chat_enabled():
            return {'ok': True}
        session.pop('maya_history', None)
        session.modified = True
        return {'ok': True}


    @app.route('/api/today-score')
    @login_required
    def api_today_score():
        db = get_db()
        score, streak = _get_today_score(db, acting_username())
        return {'ok': True, 'score': score, 'streak': streak}
