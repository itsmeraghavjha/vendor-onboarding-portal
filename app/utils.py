import os
import uuid
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import current_app, render_template, url_for
from flask_mail import Message
from .extensions import db, mail
from .models import MockEmail, User, CategoryRouting, WorkflowStep, ITRouting

# --- CRITICAL IMPORT ---
# We must import the task so we can call .delay() on it
from .tasks import send_async_email 

def save_file(file_obj, prefix):
    if not file_obj or not file_obj.filename: return None
    filename = file_obj.filename
    if '.' not in filename: return None
    ext = filename.rsplit('.', 1)[1].lower()
    if ext in current_app.config['ALLOWED_EXTENSIONS']:
        # Use config for upload folder
        upload_folder = current_app.config['UPLOAD_FOLDER']
        safe_name = secure_filename(f"{prefix}_{uuid.uuid4().hex[:8]}.{ext}")
        os.makedirs(upload_folder, exist_ok=True)
        file_obj.save(os.path.join(upload_folder, safe_name))
        return safe_name
    return None

def send_system_email(to, subject, body, link=None):
    """
    Generic sender for system alerts.
    """
    try:
        # Use .delay() to hand off the task to Celery/Redis
        # This returns immediately, so the user doesn't wait.
        send_async_email.delay(subject, to, body) 
        print(f"✓ Task queued for {to}")
    except Exception as e:
        print(f"✗ Task Error: {e}")

def send_status_email(req, next_email, stage_name):
    """Workflow-specific sender."""
    if not next_email: return
    
    subject = f"Action Required: {stage_name} - {req.vendor_name_basic}"
    
    # We tell Python: "Don't use a string. Go read 'email/notification.html' instead."
    body = render_template('email/notification.html', 
                           req=req, 
                           subject=subject,
                           body=f"The request is currently at the <b>{stage_name}</b> stage and requires your approval.",
                           link=url_for('auth.login', _external=True),
                           current_year=datetime.now().year)
    
    send_system_email(next_email, subject, body)

def get_next_approver_email(req):
    """
    Determines the next email address based on the 3-Phase Pipeline.
    """
    
    # --- PHASE 0: INITIATOR REVIEW ---
    if req.current_dept_flow == 'INITIATOR_REVIEW':
        initiator = db.session.get(User, req.initiator_id)
        return initiator.email if initiator else None, "Initiator Review"

    # --- PHASE 1: DEPARTMENT INTERNAL ---
    elif req.current_dept_flow == 'DEPT':
        # 1. Check Category Rule (Priority)
        cat_rule = CategoryRouting.query.filter_by(department=req.initiator_dept, category_name=req.vendor_type).first()
        
        if cat_rule:
            if req.current_step_number == 1:
                return cat_rule.l1_manager_email, "Department L1 Review"
            if req.current_step_number == 2:
                return cat_rule.l2_head_email, "Department Head Review"
        
        # 2. Check Standard Steps (Fallback)
        step = WorkflowStep.query.filter_by(department=req.initiator_dept, step_order=req.current_step_number).first()
        if step:
            return step.approver_email, f"{step.role_label} Review"

    # --- PHASE 2: COMMON FINANCE CHAIN ---
    elif req.current_dept_flow == 'FINANCE':
        role_map = {
            'BILL_PASSING': 'Bill Passing Team',
            'TREASURY': 'Treasury Team',
            'TAX': 'Tax Team'
        }
        target_username = role_map.get(req.finance_stage)
        if target_username:
            user = User.query.filter_by(username=target_username).first()
            fallback = current_app.config['ADMIN_EMAIL']
            return user.email if user else fallback, f"Finance: {req.finance_stage.replace('_', ' ').title()}"

    # --- PHASE 3: COMMON IT EXECUTION ---
    elif req.current_dept_flow == 'IT':
        route = ITRouting.query.filter_by(account_group=req.account_group).first()
        if route:
            return route.it_assignee_email, "IT: SAP Creation"
        else:
            return current_app.config['IT_ADMIN_EMAIL'], "IT: Admin (Fallback)"

    return None, None