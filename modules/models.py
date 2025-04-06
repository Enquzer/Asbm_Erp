from database import db
from datetime import datetime, date
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import logging

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Customer and Product-related Models
class Customer(db.Model):
    __tablename__ = 'customers'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone_number = db.Column(db.String(20), nullable=True)
    location_address = db.Column(db.String(200), nullable=True)
    product_types = db.Column(db.String(200), nullable=True)
    rating = db.Column(db.Float, default=0.0)
    contact_details = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    orders = db.relationship('Order', back_populates='customer', lazy=True)
    products = db.relationship('Product', back_populates='customer', lazy=True)

class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    product_code = db.Column(db.String(50), unique=True, nullable=False)
    product_type = db.Column(db.String(50), nullable=False, default='General')
    is_processed = db.Column(db.Boolean, default=False)
    selling_price = db.Column(db.Float, default=0.0)
    cost = db.Column(db.Float, default=0.0)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=True)
    customer_name = db.Column(db.String(100), nullable=True)
    supplier = db.Column(db.String(100), nullable=True)
    batch_number = db.Column(db.String(50), nullable=True)
    sku = db.Column(db.String(50), nullable=False)
    stock_quantity = db.Column(db.Integer, nullable=False, default=0)
    image_path = db.Column(db.String(200), nullable=True)
    parameters = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    customer = db.relationship('Customer', back_populates='products', lazy=True)
    plans = db.relationship('ProductPlan', back_populates='product', lazy=True)
    purchase_orders = db.relationship('PurchaseOrder', back_populates='product', lazy=True)
    orders = db.relationship('Order', back_populates='product', lazy=True)
    sales_records = db.relationship('SalesRecord', back_populates='product', lazy=True)
    sales = db.relationship('Sale', back_populates='product', lazy=True)
    config = db.relationship('ProductConfig', back_populates='product', uselist=False, lazy=True)
    prices = db.relationship('ProductPrice', back_populates='product', lazy=True)
    planning_records = db.relationship('Planning', back_populates='product', lazy=True)

class ProductConfig(db.Model):
    __tablename__ = 'product_configs'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    supports_direct_sales = db.Column(db.Boolean, default=True)
    supports_service_sales = db.Column(db.Boolean, default=False)
    uom = db.Column(db.String(20), nullable=False)
    product = db.relationship('Product', back_populates='config', lazy=True)

class ProductPrice(db.Model):
    __tablename__ = 'product_prices'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    price = db.Column(db.Float, nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=True)
    product = db.relationship('Product', back_populates='prices', lazy=True)

class ProductPlan(db.Model):
    __tablename__ = 'product_plans'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    plan_type = db.Column(db.String(20), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    planned_quantity = db.Column(db.Float, nullable=False)
    planned_value = db.Column(db.Float, nullable=False)
    actual_quantity = db.Column(db.Float, default=0.0)
    actual_value = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    product = db.relationship('Product', back_populates='plans', lazy=True)
    changes = db.relationship('PlanChangeLog', back_populates='plan', lazy=True)

class Planning(db.Model):
    __tablename__ = 'planning'
    id = db.Column(db.Integer, primary_key=True)
    task_name = db.Column(db.String(100), nullable=False)
    start_date = db.Column(db.DateTime, nullable=False)
    end_date = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), default='Pending')
    assigned_to = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    total_produced = db.Column(db.Float, default=0.0)
    total_etb = db.Column(db.Float, default=0.0)
    assigned_user = db.relationship('User', back_populates='planning_tasks', lazy=True)
    product = db.relationship('Product', back_populates='planning_records', lazy=True)

