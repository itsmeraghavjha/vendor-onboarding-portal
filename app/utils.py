# import os
# import uuid
# from flask_mail import Message
# from app.extensions import mail, db
# # Removed unused import: STATUS_MESSAGES
# from app.models import MockEmail, AuditLog 
# from app.tasks import send_async_email
# from werkzeug.utils import secure_filename
# from flask import current_app



# # Define allowed types explicitly
# ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg'}


# def allowed_file(filename):
#     # Uses the config list we just cleaned up
#     return '.' in filename and \
#            filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']


# def save_file(file, prefix):
#     if not file or file.filename == '':
#         return None

#     # 1. CHECK EXTENSION
#     if not allowed_file(file.filename):
#         print(f"⚠️ Blocked invalid file type: {file.filename}")
#         return None  # Return None instead of crashing

#     try:
#         # 2. SECURE FILENAME (Prevents hackers using names like "../../../system32")
#         original_filename = secure_filename(file.filename)
        
#         # 3. RENAME (Prevents overwriting existing files)
#         ext = original_filename.rsplit('.', 1)[1].lower()
#         new_filename = f"{prefix}_{uuid.uuid4().hex[:8]}.{ext}"
        
#         # 4. SAVE
#         path = os.path.join(current_app.config['UPLOAD_FOLDER'], new_filename)
#         file.save(path)
#         return new_filename

#     except Exception as e:
#         print(f"❌ Disk Error: {e}")
#         return None


# # def send_status_email(req, recipient, stage_name):
# #     # This is for internal workflow emails
# #     subject = f"Action Required: Vendor Request {req.request_id}"
# #     body = f"""
# #     Vendor: {req.vendor_name_basic}
# #     Current Stage: {stage_name}
    
# #     Please log in to the portal to review and approve.
# #     """
# #     try:
# #         msg = Message(subject, recipients=[recipient], body=body)
# #         mail.send(msg)
# #     except Exception as e:
# #         print(f"Email Error: {e}")
# #         # Log to Mock Email for demo purposes if real email fails
# #         db.session.add(MockEmail(recipient=recipient, subject=subject, body=body))
# #         db.session.commit()

# # def send_system_email(recipient, subject, html_body):
# #     # This is for external vendor emails
# #     try:
# #         msg = Message(subject, recipients=[recipient], html=html_body)
# #         mail.send(msg)
# #     except Exception as e:
# #         print(f"Email Error: {e}")
# #         db.session.add(MockEmail(recipient=recipient, subject=subject, body=html_body))
# #         db.session.commit()


# def send_status_email(req, recipient, stage_name):
#     """Sends internal workflow notification (Plain Text)."""
#     subject = f"Action Required: Vendor Request {req.request_id}"
#     body = f"""
#     Vendor: {req.vendor_name_basic}
#     Current Stage: {stage_name}
    
#     Please log in to the portal to review and approve.
#     """
    
#     # --- CHANGE: Use .delay() for Async Execution ---
#     # We pass is_html=False because this is a simple text email
#     send_async_email.delay(subject, recipient, body, is_html=False)

# # In app/utils.py

# def send_system_email(recipient, subject, html_body):
#     """Sends external vendor notification (HTML)."""
#     import time
#     print("⏱️  FLASK: Starting Async Handoff...")
#     start = time.time()
    
#     # This line should take 0.01 seconds
#     send_async_email.delay(subject, recipient, html_body, is_html=True)
    
#     end = time.time()
#     print(f"✅ FLASK: Handoff Complete! Took {end - start:.4f} seconds.")


# def get_next_approver_email(req):
#     from app.models import CategoryRouting, WorkflowStep, ITRouting, User
    
#     if req.status == 'DRAFT': return None, 'Draft'
#     if req.status == 'PENDING_VENDOR': return req.vendor_email, 'Vendor Resubmission'
#     if req.status == 'REJECTED': return None, 'Rejected'
#     if req.status == 'COMPLETED': return None, 'Completed'

#     # 1. Initiator Review
#     if req.current_dept_flow == 'INITIATOR_REVIEW':
#         u = db.session.get(User, req.initiator_id)
#         return u.email if u else None, 'Initiator Review'
    
#     # 2. Department Approval
#     if req.current_dept_flow == 'DEPT':
#         step = WorkflowStep.query.filter_by(department=req.initiator_dept, step_order=req.current_step_number).first()
#         if step: return step.approver_email, f"Dept Approval: {step.role_label}"
#         return None, 'Dept Approval'

#     # 3. Finance Approval
#     if req.current_dept_flow == 'FINANCE':
#         if req.finance_stage == 'BILL_PASSING':
#             u = User.query.filter_by(username='Bill Passing Team').first()
#             return u.email if u else None, 'Finance: Bill Passing'
#         if req.finance_stage == 'TREASURY':
#             u = User.query.filter_by(username='Treasury Team').first()
#             return u.email if u else None, 'Finance: Treasury'
#         if req.finance_stage == 'TAX':
#             u = User.query.filter_by(username='Tax Team').first()
#             return u.email if u else None, 'Finance: Tax Team'
            
