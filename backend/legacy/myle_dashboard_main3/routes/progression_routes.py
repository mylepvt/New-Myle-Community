from flask import render_template, request, redirect, url_for, flash, session
import datetime
from database import get_db
from decorators import login_required, safe_route
from services.scoring_service import add_points
from auth_context import acting_username

def register_progression_routes(app):
    @app.route('/day2-test', methods=['GET'])
    @login_required
    @safe_route
    def day2_test():
        """Renders the mandatory Day 2 -> Day 3 progression test."""
        username = acting_username()
        db = get_db()
        
        # Verify the user is actually in Day 2
        user = db.execute("SELECT user_stage, total_points FROM users WHERE username=?", (username,)).fetchone()
        if not user or user['user_stage'] != 'day2':
            flash("You are not eligible to take the Day 2 Test. Make sure you have completed Day 1 requirements.", "warning")
            return redirect(url_for('admin_dashboard') if session.get('role') == 'admin' else url_for('team_dashboard'))

        # Load questions
        questions = db.execute("SELECT id, question_text, option_a, option_b, option_c, option_d FROM day2_questions").fetchall()
        
        return render_template('day2_test.html', questions=questions)

    @app.route('/day2-test/submit', methods=['POST'])
    @login_required
    @safe_route
    def day2_test_submit():
        """Evaluates the Day 2 test submission and promotes user to Day 3 if score >= 80%."""
        username = acting_username()
        db = get_db()
        
        user = db.execute("SELECT user_stage FROM users WHERE username=?", (username,)).fetchone()
        if not user or user['user_stage'] != 'day2':
            return redirect(url_for('admin_dashboard') if session.get('role') == 'admin' else url_for('team_dashboard'))

        questions = db.execute("SELECT id, correct_option FROM day2_questions").fetchall()
        total_q = len(questions)
        if total_q == 0:
            flash("No test questions available. Contact Admin.", "danger")
            return redirect(url_for('admin_dashboard') if session.get('role') == 'admin' else url_for('team_dashboard'))

        score = 0
        for q in questions:
            ans = request.form.get(f"q_{q['id']}")
            if ans and ans.strip().upper() == q['correct_option'].strip().upper():
                score += 1
                
        percentage = (score / total_q) * 100
        
        if percentage >= 80:
            # Pass Test - Unlock Day 3
            db.execute("UPDATE users SET user_stage='day3' WHERE username=?", (username,))
            
            # Reward DAY2_COMPLETE (+100 pts)
            add_points(username, 'DAY2_COMPLETE', f'Passed Day 2 Test with {int(percentage)}%', db=db)
            
            db.commit()
            
            flash(f"🎉 Congratulations! You scored {int(percentage)}% and mastered Day 2. You are now promoted to Day 3!", "success")
            return redirect(url_for('admin_dashboard') if session.get('role') == 'admin' else url_for('team_dashboard'))
        else:
            # Failed Test
            flash(f"You scored {int(percentage)}%. You need 80% to pass and unlock Day 3. Please review your training materials and try again.", "danger")
            return redirect(url_for('day2_test'))
