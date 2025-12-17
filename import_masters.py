import os
import csv
import json
from app import create_app, db
from app.models import MasterData

app = create_app()

# CONFIGURATION: Map CSV filenames to DB Categories
# Note: 'composite_code' is used when a single column isn't unique (like for Rule tables).
# We handle the source file typos (e.g., 'Scection', 'Withhoding') explicitly here.

CSV_MAP = {
    # --- 1. Basic Lists ---
    'ACCOUNT_GROUP':    {'file': 'Account Group',   'code': 'Account Group', 'label': 'Name', 'extra': ['Module']},
    'REGION':           {'file': 'Region',          'code': 'Reg Code',      'label': 'Description'},
    'MSME_TYPE':        {'file': 'MSME Type',       'code': 'Type',          'label': 'Description'},
    'PAYMENT_TERMS':    {'file': 'Payment Terms',   'code': 'Payment Terms', 'label': 'Description'},
    'PURCHASE_ORG':     {'file': 'Purch.Org',       'code': 'Purch.Org',     'label': 'Description'},
    'GL_ACCOUNT':       {'file': 'GL list',         'code': 'GL',            'label': 'Description'},
    'HOUSE_BANK':       {'file': 'House Bank',      'code': 'House Bank',    'label': 'Bank Name', 'extra': ['Account No']},
    'WHT_TYPE':         {'file': 'Withholding Tax Types', 'code': 'TAX code', 'label': 'Description'},
    'INCOTERMS':        {'file': 'Inco terms',      'code': 'Incoterm',      'label': 'Description'},
    'EXEMPTION_REASON': {'file': 'Exemption Reason','code': 'Exemption Reason Code', 'label': 'Description'},

    # --- 2. Dependent Dropdowns ---
    'TDS_CODE': {
        'file': 'TDS Type wise', 
        'code': 'Withhoding Tax Code',   # Matches typo in CSV
        'label': 'Name', 
        'parent': 'Withhoding Tax Type', # Matches typo in CSV
        'extra': ['Scection', 'Country'] # Matches typo 'Scection' in CSV
    },
    '194Q_DROPDOWN': {
        'file': '194Q DROP DOWN',
        'code': 'Withholding Tax Code',
        'label': 'Description',
        'parent': 'Withholding Tax Type'
    },

    # --- 3. Logic & Rule Tables (Complex Keys) ---
    'TDS_RULES': {
        'file': 'TDS FIELDS', 
        # Unique Key: Type + Code + Recipient Type (e.g. "IA|I1|CO")
        'composite_code': ['Withholding Tax Type', 'Withholding Tax Code', 'Recipient Type'], 
        'label': 'Exemption Reason', 
        'extra': ['Exemption Rate', 'Exemption Start Date', 'Exemption End Date', 'Subject to w/tax', 'Exemption Certificate No.']
    },
    '194Q_RULES': {
        'file': '194Q Fields', 
        'code': 'Section Code', 
        'label': 'Exemption Reason', 
        'extra': ['Exemption Rate', 'Exemption thr amm', 'Currency', 'Withholding Tax Code']
    }
}

DATA_DIR = os.path.join(os.getcwd(), 'csv_data')

def get_value(row, col_name):
    """Safely gets value from row, trying exact match then stripped match."""
    if not col_name: return None
    # 1. Try exact match
    if col_name in row: return row[col_name]
    # 2. Try match ignoring outer spaces in keys
    for k in row.keys():
        if k.strip() == col_name.strip():
            return row[k]
    return None

def import_csv(category, config):
    # Find file
    target_file = None
    if not os.path.exists(DATA_DIR):
        print(f"Error: {DATA_DIR} not found.")
        return

    for fname in os.listdir(DATA_DIR):
        # Flexible partial matching
        if config['file'].lower().replace(' ', '') in fname.lower().replace(' ', '') and fname.endswith('.csv'):
            target_file = os.path.join(DATA_DIR, fname)
            break
    
    if not target_file:
        print(f"Skipping {category}: File containing '{config['file']}' not found.")
        return

    print(f"Processing {category} from {os.path.basename(target_file)}...")
    
    # Clear old data for this category
    db.session.query(MasterData).filter_by(category=category).delete()
    
    try:
        with open(target_file, 'r', encoding='utf-8-sig', errors='replace') as f:
            # Detect header line (skips garbage top lines common in SAP exports)
            lines = f.readlines()
            start_line = 0
            
            # Determine which column to look for to identify the header row
            search_col = config.get('code')
            if not search_col and 'composite_code' in config:
                search_col = config['composite_code'][0]
            
            if search_col:
                for i, line in enumerate(lines):
                    if search_col in line:
                        start_line = i
                        break
            
            reader = csv.DictReader(lines[start_line:])
            
            count = 0
            for row in reader:
                # 1. Build Code (Unique Key)
                code_val = None
                if 'composite_code' in config:
                    parts = []
                    for c in config['composite_code']:
                        val = get_value(row, c)
                        parts.append(val if val else 'NA')
                    code_val = "|".join(parts)
                else:
                    code_val = get_value(row, config.get('code'))
                
                if not code_val or code_val.strip() == '': 
                    continue

                # 2. Build Label
                label_val = get_value(row, config.get('label'))
                # If label missing, use code as label
                final_label = label_val.strip() if label_val else code_val.strip()
                
                # 3. Parent (Dependency)
                parent_val = get_value(row, config.get('parent'))
                
                # 4. Extras (Metadata)
                meta = {}
                if 'extra' in config:
                    for c in config['extra']:
                        val = get_value(row, c)
                        if val: meta[c] = val
                
                # Insert into DB
                md = MasterData(
                    category=category,
                    code=code_val.strip(),
                    label=final_label,
                    parent_code=parent_val.strip() if parent_val else None,
                    meta_data=json.dumps(meta)
                )
                db.session.add(md)
                count += 1
                
            db.session.commit()
            print(f"  -> Imported {count} items.")

    except Exception as e:
        print(f"  -> Error importing {category}: {e}")
        db.session.rollback()

if __name__ == "__main__":
    with app.app_context():
        db.create_all() # Ensure table exists
        print("Starting Import...")
        for cat, conf in CSV_MAP.items():
            import_csv(cat, conf)
        print("Done!")