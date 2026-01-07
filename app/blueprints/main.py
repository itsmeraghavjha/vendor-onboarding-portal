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
from app.services.admin_service import admin_service

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index(): 
    return redirect(url_for('auth.login'))

# @main_bp.route('/dashboard')
# @login_required
# def dashboard():
#     # 1. Fetch Requests based on Role
#     if current_user.role == 'admin':
#         all_reqs = VendorRequest.query.order_by(VendorRequest.created_at.desc()).all()
#     elif current_user.role == 'initiator':
#         all_reqs = VendorRequest.query.filter_by(initiator_id=current_user.id).order_by(VendorRequest.created_at.desc()).all()
#     else:
#         if current_user.department in ['Finance', 'IT', 'HR']:
#             all_reqs = VendorRequest.query.order_by(VendorRequest.created_at.desc()).all()
#         else:
#             all_reqs = VendorRequest.query.filter_by(initiator_dept=current_user.department).order_by(VendorRequest.created_at.desc()).all()

#     # 2. Identify "Action Required" items
#     pending_items = []
#     for r in all_reqs:
#         r.pending_action = False 
#         if r.status in ['DRAFT', 'REJECTED', 'COMPLETED', 'PENDING_VENDOR']: continue
            
#         pending_email, stage_name = get_next_approver_email(r)
        
#         if pending_email and current_user.email:
#             if pending_email.strip().lower() == current_user.email.strip().lower():
#                 r.pending_action = True
#                 pending_items.append(r)

#     # 3. Calculate Stats
#     stats = {
#         'total': len(all_reqs),
#         'action_required': len(pending_items),
#         'completed': sum(1 for r in all_reqs if r.status == 'COMPLETED'),
#         'rejected': sum(1 for r in all_reqs if r.status == 'REJECTED'),
#         'in_process': sum(1 for r in all_reqs if r.status not in ['DRAFT', 'COMPLETED', 'REJECTED']),
#         'stuck_dept': sum(1 for r in all_reqs if r.current_dept_flow == 'DEPT' and r.status == 'PENDING_APPROVAL'),
#         'stuck_finance': sum(1 for r in all_reqs if r.current_dept_flow == 'FINANCE' and r.status == 'PENDING_APPROVAL'),
#         'stuck_it': sum(1 for r in all_reqs if r.current_dept_flow == 'IT' and r.status == 'PENDING_APPROVAL'),
#     }

#     # 4. Categories for Modal
#     dept_categories = []
#     if current_user.department:
#         rules = CategoryRouting.query.filter_by(department=current_user.department).all()
#         dept_categories = sorted(list(set([r.category_name for r in rules])))
#         if not dept_categories: dept_categories = ["General Goods", "Services"]

#     return render_template('main/dashboard.html', 
#                            requests=all_reqs, 
#                            stats=stats,
#                            dept_categories=dept_categories)

# @main_bp.route('/create_request', methods=['POST'])
# @login_required
# def create_request():
#     vendor_type = request.form.get('vendor_type')
#     if current_user.assigned_category: vendor_type = current_user.assigned_category
    
#     new_token = uuid.uuid4().hex 
#     new_req = VendorRequest(
#         request_id=f"VR-{uuid.uuid4().hex[:6].upper()}",
#         token=new_token,
#         initiator_id=current_user.id,
#         initiator_dept=current_user.department, 
#         vendor_name_basic=request.form['vendor_name'],
#         vendor_email=request.form['vendor_email'],
#         vendor_type=vendor_type,
#         status='PENDING_VENDOR',
#         current_dept_flow='INITIATOR',
#         account_group=request.form.get('account_group', 'ZDOM') 
#     )
#     db.session.add(new_req)
#     db.session.commit()
    
#     log_audit(new_req.id, current_user.id, 'INITIATED', "Vendor Request Created")
    
#     portal_link = url_for('vendor.vendor_portal', token=new_req.token, _external=True)
#     subject = f"Invitation: Register with Heritage Foods ({new_req.request_id})"
    
#     body_html = render_template('email/notification.html',
#         req=new_req,
#         subject="Vendor Registration Invitation",
#         body=f"Dear {new_req.vendor_name_basic},<br><br>You have been invited to register with Heritage Foods. Please click the button below to start your onboarding process.",
#         link=portal_link,
#         current_year=datetime.now().year
#     )
    
#     send_system_email(new_req.vendor_email, subject, body_html)
    
