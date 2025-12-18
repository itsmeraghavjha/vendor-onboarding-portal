import uuid
import json
import csv
import io
from datetime import datetime # NEW IMPORT
from flask import Blueprint, render_template, request, redirect, url_for, flash, Response
from flask_login import login_required, current_user
from app.models import VendorRequest, CategoryRouting, WorkflowStep, MasterData
from app.extensions import db
from app.utils import send_status_email, send_system_email, get_next_approver_email

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index(): 
    return redirect(url_for('auth.login'))

@main_bp.route('/dashboard')
@login_required
def dashboard():
    all_reqs = VendorRequest.query.order_by(VendorRequest.created_at.desc()).all()
    my_items = []
    
    if current_user.role == 'admin':
        my_items = all_reqs
    elif current_user.role == 'initiator':
        my_items = [r for r in all_reqs if r.initiator_id == current_user.id]
    else:
        for r in all_reqs:
            if r.status in ['DRAFT', 'REJECTED', 'COMPLETED']: continue
            pending_email, stage_name = get_next_approver_email(r)
            if pending_email and current_user.email:
                if pending_email.strip().lower() == current_user.email.strip().lower():
                    my_items.append(r)

    dept_categories = []
    if current_user.department:
        rules = CategoryRouting.query.filter_by(department=current_user.department).all()
        dept_categories = sorted(list(set([r.category_name for r in rules])))
        if not dept_categories: dept_categories = ["General Goods", "Services"]

    return render_template('main/dashboard.html', requests=my_items, dept_categories=dept_categories, all_requests=all_reqs)

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
    db.session.commit()
    
    # --- FIX: Render the Template for Invitation Email ---
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
    req = db.session.get(VendorRequest, req_id)
    if not req: return "Not Found", 404

    t1 = req.get_tax1_rows()
    t1 = t1[0] if t1 else {}
    t2 = req.get_tax2_rows()
    t2 = t2[0] if t2 else {}

    headers = [
        "Vendor Account Group", "Title", "Name 1 (Legal Name)", "Name 2 (Trade Name)",
        "Street", "Street 2", "Street 3", "City", "Postal Code", "Region",
        "Contact Person Name", "Mobile Number 1", "Mobile Number 2", "Landline No", "E-Mail Address",
        "GST Number", "PAN Number", "MSME Number", "MSME Type",
        "IFSC Code", "Bank Account No", "Account Holder Name",
        "GL Account", "House Bank", "Payment Terms", "Purch. Org", "Inco Terms",
        "Withholding Tax Type - 1", "Withholding Tax Code - 1", "Subject to W/Tax", "Recipient Type",
        "Exemption Cert No. - 1", "Exemption Rate - 1", "Exemption Start - 1", "Exemption End - 1", "Exemption Reason - 1",
        "Section Code", "Exemption Cert No. - 2", "Exemption Rate - 2", "Exemption Start - 2", "Exemption End - 2", 
        "Exemption Reason - 2", "Withholding Tax Type - 2", "Withholding Tax Code - 2", "Exemption Thr Amt", "Currency"
    ]

    row = [
        req.account_group, req.title, req.vendor_name_basic, req.trade_name,
        req.street, req.street_2, req.street_3, req.city, req.postal_code, req.region_code,
        req.contact_person_name, req.mobile_number, req.mobile_number_2, req.landline_number, req.vendor_email,
        req.gst_number, req.pan_number, req.msme_number, req.msme_type,
        req.bank_ifsc, req.bank_account_no, req.bank_account_holder_name,
        req.gl_account, req.house_bank, req.payment_terms, req.purchase_org, req.incoterms,
        t1.get('type',''), t1.get('code',''), 'X' if t1.get('subject')=='1' else '', t1.get('recipient',''),
        t1.get('cert',''), t1.get('rate',''), t1.get('start',''), t1.get('end',''), t1.get('reason',''),
        t2.get('section',''), t2.get('cert',''), t2.get('rate',''), t2.get('start',''), t2.get('end',''),
        'T7', t2.get('type',''), t2.get('code',''), t2.get('thresh',''), 'INR'
    ]

    def generate():
        f = io.StringIO()
        w = csv.writer(f)
        w.writerow(headers)
        w.writerow(row)
        yield f.getvalue()

    return Response(generate(), mimetype='text/csv', 
                    headers={"Content-Disposition": f"attachment; filename=SAP_Upload_{req.request_id}.csv"})


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
            
            # --- FIX: Render Template for Query Email ---
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
            req.status = 'REJECTED'; db.session.commit()
            send_status_email(req, req.vendor_email, f"Rejected: {comments}")
            flash("Rejected.", "error"); return redirect(url_for('main.dashboard'))

        if req.current_dept_flow == 'INITIATOR_REVIEW':
            req.account_group = request.form.get('account_group')
            req.payment_terms = request.form.get('payment_terms')
            req.purchase_org = request.form.get('purchase_org')
            req.incoterms = request.form.get('incoterms')
        
        if req.current_dept_flow == 'IT': 
            req.sap_id = request.form.get('sap_id')
            req.status = 'COMPLETED'

        if req.finance_stage == 'BILL_PASSING': req.gl_account = request.form.get('gl_account')
        elif req.finance_stage == 'TREASURY': req.house_bank = request.form.get('house_bank')
        elif req.finance_stage == 'TAX':
            # Tax 1 Logic
            t1_types = request.form.getlist('tax1_type[]')
            t1_codes = request.form.getlist('tax1_code[]')
            t1_subj = request.form.getlist('tax1_subject_hidden[]')
            t1_recip = request.form.getlist('tax1_recipient_type[]')
            t1_reas = request.form.getlist('tax1_exemption_reason[]')
            t1_cert = request.form.getlist('tax1_cert_no[]')
            t1_rate = request.form.getlist('tax1_rate[]')
            t1_start = request.form.getlist('tax1_start_date[]')
            t1_end = request.form.getlist('tax1_end_date[]')

            rows1 = []
            for i in range(len(t1_types)):
                if t1_types[i]:
                    rows1.append({
                        'type': t1_types[i], 'code': t1_codes[i] if i < len(t1_codes) else '',
                        'subject': t1_subj[i] if i < len(t1_subj) else '0',
                        'recipient': t1_recip[i] if i < len(t1_recip) else '',
                        'reason': t1_reas[i] if i < len(t1_reas) else '',
                        'cert': t1_cert[i] if i < len(t1_cert) else '',
                        'rate': t1_rate[i] if i < len(t1_rate) else '',
                        'start': t1_start[i] if i < len(t1_start) else '',
                        'end': t1_end[i] if i < len(t1_end) else ''
                    })
            req.tax1_data = json.dumps(rows1)

            # Tax 2 Logic
            t2_sec = request.form.getlist('tax2_section_code[]')
            t2_cert = request.form.getlist('tax2_cert_no[]')
            t2_rate = request.form.getlist('tax2_rate[]')
            t2_start = request.form.getlist('tax2_start_date[]')
            t2_end = request.form.getlist('tax2_end_date[]')
            t2_type = request.form.getlist('tax2_type[]')
            t2_code = request.form.getlist('tax2_code[]')
            t2_thresh = request.form.getlist('tax2_threshold_amount[]')

            rows2 = []
            for i in range(len(t2_sec)):
                if t2_sec[i]:
                    rows2.append({
                        'section': t2_sec[i], 'cert': t2_cert[i] if i < len(t2_cert) else '',
                        'rate': t2_rate[i] if i < len(t2_rate) else '',
                        'start': t2_start[i] if i < len(t2_start) else '',
                        'end': t2_end[i] if i < len(t2_end) else '',
                        'type': t2_type[i] if i < len(t2_type) else '',
                        'code': t2_code[i] if i < len(t2_code) else '',
                        'thresh': t2_thresh[i] if i < len(t2_thresh) else ''
                    })
            req.tax2_data = json.dumps(rows2)

        if req.status != 'COMPLETED':
            if req.current_dept_flow == 'INITIATOR_REVIEW':
                req.current_dept_flow = 'DEPT'; req.current_step_number = 1
            elif req.current_dept_flow == 'DEPT':
                next_step = WorkflowStep.query.filter_by(department=req.initiator_dept, step_order=req.current_step_number + 1).first()
                if next_step: req.current_step_number += 1
                else: req.current_dept_flow = 'FINANCE'; req.finance_stage = 'BILL_PASSING'
            elif req.current_dept_flow == 'FINANCE':
                if req.finance_stage == 'BILL_PASSING': req.finance_stage = 'TREASURY'
                elif req.finance_stage == 'TREASURY': req.finance_stage = 'TAX'
                elif req.finance_stage == 'TAX': req.current_dept_flow = 'IT'; req.finance_stage = None

        db.session.commit()
        
        next_person, next_stage = get_next_approver_email(req)
        
        # --- FIX: Render Template for Completion Email ---
        if req.status == 'COMPLETED': 
             subject = "Onboarding Complete"
             body_html = render_template('email/notification.html',
                req=req,
                subject=subject,
                body=f"Congratulations! Your onboarding is complete.<br><br><b>Your Vendor Code: {req.sap_id}</b>",
                link=None, # Optional: could link to login
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