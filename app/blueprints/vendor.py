import uuid
from flask import (
    Blueprint, render_template, request, redirect,
    url_for, flash, jsonify, current_app
)

from app.extensions import db
from app.models import (
    VendorRequest, MasterData, User,
    VendorTaxDetail
)
from app.forms import VendorOnboardingForm
from app.utils import save_file, send_status_email, log_audit
from app.services.verification_service import VerificationService


from celery.result import AsyncResult
from app.extensions import limiter

vendor_bp = Blueprint("vendor", __name__)


# =========================================================
# VENDOR PORTAL
# =========================================================
# In app/blueprints/vendor.py

# app/blueprints/vendor.py

@vendor_bp.route("/portal/<token>", methods=["GET", "POST"])
def vendor_portal(token):
    req = VendorRequest.query.filter_by(token=token).first()

    if not req:
        return "Invalid Link", 404

    if req.status != "PENDING_VENDOR":
        return render_template("vendor/success.html", req=req)

    form = VendorOnboardingForm()

    # State Dropdown
    states = MasterData.query.filter_by(category="REGION").all()
    form.state.choices = [("", "-- Select State --")] + [(s.code, s.label) for s in states]

    # =====================================================
    # 1. POST: SAVE DATA (Immediate Persistence)
    # =====================================================
    if request.method == "POST":
        try:
            def reset_if_changed(form_key, flag, old_value):
                if form_key in request.form:
                    new_val = (request.form.get(form_key) or "").strip().upper()
                    old_val = (old_value or "").strip().upper()
                    if new_val != old_val:
                        setattr(req, flag, False)

            # --- Basic Info ---
            if "legal_name" in request.form:
                req.vendor_name_basic = request.form["legal_name"].strip().upper()

            # --- PAN & Aadhaar ---
            current_pan = request.form.get("pan_no", "").strip().upper()
            if "pan_no" in request.form:
                reset_if_changed("pan_no", "is_pan_verified", req.pan_number)
                req.pan_number = current_pan

            # FIX: Explicitly save Aadhaar if present
            if "aadhaar_no" in request.form:
                req.aadhaar_number = request.form.get("aadhaar_no", "").strip()

            # --- GST ---
            if "gst_no" in request.form:
                reset_if_changed("gst_no", "is_gst_verified", req.gst_number)
                req.gst_number = request.form.get("gst_no", "").strip().upper()

            # --- MSME ---
            if "msme_number" in request.form:
                reset_if_changed("msme_number", "is_msme_verified", req.msme_number)
                req.msme_number = request.form.get("msme_number", "").strip().upper()
            
            # FIX: Explicitly save MSME Type
            if "msme_type" in request.form:
                req.msme_type = request.form.get("msme_type")

            # --- Bank ---
            if "acc_no" in request.form:
                reset_if_changed("acc_no", "is_bank_verified", req.bank_account_no)
                req.bank_account_no = request.form.get("acc_no", "").strip()
            
            if "ifsc" in request.form:
                reset_if_changed("ifsc", "is_bank_verified", req.bank_ifsc)
                req.bank_ifsc = request.form.get("ifsc", "").strip().upper()

            # --- Flags (Radio Buttons) ---
            if "gst_reg" in request.form:
                val = request.form.get("gst_reg")
                # Only reset if changing from YES to NO or vice versa
                if req.gst_registered != val:
                    req.gst_registered = val
                    if val == "NO":
                        req.is_gst_verified = False # Reset if they say NO
            
            if "msme_reg" in request.form:
                val = request.form.get("msme_reg")
                if req.msme_registered != val:
                    req.msme_registered = val
                    if val == "NO":
                        req.is_msme_verified = False # Reset if they say NO

            # --- Files ---
            def save_doc(field, db_col):
                if field in request.files:
                    f = request.files[field]
                    if f and f.filename:
                        path = save_file(f, field.upper())
                        if path: setattr(req, db_col, path)

            save_doc("pan_file", "pan_file_path")
            save_doc("gst_file", "gst_file_path")
            save_doc("msme_file", "msme_file_path")
            save_doc("bank_file", "bank_proof_file_path")
            save_doc("tds_file", "tds_file_path")

            db.session.commit()
            db.session.refresh(req)

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Persistence Error: {e}")

    # =====================================================
    # 2. VALIDATION & SUBMIT
    # =====================================================
    if request.method == "POST" and form.validate_on_submit():
        errors = []
        # Enforce verification logic ONLY if the feature is enabled (YES)
        if not req.is_pan_verified: errors.append("PAN Verification is required.")
        
        if req.gst_registered == "YES" and not req.is_gst_verified: 
            errors.append("GST Verification is required.")
            
        if req.msme_registered == "YES" and not req.is_msme_verified: 
            errors.append("MSME Verification is required.")
            
        if not req.is_bank_verified: 
            errors.append("Bank Verification is required.")

        if not errors:
            try:
                # Save Form Fields
                req.title = form.title.data
                req.trade_name = form.trade_name.data
                req.constitution = form.constitution.data
                if form.cin_no.data: req.cin_number = form.cin_no.data.upper()
                
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
                req.bank_ifsc = form.ifsc.data.upper()

                # TDS Logic
                if form.tds_cert_no.data or req.tds_file_path:
                     # Clear old, add new
                     for old in req.tax_details: db.session.delete(old)
                     db.session.add(VendorTaxDetail(
                        vendor_request=req, tax_category="WHT", tax_code="Z004",
                        recipient_type="CO", cert_no=form.tds_cert_no.data,
                        start_date="01.04.2024", end_date="31.03.2025"
                    ))

                req.status = "PENDING_APPROVAL"
                req.current_dept_flow = "INITIATOR_REVIEW"
                log_audit(req.id, None, "SUBMITTED", "Vendor Submitted Form")
                db.session.commit()
                
                initiator = db.session.get(User, req.initiator_id)
                if initiator:
                    send_status_email(req, initiator.email, "Vendor Submitted")

                return redirect(url_for("vendor.vendor_portal", token=token))
            except Exception as e:
                db.session.rollback()
                flash(f"System Error: {str(e)}", "error")
        else:
            for e in errors: flash(e, "error")

    # =====================================================
    # 3. GET: PREFILL DATA (Corrected)
    # =====================================================
    if request.method == "GET":
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
        if req.aadhaar_number: form.aadhaar_no.data = req.aadhaar_number

        # 🔥 FIX: Ensure Radio Button Data Persists
        if req.gst_registered: form.gst_reg.data = req.gst_registered
        if req.gst_number: form.gst_no.data = req.gst_number

        if req.msme_registered: form.msme_reg.data = req.msme_registered
        if req.msme_number: form.msme_number.data = req.msme_number
        if req.msme_type: form.msme_type.data = req.msme_type

        wht = next((t for t in req.tax_details if t.tax_category == "WHT"), None)
        if wht: form.tds_cert_no.data = wht.cert_no

    # Frontend Flags
    req.pan_verified = bool(req.is_pan_verified)
    req.gst_verified = bool(req.is_gst_verified)
    req.msme_verified = bool(req.is_msme_verified)
    req.bank_verified = bool(req.is_bank_verified)

    initial_step = 1
    if form.errors:
        if any(k in form.errors for k in ["bank_name", "acc_no", "ifsc"]): initial_step = 3
        elif any(k in form.errors for k in ["gst_no", "pan_no", "msme_number"]): initial_step = 2

    return render_template("vendor/portal.html", req=req, form=form, initial_step=initial_step)


