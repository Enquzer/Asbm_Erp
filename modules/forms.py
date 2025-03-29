from flask_wtf import FlaskForm
from wtforms import (
    StringField,
    TextAreaField,
    SelectField,
    BooleanField,
    FloatField,
    FileField,
    IntegerField,
    DateField
)
from wtforms.validators import DataRequired, Optional

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
    hire_date = DateField('Hire Date', validators=[DataRequired()])
    internal_notes = TextAreaField('Internal Notes', validators=[Optional()])
    monthly_salary = FloatField('Monthly Salary', validators=[DataRequired()])
    additional_benefits = FloatField('Additional Benefits', validators=[Optional()])
    title = StringField('Title', validators=[DataRequired()])
    gender = SelectField('Gender', choices=[('Male', 'Male'), ('Female', 'Female'), ('Other', 'Other')], validators=[DataRequired()])
    department = StringField('Department', validators=[DataRequired()])
    contract_end_date = DateField('Contract End Date', validators=[Optional()])
    seniority = IntegerField('Seniority', validators=[Optional()])
    management_status = StringField('Management Status', validators=[DataRequired()])
    job_grade = StringField('Job Grade', validators=[DataRequired()])
    step = IntegerField('Step', validators=[DataRequired()])
    basic_salary = FloatField('Basic Salary', validators=[DataRequired()])
    travel_allowance = FloatField('Travel Allowance', validators=[Optional()])
    other_allowance = FloatField('Other Allowance', validators=[Optional()])
    non_taxable_allowance = FloatField('Non-Taxable Allowance', validators=[Optional()])
    other_deduction = FloatField('Other Deduction', validators=[Optional()])
    lunch_deduction_employee = FloatField('Lunch Deduction (Employee)', validators=[Optional()])
    lunch_deduction_court = FloatField('Lunch Deduction (Court)', validators=[Optional()])
    duty_station_id = SelectField('Duty Station', coerce=int, validators=[DataRequired()])

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