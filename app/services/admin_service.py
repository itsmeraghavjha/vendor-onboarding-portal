import csv
import io
from flask import flash
from sqlalchemy import func
from app.extensions import db
from app.models import User, Department, CategoryRouting, WorkflowStep, ITRouting, VendorRequest, MasterData, VendorTaxDetail

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
    """Generates the SAP Upload CSV with specific columns and logic."""
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

            # --- ROW LOGIC ---
            name_1 = (req.vendor_name_basic or '').upper() # Repeats
            
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
                idx,            # Repeats
                account_group,
                title,
                name_1,         # Repeats
                name_2,
                street,
                street2,
                street3,
                street4,
                city,
                postal_code,
                region,
                contact,
                mob1,
                mob2,
                landline,
                email,
                gst,
                pan,
                msme_no,
                msme_type,
                ifsc,
                bank_acc,
                holder,
                gl,
                h_bank,
                pay_term,
                purch_org,
                pay_term,       
                inco,
                
                # Tax 1
                t1.get('type',''), 
                t1.get('code',''), 
                'X' if t1.get('subject')=='1' else '', 
                t1.get('recipient',''),
                t1.get('cert',''), 
                t1.get('rate',''), 
                format_sap_date(t1.get('start','')),
                format_sap_date(t1.get('end','')),
                t1.get('reason',''),
                
                # Tax 2
                t2.get('section',''), 
                t2.get('cert',''), 
                t2.get('rate',''), 
                format_sap_date(t2.get('start','')),
                format_sap_date(t2.get('end','')),
                '',
                t2.get('code',''),
                'TDSU/S194Q' if t2 else '',
                t2.get('thresh',''),
                
                "INR" # Repeats on EVERY row
            ]
            writer.writerow(row)
    
    output.seek(0)
    return output

def get_dashboard_stats():
    """Calculates all statistics for the admin dashboard."""
    return {
        'users': User.query.count(),
        'rules': CategoryRouting.query.count() + WorkflowStep.query.count() + ITRouting.query.count(),
        'masters': MasterData.query.count(),
        'total': VendorRequest.query.count(),
        'completed': VendorRequest.query.filter_by(status='COMPLETED').count(),
        'rejected': VendorRequest.query.filter_by(status='REJECTED').count(),
        'pending': VendorRequest.query.filter(VendorRequest.status.in_(['PENDING_VENDOR', 'PENDING_APPROVAL'])).count(),
        'bottlenecks': {
            'dept': VendorRequest.query.filter_by(current_dept_flow='DEPT', status='PENDING_APPROVAL').count(),
            'bill': VendorRequest.query.filter_by(finance_stage='BILL_PASSING', status='PENDING_APPROVAL').count(),
            'treasury': VendorRequest.query.filter_by(finance_stage='TREASURY', status='PENDING_APPROVAL').count(),
            'tax': VendorRequest.query.filter_by(finance_stage='TAX', status='PENDING_APPROVAL').count(),
            'it': VendorRequest.query.filter_by(current_dept_flow='IT', status='PENDING_APPROVAL').count()
        },
        'req_by_dept': {r[0]: r[1] for r in db.session.query(VendorRequest.initiator_dept, func.count(VendorRequest.id)).group_by(VendorRequest.initiator_dept).all()}
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
            cat = row_clean.get('category', '').strip().upper() or 'HOUSE_BANK'
            code = row_clean.get('code', '').strip() or row_clean.get('Code')
            label = row_clean.get('label', '').strip() or row_clean.get('Label')
            account_no = row_clean.get('Account No')
            
            if code and label:
                exists = MasterData.query.filter_by(category=cat, code=code).first()
                if not exists:
                    db.session.add(MasterData(
                        category=cat, 
                        code=code, 
                        label=label,
                        parent_code=account_no
                    ))
                    count += 1
        db.session.commit()
        flash(f"Successfully imported {count} items.", "success")
        return True
    except Exception as e:
        db.session.rollback()
        flash(f"Import Error: {str(e)}", "error")
        return False

def update_logic_email(form):
    """Updates email addresses for various workflow rules."""
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
    """Handles User and Master Data creation/deletion."""
    if 'new_user_email' in form:
        email = form['new_user_email'].strip().lower()
        if not User.query.filter_by(email=email).first():
            u = User(
                username=form['new_user_name'], 
                email=email, 
                role=form['user_role'], 
                department=form['user_dept'], 
                assigned_category=form.get('assigned_category')
            )
            u.set_password('pass123')
            db.session.add(u)
    
    elif 'delete_user_id' in form:
        u = db.session.get(User, form['delete_user_id'])
        if u: db.session.delete(u)
            
    elif 'new_master_code' in form:
        cat, code = form['master_category'], form['new_master_code']
        if not MasterData.query.filter_by(category=cat, code=code).first():
            db.session.add(MasterData(category=cat, code=code, label=form['new_master_label']))
            
    elif 'delete_master_id' in form:
        m = db.session.get(MasterData, form['delete_master_id'])
        if m: db.session.delete(m)
        
    db.session.commit()