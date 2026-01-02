import csv
import io
from datetime import datetime
from flask import flash
from sqlalchemy import func
from app.extensions import db
from app.models import User, Department, CategoryRouting, WorkflowStep, ITRouting, VendorRequest, MasterData, VendorTaxDetail, AuditLog

def format_sap_date(date_str):
    """Converts YYYY-MM-DD to DD.MM.YYYY for SAP."""
    if not date_str: return ""
    try:
        parts = date_str.split('-')
        if len(parts) == 3:
            return f"{parts[2]}.{parts[1]}.{parts[0]}"
        return date_str
    except:
        return date_str

def generate_sap_csv(request_ids):
    """Generates the SAP Upload CSV."""
    output = io.StringIO()
    writer = csv.writer(output)

    # 1. Header
    headers = [
        "S.No", "Vendor Account Group", "Title", "Name 1 (Legal Name)", "Name 2 (Trade Name)",
        "Street", "Street2", "Street3", "Street4", "City", "Postal Code", "Region",
        "Contact Person Name", "Mobile Number 1", "Mobile Number 2", "Landline No",
        "E-Mail Address", "GST Number", "PAN Number", "MSME Number", "MSME Type",
        "IFSC Code", "Bank Account No", "Account Holder Name", "GL Account", "House Bank",
        "Payment Terms", "Purch. Org", "Payment Terms", "Inco Terms", 
        "Withholding Tax Type -1", "Withholding Tax Code -1", "Subject to w/tax", 
        "Recipient Type", "Exemption Certificate No. -1", "Exemption Rate -1", 
        "Exemption Start Date -1", "Exemption End Date -1", "Exemption Reason -1", 
        "Section Code", "Exemption Certificate No. - 2", "Exemption Rate -2", 
        "Exemption Start Date -2", "Exemption End Date -2", "Exemption Reason -2", 
        "Withholding Tax Code -2", "Withholding Tax Type -2", "Exemption thr amm", "Currency"
    ]
    writer.writerow(headers)

    requests = VendorRequest.query.filter(VendorRequest.id.in_(request_ids)).all()

    for idx, req in enumerate(requests, 1):
        t1_rows = req.get_tax1_rows()
        t2_rows = req.get_tax2_rows()
        
        max_rows = max(len(t1_rows), len(t2_rows))
        if max_rows == 0: max_rows = 1

        for i in range(max_rows):
            t1 = t1_rows[i] if i < len(t1_rows) else {}
            t2 = t2_rows[i] if i < len(t2_rows) else {}
            
            is_first = (i == 0)

            name_1 = (req.vendor_name_basic or '').upper()
            
            # Fields only on First Row
            account_group = (req.account_group or "ZDOM") if is_first else ""
            title = req.title if is_first else ""
            city = (req.city or '').upper() if is_first else ""
            
            name_2 = (req.trade_name[:35] if req.trade_name else "") if is_first else ""
            street = (req.street[:35] if req.street else "") if is_first else ""
            street2 = (req.street_2[:40] if req.street_2 else "") if is_first else ""
            street3 = (req.street_3[:40] if req.street_3 else "") if is_first else ""
            street4 = (req.street_4[:40] if req.street_4 else "") if is_first else ""
            postal_code = req.postal_code if is_first else ""
            region = req.state if is_first else ""
            
            contact = req.contact_person_name if is_first else ""
            mob1 = req.mobile_number if is_first else ""
            mob2 = req.mobile_number_2 if is_first else ""
            landline = req.landline_number if is_first else ""
            email = req.vendor_email if is_first else ""
            
            gst = (req.gst_number or "") if is_first else ""
            pan = req.pan_number if is_first else ""
            msme_no = req.msme_number if is_first else ""
            msme_type = req.msme_type if is_first else ""
            
            ifsc = req.bank_ifsc if is_first else ""
            bank_acc = req.bank_account_no if is_first else ""
            holder = (req.bank_account_holder_name[:60] if req.bank_account_holder_name else "") if is_first else ""
            
            gl = req.gl_account if is_first else ""
            h_bank = req.house_bank if is_first else ""
            pay_term = req.payment_terms if is_first else ""
            purch_org = (req.purchase_org or "1000") if is_first else ""
            inco = req.incoterms if is_first else ""

            row = [
                idx,
                account_group, title, name_1, name_2,
                street, street2, street3, street4, city, postal_code, region,
                contact, mob1, mob2, landline, email,
                gst, pan, msme_no, msme_type,
                ifsc, bank_acc, holder,
                gl, h_bank, pay_term, purch_org, pay_term, inco,
                
                t1.get('type',''), t1.get('code',''), 'X' if t1.get('subject')=='1' else '', 
                t1.get('recipient',''), t1.get('cert',''), t1.get('rate',''), 
                format_sap_date(t1.get('start','')), format_sap_date(t1.get('end','')), t1.get('reason',''),
                
                t2.get('section',''), t2.get('cert',''), t2.get('rate',''), 
                format_sap_date(t2.get('start','')), format_sap_date(t2.get('end','')), 
                '', t2.get('code',''), 'TDSU/S194Q' if t2 else '', t2.get('thresh',''),
                "INR"
            ]
            writer.writerow(row)
    
    output.seek(0)
    return output

