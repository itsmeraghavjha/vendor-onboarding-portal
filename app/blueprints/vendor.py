# import uuid
# import os
# from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
# from app.extensions import db
# from app.models import VendorRequest, MasterData, User, VendorTaxDetail
# from app.forms import VendorOnboardingForm
# from app.utils import save_file, send_status_email, log_audit
# from app.services.verification_service import VerificationService

# vendor_bp = Blueprint('vendor', __name__)

# @vendor_bp.route('/portal/<token>', methods=['GET', 'POST'])
# def vendor_portal(token):
#     req = VendorRequest.query.filter_by(token=token).first()
    
#     if not req: return "Invalid Link", 404
#     if req.status != 'PENDING_VENDOR': return render_template('vendor/success.html', req=req)

#     form = VendorOnboardingForm()
    
#     # Populate State Choices
#     states = MasterData.query.filter_by(category='REGION').all()
#     state_choices = [(s.code, s.label) for s in states]
#     state_choices.insert(0, ('', '-- Select State --'))
#     form.state.choices = state_choices

#     # 1. IMMEDIATE PERSISTENCE (Files & Text Fields)
#     if request.method == 'POST':
#         try:
#             if request.form.get('legal_name'):
#                 req.vendor_name_basic = request.form.get('legal_name').strip().upper()
#             if request.form.get('gst_no'):
#                 req.gst_number = request.form.get('gst_no').strip().upper()
#             if request.form.get('msme_number'):
#                 req.msme_number = request.form.get('msme_number').strip().upper()
            
#             # Persist Aadhaar if present
#             if request.form.get('aadhaar_no'):
#                 req.aadhaar_number = request.form.get('aadhaar_no').strip()
                
#             req.gst_registered = request.form.get('gst_reg')
#             req.msme_registered = request.form.get('msme_reg')
            
#             def handle_file(field_name, db_col, prefix):
#                 if field_name in request.files:
#                     f = request.files[field_name]
#                     if f.filename:
#                         path = save_file(f, prefix)
#                         if path:
#                             if db_col: setattr(req, db_col, path)
#                             return True
#                 return False

#             handle_file('gst_file', 'gst_file_path', 'GST')
#             handle_file('pan_file', 'pan_file_path', 'PAN')
#             handle_file('msme_file', 'msme_file_path', 'MSME')
#             handle_file('bank_file', 'bank_proof_file_path', 'BANK')
#             handle_file('tds_file', 'tds_file_path', 'TDS')

#             db.session.commit()
#             db.session.refresh(req) 
#         except Exception as e:
#             print(f"Persistence Error: {e}")
#             db.session.rollback()

#     # 2. VALIDATION & SUBMISSION
#     is_submitted_and_valid = form.validate_on_submit()

#     if request.method == 'POST':
#         # Custom file validation
#         def check_file(field, db_path, msg):
#             has_upload = field.data and getattr(field.data, 'filename', None)
#             if not db_path and not has_upload:
#                 # WTForms errors are tuples, need list to append
#                 current_errors = list(field.errors)
#                 current_errors.append(msg)
#                 field.errors = current_errors
#                 return False
#             return True

#         # Run checks
#         if not check_file(form.pan_file, req.pan_file_path, "PAN Document is required."): 
#             is_submitted_and_valid = False
#         if not check_file(form.bank_file, req.bank_proof_file_path, "Bank Proof is required."): 
#             is_submitted_and_valid = False
#         if form.gst_reg.data == 'YES':
#             if not check_file(form.gst_file, req.gst_file_path, "GST Certificate is required."): 
#                 is_submitted_and_valid = False
#         if form.msme_reg.data == 'YES':
#             if not check_file(form.msme_file, req.msme_file_path, "MSME Certificate is required."): 
#                 is_submitted_and_valid = False

#         if is_submitted_and_valid:
#             try:
#                 req.title = form.title.data
#                 if form.legal_name.data: req.vendor_name_basic = form.legal_name.data.strip().upper() 
#                 req.trade_name = form.trade_name.data
#                 req.constitution = form.constitution.data
#                 req.cin_number = form.cin_no.data.upper() if form.cin_no.data else None
#                 req.contact_person_name = form.contact_name.data
#                 req.contact_person_designation = form.designation.data
#                 req.mobile_number = form.mobile_1.data
#                 req.mobile_number_2 = form.mobile_2.data
#                 req.landline_number = form.landline.data
#                 req.product_service_description = form.product_desc.data
#                 req.street = form.street_1.data
#                 req.street_2 = form.street_2.data
#                 req.street_3 = form.street_3.data
#                 req.street_4 = form.street_4.data
#                 req.city = form.city.data
#                 req.postal_code = form.pincode.data
#                 req.state = form.state.data

