# from app.extensions import celery, mail, db
# from flask_mail import Message
# from app.models import VerificationLog
# from app import create_app
# import logging



# logger = logging.getLogger(__name__)


# @celery.task(bind=True, max_retries=3)
# def send_async_email(self, subject, recipient, body, is_html=True):
#     """
#     Background task to send an email via Flask-Mail.
#     """
#     try:
#         msg = Message(subject, recipients=[recipient])
#         if is_html:
#             msg.html = body
#         else:
#             msg.body = body
            
#         mail.send(msg)
#         return f"Email sent to {recipient}"
#     except Exception as e:
#         # Retry in 60 seconds if it fails (e.g., Network/SMTP issues)
#         self.retry(exc=e, countdown=60)



# @celery.task(bind=True, max_retries=3, name="app.tasks.log_audit_entry")
# def log_audit_entry(self, vendor_id, v_type, ext_id, status, input_data, response_data):
#     """
#     Background task to save audit logs.
#     Runs inside Celery worker with proper Flask app context.
#     """
#     app = create_app()

#     with app.app_context():
#         try:
#             log = VerificationLog(
#                 vendor_request_id=vendor_id,
#                 verification_type=v_type,
#                 external_ref_id=ext_id,
#                 status=status,
#                 input_payload=input_data,
#                 api_response=response_data,
#             )

#             db.session.add(log)
#             db.session.commit()

#             logger.info(f"✅ [Async Audit] Saved: {v_type} - {status}")
#             return "Logged"

#         except Exception as e:
#             db.session.rollback()
#             logger.error(f"❌ [Async Audit] Failed: {e}")
#             raise self.retry(exc=e, countdown=30)


# import uuid
# import base64
# import os
# import boto3
# import requests
# import logging
# from urllib.parse import urlparse
# from flask import current_app
# from flask_mail import Message

# # Extensions & Models
# from app.extensions import celery, mail, db
# from app.models import VendorRequest, VerificationLog
# from app import create_app

# # IDfy Helpers
# from app.external.idfy import run_task, poll_task

# logger = logging.getLogger(__name__)

# # ====================================================
# # 1. EXISTING TASKS (Email & Audit)
# # ====================================================

# @celery.task(bind=True, max_retries=3)
# def send_async_email(self, subject, recipient, body, is_html=True):
#     try:
#         msg = Message(subject, recipients=[recipient])
#         if is_html:
#             msg.html = body
#         else:
#             msg.body = body
#         mail.send(msg)
#         return f"Email sent to {recipient}"
#     except Exception as e:
#         self.retry(exc=e, countdown=60)


# @celery.task(bind=True, max_retries=3, name="app.tasks.log_audit_entry")
# def log_audit_entry(self, vendor_id, v_type, ext_id, status, input_data, response_data):
#     app = create_app()
#     with app.app_context():
#         try:
#             log = VerificationLog(
#                 vendor_request_id=vendor_id,
#                 verification_type=v_type,
#                 external_ref_id=ext_id,
#                 status=status,
#                 input_payload=input_data,
#                 api_response=response_data,
#             )
#             db.session.add(log)
#             db.session.commit()
#             return "Logged"
#         except Exception as e:
#             db.session.rollback()
#             raise self.retry(exc=e, countdown=30)


# # ====================================================
# # 2. HELPER: File Reader
# # ====================================================
# def file_to_base64(file_path):
#     if not file_path: return None
#     use_s3 = current_app.config.get('USE_S3')
    
#     if use_s3:
#         try:
#             key = file_path
#             if key.startswith("http"): key = urlparse(key).path.lstrip("/")
#             elif key.startswith("s3://"): key = key.split("/", 3)[-1]

#             s3 = boto3.client(
#                 's3',
#                 aws_access_key_id=current_app.config.get('AWS_ACCESS_KEY_ID'),
#                 aws_secret_access_key=current_app.config.get('AWS_SECRET_ACCESS_KEY'),
#                 region_name=current_app.config.get('AWS_REGION')
#             )
#             response = s3.get_object(Bucket=current_app.config.get('S3_BUCKET_NAME'), Key=key)
#             return base64.b64encode(response['Body'].read()).decode("utf-8")
#         except Exception as e:
#             logger.error(f"❌ S3 Read Error: {e}")

#     full_path = os.path.join(current_app.root_path, "static", "uploads", file_path)
#     if not os.path.exists(full_path):
#         if os.path.exists(file_path): full_path = file_path
#         else: return None
        
