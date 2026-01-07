import csv
import io
from collections import defaultdict
from sqlalchemy import func
from app.extensions import db
from app.models import User, Department, CategoryRouting, WorkflowStep, ITRouting, VendorRequest, MasterData

class AdminService:
    
    def format_sap_date(self, date_str):
        """Converts YYYY-MM-DD to DD.MM.YYYY for SAP."""
        if not date_str: return ""
        try:
            parts = date_str.split('-')
            if len(parts) == 3:
                return f"{parts[2]}.{parts[1]}.{parts[0]}"
            return date_str
        except:
            return date_str

    def get_detailed_breakdown(self):
        """Calculates detailed breakdown for specific dashboard cards."""
        wf_breakdown = defaultdict(lambda: defaultdict(int))
        
        # Map steps to readable labels
        step_map = {(s.department, s.step_order): s.role_label for s in WorkflowStep.query.all()}
        
        pending_items = VendorRequest.query.filter(VendorRequest.status == 'PENDING_APPROVAL').all()
        
        for req in pending_items:
            if req.current_dept_flow == 'DEPT':
                card = req.initiator_dept or "Dept"
                # Safe lookup for step label
                label = step_map.get((req.initiator_dept, req.current_step_number), f"Level {req.current_step_number}")
                wf_breakdown[card][label] += 1
                
            elif req.current_dept_flow == 'FINANCE':
                card = "Finance Provisioning"
                # Clean up stage names: 'BILL_PASSING' -> 'Bill Passing'
                label = (req.finance_stage or "General").replace('_', ' ').title()
                wf_breakdown[card][label] += 1
                
            elif req.current_dept_flow == 'IT':
                card = "IT Provisioning"
                label = f"{req.account_group or 'Standard'} Account"
                wf_breakdown[card][label] += 1
                
        return {k: dict(v) for k, v in wf_breakdown.items()}

    def get_dashboard_stats(self):
        """Calculates all statistics for the admin dashboard."""
        bottlenecks = [
            ('Department', VendorRequest.query.filter(VendorRequest.status=='PENDING_APPROVAL', VendorRequest.current_dept_flow.in_(['INITIATOR_REVIEW', 'DEPT'])).count()),
            ('Bill Passing', VendorRequest.query.filter_by(status='PENDING_APPROVAL', finance_stage='BILL_PASSING').count()),
            ('Treasury Team', VendorRequest.query.filter_by(status='PENDING_APPROVAL', finance_stage='TREASURY').count()),
            ('Tax Team', VendorRequest.query.filter_by(status='PENDING_APPROVAL', finance_stage='TAX').count()),
            ('IT Provisioning', VendorRequest.query.filter_by(status='PENDING_APPROVAL', current_dept_flow='IT').count())
        ]

        dept_stats = db.session.query(
            VendorRequest.initiator_dept, 
            func.count(VendorRequest.id)
        ).filter(
            VendorRequest.status == 'PENDING_APPROVAL',
            VendorRequest.current_dept_flow == 'DEPT'
        ).group_by(VendorRequest.initiator_dept).all()

        dept_pending = {row[0]: row[1] for row in dept_stats if row[0]}

        return {
            'bottlenecks': bottlenecks,
            'dept_pending': dept_pending,
            'total': VendorRequest.query.count(),
            'completed': VendorRequest.query.filter_by(status='COMPLETED').count(),
            'rejected': VendorRequest.query.filter_by(status='REJECTED').count(),
            'workflow_breakdown': self.get_detailed_breakdown()
        }

    def generate_sap_csv(self, request_ids):
        """Generates the SAP Upload CSV using the specific requested format."""
        output = io.StringIO()
        writer = csv.writer(output)

        # [cite_start]1. Header (Updated based on V1 Format) [cite: 1]
        headers = [
            "S.No", "VLMS Number", "Vendor Account Group", "Title", 
            "Name 1 (Legal Name)", "Name 2 (Legal Name)", "Name 3 (Trade Name)",
            "Street", "Street2", "Street3", "Street4", "City", "Postal Code", "Region",
            "Contact Person Name", "Mobile Number 1", "Mobile Number 2", "Landline No",
            "E-Mail Address", "GST Number", "PAN Number", "MSME Number", "MSME Type",
            "IFSC Code", "Bank Account No", "Account Holder Name", "GL Account", "House Bank",
            "Payment Terms", "Purch. Org", "Payment Terms", "Inco Terms", 
            "Withholding Tax Type -1", "Withholding Tax Code -1", "Subject to w/tax", 
            "Recipient Type", "Exemption Certificate No. -1", "Exemption Rate -1", 
            "Exemption Start Date -1", "Exemption End Date -1", "Exemption Reason -1", 
            "Section Code", "Exemption Certificate No. - 2", "Exemption Rate -2", 
            "Exemption Start Date -2", "Exemption End Date -2", "Exemption Reason -2", 
            "Withholding Tax Code -2", "Withholding Tax Type -2", "Exemption thr amm", "Currency"
        ]
        writer.writerow(headers)

        requests = VendorRequest.query.filter(VendorRequest.id.in_(request_ids)).all()

        for idx, req in enumerate(requests, 1):
            t1_rows = req.get_tax1_rows()
            t2_rows = req.get_tax2_rows()
            
            max_rows = max(len(t1_rows), len(t2_rows))
            if max_rows == 0: max_rows = 1

            for i in range(max_rows):
                t1 = t1_rows[i] if i < len(t1_rows) else {}
                t2 = t2_rows[i] if i < len(t2_rows) else {}
                
                is_first = (i == 0)

                # [cite_start]Name Logic Split [cite: 4]
                full_legal_name = (req.vendor_name_basic or '').upper()
                name_1 = full_legal_name[:35]       # First 35 chars
                name_2 = full_legal_name[35:70]     # Next 35 chars (Overflow)
                
                # Fields only on First Row
                vlms_no = req.request_id if is_first else ""  # Mapped from CSV 'VLMS Number'
                account_group = (req.account_group or "ZDOM") if is_first else ""
                title = req.title if is_first else ""
                city = (req.city or '').upper() if is_first else ""
                
                # [cite_start]Trade Name is now Name 3 [cite: 4]
                name_3 = (req.trade_name[:35].upper() if req.trade_name else "") if is_first else ""
                
                street = (req.street[:35] if req.street else "") if is_first else ""
                street2 = (req.street_2[:40] if req.street_2 else "") if is_first else ""
                street3 = (req.street_3[:40] if req.street_3 else "") if is_first else ""
                street4 = (req.street_4[:40] if req.street_4 else "") if is_first else ""
                postal_code = req.postal_code if is_first else ""
                region = req.state if is_first else ""
                
                contact = req.contact_person_name if is_first else ""
                mob1 = req.mobile_number if is_first else ""
                mob2 = req.mobile_number_2 if is_first else ""
                landline = req.landline_number if is_first else ""
                email = req.vendor_email if is_first else ""
                
                gst = (req.gst_number or "") if is_first else ""
                pan = req.pan_number if is_first else ""
                msme_no = req.msme_number if is_first else ""
                msme_type = req.msme_type if is_first else ""
                
                ifsc = req.bank_ifsc if is_first else ""
                bank_acc = req.bank_account_no if is_first else ""
                holder = (req.bank_account_holder_name[:60] if req.bank_account_holder_name else "") if is_first else ""
                
                gl = req.gl_account if is_first else ""
                h_bank = req.house_bank if is_first else ""
                pay_term = req.payment_terms if is_first else ""
                purch_org = (req.purchase_org or "1000") if is_first else ""
                inco = req.incoterms if is_first else ""

                row = [
                    idx,
                    vlms_no,          # New Column: VLMS Number
                    account_group, 
                    title, 
                    name_1,           # Name 1 (Legal Name 1-35)
                    name_2,           # Name 2 (Legal Name 36-70)
                    name_3,           # Name 3 (Trade Name)
                    street, street2, street3, street4, city, postal_code, region,
                    contact, mob1, mob2, landline, email,
                    gst, pan, msme_no, msme_type,
                    ifsc, bank_acc, holder,
                    gl, h_bank, pay_term, purch_org, pay_term, inco,
                    
                    t1.get('type',''), t1.get('code',''), 'X' if t1.get('subject')=='1' else '', 
                    t1.get('recipient',''), t1.get('cert',''), t1.get('rate',''), 
                    self.format_sap_date(t1.get('start','')), self.format_sap_date(t1.get('end','')), t1.get('reason',''),
                    
                    t2.get('section',''), t2.get('cert',''), t2.get('rate',''), 
                    self.format_sap_date(t2.get('start','')), self.format_sap_date(t2.get('end','')), 
                    '', t2.get('code',''), 'TDSU/S194Q' if t2 else '', t2.get('thresh',''),
                    "INR"
                ]
                writer.writerow(row)
        
        output.seek(0)
        return output

    def get_workflow_logic(self, dept_name):
        """Fetches the logic for a specific department or global stage."""
        
        # 1. Global Finance
        if dept_name == 'GLOBAL_FINANCE':
            steps = []
            for role in ['Bill Passing', 'Treasury Team', 'Tax Team']:
                step = WorkflowStep.query.filter_by(department='Finance', role_label=role).first()
                steps.append({
                    "id": step.role_label if step else role,
                    "role": role,
                    "email": step.approver_email if step else ""
                })
            return {"matrix": [], "steps": steps}
        
        # 2. Global IT
        if dept_name == 'GLOBAL_IT':
            it_routes = ITRouting.query.all()
            return {
                "matrix": [],
                "steps": [], 
                "it_routes": [{"id": r.id, "account_group": r.account_group, "it_assignee_email": r.it_assignee_email} for r in it_routes]
            }

        # 3. Standard Department
        matrix = CategoryRouting.query.filter_by(department=dept_name).all()
        steps = WorkflowStep.query.filter_by(department=dept_name).order_by(WorkflowStep.step_order).all()
        
        return {
            "matrix": [{"id": r.id, "category": r.category_name, "l1_email": r.l1_manager_email, "l2_email": r.l2_head_email} for r in matrix],
            "steps": [{"id": s.id, "role": s.role_label, "email": s.approver_email} for s in steps]
        }

admin_service = AdminService()