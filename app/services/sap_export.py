import csv
import io
from app.models import VendorRequest

def generate_sap_csv(request_ids):
    output = io.StringIO()
    writer = csv.writer(output)

    # 1. Header (Based on "Basic Structure.csv")
    headers = [
        "S.No", "Vendor Account Group", "Title", "Name 1 (Legal Name)", "Name 2 (Trade Name)",
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
        # --- LOGIC MAPPING ---
        
        # GST Vendor Class Logic: If GST is blank, "0", else blank
        gst_ven_class = "0" if not req.gst_number else ""

        # Tax Flattening Logic (Complex)
        # We need to find WHT and 194Q taxes and map them to set 1 and set 2
        tax1 = next((t for t in req.tax_details if t.tax_category == 'WHT'), None)
        tax2 = next((t for t in req.tax_details if t.tax_category == '194Q'), None)

        row = [
            idx,                            # S.No
            req.account_group or "ZDOM",    # Vendor Account Group (Default to ZDOM if empty)
            req.title,                      # Title
            req.vendor_name_basic[:35],     # Name 1 (Max 35 chars per FS)
            req.trade_name[:35] if req.trade_name else "", # Name 2
            req.street[:35] if req.street else "",         # Street
            req.street_2[:40] if req.street_2 else "",     # Street2
            req.street_3[:40] if req.street_3 else "",     # Street3
            req.street_4[:40] if req.street_4 else "",     # Street4 (NEW)
            req.city[:40] if req.city else "",             # City
            req.postal_code,                # Postal Code
            req.state,                      # Region (Ensure this matches SAP codes like '13')
            req.contact_person_name,        # Contact Person
            req.mobile_number,              # Mobile 1
            req.mobile_number_2,            # Mobile 2
            req.landline_number,            # Landline
            req.vendor_email,               # Email
            req.gst_number or "",           # GST Number
            req.pan_number,                 # PAN Number
            req.msme_number,                # MSME Number
            req.msme_type,                  # MSME Type
            req.bank_ifsc,                  # IFSC
            req.bank_account_no,            # Bank Account
            req.bank_account_holder_name[:60], # Account Holder
            req.gl_account,                 # GL Account
            req.house_bank,                 # House Bank
            req.payment_terms,              # Payment Terms
            req.purchase_org or "1000",     # Purch Org (FS says From Tool)
            req.payment_terms,              # Payment Terms (Repeated)
            req.incoterms,                  # Inco Terms
            
            # --- TAX SET 1 (WHT) ---
            "WHT" if tax1 else "",          # WHT Type -1
            tax1.tax_code if tax1 else "",  # WHT Code -1
            "X" if tax1 else "",            # Subject to w/tax
            tax1.recipient_type if tax1 else "", # Recipient Type
            tax1.cert_no if tax1 else "",   # Cert No -1
            tax1.rate if tax1 else "",      # Rate -1
            tax1.start_date if tax1 else "",# Start Date -1
            tax1.end_date if tax1 else "",  # End Date -1
            tax1.exemption_reason if tax1 else "", # Reason -1
            
            # --- TAX SET 2 (194Q) ---
            tax2.section_code if tax2 else "", # Section Code
            tax2.cert_no if tax2 else "",      # Cert No -2
            tax2.rate if tax2 else "",         # Rate -2
            tax2.start_date if tax2 else "",   # Start Date -2
            tax2.end_date if tax2 else "",     # End Date -2
            tax2.exemption_reason if tax2 else "", # Reason -2
            tax2.tax_code if tax2 else "",     # WHT Code -2
            "TDSU/S194Q" if tax2 else "",      # WHT Type -2 (Hardcoded based on CSV)
            tax2.threshold if tax2 else "",    # Exemption thr amm
            
            "INR" # Currency (Hardcoded)
        ]
        writer.writerow(row)
    
    output.seek(0)
    return output