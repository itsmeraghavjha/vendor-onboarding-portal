import uuid
import json
import csv
import io
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, Response
from flask_login import login_required, current_user
from app.models import VendorRequest, CategoryRouting, WorkflowStep, MasterData, VendorTaxDetail
from app.extensions import db
from app.utils import send_status_email, send_system_email, get_next_approver_email, log_audit
from app.services import admin_service

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index(): 
    return redirect(url_for('auth.login'))

# In app/blueprints/main.py

# In app/blueprints/main.py

@main_bp.route('/dashboard')
@login_required
def dashboard():
    # 1. Fetch Requests based on Role
    if current_user.role == 'admin':
        all_reqs = VendorRequest.query.order_by(VendorRequest.created_at.desc()).all()
    elif current_user.role == 'initiator':
        all_reqs = VendorRequest.query.filter_by(initiator_id=current_user.id).order_by(VendorRequest.created_at.desc()).all()
    else:
        if current_user.department in ['Finance', 'IT', 'HR']:
            all_reqs = VendorRequest.query.order_by(VendorRequest.created_at.desc()).all()
        else:
            all_reqs = VendorRequest.query.filter_by(initiator_dept=current_user.department).order_by(VendorRequest.created_at.desc()).all()

    # 2. Identify "Action Required" items (Only for Approvers, NOT Admin)
    pending_items = []
    
    for r in all_reqs:
        r.pending_action = False 
        
        if r.status in ['DRAFT', 'REJECTED', 'COMPLETED']:
            continue
            
        pending_email, stage_name = get_next_approver_email(r)
        
        # Check if current user is the blocker
        if pending_email and current_user.email:
            if pending_email.strip().lower() == current_user.email.strip().lower():
                r.pending_action = True
                pending_items.append(r)
        
        # REMOVED: The admin override block "if role == admin: pending_action = True" 

    # 3. Calculate Stats
    stats = {
        'total': len(all_reqs),
        'action_required': len(pending_items),
        'completed': sum(1 for r in all_reqs if r.status == 'COMPLETED'),
        'rejected': sum(1 for r in all_reqs if r.status == 'REJECTED'),
        # 'in_process' means anything NOT finished
        'in_process': sum(1 for r in all_reqs if r.status not in ['DRAFT', 'COMPLETED', 'REJECTED']),
        
        # Detailed Breakdown for trackers
        'stuck_dept': sum(1 for r in all_reqs if r.current_dept_flow == 'DEPT' and r.status == 'PENDING_APPROVAL'),
        'stuck_finance': sum(1 for r in all_reqs if r.current_dept_flow == 'FINANCE' and r.status == 'PENDING_APPROVAL'),
        'stuck_it': sum(1 for r in all_reqs if r.current_dept_flow == 'IT' and r.status == 'PENDING_APPROVAL'),
    }

    # 4. Categories for Initiator Modal
    dept_categories = []
    if current_user.department:
        rules = CategoryRouting.query.filter_by(department=current_user.department).all()
        dept_categories = sorted(list(set([r.category_name for r in rules])))
        if not dept_categories: dept_categories = ["General Goods", "Services"]

    return render_template('main/dashboard.html', 
                           requests=all_reqs, 
                           stats=stats,
                           dept_categories=dept_categories)


@main_bp.route('/create_request', methods=['POST'])
@login_required
def create_request():
    vendor_type = request.form.get('vendor_type')
    if current_user.assigned_category: vendor_type = current_user.assigned_category
    
    new_token = uuid.uuid4().hex 
    new_req = VendorRequest(
        request_id=f"VR-{uuid.uuid4().hex[:6].upper()}",
        token=new_token,
        initiator_id=current_user.id,
        initiator_dept=current_user.department, 
        vendor_name_basic=request.form['vendor_name'],
        vendor_email=request.form['vendor_email'],
        vendor_type=vendor_type,
        status='PENDING_VENDOR',
        current_dept_flow='INITIATOR',
        account_group=request.form.get('account_group', 'ZDOM') 
    )
    db.session.add(new_req)
    db.session.commit() # Commit 1: Saves the Request (generates ID)
    
    # --- FIX IS HERE ---
    log_audit(new_req.id, current_user.id, 'INITIATED', "Vendor Request Created")
    db.session.commit() # Commit 2: SAVES THE LOG (This was missing!)
    # -------------------
    
    portal_link = url_for('vendor.vendor_portal', token=new_req.token, _external=True)
    subject = f"Invitation: Register with Heritage Foods ({new_req.request_id})"
    
    body_html = render_template('email/notification.html',
        req=new_req,
        subject="Vendor Registration Invitation",
        body=f"Dear {new_req.vendor_name_basic},<br><br>You have been invited to register with Heritage Foods. Please click the button below to start your onboarding process.",
        link=portal_link,
        current_year=datetime.now().year
    )
    
    send_system_email(new_req.vendor_email, subject, body_html)
    
    flash('Invite sent to vendor.', 'success')
    return redirect(url_for('main.dashboard'))


