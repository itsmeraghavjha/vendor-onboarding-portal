import uuid
import time
import requests
import logging
import base64
import os
from flask import current_app

logger = logging.getLogger(__name__)


def normalize_pan(pan):
    if not pan:
        return None
    return pan.upper().replace(" ", "").replace("\n", "").strip()


class VerificationService:
    BASE_URL = "https://eve.idfy.com/v3"

    # --------------------------------------------------
    # HELPERS
    # --------------------------------------------------

    @staticmethod
    def file_to_base64(file_path):
        full_path = os.path.join(
            current_app.root_path, "static", "uploads", file_path
        )
        with open(full_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    @staticmethod
    def get_headers():
        return {
            "Content-Type": "application/json",
            "api-key": current_app.config.get("IDFY_API_KEY"),
            "account-id": current_app.config.get("IDFY_ACCOUNT_ID"),
        }

    # --------------------------------------------------
    # TASK STARTER
    # --------------------------------------------------

    @staticmethod
    def start_task(task_type, data_payload):
        url = f"{VerificationService.BASE_URL}/tasks/async/verify_with_source/{task_type}"

        payload = {
            "task_id": f"task-{uuid.uuid4()}",
            "group_id": f"group-{uuid.uuid4()}",
            "data": data_payload,
        }

        try:
            response = requests.post(
                url,
                headers=VerificationService.get_headers(),
                json=payload,
                timeout=10,
            )
            response.raise_for_status()
            return response.json().get("request_id"), None
        except Exception as e:
            logger.exception(f"Failed starting task {task_type}")
            return None, str(e)

    # --------------------------------------------------
    # POLLING
    # --------------------------------------------------

    @staticmethod
    def check_status(request_id):
        url = f"{VerificationService.BASE_URL}/tasks"
        params = {"request_id": request_id}

        try:
            response = requests.get(
                url,
                headers=VerificationService.get_headers(),
                params=params,
                timeout=5,
            )
            response.raise_for_status()
            data = response.json()

            if data and isinstance(data, list):
                task = data[0]
                return {"status": task.get("status"), "result": task.get("result")}

            return {"status": "pending"}

        except Exception as e:
            return {"status": "error", "error": str(e)}

    @staticmethod
    def poll_result_blocking(request_id, max_retries=12, delay=2):
        print(f"DEBUG: Polling ID: {request_id}")

        for _ in range(max_retries):
            res = VerificationService.check_status(request_id)
            status = res.get("status")

            if status == "completed":
                return res, None

            if status == "failed":
                return res, "Verification failed at source"

            if status == "error":
                return None, res.get("error")

            time.sleep(delay)

        return None, "Verification timed out"

    # --------------------------------------------------
    # PAN OCR
    # --------------------------------------------------

    @staticmethod
    def start_pan_ocr(pan_file_path):
        url = f"{VerificationService.BASE_URL}/tasks/async/extract/ind_pan"

        payload = {
            "task_id": f"task-{uuid.uuid4()}",
            "group_id": f"group-{uuid.uuid4()}",
            "data": {
                "document1": VerificationService.file_to_base64(pan_file_path)
            },
        }

        response = requests.post(
            url,
            headers=VerificationService.get_headers(),
            json=payload,
            timeout=10,
        )
        response.raise_for_status()
        return response.json().get("request_id")

    # --------------------------------------------------
    # MAIN VERIFICATION LOGIC
    # --------------------------------------------------

    @staticmethod
    def verify_vendor_data(data):
        print("\n================ Incoming Payload ================")
        print(data)
        print("=================================================\n")

        pan = normalize_pan(data.get("pan_number"))
        pan_file = data.get("pan_file_path")
        aadhaar = data.get("aadhaar_number")
        gstin = data.get("gst_number")
        udyam = data.get("msme_number")
        bank_acc = data.get("bank_account_no")
        ifsc = data.get("ifsc_code")

        if not pan or not pan_file:
            raise Exception("PAN number and PAN file are required")

        tasks = {}
        poll_data = {}

        summary = {
            "valid": True,
            "details": {
                "pan": {},
                "gst": {},
                "msme": {},
                "bank": {},
            },
        }

        # --------------------------------------------------
        # 1. PAN OCR
        # --------------------------------------------------
        ocr_id = VerificationService.start_pan_ocr(pan_file)
        ocr_res, err = VerificationService.poll_result_blocking(ocr_id)
        if err:
            raise Exception("PAN OCR failed")

        ocr_output = ocr_res["result"]["extraction_output"]
        ocr_name = ocr_output.get("name_on_card")
        ocr_dob = ocr_output.get("date_of_birth")

        print("OCR NAME:", ocr_name)
        print("OCR DOB:", ocr_dob)

        if not ocr_name:
            raise Exception("PAN OCR name missing")

        # --------------------------------------------------
        # 2. START TASKS
        # --------------------------------------------------
        tasks["pan"] = VerificationService.start_task(
            "ind_pan",
            {
                "id_number": pan,
                "full_name": ocr_name,
                "dob": ocr_dob,
                "get_contact_details": False,
            },
        )[0]

        if aadhaar:
            tasks["pan_link"] = VerificationService.start_task(
                "pan_aadhaar_link",
                {"pan_number": pan, "aadhaar_number": aadhaar},
            )[0]

        if gstin:
            tasks["gst"] = VerificationService.start_task(
                "ind_gst_certificate",
                {
                    "gstin": gstin,
                    "filing_details": True,
                    "e_invoice_details": True,
                },
            )[0]

        if udyam:
            tasks["msme"] = VerificationService.start_task(
                "udyam_aadhaar",
                {"uam_number": udyam},
            )[0]

        if bank_acc and ifsc:
            tasks["bank"] = VerificationService.start_task(
                "validate_bank_account",
                {
                    "bank_account_no": bank_acc,
                    "bank_ifsc_code": ifsc,
                    "nf_verification": False,
                },
            )[0]

        # --------------------------------------------------
        # 3. POLL ALL TASKS
        # --------------------------------------------------
        for key, req_id in tasks.items():
            if not req_id:
                continue

            res, err = VerificationService.poll_result_blocking(req_id)
            if res:
                poll_data[key] = res
                print(f"DEBUG [{key}]:", res)
            if err:
                print(f"DEBUG [{key}] FAILED:", err)


                # --------------------------------------------------
        # 4. PROCESS PAN (NORMALIZED – SINGLE SOURCE OF TRUTH)
        # --------------------------------------------------
        pan_src = poll_data.get("pan", {}).get("result", {}).get("source_output", {})

        pan_status_text = pan_src.get("pan_status", "")
        pan_id_found = pan_src.get("status") == "id_found"
        name_match = pan_src.get("name_match") is True

        # ✅ CANONICAL VALID FLAG (THIS FIXES RED ❌)
        pan_is_valid = (
            pan_id_found
            and isinstance(pan_status_text, str)
            and "existing and valid" in pan_status_text.lower()
        )

        aadhaar_linked = (
            poll_data.get("pan_link", {})
            .get("result", {})
            .get("source_output", {})
            .get("is_linked")
        )

        summary["details"]["pan"] = {
            "is_valid": pan_is_valid,          # ✅ frontend uses ONLY this
            "status_text": pan_status_text,    # display text
            "id_found": pan_id_found,
            "name_match": name_match,
            "aadhaar_linked": aadhaar_linked,
        }


        # --------------------------------------------------
        # 5. PROCESS GST
        # --------------------------------------------------
        gst_src = poll_data.get("gst", {}).get("result", {}).get("source_output", {})
        if gst_src:
            summary["details"]["gst"] = {
                "status": gst_src.get("status"),
                "gstin_status": gst_src.get("gstin_status"),
                "trade_name": gst_src.get("trade_name"),
                "legal_name": gst_src.get("legal_name"),
                "taxpayer_type": gst_src.get("taxpayer_type"),
                "e_invoice_status": gst_src.get("e_invoice_status"),
                "last_6_gstr3b": VerificationService._analyze_gst_filings(
                    gst_src.get("filing_details", {})
                ),
            }

        # --------------------------------------------------
        # 6. PROCESS MSME
        # --------------------------------------------------
        msme_src = poll_data.get("msme", {}).get("result", {}).get("source_output", {})
        if msme_src:
            summary["details"]["msme"] = {
                "status": msme_src.get("status"),
                "name": msme_src.get("enterprise_name"),
                "type": msme_src.get("enterprise_type"),
                "classification": msme_src.get("classification"),
                "date_of_registration": msme_src.get("date_of_registration"),
            }

        # --------------------------------------------------
        # 7. PROCESS BANK
        # --------------------------------------------------
        bank_src = poll_data.get("bank", {}).get("result", {}).get("source_output", {})
        if bank_src:
            summary["details"]["bank"] = {
                "status": bank_src.get("status"),
                "account_exists": bank_src.get("account_exists"),
                "name_at_bank": bank_src.get("name_at_bank"),
                "bank_name": bank_src.get("bank_name"),
                "ifsc": bank_src.get("ifsc"),
            }

        return summary

    # --------------------------------------------------
    # GST ANALYSIS
    # --------------------------------------------------

    @staticmethod
    def _analyze_gst_filings(filing_details):
        gstr3b = filing_details.get("gstr3b", [])
        recent = gstr3b[:6]
        filed = sum(1 for f in recent if f.get("status") == "Filed")
        return f"{filed}/6 Filed"
