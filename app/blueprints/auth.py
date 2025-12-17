from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, current_user
from app.models import User

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated: return redirect(url_for('main.dashboard'))
    if request.method == 'POST':
        email_in = request.form.get('email').strip().lower()
        user = User.query.filter_by(email=email_in).first()
        if user and user.check_password(request.form.get('password')):
            login_user(user)
            return redirect(url_for('main.dashboard'))
        flash('Invalid credentials.', 'error')
    return render_template('login.html')

@auth_bp.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('auth.login'))
