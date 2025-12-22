import json
import csv
import io
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, Response, stream_with_context
from flask_login import login_required, current_user
from app.models import User, Department, CategoryRouting, WorkflowStep, ITRouting, MasterData, VendorRequest
from app.extensions import db
from app.services import admin_service

admin_bp = Blueprint('admin', __name__)

# --- Drag & Drop API Endpoint ---
@admin_bp.route('/reorder_steps', methods=['POST'])
@login_required
def reorder_steps():
    if current_user.role != 'admin': return jsonify({'error': 'Unauthorized'}), 403
    data = request.get_json()
    try:
        for index, step_id in enumerate(data.get('step_ids', [])):
            step = db.session.get(WorkflowStep, step_id)
            if step: step.step_order = index + 1
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

# --- UPDATED: SAP EXPORT (Aligned with models.py) ---
@admin_bp.route('/export/sap')
@login_required
def export_sap_data():
    if current_user.role != 'admin': return "Access Denied", 403
    
    # 1. SAP FIELD LIMITS
    FIELD_LIMITS = {
        'Vendor Account Group': 4, 'Title': 15, 'Name 1 (Legal Name)': 35, 'Name 2 (Trade Name)': 35,
        'Street': 35, 'Street2': 40, 'Street3': 40, 'Street4': 40,
        'City': 40, 'Postal Code': 10, 'Region': 3, 'Country': 3,
        'Mobile Number 1': 16, 'Mobile Number 2': 16, 'Landline No': 31, 'E-Mail Address': 240,
        'Category': 3, 'GST Number': 60, 'PAN Number': 40, 'MSME Number': 40, 'MSME Type': 4,
        'IFSC Code': 15, 'Bank Account No': 18, 'Account Holder Name': 60,
        'Company Code': 4, 'GL Account': 10, 'Sort Key': 3, 'Planning Group': 10,
        'Wtax C/R Key': 3, 'House Bank': 5, 'Payment Terms': 4, 'Inco Terms': 3,
        'Incoterms Location 1': 70
    }

    # 2. FILTER SELECTION
    start_str = request.args.get('start_date')
    end_str = request.args.get('end_date')
    
    # STRICT FILTER: Only 'COMPLETED' requests
    query = VendorRequest.query.filter(VendorRequest.status == 'COMPLETED')

    if start_str:
        try: query = query.filter(VendorRequest.created_at >= datetime.strptime(start_str, '%Y-%m-%d'))
        except: pass
    if end_str:
        try: query = query.filter(VendorRequest.created_at <= datetime.strptime(end_str, '%Y-%m-%d').replace(hour=23, minute=59))
        except: pass

    def generate():
        headers = [
            'S.No', 'Vendor Account Group', 'Title', 'Name 1 (Legal Name)', 'Name 2 (Trade Name)',
            'Street', 'Street2', 'Street3', 'Street4', 'City', 'Postal Code', 'Region',
            'Contact Person Name', 'Mobile Number 1', 'Mobile Number 2', 'Landline No',
            'E-Mail Address', 'GST Number', 'PAN Number', 'MSME Number', 'MSME Type',
            'IFSC Code', 'Bank Account No', 'Account Holder Name', 'GL Account', 'House Bank',
            'Payment Terms', 'Purch. Org', 'Payment Terms', 'Inco Terms', 
            'Withholding Tax Type -1', 'Withholding Tax Code -1', 'Subject to w/tax', 
            'Recipient Type', 'Exemption Certificate No. -1', 'Exemption Rate -1', 
            'Exemption Start Date -1', 'Exemption End Date -1', 'Exemption Reason -1', 
            'Section Code', 'Withholding Tax Code -2', 'Withholding Tax Type -2', 
            'Exemption thr amm', 'Currency'
        ]
        
        data = io.StringIO()
        writer = csv.writer(data)
        writer.writerow(headers)
        yield data.getvalue()
        data.seek(0); data.truncate(0)

        # Helper to truncate fields
        def get_val(header, val):
            val = str(val or '').strip()
            limit = FIELD_LIMITS.get(header)
            if limit and len(val) > limit: return val[:limit]
            return val

        # 3. DATA MAPPING (Aligned with models.py)
        for idx, req in enumerate(query.all(), 1):
            
            # Extract Tax Details (WHT)
            tax_rows = req.get_tax1_rows()
            wht_type_1 = tax_rows[0]['type'] if tax_rows else ''
            wht_code_1 = tax_rows[0]['code'] if tax_rows else ''

            row_map = {
                'S.No': idx,
                'Vendor Account Group': get_val('Vendor Account Group', req.account_group), 
                'Title': get_val('Title', req.title),
                'Name 1 (Legal Name)': get_val('Name 1 (Legal Name)', req.vendor_name_basic),
                'Name 2 (Trade Name)': get_val('Name 2 (Trade Name)', req.trade_name),
                
                # Corrected Address Fields
                'Street': get_val('Street', req.street),
                'Street2': get_val('Street2', req.street_2),
                'Street3': get_val('Street3', req.street_3),
                'Street4': get_val('Street4', req.street_4),
                'City': get_val('City', req.city),
                'Postal Code': get_val('Postal Code', req.postal_code), # Was pincode
                'Region': get_val('Region', req.region_code),           # Was state
                
                # Corrected Contact Fields
                'Contact Person Name': req.contact_person_name,         # Was contact_name
                'Mobile Number 1': get_val('Mobile Number 1', req.mobile_number), # Was mobile_1
                'Mobile Number 2': get_val('Mobile Number 2', req.mobile_number_2),
                'Landline No': get_val('Landline No', req.landline_number), # Was landline
                'E-Mail Address': get_val('E-Mail Address', req.vendor_email),
                
                # Corrected Compliance Fields
                'GST Number': get_val('GST Number', req.gst_number),    # Was gst_no
                'PAN Number': get_val('PAN Number', req.pan_number),    # Was pan_no
                'MSME Number': get_val('MSME Number', req.msme_number),
                'MSME Type': get_val('MSME Type', req.msme_type),
                
                # Corrected Bank Fields
                'IFSC Code': get_val('IFSC Code', req.bank_ifsc),       # Was ifsc
                'Bank Account No': get_val('Bank Account No', req.bank_account_no), # Was acc_no
                'Account Holder Name': get_val('Account Holder Name', req.bank_account_holder_name), # Was holder_name
                
                # Commercial / SAP Data
                'GL Account': get_val('GL Account', req.gl_account),
                'House Bank': get_val('House Bank', req.house_bank),
                'Payment Terms': get_val('Payment Terms', req.payment_terms),
                'Purch. Org': get_val('Purch. Org', req.purchase_org),  # Was purch_org
                'Inco Terms': get_val('Inco Terms', req.incoterms),     # Was inco_terms
                
                # Tax Data
                'Withholding Tax Type -1': wht_type_1,
                'Withholding Tax Code -1': wht_code_1,
                'Subject to w/tax': 'X' if wht_type_1 else '',
                'Recipient Type': 'CO' if req.constitution and 'Company' in req.constitution else 'OT',
                'Currency': 'INR'
            }
            writer.writerow([row_map.get(h, '') for h in headers])
            yield data.getvalue()
            data.seek(0); data.truncate(0)

    filename = f"SAP_Export_APPROVED_{datetime.now().strftime('%Y%m%d')}.csv"
    return Response(stream_with_context(generate()), mimetype="text/csv", 
                    headers={"Content-disposition": f"attachment; filename={filename}"})

