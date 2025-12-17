import uuid
from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.extensions import db
from app.models import VendorRequest, MasterData
from app.utils import save_file, send_status_email

vendor_bp = Blueprint('vendor', __name__)

@vendor_bp.route('/portal/<token>', methods=['GET', 'POST'])
def vendor_portal(token):
    req = VendorRequest.query.filter_by(token=token).first()
    
    if not req: return "Invalid Link", 404
    if req.status != 'PENDING_VENDOR': return render_template('vendor_success.html', req=req)

    # UPDATED DROPDOWNS
    titles = ['Mr', 'Ms', 'M/s', 'Dr']
    
    # Clearly defined options to trigger CIN logic
    constitutions = [
        'Proprietorship', 
        'Partnership', 
        'LLP (Limited Liability Partnership)', 
        'Private Limited Company', 
        'Public Limited Company', 
        'HUF', 
        'Trust/NGO', 
        'Govt Undertaking'
    ]
    
    msme_types = ['Manufacturing Micro', 'Manufacturing Small', 'Manufacturing Medium', 'Services Micro', 'Services Small', 'Services Medium']
    states = MasterData.query.filter_by(category='REGION').all()
    banks = MasterData.query.filter_by(category='BANK').all()

    if request.method == 'POST':
        try:
            # --- SCREEN 1 ---
            req.title = request.form.get('title')
            req.vendor_name_basic = request.form.get('legal_name')
            req.trade_name = request.form.get('trade_name')
            req.constitution = request.form.get('constitution')
            req.cin_number = request.form.get('cin_no') # Capture CIN
            
            req.contact_person_name = request.form.get('contact_name')
            req.contact_person_designation = request.form.get('designation')
            req.mobile_number = request.form.get('mobile_1')
            req.mobile_number_2 = request.form.get('mobile_2')
            req.landline_number = request.form.get('landline')
            req.product_service_description = request.form.get('product_desc')
            
            req.street = request.form.get('street_1')
            req.street_2 = request.form.get('street_2')
            req.street_3 = request.form.get('street_3')
            req.city = request.form.get('city')
            req.postal_code = request.form.get('pincode')
            req.state = request.form.get('state')

            # --- SCREEN 2 ---
            req.gst_registered = request.form.get('gst_reg')
            if req.gst_registered == 'YES':
                req.gst_number = request.form.get('gst_no')
                f = request.files.get('gst_file')
                if f: req.gst_file_path = save_file(f, 'GST')

            req.pan_number = request.form.get('pan_no')
            f = request.files.get('pan_file')
            if f: req.pan_file_path = save_file(f, 'PAN')

            req.msme_registered = request.form.get('msme_reg')
            if req.msme_registered == 'YES':
                req.msme_number = request.form.get('udyam_no')
                req.msme_type = request.form.get('msme_type')
                f = request.files.get('msme_file')
                if f: req.msme_file_path = save_file(f, 'MSME')

            req.tds_exemption_number = request.form.get('tds_cert_no')
            f = request.files.get('tds_file')
            if f: req.tds_exemption_file_path = save_file(f, 'TDS')

            # --- SCREEN 3 ---
            req.bank_name = request.form.get('bank_name')
            req.bank_account_holder_name = request.form.get('holder_name')
            req.bank_account_no = request.form.get('acc_no')
            req.bank_ifsc = request.form.get('ifsc')
            f = request.files.get('bank_file')
            if f: req.bank_proof_file_path = save_file(f, 'BANK')

            req.status = 'PENDING_APPROVAL'
            req.current_dept_flow = 'INITIATOR_REVIEW'
            db.session.commit()
            
            # Use User model for email lookup
            from app.models import User
            initiator = db.session.get(User, req.initiator_id)
            if initiator:
                send_status_email(req, initiator.email, "Vendor Submitted (Ready for Review)")

            return render_template('vendor_success.html', req=req)

        except Exception as e:
            db.session.rollback()
            flash(f"Error: {str(e)}", "error")
            return redirect(request.url)

    return render_template('vendor_portal.html', req=req, titles=titles, constitutions=constitutions, msme_types=msme_types, states=states, banks=banks)