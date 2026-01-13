import uuid
import json
import csv
import io
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, Response,send_from_directory, abort, current_app, redirect 
from flask_login import login_required, current_user
from app.models import VendorRequest, CategoryRouting, WorkflowStep, MasterData, VendorTaxDetail
from app.extensions import db
from app.utils import send_status_email, send_system_email, get_next_approver_email, log_audit
from app.services.admin_service import admin_service

main_bp = Blueprint('main', __name__)



SECTION_LABELS = {
    'organization': 'Organization Profile',
    'gst': 'GST Details',
    'pan': 'PAN Details',
    'msme': 'MSME Details',
    'banking': 'Banking Details',
    'tax': 'Tax Information',
}

@main_bp.route('/')
def index(): 
    return redirect(url_for('auth.login'))


@main_bp.route('/download_sap/<int:req_id>')
@login_required
def download_sap_report(req_id):
    req = db.session.get(VendorRequest, req_id)
    if not req: return "Not Found", 404

    csv_output = admin_service.generate_sap_csv([req.id])

    return Response(
        csv_output.getvalue(), 
        mimetype='text/csv', 
        headers={"Content-Disposition": f"attachment; filename=SAP_Upload_{req.request_id}.csv"}
    )


@main_bp.route('/dashboard')
@login_required
def dashboard():
    if current_user.role == 'admin':
        all_reqs = VendorRequest.query.order_by(VendorRequest.created_at.desc()).all()
    elif current_user.role == 'initiator':
        all_reqs = VendorRequest.query.filter_by(initiator_id=current_user.id).order_by(VendorRequest.created_at.desc()).all()
    else:
        if current_user.department in ['Finance', 'IT', 'HR']:
            all_reqs = VendorRequest.query.order_by(VendorRequest.created_at.desc()).all()
        else:
            all_reqs = VendorRequest.query.filter_by(initiator_dept=current_user.department).order_by(VendorRequest.created_at.desc()).all()

    pending_items = []
    for r in all_reqs:
        r.pending_action = False 
        if r.status in ['DRAFT', 'REJECTED', 'COMPLETED', 'PENDING_VENDOR']: continue
            
        pending_email, stage_name = get_next_approver_email(r)
        
        if pending_email and current_user.email:
            if pending_email.strip().lower() == current_user.email.strip().lower():
                r.pending_action = True
                pending_items.append(r)

    stats = {
        'total': len(all_reqs),
        'action_required': len(pending_items),
        'completed': sum(1 for r in all_reqs if r.status == 'COMPLETED'),
        'rejected': sum(1 for r in all_reqs if r.status == 'REJECTED'),
        'in_process': sum(1 for r in all_reqs if r.status not in ['DRAFT', 'COMPLETED', 'REJECTED']),
        'stuck_dept': sum(1 for r in all_reqs if r.current_dept_flow == 'DEPT' and r.status == 'PENDING_APPROVAL'),
        'stuck_finance': sum(1 for r in all_reqs if r.current_dept_flow == 'FINANCE' and r.status == 'PENDING_APPROVAL'),
        'stuck_it': sum(1 for r in all_reqs if r.current_dept_flow == 'IT' and r.status == 'PENDING_APPROVAL'),
    }

    dept_categories = ["Standard"]
    if current_user.department:
        rules = CategoryRouting.query.filter_by(department=current_user.department).all()
        matrix_cats = sorted(list(set([r.category_name for r in rules])))
        dept_categories.extend(matrix_cats)

    return render_template('main/dashboard.html', 
                           requests=all_reqs, 
                           stats=stats,
                           dept_categories=dept_categories)


@main_bp.route('/create_request', methods=['POST'])
@login_required
def create_request():
    vendor_type = request.form.get('vendor_type')
    if not vendor_type:
        vendor_type = 'Standard'
    
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
    db.session.commit()
    
    log_audit(new_req.id, current_user.id, 'INITIATED', "Vendor Request Created")
    
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