#     # 4. IT Provisioning (Updated Logic)
#     if req.current_dept_flow == 'IT':
#         # A. Try to find a specific rule (e.g., Laptop, ZDOM)
#         rule = ITRouting.query.filter_by(account_group=req.account_group).first()
#         if rule: 
#             return rule.it_assignee_email, 'IT: SAP Creation'
        
#         # B. Fallback: Send to default IT Admin if no specific rule exists
#         fallback = User.query.filter_by(username='IT Admin').first()
#         if fallback: 
#             return fallback.email, 'IT: SAP Creation (Default)'
        
#         return None, 'IT Team'
        
#     return None, 'Processing'

# def log_audit(req_id, user_id, action, details=None):
#     """Records a business action to the database."""
#     try:
#         log = AuditLog(
#             vendor_request_id=req_id,
#             user_id=user_id,
#             action=action,
#             details=details
#         )
#         db.session.add(log)
#         # Commit is usually handled by the caller, but adding here is safe 
#         # as long as caller commits transaction.
#     except Exception as e:
#         print(f"Failed to create audit log: {e}")


import os
import uuid
import time
from werkzeug.utils import secure_filename
from flask import current_app
from app.extensions import db, mail
from app.models import AuditLog, MockEmail
# Ensure you have celery set up, or remove this import and use direct mail.send if not
try:
    from app.tasks import send_async_email
    ASYNC_AVAILABLE = True
except ImportError:
    ASYNC_AVAILABLE = False

# --- SAFE MAGIC IMPORT (For File Security) ---
try:
    import magic
    MAGIC_AVAILABLE = True
except ImportError:
    MAGIC_AVAILABLE = False
    # Only print this warning once in production logs
    # print("WARNING: 'python-magic' not installed. File checks limited to extensions.")

