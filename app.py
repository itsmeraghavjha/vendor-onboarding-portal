import os
import uuid
import random
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_mail import Mail, Message

app = Flask(__name__)
app.config['SECRET_KEY'] = 'heritage-foods-production-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///heritage_vendor.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# --- FILE UPLOAD ---
UPLOAD_FOLDER = os.path.join('static', 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg'}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# --- EMAIL CONFIGURATION ---
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'raghavkumar.j@heritagefoods.in' 
app.config['MAIL_PASSWORD'] = 'idne dawk mtei ugic'
app.config['MAIL_DEFAULT_SENDER'] = app.config['MAIL_USERNAME']

mail = Mail(app)
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# --- MODELS ---

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100)) # Removed unique=True so names can repeat
    email = db.Column(db.String(100), unique=True) # Email must be unique for login
    password_hash = db.Column(db.String(200)) 
    role = db.Column(db.String(50)) 
    department = db.Column(db.String(50))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    def check_password(self, password):
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

class VendorRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.String(20), unique=True)
    token = db.Column(db.String(36), default=lambda: str(uuid.uuid4()))
    status = db.Column(db.String(50), default='PENDING_VENDOR') 
    
    current_dept_flow = db.Column(db.String(50), default='INITIATOR')
    current_step_number = db.Column(db.Integer, default=0) 
    
    initiator_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    initiator_dept = db.Column(db.String(50))
    
    vendor_email = db.Column(db.String(100))
    vendor_name_basic = db.Column(db.String(100))
    vendor_type = db.Column(db.String(50)) 

    # Compliance
    structure_type = db.Column(db.String(50)) 
    cin_number = db.Column(db.String(50)) 
    msme_registered = db.Column(db.Boolean, default=False)
    msme_aadhar = db.Column(db.String(50)) 
    gst_number = db.Column(db.String(50))
    pan_number = db.Column(db.String(50))
    
    bank_name = db.Column(db.String(100))
    account_number = db.Column(db.String(50))
    ifsc_code = db.Column(db.String(20))
    
    # Documents
    doc_pan = db.Column(db.String(200))
    doc_gst = db.Column(db.String(200))
    doc_cheque = db.Column(db.String(200))

    # Checks
    check_pan_status = db.Column(db.String(20))
    check_aadhaar_link = db.Column(db.String(20))
    check_gst_active = db.Column(db.String(20))
    check_gst_type = db.Column(db.String(50))
    check_gst_filing = db.Column(db.String(20))
    check_einvoice = db.Column(db.String(20))
    check_bank_valid = db.Column(db.String(20))

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

# --- HELPERS ---

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_file(file_obj, prefix):
    if file_obj and allowed_file(file_obj.filename):
        filename = secure_filename(f"{prefix}_{uuid.uuid4().hex[:8]}_{file_obj.filename}")
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file_obj.save(file_path)
        return filename
    return None

def send_system_email(to, subject, body, link=None):
    # Log to fake inbox
    try:
        new_email = MockEmail(recipient=to, subject=subject, body=body, link=link)
        db.session.add(new_email)
        db.session.commit()
    except: pass

    # Send real email
    try:
        msg = Message(subject, recipients=[to])
        html_content = f"""
        <div style="font-family: Arial, sans-serif; padding: 20px; border: 1px solid #ddd;">
            <h2 style="color: #009C49;">Heritage Foods</h2>
            <p>{body}</p>
            {f'<p><a href="{link}" style="background-color: #009C49; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">View Action</a></p>' if link else ''}
        </div>
        """
        msg.html = html_content
        mail.send(msg)
        print(f"✅ Email sent to {to}")
    except Exception as e:
        print(f"❌ Email failed: {e}")

def run_compliance_checks(req):
    req.check_pan_status = "VALID"
    req.check_aadhaar_link = "LINKED"
    req.check_gst_active = "ACTIVE"
    req.check_gst_type = "REGULAR"
    req.check_gst_filing = "FILED" 
    req.check_einvoice = "ENABLED"
    req.check_bank_valid = "VERIFIED"
    return True

