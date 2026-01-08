from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, PasswordField, SubmitField, SelectField, TextAreaField, RadioField, BooleanField
from wtforms.validators import DataRequired, Email, EqualTo, Length, Optional

# --- Custom Validator ---
class RequiredIf(DataRequired):
    """Validator which makes a field required if another field has a desired value."""
    def __init__(self, other_field_name, *args, **kwargs):
        self.other_field_name = other_field_name
        super(RequiredIf, self).__init__(*args, **kwargs)

    def __call__(self, form, field):
        other_field = form._fields.get(self.other_field_name)
        if other_field is None:
            raise Exception(f'no field named "{self.other_field_name}" in form')
        if other_field.data == 'YES':
            super(RequiredIf, self).__call__(form, field)
        else:
            Optional()(form, field)

# --- AUTH FORMS ---
class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Secure Sign In')

class ResetPasswordRequestForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    submit = SubmitField('Request Password Reset')

class ResetPasswordForm(FlaskForm):
    password = PasswordField('New Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Reset Password')

# --- VENDOR PORTAL FORM ---
class VendorOnboardingForm(FlaskForm):
    # Step 1: General
    title = SelectField('Title', choices=[('Mr', 'Mr'), ('Ms', 'Ms'), ('M/s', 'M/s'), ('Dr', 'Dr')], validators=[DataRequired()])
    
    # 1. ADDED: Legal Name (This fixes the Jinja2 UndefinedError)
    legal_name = StringField('Legal Name', validators=[DataRequired(), Length(max=100)])
    
    trade_name = StringField('Trade Name')
    constitution = SelectField('Constitution', choices=[
        ('', '-- Select Constitution --'), 
        ('Individual', 'Individual'), ('Proprietorship', 'Proprietorship'), 
        ('Partnership', 'Partnership'), ('LLP (Limited Liability Partnership)', 'LLP (Limited Liability Partnership)'), 
        ('Private Limited Company', 'Private Limited Company'), ('Public Limited Company', 'Public Limited Company'),
        ('HUF', 'HUF'), ('Trust/NGO', 'Trust/NGO'), ('Govt Undertaking', 'Govt Undertaking'),
        ('Other', 'Other')
    ], validators=[DataRequired()])
    
    cin_no = StringField('CIN Number', filters=[lambda x: x.upper() if x else None]) 
    contact_name = StringField('Contact Person', validators=[DataRequired()])
    designation = StringField('Designation', validators=[DataRequired()])
    mobile_1 = StringField('Mobile 1', validators=[DataRequired(), Length(min=10, max=10)])
    mobile_2 = StringField('Mobile 2')
    landline = StringField('Landline')
    
    product_desc = TextAreaField('Product/Service Description', validators=[
        DataRequired(), 
        Length(max=50, message="Description cannot exceed 50 characters")
    ])
    
    street_1 = StringField('Street 1', validators=[DataRequired()])
    street_2 = StringField('Street 2')
    street_3 = StringField('Street 3')
    street_4 = StringField('Street 4')
    city = StringField('City', validators=[DataRequired()])
    pincode = StringField('Pincode', validators=[DataRequired(), Length(min=6, max=6)])
    state = SelectField('State', choices=[], validators=[DataRequired()]) 

    # Step 2: Tax & Compliance
    gst_reg = RadioField('GST Registered?', choices=[('YES', 'Yes'), ('NO', 'No')], validators=[DataRequired()])
    
    # These have validators, so we must be careful in HTML (set required=False in jinja)
    gst_no = StringField('GST Number', 
                         validators=[RequiredIf('gst_reg')], 
                         filters=[lambda x: x.upper() if x else None])
    
    gst_file = FileField('Upload GST', validators=[FileAllowed(['pdf', 'jpg', 'png'], 'Images/PDF only!')])

    pan_no = StringField('PAN Number', 
                         validators=[DataRequired(), Length(min=10, max=10)], 
                         filters=[lambda x: x.upper() if x else None])
    
    # --- ADDED AADHAAR FIELD ---
    aadhaar_no = StringField('Aadhaar Number', validators=[Optional(), Length(min=12, max=12)])
    
    pan_file = FileField('Upload PAN', validators=[FileAllowed(['pdf', 'jpg', 'png'])])

    msme_reg = RadioField('MSME Registered?', choices=[('YES', 'Yes'), ('NO', 'No')], validators=[DataRequired()])
    msme_number = StringField('Udyam No', validators=[RequiredIf('msme_reg')], filters=[lambda x: x.upper() if x else None])
    
    msme_type = SelectField('MSME Type', choices=[
        ('', '--'), ('Manufacturing Micro', 'Manufacturing Micro'), ('Manufacturing Small', 'Manufacturing Small'),
        ('Manufacturing Medium', 'Manufacturing Medium'), ('Services Micro', 'Services Micro'),
        ('Services Small', 'Services Small'), ('Services Medium', 'Services Medium')
    ], validators=[RequiredIf('msme_reg')])
    
    msme_file = FileField('Upload MSME', validators=[FileAllowed(['pdf', 'jpg', 'png'])])

    tds_cert_no = StringField('TDS Cert No')
    tds_file = FileField('Upload TDS', validators=[FileAllowed(['pdf', 'jpg', 'png'])])

    # Step 3: Bank
    bank_name = StringField('Bank Name', validators=[DataRequired()])
    holder_name = StringField('Account Holder Name', validators=[DataRequired()])
    acc_no = StringField('Account Number', validators=[DataRequired()])
    acc_no_confirm = StringField('Confirm Account Number', validators=[DataRequired(), EqualTo('acc_no', message='Account numbers must match')])
    ifsc = StringField('IFSC Code', validators=[DataRequired()], filters=[lambda x: x.upper() if x else None])
    
    bank_file = FileField('Upload Cheque/Passbook', validators=[FileAllowed(['pdf', 'jpg', 'png'])])

    agree_consent = BooleanField('Data Privacy Consent', validators=[DataRequired()])
    submit = SubmitField('Submit Application')