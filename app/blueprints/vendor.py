from flask import Blueprint, render_template, request, url_for
from app.models import VendorRequest, User
from app.extensions import db
from app.utils import save_file, send_system_email

vendor_bp = Blueprint('vendor', __name__)

@vendor_bp.route('/vendor/<token>', methods=['GET', 'POST'])
def vendor_portal(token):
    req = VendorRequest.query.filter_by(token=token).first_or_404()
    
    if req.status != 'PENDING_VENDOR': 
        return render_template('success.html', req=req)
    
    if request.method == 'POST':
        req.vendor_name_basic = request.form.get('vendor_name_basic')
        req.address_line1 = request.form.get('address_line1')
        req.address_city = request.form.get('address_city')
        req.address_state = request.form.get('address_state')
        req.address_pincode = request.form.get('address_pincode')
        req.telephone_number = request.form.get('telephone_number')
        
        req.gst_number = request.form.get('gst_number')
        req.pan_number = request.form.get('pan_number')
        req.contact_name = request.form.get('contact_name')
        req.contact_number = request.form.get('contact_number')
        req.contact_designation = request.form.get('contact_designation')
        req.product_services = request.form.get('product_services')
        req.structure_type = request.form.get('structure_type')
        req.cin_number = request.form.get('cin_number')
        
        req.msme_registered = True if request.form.get('msme_registered') == 'yes' else False
        if req.msme_registered:
            req.msme_aadhar = request.form.get('msme_aadhar')
            req.msme_type = request.form.get('msme_type')
            
        req.bank_name = request.form.get('bank_name')
        req.account_number = request.form.get('account_number')
        req.ifsc_code = request.form.get('ifsc_code')

        file_gst = request.files.get('file_gst')
        file_pan = request.files.get('file_pan')
        file_cheque = request.files.get('file_cheque')
        file_msme = request.files.get('file_msme')

        if file_gst: req.doc_gst = save_file(file_gst, 'GST')
        if file_pan: req.doc_pan = save_file(file_pan, 'PAN')
        if file_cheque: req.doc_cheque = save_file(file_cheque, 'CHEQUE')
        if file_msme: req.doc_msme = save_file(file_msme, 'MSME')
        
        req.status = 'PENDING_APPROVAL'
        req.current_dept_flow = 'INITIATOR_REVIEW'
        
        initiator = db.session.get(User, req.initiator_id)
        if initiator: 
            send_system_email(initiator.email, "Review Vendor", f"Vendor {req.vendor_name_basic} has submitted details.")
        
        db.session.commit()
        return render_template('success.html', req=req)

    return render_template('vendor_form.html', req=req)
