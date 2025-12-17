from app import create_app, db
from app.models import User, Department, CategoryRouting, WorkflowStep, ITRouting

app = create_app()

def seed_system():
    print("Seeding 3-Phase Workflow Data...")
    
    # 1. Departments
    depts = ['Purchase', 'Marketing', 'Finance', 'IT', 'HR']
    for d in depts:
        if not Department.query.filter_by(name=d).first():
            db.session.add(Department(name=d))
    
    # 2. Category Routing (Phase 1: Dept Level)
    # Example: Purchase Dept has rules for "Raw Materials"
    if not CategoryRouting.query.filter_by(category_name='Raw Materials').first():
        db.session.add(CategoryRouting(
            department='Purchase',
            category_name='Raw Materials',
            l1_manager_email='purchase_l1@heritage.com',
            l2_head_email='purchase_head@heritage.com'
        ))
    
    # 3. IT Routing (Phase 3: IT Level)
    # The "Group of 2 people" logic:
    # ZDOM (Domestic) -> Assigned to IT User 1
    # ZIMP (Import)   -> Assigned to IT User 2
    it_routes = [
        ('ZDOM', 'it_domestic@heritage.com'),
        ('ZIMP', 'it_import@heritage.com'),
        ('ZSER', 'it_domestic@heritage.com') # Service vendors also go to Domestic guy
    ]
    for grp, email in it_routes:
        if not ITRouting.query.filter_by(account_group=grp).first():
            db.session.add(ITRouting(account_group=grp, it_assignee_email=email))

    # 4. Create Users
    users = [
        # --- Admin ---
        ('System Admin', 'admin@heritage.com', 'admin', 'IT'),
        
        # --- Phase 1: Dept Users ---
        ('Purchase L1', 'purchase_l1@heritage.com', 'approver', 'Purchase'),
        ('Purchase Head', 'purchase_head@heritage.com', 'approver', 'Purchase'),
        ('Purchase Initiator', 'buyer@heritage.com', 'initiator', 'Purchase'),
        
        # --- Phase 2: Common Finance Chain (The "Group of 3") ---
        ('Bill Passing Team', 'bill_passing@heritage.com', 'approver', 'Finance'),
        ('Treasury Team', 'treasury@heritage.com', 'approver', 'Finance'),
        ('Tax Team', 'tax@heritage.com', 'approver', 'Finance'),
        
        # --- Phase 3: Common IT Team (The "Group of 2") ---
        ('IT Domestic Admin', 'it_domestic@heritage.com', 'approver', 'IT'),
        ('IT Import Admin', 'it_import@heritage.com', 'approver', 'IT'),
    ]

    for name, email, role, dept in users:
        if not User.query.filter_by(email=email).first():
            u = User(username=name, email=email, role=role, department=dept)
            if 'buyer' in email: u.assigned_category = 'Raw Materials' # Auto-assign for test
            u.set_password('pass123')
            db.session.add(u)
            print(f"Created: {name} ({email})")

    db.session.commit()
    print("--- Seeding Complete ---")

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        seed_system()