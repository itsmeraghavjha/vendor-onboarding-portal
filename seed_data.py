import os
import csv
from app import create_app
from app.extensions import db
from app.models import User, Department, MasterData

app = create_app()

FILE_CONFIG = {
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
    
    # KEY CHANGE: Mapping Parent Code (Tax Type)
    # Tuple: (Category, Code Col, Label Col, Parent Code Col)
    'TDS Type wise details.csv':    ('TDS_CODE', 'withhoding tax code', 'name', 'withhoding tax type'), 
}

def get_column_index(headers, target_name):
    target = target_name.lower().strip()
    for i, h in enumerate(headers):
        if h.lower().strip().replace('"', '') == target: return i
    return -1

def load_csvs():
    folder = 'csv_data'
    if not os.path.exists(folder):
        print(f"❌ Error: '{folder}' folder missing.")
        return

    for filename, config in FILE_CONFIG.items():
        category, target_code, target_label, target_parent = config
        filepath = os.path.join(folder, filename)
        
        if not os.path.exists(filepath):
            print(f"⚠️  Missing: {filename}"); continue

        print(f"📂 Loading {category} from {filename}...")
        
        try:
            lines = []
            try:
                with open(filepath, 'r', encoding='utf-8-sig') as f: lines = f.readlines()
            except:
                with open(filepath, 'r', encoding='latin1') as f: lines = f.readlines()

            if not lines: continue
            if 'GL list' in filename: lines = [l.replace('\t', ',') for l in lines]
            
            reader = csv.reader(lines)
            headers = next(reader, None)
            if not headers: continue

            code_idx = get_column_index(headers, target_code)
            label_idx = get_column_index(headers, target_label)
            parent_idx = get_column_index(headers, target_parent) if target_parent else -1

            if code_idx == -1: 
                print(f"   ❌ Col '{target_code}' not found."); continue

            count = 0
            for row in reader:
                if len(row) <= code_idx: continue
                
                code_val = row[code_idx].strip()
                label_val = row[label_idx].strip() if label_idx != -1 and len(row) > label_idx else code_val
                parent_val = row[parent_idx].strip() if parent_idx != -1 and len(row) > parent_idx else None

                if code_val:
                    if not MasterData.query.filter_by(category=category, code=code_val, parent_code=parent_val).first():
                        db.session.add(MasterData(category=category, code=code_val, label=label_val, parent_code=parent_val))
                        count += 1
            
            db.session.commit()
            print(f"   ✅ Added {count} items.")

        except Exception as e:
            print(f"   ❌ Error: {e}")

with app.app_context():
    print("🧹 Cleaning Database...")
    db.drop_all()
    print("✨ Creating Tables...")
    db.create_all()

    # --- CREATE USERS ---
    print("👤 Creating Users...")
    for d in ['IT', 'Finance', 'Purchase', 'HR']: db.session.add(Department(name=d))
    
    admin = User(username='System Admin', email='admin@heritage.com', role='admin', department='IT'); admin.set_password('admin123')
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
    print("📥 importing CSVs..."); load_csvs()
    print("🚀 Done.")