# --- WORKFLOW PAGE ---
# --- WORKFLOW PAGE ---
@admin_bp.route('/workflow', methods=['GET', 'POST'])
@login_required
def admin_workflow():
    if current_user.role != 'admin': return "Access Denied", 403
    
    active_tab = request.args.get('active_tab', 'dashboard')
    selected_dept = request.args.get('selected_dept', 'Purchase')
    
    # 1. Master Data Config
    MASTER_TITLES = {
        'region': 'Regions', 'payment-terms': 'Payment Terms', 'inco-terms': 'Inco Terms',
        'msme-type': 'MSME Types', 'account-group': 'Account Groups', 'gl-list': 'GL Accounts',
        'house-bank': 'House Banks', 'purch-org': 'Purchase Orgs', 'tds-types': 'Tax Types',
        'tds-codes': 'TDS Codes', 'exemption-reason': 'Exemption Reasons'
    }
    SLUG_TO_DB = {
        'region': 'REGION', 'payment-terms': 'PAYMENT_TERM', 'inco-terms': 'INCOTERM',
        'msme-type': 'MSME_TYPE', 'account-group': 'ACCOUNT_GROUP', 'gl-list': 'GL_ACCOUNT',
        'house-bank': 'HOUSE_BANK', 'purch-org': 'PURCHASE_ORG', 'tds-types': 'TAX_TYPE',
        'tds-codes': 'TDS_CODE', 'exemption-reason': 'EXEMPTION_REASON'
    }
    
    selected_master = request.args.get('master_slug')
    master_items = MasterData.query.filter_by(category=SLUG_TO_DB.get(selected_master)).order_by(MasterData.code).all() if selected_master else []

    if request.method == 'POST':
        form = request.form
        
        # 1. New Department
        if 'new_dept_name' in form:
            if not Department.query.filter_by(name=form['new_dept_name']).first():
                db.session.add(Department(name=form['new_dept_name']))
                db.session.commit()
                return redirect(url_for('admin.admin_workflow', active_tab='logic', selected_dept=form['new_dept_name']))
        
        # 2. Update Logic Emails
        elif 'update_logic_type' in form:
            admin_service.update_logic_email(form)
            
        # 3. Logic Rules (Add/Delete Steps, Categories, IT Rules)
        elif any(k in form for k in ['new_category_name', 'new_step_role', 'new_account_group', 'delete_rule_id', 'delete_step_id', 'delete_it_id']):
            admin_service.manage_logic_rules(form)
            return redirect(url_for('admin.admin_workflow', active_tab='logic', selected_dept=form.get('logic_view', selected_dept)))
            
        # 4. User Management (Add / Edit / Delete) <--- FIXED HERE
        # We now check for 'delete_user_id' and 'edit_user_id' too
        elif any(k in form for k in ['new_user_email', 'delete_user_id', 'edit_user_id']):
            admin_service.manage_users_and_masters(form)
            return redirect(url_for('admin.admin_workflow', active_tab='users'))

    # Data Fetching
    departments = Department.query.all()
    stats = admin_service.get_dashboard_stats()
    dept_matrix = CategoryRouting.query.filter_by(department=selected_dept).all()
    dept_steps = WorkflowStep.query.filter_by(department=selected_dept).order_by(WorkflowStep.step_order).all()
    it_routes = ITRouting.query.all()
    
    # Get all users (excluding admin) to manage in the UI
    all_users = User.query.filter(User.role != 'admin').order_by(User.username).all()
    
    # Separate Finance Users for the "Finance Provisioning" view
    finance_users = [u for u in all_users if u.username in ['Bill Passing Team', 'Treasury Team', 'Tax Team']]
    
    return render_template('admin/workflow.html', stats=stats, activeTab=active_tab, departments=departments,
        selected_dept=selected_dept, dept_matrix_rules=dept_matrix, dept_linear_steps=dept_steps,
        it_routes=it_routes, users=all_users, finance_users=finance_users,
        master_types=MASTER_TITLES, selected_master_slug=selected_master, master_items=master_items)
