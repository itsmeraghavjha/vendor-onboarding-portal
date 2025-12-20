import os
import uuid
from flask_mail import Message
from app.extensions import mail, db
# Removed unused import: STATUS_MESSAGES
from app.models import MockEmail, AuditLog 

def save_file(file, prefix):
    if not file: return None
    ext = file.filename.split('.')[-1]
    filename = f"{prefix}_{uuid.uuid4().hex[:8]}.{ext}"
    path = os.path.join('app/static/uploads', filename)
    file.save(path)
    return filename

def send_status_email(req, recipient, stage_name):
    # This is for internal workflow emails
    subject = f"Action Required: Vendor Request {req.request_id}"
    body = f"""
    Vendor: {req.vendor_name_basic}
    Current Stage: {stage_name}
    
    Please log in to the portal to review and approve.
    """
    try:
        msg = Message(subject, recipients=[recipient], body=body)
        mail.send(msg)
    except Exception as e:
        print(f"Email Error: {e}")
        # Log to Mock Email for demo purposes if real email fails
        db.session.add(MockEmail(recipient=recipient, subject=subject, body=body))
        db.session.commit()

def send_system_email(recipient, subject, html_body):
    # This is for external vendor emails
    try:
        msg = Message(subject, recipients=[recipient], html=html_body)
        mail.send(msg)
    except Exception as e:
        print(f"Email Error: {e}")
        db.session.add(MockEmail(recipient=recipient, subject=subject, body=html_body))
        db.session.commit()

def get_next_approver_email(req):
    from app.models import CategoryRouting, WorkflowStep, ITRouting, User
    
    if req.status == 'DRAFT': return None, 'Draft'
    if req.status == 'PENDING_VENDOR': return req.vendor_email, 'Vendor Resubmission'
    if req.status == 'REJECTED': return None, 'Rejected'
    if req.status == 'COMPLETED': return None, 'Completed'

    if req.current_dept_flow == 'INITIATOR_REVIEW':
        u = db.session.get(User, req.initiator_id)
        return u.email if u else None, 'Initiator Review'
    
    if req.current_dept_flow == 'DEPT':
        # Check specific steps first
        step = WorkflowStep.query.filter_by(department=req.initiator_dept, step_order=req.current_step_number).first()
        if step: return step.approver_email, f"Dept Approval: {step.role_label}"
        
        # Fallback to Category Managers if steps not defined
        return None, 'Dept Approval'

    if req.current_dept_flow == 'FINANCE':
        if req.finance_stage == 'BILL_PASSING':
            # Hardcoded or look up user with role/dept
            u = User.query.filter_by(username='Bill Passing Team').first()
            return u.email if u else None, 'Finance: Bill Passing'
        if req.finance_stage == 'TREASURY':
            u = User.query.filter_by(username='Treasury Team').first()
            return u.email if u else None, 'Finance: Treasury'
        if req.finance_stage == 'TAX':
            u = User.query.filter_by(username='Tax Team').first()
            return u.email if u else None, 'Finance: Tax Team'
            
    if req.current_dept_flow == 'IT':
        rule = ITRouting.query.filter_by(account_group=req.account_group).first()
        if rule: return rule.it_assignee_email, 'IT: SAP Creation'
        return None, 'IT Team'
        
    return None, 'Processing'

def log_audit(req_id, user_id, action, details=None):
    """Records a business action to the database."""
    try:
        log = AuditLog(
            vendor_request_id=req_id,
            user_id=user_id,
            action=action,
            details=details
        )
        db.session.add(log)
        # Commit is usually handled by the caller, but adding here is safe 
        # as long as caller commits transaction.
    except Exception as e:
        print(f"Failed to create audit log: {e}")