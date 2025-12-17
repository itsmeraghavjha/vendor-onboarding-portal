import os

# Define the file contents
files = {}

# 1. config.py
files['config.py'] = """import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'heritage-foods-production-key'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Uploads
    UPLOAD_FOLDER = os.path.join(os.getcwd(), 'app', 'static', 'uploads')
    ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg'}

    # Mail Config
    MAIL_SERVER = 'smtp.gmail.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = 'raghavkumar.j@heritagefoods.in'
    MAIL_PASSWORD = 'idne dawk mtei ugic' 
    MAIL_DEFAULT_SENDER = MAIL_USERNAME

class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(os.getcwd(), 'instance', 'heritage_vendor.db')

class ProductionConfig(Config):
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
"""

# 2. app/extensions.py
files[os.path.join('app', 'extensions.py')] = """from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_mail import Mail

db = SQLAlchemy()
mail = Mail()
login_manager = LoginManager()

login_manager.login_view = 'auth.login'
login_manager.login_message_category = 'error'
"""

# 3. app/models.py
files[os.path.join('app', 'models.py')] = """from datetime import datetime
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
"""

# 4. app/utils.py
files[os.path.join('app', 'utils.py')] = """import os
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
"""

# 5. app/blueprints/auth.py
files[os.path.join('app', 'blueprints', 'auth.py')] = """from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, current_user
from app.models import User

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated: return redirect(url_for('main.dashboard'))
    if request.method == 'POST':
        email_in = request.form.get('email').strip().lower()
        user = User.query.filter_by(email=email_in).first()
        if user and user.check_password(request.form.get('password')):
            login_user(user)
            return redirect(url_for('main.dashboard'))
        flash('Invalid credentials.', 'error')
    return render_template('login.html')

@auth_bp.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('auth.login'))
"""

# 6. app/blueprints/vendor.py
files[os.path.join('app', 'blueprints', 'vendor.py')] = """from flask import Blueprint, render_template, request, url_for
from app.models import VendorRequest, User
from app.extensions import db
from app.utils import save_file, send_system_email

vendor_bp = Blueprint('vendor', __name__)

@vendor_bp.route('/vendor/<token>', methods=['GET', 'POST'])
def vendor_portal(token):
    req = VendorRequest.query.filter_by(token=token).first_or_404()
    
    if req.status != 'PENDING_VENDOR': 
        return render_template('success.html', req=req)
    
    if request.method == 'POST':
        req.vendor_name_basic = request.form.get('vendor_name_basic')
        req.address_line1 = request.form.get('address_line1')
        req.address_city = request.form.get('address_city')
        req.address_state = request.form.get('address_state')
        req.address_pincode = request.form.get('address_pincode')
        req.telephone_number = request.form.get('telephone_number')
        
        req.gst_number = request.form.get('gst_number')
        req.pan_number = request.form.get('pan_number')
        req.contact_name = request.form.get('contact_name')
        req.contact_number = request.form.get('contact_number')
        req.contact_designation = request.form.get('contact_designation')
        req.product_services = request.form.get('product_services')
        req.structure_type = request.form.get('structure_type')
        req.cin_number = request.form.get('cin_number')
        
        req.msme_registered = True if request.form.get('msme_registered') == 'yes' else False
        if req.msme_registered:
            req.msme_aadhar = request.form.get('msme_aadhar')
            req.msme_type = request.form.get('msme_type')
            
        req.bank_name = request.form.get('bank_name')
        req.account_number = request.form.get('account_number')
        req.ifsc_code = request.form.get('ifsc_code')

        file_gst = request.files.get('file_gst')
        file_pan = request.files.get('file_pan')
        file_cheque = request.files.get('file_cheque')
        file_msme = request.files.get('file_msme')

        if file_gst: req.doc_gst = save_file(file_gst, 'GST')
        if file_pan: req.doc_pan = save_file(file_pan, 'PAN')
        if file_cheque: req.doc_cheque = save_file(file_cheque, 'CHEQUE')
        if file_msme: req.doc_msme = save_file(file_msme, 'MSME')
        
        req.status = 'PENDING_APPROVAL'
        req.current_dept_flow = 'INITIATOR_REVIEW'
        
        initiator = db.session.get(User, req.initiator_id)
        if initiator: 
            send_system_email(initiator.email, "Review Vendor", f"Vendor {req.vendor_name_basic} has submitted details.")
        
        db.session.commit()
        return render_template('success.html', req=req)

    return render_template('vendor_form.html', req=req)
"""

