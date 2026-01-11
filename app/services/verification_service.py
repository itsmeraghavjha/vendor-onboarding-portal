




# import uuid
# import time
# import requests
# import logging
# import base64
# import os
# import boto3
# from flask import current_app


# logger = logging.getLogger(__name__)

# def normalize_pan(pan):
#     if not pan:
#         return None
#     return pan.upper().replace(" ", "").replace("\n", "").strip()

# class VerificationService:
#     BASE_URL = "https://eve.idfy.com/v3"

#     # --------------------------------------------------
#     # HELPERS
#     # --------------------------------------------------

#     @staticmethod
#     def file_to_base64(file_path):
#         """
#         Reads a file from S3 (if enabled) or Local Disk and returns Base64 string.
#         """
#         if not file_path:
#             return None
        
#         # --- 1. Try S3 Fetch if configured ---
#         if current_app.config.get('USE_S3'):
#             try:
#                 s3 = boto3.client(
#                     's3',
#                     aws_access_key_id=current_app.config.get('AWS_ACCESS_KEY_ID'),
#                     aws_secret_access_key=current_app.config.get('AWS_SECRET_ACCESS_KEY'),
#                     region_name=current_app.config.get('AWS_REGION')
#                 )
#                 bucket_name = current_app.config.get('S3_BUCKET_NAME')
                
#                 # Fetch object from S3
#                 # file_path is the Key (e.g., PAN/1234_abc.png)
#                 response = s3.get_object(Bucket=bucket_name, Key=file_path)
#                 file_content = response['Body'].read()
                
#                 return base64.b64encode(file_content).decode("utf-8")
            
#             except Exception as e:
#                 logger.error(f"❌ S3 Read Error for {file_path}: {e}")
#                 # If S3 fails, we can try local fallback, but usually, this means failure.
#                 return None

#         # --- 2. Local Disk Fallback ---
#         full_path = os.path.join(
#             current_app.root_path, "static", "uploads", file_path
#         )
        
#         # Check if file exists locally
#         if not os.path.exists(full_path):
#             # Attempt absolute path check (for temp files)
#             if os.path.exists(file_path):
#                 full_path = file_path
#             else:
#                 logger.error(f"❌ File not found for OCR: {full_path}")
#                 return None
            
#         try:
#             with open(full_path, "rb") as f:
#                 return base64.b64encode(f.read()).decode("utf-8")
#         except Exception as e:
#             logger.error(f"❌ Local Read Error: {e}")
#             return None

#     @staticmethod
#     def get_headers():
#         return {
#             "Content-Type": "application/json",
#             "api-key": current_app.config.get("IDFY_API_KEY"),
#             "account-id": current_app.config.get("IDFY_ACCOUNT_ID"),
#         }

#     # --------------------------------------------------
#     # TASK STARTER
#     # --------------------------------------------------

#     @staticmethod
#     def start_task(task_type, data_payload):
#         url = f"{VerificationService.BASE_URL}/tasks/async/verify_with_source/{task_type}"

#         payload = {
#             "task_id": f"task-{uuid.uuid4()}",
#             "group_id": f"group-{uuid.uuid4()}",
#             "data": data_payload,
#         }

#         try:
#             response = requests.post(
#                 url,
#                 headers=VerificationService.get_headers(),
#                 json=payload,
#                 timeout=10,
#             )
#             response.raise_for_status()
#             return response.json().get("request_id"), None
#         except Exception as e:
#             logger.exception(f"Failed starting task {task_type}")
#             return None, str(e)

#     # --------------------------------------------------
#     # POLLING
#     # --------------------------------------------------

#     @staticmethod
#     def check_status(request_id):
#         url = f"{VerificationService.BASE_URL}/tasks"
#         params = {"request_id": request_id}

#         try:
#             response = requests.get(
#                 url,
#                 headers=VerificationService.get_headers(),
#                 params=params,
#                 timeout=5,
#             )
#             response.raise_for_status()
#             data = response.json()

#             if data and isinstance(data, list) and len(data) > 0:
#                 task = data[0]
#                 return {"status": task.get("status"), "result": task.get("result")}

#             return {"status": "pending"}

#         except Exception as e:
#             return {"status": "error", "error": str(e)}

#     @staticmethod
#     def poll_result_blocking(request_id, max_retries=12, delay=2):
#         print(f"DEBUG: Polling ID: {request_id}")

#         for _ in range(max_retries):
#             res = VerificationService.check_status(request_id)
#             status = res.get("status")

#             if status == "completed":
#                 return res, None

#             if status == "failed":
#                 return res, "Verification failed at source"

