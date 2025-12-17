import uuid
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.models import VendorRequest, CategoryRouting, WorkflowStep, MockEmail, User, MasterData, ITRouting
from app.extensions import db
from app.utils import send_status_email, get_next_approver_email

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index(): 
    return redirect(url_for('auth.login'))

@main_bp.route('/dashboard')
@login_required
def dashboard():
    # Fetch all requests sorted by newest
    all_reqs = VendorRequest.query.order_by(VendorRequest.created_at.desc()).all()
    
    # 1. Filter "My Pending Items"
    # We use the logic engine to see if the *current* state assigns the request to the logged-in user
    my_items = []
    
    if current_user.role == 'admin':
        my_items = all_reqs # Admin sees everything
    elif current_user.role == 'initiator':
        # Initiators see items they created
        my_items = [r for r in all_reqs if r.initiator_id == current_user.id]
    else:
        # Approvers: Check if it's their turn
        for r in all_reqs:
            # We don't check Draft/Rejected/Completed for "Pending" list
            if r.status in ['DRAFT', 'REJECTED', 'COMPLETED']:
                continue
                
            pending_email, stage_name = get_next_approver_email(r)
            
            if pending_email and current_user.email:
                if pending_email.strip().lower() == current_user.email.strip().lower():
                    my_items.append(r)

    # 2. Get Categories for the "Create Request" dropdown
    # If the user is assigned a specific category (e.g., "Raw Materials"), lock it.
    dept_categories = []
    if current_user.department:
        # Get categories specific to this department from Master Data or Routing Rules
        # Here we just check routing rules to see valid categories for this dept
        rules = CategoryRouting.query.filter_by(department=current_user.department).all()
        dept_categories = sorted(list(set([r.category_name for r in rules])))
        
        # Fallback: If no specific rules, show generic options or Master Data
        if not dept_categories:
            dept_categories = ["General Goods", "Services", "One-time Vendor"]

    return render_template('dashboard.html', requests=my_items, dept_categories=dept_categories, all_requests=all_reqs)

@main_bp.route('/create_request', methods=['POST'])
@login_required
def create_request():
    # 1. Determine Category
    vendor_type = request.form.get('vendor_type')
    if current_user.assigned_category:
        vendor_type = current_user.assigned_category
    
    # 2. Create Request Object
    new_req = VendorRequest(
        request_id=f"VR-{uuid.uuid4().hex[:6].upper()}",
        initiator_id=current_user.id,
        initiator_dept=current_user.department, 
        vendor_name_basic=request.form['vendor_name'],
        vendor_email=request.form['vendor_email'],
        vendor_type=vendor_type,
        # Default status
        status='PENDING_VENDOR',
        current_dept_flow='INITIATOR',
        account_group=request.form.get('account_group', 'ZDOM') # Default to Domestic
    )
    db.session.add(new_req)
    db.session.commit()
    
    # 3. Notify Vendor
    link = url_for('vendor.vendor_portal', token=new_req.token, _external=True)
    send_status_email(new_req, new_req.vendor_email, "Vendor Registration (Action Required)")
    
    flash('Invite sent to vendor.', 'success')
    return redirect(url_for('main.dashboard'))

