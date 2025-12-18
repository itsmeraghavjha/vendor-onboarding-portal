import uuid
from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.extensions import db
from app.models import VendorRequest, MasterData, User
from app.forms import VendorOnboardingForm
from app.utils import save_file, send_status_email

vendor_bp = Blueprint('vendor', __name__)

@vendor_bp.route('/portal/<token>', methods=['GET', 'POST'])
def vendor_portal(token):
    req = VendorRequest.query.filter_by(token=token).first()
    
    # 1. Security & Status Checks
    if not req: 
        return "Invalid Link", 404
    
    # If already submitted, show success page immediately
    if req.status != 'PENDING_VENDOR': 
        return render_template('vendor/success.html', req=req)

    # 2. Initialize Form
    form = VendorOnboardingForm()
    
    # 3. Dynamic Data: Populate State Dropdown from DB
    states = MasterData.query.filter_by(category='REGION').all()
    form.state.choices = [(s.code, s.label) for s in states]

    # 4. Pre-fill Form Data (GET Request)
    # This ensures that if they refresh or come back, their data is visible (if saved previously)
    if request.method == 'GET':
        form.title.data = req.title
        form.trade_name.data = req.trade_name
        form.constitution.data = req.constitution
        form.cin_no.data = req.cin_number
        
        form.contact_name.data = req.contact_person_name
        form.designation.data = req.contact_person_designation
        form.mobile_1.data = req.mobile_number
        form.mobile_2.data = req.mobile_number_2
        form.landline.data = req.landline_number
        form.product_desc.data = req.product_service_description
        
        form.street_1.data = req.street
        form.street_2.data = req.street_2
        form.street_3.data = req.street_3
        form.city.data = req.city
        form.pincode.data = req.postal_code
        form.state.data = req.state # Matches the code value
        
        # Pre-fill Bank Details
        form.bank_name.data = req.bank_name
        form.holder_name.data = req.bank_account_holder_name
        form.acc_no.data = req.bank_account_no
        form.acc_no_confirm.data = req.bank_account_no
        form.ifsc.data = req.bank_ifsc

        # Pre-fill Conditional Fields
        if req.gst_registered: 
            form.gst_reg.data = req.gst_registered
            if req.gst_registered == 'YES':
                form.gst_no.data = req.gst_number

        if req.msme_registered: 
            form.msme_reg.data = req.msme_registered
            if req.msme_registered == 'YES':
                form.msme_number.data = req.msme_number
                form.msme_type.data = req.msme_type
        
        if req.tds_exemption_number:
            form.tds_cert_no.data = req.tds_exemption_number
            
        if req.pan_number:
            form.pan_no.data = req.pan_number

    # 5. Handle Submission (POST Request)
    if form.validate_on_submit():
        try:
            # --- MAP FORM TO DATABASE MODEL ---
            
            # Step 1: General
            req.title = form.title.data
            req.vendor_name_basic = request.form.get('legal_name') # Hidden field (readonly)
            req.trade_name = form.trade_name.data
            req.constitution = form.constitution.data
            req.cin_number = form.cin_no.data
            
            req.contact_person_name = form.contact_name.data
            req.contact_person_designation = form.designation.data
            req.mobile_number = form.mobile_1.data
            req.mobile_number_2 = form.mobile_2.data
            req.landline_number = form.landline.data
            req.product_service_description = form.product_desc.data
            
            req.street = form.street_1.data
            req.street_2 = form.street_2.data
            req.street_3 = form.street_3.data
            req.city = form.city.data
            req.postal_code = form.pincode.data
            req.state = form.state.data

            # Step 2: Tax & Compliance + File Uploads
            req.gst_registered = form.gst_reg.data
            if form.gst_reg.data == 'YES':
                req.gst_number = form.gst_no.data
                if form.gst_file.data:
                    req.gst_file_path = save_file(form.gst_file.data, 'GST')

            req.pan_number = form.pan_no.data
            if form.pan_file.data:
                req.pan_file_path = save_file(form.pan_file.data, 'PAN')

            req.msme_registered = form.msme_reg.data
            if form.msme_reg.data == 'YES':
                req.msme_number = form.msme_number.data
                req.msme_type = form.msme_type.data
                if form.msme_file.data:
                    req.msme_file_path = save_file(form.msme_file.data, 'MSME')

            req.tds_exemption_number = form.tds_cert_no.data
            if form.tds_file.data:
                req.tds_exemption_file_path = save_file(form.tds_file.data, 'TDS')

            # Step 3: Bank Details
            req.bank_name = form.bank_name.data
            req.bank_account_holder_name = form.holder_name.data
            req.bank_account_no = form.acc_no.data
            req.bank_ifsc = form.ifsc.data
            if form.bank_file.data:
                req.bank_proof_file_path = save_file(form.bank_file.data, 'BANK')

            # --- WORKFLOW TRIGGER ---
            req.status = 'PENDING_APPROVAL'
            req.current_dept_flow = 'INITIATOR_REVIEW'
            db.session.commit()
            
            # Notify the Initiator
            initiator = db.session.get(User, req.initiator_id)
            if initiator:
                send_status_email(req, initiator.email, "Vendor Submitted (Ready for Review)")

            # Render Success Page
            return render_template('vendor/success.html', req=req)

        except Exception as e:
            db.session.rollback()
            flash(f"System Error: {str(e)}", "error")
            return redirect(request.url)

    # 6. Render Portal (Initial Load or Validation Error)
    return render_template('vendor/portal.html', req=req, form=form)