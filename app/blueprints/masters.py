from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.extensions import db
from app.models import MasterData

masters_bp = Blueprint('masters', __name__)

# Configuration for the 14 Master Data Types
# Key = URL slug, Value = Display Label
MASTER_TYPES = {
    'region': 'Regions / States',
    'payment-terms': 'Payment Terms',
    'inco-terms': 'Inco Terms',
    'msme-type': 'MSME Types',
    'account-group': 'Account Groups',
    'gl-list': 'GL Accounts',
    'house-bank': 'House Banks',
    'purch-org': 'Purchase Organizations',
    'tds-fields': 'TDS Fields',
    'tds-types': 'Withholding Tax Types',
    'tds-details': 'TDS Rate Details',
    '194q-fields': '194Q Fields',
    '194q-dropdown': '194Q Dropdowns',
    'exemption-reason': 'Exemption Reasons'
}

@masters_bp.before_request
@login_required
def require_admin():
    if current_user.role != 'admin':
        flash("Access denied.", "error")
        return redirect(url_for('main.dashboard'))

@masters_bp.route('/')
def index():
    """Dashboard to list all 14 master data links."""
    return render_template('masters/index.html', master_types=MASTER_TYPES)

@masters_bp.route('/<slug>', methods=['GET'])
def list_items(slug):
    """Generic List View"""
    if slug not in MASTER_TYPES:
        return "Invalid Master Data Type", 404
    
    # Convert slug to DB Category format (e.g., 'payment-terms' -> 'PAYMENT_TERMS')
    # You might need to adjust this matching logic based on your actual CSV data
    db_category = slug.upper().replace('-', '_') 
    
    # Fetch data
    items = MasterData.query.filter_by(category=db_category).order_by(MasterData.code).all()
    
    return render_template('masters/list.html', 
                           slug=slug, 
                           title=MASTER_TYPES[slug], 
                           items=items)

# In app/blueprints/masters.py

@masters_bp.route('/<slug>/add', methods=['GET', 'POST'])
@masters_bp.route('/<slug>/edit/<int:id>', methods=['GET', 'POST'])
def save_item(slug, id=None):
    if slug not in MASTER_TYPES:
        return "Invalid Master Data Type", 404
        
    db_category = slug.upper().replace('-', '_')
    # Use the mapping if you implemented the explicit dict earlier, otherwise:
    # db_category = SLUG_TO_DB_CATEGORY.get(slug, slug.upper().replace('-', '_'))

    item = None
    extra_fields = {} # Dictionary to hold field names for the UI

    if id:
        item = db.session.get(MasterData, id)
        if not item: return "Item not found", 404
        # If editing, use the item's own data keys
        if item.data:
            extra_fields = item.data
    else:
        # If adding NEW, try to find a sibling to guess the schema
        sibling = MasterData.query.filter_by(category=db_category).first()
        if sibling and sibling.data:
            # Create empty keys so the form knows what fields to show
            extra_fields = {k: '' for k in sibling.data.keys()}

    if request.method == 'POST':
        if not item:
            item = MasterData(category=db_category)
            db.session.add(item)
        
        # 1. Save Standard Fields
        item.code = request.form.get('code')
        item.label = request.form.get('label')
        item.parent_code = request.form.get('parent_code')
        item.is_active = True if request.form.get('is_active') else False
        
        # 2. Save Dynamic JSON Fields
        # We assume anything NOT a standard field is part of the JSON data
        standard_keys = ['code', 'label', 'parent_code', 'is_active', 'csrf_token']
        dynamic_data = {}
        
        for key, value in request.form.items():
            if key not in standard_keys:
                dynamic_data[key] = value
        
        # Only save if we actually found extra data
        if dynamic_data:
            item.data = dynamic_data
        
        try:
            db.session.commit()
            flash(f"{MASTER_TYPES[slug]} saved successfully!", "success")
            return redirect(url_for('masters.list_items', slug=slug))
        except Exception as e:
            db.session.rollback()
            flash(f"Error saving data: {str(e)}", "error")

    # Pass 'extra_fields' to the template
    return render_template('masters/form.html', 
                           slug=slug, 
                           title=MASTER_TYPES[slug], 
                           item=item,
                           extra_fields=extra_fields)


@masters_bp.route('/delete/<int:id>', methods=['POST'])
def delete_item(id):
    item = db.session.get(MasterData, id)
    if item:
        db.session.delete(item)
        db.session.commit()
        flash("Item deleted.", "success")
        # Redirect back to the list using the referer or a default
        return redirect(request.referrer or url_for('masters.index'))
    return "Error", 404