#                 req.gst_registered = form.gst_reg.data
#                 if form.gst_reg.data == 'YES': req.gst_number = form.gst_no.data.strip().upper()

#                 req.pan_number = form.pan_no.data.strip().upper()
#                 req.aadhaar_number = form.aadhaar_no.data.strip() if form.aadhaar_no.data else None

#                 req.msme_registered = form.msme_reg.data
#                 if form.msme_reg.data == 'YES':
#                     req.msme_number = form.msme_number.data.strip().upper()
#                     req.msme_type = form.msme_type.data

#                 req.bank_name = form.bank_name.data
#                 req.bank_account_holder_name = form.holder_name.data
#                 req.bank_account_no = form.acc_no.data
#                 req.bank_ifsc = form.ifsc.data.strip().upper()

#                 # TDS Logic
#                 for old_tax in req.tax_details: db.session.delete(old_tax)
#                 if form.tds_cert_no.data or req.tds_file_path or (form.tds_file.data and form.tds_file.data.filename):
#                     wht = VendorTaxDetail(
#                         vendor_request=req, tax_category='WHT', tax_code='Z004',         
#                         recipient_type='CO', cert_no=form.tds_cert_no.data,
#                         start_date='01.04.2024', end_date='31.03.2025'
#                     )
#                     db.session.add(wht)

#                 req.status = 'PENDING_APPROVAL'
#                 req.current_dept_flow = 'INITIATOR_REVIEW'
#                 log_audit(req.id, None, 'SUBMITTED_BY_VENDOR', "Vendor filled the form")

#                 db.session.commit()
                
#                 initiator = db.session.get(User, req.initiator_id)
#                 if initiator:
#                     send_status_email(req, initiator.email, "Vendor Submitted (Ready for Review)")

#                 return redirect(url_for('vendor.vendor_portal', token=token))

#             except Exception as e:
#                 db.session.rollback()
#                 flash(f"System Error: {str(e)}", "error")
#                 return render_template('vendor/portal.html', req=req, form=form, initial_step=3)

#     # 3. PRE-FILL (GET Request)
#     if request.method == 'GET':
#         form.title.data = req.title
#         form.legal_name.data = req.vendor_name_basic 
#         form.trade_name.data = req.trade_name
#         form.constitution.data = req.constitution
#         form.cin_no.data = req.cin_number
#         form.contact_name.data = req.contact_person_name
#         form.designation.data = req.contact_person_designation
#         form.mobile_1.data = req.mobile_number
#         form.mobile_2.data = req.mobile_number_2
#         form.landline.data = req.landline_number
#         form.product_desc.data = req.product_service_description
#         form.street_1.data = req.street
#         form.street_2.data = req.street_2
#         form.street_3.data = req.street_3
#         form.street_4.data = req.street_4
#         form.city.data = req.city
#         form.pincode.data = req.postal_code
#         form.state.data = req.state
#         form.bank_name.data = req.bank_name
#         form.holder_name.data = req.bank_account_holder_name
#         form.acc_no.data = req.bank_account_no
#         form.acc_no_confirm.data = req.bank_account_no
#         form.ifsc.data = req.bank_ifsc

#         if req.gst_registered: 
#             form.gst_reg.data = req.gst_registered
#             if req.gst_registered == 'YES': form.gst_no.data = req.gst_number

#         if req.msme_registered: 
#             form.msme_reg.data = req.msme_registered
#             if req.msme_registered == 'YES':
#                 form.msme_number.data = req.msme_number
#                 form.msme_type.data = req.msme_type
        
#         if req.pan_number: form.pan_no.data = req.pan_number
#         if req.aadhaar_number: form.aadhaar_no.data = req.aadhaar_number
        
#         wht_tax = next((t for t in req.tax_details if t.tax_category == 'WHT'), None)
#         if wht_tax and wht_tax.cert_no: form.tds_cert_no.data = wht_tax.cert_no

#     # 4. ERROR HANDLING
#     initial_step = 1
#     if form.errors:
#         if any(key in form.errors for key in ['bank_name', 'acc_no', 'acc_no_confirm', 'ifsc', 'bank_file']):
#             initial_step = 3
#         elif any(key in form.errors for key in ['gst_no', 'pan_no', 'msme_number', 'gst_file', 'pan_file', 'msme_file']):
#             initial_step = 2
#         for field, errors in form.errors.items():
#             for error in errors:
#                 label = getattr(form, field).label.text if hasattr(form, field) else field
#                 flash(f"{label}: {error}", "error")

