import json
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, Response
from flask_login import login_required, current_user
from sqlalchemy import func
from app.models import User, Department, CategoryRouting, WorkflowStep, ITRouting, MasterData, VendorRequest
from app.extensions import db
from app.services import admin_service

admin_bp = Blueprint('admin', __name__)

# --- NEW: Drag & Drop API Endpoint ---
@admin_bp.route('/reorder_steps', methods=['POST'])
@login_required
def reorder_steps():
    if current_user.role != 'admin': return jsonify({'error': 'Unauthorized'}), 403
    
    data = request.get_json()
    step_ids = data.get('step_ids', [])
    
    try:
        # Re-assign step_order based on the new index in the list
        for index, step_id in enumerate(step_ids):
            step = db.session.get(WorkflowStep, step_id)
            if step:
                step.step_order = index + 1
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
# -------------------------------------

@admin_bp.route('/export/sap')
@login_required
def export_sap_data():
    if current_user.role != 'admin': return "Access Denied", 403
    
    start_str = request.args.get('start_date')
    end_str = request.args.get('end_date')
    status_filter = request.args.get('status', 'ALL')

    query = VendorRequest.query

    if start_str:
        try:
            start_date = datetime.strptime(start_str, '%Y-%m-%d')
            query = query.filter(VendorRequest.created_at >= start_date)
        except ValueError: pass
    
    if end_str:
        try:
            end_date = datetime.strptime(end_str, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
            query = query.filter(VendorRequest.created_at <= end_date)
        except ValueError: pass

    if status_filter != 'ALL':
        query = query.filter(VendorRequest.status == status_filter)

    requests = query.all()
    request_ids = [r.id for r in requests]
    
    csv_output = admin_service.generate_sap_csv(request_ids)
    filename = f"SAP_Export_{start_str or 'All'}_to_{end_str or 'All'}.csv"

    return Response(
        csv_output.getvalue(),
        mimetype="text/csv",
        headers={"Content-disposition": f"attachment; filename={filename}"}
    )

@admin_bp.route('/workflow', methods=['GET', 'POST'])
@login_required
def admin_workflow():
    if current_user.role != 'admin': return "Access Denied", 403
    
    active_tab = request.args.get('active_tab', 'dashboard')
    selected_dept = request.args.get('selected_dept', 'Purchase')

    if request.method == 'POST':
        form = request.form
        
        # 1. Create New Department
        if 'new_dept_name' in form:
            dept_name = form['new_dept_name'].strip()
            if dept_name and not Department.query.filter_by(name=dept_name).first():
                db.session.add(Department(name=dept_name))
                db.session.commit()
                flash(f"Department '{dept_name}' created.", "success")
                return redirect(url_for('admin.admin_workflow', active_tab='logic', selected_dept=dept_name))

        # 2. Logic Rules
        elif 'update_logic_type' in form:
            admin_service.update_logic_email(form)
            return redirect(url_for('admin.admin_workflow', active_tab='logic', selected_dept=selected_dept))

        elif 'new_category_name' in form:
            admin_service.manage_logic_rules(form)
            return redirect(url_for('admin.admin_workflow', active_tab='logic', selected_dept=selected_dept))

        elif 'new_step_role' in form:
            admin_service.manage_logic_rules(form)
            return redirect(url_for('admin.admin_workflow', active_tab='logic', selected_dept=selected_dept))

        elif any(k in form for k in ['delete_rule_id', 'delete_step_id', 'delete_it_id']):
            admin_service.manage_logic_rules(form)
            return redirect(url_for('admin.admin_workflow', active_tab='logic', selected_dept=selected_dept))
            
        elif 'master_import_file' in request.files:
            admin_service.handle_master_import(request.files['master_import_file'])
            return redirect(url_for('admin.admin_workflow', active_tab='masters'))
            
        elif 'new_user_email' in form or 'delete_user_id' in form:
            admin_service.manage_users_and_masters(form)
            return redirect(url_for('admin.admin_workflow', active_tab='users'))

    # --- DATA PREP ---
    departments = Department.query.all()
    stats = admin_service.get_dashboard_stats()
    
    dept_matrix_rules = CategoryRouting.query.filter_by(department=selected_dept).all()
    dept_linear_steps = WorkflowStep.query.filter_by(department=selected_dept).order_by(WorkflowStep.step_order).all()
    
    finance_users = User.query.filter(User.username.in_(['Bill Passing Team', 'Treasury Team', 'Tax Team'])).all()
    f_order = {'Bill Passing Team': 1, 'Treasury Team': 2, 'Tax Team': 3}
    finance_users.sort(key=lambda u: f_order.get(u.username, 99))
    
    it_routes = ITRouting.query.all()
    
    cat_query = db.session.query(MasterData.category).distinct().all()
    master_categories = sorted([c[0] for c in cat_query]) if cat_query else []
    selected_master_cat = request.args.get('master_cat')
    master_items = MasterData.query.filter_by(category=selected_master_cat).all() if selected_master_cat else []

    # Get all potential approvers for dropdowns
    all_users = User.query.filter(User.role != 'admin').order_by(User.username).all()

    return render_template('admin/workflow.html', 
        stats=stats, activeTab=active_tab, departments=departments,
        selected_dept=selected_dept,
        dept_matrix_rules=dept_matrix_rules,
        dept_linear_steps=dept_linear_steps,
        finance_users=finance_users,
        it_routes=it_routes,
        master_categories=master_categories, selected_master_cat=selected_master_cat, master_items=master_items,
        users=all_users # Passing users for dropdowns
    )