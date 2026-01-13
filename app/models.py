import json
import jwt
from datetime import datetime, timedelta
from flask import current_app
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db
from sqlalchemy.dialects.postgresql import JSON

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
        payload = {
            'user_id': self.id,
            'exp': datetime.utcnow() + timedelta(seconds=expires_sec)
        }
        return jwt.encode(payload, current_app.config['SECRET_KEY'], algorithm='HS256')

    @staticmethod
    def verify_reset_token(token):
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
    aadhaar_number = db.Column(db.String(12))
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

    # --- NEW: VERIFICATION FLAGS ---
    is_pan_verified = db.Column(db.Boolean, default=False)
    is_gst_verified = db.Column(db.Boolean, default=False)
    is_msme_verified = db.Column(db.Boolean, default=False)
    is_bank_verified = db.Column(db.Boolean, default=False)

    # --- NEW: SNAPSHOT COLUMNS (For "Teleport" Logic) ---
    previous_dept_flow = db.Column(db.String(20), nullable=True)
    previous_step_number = db.Column(db.Integer, nullable=True)
    previous_finance_stage = db.Column(db.String(20), nullable=True)
    
    # --- NEW: SECTION LOCKING ---
    editable_sections = db.Column(db.JSON, default=list)

    # Relationships
    tax_details = db.relationship('VendorTaxDetail', backref='vendor_request', lazy=True, cascade="all, delete-orphan")
    verification_logs = db.relationship('VerificationLog', backref='vendor_request', lazy='dynamic')
    
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

    def get_api_data(self, v_type):
        """
        Retrieves and parses the latest successful API response for a specific verification type.
        """
        from app.models import VerificationLog
        import json

        # 1. Fetch the latest successful verification log for this type
        log = VerificationLog.query.filter(
            VerificationLog.vendor_request_id == self.id,
            VerificationLog.verification_type == v_type.upper(),
            VerificationLog.status.in_(['SUCCESS', 'COMPLETED', 'completed'])
        ).order_by(VerificationLog.created_at.desc()).first()

        # If no log or empty response, return None
        if not log or not log.api_response:
            return None

        try:
            # 2. Parse the JSON response
            raw = log.api_response
            if isinstance(raw, str):
                raw = json.loads(raw)

            # Common keys based on your JSON structure
            result = raw.get('result', {})
            # PAN and MSME usually nest data inside 'source_output'
            source_output = result.get('source_output', {})

            # =========================================================
            # BANKING VERIFICATION
            # =========================================================
            if v_type.upper() == 'BANK':
                # Parse account existence (Handles "YES", "TRUE", 1)
                acc_exists_raw = result.get('account_exists', 'NO')
                account_exists = str(acc_exists_raw).upper() in ['YES', 'TRUE', '1', 'ACTIVE', 'VALID']

                return {
                    "status": "completed",
                    "result": {
                        "account_exists": "YES" if account_exists else "NO",
                        "name_at_bank": result.get('name_at_bank'),
                        "status": result.get('status'),          # e.g., "id_found"
                        "message": result.get('message'),        # e.g., "Bank Account Verified"
                        "utr": result.get('utr') or result.get('bank_transfer_ref_no')
                    }
                }

            # =========================================================
            # MSME / UDYAM VERIFICATION
            # =========================================================
            if v_type.upper() == 'MSME':
                # General details are nested deep in source_output
                gen = source_output.get('general_details', {})
                
                return {
                    "active": source_output.get('status') == 'id_found',
                    "name": gen.get('enterprise_name'),
                    "type": gen.get('enterprise_type'),       # e.g. "Micro"
                    "org_type": gen.get('organization_type'), # e.g. "Partnership"
                    "activity": gen.get('major_activity'),    # e.g. "Services"
                    "social_cat": gen.get('social_category'), # e.g. "General"
                    "date_inc": gen.get('date_of_inc'),       # e.g. "2017-01-20"
                    "state": gen.get('state')
                }

            # =========================================================
            # PAN VERIFICATION
            # =========================================================
            if v_type.upper() == 'PAN':
                # Input details usually contain the name used for verification
                input_details = source_output.get('input_details', {})
                
                return {
                    "pan_status": source_output.get('pan_status', 'Unknown'),
                    "aadhaar_seeded": source_output.get('aadhaar_seeding_status'), # boolean true/false
                    "name_match": source_output.get('name_match'),                 # boolean true/false
                    "verified_name": input_details.get('input_name') or source_output.get('name_on_card')
                }

            # =========================================================
            # GST VERIFICATION (Standard)
            # =========================================================
            if v_type.upper() == 'GST':
                # GST often puts data directly in source_output or result
                data = result.get('source_output', result)
                if not data: return None

                # Address formatting
                addr_obj = data.get('principal_place_of_business_fields', {}).get('principal_place_of_business_address', {})
                addr_parts = [
                    addr_obj.get('door_number'),
                    addr_obj.get('building_name'),
                    addr_obj.get('street'),
                    addr_obj.get('location'),
                    addr_obj.get('city'),
                    addr_obj.get('dst'),
                    addr_obj.get('state_name')
                ]
                # Filter None/Null values and join
                full_address = ", ".join([str(x) for x in addr_parts if x and str(x).lower() != 'null'])
                if addr_obj.get('pincode'):
                    full_address += f" - {addr_obj.get('pincode')}"

                # Activity
                activity = data.get('nature_of_business_activity', [])
                if isinstance(activity, list):
                    activity = ", ".join(activity)

                # Filing History (Last 6 entries)
                filings = data.get('filing_details', {}).get('gstr3b', [])
                history = []
                filed_count = 0
                # Sort by date descending usually helps
                try:
                    filings.sort(key=lambda x: x.get('date_of_filing', ''), reverse=True)
                except:
                    pass # Fallback if dates are missing

                for f in filings[:6]:
                    status = f.get('status', 'Unknown')
                    if status == 'Filed': filed_count += 1
                    period = str(f.get('tax_period', ''))
                    # Format period (e.g., "July 2023" -> "JUL")
                    label = period[:3].upper() if period else '?'
                    history.append({'period': label, 'status': status, 'dof': f.get('date_of_filing')})

                return {
                    'legal_name': data.get('legal_name'),
                    'trade_name': data.get('trade_name'),
                    'taxpayer_type': data.get('taxpayer_type'),
                    'gstin_status': data.get('gstin_status'),
                    'score': f"{filed_count}/6",
                    'filing_history': history,
                    'address': full_address,
                    'activity': activity
                }

        except Exception as e:
            # Helpful error logging for debugging API mismatches
            print(f"Error parsing API data for {v_type}: {e}")
            return None

        return {}
class VendorTaxDetail(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    vendor_request_id = db.Column(db.Integer, db.ForeignKey('vendor_request.id'), nullable=False)
    
    tax_category = db.Column(db.String(20), nullable=False)
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
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True) 
    
    action = db.Column(db.String(50), nullable=False) 
    details = db.Column(db.String(255)) 
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref='audit_logs')
    vendor_request = db.relationship('VendorRequest', backref='audit_logs')

class VerificationLog(db.Model):
    __tablename__ = 'verification_logs'

    id = db.Column(db.Integer, primary_key=True)
    vendor_request_id = db.Column(db.Integer, db.ForeignKey('vendor_request.id'), nullable=True)
    
    verification_type = db.Column(db.String(50), nullable=False)
    external_ref_id = db.Column(db.String(100))
    status = db.Column(db.String(20))
    
    input_payload = db.Column(db.JSON)
    api_response = db.Column(db.JSON)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<VerifyLog {self.verification_type}: {self.status}>'