#     flash('Invite sent to vendor.', 'success')
#     return redirect(url_for('main.dashboard'))

@main_bp.route('/download_sap/<int:req_id>')
@login_required
def download_sap_report(req_id):
    """Downloads the SAP CSV for a SINGLE request."""
    req = db.session.get(VendorRequest, req_id)
    if not req: return "Not Found", 404

    csv_output = admin_service.generate_sap_csv([req.id])

    return Response(
        csv_output.getvalue(), 
        mimetype='text/csv', 
        headers={"Content-Disposition": f"attachment; filename=SAP_Upload_{req.request_id}.csv"}
    )

# @main_bp.route('/review/<int:req_id>', methods=['GET', 'POST'])
# @login_required
# def review_request(req_id):
#     req = db.session.get(VendorRequest, req_id)
#     if not req: return "Not Found", 404

#     pending_email, stage_name = get_next_approver_email(req)
#     is_my_turn = False
    
#     # Check permissions
#     if current_user.role == 'admin':
#         is_my_turn = True
#     elif pending_email and current_user.email:
#         if pending_email.strip().lower() == current_user.email.strip().lower():
#             is_my_turn = True
    
#     # Prevent Initiator from acting if it is with Vendor (Extra Safety Check)
#     if req.status == 'PENDING_VENDOR' and current_user.role == 'initiator':
#         is_my_turn = False

#     # Master Data Lookups
#     acc_groups = MasterData.query.filter_by(category='ACCOUNT_GROUP').all()
#     pay_terms = MasterData.query.filter_by(category='PAYMENT_TERM').all()
#     purch_orgs = MasterData.query.filter_by(category='PURCHASE_ORG').all()
#     incoterms = MasterData.query.filter_by(category='INCOTERM').all()
#     gl_list = MasterData.query.filter_by(category='GL_ACCOUNT').all()
#     house_banks = MasterData.query.filter_by(category='HOUSE_BANK').all()
#     tax_types = MasterData.query.filter_by(category='TAX_TYPE').all()
#     exemption_reasons = MasterData.query.filter_by(category='EXEMPTION_REASON').all()
    
#     all_tax_codes = MasterData.query.filter_by(category='TDS_CODE').all()
#     tax_code_map = {}
#     for tc in all_tax_codes:
#         p = tc.parent_code if tc.parent_code else 'General'
#         if p not in tax_code_map: tax_code_map[p] = []
#         # UPDATED: LABEL NOW INCLUDES DESCRIPTION
#         tax_code_map[p].append({'code': tc.code, 'label': f"{tc.code} - {tc.label}"})

#     if request.method == 'POST':
#         if not is_my_turn: return "Unauthorized", 403
#         action = request.form.get('action')
#         comments = request.form.get('comments', '')

#         # --- 1. HANDLE SEND BACK (QUERY) ---
#         if action == 'send_back':
#             # RESET ALL STATE FLAGS TO BEGINNING
#             req.status = 'PENDING_VENDOR' # This prevents Initiator approval
#             req.current_dept_flow = 'INITIATOR_REVIEW'
#             req.current_step_number = 1 
#             req.finance_stage = None 
            
#             req.last_query = comments
#             log_audit(req.id, current_user.id, 'QUERY_RAISED', f"Query: {comments}")
#             db.session.commit()
            
#             link = url_for('vendor.vendor_portal', token=req.token, _external=True)
#             subject = f"Query on {req.request_id}"
#             body_html = render_template('email/notification.html', req=req, subject="Application Sent Back", body=f"Query: {comments}", link=link, current_year=datetime.now().year)
#             send_system_email(req.vendor_email, subject, body_html)
#             flash("Sent back.", "warning"); return redirect(url_for('main.dashboard'))

#         # --- 2. HANDLE REJECTION ---
#         if action == 'reject':
#             req.status = 'REJECTED'
#             log_audit(req.id, current_user.id, 'REJECTED', f"Reason: {comments}")
#             db.session.commit()
#             send_status_email(req, req.vendor_email, f"Rejected: {comments}")
#             flash("Rejected.", "error"); return redirect(url_for('main.dashboard'))

#         # --- 3. APPROVAL LOGIC ---
#         log_action_name = "APPROVED"
#         if req.current_dept_flow == 'INITIATOR_REVIEW':
#             req.account_group = request.form.get('account_group')
#             req.payment_terms = request.form.get('payment_terms')
#             req.purchase_org = request.form.get('purchase_org')
#             req.incoterms = request.form.get('incoterms')
#             log_action_name = "APPROVED_INITIATOR"
        