#             if status == "error":
#                 return None, res.get("error")

#             time.sleep(delay)

#         return None, "Verification timed out"

#     # --------------------------------------------------
#     # PAN OCR
#     # --------------------------------------------------

#     @staticmethod
#     def start_pan_ocr(pan_file_path):
#         url = f"{VerificationService.BASE_URL}/tasks/async/extract/ind_pan"

#         try:
#             b64_doc = VerificationService.file_to_base64(pan_file_path)
#             if not b64_doc:
#                 raise Exception("File not found (Check S3/Local config)")
#         except Exception as e:
#             raise Exception(f"Could not read PAN file: {str(e)}")

#         payload = {
#             "task_id": f"task-{uuid.uuid4()}",
#             "group_id": f"group-{uuid.uuid4()}",
#             "data": {
#                 "document1": b64_doc
#             },
#         }

#         response = requests.post(
#             url,
#             headers=VerificationService.get_headers(),
#             json=payload,
#             timeout=10,
#         )
#         response.raise_for_status()
#         return response.json().get("request_id")

#     # --------------------------------------------------
#     # MAIN VERIFICATION LOGIC
#     # --------------------------------------------------

#     @staticmethod
#     def verify_vendor_data(data):
#         print("\n================ Incoming Payload ================")
#         print(data)
#         print("=================================================\n")

#         pan = normalize_pan(data.get("pan_number"))
#         pan_file = data.get("pan_file_path")
#         aadhaar = data.get("aadhaar_number")
#         gstin = data.get("gst_number")
#         udyam = data.get("msme_number")
#         bank_acc = data.get("bank_account_no")
#         ifsc = data.get("ifsc_code")

#         tasks = {}
#         poll_data = {}

#         summary = {
#             "valid": True,
#             "details": {
#                 "pan": {},
#                 "gst": {},
#                 "msme": {},
#                 "bank": {},
#             },
#         }

#         # 1. PAN
#         if pan:
#             if not pan_file:
#                  summary["details"]["pan"] = {"error": "Please select a PAN file to verify."}
#             else:
#                 try:
#                     ocr_id = VerificationService.start_pan_ocr(pan_file)
#                     ocr_res, err = VerificationService.poll_result_blocking(ocr_id)
                    
#                     if err: raise Exception(f"OCR Failed: {err}")
                    
#                     ocr_output = ocr_res.get("result", {}).get("extraction_output", {})
#                     ocr_name = ocr_output.get("name_on_card")
#                     ocr_dob = ocr_output.get("date_of_birth")
                    
#                     if not ocr_name: raise Exception("Could not read Name from PAN Card")

#                     tasks["pan"] = VerificationService.start_task(
#                         "ind_pan",
#                         { "id_number": pan, "full_name": ocr_name, "dob": ocr_dob, "get_contact_details": False }
#                     )[0]

#                     if aadhaar:
#                         tasks["pan_link"] = VerificationService.start_task(
#                             "pan_aadhaar_link",
#                             {"pan_number": pan, "aadhaar_number": aadhaar}
#                         )[0]
#                 except Exception as e:
#                     logger.error(f"PAN Verification Error: {e}")
#                     summary["details"]["pan"] = {"error": str(e)}

#         # 2. GST
#         if gstin:
#             tasks["gst"] = VerificationService.start_task(
#                 "ind_gst_certificate",
#                 { "gstin": gstin, "filing_details": True, "e_invoice_details": True }
#             )[0]

#         # 3. MSME
#         if udyam:
#             tasks["msme"] = VerificationService.start_task(
#                 "udyam_aadhaar", {"uam_number": udyam}
#             )[0]

#         # 4. BANK
#         if bank_acc and ifsc:
#             tasks["bank"] = VerificationService.start_task(
#                 "validate_bank_account",
#                 { "bank_account_no": bank_acc, "bank_ifsc_code": ifsc, "nf_verification": False }
#             )[0]

#         # 5. POLL
#         for key, req_id in tasks.items():
#             if not req_id: continue
#             res, err = VerificationService.poll_result_blocking(req_id)
#             if res: poll_data[key] = res
#             if err: print(f"DEBUG [{key}] FAILED:", err)

#         # --- PROCESS PAN ---
#         if "pan" in poll_data:
#             pan_src = poll_data["pan"].get("result", {}).get("source_output", {})
#             pan_status_text = pan_src.get("pan_status", "")
#             pan_id_found = pan_src.get("status") == "id_found"
            
#             pan_is_valid = (pan_id_found and "existing and valid" in str(pan_status_text).lower())

