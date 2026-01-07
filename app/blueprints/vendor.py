# import uuid
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

#     # =========================================================
#     # 1. IMMEDIATE PERSISTENCE (Files & Text Fields)
#     # =========================================================
#     if request.method == 'POST':
#         try:
#             # A. Auto-Save Text Fields (Draft Mode)
#             if request.form.get('legal_name'):
#                 req.vendor_name_basic = request.form.get('legal_name').strip().upper()
                
#             if request.form.get('gst_no'):
#                 req.gst_number = request.form.get('gst_no').strip().upper()
            
#             if request.form.get('msme_number'):
#                 req.msme_number = request.form.get('msme_number').strip().upper()
                
#             # Persist Radios
#             req.gst_registered = request.form.get('gst_reg')
#             req.msme_registered = request.form.get('msme_reg')
            
#             # B. Save Files
#             files_saved = False
#             def handle_file(field_name, db_col, prefix):
#                 if field_name in request.files:
#                     f = request.files[field_name]
#                     if f.filename:
#                         path = save_file(f, prefix)
#                         if path:
#                             if db_col: setattr(req, db_col, path)
#                             return True
#                 return False

#             if handle_file('gst_file', 'gst_file_path', 'GST'): files_saved = True
#             if handle_file('pan_file', 'pan_file_path', 'PAN'): files_saved = True
#             if handle_file('msme_file', 'msme_file_path', 'MSME'): files_saved = True
#             if handle_file('bank_file', 'bank_proof_file_path', 'BANK'): files_saved = True
#             if handle_file('tds_file', 'tds_file_path', 'TDS'): files_saved = True

#             # Commit updates (Text or Files)
#             db.session.commit()
#             db.session.refresh(req) 
            
#         except Exception as e:
#             print(f"Persistence Error: {e}")
#             db.session.rollback()

#     # =========================================================
#     # 2. VALIDATION & SUBMISSION
#     # =========================================================
    
#     # Run standard WTForms validation first
#     is_submitted_and_valid = form.validate_on_submit()

#     if request.method == 'POST':
#         # --- CUSTOM FILE VALIDATION ---
#         # Helper function to safely handle the "tuple has no attribute append" error
#         def check_file(field, db_path, msg):
#             # Check if file is NOT in DB and NOT in current upload
#             has_upload = field.data and getattr(field.data, 'filename', None)
            
#             if not db_path and not has_upload:
#                 # [CRITICAL FIX] Convert tuple to list before appending
#                 current_errors = list(field.errors)
#                 current_errors.append(msg)
#                 field.errors = current_errors
#                 return False
#             return True

#         # Run checks (these return False if invalid, effectively setting is_submitted_and_valid to False)
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

#         # --- FINAL SAVE IF VALID ---
#         if is_submitted_and_valid:
#             try:
#                 req.title = form.title.data
#                 # Use form data for reliability
#                 if form.legal_name.data:
#                     req.vendor_name_basic = form.legal_name.data.strip().upper() 
                
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
#                 if form.gst_reg.data == 'YES':
#                     req.gst_number = form.gst_no.data.strip().upper()

#                 req.pan_number = form.pan_no.data.strip().upper()

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

#     # =========================================================
#     # 3. PRE-FILL (GET Request)
#     # =========================================================
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
        
#         wht_tax = next((t for t in req.tax_details if t.tax_category == 'WHT'), None)
#         if wht_tax and wht_tax.cert_no: form.tds_cert_no.data = wht_tax.cert_no

#     # =========================================================
#     # 4. ERROR HANDLING
#     # =========================================================
#     initial_step = 1
#     if form.errors:
#         if any(key in form.errors for key in ['bank_name', 'acc_no', 'acc_no_confirm', 'ifsc', 'bank_file']):
#             initial_step = 3
#         elif any(key in form.errors for key in ['gst_no', 'pan_no', 'msme_number', 'gst_file', 'pan_file', 'msme_file']):
#             initial_step = 2
#         for field, errors in form.errors.items():
#             for error in errors:
#                 # Use label if available, otherwise field name
#                 label = getattr(form, field).label.text if hasattr(form, field) else field
#                 flash(f"{label}: {error}", "error")