#     try:
#         with open(full_path, "rb") as f:
#             return base64.b64encode(f.read()).decode("utf-8")
#     except Exception as e:
#         logger.error(f"❌ Local Read Error: {e}")
#         return None


# # ====================================================
# # 3. VERIFICATION TASK (FINAL FIXED VERSION)
# # ====================================================
# @celery.task(bind=True, name="app.tasks.verify_document_async")
# def verify_document_async(self, vendor_req_id, doc_type, data):
#     app = create_app()
#     with app.app_context():
#         req = VendorRequest.query.get(vendor_req_id)
#         if not req: return {"valid": False, "error": "Vendor Request not found"}

#         try:
#             result = {}

#             # =========================================================
#             # 1. PAN VERIFICATION
#             # =========================================================
#             if doc_type == "PAN":
#                 pan = data.get("pan_number", "").strip().upper()
#                 pan_file_path = data.get("pan_file_path")
                
#                 # --- OCR STEP ---
#                 if not pan_file_path: raise ValueError("PAN File missing")
#                 b64_doc = file_to_base64(pan_file_path)
                
#                 ocr_headers = { "Content-Type": "application/json", "api-key": app.config["IDFY_API_KEY"], "account-id": app.config["IDFY_ACCOUNT_ID"] }
#                 ocr_res = requests.post("https://eve.idfy.com/v3/tasks/async/extract/ind_pan", headers=ocr_headers, json={"task_id": str(uuid.uuid4()), "group_id": f"VR_{req.id}", "data": {"document1": b64_doc}}, timeout=30)
#                 ocr_res.raise_for_status()
                
#                 ocr_data = poll_task(ocr_res.json()["request_id"])
#                 ocr_out = ocr_data.get("result", {}).get("extraction_output", {})
#                 dob_on_card = ocr_out.get("date_of_birth")

#                 # --- VERIFY STEP ---
#                 v_req_id = run_task("ind_pan", { 
#                     "task_id": str(uuid.uuid4()), 
#                     "group_id": f"VR_{req.id}", 
#                     "data": { 
#                         "id_number": pan, 
#                         "full_name": ocr_out.get("name_on_card"), 
#                         "dob": dob_on_card,
#                         "get_contact_details": False 
#                     } 
#                 })
                
#                 api_resp = poll_task(v_req_id)
#                 result_root = api_resp.get("result", {})
#                 src = result_root.get("source_output") or {}
                
#                 # STATUS CHECK
#                 is_valid = (api_resp.get("status") == "completed") and (src.get("status") == "id_found")

#                 # PERSIST AADHAAR (If provided)
#                 if is_valid:
#                     req.is_pan_verified = True
#                     req.pan_number = pan
#                     if pan_file_path: req.pan_file_path = pan_file_path
                    
#                     aadhaar_input = data.get("aadhaar_number", "").strip()
#                     if aadhaar_input:
#                         req.aadhaar_number = aadhaar_input

#                 # MAPPING (Based on your log: "aadhaar_seeding_status": true)
#                 seeding = src.get("aadhaar_seeding_status")
#                 seeding_txt = "LINKED" if seeding is True else ("NOT LINKED" if seeding is False else "Unknown")

#                 result = {
#                     "valid": is_valid,
#                     "details": {
#                         "pan": {
#                             "is_valid": is_valid,
#                             "status_text": src.get("pan_status") or src.get("status"),
#                             "ocr_name": ocr_out.get("name_on_card") or "N/A", 
#                             "full_name": src.get("full_name") or src.get("name_match_score") or "Matched",       
#                             "category": src.get("category") or "Individual",          
#                             "aadhaar_seeding_status": seeding_txt
#                         }
#                     }
#                 }
#                 _internal_audit_log(req.id, "PAN", "SUCCESS" if is_valid else "FAILED", data, api_resp)

#             # =========================================================
#             # 2. GST VERIFICATION (Fix: filing_details)
#             # =========================================================
#             elif doc_type == "GST":
#                 gst = data.get("gst_number", "").strip().upper()
#                 gst_file_path = data.get("gst_file_path")

#                 t_id = run_task("ind_gst_certificate", {
#                     "task_id": str(uuid.uuid4()), "group_id": f"VR_{req.id}",
#                     "data": { "gstin": gst, "filing_details": True }
#                 })
#                 api_resp = poll_task(t_id)
#                 src = api_resp.get("result", {}).get("source_output", {})
                
