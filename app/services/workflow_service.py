from app.extensions import db
from app.models import Department, CategoryRouting, WorkflowStep, ITRouting, User

class WorkflowService:
    
    # --- DEPARTMENT MANAGEMENT ---
    @staticmethod
    def rename_department(old_name, new_name):
        dept = Department.query.filter_by(name=old_name).first()
        if dept and new_name:
            dept.name = new_name
            # Manual cascade update
            CategoryRouting.query.filter_by(department=old_name).update({'department': new_name})
            WorkflowStep.query.filter_by(department=old_name).update({'department': new_name})
            User.query.filter_by(department=old_name).update({'department': new_name})
            db.session.commit()

    @staticmethod
    def delete_department(name):
        dept = Department.query.filter_by(name=name).first()
        if dept:
            db.session.delete(dept)
            CategoryRouting.query.filter_by(department=name).delete()
            WorkflowStep.query.filter_by(department=name).delete()
            db.session.commit()

    # --- ASSIGNMENTS & MATRIX ---
    @staticmethod
    def update_assignment(assign_type, record_id, email):
        if assign_type == 'matrix_l1':
            db.session.get(CategoryRouting, record_id).l1_manager_email = email
        elif assign_type == 'matrix_l2':
            db.session.get(CategoryRouting, record_id).l2_head_email = email
        elif assign_type == 'step_user':
            db.session.get(WorkflowStep, record_id).approver_email = email
        db.session.commit()

    @staticmethod
    def manage_category(action, data):
        if action == 'add_category':
            db.session.add(CategoryRouting(
                department=data['dept'], 
                category_name=data['category'], 
                l1_manager_email=data['l1'], 
                l2_head_email=data['l2']
            ))
        elif action == 'delete_category':
            db.session.delete(db.session.get(CategoryRouting, data['id']))
        db.session.commit()

    # --- STEPS MANAGEMENT ---
    @staticmethod
    def manage_step(action, data):
        if action == 'add_step':
            count = WorkflowStep.query.filter_by(department=data['dept']).count()
            db.session.add(WorkflowStep(
                department=data['dept'], 
                step_order=count + 1, 
                role_label=data['role'], 
                approver_email=data['email']
            ))
        elif action == 'delete_step':
            db.session.delete(db.session.get(WorkflowStep, data['id']))
        elif action == 'reorder_steps':
            for idx, step_id in enumerate(data.get('order', [])):
                step = db.session.get(WorkflowStep, step_id)
                if step: step.step_order = idx + 1
        
        elif action == 'finance_stage':
            # Finance steps are special (often just 1 or 2 fixed steps)
            step = WorkflowStep.query.filter_by(department='Finance', role_label=data.get('id')).first()
            if step:
                step.approver_email = data.get('email')
            else:
                db.session.add(WorkflowStep(
                    department='Finance', 
                    role_label=data.get('id'), 
                    approver_email=data.get('email'), 
                    step_order=0
                ))
        db.session.commit()

    # --- IT ROUTING ---
    @staticmethod
    def manage_it_route(action, data):
        if action == 'it_route': # Update
            route = db.session.get(ITRouting, data.get('id'))
            if route: route.it_assignee_email = data.get('email')
        
        elif action == 'add_it_mapping':
            if not ITRouting.query.filter_by(account_group=data.get('group')).first():
                db.session.add(ITRouting(account_group=data.get('group'), it_assignee_email=data.get('email')))
        
        elif action == 'delete_it_mapping':
            db.session.delete(db.session.get(ITRouting, data.get('id')))
        
        db.session.commit()