def get_dashboard_stats():
    """Calculates operational analytics."""
    
    # 1. Basic Counts
    total_reqs = VendorRequest.query.count()
    completed = VendorRequest.query.filter_by(status='COMPLETED').count()
    rejected = VendorRequest.query.filter_by(status='REJECTED').count()
    pending = VendorRequest.query.filter(VendorRequest.status.in_(['PENDING_VENDOR', 'PENDING_APPROVAL'])).count()
    
    # 2. Pipeline Bottlenecks (Where are they stuck?)
    bottlenecks = {
        'dept': VendorRequest.query.filter(VendorRequest.status=='PENDING_APPROVAL', VendorRequest.current_dept_flow.in_(['INITIATOR_REVIEW', 'DEPT'])).count(),
        'bill': VendorRequest.query.filter_by(status='PENDING_APPROVAL', finance_stage='BILL_PASSING').count(),
        'treasury': VendorRequest.query.filter_by(status='PENDING_APPROVAL', finance_stage='TREASURY').count(),
        'tax': VendorRequest.query.filter_by(status='PENDING_APPROVAL', finance_stage='TAX').count(),
        'it': VendorRequest.query.filter_by(status='PENDING_APPROVAL', current_dept_flow='IT').count()
    }

    # 3. Cycle Time Calculation (Avg days to complete)
    completed_reqs = VendorRequest.query.filter_by(status='COMPLETED').all()
    total_days = 0
    avg_cycle_time = 0
    
    if completed_reqs:
        for r in completed_reqs:
            end_time = datetime.utcnow()
            # Try to find the exact completion log
            log = AuditLog.query.filter_by(vendor_request_id=r.id, action='COMPLETED_BY_IT').first()
            if log: end_time = log.timestamp
            
            delta = end_time - r.created_at
            total_days += delta.days
        
        avg_cycle_time = round(total_days / len(completed_reqs), 1)

    # 4. Department Volume
    dept_stats = {}
    raw_data = db.session.query(
        VendorRequest.initiator_dept, 
        func.count(VendorRequest.id)
    ).group_by(VendorRequest.initiator_dept).all()

    dept_labels = []
    dept_volumes = []
    
    for dept, count in raw_data:
        if dept:
            dept_labels.append(dept)
            dept_volumes.append(count)

    # Fallback for empty data to prevent JS errors
    if not dept_labels:
        dept_labels = ["No Data"]
        dept_volumes = [0]

    return {
        'users': User.query.count(),
        'rules': CategoryRouting.query.count() + WorkflowStep.query.count() + ITRouting.query.count(),
        'masters': MasterData.query.count(),
        'total': total_reqs,
        'completed': completed,
        'rejected': rejected,
        'pending': pending,
        'avg_cycle_time': avg_cycle_time,
        'bottlenecks': bottlenecks,
        'dept_labels': dept_labels,
        'dept_volumes': dept_volumes
    }