#                 is_active = (api_resp.get("status") == "completed") and (src.get("gstin_status") == "Active")
                
#                 if is_active:
#                     req.is_gst_verified = True
#                     req.gst_number = gst
#                     req.gst_registered = "YES"
#                     if gst_file_path: req.gst_file_path = gst_file_path
                
#                 # ✅ FIX: Log shows 'filing_details', not 'filing_status'
#                 filing_txt = "N/A"
#                 filing_source = src.get("filing_details") or src.get("filing_status")
                
#                 if filing_source:
#                     gstr3b = filing_source.get("gstr3b", [])
#                     recent = gstr3b[:6] 
#                     filed_count = sum(1 for f in recent if f.get("status") == "Filed")
#                     filing_txt = f"{filed_count}/{len(recent)} Filed"

#                 result = {
#                     "valid": is_active,
#                     "details": {
#                         "gst": {
#                             "gstin_status": src.get("gstin_status") or "Inactive",
#                             "legal_name": src.get("legal_name") or "N/A",
#                             "trade_name": src.get("trade_name") or "N/A",
#                             "taxpayer_type": src.get("taxpayer_type") or "N/A", 
#                             "registration_date": src.get("date_of_registration"), # Updated key based on log
#                             "filing_status": filing_txt
#                         }
#                     }
#                 }
#                 _internal_audit_log(req.id, "GST", "SUCCESS" if is_active else "FAILED", data, api_resp)

#             # =========================================================
#             # 3. MSME VERIFICATION (Fix: general_details)
#             # =========================================================
#             elif doc_type == "MSME":
#                 msme = data.get("msme_number", "").strip().upper()
#                 msme_file_path = data.get("msme_file_path")
                
#                 t_id = run_task("udyam_aadhaar", {
#                     "task_id": str(uuid.uuid4()), "group_id": f"VR_{req.id}", "data": { "uam_number": msme }
#                 })
#                 api_resp = poll_task(t_id)
#                 src = api_resp.get("result", {}).get("source_output", {})
                
#                 # Log shows "general_details" holds the clean data
#                 gen_details = src.get("general_details", {})
                
#                 found = (api_resp.get("status") == "completed") and (src.get("status") == "id_found")
                
#                 # ✅ FIX: Get Type from general_details -> enterprise_type
#                 # The root enterprise_type is a list of dicts, which breaks logic.
#                 api_msme_type = gen_details.get("enterprise_type") 

#                 if found:
#                     req.is_msme_verified = True
#                     req.msme_number = msme
#                     req.msme_registered = "YES"
#                     if msme_file_path: req.msme_file_path = msme_file_path
                    
#                     # Persist Type: Prefer API, fallback to user input
#                     if api_msme_type:
#                         req.msme_type = str(api_msme_type).capitalize()
#                     else:
#                         user_type = data.get("msme_type")
#                         if user_type: req.msme_type = user_type

#                 result = {
#                     "valid": found,
#                     "details": {
#                         "msme": {
#                             "status": src.get("status"),
#                             "enterprise_name": gen_details.get("enterprise_name") or "N/A",
#                             "enterprise_type": api_msme_type or "N/A", 
#                             "major_activity": gen_details.get("major_activity") or "N/A",
#                             "organisation_type": gen_details.get("organization_type") or "N/A" # Note spelling 'z' in log
#                         }
#                     }
#                 }
#                 _internal_audit_log(req.id, "MSME", "SUCCESS" if found else "FAILED", data, api_resp)

#             # =========================================================
#             # 4. BANK VERIFICATION (Fix: Flat Structure)
#             # =========================================================
#             elif doc_type == "BANK":
#                 acc = data.get("bank_account_no")
#                 ifsc = data.get("ifsc_code")
#                 bank_proof_path = data.get("bank_proof_file_path")

#                 t_id = run_task("validate_bank_account", {
#                     "task_id": str(uuid.uuid4()), "group_id": f"VR_{req.id}", "data": { "bank_account_no": acc, "bank_ifsc_code": ifsc, "nf_verification": False }
#                 })
#                 api_resp = poll_task(t_id)
                
#                 # ✅ FIX: Log shows result is FLAT. There is no 'source_output'.
#                 # result: {"account_exists": "YES", ...}
#                 src = api_resp.get("result", {})
                
#                 raw_exists = src.get("account_exists")
#                 is_exists = (raw_exists is True) or (str(raw_exists).upper() in ["YES", "TRUE", "1"])
                