@main_bp.route('/download_sap/<int:req_id>')
@login_required
def download_sap_report(req_id):
    """Downloads the SAP CSV for a SINGLE request (IT Team Button)."""
    req = db.session.get(VendorRequest, req_id)
    if not req: return "Not Found", 404

    csv_output = admin_service.generate_sap_csv([req.id])

    return Response(
        csv_output.getvalue(), 
        mimetype='text/csv', 
        headers={"Content-Disposition": f"attachment; filename=SAP_Upload_{req.request_id}.csv"}
    )

@main_bp.route('/review/<int:req_id>', methods=['GET', 'POST'])
@login_required
def review_request(req_id):
    req = db.session.get(VendorRequest, req_id)
    if not req: return "Not Found", 404

    pending_email, stage_name = get_next_approver_email(req)
    is_my_turn = (pending_email and current_user.email and pending_email.strip().lower() == current_user.email.strip().lower())
    if current_user.role == 'admin': is_my_turn = True

    acc_groups = MasterData.query.filter_by(category='ACCOUNT_GROUP').all()
    pay_terms = MasterData.query.filter_by(category='PAYMENT_TERM').all()
    purch_orgs = MasterData.query.filter_by(category='PURCHASE_ORG').all()
    incoterms = MasterData.query.filter_by(category='INCOTERM').all()
    gl_list = MasterData.query.filter_by(category='GL_ACCOUNT').all()
    house_banks = MasterData.query.filter_by(category='HOUSE_BANK').all()
    
    tax_types = MasterData.query.filter_by(category='TAX_TYPE').all()
    all_tax_codes = MasterData.query.filter_by(category='TDS_CODE').all()
    tax_code_map = {}
    for tc in all_tax_codes:
        p = tc.parent_code if tc.parent_code else 'General'
        if p not in tax_code_map: tax_code_map[p] = []
        tax_code_map[p].append({'code': tc.code, 'label': tc.label})

    exemption_reasons = MasterData.query.filter_by(category='EXEMPTION_REASON').all()

    if request.method == 'POST':
        if not is_my_turn: return "Unauthorized", 403
        action = request.form.get('action')
        comments = request.form.get('comments', '')

        if action == 'send_back':
            req.status = 'PENDING_VENDOR'; req.current_dept_flow = 'INITIATOR_REVIEW'
            db.session.commit()
            
            log_audit(req.id, current_user.id, 'QUERY_RAISED', f"Query: {comments}")

            req.last_query = comments 
            db.session.commit()
            
            link = url_for('vendor.vendor_portal', token=req.token, _external=True)
            subject = f"Query on {req.request_id}"
            body_html = render_template('email/notification.html',
                req=req,
                subject="Application Sent Back",
                body=f"The reviewer has sent back your application with the following query:<br><br><b>{comments}</b><br><br>Please update your details and resubmit.",
                link=link,
                current_year=datetime.now().year
            )
            
            send_system_email(req.vendor_email, subject, body_html)
            flash("Sent back.", "warning"); return redirect(url_for('main.dashboard'))

        if action == 'reject':
            req.status = 'REJECTED'
            log_audit(req.id, current_user.id, 'REJECTED', f"Reason: {comments}")
            db.session.commit()
            send_status_email(req, req.vendor_email, f"Rejected: {comments}")
            flash("Rejected.", "error"); return redirect(url_for('main.dashboard'))

        # --- ACTION LOGGING LOGIC ---
        log_action_name = "APPROVED"

        if req.current_dept_flow == 'INITIATOR_REVIEW':
            req.account_group = request.form.get('account_group')
            req.payment_terms = request.form.get('payment_terms')
            req.purchase_org = request.form.get('purchase_org')
            req.incoterms = request.form.get('incoterms')
            log_action_name = "APPROVED_INITIATOR"
        
        elif req.current_dept_flow == 'DEPT':
            # Identify which step/role is approving
            step = WorkflowStep.query.filter_by(department=req.initiator_dept, step_order=req.current_step_number).first()
            role_label = step.role_label if step else f"STEP_{req.current_step_number}"
            # Clean string for DB (e.g., "Factory Head" -> "APPROVED_FACTORY_HEAD")
            log_action_name = f"APPROVED_{role_label.replace(' ', '_').upper()}"

        elif req.current_dept_flow == 'IT': 
            req.sap_id = request.form.get('sap_id')
            req.status = 'COMPLETED'
            log_action_name = "COMPLETED_BY_IT"

        elif req.finance_stage == 'BILL_PASSING': 
            req.gl_account = request.form.get('gl_account')
            log_action_name = "APPROVED_BILL_PASSING"
            
        elif req.finance_stage == 'TREASURY': 
            req.house_bank = request.form.get('house_bank')
            log_action_name = "APPROVED_TREASURY"
            
        elif req.finance_stage == 'TAX':
            log_action_name = "APPROVED_TAX"
            # 1. Wipe old tax details
            for old_tax in req.tax_details:
                db.session.delete(old_tax)
            
            # 2. Save Tax 1 (WHT)
            t1_types = request.form.getlist('tax1_type[]')
            t1_codes = request.form.getlist('tax1_code[]')
            t1_recip = request.form.getlist('tax1_recipient_type[]')
            t1_reas = request.form.getlist('tax1_exemption_reason[]')
            t1_cert = request.form.getlist('tax1_cert_no[]')
            t1_rate = request.form.getlist('tax1_rate[]')
            t1_start = request.form.getlist('tax1_start_date[]')
            t1_end = request.form.getlist('tax1_end_date[]')

            for i in range(len(t1_types)):
                if t1_types[i]:
                    new_wht = VendorTaxDetail(
                        vendor_request=req,
                        tax_category='WHT',
                        tax_code=t1_codes[i] if i < len(t1_codes) else '',
                        recipient_type=t1_recip[i] if i < len(t1_recip) else '',
                        exemption_reason=t1_reas[i] if i < len(t1_reas) else '',
                        cert_no=t1_cert[i] if i < len(t1_cert) else '',
                        rate=t1_rate[i] if i < len(t1_rate) else '',
                        start_date=t1_start[i] if i < len(t1_start) else '',
                        end_date=t1_end[i] if i < len(t1_end) else ''
                    )
                    db.session.add(new_wht)

            # 3. Save Tax 2 (194Q)
            t2_sec = request.form.getlist('tax2_section_code[]')
            t2_cert = request.form.getlist('tax2_cert_no[]')
            t2_rate = request.form.getlist('tax2_rate[]')
            t2_start = request.form.getlist('tax2_start_date[]')
            t2_end = request.form.getlist('tax2_end_date[]')
            t2_type = request.form.getlist('tax2_type[]')
            t2_code = request.form.getlist('tax2_code[]')
            t2_thresh = request.form.getlist('tax2_threshold_amount[]')

            for i in range(len(t2_sec)):
                if t2_sec[i]:
                    new_194q = VendorTaxDetail(
                        vendor_request=req,
                        tax_category='194Q',
                        section_code=t2_sec[i],
                        cert_no=t2_cert[i] if i < len(t2_cert) else '',
                        rate=t2_rate[i] if i < len(t2_rate) else '',
                        start_date=t2_start[i] if i < len(t2_start) else '',
                        end_date=t2_end[i] if i < len(t2_end) else '',
                        tax_code=t2_code[i] if i < len(t2_code) else '',
                        threshold=t2_thresh[i] if i < len(t2_thresh) else ''
                    )
                    db.session.add(new_194q)

        # Log the specific approval action
        log_audit(req.id, current_user.id, log_action_name)

        # --- TRANSITION LOGIC & LOGGING ---
        if req.status != 'COMPLETED':
            if req.current_dept_flow == 'INITIATOR_REVIEW':
                req.current_dept_flow = 'DEPT'; req.current_step_number = 1
                log_audit(req.id, current_user.id, "MOVED_TO_DEPT_FLOW")
            
            elif req.current_dept_flow == 'DEPT':
                next_step = WorkflowStep.query.filter_by(department=req.initiator_dept, step_order=req.current_step_number + 1).first()
                if next_step: 
                    req.current_step_number += 1
                    # Log movement to next department step
                    log_audit(req.id, current_user.id, f"MOVED_TO_DEPT_STEP_{next_step.step_order}", f"Next: {next_step.role_label}")
                else: 
                    req.current_dept_flow = 'FINANCE'; req.finance_stage = 'BILL_PASSING'
                    log_audit(req.id, current_user.id, "MOVED_TO_FINANCE_BILL_PASSING")
            
            elif req.current_dept_flow == 'FINANCE':
                if req.finance_stage == 'BILL_PASSING': 
                    req.finance_stage = 'TREASURY'
                    log_audit(req.id, current_user.id, "MOVED_TO_FINANCE_TREASURY")
                elif req.finance_stage == 'TREASURY': 
                    req.finance_stage = 'TAX'
                    log_audit(req.id, current_user.id, "MOVED_TO_FINANCE_TAX")
                elif req.finance_stage == 'TAX': 
                    req.current_dept_flow = 'IT'; req.finance_stage = None
                    log_audit(req.id, current_user.id, "MOVED_TO_IT_TEAM")

        db.session.commit()
        
        next_person, next_stage = get_next_approver_email(req)
        
        if req.status == 'COMPLETED': 
             subject = "Onboarding Complete"
             body_html = render_template('email/notification.html',
                req=req,
                subject=subject,
                body=f"Congratulations! Your onboarding is complete.<br><br><b>Your Vendor Code: {req.sap_id}</b>",
                link=None,
                current_year=datetime.now().year
             )
             send_system_email(req.vendor_email, subject, body_html)
             
        elif next_person: 
            send_status_email(req, next_person, next_stage)

        flash("Approved.", "success"); return redirect(url_for('main.dashboard'))

    return render_template('main/review.html', req=req, pending_email=pending_email, is_my_turn=is_my_turn, stage_name=stage_name,
                           acc_groups=acc_groups, pay_terms=pay_terms, purch_orgs=purch_orgs, incoterms=incoterms,
                           gl_list=gl_list, house_banks=house_banks,
                           tax_types=tax_types, tax_code_map=json.dumps(tax_code_map), exemption_reasons=exemption_reasons)