# --- HELPER: WHO HAS THE BALL? ---
def get_current_pending_email(req):
    if req.status in ['COMPLETED', 'REJECTED', 'DRAFT']: return None
    if req.status == 'PENDING_VENDOR': return req.vendor_email

    # 1. NEW: Initiator Review (The first step after vendor submits)
    if req.current_dept_flow == 'INITIATOR_REVIEW':
        initiator = User.query.get(req.initiator_id)
        return initiator.email if initiator else None

    # 2. Department Approvals (Manager, Head, CMO, etc.)
    if req.current_dept_flow == 'DEPT':
        step = WorkflowStep.query.filter_by(department=req.initiator_dept, step_order=req.current_step_number).first()
        return step.approver_email if step else None

    # 3. Accounts/Finance Processing (Universal Step for GL Codes)
    elif req.current_dept_flow == 'ACCOUNTS':
        # Hardcoded to accounts team as per your flow
        return 'accounts@heritage.com'

    # 4. IT Provisioning (Universal Step for SAP)
    elif req.current_dept_flow == 'IT':
        return 'it_admin@heritage.com'
        
    return None


# --- ROUTES ---

@app.route('/')
def index():
    if current_user.is_authenticated: return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated: return redirect(url_for('dashboard'))
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Invalid credentials.', 'error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/admin/workflow', methods=['GET', 'POST'])
@login_required
def admin_workflow():
    if current_user.role != 'admin': return "Access Denied", 403
    
    # Default active tab
    active_tab = 'users'
    
    if request.method == 'POST':
        # 1. Create Department
        if 'new_dept_name' in request.form:
            dept_name = request.form['new_dept_name'].strip()
            if dept_name and not Department.query.filter_by(name=dept_name).first():
                db.session.add(Department(name=dept_name))
                db.session.commit()
                flash(f"Department '{dept_name}' created.", "success")
            active_tab = 'departments' # Stay on Dept tab
        
        # 2. Add Workflow Step
        elif 'step_dept' in request.form:
            dept = request.form['step_dept']
            existing_count = WorkflowStep.query.filter_by(department=dept).count()
            db.session.add(WorkflowStep(
                department=dept, step_order=existing_count + 1, 
                role_label=request.form['role_label'], 
                approver_email=request.form['approver_email']
            ))
            db.session.commit()
            flash(f"Step added for {dept}", "success")
            active_tab = 'workflow' # Stay on Workflow tab

        # 3. Create User (Automatic Login Creation)
        elif 'new_user_email' in request.form:
            email = request.form['new_user_email']
            name = request.form['new_user_name']
            dept = request.form['user_dept']
            role = request.form['user_role'] 
            
            if User.query.filter_by(email=email).first():
                flash("User with this email already exists.", "error")
            else:
                new_user = User(username=name, email=email, role=role, department=dept)
                new_user.set_password('pass123') # AUTOMATIC PASSWORD
                db.session.add(new_user)
                db.session.commit()
                flash(f"User created! Login: {email} / pass123", "success")
            active_tab = 'users' # Stay on Users tab

    steps = WorkflowStep.query.order_by(WorkflowStep.department, WorkflowStep.step_order).all()
    departments = Department.query.order_by(Department.name).all()
    users = User.query.filter(User.role != 'admin').order_by(User.department).all()
    
    return render_template('admin_workflow.html', steps=steps, departments=departments, users=users, active_tab=active_tab)

@app.route('/admin/workflow/delete/<int:id>')
@login_required
def delete_step(id):
    if current_user.role != 'admin': return "Access Denied", 403
    db.session.delete(WorkflowStep.query.get(id))
    db.session.commit()
    flash("Step removed", "success")
    return redirect(url_for('admin_workflow', _anchor='workflow')) # Anchor helps keep position


# --- Add this near your other Admin routes in app.py ---

@app.route('/admin/workflow/reorder', methods=['POST'])
@login_required
def reorder_workflow():
    if current_user.role != 'admin': return jsonify({"error": "Unauthorized"}), 403
    
    data = request.get_json()
    step_ids = data.get('step_ids', [])
    
    # Loop through the IDs in the order received from frontend
    for index, step_id in enumerate(step_ids):
        step = WorkflowStep.query.get(step_id)
        if step:
            step.step_order = index + 1 # Update level (1, 2, 3...)
            
    db.session.commit()
    return jsonify({"status": "success", "message": "Workflow reordered"})

# --- DASHBOARD ROUTE (FILTERED) ---
@app.route('/dashboard')
@login_required
def dashboard():
    # Get all requests sorted by newest first
    all_reqs = VendorRequest.query.order_by(VendorRequest.created_at.desc()).all()
    my_action_items = []

    # LOGIC: Who sees what?
    
    # 1. ADMIN sees everything
    if current_user.role == 'admin':
        my_action_items = all_reqs
        
    # 2. INITIATOR sees requests they started
    elif current_user.role == 'initiator':
        my_action_items = [r for r in all_reqs if r.initiator_id == current_user.id]
        
    # 3. APPROVER sees ONLY requests waiting for THEM
    else:
        for r in all_reqs:
            pending_email = get_current_pending_email(r)
            # Case-insensitive comparison
            if pending_email and pending_email.lower() == current_user.email.lower():
                my_action_items.append(r)
            # Optional: You might want Approvers to see requests they *previously* approved (History).
            # For this strict prototype, we only show "To-Do" items.
                
    return render_template('dashboard.html', requests=my_action_items)