@main_bp.route('/review/<int:req_id>', methods=['GET', 'POST'])
@login_required
def review_request(req_id):
    req = db.session.get(VendorRequest, req_id)
    if not req: return "Not Found", 404

    # --- 1. SETUP & PERMISSIONS ---
    pending_email, stage_name = get_next_approver_email(req)
    is_my_turn = False
    
    if current_user.role == 'admin':
        is_my_turn = True
    elif pending_email and current_user.email:
        if pending_email.strip().lower() == current_user.email.strip().lower():
            is_my_turn = True
    
    if req.status == 'PENDING_VENDOR' and current_user.role == 'initiator':
        is_my_turn = False

    # --- 2. FETCH MASTER DATA ---
    acc_groups = MasterData.query.filter_by(category='ACCOUNT_GROUP').all()
    pay_terms = MasterData.query.filter_by(category='PAYMENT_TERM').all()
    purch_orgs = MasterData.query.filter_by(category='PURCHASE_ORG').all()
    incoterms = MasterData.query.filter_by(category='INCOTERM').all()
    gl_list = MasterData.query.filter_by(category='GL_ACCOUNT').all()
    house_banks = MasterData.query.filter_by(category='HOUSE_BANK').all()
    tax_types = MasterData.query.filter_by(category='TAX_TYPE').all()
    exemption_reasons = MasterData.query.filter_by(category='EXEMPTION_REASON').all()
    
    all_tax_codes = MasterData.query.filter_by(category='TDS_CODE').all()
    tax_code_map = {}
    for tc in all_tax_codes:
        p = tc.parent_code if tc.parent_code else 'General'
        if p not in tax_code_map: tax_code_map[p] = []
        tax_code_map[p].append({'code': tc.code, 'label': f"{tc.code} - {tc.label}"})

    # --- 3. HANDLE FORM SUBMISSION ---
    if request.method == 'POST':
        if not is_my_turn: return "Unauthorized", 403
        action = request.form.get('action')
        comments = request.form.get('comments', '')

        # =========================================================
        # ACTION: SEND BACK (QUERY)
        # Logic: Save current spot -> Send to Vendor -> Reset to Initiator
        # =========================================================
        if action == 'send_back':
            # 1. Snapshot the current location (if not already at start)
            if req.current_dept_flow != 'INITIATOR_REVIEW':
                req.previous_dept_flow = req.current_dept_flow
                req.previous_step_number = req.current_step_number
                req.previous_finance_stage = req.finance_stage
            
            # 2. Reset workflow to beginning
            req.status = 'PENDING_VENDOR' 
            req.current_dept_flow = 'INITIATOR_REVIEW'
            req.current_step_number = 1 
            req.finance_stage = None 
            
            # 3. Lock/Unlock specific fields
            req.editable_sections = request.form.getlist('unlock_sections[]')

            unlock_sections = req.editable_sections

            flagged_labels = [
                SECTION_LABELS.get(s, s) for s in unlock_sections
            ]

            
            # 4. Audit & Notify
            req.last_query = comments
            log_audit(
                req.id,
                current_user.id,
                'QUERY_RAISED',
                (
                    f"Sent Back from {stage_name}\n"
                    f"Reason: {comments}\n"
                    f"Flagged Sections: {', '.join(flagged_labels) if flagged_labels else 'None'}"
                )
            )

            db.session.commit()
            
            link = url_for('vendor.vendor_portal', token=req.token, _external=True)
            body_html = render_template(
                'email/notification.html',
                req=req,
                subject="Action Required",
                body=(
                    f"<b>Reason:</b><br>{comments}<br><br>"
                    f"<b>Sections requiring correction:</b><br>"
                    "<ul>"
                    + "".join(f"<li>{s}</li>" for s in flagged_labels)
                    + "</ul>"
                ),
                link=link,
                current_year=datetime.now().year
            )

            send_system_email(req.vendor_email, f"Query on {req.request_id}", body_html)
            
            flash("Sent back to vendor successfully.", "warning")
            return redirect(url_for('main.dashboard'))

        # =========================================================
        # ACTION: REJECT
        # =========================================================
        if action == 'reject':
            req.status = 'REJECTED'
            log_audit(req.id, current_user.id, 'REJECTED', f"Reason: {comments}")
            db.session.commit()
            send_status_email(req, req.vendor_email, f"Application Rejected. Reason: {comments}")
            flash("Application rejected.", "error")
            return redirect(url_for('main.dashboard'))

        # =========================================================
        # ACTION: APPROVE (Main Logic)
        # =========================================================
        log_action_name = "APPROVED"
        
        # --- A. INITIATOR REVIEW (The "Gatekeeper") ---
        if req.current_dept_flow == 'INITIATOR_REVIEW':
            # Save Commercial Terms
            req.account_group = request.form.get('account_group')
            req.payment_terms = request.form.get('payment_terms')
            req.purchase_org = request.form.get('purchase_org')
            req.incoterms = request.form.get('incoterms')
            
            log_action_name = "APPROVED_INITIATOR"
            
            # [CRITICAL LOGIC] Check if we need to "Restore" to a later stage
            if req.previous_dept_flow:
                # 1. Audit Log the Skip (For Compliance)
                restore_msg = (
                    f"Workflow restored to Stage: {req.previous_dept_flow} "
                    f"(Step {req.previous_step_number}). "
                    f"Intermediate steps skipped based on prior approval."
                )
                log_audit(req.id, current_user.id, "WORKFLOW_RESTORED", restore_msg)
                
                # 2. Teleport the Request
                req.current_dept_flow = req.previous_dept_flow
                req.current_step_number = req.previous_step_number
                req.finance_stage = req.previous_finance_stage
                
                # 3. Wipe the Snapshot
                req.previous_dept_flow = None
                req.previous_step_number = None
                req.previous_finance_stage = None
            else:
                # Standard Flow: Move to Dept Head
                req.current_dept_flow = 'DEPT'
                req.current_step_number = 1

        # --- B. DEPARTMENT FLOW ---
        elif req.current_dept_flow == 'DEPT':
            # Dynamic Label for Audit
            cat_rule = CategoryRouting.query.filter_by(department=req.initiator_dept, category_name=req.vendor_type).first()
            if cat_rule:
                role_label = f"Category_Approver_L{req.current_step_number}"
            else:
                step = WorkflowStep.query.filter_by(department=req.initiator_dept, step_order=req.current_step_number).first()
                role_label = step.role_label if step else f"STEP_{req.current_step_number}"
            
            log_action_name = f"APPROVED_{role_label.replace(' ', '_').upper()}"

        # --- C. FINANCE FLOW ---
        elif req.finance_stage == 'BILL_PASSING': 
            req.gl_account = request.form.get('gl_account')
            log_action_name = "APPROVED_BILL_PASSING"
            
        elif req.finance_stage == 'TREASURY': 
            req.house_bank = request.form.get('house_bank')
            log_action_name = "APPROVED_TREASURY"
            
        elif req.finance_stage == 'TAX':
            log_action_name = "APPROVED_TAX"
            # (Save Tax Details - Your existing logic)
            for old_tax in req.tax_details: db.session.delete(old_tax)
            # ... [Insert your Tax saving loop here from previous code] ...

        # --- D. IT FLOW ---
        elif req.current_dept_flow == 'IT': 
            req.sap_id = request.form.get('sap_id')
            req.status = 'COMPLETED'
            log_action_name = "COMPLETED_BY_IT"

        # --- SAVE & LOG ---
        log_audit(req.id, current_user.id, log_action_name)
        db.session.commit()

        # =========================================================
        # ROUTING LOGIC (Advance to Next Step)
        # Only run this if we didn't just "Restore" via Initiator
        # =========================================================
        if req.status != 'COMPLETED' and log_action_name != "APPROVED_INITIATOR":
            
            # 1. DEPT ROUTING
            if req.current_dept_flow == 'DEPT':
                cat_rule = CategoryRouting.query.filter_by(department=req.initiator_dept, category_name=req.vendor_type).first()
                
                # Check if there is a Next Step in Dept
                moved_to_next_step = False
                if cat_rule:
                    if req.current_step_number == 1 and cat_rule.l2_head_email:
                        req.current_step_number = 2
                        moved_to_next_step = True
                else:
                    next_step = WorkflowStep.query.filter_by(department=req.initiator_dept, step_order=req.current_step_number + 1).first()
                    if next_step:
                        req.current_step_number += 1
                        moved_to_next_step = True
                
                # If no next step in Dept, move to Finance
                if not moved_to_next_step:
                    req.current_dept_flow = 'FINANCE'
                    req.finance_stage = 'BILL_PASSING'
                    req.current_step_number = 1

            # 2. FINANCE ROUTING
            elif req.current_dept_flow == 'FINANCE':
                if req.finance_stage == 'BILL_PASSING': req.finance_stage = 'TREASURY'
                elif req.finance_stage == 'TREASURY': req.finance_stage = 'TAX'
                elif req.finance_stage == 'TAX': 
                    req.current_dept_flow = 'IT'
                    req.finance_stage = None

        db.session.commit()
        
        # --- NOTIFICATIONS ---
        next_person, next_stage = get_next_approver_email(req)
        if req.status == 'COMPLETED': 
             body_html = render_template('email/notification.html', req=req, subject="Onboarding Complete", body=f"<b>Your Vendor Code: {req.sap_id}</b>", link=None, current_year=datetime.now().year)
             send_system_email(req.vendor_email, "Onboarding Complete", body_html)
        elif next_person: 
            send_status_email(req, next_person, next_stage)

        flash("Request approved successfully.", "success")
        return redirect(url_for('main.dashboard'))
    
    # --- RENDER TEMPLATE ---
    return render_template('main/review.html', req=req, pending_email=pending_email, is_my_turn=is_my_turn, stage_name=stage_name,
                           acc_groups=acc_groups, pay_terms=pay_terms, purch_orgs=purch_orgs, incoterms=incoterms,
                           gl_list=gl_list, house_banks=house_banks, tax_types=tax_types, 
                           tax_code_map=json.dumps(tax_code_map), exemption_reasons=exemption_reasons)


@main_bp.route('/secure-files/<path:filename>')
@login_required
def serve_protected_file(filename):
    authorized_roles = ['admin', 'approver', 'initiator']
    if current_user.role not in authorized_roles and not current_user.is_admin:
         abort(403) 

    if current_app.config.get('USE_S3', False):
        try:
            from app.services.s3_service import S3Service
            s3 = S3Service()
            presigned_url = s3.generate_presigned_url(filename, expiration=60)
            if presigned_url:
                return redirect(presigned_url)
            else:
                abort(404)
        except Exception as e:
            print(f"S3 Error: {e}")
            abort(404)
    else:
        try:
            return send_from_directory(
                current_app.config['UPLOAD_FOLDER'], 
                filename, 
                as_attachment=False 
            )
        except FileNotFoundError:
            abort(404)