#                 valid = (api_resp.get("status") == "completed") and is_exists
                
#                 if valid:
#                     req.is_bank_verified = True
#                     req.bank_account_no = acc
#                     req.bank_ifsc = ifsc
#                     req.bank_account_holder_name = src.get("name_at_bank")
#                     if bank_proof_path: req.bank_proof_file_path = bank_proof_path

#                 result = {
#                     "valid": valid,
#                     "details": {
#                         "bank": {
#                             "account_exists": "YES" if valid else "NO",
#                             "name_at_bank": src.get("name_at_bank") or "N/A",
#                             # Log does NOT have 'utr', using 'task_id' or 'request_id' as ref if needed
#                             "utr": src.get("utr") or src.get("request_id") or "-"
#                         }
#                     }
#                 }
#                 _internal_audit_log(req.id, "BANK", "SUCCESS" if valid else "FAILED", data, api_resp)

#             db.session.commit()
#             return result

#         except Exception as e:
#             db.session.rollback()
#             return {"valid": False, "error": str(e)}

# def _internal_audit_log(req_id, vtype, status, input_payload, response):
#     try:
#         db.session.add(VerificationLog(
#             vendor_request_id=req_id, verification_type=vtype,
#             status=status, input_payload=input_payload, api_response=response
#         ))
#         db.session.flush()
#     except:
#         pass









import uuid
import base64
import os
import boto3
import requests
import logging
from urllib.parse import urlparse
from flask import current_app
from flask_mail import Message

# Extensions & Models
from app.extensions import celery, mail, db
from app.models import VendorRequest, VerificationLog
from app import create_app

# IDfy Helpers
from app.external.idfy import run_task, poll_task

logger = logging.getLogger(__name__)

