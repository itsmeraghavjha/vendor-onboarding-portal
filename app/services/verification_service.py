
# import uuid
# import json
# import base64
# import os
# import boto3
# import requests
# from urllib.parse import urlparse
# from flask import current_app
# from app.extensions import db
# from app.models import VendorRequest, VerificationLog

# # ---------------------------------------------------------
# # IMPORT IDFY FUNCTIONS
# # ---------------------------------------------------------
# from app.external.idfy import run_task, poll_task

# class VerificationService:
#     """
#     SINGLE SOURCE OF TRUTH FOR VERIFICATION
#     Integrates with IDfy Async API v3
#     """

#     # =====================================================
#     # HELPER: FILE TO BASE64 (For OCR)
#     # =====================================================
#     @staticmethod
#     def file_to_base64(file_path):
#         """
#         Reads a file from S3 (if enabled) or Local Disk and returns Base64 string.
#         """
#         if not file_path:
#             return None
        
#         print(f"--> Reading File: {file_path}")

#         # --- 1. Try S3 Fetch if configured ---
#         if current_app.config.get('USE_S3'):
#             try:
#                 # Normalize Key (remove s3:// or http prefixes)
#                 key = file_path
#                 if key.startswith("http"):
#                     key = urlparse(key).path.lstrip("/")
#                 elif key.startswith("s3://"):
#                     key = key.split("/", 3)[-1]

#                 s3 = boto3.client(
#                     's3',
#                     aws_access_key_id=current_app.config.get('AWS_ACCESS_KEY_ID'),
#                     aws_secret_access_key=current_app.config.get('AWS_SECRET_ACCESS_KEY'),
#                     region_name=current_app.config.get('AWS_REGION')
#                 )
#                 bucket_name = current_app.config.get('S3_BUCKET_NAME')
                
#                 print(f"    S3 Fetch: Bucket={bucket_name}, Key={key}")
#                 response = s3.get_object(Bucket=bucket_name, Key=key)
#                 file_content = response['Body'].read()
#                 return base64.b64encode(file_content).decode("utf-8")
            
#             except Exception as e:
#                 print(f"❌ S3 Read Error: {e}")
#                 # Fallback to local if S3 fails is usually not recommended if path is S3 key, 
#                 # but we proceed just in case.

#         # --- 2. Local Disk Fallback ---
#         # Assuming file_path is relative to static/uploads if not absolute
#         full_path = os.path.join(current_app.root_path, "static", "uploads", file_path)
        
#         if not os.path.exists(full_path):
#             # Try absolute path
#             if os.path.exists(file_path):
#                 full_path = file_path
#             else:
#                 print(f"❌ File not found: {full_path}")
#                 return None
            
#         try:
#             with open(full_path, "rb") as f:
#                 return base64.b64encode(f.read()).decode("utf-8")
#         except Exception as e:
#             print(f"❌ Local Read Error: {e}")
#             return None

#     # =====================================================
#     # ENTRY POINT (USED BY FRONTEND)
#     # =====================================================
#     @staticmethod
#     def verify_vendor_data(data: dict) -> dict:
#         print("\n================ VERIFICATION START ================")
#         print(f"Incoming Data: {json.dumps(data, indent=2)}")

#         vendor_request_id = data.get("vendor_request_id")
#         if not vendor_request_id:
#             return {"error": "vendor_request_id missing", "details": None}

#         req = VendorRequest.query.filter_by(request_id=vendor_request_id).first()
#         if not req:
#             return {"error": "Invalid vendor request", "details": None}

#         details = {}

#         try:
#             # ---------------- PAN (OCR + VERIFY) ----------------
#             if "pan_number" in data:
#                 print(f"--> Starting PAN Verification for {data['pan_number']}")
#                 details["pan"] = VerificationService._verify_pan(req, data)

#             # ---------------- GST ----------------
#             if "gst_number" in data:
#                 print(f"--> Starting GST Verification for {data['gst_number']}")
#                 details["gst"] = VerificationService._verify_gst(req, data)

#             # ---------------- MSME ----------------
#             if "msme_number" in data:
#                 print(f"--> Starting MSME Verification for {data['msme_number']}")
#                 details["msme"] = VerificationService._verify_msme(req, data)

