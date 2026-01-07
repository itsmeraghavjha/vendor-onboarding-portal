import uuid
import time
import requests
import logging
from flask import current_app

logger = logging.getLogger(__name__)

class VerificationService:
    BASE_URL = "https://eve.idfy.com/v3"
    
    @staticmethod
    def get_headers():
        return {
            'Content-Type': 'application/json',
            'api-key': current_app.config.get('IDFY_API_KEY'),
            'account-id': current_app.config.get('IDFY_ACCOUNT_ID'),
        }

    @staticmethod
    def start_task(task_type, data_payload):
        url = f"{VerificationService.BASE_URL}/tasks/async/verify_with_source/{task_type}"
        payload = {
            "task_id": f"task-{uuid.uuid4()}",
            "group_id": f"group-{uuid.uuid4()}",
            "data": data_payload
        }
        try:
            response = requests.post(
                url, headers=VerificationService.get_headers(), json=payload, timeout=10
            )
            response.raise_for_status()
            return response.json().get('request_id'), None
        except Exception as e:
            print(f"!!! CRITICAL ERROR STARTING {task_type}: {e}")
            if hasattr(e, 'response') and e.response: print(e.response.text)
            return None, str(e)

    # --- WRAPPERS ---
    @staticmethod
    def verify_pan(pan_number):
        req_id, err = VerificationService.start_task("ind_pan", {"id_number": pan_number, "get_contact_details": False})
        if err: raise Exception(err)
        return req_id

    @staticmethod
    def verify_gst(gstin):
        req_id, err = VerificationService.start_task("ind_gst_certificate", {"gstin": gstin, "filing_details": True, "e_invoice_details": True})
        if err: raise Exception(err)
        return req_id

    @staticmethod
    def verify_bank(account, ifsc):
        req_id, err = VerificationService.start_task("validate_bank_account", {"bank_account_no": account, "bank_ifsc_code": ifsc, "nf_verification": False})
        if err: raise Exception(err)
        return req_id

    # --- POLLING ---
    @staticmethod
    def check_status(request_id):
        url = f"{VerificationService.BASE_URL}/tasks"
        params = {'request_id': request_id}
        try:
            response = requests.get(url, headers=VerificationService.get_headers(), params=params, timeout=5)
            response.raise_for_status()
            data = response.json()
            
            if data and isinstance(data, list) and len(data) > 0:
                task = data[0]
                return {'status': task.get('status'), 'result': task.get('result')}
            return {'status': 'pending'}
        except Exception as e:
            return {'status': 'error', 'error': str(e)}

    @staticmethod
    def poll_result_blocking(request_id, max_retries=10, delay=2):
        print(f"DEBUG: Polling ID: {request_id}")
        for _ in range(max_retries):
            res = VerificationService.check_status(request_id)
            status = res.get('status')
            
            if status == 'completed':
                return res, None
            if status == 'failed':
                print(f"DEBUG: Task {request_id} FAILED at source.")
                return res, "Verification failed at source."
            if status == 'error':
                return None, res.get('error')
            
            time.sleep(delay)
        return None, "Verification timed out."

    # --- MAIN LOGIC ---
    @staticmethod
    def verify_vendor_data(data):
        print(f"\n{'='*40}\nIncoming Payload: {data}\n{'='*40}")

        pan = data.get('pan_number', '').strip().upper()
        gstin = data.get('gst_number', '').strip().upper()
        udyam = data.get('msme_number', '').strip().upper()
        bank_acc = data.get('bank_account_no', '').strip()
        ifsc = data.get('ifsc_code', '').strip().upper()
        name_on_pan = data.get('vendor_name', '').strip()
        
        tasks = {}
        poll_data = {}
        errors = {}
        
        summary = { 
            'valid': True, 
            'remarks': [], 
            'details': { 'pan': None, 'gst': None, 'bank': None, 'msme': None } 
        }

        # 1. Start Tasks
        if pan:
            tasks['pan'], errors['pan'] = VerificationService.start_task("ind_pan", {
                "id_number": pan, "full_name": name_on_pan, "get_contact_details": False
            })
        
        if gstin:
             tasks['gst'], errors['gst'] = VerificationService.start_task("ind_gst_certificate", {
                 "gstin": gstin, "filing_details": True, "e_invoice_details": True 
             })
        
        if udyam:
             tasks['msme'], errors['msme'] = VerificationService.start_task("udyam_aadhaar", {
                 "uam_number": udyam
             })

        if bank_acc and ifsc:
            tasks['bank'], errors['bank'] = VerificationService.start_task("validate_bank_account", {
                "bank_account_no": bank_acc, 
                "bank_ifsc_code": ifsc, 
                "nf_verification": False 
            })

        # 2. Poll Results
        for key, req_id in tasks.items():
            if req_id:
                res, err = VerificationService.poll_result_blocking(req_id)
                if res: 
                    poll_data[key] = res
                    print(f"DEBUG [{key}]: {res}")
                if err: 
                    errors[key] = err
                    print(f"DEBUG [{key}] FAILED: {err}")

        # 3. Process Results (DEFENSIVE CODING)

        # --- PAN ---
        if 'pan' in poll_data:
            res = poll_data['pan']
            task_result = res.get('result')
            
            # Check if result is None (Failed Task)
            if not task_result or res.get('status') == 'failed':
                summary['details']['pan'] = { 'status': 'FAILED', 'name_match': False, 'score': 0, 'aadhaar_linked': 'N/A' }
            else:
                src = task_result.get('source_output', {})
                raw_score = src.get('name_match_score')
                summary['details']['pan'] = {
                    'status': src.get('pan_status', 'UNKNOWN'),
                    'name_match': (raw_score is not None and raw_score > 0.8),
                    'score': raw_score,
                    'aadhaar_linked': src.get('aadhaar_seeding_status', 'N/A')
                }
        else:
            summary['details']['pan'] = {'status': 'Not Provided'}

        # --- GST ---
        if 'gst' in poll_data:
            res = poll_data['gst']
            task_result = res.get('result')

            if not task_result or res.get('status') == 'failed':
                summary['details']['gst'] = { 'status': 'FAILED', 'legal_name': 'Error' }
            else:
                src = task_result.get('source_output', {})
                status = src.get('gstin_status') or 'Active'
                
                if src.get('status') == 'id_not_found':
                    summary['details']['gst'] = { 'status': 'Invalid ID', 'legal_name': 'Not Found' }
                else:
                    einvoice = src.get('e_invoice_status', 'N/A')
                    summary['details']['gst'] = {
                        'status': status,
                        'legal_name': src.get('legal_name') or src.get('legal_name_of_business', 'N/A'),
                        'trade_name': src.get('trade_name', 'N/A'),
                        'type': src.get('taxpayer_type', 'N/A'),
                        'filing_status': VerificationService._analyze_gst_filings(src.get('filing_details', {})),
                        'einvoice': "Not Enabled" if einvoice == 'CNL' else einvoice
                    }
        else:
            summary['details']['gst'] = { 'status': 'Skipped' }

        # --- MSME ---
        if 'msme' in poll_data:
            res = poll_data['msme']
            task_result = res.get('result')
            
            if not task_result or res.get('status') == 'failed':
                 summary['details']['msme'] = { 'status': 'FAILED', 'name': 'Error' }
            else:
                src = task_result.get('source_output', {})
                general = src.get('general_details', {})
                summary['details']['msme'] = {
                    'status': src.get('status', 'Unknown'),
                    'enterprise_type': general.get('enterprise_type', 'N/A'),
                    'name': general.get('enterprise_name', 'N/A')
                }
        else:
             summary['details']['msme'] = { 'status': 'Skipped' }

        # --- BANK ---
        if 'bank' in poll_data:
            res = poll_data['bank']
            task_result = res.get('result')
            
            if not task_result or res.get('status') == 'failed':
                summary['details']['bank'] = { 'status': 'FAILED', 'name_at_bank': 'Error' }
            else:
                exists = task_result.get('account_exists') 
                bank_name = task_result.get('name_at_bank') 
                if not bank_name:
                    bank_name = task_result.get('source_output', {}).get('beneficiary_name', 'N/A')

                summary['details']['bank'] = {
                    'status': 'Verified' if exists == 'YES' else 'Failed',
                    'name_at_bank': bank_name
                }
        else:
            summary['details']['bank'] = { 'status': 'Skipped' }

        return summary

    @staticmethod
    def _analyze_gst_filings(filing_details):
        if not filing_details: return "No Data"
        gstr3b = filing_details.get('gstr3b', [])
        if not gstr3b: return "No GSTR-3B Data"
        recent_6 = gstr3b[:6]
        if not recent_6: return "No Data"
        filed_count = sum(1 for f in recent_6 if f.get('status') == 'Filed')
        return f"{filed_count}/6 Filed"