#         elif req.current_dept_flow == 'DEPT':
#             step = WorkflowStep.query.filter_by(department=req.initiator_dept, step_order=req.current_step_number).first()
#             role_label = step.role_label if step else f"STEP_{req.current_step_number}"
#             log_action_name = f"APPROVED_{role_label.replace(' ', '_').upper()}"

#         elif req.current_dept_flow == 'IT': 
#             req.sap_id = request.form.get('sap_id')
#             req.status = 'COMPLETED'
#             log_action_name = "COMPLETED_BY_IT"

#         elif req.finance_stage == 'BILL_PASSING': 
#             req.gl_account = request.form.get('gl_account')
#             log_action_name = "APPROVED_BILL_PASSING"
            
#         elif req.finance_stage == 'TREASURY': 
#             req.house_bank = request.form.get('house_bank')
#             log_action_name = "APPROVED_TREASURY"
            
#         elif req.finance_stage == 'TAX':
#             log_action_name = "APPROVED_TAX"
#             for old_tax in req.tax_details: db.session.delete(old_tax)
            
#             # Save WHT (Tax 1)
#             t1_types = request.form.getlist('tax1_type[]')
#             t1_codes = request.form.getlist('tax1_code[]')
#             t1_recip = request.form.getlist('tax1_recipient_type[]')
#             t1_reas = request.form.getlist('tax1_exemption_reason[]')
#             t1_cert = request.form.getlist('tax1_cert_no[]')
#             t1_rate = request.form.getlist('tax1_rate[]')
#             t1_start = request.form.getlist('tax1_start_date[]')
#             t1_end = request.form.getlist('tax1_end_date[]')

#             for i in range(len(t1_types)):
#                 if t1_types[i]:
#                     db.session.add(VendorTaxDetail(
#                         vendor_request=req, tax_category='WHT', tax_code=t1_codes[i], recipient_type=t1_recip[i],
#                         exemption_reason=t1_reas[i], cert_no=t1_cert[i], rate=t1_rate[i], start_date=t1_start[i], end_date=t1_end[i]
#                     ))

#             # Save 194Q (Tax 2)
#             t2_sec = request.form.getlist('tax2_section_code[]')
#             t2_cert = request.form.getlist('tax2_cert_no[]')
#             t2_rate = request.form.getlist('tax2_rate[]')
#             t2_start = request.form.getlist('tax2_start_date[]')
#             t2_end = request.form.getlist('tax2_end_date[]')
#             t2_code = request.form.getlist('tax2_code[]')
#             t2_thresh = request.form.getlist('tax2_threshold_amount[]')

#             for i in range(len(t2_sec)):
#                 if t2_sec[i]:
#                     db.session.add(VendorTaxDetail(
#                         vendor_request=req, tax_category='194Q', section_code=t2_sec[i], cert_no=t2_cert[i],
#                         rate=t2_rate[i], start_date=t2_start[i], end_date=t2_end[i], tax_code=t2_code[i], threshold=t2_thresh[i]
#                     ))

#         log_audit(req.id, current_user.id, log_action_name)

#         # --- 4. TRANSITIONS ---
#         if req.status != 'COMPLETED':
#             if req.current_dept_flow == 'INITIATOR_REVIEW':
#                 req.current_dept_flow = 'DEPT'; req.current_step_number = 1
            
#             elif req.current_dept_flow == 'DEPT':
#                 next_step = WorkflowStep.query.filter_by(department=req.initiator_dept, step_order=req.current_step_number + 1).first()
#                 if next_step: req.current_step_number += 1
#                 else: req.current_dept_flow = 'FINANCE'; req.finance_stage = 'BILL_PASSING'
            
#             elif req.current_dept_flow == 'FINANCE':
#                 if req.finance_stage == 'BILL_PASSING': req.finance_stage = 'TREASURY'
#                 elif req.finance_stage == 'TREASURY': req.finance_stage = 'TAX'
#                 elif req.finance_stage == 'TAX': req.current_dept_flow = 'IT'; req.finance_stage = None

#         db.session.commit()
        
