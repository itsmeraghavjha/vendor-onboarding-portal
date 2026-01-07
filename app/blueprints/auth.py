from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, current_user
from app.models import User
from app.extensions import db
from app.forms import LoginForm, ResetPasswordRequestForm, ResetPasswordForm
from app.utils import send_system_email


auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated: return redirect(url_for('main.dashboard'))
    
    # Assuming you are using the WTForms logic we discussed earlier
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower().strip()).first()
        if user and user.check_password(form.password.data):
            if not user.is_active:
                flash('Your account has been disabled. Please contact the administrator.', 'error')
                return render_template('auth/login.html', form=form)
                
            login_user(user)
            return redirect(url_for('main.dashboard'))
        flash('Invalid email or password.', 'error')
    
    # FIX: Updated path to 'auth/login.html'
    return render_template('auth/login.html', form=form)

@auth_bp.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('auth.login'))

@auth_bp.route('/reset_password_request', methods=['GET', 'POST'])
def reset_password_request():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    form = ResetPasswordRequestForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower().strip()).first()
        if user:
            token = user.get_reset_token()
            # In production, ensure _external=True generates the correct HTTPS link
            url = url_for('auth.reset_password', token=token, _external=True)
            body = f"""
            <h3>Password Reset Request</h3>
            <p>To reset your password, click the following link:</p>
            <p><a href='{url}'>{url}</a></p>
            <p>If you did not make this request, simply ignore this email and no changes will be made.</p>
            """
            send_system_email(user.email, "Password Reset Request", body)
        
        flash('Check your email for instructions to reset your password.', 'info')
        return redirect(url_for('auth.login'))
        
    return render_template('auth/reset_request.html', form=form)

@auth_bp.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
        
    user = User.verify_reset_token(token)
    if not user:
        flash('That is an invalid or expired token.', 'error')
        return redirect(url_for('auth.reset_password_request'))
        
    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        db.session.commit()
        flash('Your password has been updated! You can now log in.', 'success')
        return redirect(url_for('auth.login'))
        
    return render_template('auth/reset_token.html', form=form)