# ====================================================
# 1. HELPER: File Reader (Safe for S3 & Local)
# ====================================================
def file_to_base64(file_path):
    if not file_path or not isinstance(file_path, str):
        return None

    use_s3 = current_app.config.get('USE_S3')
    
    if use_s3:
        try:
            key = file_path
            if key.startswith("http"):
                key = urlparse(key).path.lstrip("/")
            elif key.startswith("s3://"):
                key = key.split("/", 3)[-1]

            s3 = boto3.client(
                's3',
                aws_access_key_id=current_app.config.get('AWS_ACCESS_KEY_ID'),
                aws_secret_access_key=current_app.config.get('AWS_SECRET_ACCESS_KEY'),
                region_name=current_app.config.get('AWS_REGION')
            )
            response = s3.get_object(Bucket=current_app.config.get('S3_BUCKET_NAME'), Key=key)
            return base64.b64encode(response['Body'].read()).decode("utf-8")
        except Exception as e:
            logger.error(f"❌ S3 Read Error: {e}")
            return None

    full_path = os.path.join(current_app.root_path, "static", "uploads", file_path)
    if not os.path.exists(full_path):
        if os.path.exists(file_path): 
            full_path = file_path
        else: 
            return None
        
    try:
        with open(full_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    except Exception as e:
        logger.error(f"❌ Local Read Error: {e}")
        return None


# ====================================================
# 2. AUDIT LOG HELPER (Internal)
# ====================================================
def _internal_audit_log(req_id, vtype, status, input_payload, response):
    try:
        log_entry = VerificationLog(
            vendor_request_id=req_id, 
            verification_type=vtype,
            status=status, 
            input_payload=input_payload, 
            api_response=response
        )
        db.session.add(log_entry)
        # Flush to generate ID, commit happens in main task
        db.session.flush()
    except Exception as e:
        logger.error(f"❌ Audit Log Error: {e}")


# ====================================================
# 3. VERIFICATION TASK (FINAL)
# ====================================================
@celery.task(bind=True, name="app.tasks.verify_document_async")
def verify_document_async(self, vendor_req_id, doc_type, data):
    app = create_app()
    with app.app_context():
        req = VendorRequest.query.get(vendor_req_id)
        if not req: 
            return {"valid": False, "error": "Vendor Request not found"}

        try:
            result = {}
            is_valid = False
            api_resp = {}

            # =========================================================
            # A. PAN VERIFICATION
            # =========================================================
            if doc_type == "PAN":
                pan = data.get("pan_number", "").strip().upper()
                pan_file_path = data.get("pan_file_path")
                
                # 1. OCR Extraction
                if not pan_file_path: raise ValueError("PAN File Path missing")
                b64_doc = file_to_base64(pan_file_path)
                
                ocr_headers = {
                    "Content-Type": "application/json", 
                    "api-key": app.config["IDFY_API_KEY"], 
                    "account-id": app.config["IDFY_ACCOUNT_ID"]
                }
                ocr_payload = {
                    "task_id": str(uuid.uuid4()), 
                    "group_id": f"VR_{req.id}", 
                    "data": {"document1": b64_doc}
                }
                
                ocr_res = requests.post("https://eve.idfy.com/v3/tasks/async/extract/ind_pan", headers=ocr_headers, json=ocr_payload, timeout=30)
                ocr_res.raise_for_status()
                
                ocr_data = poll_task(ocr_res.json()["request_id"])
                ocr_out = ocr_data.get("result", {}).get("extraction_output", {})
                
                # 2. Verification
                v_req_id = run_task("ind_pan", { 
                    "task_id": str(uuid.uuid4()), 
                    "group_id": f"VR_{req.id}", 
                    "data": { 
                        "id_number": pan, 
                        "full_name": ocr_out.get("name_on_card"), 
                        "dob": ocr_out.get("date_of_birth"),
                        "get_contact_details": False 
                    } 
                })
                
                api_resp = poll_task(v_req_id)
                src = api_resp.get("result", {}).get("source_output", {})
                
                is_valid = (api_resp.get("status") == "completed") and (src.get("status") == "id_found")

                # DB UPDATE
                if is_valid:
                    req.is_pan_verified = True
                    req.pan_number = pan
                    if pan_file_path: req.pan_file_path = pan_file_path
                    
                    aadhaar_input = data.get("aadhaar_number", "").strip()
                    if aadhaar_input: req.aadhaar_number = aadhaar_input

                # FRONTEND RESPONSE
                seeding = src.get("aadhaar_seeding_status")
                seeding_txt = "LINKED" if seeding is True else ("NOT LINKED" if seeding is False else "Unknown")

                result = {
                    "valid": is_valid,
                    "details": {
                        "pan": {
                            "status_text": src.get("pan_status") or src.get("status"),
                            "ocr_name": ocr_out.get("name_on_card") or "N/A", 
                            "full_name": src.get("full_name") or src.get("name_match_score"),
                            "aadhaar_seeding": seeding_txt
                        }
                    }
                }
                _internal_audit_log(req.id, "PAN", "SUCCESS" if is_valid else "FAILED", data, api_resp)

            # =========================================================
            # B. GST VERIFICATION (ALL FIELDS)
            # =========================================================
            elif doc_type == "GST":
                gst = data.get("gst_number", "").strip().upper()
                gst_file_path = data.get("gst_file_path")

                # 1. API CALL
                t_id = run_task("ind_gst_certificate", {
                    "task_id": str(uuid.uuid4()), 
                    "group_id": f"VR_{req.id}",
                    "data": { "gstin": gst, "filing_details": True }
                })
                api_resp = poll_task(t_id)
                
                # 2. GET FRESH DATA
                src = api_resp.get("result", {}).get("source_output", {})
                
                is_valid = (api_resp.get("status") == "completed") and (src.get("gstin_status") == "Active")
                
                # 3. DB UPDATE
                if is_valid:
                    req.is_gst_verified = True
                    req.gst_number = gst
                    req.gst_registered = "YES"
                    if gst_file_path: req.gst_file_path = gst_file_path
                    
                    # Try to save details if DB columns exist (Fail silently if they don't)
                    try:
                        req.gst_legal_name = src.get("legal_name")
                        req.gst_trade_name = src.get("trade_name")
                    except:
                        pass

                # 4. FRONTEND RESPONSE (ALL FIELDS FROM API)
                filing_source = src.get("filing_details") or src.get("filing_status")
                filing_txt = "N/A"
                if filing_source:
                    gstr3b = filing_source.get("gstr3b", [])
                    recent = gstr3b[:6] 
                    filed_count = sum(1 for f in recent if f.get("status") == "Filed")
                    filing_txt = f"{filed_count}/{len(recent)} Filed"

                result = {
                    "valid": is_valid,
                    "details": {
                        "gst": {
                            "gstin_status": src.get("gstin_status"),
                            "legal_name": src.get("legal_name"),
                            "trade_name": src.get("trade_name"),
                            "registration_date": src.get("date_of_registration"),
                            "taxpayer_type": src.get("taxpayer_type"),
                            "constitution": src.get("constitution_of_business"),
                            "nature_of_business": src.get("nature_of_business_activity"),
                            "jurisdiction_state": src.get("state_jurisdiction"),
                            "jurisdiction_center": src.get("center_jurisdiction"),
                            "filing_status": filing_txt,
                            "address": src.get("principal_place_of_business")
                        }
                    }
                }
                _internal_audit_log(req.id, "GST", "SUCCESS" if is_valid else "FAILED", data, api_resp)

            # =========================================================
            # C. MSME VERIFICATION
            # =========================================================
            elif doc_type == "MSME":
                msme = data.get("msme_number", "").strip().upper()
                msme_file_path = data.get("msme_file_path")
                
                t_id = run_task("udyam_aadhaar", {
                    "task_id": str(uuid.uuid4()), 
                    "group_id": f"VR_{req.id}", 
                    "data": { "uam_number": msme }
                })
                api_resp = poll_task(t_id)
                src = api_resp.get("result", {}).get("source_output", {})
                gen_details = src.get("general_details", {})
                
                is_valid = (api_resp.get("status") == "completed") and (src.get("status") == "id_found")
                
                # NORMALIZE TYPE
                raw_type = gen_details.get("enterprise_type")
                api_msme_type = None
                if isinstance(raw_type, list) and len(raw_type) > 0:
                    api_msme_type = raw_type[0].get("name")
                elif isinstance(raw_type, dict):
                    api_msme_type = raw_type.get("name")
                elif isinstance(raw_type, str):
                    api_msme_type = raw_type

                if is_valid:
                    req.is_msme_verified = True
                    req.msme_number = msme
                    req.msme_registered = "YES"
                    if msme_file_path: req.msme_file_path = msme_file_path
                    
                    if api_msme_type:
                        req.msme_type = str(api_msme_type).capitalize()
                    else:
                        req.msme_type = data.get("msme_type", "Micro")

                result = {
                    "valid": is_valid,
                    "details": {
                        "msme": {
                            "enterprise_name": gen_details.get("enterprise_name"),
                            "type": api_msme_type or "N/A",
                            "activity": gen_details.get("major_activity")
                        }
                    }
                }
                _internal_audit_log(req.id, "MSME", "SUCCESS" if is_valid else "FAILED", data, api_resp)

            # =========================================================
            # D. BANK VERIFICATION
            # =========================================================
            elif doc_type == "BANK":
                acc = data.get("bank_account_no")
                ifsc = data.get("ifsc_code")
                bank_proof_path = data.get("bank_proof_file_path")

                t_id = run_task("validate_bank_account", {
                    "task_id": str(uuid.uuid4()), 
                    "group_id": f"VR_{req.id}", 
                    "data": { "bank_account_no": acc, "bank_ifsc_code": ifsc, "nf_verification": False }
                })
                api_resp = poll_task(t_id)
                src = api_resp.get("result", {})
                
                raw_exists = src.get("account_exists")
                is_exists = (raw_exists is True) or (str(raw_exists).upper() in ["YES", "TRUE", "1"])
                is_valid = (api_resp.get("status") == "completed") and is_exists

                if is_valid:
                    req.is_bank_verified = True
                    req.bank_account_no = acc
                    req.bank_ifsc = ifsc
                    req.bank_account_holder_name = src.get("name_at_bank")
                    if bank_proof_path: req.bank_proof_file_path = bank_proof_path

                result = {
                    "valid": is_valid,
                    "details": {
                        "bank": {
                            "account_exists": "YES" if is_valid else "NO",
                            "name_at_bank": src.get("name_at_bank"),
                            "utr": src.get("utr") or src.get("request_id") or "-"
                        }
                    }
                }
                _internal_audit_log(req.id, "BANK", "SUCCESS" if is_valid else "FAILED", data, api_resp)

            db.session.commit()
            return result

        except Exception as e:
            db.session.rollback()
            logger.error(f"❌ Verification Task Failed: {e}")
            return {"valid": False, "error": str(e)}

@celery.task(bind=True, max_retries=3)
def send_async_email(self, subject, recipient, body, is_html=True):
    try:
        msg = Message(subject, recipients=[recipient])
        if is_html:
            msg.html = body
        else:
            msg.body = body
        mail.send(msg)
        return f"Email sent to {recipient}"
    except Exception as e:
        self.retry(exc=e, countdown=60)