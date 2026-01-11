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

vendor_bp = Blueprint("vendor", __name__)


# =========================================================
# VENDOR PORTAL
# =========================================================
@vendor_bp.route("/portal/<token>", methods=["GET", "POST"])
def vendor_portal(token):
    req = VendorRequest.query.filter_by(token=token).first()

    if not req:
        return "Invalid Link", 404

    if req.status != "PENDING_VENDOR":
        return render_template("vendor/success.html", req=req)

    form = VendorOnboardingForm()

    # ---------------------------
    # STATE DROPDOWN
    # ---------------------------
    states = MasterData.query.filter_by(category="REGION").all()
    form.state.choices = [("", "-- Select State --")] + [
        (s.code, s.label) for s in states
    ]

    # =====================================================
    # 1. IMMEDIATE PERSISTENCE + HARD UNVERIFY
    # =====================================================
    if request.method == "POST":
        try:
            # 🔥 IMPORTANT:
            # If field is PRESENT in POST → UNVERIFY
            # def reset_if_changed(form_key, flag, old_value):
            #     if form_key in request.form:
            #         # Get new value and normalize
            #         new_value = (request.form.get(form_key) or "").strip()
            #         old_value = (old_value or "").strip()
                    
            #         # ✅ FIX: Compare UPPERCASE to UPPERCASE to avoid case-sensitivity issues
            #         is_currently_verified = getattr(req, flag)
            #         if is_currently_verified and not old_value and new_value:
            #             return 

            #         # 2. Standard Check: If values are different, unverify.
            #         if new_value.upper() != old_value.upper():
            #             setattr(req, flag, False)

            # =====================================================
            # DEBUGGING VERSION (Replace your current reset_if_changed with this)
            # =====================================================
            def reset_if_changed(form_key, flag, old_value):
                if form_key in request.form:
                    new_value = (request.form.get(form_key) or "").strip()
                    old_value = (old_value or "").strip()
                    current_status = getattr(req, flag)

                    # --- THE PROOF IS IN THESE LOGS ---
                    print(f"\n[DEBUG] Checking {form_key}...")
                    print(f"   -> DB Value:   '{old_value}'")
                    print(f"   -> Form Value: '{new_value}'")
                    print(f"   -> Currently Verified? {current_status}")

                    if new_value.upper() != old_value.upper():
                        print(f"   !!! MISMATCH !!! Backend is setting {flag} = False")
                        setattr(req, flag, False)
                    else:
                        print(f"   -> Values match. Status remains: {current_status}")


            def handle_file(field_name, db_col, reset_flag, prefix):
                if field_name in request.files:
                    f = request.files[field_name]
                    if f and f.filename:
                        path = save_file(f, prefix)
                        if path:
                            setattr(req, db_col, path)
                            if reset_flag:
                                setattr(req, reset_flag, False)

            # ---------- BASIC ----------
            if request.form.get("legal_name"):
                req.vendor_name_basic = request.form["legal_name"].strip().upper()

            # ---------- PAN ----------
            if "pan_no" in request.form:
                reset_if_changed("pan_no", "is_pan_verified", req.pan_number)
                req.pan_number = request.form.get("pan_no", "").strip().upper()


            if "aadhaar_no" in request.form:
                reset_if_changed("aadhaar_no", "is_pan_verified", req.aadhaar_number)
                req.aadhaar_number = request.form.get("aadhaar_no", "").strip()


            # ---------- GST ----------
            if "gst_no" in request.form:
                reset_if_changed("gst_no", "is_gst_verified", req.gst_number)
                req.gst_number = request.form.get("gst_no", "").strip().upper()


            # ---------- MSME ----------
            if "msme_number" in request.form:
                reset_if_changed("msme_number", "is_msme_verified", req.msme_number)
                req.msme_number = request.form.get("msme_number", "").strip().upper()


            if "acc_no" in request.form:
                reset_if_changed("acc_no", "is_bank_verified", req.bank_account_no)
                req.bank_account_no = request.form.get("acc_no", "").strip()

            if "ifsc" in request.form:
                reset_if_changed("ifsc", "is_bank_verified", req.bank_ifsc)
                req.bank_ifsc = request.form.get("ifsc", "").strip().upper()


            # ---------- RADIO ----------
            # ---------- RADIO (CORRECTED) ----------
            if "gst_reg" in request.form:
                new_val = request.form.get("gst_reg")
                # Only reset if the user ACTUALLY toggled from YES to NO (or vice versa)
                if req.gst_registered != new_val:
                    req.gst_registered = new_val
                    req.is_gst_verified = False

            if "msme_reg" in request.form:
                new_val = request.form.get("msme_reg")
                if req.msme_registered != new_val:
                    req.msme_registered = new_val
                    req.is_msme_verified = False

            # ---------- FILES ----------
            handle_file("pan_file", "pan_file_path", "is_pan_verified", "PAN")
            handle_file("gst_file", "gst_file_path", "is_gst_verified", "GST")
            handle_file("msme_file", "msme_file_path", "is_msme_verified", "MSME")
            handle_file("bank_file", "bank_proof_file_path", "is_bank_verified", "BANK")
            handle_file("tds_file", "tds_file_path", None, "TDS")

            db.session.commit()
            db.session.refresh(req)

        except Exception:
            db.session.rollback()
            current_app.logger.exception("Immediate persistence failed")

    # =====================================================
    # 2. FORM VALIDATION & FINAL SUBMIT
    # =====================================================
    is_valid = form.validate_on_submit()

    if request.method == "POST":

        def require_file(field, path, msg):
            has_upload = field.data and getattr(field.data, "filename", None)
            if not path and not has_upload:
                field.errors = list(field.errors) + [msg]
                return False
            return True

        if not require_file(form.pan_file, req.pan_file_path, "PAN Document is required"):
            is_valid = False

        if not require_file(form.bank_file, req.bank_proof_file_path, "Bank Proof is required"):
            is_valid = False

        if form.gst_reg.data == "YES":
            if not require_file(form.gst_file, req.gst_file_path, "GST Certificate required"):
                is_valid = False

        if form.msme_reg.data == "YES":
            if not require_file(form.msme_file, req.msme_file_path, "MSME Certificate required"):
                is_valid = False

        # ---------- FINAL SUBMIT ----------
        if is_valid:
            try:
                req.title = form.title.data
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

                if form.msme_reg.data == "YES":
                    req.msme_type = form.msme_type.data

                # ---------- TDS ----------
                for old in req.tax_details:
                    db.session.delete(old)

                if form.tds_cert_no.data or req.tds_file_path:
                    db.session.add(
                        VendorTaxDetail(
                            vendor_request=req,
                            tax_category="WHT",
                            tax_code="Z004",
                            recipient_type="CO",
                            cert_no=form.tds_cert_no.data,
                            start_date="01.04.2024",
                            end_date="31.03.2025",
                        )
                    )

                req.status = "PENDING_APPROVAL"
                req.current_dept_flow = "INITIATOR_REVIEW"

                log_audit(req.id, None, "SUBMITTED_BY_VENDOR", "Vendor submitted form")
                db.session.commit()

                initiator = db.session.get(User, req.initiator_id)
                if initiator:
                    send_status_email(req, initiator.email, "Vendor Submitted")

                return redirect(url_for("vendor.vendor_portal", token=token))

            except Exception as e:
                db.session.rollback()
                flash(f"System Error: {str(e)}", "error")

    # =====================================================
    # 3. PREFILL (GET)
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
        form.aadhaar_no.data = req.aadhaar_number

        if req.gst_registered == "YES":
            form.gst_reg.data = "YES"
            form.gst_no.data = req.gst_number

        if req.msme_registered == "YES":
            form.msme_reg.data = "YES"
            form.msme_number.data = req.msme_number
            form.msme_type.data = req.msme_type

        wht = next((t for t in req.tax_details if t.tax_category == "WHT"), None)
        if wht:
            form.tds_cert_no.data = wht.cert_no

    # =====================================================
    # FRONTEND SAFE FLAGS
    # =====================================================
    req.pan_verified = bool(req.is_pan_verified)
    req.gst_verified = bool(req.is_gst_verified)
    req.msme_verified = bool(req.is_msme_verified)
    req.bank_verified = bool(req.is_bank_verified)

    # =====================================================
    # INITIAL STEP
    # =====================================================
    initial_step = 1
    if form.errors:
        if any(k in form.errors for k in ["bank_name", "acc_no", "ifsc"]):
            initial_step = 3
        elif any(k in form.errors for k in ["gst_no", "pan_no", "msme_number"]):
            initial_step = 2

    return render_template(
        "vendor/portal.html",
        req=req,
        form=form,
        initial_step=initial_step,
    )


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
def verify_details():
    try:
        data = request.form.to_dict()

        # 1. Handle File Uploads (Keep existing logic)
        def save_temp(file_key, prefix):
            if file_key in request.files:
                f = request.files[file_key]
                if f and f.filename:
                    return save_file(f, prefix)
            return None

        if "pan_file" in request.files:
            data["pan_file_path"] = save_temp("pan_file", "PAN")
        if "gst_file" in request.files:
            data["gst_file_path"] = save_temp("gst_file", "GST")
        if "msme_file" in request.files:
            data["msme_file_path"] = save_temp("msme_file", "MSME")
        if "bank_file" in request.files:
            data["bank_proof_file_path"] = save_temp("bank_file", "BANK")

        # 2. Call Service to get API Result
        result = VerificationService.verify_vendor_data(data)
        
        # 3. 🔥 FORCE DB UPDATE IF VALID 🔥
        # We re-fetch the request to ensure we have a live DB session
        req_id = data.get("vendor_request_id")
        req = VendorRequest.query.filter_by(request_id=req_id).first()
        
        if req and result.get("valid") is True:
            print(f"[API ROUTE] Verification Passed. Saving to DB for {req_id}...")
            details = result.get("details", {})

            # --- PAN Save ---
            if "pan" in details and details["pan"].get("is_valid"):
                req.is_pan_verified = True
                req.pan_number = data.get("pan_number", req.pan_number).upper()
                if "pan_file_path" in data: req.pan_file_path = data["pan_file_path"]

            # --- GST Save ---
            # Check for active status in the response
            gst_res = details.get("gst", {})
            if gst_res.get("gstin_status") == "Active" or gst_res.get("status") == "Active":
                req.is_gst_verified = True
                req.gst_number = data.get("gst_number", req.gst_number).upper()
                req.gst_registered = "YES"
                if "gst_file_path" in data: req.gst_file_path = data["gst_file_path"]

            # --- MSME Save ---
            msme_res = details.get("msme", {})
            if msme_res.get("status") in ["id_found", "Verified"]:
                req.is_msme_verified = True
                req.msme_number = data.get("msme_number", req.msme_number).upper()
                req.msme_registered = "YES"
                if "msme_file_path" in data: req.msme_file_path = data["msme_file_path"]

            # --- BANK Save (The Critical Part) ---
            if "bank" in details:
                bank_res = details["bank"]
                # Check various success indicators
                is_bank_valid = (
                    str(bank_res.get("account_exists")).lower() == "true" or 
                    bank_res.get("account_exists") is True or
                    bank_res.get("status") == "id_found"
                )
                
                if is_bank_valid:
                    print(f"[API ROUTE] Saving Bank Verified = True for Acc: {data.get('bank_account_no')}")
                    req.is_bank_verified = True
                    req.bank_account_no = data.get("bank_account_no")
                    req.bank_ifsc = data.get("ifsc_code").upper()
                    
                    # Save the Penny Drop Name if available
                    if bank_res.get("name_at_bank"):
                        req.bank_account_holder_name = bank_res.get("name_at_bank")
                    
                    if "bank_proof_file_path" in data: 
                        req.bank_proof_file_path = data["bank_proof_file_path"]

            # 4. Commit Changes
            db.session.add(req)
            db.session.commit()
            print("[API ROUTE] Database Commit Successful.")

        return jsonify(result)

    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Verification failed")
        return jsonify({"error": str(e), "details": None}), 200