#     return render_template('vendor/portal.html', req=req, form=form, initial_step=initial_step)


# @vendor_bp.route('/api/verify-initiate', methods=['POST'])
# def verify_initiate():
#     data = request.get_json()
#     field_type = data.get('type') # 'pan', 'gst', or 'bank'
#     value = data.get('value')
    
#     try:
#         req_id = None
#         if field_type == 'pan':
#             req_id = VerificationService.verify_pan(value)
#         elif field_type == 'gst':
#             req_id = VerificationService.verify_gst(value)
        
#         return jsonify({'status': 'initiated', 'request_id': req_id})
#     except Exception as e:
#         return jsonify({'error': str(e)}), 500

# @vendor_bp.route('/api/verify-status/<request_id>', methods=['GET'])
# def verify_status(request_id):
#     result = VerificationService.check_status(request_id)
#     return jsonify(result)

# @vendor_bp.route('/api/verify-details', methods=['POST'])
# def verify_details():
#     """AJAX Endpoint for Vendor Portal to verify data live."""
#     try:
#         data = request.get_json()

#         result = VerificationService.verify_vendor_data(data)

#         return jsonify(result)

#     except Exception as e:
#         current_app.logger.error(f"Verification Failed: {e}")

#         return jsonify({'error': 'Verification service unavailable'}), 500

import uuid
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
    
    # Populate State Choices
    states = MasterData.query.filter_by(category='REGION').all()
    state_choices = [(s.code, s.label) for s in states]
    state_choices.insert(0, ('', '-- Select State --'))
    form.state.choices = state_choices

    # 1. IMMEDIATE PERSISTENCE (Files & Text Fields)
    if request.method == 'POST':
        try:
            if request.form.get('legal_name'):
                req.vendor_name_basic = request.form.get('legal_name').strip().upper()
            if request.form.get('gst_no'):
                req.gst_number = request.form.get('gst_no').strip().upper()
            if request.form.get('msme_number'):
                req.msme_number = request.form.get('msme_number').strip().upper()
                
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
            print(f"Persistence Error: {e}")
            db.session.rollback()

    # 2. VALIDATION & SUBMISSION
    is_submitted_and_valid = form.validate_on_submit()

    if request.method == 'POST':
        # Custom file validation
        def check_file(field, db_path, msg):
            has_upload = field.data and getattr(field.data, 'filename', None)
            if not db_path and not has_upload:
                # WTForms errors are tuples, need list to append
                current_errors = list(field.errors)
                current_errors.append(msg)
                field.errors = current_errors
                return False
            return True

        # Run checks
        if not check_file(form.pan_file, req.pan_file_path, "PAN Document is required."): 
            is_submitted_and_valid = False
        if not check_file(form.bank_file, req.bank_proof_file_path, "Bank Proof is required."): 
            is_submitted_and_valid = False
        if form.gst_reg.data == 'YES':
            if not check_file(form.gst_file, req.gst_file_path, "GST Certificate is required."): 
                is_submitted_and_valid = False
        if form.msme_reg.data == 'YES':
            if not check_file(form.msme_file, req.msme_file_path, "MSME Certificate is required."): 
                is_submitted_and_valid = False

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

                req.gst_registered = form.gst_reg.data
                if form.gst_reg.data == 'YES': req.gst_number = form.gst_no.data.strip().upper()

                req.pan_number = form.pan_no.data.strip().upper()

                req.msme_registered = form.msme_reg.data
                if form.msme_reg.data == 'YES':
                    req.msme_number = form.msme_number.data.strip().upper()
                    req.msme_type = form.msme_type.data

                req.bank_name = form.bank_name.data
                req.bank_account_holder_name = form.holder_name.data
                req.bank_account_no = form.acc_no.data
                req.bank_ifsc = form.ifsc.data.strip().upper()

                # TDS Logic
                for old_tax in req.tax_details: db.session.delete(old_tax)
                if form.tds_cert_no.data or req.tds_file_path or (form.tds_file.data and form.tds_file.data.filename):
                    wht = VendorTaxDetail(
                        vendor_request=req, tax_category='WHT', tax_code='Z004',         
                        recipient_type='CO', cert_no=form.tds_cert_no.data,
                        start_date='01.04.2024', end_date='31.03.2025'
                    )
                    db.session.add(wht)

                req.status = 'PENDING_APPROVAL'
                req.current_dept_flow = 'INITIATOR_REVIEW'
                log_audit(req.id, None, 'SUBMITTED_BY_VENDOR', "Vendor filled the form")

                db.session.commit()
                
                initiator = db.session.get(User, req.initiator_id)
                if initiator:
                    send_status_email(req, initiator.email, "Vendor Submitted (Ready for Review)")

                return redirect(url_for('vendor.vendor_portal', token=token))

            except Exception as e:
                db.session.rollback()
                flash(f"System Error: {str(e)}", "error")
                return render_template('vendor/portal.html', req=req, form=form, initial_step=3)

    # 3. PRE-FILL (GET Request)
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

        if req.gst_registered: 
            form.gst_reg.data = req.gst_registered
            if req.gst_registered == 'YES': form.gst_no.data = req.gst_number

        if req.msme_registered: 
            form.msme_reg.data = req.msme_registered
            if req.msme_registered == 'YES':
                form.msme_number.data = req.msme_number
                form.msme_type.data = req.msme_type
        
        if req.pan_number: form.pan_no.data = req.pan_number
        
        wht_tax = next((t for t in req.tax_details if t.tax_category == 'WHT'), None)
        if wht_tax and wht_tax.cert_no: form.tds_cert_no.data = wht_tax.cert_no

    # 4. ERROR HANDLING
    initial_step = 1
    if form.errors:
        if any(key in form.errors for key in ['bank_name', 'acc_no', 'acc_no_confirm', 'ifsc', 'bank_file']):
            initial_step = 3
        elif any(key in form.errors for key in ['gst_no', 'pan_no', 'msme_number', 'gst_file', 'pan_file', 'msme_file']):
            initial_step = 2
        for field, errors in form.errors.items():
            for error in errors:
                label = getattr(form, field).label.text if hasattr(form, field) else field
                flash(f"{label}: {error}", "error")

    return render_template('vendor/portal.html', req=req, form=form, initial_step=initial_step)


