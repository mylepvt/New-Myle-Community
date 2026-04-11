"""
Admin task routes (create / mark-done / delete) and my-tasks API.

Registered via register_tasks_routes(app) at the end of app.py load.
"""
from __future__ import annotations

from flask import jsonify, request, session

from database import get_db
from decorators import admin_required, login_required
from helpers import _now_ist
from auth_context import acting_username


def _admin_task_visible_to_actor(db, task_id: int, username: str, role: str):
    """Same targeting rules as /api/my-tasks — must match before marking done."""
    row = db.execute(
        """
        SELECT 1 FROM admin_tasks t
        WHERE t.id=? AND t.is_done=0
          AND (t.target='all' OR t.target=? OR t.target=?)
        LIMIT 1
        """,
        (task_id, role, username),
    ).fetchone()
    return row is not None


def register_tasks_routes(app):
    """Attach task-related URL rules to the Flask app."""

    @app.route('/admin/tasks/create', methods=['POST'])
    @admin_required
    def admin_task_create():
        csrf = request.form.get('csrf_token', '')
        if csrf != session.get('_csrf_token', ''):
            return jsonify({'ok': False, 'error': 'CSRF'}), 403
        title    = (request.form.get('title', '') or '').strip()
        body     = (request.form.get('body', '') or '').strip()
        target   = request.form.get('target', 'all')
        priority = request.form.get('priority', 'normal')
        due_date = (request.form.get('due_date', '') or '').strip()
        if not title:
            return jsonify({'ok': False, 'error': 'Title required'}), 400
        db = get_db()
        now_str = _now_ist().strftime('%Y-%m-%d %H:%M:%S')
        cursor = db.execute(
            "INSERT INTO admin_tasks (title,body,created_by,target,priority,due_date,created_at) VALUES (?,?,?,?,?,?,?)",
            (title, body, acting_username(), target, priority, due_date, now_str)
        )
        task_id = cursor.lastrowid
        db.commit()
        return jsonify({'ok': True, 'id': task_id, 'title': title, 'priority': priority, 'body': body, 'due_date': due_date, 'target': target})


    @app.route('/tasks/<int:task_id>/done', methods=['POST'])
    @login_required
    def task_mark_done(task_id):
        if request.is_json:
            data = request.get_json(silent=True) or {}
            csrf = data.get('csrf_token', '')
        else:
            csrf = request.form.get('csrf_token', '')
        if csrf != session.get('_csrf_token', ''):
            return jsonify({'ok': False, 'error': 'CSRF'}), 403
        db = get_db()
        username = acting_username()
        role = session.get('role', 'team')
        if not _admin_task_visible_to_actor(db, task_id, username or '', role):
            return jsonify({'ok': False, 'error': 'Task not available'}), 403
        now_str = _now_ist().strftime('%Y-%m-%d %H:%M:%S')
        try:
            db.execute(
                "INSERT OR IGNORE INTO admin_task_done (task_id, username, done_at) VALUES (?,?,?)",
                (task_id, username, now_str),
            )
            db.commit()
        except Exception as ex:
            app.logger.error("task_mark_done failed task_id=%s user=%s: %s", task_id, username, ex)
            return jsonify({'ok': False, 'error': 'Could not save'}), 500
        return jsonify({'ok': True})


    @app.route('/admin/tasks/<int:task_id>/delete', methods=['POST'])
    @admin_required
    def admin_task_delete(task_id):
        csrf = request.form.get('csrf_token', '')
        if csrf != session.get('_csrf_token', ''):
            return jsonify({'ok': False, 'error': 'CSRF'}), 403
        db = get_db()
        db.execute("UPDATE admin_tasks SET is_done=1 WHERE id=?", (task_id,))
        db.commit()
        return jsonify({'ok': True})


    @app.route('/api/my-tasks')
    @login_required
    def api_my_tasks():
        """Return pending tasks for the current user (leader/team)."""
        db = get_db()
        username = acting_username()
        role     = session.get('role', 'team')
        tasks = db.execute("""
            SELECT t.id, t.title, t.body, t.priority, t.due_date, t.created_at,
                   d.done_at
            FROM admin_tasks t
            LEFT JOIN admin_task_done d ON d.task_id=t.id AND d.username=?
            WHERE t.is_done=0
              AND (t.target='all'
                   OR t.target=?
                   OR t.target=?)
            ORDER BY t.priority='urgent' DESC, t.created_at DESC
        """, (username, role, username)).fetchall()
        return jsonify([dict(t) for t in tasks])
