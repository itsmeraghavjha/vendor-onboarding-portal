import json
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, Response
from flask_login import login_required, current_user
from sqlalchemy import func
from app.models import User, Department, CategoryRouting, WorkflowStep, ITRouting, MasterData, VendorRequest
from app.extensions import db
from app.services import admin_service

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/export/sap')
@login_required
def export_sap_data():
    if current_user.role != 'admin': 
        return "Access Denied", 403
    
    # Export all for now (or add filtering later)
    requests = VendorRequest.query.all() 
    request_ids = [r.id for r in requests]
    
    csv_output = admin_service.generate_sap_csv(request_ids)
    
    return Response(
        csv_output.getvalue(),
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=sap_vendor_creation.csv"}
    )

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
    
    active_tab = request.form.get('active_tab', request.args.get('active_tab', 'dashboard'))
    logic_view = request.form.get('logic_view') or request.args.get('logic_view')
    selected_master_cat = request.form.get('master_category') or request.args.get('master_cat')
    user_dept_view = request.form.get('user_dept') or request.form.get('user_dept_hidden') or request.args.get('user_dept')

    if request.method == 'POST':
        if 'master_import_file' in request.files:
            if admin_service.handle_master_import(request.files['master_import_file']):
                active_tab = 'masters'
                selected_master_cat = None 

        elif 'update_logic_type' in request.form:
            admin_service.update_logic_email(request.form)
            return redirect(url_for('admin.admin_workflow', active_tab='logic', logic_view=logic_view))

        elif any(k in request.form for k in ['new_category_name', 'delete_rule_id', 'new_step_role', 'delete_step_id', 'new_account_group', 'delete_it_id']):
            admin_service.manage_logic_rules(request.form)
            active_tab = 'logic'

        elif any(k in request.form for k in ['new_user_email', 'delete_user_id']):
            admin_service.manage_users_and_masters(request.form)
            active_tab = 'users'

        elif any(k in request.form for k in ['new_master_code', 'delete_master_id']):
            admin_service.manage_users_and_masters(request.form)
            active_tab = 'masters'
            if 'new_master_code' in request.form:
                selected_master_cat = request.form['master_category']

        return redirect(url_for('admin.admin_workflow', active_tab=active_tab, logic_view=logic_view, master_cat=selected_master_cat, user_dept=user_dept_view))

    cat_query = db.session.query(MasterData.category).distinct().all()
    master_categories = sorted([c[0] for c in cat_query]) if cat_query else []
    master_items = MasterData.query.filter_by(category=selected_master_cat).all() if selected_master_cat else []

    departments = Department.query.all()
    
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

    dept_rule_counts = {d.name: 0 for d in departments}
    for d, c in db.session.query(CategoryRouting.department, func.count(CategoryRouting.id)).group_by(CategoryRouting.department).all():
        if d in dept_rule_counts: dept_rule_counts[d] += c
    for d, c in db.session.query(WorkflowStep.department, func.count(WorkflowStep.id)).group_by(WorkflowStep.department).all():
        if d in dept_rule_counts: dept_rule_counts[d] += c

    dept_rules, dept_steps, dept_it_routes = [], [], []
    finance_users = []

    if logic_view == 'FINANCE_COMMON':
        finance_users = User.query.filter(User.username.in_(['Bill Passing Team', 'Treasury Team', 'Tax Team'])).all()
        order = {'Bill Passing Team': 1, 'Treasury Team': 2, 'Tax Team': 3}
        finance_users.sort(key=lambda u: order.get(u.username, 99))
    elif logic_view == 'IT_COMMON':
        dept_it_routes = ITRouting.query.all()
    elif logic_view:
        dept_rules = CategoryRouting.query.filter_by(department=logic_view).all()
        dept_steps = WorkflowStep.query.filter_by(department=logic_view).order_by(WorkflowStep.step_order).all()

    stats = admin_service.get_dashboard_stats()

    return render_template('admin/workflow.html', 
        departments=departments, stats=stats, activeTab=active_tab, 
        master_categories=master_categories, selected_master_cat=selected_master_cat, master_items=master_items, 
        logic_view=logic_view, dept_rule_counts=dept_rule_counts, dept_rules=dept_rules, dept_steps=dept_steps, 
        dept_it_routes=dept_it_routes, finance_users=finance_users, user_dept_view=user_dept_view, 
        dept_user_stats=dept_user_stats, dept_initiators=dept_initiators, dept_approvers=dept_approvers, json=json
    )