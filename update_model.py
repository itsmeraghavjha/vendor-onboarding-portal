# Create file: update_model.py
import os

path = os.path.join('app', 'models.py')
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# We replace the MasterData class with a more robust version
new_class = """class MasterData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(50), index=True) # e.g. 'REGION', 'BANK'
    code = db.Column(db.String(50))                 # e.g. '01', 'HDFC'
    label = db.Column(db.String(255))               # e.g. 'Andhra Pradesh'
    parent_code = db.Column(db.String(50))          # For dependent dropdowns
    meta_data = db.Column(db.Text)                  # JSON string for extras (e.g. Account No)
    is_active = db.Column(db.Boolean, default=True)

    def __repr__(self):
        return f"<{self.category}: {self.code}>"
"""

if "class MasterData" in content:
    # Basic replace - for a production app we would use migration scripts, 
    # but for this setup, overwriting the class definition text is fastest.
    import re
    # Regex to replace the existing MasterData class block
    content = re.sub(r'class MasterData\(db\.Model\):[\s\S]*?(?=\nclass|\Z)', new_class, content)
    
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("MasterData model updated successfully.")
else:
    print("MasterData model not found. Please ensure you ran the previous fixes.")