# =========================================================
# UNVERIFY API (PERSISTENT)
# =========================================================
@vendor_bp.route("/api/unverify", methods=["POST"])
def unverify_section():
    data = request.get_json()
    req_id = data.get("vendor_request_id")
    section = data.get("section")

    req = VendorRequest.query.filter_by(request_id=req_id).first()
    if not req:
        return jsonify({"error": "Invalid vendor request"}), 404

    if section == "pan":
        req.is_pan_verified = False
    elif section == "gst":
        req.is_gst_verified = False
    elif section == "msme":
        req.is_msme_verified = False
    elif section == "bank":
        req.is_bank_verified = False
    else:
        return jsonify({"error": "Invalid section"}), 400

    db.session.commit()
    return jsonify({"success": True})



# =========================================================
# VERIFY API (Updated to FORCE SAVE)
# =========================================================
@vendor_bp.route("/api/verify-details", methods=["POST"])
@limiter.limit("30 per minute")
def verify_details():
    try:
        data = request.form.to_dict()

        # Handle Files (Upload to temp/S3 before passing to Task)
        def save_temp(file_key, prefix):
            if file_key in request.files:
                f = request.files[file_key]
                if f and f.filename:
                    return save_file(f, prefix)
            return None

        if "pan_file" in request.files: data["pan_file_path"] = save_temp("pan_file", "PAN")
        if "gst_file" in request.files: data["gst_file_path"] = save_temp("gst_file", "GST")
        if "msme_file" in request.files: data["msme_file_path"] = save_temp("msme_file", "MSME")
        if "bank_file" in request.files: data["bank_proof_file_path"] = save_temp("bank_file", "BANK")

        # Dispatch
        result = VerificationService.verify_vendor_data(data)
        
        if "error" in result:
            return jsonify(result), 400
            
        return jsonify(result) # Returns {"task_id": "...", "status": "processing"}

    except Exception as e:
        current_app.logger.exception("Verification Trigger Failed")
        return jsonify({"error": str(e)}), 500
    

# =========================================================
# 2. TASK STATUS CHECK (NEW ROUTE)
# =========================================================
@vendor_bp.route("/api/task-status/<task_id>", methods=["GET"])
def check_task_status(task_id):
    task_result = AsyncResult(task_id)
    
    if task_result.state == 'PENDING':
        return jsonify({"state": "PENDING", "status": "Processing..."})
    
    elif task_result.state != 'FAILURE':
        # SUCCESS
        return jsonify({
            "state": "SUCCESS",
            "result": task_result.result # This contains the {"valid": True, "details": ...} dict
        })
    
    else:
        # FAILURE
        return jsonify({
            "state": "FAILURE",
            "error": str(task_result.result)
        })
    