#     return render_template('vendor/portal.html', req=req, form=form, initial_step=initial_step)


# # =========================================================
# # ASYNC VERIFICATION ROUTES
# # =========================================================

# @vendor_bp.route('/api/verify-details', methods=['POST'])
# def verify_details():
#     """
#     AJAX Endpoint for Vendor Portal to verify all data.
#     Now supports auto-uploading files via Multipart form data.
#     """
#     try:
#         # Check if content type is JSON or Multipart
#         if request.is_json:
#             data = request.get_json()
#         else:
#             # Handle Multipart Form Data
#             data = request.form.to_dict()
            
#             # Helper to save temporary files for verification
#             def save_temp_file(file_key, prefix):
#                 if file_key in request.files:
#                     f = request.files[file_key]
#                     if f.filename:
#                         # Save using the standard utils function
#                         return save_file(f, prefix)
#                 return None

#             # Attempt to save files if they were uploaded with the verification request
#             # This ensures the VerificationService can find the file on disk
#             if 'pan_file' in request.files:
#                 path = save_temp_file('pan_file', 'PAN')
#                 if path: data['pan_file_path'] = path
            
#             if 'gst_file' in request.files:
#                 path = save_temp_file('gst_file', 'GST')
#                 if path: data['gst_file_path'] = path # For future use if GST OCR is added

#         # Sanitize data: 'None' string -> None object
#         if data.get('pan_file_path') == 'None':
#             data['pan_file_path'] = None

#         result = VerificationService.verify_vendor_data(data)
#         return jsonify(result)
        
#     except Exception as e:
#         current_app.logger.error(f"Verification Failed: {e}")
#         return jsonify({'error': f'Verification service unavailable: {str(e)}'}), 500


import uuid
import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from app.extensions import db
from app.models import VendorRequest, MasterData, User, VendorTaxDetail
from app.forms import VendorOnboardingForm
from app.utils import save_file, send_status_email, log_audit
from app.services.verification_service import VerificationService

vendor_bp = Blueprint('vendor', __name__)

