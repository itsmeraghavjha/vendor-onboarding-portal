from flask import Blueprint, render_template, request, redirect, url_for
from flask_login import login_required, current_user
from app.models import User, Department, CategoryRouting, WorkflowStep, ITRouting, VendorRequest, MasterData
from app.extensions import db

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/workflow', methods=['GET', 'POST'])
@login_required
def admin_workflow():
    if current_user.role != 'admin': return "Access Denied", 403
    active_tab = request.form.get('active_tab', request.args.get('active_tab', 'users'))
    
    # --- Master Data Setup ---
    # Get all unique categories
    cat_query = db.session.query(MasterData.category).distinct().all()
    master_categories = [c[0] for c in cat_query] if cat_query else []
    
    # Determine selected category
    selected_master_cat = request.args.get('master_cat') or request.form.get('master_category')
    if not selected_master_cat and master_categories:
        selected_master_cat = master_categories[0]
        
    master_items = []
    if selected_master_cat:
        master_items = MasterData.query.filter_by(category=selected_master_cat).all()

    if request.method == 'POST':
        # --- User Logic ---
        if 'new_user_email' in request.form:
            email = request.form['new_user_email'].strip().lower()
            if not User.query.filter_by(email=email).first():
                u = User(username=request.form['new_user_name'], email=email, role=request.form['user_role'], department=request.form['user_dept'], assigned_category=request.form.get('assigned_category'))
                u.set_password('pass123')
                db.session.add(u)
                db.session.commit()
            active_tab = 'users'
        
        elif 'delete_user_id' in request.form:
            user = db.session.get(User, request.form['delete_user_id'])
            if user:
                db.session.delete(user)
                db.session.commit()
            active_tab = 'users'

        # --- Master Data Logic ---
        elif 'new_master_code' in request.form:
            cat = request.form['master_category']
            code = request.form['new_master_code']
            label = request.form['new_master_label']
            if not MasterData.query.filter_by(category=cat, code=code).first():
                db.session.add(MasterData(category=cat, code=code, label=label))
                db.session.commit()
            active_tab = 'masters'
            selected_master_cat = cat
            
        elif 'delete_master_id' in request.form:
            item = db.session.get(MasterData, request.form['delete_master_id'])
            if item:
                db.session.delete(item)
                db.session.commit()
            active_tab = 'masters'

        # --- Workflow Logic ---
        elif 'new_category_name' in request.form:
            cat = request.form['new_category_name']
            dept = request.form['target_dept']
            if not CategoryRouting.query.filter_by(department=dept, category_name=cat).first():
                db.session.add(CategoryRouting(department=dept, category_name=cat, l1_manager_email=request.form['l1_email'], l2_head_email=request.form['l2_email']))
                db.session.commit()
            active_tab = 'logic'
            
        elif 'delete_rule_id' in request.form:
            rule = db.session.get(CategoryRouting, request.form['delete_rule_id'])
            if rule:
                db.session.delete(rule)
                db.session.commit()
            active_tab = 'logic'
            
        elif 'standard_dept' in request.form:
            dept = request.form['standard_dept']
            current_steps = WorkflowStep.query.filter_by(department=dept).count()
            db.session.add(WorkflowStep(department=dept, step_order=current_steps + 1, role_label=request.form['standard_role'], approver_email=request.form['standard_email']))
            db.session.commit()
            active_tab = 'logic'
            
        elif 'delete_step_id' in request.form:
            step = db.session.get(WorkflowStep, request.form['delete_step_id'])
            if step:
                db.session.delete(step)
                db.session.commit()
            active_tab = 'logic'
            
        elif 'new_account_group' in request.form:
            grp = request.form['new_account_group']
            if not ITRouting.query.filter_by(account_group=grp).first():
                db.session.add(ITRouting(account_group=grp, it_assignee_email=request.form['it_email']))
                db.session.commit()
            active_tab = 'logic'
            
        elif 'delete_it_id' in request.form:
            route = db.session.get(ITRouting, request.form['delete_it_id'])
            if route:
                db.session.delete(route)
                db.session.commit()
            active_tab = 'logic'
            
        # Refresh master items if post changed something
        if selected_master_cat:
            master_items = MasterData.query.filter_by(category=selected_master_cat).all()

    users = User.query.filter(User.role != 'admin').order_by(User.department).all()
    departments = Department.query.all()
    category_rules = CategoryRouting.query.order_by(CategoryRouting.department).all()
    standard_steps = WorkflowStep.query.order_by(WorkflowStep.department, WorkflowStep.step_order).all()
    it_routes = ITRouting.query.all()
    
    stats = {
        'users': User.query.count(), 
        'requests': VendorRequest.query.count(), 
        'rules': len(category_rules)+len(standard_steps)+len(it_routes)
    }

    return render_template('admin_workflow.html', 
                         users=users, 
                         departments=departments, 
                         category_rules=category_rules, 
                         standard_steps=standard_steps, 
                         it_routes=it_routes, 
                         stats=stats, 
                         activeTab=active_tab,
                         master_categories=master_categories,
                         selected_master_cat=selected_master_cat,
                         master_items=master_items)

@admin_bp.route('/nuke-and-reset')
def nuke_and_reset():
    # ... (Keep existing nuke logic if needed, but omitted for brevity as user already has DB)
    return redirect(url_for('auth.login'))