#             aadhaar_linked = None
#             if "pan_link" in poll_data:
#                 aadhaar_linked = poll_data["pan_link"].get("result", {}).get("source_output", {}).get("is_linked")

#             summary["details"]["pan"] = {
#                 "is_valid": pan_is_valid,
#                 "status_text": pan_status_text,
#                 "name_match": pan_src.get("name_match"),
#                 "aadhaar_linked": aadhaar_linked,
#             }

#         # --- PROCESS GST ---
#         if "gst" in poll_data:
#             gst_src = poll_data["gst"].get("result", {}).get("source_output", {})
#             summary["details"]["gst"] = {
#                 "status": gst_src.get("status"),
#                 "gstin_status": gst_src.get("gstin_status"),
#                 "trade_name": gst_src.get("trade_name"),
#                 "legal_name": gst_src.get("legal_name"),
#                 "taxpayer_type": gst_src.get("taxpayer_type"),
#                 "e_invoice_status": gst_src.get("e_invoice_status"),
#                 "last_6_gstr3b": VerificationService._analyze_gst_filings(gst_src.get("filing_details", {})),
#             }

#         # --- PROCESS MSME ---
#         if "msme" in poll_data:
#             msme_src = poll_data["msme"].get("result", {}).get("source_output", {})
#             general_details = msme_src.get("general_details", {})

#             # Name Fallback
#             ent_name = (
#                 general_details.get("enterprise_name") or 
#                 msme_src.get("enterprise_name") or 
#                 msme_src.get("name") or 
#                 "N/A"
#             )

#             # Type Parsing
#             ent_type_raw = general_details.get("enterprise_type") or msme_src.get("enterprise_type")
#             ent_type = "N/A"
#             if isinstance(ent_type_raw, str):
#                 ent_type = ent_type_raw
#             elif isinstance(ent_type_raw, dict):
#                 ent_type = ent_type_raw.get("label") or ent_type_raw.get("code") or "N/A"

#             summary["details"]["msme"] = {
#                 "status": msme_src.get("status"),
#                 "name": ent_name,
#                 "type": ent_type,
#             }

#         # --- PROCESS BANK ---
#         if "bank" in poll_data:
#             bank_res = poll_data["bank"].get("result", {})
#             # Check for source_output first (just in case), otherwise use direct result
#             bank_src = bank_res.get("source_output") or bank_res

#             summary["details"]["bank"] = {
#                 "status": bank_src.get("status"),
#                 "account_exists": bank_src.get("account_exists"),
#                 "name_at_bank": bank_src.get("name_at_bank"),
#             }

#         return summary

#     @staticmethod
#     def _analyze_gst_filings(filing_details):
#         if not filing_details: return "N/A"
#         gstr3b = filing_details.get("gstr3b", [])
#         if not gstr3b: return "0/6"
#         recent = gstr3b[:6]
#         filed = sum(1 for f in recent if f.get("status") == "Filed")
#         return f"{filed}/6 Filed"

# ----------------------------------- @------------------------------2--------------

# import uuid
# import time
# import requests
# import logging
# import base64
# import boto3
# from flask import current_app
# from urllib.parse import urlparse

# from app.tasks import log_audit_entry

# logger = logging.getLogger(__name__)

# # ==================================================
# # HELPERS
# # ==================================================

# def normalize_pan(pan):
#     if not pan:
#         return None
#     return pan.upper().replace(" ", "").replace("\n", "").strip()

# def normalize_s3_key(path):
#     if not path:
#         return None
#     if path.startswith("http"):
#         return urlparse(path).path.lstrip("/")
#     if path.startswith("s3://"):
#         return path.split("/", 3)[-1]
#     return path

# # ==================================================
# # SERVICE
# # ==================================================

# class VerificationService:
#     BASE_URL = "https://eve.idfy.com/v3"

#     # --------------------------------------------------
#     # FILE READ (S3)
#     # --------------------------------------------------

#     @staticmethod
#     def file_to_base64(file_path):
#         print("\n========== FILE READ ==========")
#         print("RAW PATH :", file_path)

#         try:
#             key = normalize_s3_key(file_path)
#             print("S3 KEY   :", key)

#             s3 = boto3.client(
#                 "s3",
#                 aws_access_key_id=current_app.config["AWS_ACCESS_KEY_ID"],
#                 aws_secret_access_key=current_app.config["AWS_SECRET_ACCESS_KEY"],
#                 region_name=current_app.config["AWS_REGION"],
#             )

#             obj = s3.get_object(
#                 Bucket=current_app.config["S3_BUCKET_NAME"],
#                 Key=key,
#             )