class SalesRecord(db.Model):
    __tablename__ = 'sales_records'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    value = db.Column(db.Float, nullable=False)
    sale_date = db.Column(db.Date, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    product = db.relationship('Product', back_populates='sales_records', lazy=True)

class PlanChangeLog(db.Model):
    __tablename__ = 'plan_change_logs'
    id = db.Column(db.Integer, primary_key=True)
    plan_id = db.Column(db.Integer, db.ForeignKey('product_plans.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    old_value = db.Column(db.Float, nullable=True)
    new_value = db.Column(db.Float, nullable=True)
    change_description = db.Column(db.Text, nullable=True)
    change_date = db.Column(db.DateTime, default=datetime.utcnow)
    plan = db.relationship('ProductPlan', back_populates='changes', lazy=True)
    user = db.relationship('User', back_populates='plan_changes', lazy=True)

class Settings(db.Model):
    __tablename__ = 'settings'
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    value = db.Column(db.String(100), nullable=False)

class Order(db.Model):
    __tablename__ = 'orders'
    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(50), unique=True, nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    order_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    payment_status = db.Column(db.String(20), nullable=False, default='Pending')
    order_status = db.Column(db.String(20), nullable=False, default='Placed')
    tax = db.Column(db.Float, nullable=False, default=0.0)
    total = db.Column(db.Float, nullable=False, default=0.0)
    delivery_info = db.Column(db.Text, nullable=True)
    order_placed_date = db.Column(db.Date, nullable=True)
    required_delivery_date = db.Column(db.Date, nullable=True)
    total_value = db.Column(db.Float, nullable=True)
    customer = db.relationship('Customer', back_populates='orders', lazy=True)
    product = db.relationship('Product', back_populates='orders', lazy=True)
    sales = db.relationship('Sale', back_populates='order', lazy=True)

class Sale(db.Model):
    __tablename__ = 'sales'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=True)
    sale_date = db.Column(db.Date, nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    total_price = db.Column(db.Float, nullable=False)
    sale_type = db.Column(db.String(20), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    product = db.relationship('Product', back_populates='sales', lazy=True)
    order = db.relationship('Order', back_populates='sales', lazy=True)

class PurchaseOrder(db.Model):
    __tablename__ = 'purchase_orders'
    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(20), unique=True, nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    order_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    status = db.Column(db.String(20), nullable=False, default='Pending')
    product = db.relationship('Product', back_populates='purchase_orders', lazy=True)

class ProductionPlan(db.Model):
    __tablename__ = 'production_plans'
    id = db.Column(db.Integer, primary_key=True)
    planned_quantity = db.Column(db.Integer, nullable=False)
    plan_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

class ProductionActual(db.Model):
    __tablename__ = 'production_actuals'
    id = db.Column(db.Integer, primary_key=True)
    actual_quantity = db.Column(db.Integer, nullable=False)
    actual_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

class RevenuePlan(db.Model):
    __tablename__ = 'revenue_plans'
    id = db.Column(db.Integer, primary_key=True)
    planned_revenue = db.Column(db.Float, nullable=False, default=0.0)
    plan_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

class RevenueActual(db.Model):
    __tablename__ = 'revenue_actuals'
    id = db.Column(db.Integer, primary_key=True)
    actual_revenue = db.Column(db.Float, nullable=False, default=0.0)
    actual_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

# HR-related Models
class DutyStation(db.Model):
    __tablename__ = 'duty_stations'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    employees = db.relationship('Employee', back_populates='duty_station', lazy=True)
    positions = db.relationship('Position', back_populates='duty_station', lazy=True)
    food_fuel_records = db.relationship('FoodFuelRecord', back_populates='duty_station', lazy=True)
    security_incidents = db.relationship('SecurityIncident', back_populates='duty_station', lazy=True)
    petty_cash = db.relationship('PettyCash', back_populates='duty_station', lazy=True)
    project_funding = db.relationship('ProjectFunding', back_populates='duty_station', lazy=True)
    property_items = db.relationship('PropertyItem', back_populates='duty_station', lazy=True)
    admin_letters = db.relationship('AdminLetter', back_populates='duty_station', lazy=True)
    bills = db.relationship('Bill', back_populates='duty_station', lazy=True)

class Employee(db.Model):
    __tablename__ = 'employees'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    address_woreda = db.Column(db.String(100), nullable=True)
    address_kifle_ketema = db.Column(db.String(100), nullable=True)
    phone_number = db.Column(db.String(20), nullable=True)
    emergency_contact_name = db.Column(db.String(100), nullable=True)
    emergency_contact_phone = db.Column(db.String(20), nullable=True)
    photo_path = db.Column(db.String(200), nullable=True)
    cv_path = db.Column(db.String(200), nullable=True)
    manager_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True)
    position_id = db.Column(db.Integer, db.ForeignKey('positions.id'), nullable=True)
    badge_id = db.Column(db.String(50), unique=True, nullable=True)
    location = db.Column(db.String(100), nullable=True)
    birth_date = db.Column(db.Date, nullable=False)
    hire_date = db.Column(db.Date, nullable=False)
    internal_notes = db.Column(db.Text, nullable=True)
    monthly_salary = db.Column(db.Float, nullable=False, default=0.0)
    additional_benefits = db.Column(db.Float, nullable=True, default=0.0)
    title = db.Column(db.String(100), nullable=False)
    gender = db.Column(db.String(10), nullable=False)
    department = db.Column(db.String(100), nullable=False)
    contract_end_date = db.Column(db.Date, nullable=True)
    seniority = db.Column(db.Integer, nullable=True)
    management_status = db.Column(db.String(10), nullable=False, default='Active')
    job_grade = db.Column(db.String(20), nullable=False)
    step = db.Column(db.Integer, nullable=False)
    travel_allowance = db.Column(db.Float, nullable=True, default=0.0)
    other_allowance = db.Column(db.Float, nullable=True, default=0.0)
    non_taxable_allowance = db.Column(db.Float, nullable=True, default=0.0)
    other_deduction = db.Column(db.Float, nullable=True, default=0.0)
    lunch_deduction_employee = db.Column(db.Float, nullable=True, default=0.0)
    lunch_deduction_court = db.Column(db.Float, nullable=True, default=0.0)
    duty_station_id = db.Column(db.Integer, db.ForeignKey('duty_stations.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    basic_salary = db.Column(db.Float, nullable=False, default=0.0)
    termination_date = db.Column(db.Date, nullable=True)
    periods = db.relationship('EmployeePeriod', back_populates='employee', lazy=True)
    manager = db.relationship('Employee', remote_side=[id], back_populates='subordinates')
    subordinates = db.relationship('Employee', back_populates='manager', lazy=True)
    position = db.relationship('Position', back_populates='employees', lazy=True)
    duty_station = db.relationship('DutyStation', back_populates='employees', lazy=True)
    overtime_records = db.relationship(
        'Overtime',
        foreign_keys='Overtime.employee_id',
        primaryjoin='Employee.id == Overtime.employee_id',
        back_populates='employee',
        lazy=True
    )
    overtime_approvals = db.relationship(
        'Overtime',
        foreign_keys='Overtime.approved_by',
        primaryjoin='Employee.id == Overtime.approved_by',
        back_populates='approved_by_employee',
        lazy=True
    )
    attendance_records = db.relationship('Attendance', back_populates='employee', lazy=True)
    leave_records = db.relationship(
        'AnnualLeave',
        foreign_keys='AnnualLeave.employee_id',
        primaryjoin='Employee.id == AnnualLeave.employee_id',
        back_populates='employee',
        lazy=True
    )
    leave_approvals = db.relationship(
        'AnnualLeave',
        foreign_keys='AnnualLeave.approved_by',
        primaryjoin='Employee.id == AnnualLeave.approved_by',
        back_populates='approved_by_employee',
        lazy=True
    )
    letters = db.relationship('EmploymentLetter', back_populates='employee', lazy=True)
    contracts = db.relationship('Contract', back_populates='employee', lazy=True)
    property_items = db.relationship('PropertyItem', back_populates='employee', lazy=True)
    petty_cash = db.relationship('PettyCash', back_populates='employee', lazy=True)
    food_fuel_records = db.relationship('FoodFuelRecord', back_populates='payee', lazy=True)

class EmployeePeriod(db.Model):
    __tablename__ = 'employee_periods'
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    worked_days = db.Column(db.Integer, nullable=False, default=0)
    employee = db.relationship('Employee', back_populates='periods', lazy=True)

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(50), nullable=False)
    permissions = db.Column(db.JSON, default=lambda: {'dashboard': {'view': True}})
    profile_picture = db.Column(db.String(100), default='placeholder_user.jpg')
    plan_changes = db.relationship('PlanChangeLog', back_populates='user', lazy=True)
    planning_tasks = db.relationship('Planning', back_populates='assigned_user', lazy=True)
    petty_cash_approvals = db.relationship('PettyCash', back_populates='approver', lazy=True)
    resources = db.relationship('Resource', back_populates='uploader', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def has_permission(self, module, action='view'):
        return self.is_admin() or (self.permissions.get(module, {}).get(action, False))

    def is_admin(self):
        return self.role.lower() == 'admin'

    def is_authenticated(self):
        return True

    def is_active(self):
        return True

    def is_anonymous(self):
        return False

    def get_id(self):
        return str(self.id)

class Resource(db.Model):
    __tablename__ = 'resources'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    filename = db.Column(db.String(100), nullable=False)
    uploaded_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    upload_date = db.Column(db.DateTime, default=db.func.current_timestamp())
    uploader = db.relationship('User', back_populates='resources', lazy=True)

class Department(db.Model):
    __tablename__ = 'departments'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    activities = db.relationship('Activity', back_populates='department', lazy=True)

class Project(db.Model):
    __tablename__ = 'projects'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), default='Active')
    duty_station_id = db.Column(db.Integer, db.ForeignKey('duty_stations.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    activities = db.relationship('Activity', back_populates='project', lazy=True)
    reports = db.relationship('Report', back_populates='project', lazy=True)
    funding = db.relationship('ProjectFunding', back_populates='project', lazy=True)
    duty_station = db.relationship('DutyStation', backref='projects', lazy=True)

class Activity(db.Model):
    __tablename__ = 'activities'
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=True)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True)
    activity_name = db.Column(db.String(100), nullable=False)
    planned_date = db.Column(db.Date, nullable=False)
    intended_result = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default='Not Achieved')
    project = db.relationship('Project', back_populates='activities', lazy=True)
    department = db.relationship('Department', back_populates='activities', lazy=True)
    followups = db.relationship('ActivityFollowup', back_populates='activity', lazy=True)

class ActivityFollowup(db.Model):
    __tablename__ = 'activity_followups'
    id = db.Column(db.Integer, primary_key=True)
    activity_id = db.Column(db.Integer, db.ForeignKey('activities.id'), nullable=False)
    followup_date = db.Column(db.Date, nullable=False)
    notes = db.Column(db.Text, nullable=True)
    comment = db.Column(db.Text, nullable=True)
    status_update = db.Column(db.Text, nullable=True)
    activity = db.relationship('Activity', back_populates='followups', lazy=True)

class Report(db.Model):
    __tablename__ = 'reports'
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    week_start = db.Column(db.Date, nullable=True)
    week_end = db.Column(db.Date, nullable=True)
    summary = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    report_date = db.Column(db.Date, nullable=False)
    project = db.relationship('Project', back_populates='reports', lazy=True)

class Overtime(db.Model):
    __tablename__ = 'overtime'
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    hours = db.Column(db.Float, nullable=False)
    rate = db.Column(db.Float, nullable=False, default=1.5)
    approved = db.Column(db.Boolean, default=False)
    approved_by = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    employee = db.relationship(
        'Employee',
        foreign_keys=[employee_id],
        primaryjoin='Employee.id == Overtime.employee_id',
        back_populates='overtime_records',
        lazy=True
    )
    approved_by_employee = db.relationship(
        'Employee',
        foreign_keys=[approved_by],
        primaryjoin='Employee.id == Overtime.approved_by',
        back_populates='overtime_approvals',
        lazy=True
    )

class Attendance(db.Model):
    __tablename__ = 'attendance'
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    check_in = db.Column(db.DateTime, nullable=True)
    check_out = db.Column(db.DateTime, nullable=True)
    badge_id = db.Column(db.String(50), nullable=True)
    status = db.Column(db.String(20), default='Present')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    employee = db.relationship('Employee', back_populates='attendance_records', lazy=True)

class AnnualLeave(db.Model):
    __tablename__ = 'annual_leave'
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    total_days = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), default='Pending')
    approved_by = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True)
    applied_at = db.Column(db.DateTime, default=datetime.utcnow)
    approved_at = db.Column(db.DateTime, nullable=True)
    employee = db.relationship(
        'Employee',
        foreign_keys=[employee_id],
        primaryjoin='Employee.id == AnnualLeave.employee_id',
        back_populates='leave_records',
        lazy=True
    )
    approved_by_employee = db.relationship(
        'Employee',
        foreign_keys=[approved_by],
        primaryjoin='Employee.id == AnnualLeave.approved_by',
        back_populates='leave_approvals',
        lazy=True
    )