@app.route('/create_request', methods=['POST'])
@login_required
def create_request():
    new_req = VendorRequest(
        request_id=f"VR-{uuid.uuid4().hex[:6].upper()}",
        initiator_id=current_user.id,
        initiator_dept=current_user.department, 
        vendor_name_basic=request.form['vendor_name'],
        vendor_email=request.form['vendor_email'],
        vendor_type=request.form['vendor_type']
    )
    db.session.add(new_req)
    db.session.commit()
    link = url_for('vendor_portal', token=new_req.token, _external=True)
    send_system_email(new_req.vendor_email, "Heritage Foods: Vendor Registration", "Please complete your profile.", link)
    flash('Invite sent.', 'success')
    return redirect(url_for('dashboard'))

# --- VENDOR PORTAL (UPDATED) ---
@app.route('/vendor/<token>', methods=['GET', 'POST'])
def vendor_portal(token):
    req = VendorRequest.query.filter_by(token=token).first_or_404()
    if req.status != 'PENDING_VENDOR': return "This form is closed."
    
    if request.method == 'POST':
        # ... (Keep existing form data capture lines for structure, pan, gst, etc.) ...
        req.structure_type = request.form.get('structure_type')
        req.cin_number = request.form.get('cin_number')
        req.msme_registered = True if request.form.get('msme_registered') == 'yes' else False
        req.msme_aadhar = request.form.get('msme_aadhar')
        req.gst_number = request.form.get('gst_number')
        req.pan_number = request.form.get('pan_number')
        req.bank_name = request.form.get('bank_name')
        req.account_number = request.form.get('account_number')
        req.ifsc_code = request.form.get('ifsc_code')
        req.legal_name = request.form.get('vendor_name_basic', req.vendor_name_basic)
        
        # File uploads (Keep existing file logic)
        file_pan = request.files.get('file_pan')
        file_gst = request.files.get('file_gst')
        file_cheque = request.files.get('file_cheque')
        if file_pan: req.doc_pan = save_file(file_pan, 'PAN')
        if file_gst: req.doc_gst = save_file(file_gst, 'GST')
        if file_cheque: req.doc_cheque = save_file(file_cheque, 'CHEQUE')
        
        # Compliance Check
        run_compliance_checks(req)
        
        # --- LOGIC CHANGE HERE ---
        # Instead of going to DEPT immediately, it goes back to INITIATOR
        req.status = 'PENDING_APPROVAL'
        req.current_dept_flow = 'INITIATOR_REVIEW' 
        
        # Get Initiator Email
        initiator = User.query.get(req.initiator_id)
        send_system_email(initiator.email, "Action Required: Review Vendor Submission", 
                          f"Vendor {req.vendor_name_basic} has submitted details. Please review and approve to send to your manager.")
        
        db.session.commit()
        return "<h1>Application Submitted. The Initiator is reviewing your details.</h1>"
        
    return render_template('vendor_form.html', req=req)