#             print("✅ FILE READ SUCCESS")
#             return base64.b64encode(obj["Body"].read()).decode("utf-8")

#         except Exception as e:
#             print("❌ FILE READ FAILED:", e)
#             return None

#     # --------------------------------------------------
#     # HEADERS
#     # --------------------------------------------------

#     @staticmethod
#     def get_headers():
#         return {
#             "Content-Type": "application/json",
#             "api-key": current_app.config["IDFY_API_KEY"],
#             "account-id": current_app.config["IDFY_ACCOUNT_ID"],
#         }

#     # --------------------------------------------------
#     # START TASK
#     # --------------------------------------------------

#     @staticmethod
#     def start_task(task_type, payload):
#         print(f"\n========== START TASK [{task_type}] ==========")
#         print("PAYLOAD:", payload)

#         try:
#             res = requests.post(
#                 f"{VerificationService.BASE_URL}/tasks/async/verify_with_source/{task_type}",
#                 headers=VerificationService.get_headers(),
#                 json={
#                     "task_id": f"task-{uuid.uuid4()}",
#                     "group_id": f"group-{uuid.uuid4()}",
#                     "data": payload,
#                 },
#                 timeout=15,
#             )
#             res.raise_for_status()
#             req_id = res.json().get("request_id")
#             print("REQUEST ID:", req_id)
#             return req_id
#         except Exception as e:
#             print("❌ TASK START FAILED:", e)
#             return None

#     # --------------------------------------------------
#     # POLLING
#     # --------------------------------------------------

#     @staticmethod
#     def poll(request_id):
#         print("\n🔁 POLLING:", request_id)
#         for _ in range(12):
#             try:
#                 r = requests.get(
#                     f"{VerificationService.BASE_URL}/tasks",
#                     headers=VerificationService.get_headers(),
#                     params={"request_id": request_id},
#                     timeout=5,
#                 )
#                 r.raise_for_status()
#                 task = r.json()[0]
#                 print("STATUS:", task.get("status"))
#                 if task.get("status") in ["completed", "failed"]:
#                     return task
#                 time.sleep(2)
#             except Exception as e:
#                 print("❌ POLLING ERROR:", e)
#                 return None
#         return None

#     # --------------------------------------------------
#     # PAN OCR
#     # --------------------------------------------------

#     @staticmethod
#     def pan_ocr(file_path):
#         print("\n========== PAN OCR ==========")
#         b64 = VerificationService.file_to_base64(file_path)
#         if not b64:
#             return None

#         res = requests.post(
#             f"{VerificationService.BASE_URL}/tasks/async/extract/ind_pan",
#             headers=VerificationService.get_headers(),
#             json={
#                 "task_id": f"task-{uuid.uuid4()}",
#                 "group_id": f"group-{uuid.uuid4()}",
#                 "data": {"document1": b64},
#             },
#             timeout=20,
#         )
#         res.raise_for_status()
#         return res.json().get("request_id")

#     # --------------------------------------------------
#     # AUDIT LOG
#     # --------------------------------------------------

#     @staticmethod
#     def audit(vendor_id, v_type, ext_id, status, input_data, response):
#         print(f"\n📜 AUDIT LOG [{v_type}] -> {status}")
#         try:
#             log_audit_entry.delay(
#                 vendor_id=vendor_id,
#                 v_type=v_type,
#                 ext_id=ext_id,
#                 status=status,
#                 input_data=input_data,
#                 response_data=response,
#             )
#             print("✅ AUDIT QUEUED")
#         except Exception as e:
#             print("❌ AUDIT FAILED:", e)

#     # --------------------------------------------------
#     # MAIN (LEGACY SAFE)
#     # --------------------------------------------------

#     @staticmethod
#     def verify_vendor_data(data):
#         print("\n================ VERIFICATION START ================")
#         print(data)
#         print("====================================================")

#         vendor_id = data.get("vendor_request_id")
#         raw = {}

#         # ================= PAN =================
#         if data.get("pan_number"):
#             ocr_id = VerificationService.pan_ocr(data["pan_file_path"])
#             ocr_res = VerificationService.poll(ocr_id)
#             ocr_out = ocr_res["result"]["extraction_output"]

#             pan_payload = {
#                 "id_number": normalize_pan(data["pan_number"]),
#                 "full_name": ocr_out.get("name_on_card"),
#                 "dob": ocr_out.get("date_of_birth"),
#                 "get_contact_details": False,
#             }

#             pan_id = VerificationService.start_task("ind_pan", pan_payload)
#             pan_res = VerificationService.poll(pan_id)