class EmploymentLetter(db.Model):
    __tablename__ = 'employment_letters'
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    letter_type = db.Column(db.String(50), nullable=False)
    content = db.Column(db.Text, nullable=False)
    file_path = db.Column(db.String(200), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    employee = db.relationship('Employee', back_populates='letters', lazy=True)

class Contract(db.Model):
    __tablename__ = 'contracts'
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=True)
    file_path = db.Column(db.String(200), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    employee = db.relationship('Employee', back_populates='contracts', lazy=True)

class Position(db.Model):
    __tablename__ = 'positions'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    department = db.Column(db.String(100))
    salary_range_min = db.Column(db.Float)
    salary_range_max = db.Column(db.Float)
    duty_station_id = db.Column(db.Integer, db.ForeignKey('duty_stations.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    duty_station = db.relationship('DutyStation', back_populates='positions', lazy=True)
    employees = db.relationship('Employee', back_populates='position', lazy=True)

# Admin Activities Models
class Bill(db.Model):
    __tablename__ = 'bills'
    id = db.Column(db.Integer, primary_key=True)
    bill_number = db.Column(db.String(50), unique=True, nullable=False)
    receipt_number = db.Column(db.String(50), nullable=True)
    bill_type = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text, nullable=True)
    amount = db.Column(db.Float, nullable=False)
    due_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), default='Pending')
    duty_station_id = db.Column(db.Integer, db.ForeignKey('duty_stations.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    paid_at = db.Column(db.DateTime, nullable=True)
    duty_station = db.relationship('DutyStation', back_populates='bills', lazy=True)

class FoodFuelRecord(db.Model):
    __tablename__ = 'food_fuel_records'
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(20), nullable=False)
    description = db.Column(db.Text, nullable=True)
    quantity = db.Column(db.Float, nullable=False)
    cost = db.Column(db.Float, nullable=False)
    date = db.Column(db.Date, nullable=False)
    payee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True)
    payee_name = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    duty_station_id = db.Column(db.Integer, db.ForeignKey('duty_stations.id'), nullable=False)
    duty_station = db.relationship('DutyStation', back_populates='food_fuel_records', lazy=True)
    payee = db.relationship('Employee', back_populates='food_fuel_records', lazy=True)