# =========================================================
# ASYNC VERIFICATION ROUTES
# =========================================================

@vendor_bp.route('/api/verify-initiate', methods=['POST'])
def verify_initiate():
    data = request.get_json()
    field_type = data.get('type') # 'pan', 'gst', or 'bank'
    value = data.get('value')
    
    try:
        req_id = None
        if field_type == 'pan':
            req_id = VerificationService.verify_pan(value)
        elif field_type == 'gst':
            req_id = VerificationService.verify_gst(value)
        elif field_type == 'bank':
            account = value.get('account')
            ifsc = value.get('ifsc')
            if account and ifsc:
                req_id = VerificationService.verify_bank(account, ifsc)
            else:
                return jsonify({'error': 'Missing Bank Account or IFSC'}), 400
        
        if req_id:
            return jsonify({'status': 'initiated', 'request_id': req_id})
        else:
            return jsonify({'error': 'Invalid verification type'}), 400
            
    except Exception as e:
        current_app.logger.error(f"Init Error: {str(e)}")
        return jsonify({'error': str(e)}), 500


@vendor_bp.route('/api/verify-status/<request_id>', methods=['GET'])
def verify_status(request_id):
    try:
        # Calls the non-blocking check status method
        result = VerificationService.check_status(request_id)
        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"Status Error: {str(e)}")
        return jsonify({'error': str(e)}), 500
    

@vendor_bp.route('/api/verify-details', methods=['POST'])
def verify_details():
    """
    AJAX Endpoint for Vendor Portal to verify all data.
    (This is the one your portal.html uses)
    """
    try:
        data = request.get_json()
        result = VerificationService.verify_vendor_data(data)
        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"Verification Failed: {e}")
        return jsonify({'error': 'Verification service unavailable'}), 500