#             # ---------------- BANK ----------------
#             if "bank_account_no" in data:
#                 print(f"--> Starting Bank Verification for {data['bank_account_no']}")
#                 details["bank"] = VerificationService._verify_bank(req, data)
                

#             # Final Commit to save all updates (including is_verified flags AND values)
#             db.session.commit()
            
#             print("================ VERIFICATION COMPLETE ================\n")
#             return {
#                 "valid": True,
#                 "details": details
#             }

#         except Exception as e:
#             db.session.rollback()
#             current_app.logger.exception("Verification process failed")
#             print(f"!!! CRITICAL FAILURE: {str(e)}")
#             return {"error": str(e), "details": None}

#     # =====================================================
#     # PAN VERIFICATION (OCR -> VERIFY)
#     # =====================================================
#     @staticmethod
#     def _verify_pan(req: VendorRequest, data: dict) -> dict:
#         pan = data.get("pan_number", "").strip().upper()
#         pan_file_path = data.get("pan_file_path")
        
#         try:
#             # --- STEP 1: OCR ---
#             if not pan_file_path:
#                 raise ValueError("PAN File Path missing. Cannot perform OCR.")

#             b64_doc = VerificationService.file_to_base64(pan_file_path)
#             if not b64_doc:
#                 raise ValueError("Could not read PAN file content.")

#             # We use direct requests for OCR because run_task is configured for verify_with_source
#             ocr_url = "https://eve.idfy.com/v3/tasks/async/extract/ind_pan"
#             headers = {
#                 "Content-Type": "application/json",
#                 "api-key": current_app.config["IDFY_API_KEY"],
#                 "account-id": current_app.config["IDFY_ACCOUNT_ID"],
#             }
#             ocr_payload = {
#                 "task_id": str(uuid.uuid4()),
#                 "group_id": f"VENDOR_{req.id}_OCR",
#                 "data": {"document1": b64_doc}
#             }

#             print("[PAN OCR] Starting Extraction...")
#             ocr_res = requests.post(ocr_url, headers=headers, json=ocr_payload, timeout=30)
#             ocr_res.raise_for_status()
#             ocr_req_id = ocr_res.json().get("request_id")
            
#             print(f"[PAN OCR] Request ID: {ocr_req_id}")
#             ocr_result = poll_task(ocr_req_id) # Reuse poll_task logic
            
#             ocr_output = ocr_result.get("result", {}).get("extraction_output", {})
#             name_on_card = ocr_output.get("name_on_card")
#             dob_on_card = ocr_output.get("date_of_birth")

#             if not name_on_card:
#                 raise ValueError("OCR completed but could not read Name from PAN card.")

#             print(f"[PAN OCR] Extracted Name: {name_on_card}, DOB: {dob_on_card}")

#             # --- STEP 2: VERIFY ---
#             verify_payload = {
#                 "task_id": str(uuid.uuid4()),
#                 "group_id": f"VENDOR_{req.id}",
#                 "data": {
#                     "id_number": pan, 
#                     "full_name": name_on_card,
#                     "dob": dob_on_card,
#                     "get_contact_details": False
#                 }
#             }

#             print(f"[PAN VERIFY] Sending Payload: {verify_payload}")
            
#             # Task Type: 'ind_pan'
#             verify_req_id = run_task("ind_pan", verify_payload)
#             print(f"[PAN VERIFY] Request ID: {verify_req_id}")

#             api_resp = poll_task(verify_req_id)
            
#             # Extract Data
#             result_block = api_resp.get("result", {}).get("source_output", {})
#             status_text = result_block.get("pan_status", "INVALID")
#             id_found = result_block.get("status") == "id_found"
            
#             is_valid = (api_resp.get("status") == "completed") and id_found

#             # Safety check: if 'fake' or 'deleted' appears in status
#             if is_valid and "valid" not in str(status_text).lower():
#                  is_valid = False

#             output = {
#                 "is_valid": is_valid,
#                 "status_text": status_text,
#                 "name_match": result_block.get("name_match"),
#                 "dob_match": result_block.get("dob_match"),
#                 "aadhaar_linked": result_block.get("aadhaar_seeding_status"),
#                 "ocr_name": name_on_card
#             }

