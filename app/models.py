import json
import jwt
from datetime import datetime, timedelta
from flask import current_app
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    role = db.Column(db.String(20), nullable=False)
    department = db.Column(db.String(50))
    assigned_category = db.Column(db.String(50))

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
        # Use a secret key from config to sign the token
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

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Department(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)

class MasterData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(50), nullable=False)
    code = db.Column(db.String(50), nullable=False)
    label = db.Column(db.String(200), nullable=False)
    parent_code = db.Column(db.String(50)) # NEW: Links Tax Code (Child) to Tax Type (Parent)
    is_active = db.Column(db.Boolean, default=True)

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
    city = db.Column(db.String(50))
    state = db.Column(db.String(50)) 
    postal_code = db.Column(db.String(10))
    region_code = db.Column(db.String(10))
    
    # Compliance
    gst_registered = db.Column(db.String(5))
    gst_number = db.Column(db.String(15))
    gst_file_path = db.Column(db.String(200))
    pan_number = db.Column(db.String(10))
    pan_file_path = db.Column(db.String(200))
    msme_registered = db.Column(db.String(5))
    msme_type = db.Column(db.String(50))
    msme_number = db.Column(db.String(50))
    msme_file_path = db.Column(db.String(200))
    tds_exemption_number = db.Column(db.String(50))
    tds_exemption_file_path = db.Column(db.String(200))
    
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

    # --- TAX TEAM (JSON STORAGE FOR MULTI-ROW) ---
    # We store the entire table as a JSON string
    tax1_data = db.Column(db.Text) # Withholding Tax Table
    tax2_data = db.Column(db.Text) # 194Q Table
    
    sap_id = db.Column(db.String(20))
    last_query = db.Column(db.Text)

    def get_tax1_rows(self):
        try: return json.loads(self.tax1_data) if self.tax1_data else []
        except: return []

    def get_tax2_rows(self):
        try: return json.loads(self.tax2_data) if self.tax2_data else []
        except: return []

class MockEmail(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    recipient = db.Column(db.String(120))
    subject = db.Column(db.String(200))
    body = db.Column(db.Text)
    link = db.Column(db.String(500))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)