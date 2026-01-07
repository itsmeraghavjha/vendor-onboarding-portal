import csv
import io
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, Response
from flask_login import login_required, current_user
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import Department, User, ITRouting, VendorRequest
from app.services.admin_service import admin_service
from app.services.user_service import UserService
from app.services.workflow_service import WorkflowService
from app.services.master_service import MasterService

admin_bp = Blueprint('admin', __name__)

# --- API: GET DATA ---

@admin_bp.route('/api/logic/<dept_name>', methods=['GET'])
@login_required
def get_dept_logic(dept_name):
    """Returns logic (Matrix + Steps) for a department."""
    logic = admin_service.get_workflow_logic(dept_name)
    return jsonify(logic)

@admin_bp.route('/api/masters/<slug>', methods=['GET'])
@login_required
def get_master_data(slug):
    """Returns master data items for a specific category slug."""
    items = MasterService.get_by_slug(slug)
    return jsonify([{'id': i.id, 'code': i.code, 'label': i.label, 'is_active': i.is_active} for i in items])

# --- API: UNIFIED UPDATE (Refactored) ---

@admin_bp.route('/api/update', methods=['POST'])
@login_required
def api_update():
    """Unified endpoint delegates to specialized Services."""
    if current_user.role != 'admin': 
        return jsonify({'error': 'Unauthorized'}), 403
    
    data = request.get_json()
    action = data.get('action')
    
    try:
        # 1. USER ACTIONS
        if action == 'save_user':
            UserService.create_or_update_user(data)
        elif action == 'delete_user':
            UserService.delete_user(data['id'])

        # 2. DEPARTMENT ACTIONS
        elif action == 'rename_dept':
            WorkflowService.rename_department(data['old_name'], data['new_name'])
        elif action == 'delete_dept':
            WorkflowService.delete_department(data['name'])

        # 3. WORKFLOW & ASSIGNMENT ACTIONS
        elif action == 'update_assignment':
            WorkflowService.update_assignment(data.get('type'), data.get('id'), data.get('email'))
        elif action in ['add_category', 'delete_category']:
            WorkflowService.manage_category(action, data)
        elif action in ['add_step', 'delete_step', 'reorder_steps', 'finance_stage']:
            WorkflowService.manage_step(action, data)
        elif action in ['it_route', 'add_it_mapping', 'delete_it_mapping']:
            WorkflowService.manage_it_route(action, data)

        # 4. MASTER DATA ACTIONS
        elif action == 'save_master':
            MasterService.save_master(data)
        elif action == 'toggle_master':
            MasterService.toggle_master(data['id'])
        elif action == 'delete_master':
            MasterService.delete_master(data['id'])

        return jsonify({'success': True})

    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except IntegrityError:
        db.session.rollback()
        return jsonify({'success': False, 'error': 'Database Integrity Error: Possible duplicate entry.'}), 400
    except Exception as e:
        db.session.rollback()
        # In production, check app logs for the stack trace
        return jsonify({'success': False, 'error': f"System Error: {str(e)}"}), 500

# --- MAIN VIEW ---

@admin_bp.route('/workflow', methods=['GET', 'POST'])
@login_required
def admin_workflow():
    if current_user.role != 'admin': return "Access Denied", 403
    
    if request.method == 'POST':
        # Dept Creation
        if 'new_dept_name' in request.form:
            name = request.form.get('new_dept_name').strip()
            if name and not Department.query.filter_by(name=name).first():
                db.session.add(Department(name=name))
                db.session.commit()
                flash(f"Department {name} created", "success")
        return redirect(url_for('admin.admin_workflow', active_tab='logic'))

    departments = [d.name for d in Department.query.all()]
    all_users = User.query.filter(User.role != 'admin').order_by(User.username).all()
    
    master_types = [{'slug': k, 'label': k.replace('-', ' ').title()} for k in MasterService.SLUG_TO_DB.keys()]

    app_data = {
        'active_tab': request.args.get('active_tab', 'dashboard'),
        'stats': admin_service.get_dashboard_stats(),
        'departments': departments,
        'users': [{
            'id': u.id, 
            'username': u.username, 
            'email': u.email, 
            'department': u.department, 
            'role': u.role, 
            'category': u.assigned_category,
            'is_active': u.is_active  # <--- THIS WAS MISSING
        } for u in all_users],
        'it_routes': [{'id': r.id, 'account_group': r.account_group, 'it_assignee_email': r.it_assignee_email} for r in ITRouting.query.all()],
        'master_types': master_types
    }

    return render_template('admin/workflow.html', app_data=app_data)

# --- SAP EXPORT ---
@admin_bp.route('/export/sap')
@login_required
def export_sap_data():
    if current_user.role != 'admin': return "Access Denied", 403
    
    completed_reqs = VendorRequest.query.filter(VendorRequest.status == 'COMPLETED').with_entities(VendorRequest.id).all()
    req_ids = [r.id for r in completed_reqs]
    
    csv_file = admin_service.generate_sap_csv(req_ids)
    
    filename = f"SAP_Export_{datetime.now().strftime('%Y%m%d')}.csv"
    return Response(
        csv_file.getvalue(),
        mimetype="text/csv", 
        headers={"Content-disposition": f"attachment; filename={filename}"}
    )