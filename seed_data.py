# import os
# import csv
# from app import create_app
# from app.extensions import db
# from app.models import User, Department, MasterData

# app = create_app()

# FILE_CONFIG = {
#     'Account Group List.csv':       ('ACCOUNT_GROUP',   'account group',         'name',        None),
#     'Exemption Reason Drodown.csv': ('EXEMPTION_REASON','exemption reason code', 'description', None),
#     'GL list.csv':                  ('GL_ACCOUNT',      'gl',                    'description', None),
#     'House Bank.csv':               ('HOUSE_BANK',      'house bank',            'bank name',   None),
#     'Inco terms.csv':               ('INCOTERM',        'incoterm',              'description', None),
#     'MSME Type.csv':                ('MSME_TYPE',       'type',                  'description', None),
#     'Payment Terms.csv':            ('PAYMENT_TERM',    'payment terms',         'description', None),
#     'Purch.Org.csv':                ('PURCHASE_ORG',    'purch.org',             'description', None),
#     'Region.csv':                   ('REGION',          'reg code',              'description', None),
#     'Withholding Tax Types.csv':    ('TAX_TYPE',        'tax code',              'description', None),
    
#     # KEY CHANGE: Mapping Parent Code (Tax Type)
#     # Tuple: (Category, Code Col, Label Col, Parent Code Col)
#     'TDS Type wise details.csv':    ('TDS_CODE', 'withhoding tax code', 'name', 'withhoding tax type'), 
# }

# def get_column_index(headers, target_name):
#     target = target_name.lower().strip()
#     for i, h in enumerate(headers):
#         if h.lower().strip().replace('"', '') == target: return i
#     return -1

# def load_csvs():
#     folder = 'csv_data'
#     if not os.path.exists(folder):
#         print(f"❌ Error: '{folder}' folder missing.")
#         return

#     for filename, config in FILE_CONFIG.items():
#         category, target_code, target_label, target_parent = config
#         filepath = os.path.join(folder, filename)
        
#         if not os.path.exists(filepath):
#             print(f"⚠️  Missing: {filename}"); continue

#         print(f"📂 Loading {category} from {filename}...")
        
#         try:
#             lines = []
#             try:
#                 with open(filepath, 'r', encoding='utf-8-sig') as f: lines = f.readlines()
#             except:
#                 with open(filepath, 'r', encoding='latin1') as f: lines = f.readlines()

#             if not lines: continue
#             if 'GL list' in filename: lines = [l.replace('\t', ',') for l in lines]
            
#             reader = csv.reader(lines)
#             headers = next(reader, None)
#             if not headers: continue

#             code_idx = get_column_index(headers, target_code)
#             label_idx = get_column_index(headers, target_label)
#             parent_idx = get_column_index(headers, target_parent) if target_parent else -1

#             if code_idx == -1: 
#                 print(f"   ❌ Col '{target_code}' not found."); continue

#             count = 0
#             for row in reader:
#                 if len(row) <= code_idx: continue
                
#                 code_val = row[code_idx].strip()
#                 label_val = row[label_idx].strip() if label_idx != -1 and len(row) > label_idx else code_val
#                 parent_val = row[parent_idx].strip() if parent_idx != -1 and len(row) > parent_idx else None

#                 if code_val:
#                     if not MasterData.query.filter_by(category=category, code=code_val, parent_code=parent_val).first():
#                         db.session.add(MasterData(category=category, code=code_val, label=label_val, parent_code=parent_val))
#                         count += 1
            
#             db.session.commit()
#             print(f"   ✅ Added {count} items.")

#         except Exception as e:
#             print(f"   ❌ Error: {e}")

# with app.app_context():
#     print("🧹 Cleaning Database...")
#     db.drop_all()
#     print("✨ Creating Tables...")
#     db.create_all()

#     # --- CREATE USERS ---
#     print("👤 Creating Users...")
#     for d in ['IT', 'Finance', 'Purchase', 'HR']: db.session.add(Department(name=d))
    
#     admin = User(username='System Admin', email='admin@heritage.com', role='admin', department='IT'); admin.set_password('admin123')
#     db.session.add(admin)

