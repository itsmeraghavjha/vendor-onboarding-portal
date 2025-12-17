import os
import uuid
from werkzeug.utils import secure_filename
from flask import current_app, render_template, url_for
from flask_mail import Message
from .extensions import db, mail
from .models import MockEmail, User, CategoryRouting, WorkflowStep, ITRouting

def save_file(file_obj, prefix):
    if not file_obj or not file_obj.filename: return None
    filename = file_obj.filename
    if '.' not in filename: return None
    ext = filename.rsplit('.', 1)[1].lower()
    if ext in current_app.config['ALLOWED_EXTENSIONS']:
        safe_name = secure_filename(f"{prefix}_{uuid.uuid4().hex[:8]}.{ext}")
        os.makedirs(current_app.config['UPLOAD_FOLDER'], exist_ok=True)
        file_obj.save(os.path.join(current_app.config['UPLOAD_FOLDER'], safe_name))
        return safe_name
    return None

def send_system_email(to, subject, body, link=None):
    """Generic sender for system alerts."""
    try:
        db.session.add(MockEmail(recipient=to, subject=subject, body=body, link=link))
        db.session.commit()
    except: db.session.rollback()
    
    try:
        msg = Message(subject, recipients=[to])
        html_body = body
        if link: html_body += f"<br><br><a href='{link}'>Click here to access</a>"
        msg.html = html_body
        mail.send(msg)
    except: pass

def send_status_email(req, next_email, stage_name):
    """Workflow-specific sender."""
    if not next_email: return
    subject = f"Action Required: {stage_name} - {req.vendor_name_basic}"
    body = f"<h3>Vendor Request</h3><p><b>Vendor:</b> {req.vendor_name_basic}</p><p><b>Stage:</b> {stage_name}</p><p>Please login to review.</p>"
    send_system_email(next_email, subject, body, url_for('auth.login', _external=True))

def get_next_approver_email(req):
    """
    Determines the next email address based on the 3-Phase Pipeline.
    """
    
    # --- PHASE 1: DEPARTMENT INTERNAL ---
    if req.current_dept_flow == 'DEPT':
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
        # Map stage codes to the Role Names in the User Database
        role_map = {
            'BILL_PASSING': 'Bill Passing Team',
            'TREASURY': 'Treasury Team',
            'TAX': 'Tax Team'
        }
        
        target_username = role_map.get(req.finance_stage)
        if target_username:
            user = User.query.filter_by(username=target_username).first()
            # If user exists, return their email. If not, fallback to admin (safety net)
            return user.email if user else 'admin@heritage.com', f"Finance: {req.finance_stage.replace('_', ' ').title()}"

    # --- PHASE 3: COMMON IT EXECUTION ---
    elif req.current_dept_flow == 'IT':
        # Look up routing based on Account Group (ZDOM/ZIMP)
        route = ITRouting.query.filter_by(account_group=req.account_group).first()
        if route:
            return route.it_assignee_email, "IT: SAP Creation"
        else:
            return 'it_admin@heritage.com', "IT: Admin (Fallback)"

    return None, None