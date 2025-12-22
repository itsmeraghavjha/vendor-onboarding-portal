import os
import uuid
from flask_mail import Message
from app.extensions import mail, db
# Removed unused import: STATUS_MESSAGES
from app.models import MockEmail, AuditLog 
from app.tasks import send_async_email
from werkzeug.utils import secure_filename
from flask import current_app



# Define allowed types explicitly
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg'}


def allowed_file(filename):
    # Uses the config list we just cleaned up
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']


def save_file(file, prefix):
    if not file or file.filename == '':
        return None

    # 1. CHECK EXTENSION
    if not allowed_file(file.filename):
        print(f"⚠️ Blocked invalid file type: {file.filename}")
        return None  # Return None instead of crashing

    try:
        # 2. SECURE FILENAME (Prevents hackers using names like "../../../system32")
        original_filename = secure_filename(file.filename)
        
        # 3. RENAME (Prevents overwriting existing files)
        ext = original_filename.rsplit('.', 1)[1].lower()
        new_filename = f"{prefix}_{uuid.uuid4().hex[:8]}.{ext}"
        
        # 4. SAVE
        path = os.path.join(current_app.config['UPLOAD_FOLDER'], new_filename)
        file.save(path)
        return new_filename

    except Exception as e:
        print(f"❌ Disk Error: {e}")
        return None


# def send_status_email(req, recipient, stage_name):
#     # This is for internal workflow emails
#     subject = f"Action Required: Vendor Request {req.request_id}"
#     body = f"""
#     Vendor: {req.vendor_name_basic}
#     Current Stage: {stage_name}
    
#     Please log in to the portal to review and approve.
#     """
#     try:
#         msg = Message(subject, recipients=[recipient], body=body)
#         mail.send(msg)
#     except Exception as e:
#         print(f"Email Error: {e}")
#         # Log to Mock Email for demo purposes if real email fails
#         db.session.add(MockEmail(recipient=recipient, subject=subject, body=body))
#         db.session.commit()

# def send_system_email(recipient, subject, html_body):
#     # This is for external vendor emails
#     try:
#         msg = Message(subject, recipients=[recipient], html=html_body)
#         mail.send(msg)
#     except Exception as e:
#         print(f"Email Error: {e}")
#         db.session.add(MockEmail(recipient=recipient, subject=subject, body=html_body))
#         db.session.commit()


def send_status_email(req, recipient, stage_name):
    """Sends internal workflow notification (Plain Text)."""
    subject = f"Action Required: Vendor Request {req.request_id}"
    body = f"""
    Vendor: {req.vendor_name_basic}
    Current Stage: {stage_name}
    
    Please log in to the portal to review and approve.
    """
    
    # --- CHANGE: Use .delay() for Async Execution ---
    # We pass is_html=False because this is a simple text email
    send_async_email.delay(subject, recipient, body, is_html=False)

# In app/utils.py

def send_system_email(recipient, subject, html_body):
    """Sends external vendor notification (HTML)."""
    import time
    print("⏱️  FLASK: Starting Async Handoff...")
    start = time.time()
    
    # This line should take 0.01 seconds
    send_async_email.delay(subject, recipient, html_body, is_html=True)
    
    end = time.time()
    print(f"✅ FLASK: Handoff Complete! Took {end - start:.4f} seconds.")


def get_next_approver_email(req):
    from app.models import CategoryRouting, WorkflowStep, ITRouting, User
    
    if req.status == 'DRAFT': return None, 'Draft'
    if req.status == 'PENDING_VENDOR': return req.vendor_email, 'Vendor Resubmission'
    if req.status == 'REJECTED': return None, 'Rejected'
    if req.status == 'COMPLETED': return None, 'Completed'

    # 1. Initiator Review
    if req.current_dept_flow == 'INITIATOR_REVIEW':
        u = db.session.get(User, req.initiator_id)
        return u.email if u else None, 'Initiator Review'
    
    # 2. Department Approval
    if req.current_dept_flow == 'DEPT':
        step = WorkflowStep.query.filter_by(department=req.initiator_dept, step_order=req.current_step_number).first()
        if step: return step.approver_email, f"Dept Approval: {step.role_label}"
        return None, 'Dept Approval'

    # 3. Finance Approval
    if req.current_dept_flow == 'FINANCE':
        if req.finance_stage == 'BILL_PASSING':
            u = User.query.filter_by(username='Bill Passing Team').first()
            return u.email if u else None, 'Finance: Bill Passing'
        if req.finance_stage == 'TREASURY':
            u = User.query.filter_by(username='Treasury Team').first()
            return u.email if u else None, 'Finance: Treasury'
        if req.finance_stage == 'TAX':
            u = User.query.filter_by(username='Tax Team').first()
            return u.email if u else None, 'Finance: Tax Team'
            
    # 4. IT Provisioning (Updated Logic)
    if req.current_dept_flow == 'IT':
        # A. Try to find a specific rule (e.g., Laptop, ZDOM)
        rule = ITRouting.query.filter_by(account_group=req.account_group).first()
        if rule: 
            return rule.it_assignee_email, 'IT: SAP Creation'
        
        # B. Fallback: Send to default IT Admin if no specific rule exists
        fallback = User.query.filter_by(username='IT Admin').first()
        if fallback: 
            return fallback.email, 'IT: SAP Creation (Default)'
        
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