#             VerificationService.audit(
#                 vendor_id, "PAN", pan_id, pan_res["status"],
#                 {"pan": data["pan_number"]}, pan_res
#             )

#             raw["pan"] = pan_res

#             # Aadhaar link
#             if data.get("aadhaar_number"):
#                 link_id = VerificationService.start_task(
#                     "pan_aadhaar_link",
#                     {
#                         "pan_number": data["pan_number"],
#                         "aadhaar_number": data["aadhaar_number"],
#                     },
#                 )
#                 link_res = VerificationService.poll(link_id)

#                 VerificationService.audit(
#                     vendor_id, "PAN_AADHAAR", link_id, link_res["status"],
#                     {"pan": data["pan_number"]}, link_res
#                 )

#                 raw["pan_link"] = link_res

#         # ================= BANK =================
#         if data.get("bank_account_no") and data.get("ifsc_code"):
#             bank_id = VerificationService.start_task(
#                 "validate_bank_account",
#                 {
#                     "bank_account_no": data["bank_account_no"],
#                     "bank_ifsc_code": data["ifsc_code"],
#                     "nf_verification": False,
#                 },
#             )
#             bank_res = VerificationService.poll(bank_id)

#             VerificationService.audit(
#                 vendor_id, "BANK", bank_id, bank_res["status"],
#                 {"ifsc": data["ifsc_code"]}, bank_res
#             )

#             raw["bank"] = bank_res

#         # ==================================================
#         # 🔒 LEGACY RESPONSE (UNCHANGED CONTRACT)
#         # ==================================================

#         summary = {
#             "valid": True,
#             "details": {}
#         }

#         # PAN
#         if "pan" in raw:
#             src = (raw["pan"].get("result") or {}).get("source_output") or {}
#             summary["details"]["pan"] = {
#                 "is_valid": src.get("status") == "id_found",
#                 "status_text": src.get("pan_status"),
#                 "name_match": src.get("name_match"),
#                 "dob_match": src.get("dob_match"),
#                 "aadhaar_seeded": src.get("aadhaar_seeding_status"),
#             }
#             # 🔁 Mirror PAN–Aadhaar link for frontend compatibility
#             if "pan_link" in raw:
#                 link_src = (raw["pan_link"].get("result") or {}).get("source_output") or {}
#                 summary["details"]["pan"]["aadhaar_linked"] = link_src.get("is_linked")
#             else:
#                 summary["details"]["pan"]["aadhaar_linked"] = None
#         else:
#             summary["valid"] = False
#             summary["details"]["pan"] = {"error": "PAN verification failed"}

#         # PAN–AADHAAR LINK
#         if "pan_link" in raw:
#             link_src = (raw["pan_link"].get("result") or {}).get("source_output") or {}
#             summary["details"]["pan_link"] = {
#                 "is_linked": link_src.get("is_linked"),
#                 "message": link_src.get("message"),
#                 "status": link_src.get("status"),
#             }

#         # BANK
#         if "bank" in raw:
#             bank_src = (raw["bank"].get("result") or {}).get("source_output") or raw["bank"].get("result") or {}
#             summary["details"]["bank"] = {
#                 "account_exists": bank_src.get("account_exists"),
#                 "name_at_bank": bank_src.get("name_at_bank"),
#                 "status": bank_src.get("status"),
#             }

#         print("\n================ FINAL SUMMARY (LEGACY) ================")
#         print(summary)
#         print("=======================================================")

#         return summary

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

# ---------------------------------------------------------
# IMPORT IDFY FUNCTIONS
# ---------------------------------------------------------
from app.external.idfy import run_task, poll_task

