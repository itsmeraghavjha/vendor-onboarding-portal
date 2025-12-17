import os

# Define the folder containing templates
TEMPLATE_DIR = os.path.join('app', 'templates')

# Map old endpoint names to new Blueprint endpoint names
replacements = {
    "url_for('login')": "url_for('auth.login')",
    "url_for('logout')": "url_for('auth.logout')",
    
    "url_for('dashboard')": "url_for('main.dashboard')",
    "url_for('create_request')": "url_for('main.create_request')",
    "url_for('review_request'": "url_for('main.review_request'",  # Partial match for args
    "url_for('fake_inbox')": "url_for('main.fake_inbox')",
    "url_for('index')": "url_for('main.index')",
    
    "url_for('admin_workflow')": "url_for('admin.admin_workflow')",
    "url_for('nuke_and_reset')": "url_for('admin.nuke_and_reset')",
    
    "url_for('vendor_portal'": "url_for('vendor.vendor_portal'",
    "url_for('static'": "url_for('static'" # static remains the same, strictly ignored
}

def update_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    
    for old, new in replacements.items():
        # Avoid double replacing if ran twice
        if new not in content: 
            content = content.replace(old, new)
            
    if content != original_content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Fixed: {filepath}")
    else:
        print(f"No changes needed: {filepath}")

if __name__ == "__main__":
    if not os.path.exists(TEMPLATE_DIR):
        print(f"Error: Could not find directory {TEMPLATE_DIR}")
    else:
        print("Scanning templates...")
        for filename in os.listdir(TEMPLATE_DIR):
            if filename.endswith(".html"):
                update_file(os.path.join(TEMPLATE_DIR, filename))
        print("\nAll templates updated! Restart your server.")