@vendor_bp.route('/portal/<token>', methods=['GET', 'POST'])
def vendor_portal(token):
    req = VendorRequest.query.filter_by(token=token).first()
    
    if not req: return "Invalid Link", 404
    if req.status != 'PENDING_VENDOR': return render_template('vendor/success.html', req=req)

    form = VendorOnboardingForm()
    
    states = MasterData.query.filter_by(category='REGION').all()
    state_choices = [(s.code, s.label) for s in states]
    state_choices.insert(0, ('', '-- Select State --'))
    form.state.choices = state_choices

    # 1. IMMEDIATE PERSISTENCE (Files & Text Fields)
    if request.method == 'POST':
        try:
            if request.form.get('legal_name'): req.vendor_name_basic = request.form.get('legal_name').strip().upper()
            if request.form.get('gst_no'): req.gst_number = request.form.get('gst_no').strip().upper()
            if request.form.get('msme_number'): req.msme_number = request.form.get('msme_number').strip().upper()
            if request.form.get('aadhaar_no'): req.aadhaar_number = request.form.get('aadhaar_no').strip()
            if request.form.get('pan_no'): req.pan_number = request.form.get('pan_no').strip().upper()
                
            req.gst_registered = request.form.get('gst_reg')
            req.msme_registered = request.form.get('msme_reg')
            
            def handle_file(field_name, db_col, prefix):
                if field_name in request.files:
                    f = request.files[field_name]
                    if f.filename:
                        path = save_file(f, prefix)
                        if path:
                            if db_col: setattr(req, db_col, path)
                            return True
                return False

            handle_file('gst_file', 'gst_file_path', 'GST')
            handle_file('pan_file', 'pan_file_path', 'PAN')
            handle_file('msme_file', 'msme_file_path', 'MSME')
            handle_file('bank_file', 'bank_proof_file_path', 'BANK')
            handle_file('tds_file', 'tds_file_path', 'TDS')

            db.session.commit()
            db.session.refresh(req) 
        except Exception as e:
            db.session.rollback()

    # 2. VALIDATION & SUBMISSION
    is_submitted_and_valid = form.validate_on_submit()

    if request.method == 'POST':
        def check_file(field, db_path, msg):
            has_upload = field.data and getattr(field.data, 'filename', None)
            if not db_path and not has_upload:
                current_errors = list(field.errors)
                current_errors.append(msg)
                field.errors = current_errors
                return False
            return True

        if not check_file(form.pan_file, req.pan_file_path, "PAN Document is required."): is_submitted_and_valid = False
        if not check_file(form.bank_file, req.bank_proof_file_path, "Bank Proof is required."): is_submitted_and_valid = False
        if form.gst_reg.data == 'YES' and not check_file(form.gst_file, req.gst_file_path, "GST Certificate is required."): is_submitted_and_valid = False
        if form.msme_reg.data == 'YES' and not check_file(form.msme_file, req.msme_file_path, "MSME Certificate is required."): is_submitted_and_valid = False

        if is_submitted_and_valid:
            try:
                req.title = form.title.data
                if form.legal_name.data: req.vendor_name_basic = form.legal_name.data.strip().upper() 
                req.trade_name = form.trade_name.data
                req.constitution = form.constitution.data
                req.cin_number = form.cin_no.data.upper() if form.cin_no.data else None
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
                
                req.bank_name = form.bank_name.data
                req.bank_account_holder_name = form.holder_name.data
                req.bank_account_no = form.acc_no.data
                req.bank_ifsc = form.ifsc.data.strip().upper()
                
                req.gst_registered = form.gst_reg.data
                if form.gst_reg.data == 'YES': req.gst_number = form.gst_no.data.strip().upper()
                
                req.msme_registered = form.msme_reg.data
                if form.msme_reg.data == 'YES':
                    req.msme_number = form.msme_number.data.strip().upper()
                    req.msme_type = form.msme_type.data

                # TDS Logic
                for old_tax in req.tax_details: db.session.delete(old_tax)
                if form.tds_cert_no.data or req.tds_file_path:
                    wht = VendorTaxDetail(vendor_request=req, tax_category='WHT', tax_code='Z004', recipient_type='CO', cert_no=form.tds_cert_no.data, start_date='01.04.2024', end_date='31.03.2025')
                    db.session.add(wht)

                req.status = 'PENDING_APPROVAL'
                req.current_dept_flow = 'INITIATOR_REVIEW'
                log_audit(req.id, None, 'SUBMITTED_BY_VENDOR', "Vendor filled the form")
                db.session.commit()
                
                initiator = db.session.get(User, req.initiator_id)
                if initiator: send_status_email(req, initiator.email, "Vendor Submitted (Ready for Review)")
                return redirect(url_for('vendor.vendor_portal', token=token))

            except Exception as e:
                db.session.rollback()
                flash(f"System Error: {str(e)}", "error")
                return render_template('vendor/portal.html', req=req, form=form, initial_step=3)

    # 3. PRE-FILL
    if request.method == 'GET':
        form.title.data = req.title
        form.legal_name.data = req.vendor_name_basic 
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
        form.pan_no.data = req.pan_number
        form.aadhaar_no.data = req.aadhaar_number

        if req.gst_registered: 
            form.gst_reg.data = req.gst_registered
            if req.gst_registered == 'YES': form.gst_no.data = req.gst_number

        if req.msme_registered: 
            form.msme_reg.data = req.msme_registered
            if req.msme_registered == 'YES':
                form.msme_number.data = req.msme_number
                form.msme_type.data = req.msme_type
        
        wht_tax = next((t for t in req.tax_details if t.tax_category == 'WHT'), None)
        if wht_tax and wht_tax.cert_no: form.tds_cert_no.data = wht_tax.cert_no

    initial_step = 1
    if form.errors:
        if any(key in form.errors for key in ['bank_name', 'acc_no', 'ifsc']): initial_step = 3
        elif any(key in form.errors for key in ['gst_no', 'pan_no', 'msme_number']): initial_step = 2
        for field, errors in form.errors.items():
            for error in errors: flash(f"{getattr(form, field).label.text}: {error}", "error")

    return render_template('vendor/portal.html', req=req, form=form, initial_step=initial_step)


@vendor_bp.route('/api/verify-details', methods=['POST'])
def verify_details():
    try:
        if request.is_json:
            data = request.get_json()
        else:
            data = request.form.to_dict()
            
            # Save temp files for OCR to work immediately
            def save_temp_file(file_key, prefix):
                if file_key in request.files:
                    f = request.files[file_key]
                    if f.filename:
                        return save_file(f, prefix)
                return None

            if 'pan_file' in request.files:
                path = save_temp_file('pan_file', 'PAN')
                if path: data['pan_file_path'] = path
            
            if 'gst_file' in request.files:
                path = save_temp_file('gst_file', 'GST')
                if path: data['gst_file_path'] = path

        if data.get('pan_file_path') == 'None': data['pan_file_path'] = None

        result = VerificationService.verify_vendor_data(data)
        return jsonify(result)
        
    except Exception as e:
        current_app.logger.error(f"Verification Failed: {e}")
        # Return strict error format so JS can handle it without crashing
        return jsonify({'error': str(e), 'details': None}), 200