import os
import uuid
from werkzeug.utils import secure_filename
from flask import current_app, render_template
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
    try:
        db.session.add(MockEmail(recipient=to, subject=subject, body=body, link=link))
        db.session.commit()
    except Exception as e:
        print(f"Mock Email DB Error: {e}")

    try:
        msg = Message(subject, recipients=[to])
        try:
            msg.html = render_template('email_notification.html', subject=subject, body=body, link=link)
        except:
            msg.html = f"<p>{body}</p>"
        mail.send(msg)
    except Exception as e: 
        print(f"SMTP Error: {e}")

def get_current_pending_email(req):
    if req.status in ['COMPLETED', 'REJECTED', 'DRAFT']: return None
    if req.status == 'PENDING_VENDOR': return req.vendor_email

    if req.current_dept_flow == 'INITIATOR_REVIEW':
        initiator = db.session.get(User, req.initiator_id)
        return initiator.email if initiator else None

    if req.current_dept_flow == 'DEPT':
        cat_rule = CategoryRouting.query.filter_by(department=req.initiator_dept, category_name=req.vendor_type).first()
        if cat_rule:
            if req.current_step_number == 1: return cat_rule.l1_manager_email
            if req.current_step_number == 2: return cat_rule.l2_head_email
        else:
            step = WorkflowStep.query.filter_by(department=req.initiator_dept, step_order=req.current_step_number).first()
            return step.approver_email if step else None

    elif req.current_dept_flow == 'FINANCE':
        if req.finance_stage == 'BILL_PASSING': return 'bill_passing@heritage.com'
        if req.finance_stage == 'TREASURY': return 'treasury@heritage.com'
        if req.finance_stage == 'TAX': return 'tax@heritage.com'

    elif req.current_dept_flow == 'IT':
        route = ITRouting.query.filter_by(account_group=req.account_group).first()
        return route.it_assignee_email if route else 'it_admin@heritage.com'
        
    return None