#             VerificationService._log(req, "PAN", "SUCCESS" if is_valid else "FAILED", data, api_resp)

#             if is_valid:
#                 # 🔥 FIX FOR REFRESH BUG: Save data immediately
#                 req.is_pan_verified = True
#                 req.pan_number = pan 
            
#             return output

#         except Exception as e:
#             print(f"[PAN] EXCEPTION: {e}")
#             current_app.logger.error(f"PAN Verification Error: {e}")
#             VerificationService._log(req, "PAN", "ERROR", data, {"error": str(e)})
#             return {"is_valid": False, "status_text": "ERROR", "error": str(e)}

#     # =====================================================
#     # GST VERIFICATION
#     # =====================================================
#     @staticmethod
#     def _verify_gst(req: VendorRequest, data: dict) -> dict:
#         gst = data.get("gst_number", "").strip().upper()

#         try:
#             payload = {
#                 "task_id": str(uuid.uuid4()),
#                 "group_id": f"VENDOR_{req.id}",
#                 "data": {
#                     "gstin": gst,
#                     "filing_details": True,
#                     "e_invoice_details": True
#                 }
#             }

#             print(f"[GST] Sending Payload: {payload}")
#             request_id = run_task("ind_gst_certificate", payload)
            
#             api_resp = poll_task(request_id)
            
#             result_block = api_resp.get("result", {}).get("source_output", {})
#             gst_status = result_block.get("gstin_status", "Inactive")
            
#             is_active = (api_resp.get("status") == "completed") and (gst_status == "Active")

#             output = {
#                 "status": result_block.get("status"),
#                 "gstin_status": gst_status,
#                 "legal_name": result_block.get("legal_name"),
#                 "trade_name": result_block.get("trade_name"),
#                 "taxpayer_type": result_block.get("taxpayer_type"),
#                 "e_invoice_status": result_block.get("e_invoice_status"),
#                 "last_6_gstr3b": VerificationService._analyze_gst_filings(result_block.get("filing_details", {})),
#                 "address": result_block.get("principal_place_of_business_address")
#             }

#             VerificationService._log(req, "GST", "SUCCESS" if is_active else "FAILED", data, api_resp)

#             if is_active:
#                 # 🔥 FIX FOR REFRESH BUG: Save data immediately
#                 req.is_gst_verified = True
#                 req.gst_number = gst
#                 # Optional: Autofill names
#                 # if result_block.get("legal_name"): req.vendor_name_basic = result_block.get("legal_name")

#             return output

#         except Exception as e:
#             print(f"[GST] EXCEPTION: {e}")
#             current_app.logger.error(f"GST Verification Error: {e}")
#             VerificationService._log(req, "GST", "ERROR", data, {"error": str(e)})
#             return {"gstin_status": "ERROR", "error": str(e)}

#     # =====================================================
#     # MSME / UDYAM VERIFICATION
#     # =====================================================
#     @staticmethod
#     def _verify_msme(req: VendorRequest, data: dict) -> dict:
#         raw_msme = data.get("msme_number", "").strip().upper()

#         try:
#             payload = {
#                 "task_id": str(uuid.uuid4()),
#                 "group_id": f"VENDOR_{req.id}",
#                 "data": {"uam_number": raw_msme}
#             }

#             print(f"[MSME] Sending Payload: {payload}")
#             request_id = run_task("udyam_aadhaar", payload)
            
#             api_resp = poll_task(request_id)
            
#             result_block = api_resp.get("result", {}).get("source_output", {})
#             general_details = result_block.get("general_details", {})

#             ent_name = (
#                 general_details.get("enterprise_name") or 
#                 result_block.get("enterprise_name") or 
#                 result_block.get("name") or 
#                 "N/A"
#             )

#             ent_type_raw = general_details.get("enterprise_type") or result_block.get("enterprise_type")
#             ent_type = "N/A"
#             if isinstance(ent_type_raw, str):
#                 ent_type = ent_type_raw
#             elif isinstance(ent_type_raw, dict):
#                 ent_type = ent_type_raw.get("label") or ent_type_raw.get("code") or "N/A"

#             found = (api_resp.get("status") == "completed") and (result_block.get("status") == "id_found")