# 7. app/blueprints/admin.py
files[os.path.join('app', 'blueprints', 'admin.py')] = """from flask import Blueprint, render_template, request
from flask_login import login_required, current_user
from app.models import User, Department, CategoryRouting, WorkflowStep, ITRouting, VendorRequest
from app.extensions import db

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/workflow', methods=['GET', 'POST'])
@login_required
def admin_workflow():
    if current_user.role != 'admin': return "Access Denied", 403
    active_tab = request.form.get('active_tab', 'users')
    
    if request.method == 'POST':
        if 'new_user_email' in request.form:
            email = request.form['new_user_email'].strip().lower()
            if not User.query.filter_by(email=email).first():
                u = User(username=request.form['new_user_name'], email=email, role=request.form['user_role'], department=request.form['user_dept'], assigned_category=request.form.get('assigned_category'))
                u.set_password('pass123')
                db.session.add(u)
                db.session.commit()
            active_tab = 'users'
        elif 'delete_user_id' in request.form:
            db.session.delete(db.session.get(User, request.form['delete_user_id']))
            db.session.commit()
            active_tab = 'users'
        elif 'new_category_name' in request.form:
            cat = request.form['new_category_name']
            dept = request.form['target_dept']
            if not CategoryRouting.query.filter_by(department=dept, category_name=cat).first():
                db.session.add(CategoryRouting(department=dept, category_name=cat, l1_manager_email=request.form['l1_email'], l2_head_email=request.form['l2_email']))
                db.session.commit()
            active_tab = 'logic'
        elif 'delete_rule_id' in request.form:
            db.session.delete(db.session.get(CategoryRouting, request.form['delete_rule_id']))
            db.session.commit()
            active_tab = 'logic'
        elif 'standard_dept' in request.form:
            dept = request.form['standard_dept']
            current_steps = WorkflowStep.query.filter_by(department=dept).count()
            db.session.add(WorkflowStep(department=dept, step_order=current_steps + 1, role_label=request.form['standard_role'], approver_email=request.form['standard_email']))
            db.session.commit()
            active_tab = 'logic'
        elif 'delete_step_id' in request.form:
            db.session.delete(db.session.get(WorkflowStep, request.form['delete_step_id']))
            db.session.commit()
            active_tab = 'logic'
        elif 'new_account_group' in request.form:
            grp = request.form['new_account_group']
            if not ITRouting.query.filter_by(account_group=grp).first():
                db.session.add(ITRouting(account_group=grp, it_assignee_email=request.form['it_email']))
                db.session.commit()
            active_tab = 'logic'
        elif 'delete_it_id' in request.form:
            db.session.delete(db.session.get(ITRouting, request.form['delete_it_id']))
            db.session.commit()
            active_tab = 'logic'

    users = User.query.filter(User.role != 'admin').order_by(User.department).all()
    departments = Department.query.all()
    category_rules = CategoryRouting.query.order_by(CategoryRouting.department).all()
    standard_steps = WorkflowStep.query.order_by(WorkflowStep.department, WorkflowStep.step_order).all()
    it_routes = ITRouting.query.all()
    stats = {'users': User.query.count(), 'requests': VendorRequest.query.count(), 'rules': len(category_rules)+len(standard_steps)+len(it_routes)}

    return render_template('admin_workflow.html', users=users, departments=departments, category_rules=category_rules, standard_steps=standard_steps, it_routes=it_routes, stats=stats, activeTab=active_tab)

@admin_bp.route('/nuke-and-reset')
def nuke_and_reset():
    db.drop_all()
    db.create_all()
    
    db.session.add_all([Department(name='Purchase'), Department(name='Procurement'), Department(name='Marketing'), Department(name='Finance'), Department(name='IT')])

    materials = ["Capital Materials", "HDC & Marketing", "Spares & Others", "AMC & Service", "Raw Materials", "Packing Materials"]
    for m in materials:
        slug = m.split()[0].lower().replace('&', '').replace(' ', '')
        db.session.add(CategoryRouting(department='Purchase', category_name=m, l1_manager_email=f"{slug}_l1@heritage.com", l2_head_email=f"{slug}_head@heritage.com"))
        u1 = User(username=f"{m} L1", email=f"{slug}_l1@heritage.com", role='approver', department='Purchase')
        u1.set_password('pass123')
        db.session.add(u1)
        u2 = User(username=f"{m} Head", email=f"{slug}_head@heritage.com", role='approver', department='Purchase')
        u2.set_password('pass123')
        db.session.add(u2)

    db.session.add(ITRouting(account_group='ZDOM', it_assignee_email='it_domestic@heritage.com'))
    db.session.add(ITRouting(account_group='ZIMP', it_assignee_email='it_import@heritage.com'))
    
    db.session.add(WorkflowStep(department='Procurement', step_order=1, role_label='Procurement Head', approver_email='proc_head@heritage.com'))

    u_cap = User(username='Capital Init', email='capital_init@heritage.com', role='initiator', department='Purchase', assigned_category='Capital Materials')
    u_cap.set_password('pass123')
    db.session.add(u_cap)

    approvers = [
        ('Admin', 'admin@heritage.com', 'admin', 'IT'),
        ('Bill Passing', 'bill_passing@heritage.com', 'approver', 'Finance'),
        ('Treasury', 'treasury@heritage.com', 'approver', 'Finance'),
        ('Tax Team', 'tax@heritage.com', 'approver', 'Finance'),
        ('IT Domestic', 'it_domestic@heritage.com', 'approver', 'IT'),
        ('IT Import', 'it_import@heritage.com', 'approver', 'IT'),
    ]
    for name, email, role, dept in approvers:
        u = User(username=name, email=email, role=role, department=dept)
        u.set_password('pass123')
        db.session.add(u)
    
    db.session.commit()
    return "Reset Complete. <a href='/login'>Login</a>"
"""