@app.route('/review/<int:req_id>', methods=['GET', 'POST'])
@login_required
def review_request(req_id):
    req = VendorRequest.query.get_or_404(req_id)
    pending_email = get_current_pending_email(req)
    
    # Auth Check
    is_my_turn = (pending_email and pending_email.lower() == current_user.email.lower()) or current_user.role == 'admin'
    
    # Labels
    current_stage_label = "Processing"
    if req.current_dept_flow == 'INITIATOR_REVIEW': current_stage_label = "Initiator Review (You)"
    elif req.current_dept_flow == 'DEPT': current_stage_label = f"Department Approval ({req.initiator_dept})"
    elif req.current_dept_flow == 'ACCOUNTS': current_stage_label = "Accounts (GL Code)"
    elif req.current_dept_flow == 'IT': current_stage_label = "IT (SAP Creation)"

    if request.method == 'POST':
        if not is_my_turn:
            flash("Not authorized.", "error")
            return redirect(url_for('dashboard'))

        if request.form.get('action') == 'reject':
            req.status = 'REJECTED'
            db.session.commit()
            send_system_email(req.vendor_email, "Application Rejected", "Your application was rejected.")
            return redirect(url_for('dashboard'))

        # --- FLOW LOGIC ---

        # 1. Initiator Review -> Moves to Dept Level 1
        if req.current_dept_flow == 'INITIATOR_REVIEW':
            req.current_dept_flow = 'DEPT'
            req.current_step_number = 1
            
            # Find first approver (e.g. Marketing Head)
            step = WorkflowStep.query.filter_by(department=req.initiator_dept, step_order=1).first()
            if step:
                send_system_email(step.approver_email, "Approval Needed", f"Initiator approved {req.vendor_name_basic}. Pending your review.")
            else:
                # No Dept steps configured? Skip to Accounts.
                req.current_dept_flow = 'ACCOUNTS'
                send_system_email('accounts@heritage.com', "Action Required", "No dept workflow found. Please process GL Code.")

        # 2. Dept Flow -> Moves to Next Dept Level OR Accounts
        elif req.current_dept_flow == 'DEPT':
            next_step = WorkflowStep.query.filter_by(department=req.initiator_dept, step_order=req.current_step_number + 1).first()
            if next_step:
                req.current_step_number += 1
                send_system_email(next_step.approver_email, "Approval Needed", f"Level {next_step.step_order} Approval required.")
            else:
                # Dept Done -> Accounts
                req.current_dept_flow = 'ACCOUNTS'
                send_system_email("accounts@heritage.com", "Action Required: Accounts", "Department approved. Please assign GL Code.")

        # 3. Accounts Flow -> Moves to IT
        elif req.current_dept_flow == 'ACCOUNTS':
             if request.form.get('gl_code'): req.gl_code = request.form.get('gl_code')
             
             req.current_dept_flow = 'IT'
             send_system_email("it_admin@heritage.com", "Action Required: Create SAP ID", "Accounts verified. Ready for creation.")

        # 4. IT Flow -> Complete
        elif req.current_dept_flow == 'IT':
             req.sap_id = request.form.get('sap_id')
             req.status = 'COMPLETED'
             send_system_email(req.vendor_email, "Onboarding Complete", f"Welcome! SAP ID: {req.sap_id}")
             
             # Notify Initiator
             initiator = User.query.get(req.initiator_id)
             if initiator: send_system_email(initiator.email, "Onboarding Complete", f"{req.vendor_name_basic} is active.")

        db.session.commit()
        flash("Moved to next stage.", "success")
        return redirect(url_for('dashboard'))

    return render_template('review.html', req=req, is_my_turn=is_my_turn, current_stage_label=current_stage_label, pending_email=pending_email)



@app.route('/fake_inbox')
def fake_inbox():
    return render_template('fake_inbox.html', emails=MockEmail.query.order_by(MockEmail.timestamp.desc()).all())

@app.cli.command("seed_db")
def seed_db():
    db.drop_all() 
    db.create_all()
    
    # Departments
    db.session.add_all([Department(name='Procurement'), Department(name='Marketing'), Department(name='Finance'), Department(name='IT')])
    db.session.commit()

    # Users
    users = [
        User(username='Admin', email='admin@heritage.com', role='admin', department='IT'),
        
        # MARKETING SCENARIO
        User(username='Marketer', email='marketer@heritage.com', role='initiator', department='Marketing'),
        User(username='CMO', email='cmo@heritage.com', role='approver', department='Marketing'),

        # FINANCE SCENARIO
        User(username='Finance User', email='fin_user@heritage.com', role='initiator', department='Finance'),
        User(username='CFO', email='cfo@heritage.com', role='approver', department='Finance'),

        # IT SCENARIO
        User(username='IT User', email='it_user@heritage.com', role='initiator', department='IT'),
        User(username='IT Head', email='it_head@heritage.com', role='approver', department='IT'),

        # PROCESSING TEAMS (Universal)
        User(username='Accounts Team', email='accounts@heritage.com', role='approver', department='Finance'),
        User(username='IT Admin', email='it_admin@heritage.com', role='approver', department='IT'),
    ]
    for u in users: u.set_password('pass123')
    db.session.add_all(users)
    
    # Workflows (Departmental Levels ONLY)
    db.session.add(WorkflowStep(department='Marketing', step_order=1, role_label='CMO', approver_email='cmo@heritage.com'))
    db.session.add(WorkflowStep(department='Finance', step_order=1, role_label='CFO', approver_email='cfo@heritage.com'))
    db.session.add(WorkflowStep(department='IT', step_order=1, role_label='IT Head', approver_email='it_head@heritage.com'))
    
    db.session.commit()
    print("Database Seeded. Accounts Team: accounts@heritage.com / pass123")



if __name__ == '__main__':
    with app.app_context(): db.create_all()
    # host='0.0.0.0' makes it accessible to the network
    app.run(host='0.0.0.0', port=5000, debug=True)