def handle_master_import(file):
    """Parses and imports CSV master data."""
    if not file or not file.filename.endswith('.csv'):
        flash("Please upload a valid CSV file.", "error")
        return False

    try:
        stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
        csv_input = csv.DictReader(stream)
        count = 0
        for row in csv_input:
            row_clean = {k.strip().lower(): v for k, v in row.items()}
            cat = row_clean.get('category', '').strip().upper() or 'GENERAL'
            code = row_clean.get('code', '').strip() or row_clean.get('Code')
            label = row_clean.get('label', '').strip() or row_clean.get('Label')
            
            if code and label:
                exists = MasterData.query.filter_by(category=cat, code=code).first()
                if not exists:
                    db.session.add(MasterData(category=cat, code=code, label=label))
                    count += 1
        db.session.commit()
        flash(f"Successfully imported {count} items.", "success")
        return True
    except Exception as e:
        db.session.rollback()
        flash(f"Import Error: {str(e)}", "error")
        return False

def update_logic_email(form):
    """Updates email addresses for workflow rules."""
    l_type = form.get('update_logic_type')
    r_id = form.get('rule_id')
    new_email = form.get('new_email')
    
    if l_type == 'cat_l1': 
        db.session.get(CategoryRouting, r_id).l1_manager_email = new_email
    elif l_type == 'cat_l2': 
        db.session.get(CategoryRouting, r_id).l2_head_email = new_email
    elif l_type == 'step': 
        db.session.get(WorkflowStep, r_id).approver_email = new_email
    elif l_type == 'it_route': 
        db.session.get(ITRouting, r_id).it_assignee_email = new_email
    elif l_type == 'finance_user': 
        user = db.session.get(User, r_id)
        if user: user.email = new_email
    
    db.session.commit()

def manage_logic_rules(form):
    """Handles creation and deletion of workflow rules."""
    logic_view = form.get('logic_view')

    if 'new_category_name' in form:
        cat = form['new_category_name']
        if not CategoryRouting.query.filter_by(department=logic_view, category_name=cat).first():
            db.session.add(CategoryRouting(department=logic_view, category_name=cat, l1_manager_email=form['l1_email'], l2_head_email=form['l2_email']))
    
    elif 'delete_rule_id' in form:
        db.session.delete(db.session.get(CategoryRouting, form['delete_rule_id']))
    
    elif 'new_step_role' in form:
        curr = WorkflowStep.query.filter_by(department=logic_view).count()
        db.session.add(WorkflowStep(department=logic_view, step_order=curr+1, role_label=form['new_step_role'], approver_email=form['new_step_email']))
    
    elif 'delete_step_id' in form:
        db.session.delete(db.session.get(WorkflowStep, form['delete_step_id']))
    
    elif 'new_account_group' in form:
        if not ITRouting.query.filter_by(account_group=form['new_account_group']).first():
            db.session.add(ITRouting(account_group=form['new_account_group'], it_assignee_email=form['it_email']))
    
    elif 'delete_it_id' in form:
        db.session.delete(db.session.get(ITRouting, form['delete_it_id']))
        
    db.session.commit()

def manage_users_and_masters(form):
    """Handles User and Master Data creation, editing, and deletion."""
    
    # 1. DELETE USER
    if 'delete_user_id' in form:
        u = db.session.get(User, form['delete_user_id'])
        if u: db.session.delete(u)
        
    # 2. EDIT USER (FIX: Added explicit edit handling)
    elif 'edit_user_id' in form and form['edit_user_id']:
        u = db.session.get(User, form['edit_user_id'])
        if u:
            u.username = form['new_user_name']
            u.email = form['new_user_email'].strip().lower()
            u.role = form['user_role']
            u.department = form['user_dept']
            u.assigned_category = form.get('user_category', '').strip() or None
            # Note: Password is NOT reset on edit for security/UX reasons.

    # 3. CREATE NEW USER
    elif 'new_user_email' in form:
        email = form['new_user_email'].strip().lower()
        if not User.query.filter_by(email=email).first():
            u = User(
                username=form['new_user_name'], 
                email=email, 
                role=form['user_role'], 
                department=form['user_dept'],
                assigned_category=form.get('user_category', '').strip() or None
            )
            u.set_password('pass123')
            db.session.add(u)
    
    db.session.commit()