class VerificationService:
    """
    SINGLE SOURCE OF TRUTH FOR VERIFICATION
    Integrates with IDfy Async API v3
    """

    # =====================================================
    # HELPER: FILE TO BASE64 (For OCR)
    # =====================================================
    @staticmethod
    def file_to_base64(file_path):
        """
        Reads a file from S3 (if enabled) or Local Disk and returns Base64 string.
        """
        if not file_path:
            return None
        
        print(f"--> Reading File: {file_path}")

        # --- 1. Try S3 Fetch if configured ---
        if current_app.config.get('USE_S3'):
            try:
                # Normalize Key (remove s3:// or http prefixes)
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
                
                print(f"    S3 Fetch: Bucket={bucket_name}, Key={key}")
                response = s3.get_object(Bucket=bucket_name, Key=key)
                file_content = response['Body'].read()
                return base64.b64encode(file_content).decode("utf-8")
            
            except Exception as e:
                print(f"❌ S3 Read Error: {e}")
                # Fallback to local if S3 fails is usually not recommended if path is S3 key, 
                # but we proceed just in case.

        # --- 2. Local Disk Fallback ---
        # Assuming file_path is relative to static/uploads if not absolute
        full_path = os.path.join(current_app.root_path, "static", "uploads", file_path)
        
        if not os.path.exists(full_path):
            # Try absolute path
            if os.path.exists(file_path):
                full_path = file_path
            else:
                print(f"❌ File not found: {full_path}")
                return None
            
        try:
            with open(full_path, "rb") as f:
                return base64.b64encode(f.read()).decode("utf-8")
        except Exception as e:
            print(f"❌ Local Read Error: {e}")
            return None

    # =====================================================
    # ENTRY POINT (USED BY FRONTEND)
    # =====================================================
    @staticmethod
    def verify_vendor_data(data: dict) -> dict:
        print("\n================ VERIFICATION START ================")
        print(f"Incoming Data: {json.dumps(data, indent=2)}")

        vendor_request_id = data.get("vendor_request_id")
        if not vendor_request_id:
            return {"error": "vendor_request_id missing", "details": None}

        req = VendorRequest.query.filter_by(request_id=vendor_request_id).first()
        if not req:
            return {"error": "Invalid vendor request", "details": None}

        details = {}

        try:
            # ---------------- PAN (OCR + VERIFY) ----------------
            if "pan_number" in data:
                print(f"--> Starting PAN Verification for {data['pan_number']}")
                details["pan"] = VerificationService._verify_pan(req, data)

            # ---------------- GST ----------------
            if "gst_number" in data:
                print(f"--> Starting GST Verification for {data['gst_number']}")
                details["gst"] = VerificationService._verify_gst(req, data)

            # ---------------- MSME ----------------
            if "msme_number" in data:
                print(f"--> Starting MSME Verification for {data['msme_number']}")
                details["msme"] = VerificationService._verify_msme(req, data)

            # ---------------- BANK ----------------
            if "bank_account_no" in data:
                print(f"--> Starting Bank Verification for {data['bank_account_no']}")
                details["bank"] = VerificationService._verify_bank(req, data)
                

            # Final Commit to save all updates (including is_verified flags AND values)
            db.session.commit()
            
            print("================ VERIFICATION COMPLETE ================\n")
            return {
                "valid": True,
                "details": details
            }

        except Exception as e:
            db.session.rollback()
            current_app.logger.exception("Verification process failed")
            print(f"!!! CRITICAL FAILURE: {str(e)}")
            return {"error": str(e), "details": None}

    # =====================================================
    # PAN VERIFICATION (OCR -> VERIFY)
    # =====================================================
    @staticmethod
    def _verify_pan(req: VendorRequest, data: dict) -> dict:
        pan = data.get("pan_number", "").strip().upper()
        pan_file_path = data.get("pan_file_path")
        
        try:
            # --- STEP 1: OCR ---
            if not pan_file_path:
                raise ValueError("PAN File Path missing. Cannot perform OCR.")

            b64_doc = VerificationService.file_to_base64(pan_file_path)
            if not b64_doc:
                raise ValueError("Could not read PAN file content.")

            # We use direct requests for OCR because run_task is configured for verify_with_source
            ocr_url = "https://eve.idfy.com/v3/tasks/async/extract/ind_pan"
            headers = {
                "Content-Type": "application/json",
                "api-key": current_app.config["IDFY_API_KEY"],
                "account-id": current_app.config["IDFY_ACCOUNT_ID"],
            }
            ocr_payload = {
                "task_id": str(uuid.uuid4()),
                "group_id": f"VENDOR_{req.id}_OCR",
                "data": {"document1": b64_doc}
            }

            print("[PAN OCR] Starting Extraction...")
            ocr_res = requests.post(ocr_url, headers=headers, json=ocr_payload, timeout=30)
            ocr_res.raise_for_status()
            ocr_req_id = ocr_res.json().get("request_id")
            
            print(f"[PAN OCR] Request ID: {ocr_req_id}")
            ocr_result = poll_task(ocr_req_id) # Reuse poll_task logic
            
            ocr_output = ocr_result.get("result", {}).get("extraction_output", {})
            name_on_card = ocr_output.get("name_on_card")
            dob_on_card = ocr_output.get("date_of_birth")

            if not name_on_card:
                raise ValueError("OCR completed but could not read Name from PAN card.")

            print(f"[PAN OCR] Extracted Name: {name_on_card}, DOB: {dob_on_card}")

            # --- STEP 2: VERIFY ---
            verify_payload = {
                "task_id": str(uuid.uuid4()),
                "group_id": f"VENDOR_{req.id}",
                "data": {
                    "id_number": pan, 
                    "full_name": name_on_card,
                    "dob": dob_on_card,
                    "get_contact_details": False
                }
            }

            print(f"[PAN VERIFY] Sending Payload: {verify_payload}")
            
            # Task Type: 'ind_pan'
            verify_req_id = run_task("ind_pan", verify_payload)
            print(f"[PAN VERIFY] Request ID: {verify_req_id}")

            api_resp = poll_task(verify_req_id)
            
            # Extract Data
            result_block = api_resp.get("result", {}).get("source_output", {})
            status_text = result_block.get("pan_status", "INVALID")
            id_found = result_block.get("status") == "id_found"
            
            is_valid = (api_resp.get("status") == "completed") and id_found

            # Safety check: if 'fake' or 'deleted' appears in status
            if is_valid and "valid" not in str(status_text).lower():
                 is_valid = False

            output = {
                "is_valid": is_valid,
                "status_text": status_text,
                "name_match": result_block.get("name_match"),
                "dob_match": result_block.get("dob_match"),
                "aadhaar_linked": result_block.get("aadhaar_seeding_status"),
                "ocr_name": name_on_card
            }

            VerificationService._log(req, "PAN", "SUCCESS" if is_valid else "FAILED", data, api_resp)

            if is_valid:
                # 🔥 FIX FOR REFRESH BUG: Save data immediately
                req.is_pan_verified = True
                req.pan_number = pan 
            
            return output

        except Exception as e:
            print(f"[PAN] EXCEPTION: {e}")
            current_app.logger.error(f"PAN Verification Error: {e}")
            VerificationService._log(req, "PAN", "ERROR", data, {"error": str(e)})
            return {"is_valid": False, "status_text": "ERROR", "error": str(e)}

    # =====================================================
    # GST VERIFICATION
    # =====================================================
    @staticmethod
    def _verify_gst(req: VendorRequest, data: dict) -> dict:
        gst = data.get("gst_number", "").strip().upper()

        try:
            payload = {
                "task_id": str(uuid.uuid4()),
                "group_id": f"VENDOR_{req.id}",
                "data": {
                    "gstin": gst,
                    "filing_details": True,
                    "e_invoice_details": True
                }
            }

            print(f"[GST] Sending Payload: {payload}")
            request_id = run_task("ind_gst_certificate", payload)
            
            api_resp = poll_task(request_id)
            
            result_block = api_resp.get("result", {}).get("source_output", {})
            gst_status = result_block.get("gstin_status", "Inactive")
            
            is_active = (api_resp.get("status") == "completed") and (gst_status == "Active")

            output = {
                "status": result_block.get("status"),
                "gstin_status": gst_status,
                "legal_name": result_block.get("legal_name"),
                "trade_name": result_block.get("trade_name"),
                "taxpayer_type": result_block.get("taxpayer_type"),
                "e_invoice_status": result_block.get("e_invoice_status"),
                "last_6_gstr3b": VerificationService._analyze_gst_filings(result_block.get("filing_details", {})),
                "address": result_block.get("principal_place_of_business_address")
            }

            VerificationService._log(req, "GST", "SUCCESS" if is_active else "FAILED", data, api_resp)

            if is_active:
                # 🔥 FIX FOR REFRESH BUG: Save data immediately
                req.is_gst_verified = True
                req.gst_number = gst
                # Optional: Autofill names
                # if result_block.get("legal_name"): req.vendor_name_basic = result_block.get("legal_name")

            return output

        except Exception as e:
            print(f"[GST] EXCEPTION: {e}")
            current_app.logger.error(f"GST Verification Error: {e}")
            VerificationService._log(req, "GST", "ERROR", data, {"error": str(e)})
            return {"gstin_status": "ERROR", "error": str(e)}

    # =====================================================
    # MSME / UDYAM VERIFICATION
    # =====================================================
    @staticmethod
    def _verify_msme(req: VendorRequest, data: dict) -> dict:
        raw_msme = data.get("msme_number", "").strip().upper()

        try:
            payload = {
                "task_id": str(uuid.uuid4()),
                "group_id": f"VENDOR_{req.id}",
                "data": {"uam_number": raw_msme}
            }

            print(f"[MSME] Sending Payload: {payload}")
            request_id = run_task("udyam_aadhaar", payload)
            
            api_resp = poll_task(request_id)
            
            result_block = api_resp.get("result", {}).get("source_output", {})
            general_details = result_block.get("general_details", {})

            ent_name = (
                general_details.get("enterprise_name") or 
                result_block.get("enterprise_name") or 
                result_block.get("name") or 
                "N/A"
            )

            ent_type_raw = general_details.get("enterprise_type") or result_block.get("enterprise_type")
            ent_type = "N/A"
            if isinstance(ent_type_raw, str):
                ent_type = ent_type_raw
            elif isinstance(ent_type_raw, dict):
                ent_type = ent_type_raw.get("label") or ent_type_raw.get("code") or "N/A"

            found = (api_resp.get("status") == "completed") and (result_block.get("status") == "id_found")

            output = {
                "status": result_block.get("status"),
                "name": ent_name,
                "type": ent_type,
                "major_activity": result_block.get("major_activity")
            }

            VerificationService._log(req, "MSME", "SUCCESS" if found else "FAILED", data, api_resp)

            if found:
                # 🔥 FIX FOR REFRESH BUG: Save data immediately
                req.is_msme_verified = True
                req.msme_number = raw_msme
                req.msme_registered = "YES"

            return output

        except Exception as e:
            print(f"[MSME] EXCEPTION: {e}")
            current_app.logger.error(f"MSME Verification Error: {e}")
            VerificationService._log(req, "MSME", "ERROR", data, {"error": str(e)})
            return {"status": "ERROR", "error": str(e)}

    # =====================================================
    # BANK ACCOUNT VERIFICATION
    # =====================================================
    @staticmethod
    def _verify_bank(req: VendorRequest, data: dict) -> dict:
        acc = data.get("bank_account_no", "")
        ifsc = data.get("ifsc_code", "")

        try:
            payload = {
                "task_id": str(uuid.uuid4()),
                "group_id": f"VENDOR_{req.id}",
                "data": {
                    "bank_account_no": acc,
                    "bank_ifsc_code": ifsc,
                    "nf_verification": False
                }
            }

            print(f"[BANK] Sending Payload: {payload}")
            request_id = run_task("validate_bank_account", payload)
            
            api_resp = poll_task(request_id)

            result_block = api_resp.get("result", {})
            source_block = result_block.get("source_output") or result_block
            
            # Check penny drop status
            is_valid = (api_resp.get("status") == "completed") and (source_block.get("account_exists") == True)

            output = {
                "status": source_block.get("status"),
                "account_exists": source_block.get("account_exists"),
                "name_at_bank": source_block.get("name_at_bank"),
                "utr": source_block.get("utr")
            }

            VerificationService._log(req, "BANK", "SUCCESS" if is_valid else "FAILED", data, api_resp)

            if is_valid:
                # 🔥 FIX FOR REFRESH BUG: Save data immediately
                req.is_bank_verified = True
                req.bank_account_no = acc
                req.bank_ifsc = ifsc
                req.bank_account_holder_name = source_block.get("name_at_bank")

            return output

        except Exception as e:
            print(f"[BANK] EXCEPTION: {e}")
            current_app.logger.error(f"Bank Verification Error: {e}")
            VerificationService._log(req, "BANK", "ERROR", data, {"error": str(e)})
            return {"status": "ERROR", "error": str(e)}

    # =====================================================
    # HELPER: GST FILINGS
    # =====================================================
    @staticmethod
    def _analyze_gst_filings(filing_details):
        if not filing_details: return "N/A"
        gstr3b = filing_details.get("gstr3b", [])
        if not gstr3b: return "0/6"
        recent = gstr3b[:6]
        filed = sum(1 for f in recent if f.get("status") == "Filed")
        return f"{filed}/6 Filed"

    # =====================================================
    # UNVERIFY & LOGS
    # =====================================================
    @staticmethod
    def mark_unverified(req: VendorRequest, section: str):
        if section == "pan":
            req.is_pan_verified = False
        elif section == "gst":
            req.is_gst_verified = False
        elif section == "msme":
            req.is_msme_verified = False
        elif section == "bank":
            req.is_bank_verified = False
        else:
            raise ValueError(f"Invalid section: {section}")
        db.session.add(req)
        db.session.commit()

    @staticmethod
    def _log(req, vtype, status, payload, response):
        try:
            db.session.add(
                VerificationLog(
                    vendor_request_id=req.id,
                    verification_type=vtype,
                    status=status,
                    input_payload=payload,
                    api_response=response
                )
            )
            # Flush to generate ID, do not commit
            db.session.flush() 
        except Exception as e:
            print(f"!!! LOG FAILURE: {e}")