# ---------------------------------------------------------
# 1. FILE UPLOAD UTILITIES
# ---------------------------------------------------------
def allowed_file(filename):
    """Checks extension against allowed list config."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

def save_file(file_storage, prefix='DOC'):
    """
    Saves a file with strict security checks.
    1. Validates extension.
    2. (Optional) Validates real content type using magic bytes.
    3. Renames file to UUID to prevent overwrites/attacks.
    """
    if not file_storage or file_storage.filename == '':
        return None

    filename = secure_filename(file_storage.filename)
    
    # 1. Extension Check
    if not allowed_file(filename):
        print(f"⚠️ Blocked invalid file extension: {filename}")
        return None

    # 2. Content Check (Magic Bytes) - Optional but Recommended
    if MAGIC_AVAILABLE:
        try:
            # Read header
            header = file_storage.read(2048)
            file_storage.seek(0) # Reset cursor!
            
            mime = magic.Magic(mime=True)
            real_mime = mime.from_buffer(header)
            
            # Allow generic types. Adjust this list as needed.
            # allowed_mimes = ['application/pdf', 'image/jpeg', 'image/png']
            # if real_mime not in allowed_mimes:
            #     print(f"⚠️ Blocked Mime Type: {real_mime} for {filename}")
            #     return None
        except Exception as e:
            print(f"Magic check failed: {e}")

    # 3. Rename & Save
    try:
        _, ext = os.path.splitext(filename)
        unique_name = f"{prefix}_{uuid.uuid4().hex[:8]}{ext}"
        path = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_name)
        file_storage.save(path)
        return unique_name
    except Exception as e:
        print(f"❌ Disk Error: {e}")
        return None

# ---------------------------------------------------------
# 2. EMAIL UTILITIES
# ---------------------------------------------------------
def send_status_email(req, recipient, stage_name):
    """Sends internal workflow notification (Plain Text)."""
    subject = f"Action Required: Vendor Request {req.request_id}"
    body = f"""
    Vendor: {req.vendor_name_basic}
    Current Stage: {stage_name}
    
    Please log in to the portal to review and approve.
    """
    
    if ASYNC_AVAILABLE:
        send_async_email.delay(subject, recipient, body, is_html=False)
    else:
        # Fallback if Celery is not running/installed
        from flask_mail import Message
        try:
            msg = Message(subject, recipients=[recipient], body=body)
            mail.send(msg)
        except Exception as e:
            print(f"Email Error: {e}")

def send_system_email(recipient, subject, html_body):
    """Sends external vendor notification (HTML)."""
    if ASYNC_AVAILABLE:
        send_async_email.delay(subject, recipient, html_body, is_html=True)
    else:
        # Fallback
        from flask_mail import Message
        try:
            msg = Message(subject, recipients=[recipient], html=html_body)
            mail.send(msg)
        except Exception as e:
            print(f"Email Error: {e}")

# ---------------------------------------------------------
# 3. WORKFLOW & AUDIT UTILITIES
# ---------------------------------------------------------
# def get_next_approver_email(req):
#     """Determines who should receive the next email based on workflow state."""
#     # Import inside function to avoid Circular Imports with models.py
#     from app.models import WorkflowStep, ITRouting, User
    
#     if req.status == 'DRAFT': return None, 'Draft'
#     if req.status == 'PENDING_VENDOR': return req.vendor_email, 'Vendor Resubmission'
#     if req.status == 'REJECTED': return None, 'Rejected'
#     if req.status == 'COMPLETED': return None, 'Completed'

#     # 1. Initiator Review
#     if req.current_dept_flow == 'INITIATOR_REVIEW':
#         u = db.session.get(User, req.initiator_id)
#         return (u.email if u else None), 'Initiator Review'
    
#     # 2. Department Approval
#     if req.current_dept_flow == 'DEPT':
#         step = WorkflowStep.query.filter_by(department=req.initiator_dept, step_order=req.current_step_number).first()
#         if step: 
#             return step.approver_email, f"Dept Approval: {step.role_label}"
#         return None, 'Dept Approval'

#     # 3. Finance Approval
#     if req.current_dept_flow == 'FINANCE':
#         # Hardcoded logic (Ideal: Move to DB/Config)
#         if req.finance_stage == 'BILL_PASSING':
#             u = User.query.filter_by(username='Bill Passing Team').first()
#             return (u.email if u else None), 'Finance: Bill Passing'
#         if req.finance_stage == 'TREASURY':
#             u = User.query.filter_by(username='Treasury Team').first()
#             return (u.email if u else None), 'Finance: Treasury'
#         if req.finance_stage == 'TAX':
#             u = User.query.filter_by(username='Tax Team').first()
#             return (u.email if u else None), 'Finance: Tax Team'
            
#     # 4. IT Provisioning
#     if req.current_dept_flow == 'IT':
#         # A. Try specific routing rule
#         rule = ITRouting.query.filter_by(account_group=req.account_group).first()
#         if rule: 
#             return rule.it_assignee_email, 'IT: SAP Creation'
        
#         # B. Fallback to generic IT Admin
#         fallback = User.query.filter_by(username='IT Admin').first()
#         if fallback: 
#             return fallback.email, 'IT: SAP Creation (Default)'
        
#         return None, 'IT Team'
        
#     return None, 'Processing'


def get_next_approver_email(req):
    """Determines who should receive the next email based on workflow state."""
    # ADDED: CategoryRouting to imports
    from app.models import CategoryRouting, WorkflowStep, ITRouting, User
    
    if req.status == 'DRAFT': return None, 'Draft'
    if req.status == 'PENDING_VENDOR': return req.vendor_email, 'Vendor Resubmission'
    if req.status == 'REJECTED': return None, 'Rejected'
    if req.status == 'COMPLETED': return None, 'Completed'

    # 1. Initiator Review
    if req.current_dept_flow == 'INITIATOR_REVIEW':
        u = db.session.get(User, req.initiator_id)
        return (u.email if u else None), 'Initiator Review'
    
    # 2. Department Approval (Hybrid Logic)
    if req.current_dept_flow == 'DEPT':
        # A. Check for Category Specific Routing (The Matrix)
        cat_rule = CategoryRouting.query.filter_by(
            department=req.initiator_dept, 
            category_name=req.vendor_type
        ).first()

        if cat_rule:
            # --- MATRIX PATH ---
            if req.current_step_number == 1:
                return cat_rule.l1_manager_email, f"Category Approval (L1): {req.vendor_type}"
            elif req.current_step_number == 2:
                return cat_rule.l2_head_email, f"Category Approval (L2): {req.vendor_type}"
        
        # B. Fallback to Generic Workflow Steps (Standard Path)
        # This runs if vendor_type is 'Standard' OR if no matrix rule exists for selected category
        step = WorkflowStep.query.filter_by(department=req.initiator_dept, step_order=req.current_step_number).first()
        if step: 
            return step.approver_email, f"Dept Approval: {step.role_label}"
        
        return None, 'Dept Approval'

    # 3. Finance Approval
    if req.current_dept_flow == 'FINANCE':
        # Hardcoded logic (Ideal: Move to DB/Config)
        if req.finance_stage == 'BILL_PASSING':
            u = User.query.filter_by(username='Bill Passing Team').first()
            return (u.email if u else None), 'Finance: Bill Passing'
        if req.finance_stage == 'TREASURY':
            u = User.query.filter_by(username='Treasury Team').first()
            return (u.email if u else None), 'Finance: Treasury'
        if req.finance_stage == 'TAX':
            u = User.query.filter_by(username='Tax Team').first()
            return (u.email if u else None), 'Finance: Tax Team'
            
    # 4. IT Provisioning
    if req.current_dept_flow == 'IT':
        # A. Try specific routing rule
        rule = ITRouting.query.filter_by(account_group=req.account_group).first()
        if rule: 
            return rule.it_assignee_email, 'IT: SAP Creation'
        
        # B. Fallback to generic IT Admin
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
        db.session.commit()
    except Exception as e:
        print(f"Failed to create audit log: {e}")
        db.session.rollback()