@main_bp.route('/review/<int:req_id>', methods=['GET', 'POST'])
@login_required
def review_request(req_id):
    req = db.session.get(VendorRequest, req_id)
    if not req: return "Not Found", 404

    # Determine if it's currently this user's turn
    pending_email, stage_name = get_next_approver_email(req)
    
    is_my_turn = False
    if pending_email and current_user.email:
         if pending_email.strip().lower() == current_user.email.strip().lower():
             is_my_turn = True
    if current_user.role == 'admin': is_my_turn = True

    if request.method == 'POST':
        if not is_my_turn: return "Unauthorized", 403

        action = request.form.get('action')

        # --- REJECTION LOGIC ---
        if action == 'reject':
            req.status = 'REJECTED'
            db.session.commit()
            
            # Notify Initiator of Rejection
            initiator = db.session.get(User, req.initiator_id)
            if initiator:
                send_status_email(req, initiator.email, "Request REJECTED")
            
            flash("Request rejected.", "error")
            return redirect(url_for('main.dashboard'))

        # --- DATA UPDATES (Based on who is approving) ---
        
        # Finance Teams can edit Commercial Terms
        if req.current_dept_flow == 'FINANCE':
            if request.form.get('payment_terms'): req.payment_terms = request.form.get('payment_terms')
            if request.form.get('incoterms'): req.incoterms = request.form.get('incoterms')
            if request.form.get('purchase_org'): req.purchase_org = request.form.get('purchase_org')
            if request.form.get('account_group'): req.account_group = request.form.get('account_group')

        # IT Team sets SAP ID
        if req.current_dept_flow == 'IT':
            req.sap_id = request.form.get('sap_id')

        # --- WORKFLOW TRANSITION LOGIC (3-PHASE PIPELINE) ---

        # 0. Start: Vendor Submitted -> Move to Phase 1 (Dept)
        if req.current_dept_flow == 'INITIATOR_REVIEW':
            req.current_dept_flow = 'DEPT'
            req.current_step_number = 1
            # Note: We don't check for next step here, we let the DB save 'DEPT', 1
            # The 'get_next_approver_email' logic handles if Step 1 exists or not.

        # Phase 1: Department Internal
        elif req.current_dept_flow == 'DEPT':
            # Check for Category Routing Rule first
            cat_rule = CategoryRouting.query.filter_by(department=req.initiator_dept, category_name=req.vendor_type).first()
            
            if cat_rule:
                # Rule-based Routing (L1 -> L2 -> Finance)
                if req.current_step_number == 1:
                    # L1 Approved -> Move to L2
                    req.current_step_number = 2
                else:
                    # L2 Approved -> Move to Phase 2 (Finance)
                    req.current_dept_flow = 'FINANCE'
                    req.finance_stage = 'BILL_PASSING' # Start of Finance Chain
            else:
                # Standard Steps Routing (Step 1 -> Step 2... -> Finance)
                # Check if there is a next step defined in DB
                next_step_exists = WorkflowStep.query.filter_by(department=req.initiator_dept, step_order=req.current_step_number + 1).first()
                
                if next_step_exists:
                    req.current_step_number += 1
                else:
                    # No more steps in Dept -> Move to Phase 2 (Finance)
                    req.current_dept_flow = 'FINANCE'
                    req.finance_stage = 'BILL_PASSING'

        # Phase 2: Common Finance Chain
        elif req.current_dept_flow == 'FINANCE':
            if req.finance_stage == 'BILL_PASSING':
                req.finance_stage = 'TREASURY'
            elif req.finance_stage == 'TREASURY':
                req.finance_stage = 'TAX'
            elif req.finance_stage == 'TAX':
                # Finance Chain Complete -> Move to Phase 3 (IT)
                req.current_dept_flow = 'IT'
                req.finance_stage = None

        # Phase 3: IT Execution
        elif req.current_dept_flow == 'IT':
            req.status = 'COMPLETED'
            # Flow Ends

        db.session.commit()
        
        # --- NOTIFICATION ---
        next_person, next_stage = get_next_approver_email(req)
        
        if req.status == 'COMPLETED':
            # Notify Vendor and Initiator
            send_status_email(req, req.vendor_email, f"Onboarding Complete! SAP ID: {req.sap_id}")
            initiator = db.session.get(User, req.initiator_id)
            if initiator:
                send_status_email(req, initiator.email, "Request Completed")
        elif next_person:
            # Notify next approver
            send_status_email(req, next_person, next_stage)

        flash("Approved. Moved to next stage.", "success")
        return redirect(url_for('main.dashboard'))

    return render_template('review.html', req=req, pending_email=pending_email, is_my_turn=is_my_turn, stage_name=stage_name)

@main_bp.route('/fake_inbox')
def fake_inbox():
    return render_template('fake_inbox.html', emails=MockEmail.query.order_by(MockEmail.timestamp.desc()).all())