# 8. app/blueprints/main.py
files[os.path.join('app', 'blueprints', 'main.py')] = """import uuid
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.models import VendorRequest, CategoryRouting, WorkflowStep, MockEmail
from app.extensions import db
from app.utils import send_system_email, get_current_pending_email

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index(): 
    return redirect(url_for('auth.login'))

@main_bp.route('/dashboard')
@login_required
def dashboard():
    all_reqs = VendorRequest.query.order_by(VendorRequest.created_at.desc()).all()
    dept_categories = []
    if current_user.role == 'initiator':
        rules = CategoryRouting.query.filter_by(department=current_user.department).all()
        dept_categories = [r.category_name for r in rules]

    my_items = []
    if current_user.role == 'admin': my_items = all_reqs
    elif current_user.role == 'initiator':
        my_items = [r for r in all_reqs if r.initiator_id == current_user.id]
    else:
        for r in all_reqs:
            pending = get_current_pending_email(r)
            if pending and current_user.email and pending.strip().lower() == current_user.email.strip().lower():
                my_items.append(r)
                
    return render_template('dashboard.html', requests=my_items, dept_categories=dept_categories)

@main_bp.route('/create_request', methods=['POST'])
@login_required
def create_request():
    vendor_type = request.form['vendor_type']
    if current_user.assigned_category:
        vendor_type = current_user.assigned_category
    
    new_req = VendorRequest(
        request_id=f"VR-{uuid.uuid4().hex[:6].upper()}",
        initiator_id=current_user.id,
        initiator_dept=current_user.department, 
        vendor_name_basic=request.form['vendor_name'],
        vendor_email=request.form['vendor_email'],
        vendor_type=vendor_type,
        account_group=request.form.get('account_group', 'ZDOM') 
    )
    db.session.add(new_req)
    db.session.commit()
    
    link = url_for('vendor.vendor_portal', token=new_req.token, _external=True)
    send_system_email(new_req.vendor_email, "Vendor Onboarding Invite", "Please fill your details.", link)
    flash('Invite sent.', 'success')
    return redirect(url_for('main.dashboard'))

@main_bp.route('/review/<int:req_id>', methods=['GET', 'POST'])
@login_required
def review_request(req_id):
    req = db.session.get(VendorRequest, req_id)
    if not req: return "Not Found", 404

    pending_email = get_current_pending_email(req)
    
    is_my_turn = False
    if pending_email and current_user.email:
         if pending_email.strip().lower() == current_user.email.strip().lower():
             is_my_turn = True
    if current_user.role == 'admin': is_my_turn = True

    if request.method == 'POST':
        if not is_my_turn: return "Unauthorized", 403

        if request.form.get('action') == 'reject':
            req.status = 'REJECTED'
            db.session.commit()
            return redirect(url_for('main.dashboard'))

        if request.form.get('payment_terms'): req.payment_terms = request.form.get('payment_terms')
        if request.form.get('incoterms'): req.incoterms = request.form.get('incoterms')
        if request.form.get('purchase_org'): req.purchase_org = request.form.get('purchase_org')

        if req.current_dept_flow == 'INITIATOR_REVIEW':
            req.current_dept_flow = 'DEPT'
            req.current_step_number = 1 
            if request.form.get('account_group'): req.account_group = request.form.get('account_group')

        elif req.current_dept_flow == 'DEPT':
            cat_rule = CategoryRouting.query.filter_by(department=req.initiator_dept, category_name=req.vendor_type).first()
            if cat_rule:
                if req.current_step_number == 1: req.current_step_number = 2
                else:
                    req.current_dept_flow = 'FINANCE'
                    req.finance_stage = 'BILL_PASSING'
            else:
                next_step = WorkflowStep.query.filter_by(department=req.initiator_dept, step_order=req.current_step_number + 1).first()
                if next_step: req.current_step_number += 1
                else:
                    req.current_dept_flow = 'FINANCE'
                    req.finance_stage = 'BILL_PASSING'

        elif req.current_dept_flow == 'FINANCE':
            if req.finance_stage == 'BILL_PASSING': req.finance_stage = 'TREASURY'
            elif req.finance_stage == 'TREASURY': req.finance_stage = 'TAX'
            elif req.finance_stage == 'TAX':
                if request.form.get('account_group'): req.account_group = request.form.get('account_group')
                req.current_dept_flow = 'IT'
                req.finance_stage = None 

        elif req.current_dept_flow == 'IT':
            req.sap_id = request.form.get('sap_id')
            req.status = 'COMPLETED'

        db.session.commit()
        
        next_approver = get_current_pending_email(req)
        if next_approver:
            send_system_email(next_approver, "Action Required", f"Request {req.request_id} is waiting for your approval.")
        elif req.status == 'COMPLETED':
            send_system_email(req.vendor_email, "Onboarding Complete", f"Welcome! SAP ID: {req.sap_id}")

        flash("Approved.", "success")
        return redirect(url_for('main.dashboard'))

    return render_template('review.html', req=req, pending_email=pending_email, is_my_turn=is_my_turn)

@main_bp.route('/fake_inbox')
def fake_inbox():
    return render_template('fake_inbox.html', emails=MockEmail.query.order_by(MockEmail.timestamp.desc()).all())
"""

# 9. app/__init__.py
files[os.path.join('app', '__init__.py')] = """from flask import Flask
from config import DevelopmentConfig
from .extensions import db, login_manager, mail

def create_app(config_class=DevelopmentConfig):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)

    from .blueprints.auth import auth_bp
    from .blueprints.main import main_bp
    from .blueprints.admin import admin_bp
    from .blueprints.vendor import vendor_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(vendor_bp)

    with app.app_context():
        db.create_all()

    return app
"""

# 10. run.py
files['run.py'] = """from app import create_app

app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
"""

# Write files
for path, content in files.items():
    try:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Successfully wrote: {path}")
    except Exception as e:
        print(f"Error writing {path}: {e}")

print("\\nDONE! You can now run 'python run.py'")