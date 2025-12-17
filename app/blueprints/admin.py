import json
import csv
import io
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from sqlalchemy import func
from app.models import User, Department, CategoryRouting, WorkflowStep, ITRouting, VendorRequest, MasterData
from app.extensions import db

admin_bp = Blueprint('admin', __name__)

# --- DRAG-AND-DROP API ---
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

@admin_bp.route('/workflow', methods=['GET', 'POST'])
@login_required
def admin_workflow():
    if current_user.role != 'admin': return "Access Denied", 403
    
    # CORRECT VARIABLE DEFINITION (snake_case)
    active_tab = request.form.get('active_tab', request.args.get('active_tab', 'dashboard'))
    
    # --- 1. Master Data Setup ---
    cat_query = db.session.query(MasterData.category).distinct().all()
    master_categories = sorted([c[0] for c in cat_query]) if cat_query else []
    selected_master_cat = request.args.get('master_cat') or request.form.get('master_category')
    master_items = MasterData.query.filter_by(category=selected_master_cat).all() if selected_master_cat else []

    # --- 2. User Logic Setup ---
    departments = Department.query.all()
    user_dept_view = request.args.get('user_dept') or request.form.get('user_dept')
    
    # Calculate User Counts
    dept_user_stats = {d.name: {'initiator': 0, 'approver': 0} for d in departments}
    for u in User.query.filter(User.role != 'admin').all():
        if u.department in dept_user_stats:
            r = u.role if u.role in ['initiator', 'approver'] else 'initiator'
            dept_user_stats[u.department][r] += 1

    dept_initiators, dept_approvers = [], []
    if user_dept_view:
        users = User.query.filter_by(department=user_dept_view).filter(User.role != 'admin').all()
        dept_initiators = [u for u in users if u.role == 'initiator']
        dept_approvers = [u for u in users if u.role == 'approver']

    # --- 3. Workflow Logic Setup ---
    logic_view = request.args.get('logic_view') or request.form.get('logic_view')
    
    # Logic Rule Counts
    dept_rule_counts = {d.name: 0 for d in departments}
    for d, c in db.session.query(CategoryRouting.department, func.count(CategoryRouting.id)).group_by(CategoryRouting.department).all():
        if d in dept_rule_counts: dept_rule_counts[d] += c
    for d, c in db.session.query(WorkflowStep.department, func.count(WorkflowStep.id)).group_by(WorkflowStep.department).all():
        if d in dept_rule_counts: dept_rule_counts[d] += c

    dept_rules, dept_steps, dept_it_routes = [], [], []
    finance_users = []

    # FETCH LOGIC DATA
    if logic_view == 'FINANCE_COMMON':
        # Fetch actual users for the 3 fixed roles
        finance_users = User.query.filter(User.username.in_(['Bill Passing Team', 'Treasury Team', 'Tax Team'])).all()
        order = {'Bill Passing Team': 1, 'Treasury Team': 2, 'Tax Team': 3}
        finance_users.sort(key=lambda u: order.get(u.username, 99))
        
    elif logic_view == 'IT_COMMON':
        dept_it_routes = ITRouting.query.all()
        
    elif logic_view: # Department View
        dept_rules = CategoryRouting.query.filter_by(department=logic_view).all()
        dept_steps = WorkflowStep.query.filter_by(department=logic_view).order_by(WorkflowStep.step_order).all()

    # --- POST HANDLING ---
    if request.method == 'POST':
        
        # --- BULK IMPORT MASTERS ---
        if 'master_import_file' in request.files:
            file = request.files['master_import_file']
            if file and file.filename.endswith('.csv'):
                try:
                    stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
                    csv_input = csv.DictReader(stream)
                    count = 0
                    for row in csv_input:
                        row_clean = {k.strip().lower(): v for k, v in row.items()}
                        cat = row_clean.get('category', '').strip().upper()
                        code = row_clean.get('code', '').strip()
                        label = row_clean.get('label', '').strip()
                        
                        if cat and code and label:
                            exists = MasterData.query.filter_by(category=cat, code=code).first()
                            if not exists:
                                db.session.add(MasterData(category=cat, code=code, label=label))
                                count += 1
                    db.session.commit()
                    flash(f"Successfully imported {count} items.", "success")
                except Exception as e:
                    db.session.rollback()
                    flash(f"Import Error: {str(e)}", "error")
            else:
                flash("Please upload a valid CSV file.", "error")
            
            active_tab = 'masters'
            selected_master_cat = None 

        # A. UPDATE EMAIL
        elif 'update_logic_type' in request.form:
            l_type = request.form['update_logic_type']
            r_id = request.form['rule_id']
            new_email = request.form['new_email']
            
            if l_type == 'cat_l1': db.session.get(CategoryRouting, r_id).l1_manager_email = new_email
            elif l_type == 'cat_l2': db.session.get(CategoryRouting, r_id).l2_head_email = new_email
            elif l_type == 'step': db.session.get(WorkflowStep, r_id).approver_email = new_email
            elif l_type == 'it_route': db.session.get(ITRouting, r_id).it_assignee_email = new_email
            elif l_type == 'finance_user': 
                user = db.session.get(User, r_id)
                if user: user.email = new_email
            
            db.session.commit()
            return redirect(url_for('admin.admin_workflow', active_tab='logic', logic_view=logic_view))

        # B. LOGIC CREATION/DELETION
        elif 'new_category_name' in request.form:
            cat, dept = request.form['new_category_name'], request.form['logic_view']
            if not CategoryRouting.query.filter_by(department=dept, category_name=cat).first():
                db.session.add(CategoryRouting(department=dept, category_name=cat, l1_manager_email=request.form['l1_email'], l2_head_email=request.form['l2_email']))
                db.session.commit()
            active_tab = 'logic'
        elif 'delete_rule_id' in request.form:
            db.session.delete(db.session.get(CategoryRouting, request.form['delete_rule_id']))
            db.session.commit()
            active_tab = 'logic'
        elif 'new_step_role' in request.form:
            dept = request.form['logic_view']
            curr = WorkflowStep.query.filter_by(department=dept).count()
            db.session.add(WorkflowStep(department=dept, step_order=curr+1, role_label=request.form['new_step_role'], approver_email=request.form['new_step_email']))
            db.session.commit()
            active_tab = 'logic'
        elif 'delete_step_id' in request.form:
            db.session.delete(db.session.get(WorkflowStep, request.form['delete_step_id']))
            db.session.commit()
            active_tab = 'logic'
        elif 'new_account_group' in request.form:
            if not ITRouting.query.filter_by(account_group=request.form['new_account_group']).first():
                db.session.add(ITRouting(account_group=request.form['new_account_group'], it_assignee_email=request.form['it_email']))
                db.session.commit()
            active_tab = 'logic'
        elif 'delete_it_id' in request.form:
            db.session.delete(db.session.get(ITRouting, request.form['delete_it_id']))
            db.session.commit()
            active_tab = 'logic'

        # C. USER & MASTER DATA ACTIONS
        elif 'new_user_email' in request.form:
            email = request.form['new_user_email'].strip().lower()
            if not User.query.filter_by(email=email).first():
                u = User(username=request.form['new_user_name'], email=email, role=request.form['user_role'], department=request.form['user_dept'], assigned_category=request.form.get('assigned_category'))
                u.set_password('pass123')
                db.session.add(u)
                db.session.commit()
            active_tab = 'users'
            user_dept_view = request.form.get('user_dept_hidden')
        elif 'delete_user_id' in request.form:
            u = db.session.get(User, request.form['delete_user_id'])
            if u: db.session.delete(u); db.session.commit()
            active_tab = 'users'
            user_dept_view = request.form.get('user_dept_hidden')
        elif 'new_master_code' in request.form:
            cat, code = request.form['master_category'], request.form['new_master_code']
            if not MasterData.query.filter_by(category=cat, code=code).first():
                db.session.add(MasterData(category=cat, code=code, label=request.form['new_master_label']))
                db.session.commit()
            active_tab = 'masters'
            selected_master_cat = cat
        elif 'delete_master_id' in request.form:
            m = db.session.get(MasterData, request.form['delete_master_id'])
            if m: db.session.delete(m); db.session.commit()
            active_tab = 'masters'
            selected_master_cat = request.form.get('master_category')

        # Redirect to clean POST data
        return redirect(url_for('admin.admin_workflow', active_tab=active_tab, logic_view=logic_view, master_cat=selected_master_cat, user_dept=user_dept_view))

    # --- DASHBOARD STATS ---
    stats = {
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

    # CORRECT RETURN STATEMENT
    return render_template('admin_workflow.html', departments=departments, stats=stats, activeTab=active_tab, master_categories=master_categories, selected_master_cat=selected_master_cat, master_items=master_items, logic_view=logic_view, dept_rule_counts=dept_rule_counts, dept_rules=dept_rules, dept_steps=dept_steps, dept_it_routes=dept_it_routes, finance_users=finance_users, user_dept_view=user_dept_view, dept_user_stats=dept_user_stats, dept_initiators=dept_initiators, dept_approvers=dept_approvers, json=json)