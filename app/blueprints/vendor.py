import uuid
from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.extensions import db
from app.models import VendorRequest, MasterData, User, VendorTaxDetail
from app.forms import VendorOnboardingForm
from app.utils import save_file, send_status_email, log_audit # <--- Import log_audit

vendor_bp = Blueprint('vendor', __name__)

@vendor_bp.route('/portal/<token>', methods=['GET', 'POST'])
def vendor_portal(token):
    req = VendorRequest.query.filter_by(token=token).first()
    
    if not req: 
        return "Invalid Link", 404
    
    if req.status != 'PENDING_VENDOR': 
        return render_template('vendor/success.html', req=req)

    form = VendorOnboardingForm()
    states = MasterData.query.filter_by(category='REGION').all()
    form.state.choices = [(s.code, s.label) for s in states]

    # Pre-fill (GET)
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
        form.street_4.data = req.street_4
        form.city.data = req.city
        form.pincode.data = req.postal_code
        form.state.data = req.state
        
        form.bank_name.data = req.bank_name
        form.holder_name.data = req.bank_account_holder_name
        form.acc_no.data = req.bank_account_no
        form.acc_no_confirm.data = req.bank_account_no
        form.ifsc.data = req.bank_ifsc

        if req.gst_registered: 
            form.gst_reg.data = req.gst_registered
            if req.gst_registered == 'YES':
                form.gst_no.data = req.gst_number

        if req.msme_registered: 
            form.msme_reg.data = req.msme_registered
            if req.msme_registered == 'YES':
                form.msme_number.data = req.msme_number
                form.msme_type.data = req.msme_type
        
        wht_tax = next((t for t in req.tax_details if t.tax_category == 'WHT'), None)
        if wht_tax and wht_tax.cert_no:
            form.tds_cert_no.data = wht_tax.cert_no
            
        if req.pan_number:
            form.pan_no.data = req.pan_number

    # Handle Submission (POST)
    if form.validate_on_submit():
        try:
            # 1. General
            req.title = form.title.data
            req.vendor_name_basic = request.form.get('legal_name')
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
            req.street_4 = form.street_4.data
            req.city = form.city.data
            req.postal_code = form.pincode.data
            req.state = form.state.data

            # 2. Tax & Compliance
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

            # Tax Details
            for old_tax in req.tax_details:
                db.session.delete(old_tax)

            if form.tds_cert_no.data or form.tds_file.data:
                if form.tds_file.data:
                     save_file(form.tds_file.data, 'TDS')

                wht = VendorTaxDetail(
                    vendor_request=req,
                    tax_category='WHT',
                    tax_code='Z004',         
                    recipient_type='CO',     
                    cert_no=form.tds_cert_no.data,
                    start_date='01.04.2024', 
                    end_date='31.03.2025'
                )
                db.session.add(wht)

            # 3. Bank Details
            req.bank_name = form.bank_name.data
            req.bank_account_holder_name = form.holder_name.data
            req.bank_account_no = form.acc_no.data
            req.bank_ifsc = form.ifsc.data
            if form.bank_file.data:
                req.bank_proof_file_path = save_file(form.bank_file.data, 'BANK')

            # Workflow
            req.status = 'PENDING_APPROVAL'
            req.current_dept_flow = 'INITIATOR_REVIEW'
            
            # --- NEW: Log the vendor action ---
            # Use None for user_id since this is an external user
            log_audit(req.id, None, 'SUBMITTED_BY_VENDOR', "Vendor filled the form")
            # ----------------------------------

            db.session.commit()
            
            initiator = db.session.get(User, req.initiator_id)
            if initiator:
                send_status_email(req, initiator.email, "Vendor Submitted (Ready for Review)")

            return render_template('vendor/success.html', req=req)

        except Exception as e:
            db.session.rollback()
            flash(f"System Error: {str(e)}", "error")
            return redirect(request.url)

    return render_template('vendor/portal.html', req=req, form=form)