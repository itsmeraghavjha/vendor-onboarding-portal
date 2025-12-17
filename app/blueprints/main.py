import uuid
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.models import VendorRequest, CategoryRouting, WorkflowStep, MockEmail
from app.extensions import db
from app.utils import send_system_email, get_current_pending_email

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index(): 
    return redirect(url_for('auth.login'))

@main_bp.route('/dashboard')
@login_required
def dashboard():
    all_reqs = VendorRequest.query.order_by(VendorRequest.created_at.desc()).all()
    dept_categories = []
    if current_user.role == 'initiator':
        rules = CategoryRouting.query.filter_by(department=current_user.department).all()
        dept_categories = [r.category_name for r in rules]

    my_items = []
    if current_user.role == 'admin': my_items = all_reqs
    elif current_user.role == 'initiator':
        my_items = [r for r in all_reqs if r.initiator_id == current_user.id]
    else:
        for r in all_reqs:
            pending = get_current_pending_email(r)
            if pending and current_user.email and pending.strip().lower() == current_user.email.strip().lower():
                my_items.append(r)
                
    return render_template('dashboard.html', requests=my_items, dept_categories=dept_categories)

@main_bp.route('/create_request', methods=['POST'])
@login_required
def create_request():
    vendor_type = request.form['vendor_type']
    if current_user.assigned_category:
        vendor_type = current_user.assigned_category
    
    new_req = VendorRequest(
        request_id=f"VR-{uuid.uuid4().hex[:6].upper()}",
        initiator_id=current_user.id,
        initiator_dept=current_user.department, 
        vendor_name_basic=request.form['vendor_name'],
        vendor_email=request.form['vendor_email'],
        vendor_type=vendor_type,
        account_group=request.form.get('account_group', 'ZDOM') 
    )
    db.session.add(new_req)
    db.session.commit()
    
    link = url_for('vendor.vendor_portal', token=new_req.token, _external=True)
    send_system_email(new_req.vendor_email, "Vendor Onboarding Invite", "Please fill your details.", link)
    flash('Invite sent.', 'success')
    return redirect(url_for('main.dashboard'))

@main_bp.route('/review/<int:req_id>', methods=['GET', 'POST'])
@login_required
def review_request(req_id):
    req = db.session.get(VendorRequest, req_id)
    if not req: return "Not Found", 404

    pending_email = get_current_pending_email(req)
    
    is_my_turn = False
    if pending_email and current_user.email:
         if pending_email.strip().lower() == current_user.email.strip().lower():
             is_my_turn = True
    if current_user.role == 'admin': is_my_turn = True

    if request.method == 'POST':
        if not is_my_turn: return "Unauthorized", 403

        if request.form.get('action') == 'reject':
            req.status = 'REJECTED'
            db.session.commit()
            return redirect(url_for('main.dashboard'))

        if request.form.get('payment_terms'): req.payment_terms = request.form.get('payment_terms')
        if request.form.get('incoterms'): req.incoterms = request.form.get('incoterms')
        if request.form.get('purchase_org'): req.purchase_org = request.form.get('purchase_org')

        if req.current_dept_flow == 'INITIATOR_REVIEW':
            req.current_dept_flow = 'DEPT'
            req.current_step_number = 1 
            if request.form.get('account_group'): req.account_group = request.form.get('account_group')

        elif req.current_dept_flow == 'DEPT':
            cat_rule = CategoryRouting.query.filter_by(department=req.initiator_dept, category_name=req.vendor_type).first()
            if cat_rule:
                if req.current_step_number == 1: req.current_step_number = 2
                else:
                    req.current_dept_flow = 'FINANCE'
                    req.finance_stage = 'BILL_PASSING'
            else:
                next_step = WorkflowStep.query.filter_by(department=req.initiator_dept, step_order=req.current_step_number + 1).first()
                if next_step: req.current_step_number += 1
                else:
                    req.current_dept_flow = 'FINANCE'
                    req.finance_stage = 'BILL_PASSING'

        elif req.current_dept_flow == 'FINANCE':
            if req.finance_stage == 'BILL_PASSING': req.finance_stage = 'TREASURY'
            elif req.finance_stage == 'TREASURY': req.finance_stage = 'TAX'
            elif req.finance_stage == 'TAX':
                if request.form.get('account_group'): req.account_group = request.form.get('account_group')
                req.current_dept_flow = 'IT'
                req.finance_stage = None 

        elif req.current_dept_flow == 'IT':
            req.sap_id = request.form.get('sap_id')
            req.status = 'COMPLETED'

        db.session.commit()
        
        next_approver = get_current_pending_email(req)
        if next_approver:
            send_system_email(next_approver, "Action Required", f"Request {req.request_id} is waiting for your approval.")
        elif req.status == 'COMPLETED':
            send_system_email(req.vendor_email, "Onboarding Complete", f"Welcome! SAP ID: {req.sap_id}")

        flash("Approved.", "success")
        return redirect(url_for('main.dashboard'))

    return render_template('review.html', req=req, pending_email=pending_email, is_my_turn=is_my_turn)

@main_bp.route('/fake_inbox')
def fake_inbox():
    return render_template('fake_inbox.html', emails=MockEmail.query.order_by(MockEmail.timestamp.desc()).all())