#     teams = [('Bill Passing Team', 'bill_passing@heritage.com', 'Finance'),
#              ('Treasury Team', 'treasury@heritage.com', 'Finance'),
#              ('Tax Team', 'tax@heritage.com', 'Finance'),
#              ('IT Admin', 'it_admin@heritage.com', 'IT'),
#              ('Purchase Initiator', 'initiator@heritage.com', 'Purchase')]
    
#     for name, email, dept in teams:
#         role = 'initiator' if 'Initiator' in name else 'approver'
#         u = User(username=name, email=email, role=role, department=dept)
#         if role == 'initiator': u.assigned_category = 'Raw Materials'
#         u.set_password('pass123')
#         db.session.add(u)
    
#     db.session.commit()
#     print("📥 importing CSVs..."); load_csvs()
#     print("🚀 Done.")


import os
import csv
import json
from app import create_app
from app.extensions import db
from app.models import User, Department, MasterData

app = create_app()

# Config Format: 'Filename': ('DB_CATEGORY', 'Code Column', 'Label Column', 'Parent Code Column')
FILE_CONFIG = {
    # 1. Standard Dropdowns
    'Account Group List.csv':       ('ACCOUNT_GROUP',   'account group',         'name',        None),
    'Exemption Reason Drodown.csv': ('EXEMPTION_REASON','exemption reason code', 'description', None),
    'GL list.csv':                  ('GL_ACCOUNT',      'gl',                    'description', None),
    'House Bank.csv':               ('HOUSE_BANK',      'house bank',            'bank name',   None),
    'Inco terms.csv':               ('INCOTERM',        'incoterm',              'description', None),
    'MSME Type.csv':                ('MSME_TYPE',       'type',                  'description', None),
    'Payment Terms.csv':            ('PAYMENT_TERM',    'payment terms',         'description', None),
    'Purch.Org.csv':                ('PURCHASE_ORG',    'purch.org',             'description', None),
    'Region.csv':                   ('REGION',          'reg code',              'description', None),
    'Withholding Tax Types.csv':    ('TAX_TYPE',        'tax code',              'description', None),
    
    # 2. Complex Tax Mappings
    'TDS Type wise details.csv':    ('TDS_CODE',   'withhoding tax code', 'name',             'withhoding tax type'),
    '194Q Fields.csv':              ('194Q_FIELD', 'section code',        'exemption reason', None),
    
    # 3. NEW: TDS Fields (Mapping Tax Code -> Exemption Reason, with Tax Type as Parent)
    'TDS FIELDS.csv':               ('TDS_FIELD',  'withholding tax code','exemption reason', 'withholding tax type')
}

def get_column_index(headers, target_name):
    """Finds the index of a column by name (case-insensitive)."""
    target = target_name.lower().strip()
    for i, h in enumerate(headers):
        if h.lower().strip().replace('"', '') == target: return i
    return -1