class SecurityIncident(db.Model):
    __tablename__ = 'security_incidents'
    id = db.Column(db.Integer, primary_key=True)
    incident_type = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text, nullable=False)
    location = db.Column(db.String(100), nullable=True)
    reported_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), default='Open')
    resolved_date = db.Column(db.Date, nullable=True)
    duty_station_id = db.Column(db.Integer, db.ForeignKey('duty_stations.id'), nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    duty_station = db.relationship('DutyStation', back_populates='security_incidents', lazy=True)

class PettyCash(db.Model):
    __tablename__ = 'petty_cash'
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.Text, nullable=False)
    amount = db.Column(db.Float, nullable=False)
    request_date = db.Column(db.Date, nullable=False)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    employee_title = db.Column(db.String(100), nullable=True)
    reason = db.Column(db.Text, nullable=False)
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    approver_name = db.Column(db.String(100), nullable=True)
    status = db.Column(db.String(20), default='Pending')
    duty_station_id = db.Column(db.Integer, db.ForeignKey('duty_stations.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    employee = db.relationship('Employee', back_populates='petty_cash', lazy=True)
    approver = db.relationship('User', back_populates='petty_cash_approvals', lazy=True)
    duty_station = db.relationship('DutyStation', back_populates='petty_cash', lazy=True)

class ProjectFunding(db.Model):
    __tablename__ = 'project_funding'
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    funding_date = db.Column(db.Date, nullable=False)
    start_date = db.Column(db.Date, nullable=True)
    end_date = db.Column(db.Date, nullable=True)
    source = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    duty_station_id = db.Column(db.Integer, db.ForeignKey('duty_stations.id'), nullable=False)
    project = db.relationship('Project', back_populates='funding', lazy=True)
    duty_station = db.relationship('DutyStation', back_populates='project_funding', lazy=True)

class PropertyItem(db.Model):
    __tablename__ = 'property_items'
    id = db.Column(db.Integer, primary_key=True)
    item_code = db.Column(db.String(50), unique=True, nullable=False)
    item_type = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text, nullable=False)
    assigned_to = db.Column(db.String(100), nullable=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True)
    assigned_date = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(20), default='In Use')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    duty_station_id = db.Column(db.Integer, db.ForeignKey('duty_stations.id'), nullable=False)
    employee = db.relationship('Employee', back_populates='property_items', lazy=True)
    duty_station = db.relationship('DutyStation', back_populates='property_items', lazy=True)

class AdminLetter(db.Model):
    __tablename__ = 'admin_letters'
    id = db.Column(db.Integer, primary_key=True)
    letter_type = db.Column(db.String(20), nullable=False)
    recipient = db.Column(db.String(100), nullable=False)
    subject = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    file_path = db.Column(db.String(200), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    duty_station_id = db.Column(db.Integer, db.ForeignKey('duty_stations.id'), nullable=False)
    duty_station = db.relationship('DutyStation', back_populates='admin_letters', lazy=True)