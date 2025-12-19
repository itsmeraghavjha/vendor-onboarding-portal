import sqlite3
import os

# Connect to the database
db_path = os.path.join(os.getcwd(), 'app.db')

if not os.path.exists(db_path):
    print(f"Error: Database not found at {db_path}")
else:
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Add the missing column
        print("Attempting to add 'last_query' column...")
        cursor.execute("ALTER TABLE vendor_request ADD COLUMN last_query TEXT")
        
        conn.commit()
        conn.close()
        print("✅ Success! Column 'last_query' added. You can now restart your app.")
        
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("ℹ️  Column 'last_query' already exists. No changes needed.")
        else:
            print(f"❌ Error: {e}")