def load_standard_csvs():
    folder = 'csv_data'
    if not os.path.exists(folder):
        print(f"❌ Error: '{folder}' folder missing.")
        return

    for filename, config in FILE_CONFIG.items():
        category, target_code, target_label, target_parent = config
        filepath = os.path.join(folder, filename)
        
        if not os.path.exists(filepath):
            print(f"⚠️  Skipping missing file: {filename}")
            continue

        print(f"📂 Loading {category} from {filename}...")
        
        try:
            lines = []
            try:
                with open(filepath, 'r', encoding='utf-8-sig') as f: lines = f.readlines()
            except:
                with open(filepath, 'r', encoding='latin1') as f: lines = f.readlines()

            if not lines: continue
            
            # Fix tab-separated GL file
            if 'GL list' in filename: lines = [l.replace('\t', ',') for l in lines]
            
            reader = csv.reader(lines)
            headers = next(reader, None)
            if not headers: continue

            # Clean headers for JSON keys (remove extra spaces)
            clean_headers = [h.strip() for h in headers]

            code_idx = get_column_index(headers, target_code)
            label_idx = get_column_index(headers, target_label)
            parent_idx = get_column_index(headers, target_parent) if target_parent else -1

            if code_idx == -1:
                print(f"   ❌ Column '{target_code}' not found in {filename}"); continue

            count = 0
            for row in reader:
                if len(row) <= code_idx: continue
                
                code_val = row[code_idx].strip()
                # Use Code as Label if Label column is missing
                label_val = row[label_idx].strip() if label_idx != -1 and len(row) > label_idx else code_val
                parent_val = row[parent_idx].strip() if parent_idx != -1 and len(row) > parent_idx else None

                # --- CAPTURE EXTRA COLUMNS (Rates, Dates, Thresholds) ---
                extra_data = {}
                for i, cell in enumerate(row):
                    # Store everything that isn't the Code, Label, or Parent
                    if i != code_idx and i != label_idx and i != parent_idx:
                        if i < len(clean_headers) and cell.strip():
                            extra_data[clean_headers[i]] = cell.strip()
                # --------------------------------------------------------

                if code_val:
                    if not MasterData.query.filter_by(category=category, code=code_val, parent_code=parent_val).first():
                        db.session.add(MasterData(
                            category=category, 
                            code=code_val, 
                            label=label_val, 
                            parent_code=parent_val,
                            data=extra_data  # Stores the flexible JSON data
                        ))
                        count += 1
            
            db.session.commit()
            print(f"   ✅ Added {count} items.")
        except Exception as e:
            print(f"   ❌ Error: {e}")

def load_194q_dropdown():
    """Special handler for the messy '194Q DROP DOWN FIELDS.csv'"""
    filename = '194Q DROP DOWN FIELDS.csv'
    filepath = os.path.join('csv_data', filename)
    if not os.path.exists(filepath): return

    print(f"📂 Loading 194Q_DROPDOWN from {filename}...")
    try:
        with open(filepath, 'r', encoding='utf-8-sig') as f: lines = f.readlines()
        
        count = 0
        for line in lines:
            row = line.strip().split(',')
            # Logic: Identify data rows by checking for valid codes in first 2 columns
            if len(row) >= 3:
                tax_type = row[0].strip()
                tax_code = row[1].strip()
                desc = row[2].strip()

                if len(tax_type) == 2 and len(tax_code) == 2 and tax_type.isalpha():
                    if not MasterData.query.filter_by(category='194Q_DROPDOWN', code=tax_code).first():
                        db.session.add(MasterData(
                            category='194Q_DROPDOWN', 
                            code=tax_code, 
                            label=desc, 
                            parent_code=tax_type
                        ))
                        count += 1
        
        db.session.commit()
        print(f"   ✅ Added {count} items.")
    except Exception as e:
        print(f"   ❌ Error: {e}")

with app.app_context():
    print("WARNING: Re-creating database to ensure schema updates...")
    db.drop_all()
    db.create_all()

    # --- CREATE DEPARTMENTS & USERS ---
    print("👤 Creating Users & Departments...")
    for d in ['IT', 'Finance', 'Purchase', 'HR']: 
        db.session.add(Department(name=d))
    
    admin = User(username='System Admin', email='admin@heritagefoods.in', role='admin', department='IT')
    admin.set_password('admin123')
    db.session.add(admin)

    teams = [('Bill Passing Team', 'bill_passing@heritage.com', 'Finance'),
             ('Treasury Team', 'treasury@heritage.com', 'Finance'),
             ('Tax Team', 'tax@heritage.com', 'Finance'),
             ('IT Admin', 'it_admin@heritage.com', 'IT'),
             ('Purchase Initiator', 'initiator@heritage.com', 'Purchase')]
    
    for name, email, dept in teams:
        role = 'initiator' if 'Initiator' in name else 'approver'
        u = User(username=name, email=email, role=role, department=dept)
        if role == 'initiator': u.assigned_category = 'Raw Materials'
        u.set_password('pass123')
        db.session.add(u)
    
    db.session.commit()

    print("📥 Importing 14 Master Data Files...")
    load_standard_csvs()  # Handles 13 files (including TDS FIELDS.csv)
    load_194q_dropdown()  # Handles the 14th messy file
    print("🚀 Database Seeded Successfully.")