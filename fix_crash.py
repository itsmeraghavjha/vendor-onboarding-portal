import os

template_path = os.path.join('app', 'templates', 'admin_workflow.html')

try:
    with open(template_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # We find the code that crashes and replace it with a safe version
    # It changes: {{ selected_master_cat.replace... }} 
    # To:         {{ (selected_master_cat or 'Master Data').replace... }}
    
    broken_code = "{{ selected_master_cat.replace('_', ' ') }}"
    fixed_code = "{{ (selected_master_cat or 'Master Data').replace('_', ' ') }}"
    
    if broken_code in content:
        new_content = content.replace(broken_code, fixed_code)
        
        with open(template_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print("SUCCESS: Fixed the crash in admin_workflow.html")
    else:
        print("NOTICE: Could not find the specific crash line. It might already be fixed.")

except FileNotFoundError:
    print(f"ERROR: Could not find {template_path}. Are you in the right folder?")