#             output = {
#                 "status": result_block.get("status"),
#                 "name": ent_name,
#                 "type": ent_type,
#                 "major_activity": result_block.get("major_activity")
#             }

#             VerificationService._log(req, "MSME", "SUCCESS" if found else "FAILED", data, api_resp)

#             if found:
#                 # 🔥 FIX FOR REFRESH BUG: Save data immediately
#                 req.is_msme_verified = True
#                 req.msme_number = raw_msme
#                 req.msme_registered = "YES"

#             return output

#         except Exception as e:
#             print(f"[MSME] EXCEPTION: {e}")
#             current_app.logger.error(f"MSME Verification Error: {e}")
#             VerificationService._log(req, "MSME", "ERROR", data, {"error": str(e)})
#             return {"status": "ERROR", "error": str(e)}

#     # =====================================================
#     # BANK ACCOUNT VERIFICATION
#     # =====================================================
#     @staticmethod
#     def _verify_bank(req: VendorRequest, data: dict) -> dict:
#         acc = data.get("bank_account_no", "")
#         ifsc = data.get("ifsc_code", "")

#         try:
#             payload = {
#                 "task_id": str(uuid.uuid4()),
#                 "group_id": f"VENDOR_{req.id}",
#                 "data": {
#                     "bank_account_no": acc,
#                     "bank_ifsc_code": ifsc,
#                     "nf_verification": False
#                 }
#             }

#             print(f"[BANK] Sending Payload: {payload}")
#             request_id = run_task("validate_bank_account", payload)
            
#             api_resp = poll_task(request_id)

#             result_block = api_resp.get("result", {})
#             source_block = result_block.get("source_output") or result_block
            
#             # Check penny drop status
#             is_valid = (api_resp.get("status") == "completed") and (source_block.get("account_exists") == True)

#             output = {
#                 "status": source_block.get("status"),
#                 "account_exists": source_block.get("account_exists"),
#                 "name_at_bank": source_block.get("name_at_bank"),
#                 "utr": source_block.get("utr")
#             }

#             VerificationService._log(req, "BANK", "SUCCESS" if is_valid else "FAILED", data, api_resp)

#             if is_valid:
#                 # 🔥 FIX FOR REFRESH BUG: Save data immediately
#                 req.is_bank_verified = True
#                 req.bank_account_no = acc
#                 req.bank_ifsc = ifsc
#                 req.bank_account_holder_name = source_block.get("name_at_bank")

#             return output

#         except Exception as e:
#             print(f"[BANK] EXCEPTION: {e}")
#             current_app.logger.error(f"Bank Verification Error: {e}")
#             VerificationService._log(req, "BANK", "ERROR", data, {"error": str(e)})
#             return {"status": "ERROR", "error": str(e)}

#     # =====================================================
#     # HELPER: GST FILINGS
#     # =====================================================
#     @staticmethod
#     def _analyze_gst_filings(filing_details):
#         if not filing_details: return "N/A"
#         gstr3b = filing_details.get("gstr3b", [])
#         if not gstr3b: return "0/6"
#         recent = gstr3b[:6]
#         filed = sum(1 for f in recent if f.get("status") == "Filed")
#         return f"{filed}/6 Filed"

#     # =====================================================
#     # UNVERIFY & LOGS
#     # =====================================================
#     @staticmethod
#     def mark_unverified(req: VendorRequest, section: str):
#         if section == "pan":
#             req.is_pan_verified = False
#         elif section == "gst":
#             req.is_gst_verified = False
#         elif section == "msme":
#             req.is_msme_verified = False
#         elif section == "bank":
#             req.is_bank_verified = False
#         else:
#             raise ValueError(f"Invalid section: {section}")
#         db.session.add(req)
#         db.session.commit()

#     @staticmethod
#     def _log(req, vtype, status, payload, response):
#         try:
#             db.session.add(
#                 VerificationLog(
#                     vendor_request_id=req.id,
#                     verification_type=vtype,
#                     status=status,
#                     input_payload=payload,
#                     api_response=response
#                 )
#             )
#             # Flush to generate ID, do not commit
#             db.session.flush() 
#         except Exception as e:
#             print(f"!!! LOG FAILURE: {e}")