#         next_person, next_stage = get_next_approver_email(req)
#         if req.status == 'COMPLETED': 
#              body_html = render_template('email/notification.html', req=req, subject="Onboarding Complete", body=f"<b>Your Vendor Code: {req.sap_id}</b>", link=None, current_year=datetime.now().year)
#              send_system_email(req.vendor_email, "Onboarding Complete", body_html)
#         elif next_person: 
#             send_status_email(req, next_person, next_stage)

#         flash("Approved.", "success"); return redirect(url_for('main.dashboard'))

#     return render_template('main/review.html', req=req, pending_email=pending_email, is_my_turn=is_my_turn, stage_name=stage_name,
#                            acc_groups=acc_groups, pay_terms=pay_terms, purch_orgs=purch_orgs, incoterms=incoterms,
#                            gl_list=gl_list, house_banks=house_banks, tax_types=tax_types, 
#                            tax_code_map=json.dumps(tax_code_map), exemption_reasons=exemption_reasons)



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

    # 2. Identify "Action Required" items
    pending_items = []
    for r in all_reqs:
        r.pending_action = False 
        if r.status in ['DRAFT', 'REJECTED', 'COMPLETED', 'PENDING_VENDOR']: continue
            
        pending_email, stage_name = get_next_approver_email(r)
        
        if pending_email and current_user.email:
            if pending_email.strip().lower() == current_user.email.strip().lower():
                r.pending_action = True
                pending_items.append(r)

    # 3. Calculate Stats
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

    # 4. Categories for Modal (UPDATED)
    # Always start with "Standard" as fallback
    dept_categories = ["Standard"]
    if current_user.department:
        # Fetch all categories mapped to this department in the Matrix
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
    # UPDATED: Do not force assigned_category. Trust the form or default to 'Standard'.
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
        vendor_type=vendor_type, # Stores 'Hardware', 'Software', or 'Standard'
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

    pending_email, stage_name = get_next_approver_email(req)
    is_my_turn = False
    
    # Check permissions
    if current_user.role == 'admin':
        is_my_turn = True
    elif pending_email and current_user.email:
        if pending_email.strip().lower() == current_user.email.strip().lower():
            is_my_turn = True
    
    # Prevent Initiator from acting if it is with Vendor
    if req.status == 'PENDING_VENDOR' and current_user.role == 'initiator':
        is_my_turn = False

    # Master Data Lookups
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

    if request.method == 'POST':
        if not is_my_turn: return "Unauthorized", 403
        action = request.form.get('action')
        comments = request.form.get('comments', '')

        # --- 1. HANDLE SEND BACK (QUERY) ---
        if action == 'send_back':
            req.status = 'PENDING_VENDOR' 
            req.current_dept_flow = 'INITIATOR_REVIEW'
            req.current_step_number = 1 
            req.finance_stage = None 
            
            req.last_query = comments
            log_audit(req.id, current_user.id, 'QUERY_RAISED', f"Query: {comments}")
            db.session.commit()
            
            link = url_for('vendor.vendor_portal', token=req.token, _external=True)
            subject = f"Query on {req.request_id}"
            body_html = render_template('email/notification.html', req=req, subject="Application Sent Back", body=f"Query: {comments}", link=link, current_year=datetime.now().year)
            send_system_email(req.vendor_email, subject, body_html)
            flash("Sent back.", "warning"); return redirect(url_for('main.dashboard'))

        # --- 2. HANDLE REJECTION ---
        if action == 'reject':
            req.status = 'REJECTED'
            log_audit(req.id, current_user.id, 'REJECTED', f"Reason: {comments}")
            db.session.commit()
            send_status_email(req, req.vendor_email, f"Rejected: {comments}")
            flash("Rejected.", "error"); return redirect(url_for('main.dashboard'))

        # --- 3. APPROVAL LOGIC ---
        log_action_name = "APPROVED"
        if req.current_dept_flow == 'INITIATOR_REVIEW':
            req.account_group = request.form.get('account_group')
            req.payment_terms = request.form.get('payment_terms')
            req.purchase_org = request.form.get('purchase_org')
            req.incoterms = request.form.get('incoterms')
            log_action_name = "APPROVED_INITIATOR"
        
        elif req.current_dept_flow == 'DEPT':
            # UPDATED: Log correct role based on Hybrid Flow
            cat_rule = CategoryRouting.query.filter_by(department=req.initiator_dept, category_name=req.vendor_type).first()
            if cat_rule:
                role_label = f"Category L{req.current_step_number}"
            else:
                step = WorkflowStep.query.filter_by(department=req.initiator_dept, step_order=req.current_step_number).first()
                role_label = step.role_label if step else f"STEP_{req.current_step_number}"
            
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
            for old_tax in req.tax_details: db.session.delete(old_tax)
            
            # Save WHT (Tax 1)
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
                    db.session.add(VendorTaxDetail(
                        vendor_request=req, tax_category='WHT', tax_code=t1_codes[i], recipient_type=t1_recip[i],
                        exemption_reason=t1_reas[i], cert_no=t1_cert[i], rate=t1_rate[i], start_date=t1_start[i], end_date=t1_end[i]
                    ))

            # Save 194Q (Tax 2)
            t2_sec = request.form.getlist('tax2_section_code[]')
            t2_cert = request.form.getlist('tax2_cert_no[]')
            t2_rate = request.form.getlist('tax2_rate[]')
            t2_start = request.form.getlist('tax2_start_date[]')
            t2_end = request.form.getlist('tax2_end_date[]')
            t2_code = request.form.getlist('tax2_code[]')
            t2_thresh = request.form.getlist('tax2_threshold_amount[]')

            for i in range(len(t2_sec)):
                if t2_sec[i]:
                    db.session.add(VendorTaxDetail(
                        vendor_request=req, tax_category='194Q', section_code=t2_sec[i], cert_no=t2_cert[i],
                        rate=t2_rate[i], start_date=t2_start[i], end_date=t2_end[i], tax_code=t2_code[i], threshold=t2_thresh[i]
                    ))

        log_audit(req.id, current_user.id, log_action_name)

        # --- 4. TRANSITIONS (UPDATED FOR HYBRID FLOW) ---
        if req.status != 'COMPLETED':
            if req.current_dept_flow == 'INITIATOR_REVIEW':
                req.current_dept_flow = 'DEPT'; req.current_step_number = 1
            
            elif req.current_dept_flow == 'DEPT':
                # Check for Category Matrix Rule First
                cat_rule = CategoryRouting.query.filter_by(
                    department=req.initiator_dept, 
                    category_name=req.vendor_type
                ).first()
                
                if cat_rule:
                    # MATRIX PATH (L1 -> L2)
                    if req.current_step_number == 1:
                        # If L2 exists in matrix, go to L2. Else go to Finance.
                        if cat_rule.l2_head_email:
                            req.current_step_number = 2
                        else:
                            req.current_dept_flow = 'FINANCE'; req.finance_stage = 'BILL_PASSING'
                    else:
                        # If at L2 (or greater), done with Matrix -> Finance
                        req.current_dept_flow = 'FINANCE'; req.finance_stage = 'BILL_PASSING'
                else:
                    # STANDARD PATH (Generic Steps)
                    next_step = WorkflowStep.query.filter_by(department=req.initiator_dept, step_order=req.current_step_number + 1).first()
                    if next_step: 
                        req.current_step_number += 1
                    else: 
                        req.current_dept_flow = 'FINANCE'; req.finance_stage = 'BILL_PASSING'
            
            elif req.current_dept_flow == 'FINANCE':
                if req.finance_stage == 'BILL_PASSING': req.finance_stage = 'TREASURY'
                elif req.finance_stage == 'TREASURY': req.finance_stage = 'TAX'
                elif req.finance_stage == 'TAX': req.current_dept_flow = 'IT'; req.finance_stage = None

        db.session.commit()
        
        next_person, next_stage = get_next_approver_email(req)
        if req.status == 'COMPLETED': 
             body_html = render_template('email/notification.html', req=req, subject="Onboarding Complete", body=f"<b>Your Vendor Code: {req.sap_id}</b>", link=None, current_year=datetime.now().year)
             send_system_email(req.vendor_email, "Onboarding Complete", body_html)
        elif next_person: 
            send_status_email(req, next_person, next_stage)

        flash("Approved.", "success"); return redirect(url_for('main.dashboard'))

    return render_template('main/review.html', req=req, pending_email=pending_email, is_my_turn=is_my_turn, stage_name=stage_name,
                           acc_groups=acc_groups, pay_terms=pay_terms, purch_orgs=purch_orgs, incoterms=incoterms,
                           gl_list=gl_list, house_banks=house_banks, tax_types=tax_types, 
                           tax_code_map=json.dumps(tax_code_map), exemption_reasons=exemption_reasons)