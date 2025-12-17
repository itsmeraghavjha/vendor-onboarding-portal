from datetime import datetime
import uuid
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from .extensions import db, login_manager

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100)) 
    email = db.Column(db.String(100), unique=True)
    password_hash = db.Column(db.String(200)) 
    role = db.Column(db.String(50))      
    department = db.Column(db.String(50)) 
    assigned_category = db.Column(db.String(50), nullable=True) 

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    def check_password(self, password):
        if not self.password_hash: return False
        return check_password_hash(self.password_hash, password)

class Department(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True)

class WorkflowStep(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    department = db.Column(db.String(50))
    step_order = db.Column(db.Integer)
    role_label = db.Column(db.String(100))
    approver_email = db.Column(db.String(100))

class CategoryRouting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    department = db.Column(db.String(50))
    category_name = db.Column(db.String(50))
    l1_manager_email = db.Column(db.String(100))          
    l2_head_email = db.Column(db.String(100))
    __table_args__ = (db.UniqueConstraint('department', 'category_name', name='dept_cat_uc'),)

class ITRouting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    account_group = db.Column(db.String(50), unique=True) 
    it_assignee_email = db.Column(db.String(100))

class VendorRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.String(20), unique=True)
    token = db.Column(db.String(36), default=lambda: str(uuid.uuid4()))
    status = db.Column(db.String(50), default='PENDING_VENDOR') 
    
    current_dept_flow = db.Column(db.String(50), default='INITIATOR') 
    finance_stage = db.Column(db.String(50), nullable=True) 
    current_step_number = db.Column(db.Integer, default=0) 
    
    initiator_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    initiator_dept = db.Column(db.String(50))
    
    vendor_email = db.Column(db.String(100))
    vendor_name_basic = db.Column(db.String(100))
    vendor_type = db.Column(db.String(50)) 
    account_group = db.Column(db.String(50)) 

    # --- ADDRESS ---
    contact_name = db.Column(db.String(100))
    contact_number = db.Column(db.String(20))
    telephone_number = db.Column(db.String(20))
    contact_designation = db.Column(db.String(100))
    
    address_line1 = db.Column(db.String(200))
    address_city = db.Column(db.String(100))
    address_state = db.Column(db.String(100))
    address_pincode = db.Column(db.String(20))

    # --- COMMERCIAL ---
    payment_terms = db.Column(db.String(100))
    incoterms = db.Column(db.String(100))
    purchase_org = db.Column(db.String(50))

    # Form Fields
    product_services = db.Column(db.Text)
    structure_type = db.Column(db.String(50)) 
    cin_number = db.Column(db.String(50)) 
    msme_registered = db.Column(db.Boolean, default=False)
    msme_aadhar = db.Column(db.String(50)) 
    msme_type = db.Column(db.String(50))
    gst_number = db.Column(db.String(50))
    pan_number = db.Column(db.String(50))
    bank_name = db.Column(db.String(100))
    account_number = db.Column(db.String(50))
    ifsc_code = db.Column(db.String(20))
    
    doc_pan = db.Column(db.String(200))
    doc_gst = db.Column(db.String(200))
    doc_cheque = db.Column(db.String(200))
    doc_msme = db.Column(db.String(200))

    gl_code = db.Column(db.String(50))
    sap_id = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class MockEmail(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    recipient = db.Column(db.String(100))
    subject = db.Column(db.String(200))
    body = db.Column(db.Text)
    link = db.Column(db.String(300))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)


class MasterData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(50), index=True) # e.g. 'REGION', 'BANK'
    code = db.Column(db.String(50))                 # e.g. '01', 'HDFC'
    label = db.Column(db.String(255))               # e.g. 'Andhra Pradesh'
    parent_code = db.Column(db.String(50))          # For dependent dropdowns
    meta_data = db.Column(db.Text)                  # JSON string for extras (e.g. Account No)
    is_active = db.Column(db.Boolean, default=True)

    def __repr__(self):
        return f"<{self.category}: {self.code}>"