import uuid
import json
import base64
import os
import boto3
import requests
from urllib.parse import urlparse
from flask import current_app
from app.extensions import db
from app.models import VendorRequest, VerificationLog

# Import the helper functions you uploaded
from app.external.idfy import run_task, poll_task
from app.tasks import verify_document_async

class VerificationService:
    """
    SINGLE SOURCE OF TRUTH FOR VERIFICATION
    Integrates with IDfy Async API v3 via app.external.idfy
    """

    @staticmethod
    def file_to_base64(file_path):
        """Reads a file from S3 (if enabled) or Local Disk and returns Base64 string."""
        if not file_path:
            return None
        
        # --- 1. Try S3 Fetch if configured ---
        if current_app.config.get('USE_S3'):
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
                bucket_name = current_app.config.get('S3_BUCKET_NAME')
                
                response = s3.get_object(Bucket=bucket_name, Key=key)
                file_content = response['Body'].read()
                return base64.b64encode(file_content).decode("utf-8")
            
            except Exception as e:
                print(f"❌ S3 Read Error: {e}")

        # --- 2. Local Disk Fallback ---
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
            print(f"❌ Local Read Error: {e}")
            return None

    @staticmethod
    def verify_vendor_data(data: dict) -> dict:
        """
        Dispatches verification logic to a background Celery task.
        Returns: { "task_id": "..." }
        """
        req_id = data.get("vendor_request_id")
        req = VendorRequest.query.filter_by(request_id=req_id).first()
        if not req:
            return {"error": "Invalid Request ID"}

        doc_type = None
        if "pan_number" in data: doc_type = "PAN"
        elif "gst_number" in data: doc_type = "GST"
        elif "msme_number" in data: doc_type = "MSME"
        elif "bank_account_no" in data: doc_type = "BANK"
        
        if not doc_type:
            return {"error": "Unknown verification type"}

        # Launch Async Task
        task = verify_document_async.delay(req.id, doc_type, data)

        return {
            "status": "processing",
            "task_id": task.id
        }
   
   
   
    # =====================================================
    # INDIVIDUAL VERIFICATION METHODS
    # =====================================================

    @staticmethod
    def _verify_pan(req: VendorRequest, data: dict) -> dict:
        pan = data.get("pan_number", "").strip().upper()
        pan_file_path = data.get("pan_file_path")
        
        # 1. OCR Step
        if not pan_file_path: raise ValueError("PAN File missing for OCR")
        b64_doc = VerificationService.file_to_base64(pan_file_path)
        if not b64_doc: raise ValueError("Could not read PAN file content")

        # Call OCR directly
        ocr_url = "https://eve.idfy.com/v3/tasks/async/extract/ind_pan"
        headers = {
            "Content-Type": "application/json",
            "api-key": current_app.config["IDFY_API_KEY"],
            "account-id": current_app.config["IDFY_ACCOUNT_ID"],
        }
        ocr_res = requests.post(ocr_url, headers=headers, json={
            "task_id": str(uuid.uuid4()), "group_id": f"VENDOR_{req.id}_OCR", "data": {"document1": b64_doc}
        }, timeout=30)
        ocr_res.raise_for_status()
        
        # Poll OCR
        ocr_result = poll_task(ocr_res.json().get("request_id"))
        ocr_output = ocr_result.get("result", {}).get("extraction_output", {})
        name_on_card = ocr_output.get("name_on_card")
        dob_on_card = ocr_output.get("date_of_birth")

        if not name_on_card: raise ValueError("OCR could not read Name from PAN card")

        # 2. Verify Step
        verify_req_id = run_task("ind_pan", {
            "task_id": str(uuid.uuid4()), "group_id": f"VENDOR_{req.id}",
            "data": { "id_number": pan, "full_name": name_on_card, "dob": dob_on_card, "get_contact_details": False }
        })
        api_resp = poll_task(verify_req_id)
        
        result_block = api_resp.get("result", {}).get("source_output", {})
        status_text = result_block.get("pan_status", "INVALID")
        id_found = result_block.get("status") == "id_found"
        
        is_valid = (api_resp.get("status") == "completed") and id_found
        if is_valid and "valid" not in str(status_text).lower(): is_valid = False

        VerificationService._log(req, "PAN", "SUCCESS" if is_valid else "FAILED", data, api_resp)

        if is_valid:
            req.is_pan_verified = True
            req.pan_number = pan 

        return {
            "is_valid": is_valid, "status_text": status_text,
            "name_match": result_block.get("name_match"), "ocr_name": name_on_card,
            "aadhaar_linked": result_block.get("aadhaar_seeding_status")
        }

    @staticmethod
    def _verify_gst(req: VendorRequest, data: dict) -> dict:
        gst = data.get("gst_number", "").strip().upper()
        req_id = run_task("ind_gst_certificate", {
            "task_id": str(uuid.uuid4()), "group_id": f"VENDOR_{req.id}",
            "data": { "gstin": gst, "filing_details": True, "e_invoice_details": True }
        })
        api_resp = poll_task(req_id)
        
        result_block = api_resp.get("result", {}).get("source_output", {})
        gst_status = result_block.get("gstin_status", "Inactive")
        is_active = (api_resp.get("status") == "completed") and (gst_status == "Active")

        VerificationService._log(req, "GST", "SUCCESS" if is_active else "FAILED", data, api_resp)

        if is_active:
            req.is_gst_verified = True
            req.gst_number = gst

        return {
            "gstin_status": gst_status, 
            "legal_name": result_block.get("legal_name"),
            "trade_name": result_block.get("trade_name"), 
            "address": result_block.get("principal_place_of_business_address"),
            "last_6_gstr3b": VerificationService._analyze_gst_filings(result_block.get("filing_details", {}))
        }

    @staticmethod
    def _verify_msme(req: VendorRequest, data: dict) -> dict:
        raw_msme = data.get("msme_number", "").strip().upper()
        req_id = run_task("udyam_aadhaar", {
            "task_id": str(uuid.uuid4()), "group_id": f"VENDOR_{req.id}",
            "data": {"uam_number": raw_msme}
        })
        api_resp = poll_task(req_id)
        
        result_block = api_resp.get("result", {}).get("source_output", {})
        found = (api_resp.get("status") == "completed") and (result_block.get("status") == "id_found")

        VerificationService._log(req, "MSME", "SUCCESS" if found else "FAILED", data, api_resp)

        if found:
            req.is_msme_verified = True
            req.msme_number = raw_msme
            req.msme_registered = "YES"

        return {"status": result_block.get("status"), "name": result_block.get("enterprise_name")}

    @staticmethod
    def _verify_bank(req: VendorRequest, data: dict) -> dict:
        acc = data.get("bank_account_no", "")
        ifsc = data.get("ifsc_code", "")
        req_id = run_task("validate_bank_account", {
            "task_id": str(uuid.uuid4()), "group_id": f"VENDOR_{req.id}",
            "data": { "bank_account_no": acc, "bank_ifsc_code": ifsc, "nf_verification": False }
        })
        api_resp = poll_task(req_id)
        
        source_block = api_resp.get("result", {}).get("source_output", {}) or api_resp.get("result", {})
        is_valid = (api_resp.get("status") == "completed") and (source_block.get("account_exists") == True)

        VerificationService._log(req, "BANK", "SUCCESS" if is_valid else "FAILED", data, api_resp)

        if is_valid:
            req.is_bank_verified = True
            req.bank_account_no = acc
            req.bank_ifsc = ifsc
            req.bank_account_holder_name = source_block.get("name_at_bank")

        return {"account_exists": source_block.get("account_exists"), "name_at_bank": source_block.get("name_at_bank")}

    @staticmethod
    def _analyze_gst_filings(filing_details):
        if not filing_details: return "N/A"
        gstr3b = filing_details.get("gstr3b", [])
        if not gstr3b: return "0/6"
        recent = gstr3b[:6]
        filed = sum(1 for f in recent if f.get("status") == "Filed")
        return f"{filed}/6 Filed"

    @staticmethod
    def _log(req, vtype, status, payload, response):
        try:
            db.session.add(VerificationLog(
                vendor_request_id=req.id, verification_type=vtype, status=status,
                input_payload=payload, api_response=response
            ))
            db.session.flush()
        except Exception as e:
            print(f"!!! LOG FAILURE: {e}")