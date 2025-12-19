import csv
import io
from flask import flash
from sqlalchemy import func
from app.extensions import db
from app.models import User, Department, CategoryRouting, WorkflowStep, ITRouting, VendorRequest, MasterData

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

            # --- CAPTURE ACCOUNT NO ---
            # We save 'Account No' into the 'parent_code' column
            account_no = row_clean.get('Account No')
            
            if code and label:
                # Check if exists
                exists = MasterData.query.filter_by(category=cat, code=code).first()
                if not exists:
                    db.session.add(MasterData(
                        category=cat, 
                        code=code, 
                        label=label,
                        parent_code=account_no # <--- SAVING IT HERE
                    ))
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