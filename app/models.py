import json
import jwt
from datetime import datetime, timedelta
from flask import current_app
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=False, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    role = db.Column(db.String(20), nullable=False)
    department = db.Column(db.String(50))
    assigned_category = db.Column(db.String(50))
    is_active = db.Column(db.Boolean, default=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_reset_token(self, expires_sec=1800):
        """Generates a JWT token valid for 30 minutes."""
        payload = {
            'user_id': self.id,
            'exp': datetime.utcnow() + timedelta(seconds=expires_sec)
        }
        return jwt.encode(payload, current_app.config['SECRET_KEY'], algorithm='HS256')

    @staticmethod
    def verify_reset_token(token):
        """Verifies the JWT token and returns the user."""
        try:
            payload = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
            user_id = payload['user_id']
            return db.session.get(User, user_id)
        except:
            return None

class Department(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)

class MasterData(db.Model):
    __tablename__ = 'master_data'
    
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(50), index=True)
    code = db.Column(db.String(100), index=True)
    label = db.Column(db.String(255))
    parent_code = db.Column(db.String(100), index=True, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    data = db.Column(db.JSON, nullable=True) 

    def __repr__(self):
        return f"<Master {self.category}: {self.code}>"

class CategoryRouting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    department = db.Column(db.String(50), nullable=False)
    category_name = db.Column(db.String(50), nullable=False)
    l1_manager_email = db.Column(db.String(120), nullable=False)
    l2_head_email = db.Column(db.String(120), nullable=False)

class WorkflowStep(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    department = db.Column(db.String(50), nullable=False)
    step_order = db.Column(db.Integer, nullable=False)
    role_label = db.Column(db.String(50), nullable=False)
    approver_email = db.Column(db.String(120), nullable=False)

class ITRouting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    account_group = db.Column(db.String(50), nullable=False)
    it_assignee_email = db.Column(db.String(120), nullable=False)

class VendorRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.String(20), unique=True, nullable=False)
    token = db.Column(db.String(100), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='DRAFT') 
    
    # Workflow
    current_dept_flow = db.Column(db.String(20)) 
    current_step_number = db.Column(db.Integer, default=1)
    finance_stage = db.Column(db.String(20)) 
    
    # Initiator
    initiator_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    initiator_dept = db.Column(db.String(50))
    vendor_type = db.Column(db.String(50))
    
    # Basic Data
    title = db.Column(db.String(10))
    vendor_name_basic = db.Column(db.String(100))
    trade_name = db.Column(db.String(100))
    constitution = db.Column(db.String(50))
    cin_number = db.Column(db.String(21))
    contact_person_name = db.Column(db.String(100))
    contact_person_designation = db.Column(db.String(50))
    mobile_number = db.Column(db.String(15))
    mobile_number_2 = db.Column(db.String(15))
    landline_number = db.Column(db.String(15))
    vendor_email = db.Column(db.String(100))
    product_service_description = db.Column(db.Text)
    
    # Address
    street = db.Column(db.String(100))
    street_2 = db.Column(db.String(100))
    street_3 = db.Column(db.String(100))
    street_4 = db.Column(db.String(100))
    city = db.Column(db.String(50))
    state = db.Column(db.String(50)) 
    postal_code = db.Column(db.String(10))
    region_code = db.Column(db.String(10))
    
    # Compliance
    gst_registered = db.Column(db.String(5))
    gst_number = db.Column(db.String(15))
    gst_file_path = db.Column(db.String(200))
    pan_number = db.Column(db.String(10))
    aadhaar_number = db.Column(db.String(12))  # <--- ADDED THIS FIELD
    pan_file_path = db.Column(db.String(200))
    msme_registered = db.Column(db.String(5))
    msme_type = db.Column(db.String(50))
    msme_number = db.Column(db.String(50))
    msme_file_path = db.Column(db.String(200))
    
    tds_file_path = db.Column(db.String(200))
    
    # Bank
    bank_name = db.Column(db.String(100))
    bank_account_holder_name = db.Column(db.String(100))
    bank_account_no = db.Column(db.String(50))
    bank_ifsc = db.Column(db.String(20))
    bank_proof_file_path = db.Column(db.String(200))
    
    # Commercial
    payment_terms = db.Column(db.String(50))
    incoterms = db.Column(db.String(50))
    account_group = db.Column(db.String(50))
    purchase_org = db.Column(db.String(50))
    
    # Finance
    gl_account = db.Column(db.String(50))
    house_bank = db.Column(db.String(50))
    
    sap_id = db.Column(db.String(20))
    last_query = db.Column(db.Text)
    
    # Relationship
    tax_details = db.relationship('VendorTaxDetail', backref='vendor_request', lazy=True, cascade="all, delete-orphan")

    def get_tax1_rows(self):
        return [
            {
                'type': t.tax_category,
                'code': t.tax_code,
                'rate': t.rate,
                'cert': t.cert_no,
                'start': t.start_date,
                'end': t.end_date,
                'recipient': t.recipient_type,
                'reason': t.exemption_reason,
                'subject': '1' 
            }
            for t in self.tax_details if t.tax_category == 'WHT'
        ]

    def get_tax2_rows(self):
        return [
            {
                'section': t.section_code,
                'code': t.tax_code,
                'rate': t.rate,
                'cert': t.cert_no,
                'start': t.start_date,
                'end': t.end_date,
                'thresh': t.threshold,
                'type': t.tax_category
            }
            for t in self.tax_details if t.tax_category == '194Q'
        ]


class VendorTaxDetail(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    vendor_request_id = db.Column(db.Integer, db.ForeignKey('vendor_request.id'), nullable=False)
    
    tax_category = db.Column(db.String(20), nullable=False) # 'WHT' or '194Q'
    
    tax_code = db.Column(db.String(50)) 
    rate = db.Column(db.String(20))
    cert_no = db.Column(db.String(100))
    
    start_date = db.Column(db.String(20)) 
    end_date = db.Column(db.String(20))
    
    recipient_type = db.Column(db.String(20))
    exemption_reason = db.Column(db.String(100))
    
    section_code = db.Column(db.String(50))
    threshold = db.Column(db.String(50))
    
    is_active = db.Column(db.Boolean, default=True)

class MockEmail(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    recipient = db.Column(db.String(120))
    subject = db.Column(db.String(200))
    body = db.Column(db.Text)
    link = db.Column(db.String(500))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    vendor_request_id = db.Column(db.Integer, db.ForeignKey('vendor_request.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True) # Nullable for system actions
    
    action = db.Column(db.String(50), nullable=False) # e.g., 'APPROVED_TAX', 'REJECTED'
    details = db.Column(db.String(255)) # e.g., "Comments: Invalid GST No"
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref='audit_logs')
    vendor_request = db.relationship('VendorRequest', backref='audit_logs')