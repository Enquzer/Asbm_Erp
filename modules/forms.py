# modules/forms.py
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, BooleanField, FloatField, FileField, IntegerField, DateField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Optional, Length, EqualTo

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=4, max=50)])
    password = PasswordField('Password', validators=[DataRequired()])
    remember = BooleanField('Remember me')
    submit = SubmitField('Login')

class RegisterForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=4, max=50)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    role = StringField('Role', validators=[DataRequired()])
    submit = SubmitField('Register')

class ProfileForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=4, max=50)])
    profile_picture = FileField('Profile Picture')
    password = PasswordField('New Password', validators=[Length(min=6)])
    confirm_password = PasswordField('Confirm New Password', validators=[EqualTo('password')])
    submit = SubmitField('Update Profile')

class EmployeeForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired()])
    address_woreda = StringField('Woreda', validators=[Optional()])
    address_kifle_ketema = StringField('Kifle Ketema', validators=[Optional()])
    phone_number = StringField('Phone Number', validators=[Optional()])
    emergency_contact_name = StringField('Emergency Contact Name', validators=[Optional()])
    emergency_contact_phone = StringField('Emergency Contact Phone', validators=[Optional()])
    photo = FileField('Photo', validators=[Optional()])
    cv = FileField('CV (PDF)', validators=[Optional()])
    manager_id = SelectField('Manager', coerce=int, validators=[Optional()])
    location = StringField('Location', validators=[Optional()])
    birth_date = DateField('Date of Birth', validators=[DataRequired()])
    hire_date = DateField('Hire Date', format='%Y-%m-%d', validators=[DataRequired()])
    internal_notes = TextAreaField('Internal Notes', validators=[Optional()])
    monthly_salary = FloatField('Monthly Salary', validators=[DataRequired()])
    additional_benefits = FloatField('Additional Benefits', validators=[Optional()])
    job_title = StringField('Job Title', validators=[DataRequired()])
    gender = SelectField('Gender', choices=[('Male', 'Male'), ('Female', 'Female'), ('Other', 'Other')], validators=[DataRequired()])
    department = StringField('Department', validators=[DataRequired()])
    contract_end_date = DateField('Contract End Date', validators=[Optional()])
    seniority = IntegerField('Seniority', validators=[Optional()])
    management_status = StringField('Management Status', validators=[DataRequired()], default='Active')
    job_grade = StringField('Job Grade', validators=[DataRequired()])
    step = IntegerField('Step', validators=[DataRequired()])
    travel_allowance = FloatField('Travel Allowance', validators=[Optional()])
    other_allowance = FloatField('Other Allowance', validators=[Optional()])
    non_taxable_allowance = FloatField('Non-Taxable Allowance', validators=[Optional()])
    other_deduction = FloatField('Other Deduction', validators=[Optional()])
    lunch_deduction_employee = FloatField('Lunch Deduction (Employee)', validators=[Optional()])
    lunch_deduction_court = FloatField('Lunch Deduction (Court)', validators=[Optional()])
    duty_station_id = SelectField('Duty Station', coerce=int, validators=[DataRequired()])
    position_id = SelectField('Position', coerce=int)
    badge_id = StringField('Badge ID')

class ProductForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired()])
    description = TextAreaField('Description', validators=[Optional()])
    product_code = StringField('Product Code', validators=[DataRequired()])
    product_type = StringField('Product Type', validators=[DataRequired()])
    is_processed = BooleanField('Is Processed', default=False)
    selling_price = FloatField('Selling Price', validators=[DataRequired()])
    cost = FloatField('Cost', validators=[DataRequired()])
    customer_id = SelectField('Customer', coerce=int, validators=[Optional()])
    supplier = StringField('Supplier', validators=[Optional()])
    batch_number = StringField('Batch Number', validators=[Optional()])
    image_path = FileField('Image', validators=[Optional()])
    parameters = StringField('Parameters', validators=[Optional()])

class CustomerForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired(), Length(max=100)])
    email = StringField('Email', validators=[DataRequired()])
    phone_number = StringField('Phone Number', validators=[DataRequired(), Length(max=20)])
    location_address = StringField('Location Address', validators=[DataRequired(), Length(max=200)])
    product_types = StringField('Product Types', validators=[DataRequired(), Length(max=100)])
    rating = FloatField('Rating', validators=[Optional()])
    submit = SubmitField('Add Customer')

class OrderForm(FlaskForm):
    product_id = SelectField('Product', coerce=int, validators=[DataRequired()])
    customer_id = SelectField('Customer', coerce=int, validators=[DataRequired()])
    quantity = FloatField('Quantity', validators=[DataRequired()])
    order_date = DateField('Order Date', format='%Y-%m-%d', validators=[DataRequired()])
    status = SelectField('Status', choices=[('Pending', 'Pending'), ('Completed', 'Completed'), ('Cancelled', 'Cancelled')], validators=[DataRequired()])
    submit = SubmitField('Add Order')