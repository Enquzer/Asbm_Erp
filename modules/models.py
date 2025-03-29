from database import db
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import logging

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class Customer(db.Model):
    __tablename__ = 'customers'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone_number = db.Column(db.String(20), nullable=True)
    location_address = db.Column(db.String(200), nullable=True)
    product_types = db.Column(db.String(200))
    rating = db.Column(db.Float, default=0.0)  # Calculated rating based on orders
    contact_details = db.Column(db.Text, nullable=True)  # Added for your template
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    orders = db.relationship('Order', backref='customer', lazy=True)
    products = db.relationship('Product', backref='customer', lazy=True)

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
    # Relationships
    plans = db.relationship('ProductPlan', backref='product', lazy=True)
    purchase_orders = db.relationship('PurchaseOrder', backref='product', lazy=True)
    orders = db.relationship('Order', backref='product', lazy=True)
    sales_records = db.relationship('SalesRecord', backref='product', lazy=True)
    sales = db.relationship('Sale', backref='product', lazy=True)
    config = db.relationship('ProductConfig', backref='product', uselist=False, lazy=True)
    prices = db.relationship('ProductPrice', backref='product', lazy=True)

class ProductConfig(db.Model):
    __tablename__ = 'product_configs'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    supports_direct_sales = db.Column(db.Boolean, default=True)
    supports_service_sales = db.Column(db.Boolean, default=False)
    uom = db.Column(db.String(20), nullable=False)  # e.g., 'kg', 'meter'

class ProductPrice(db.Model):
    __tablename__ = 'product_prices'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    price = db.Column(db.Float, nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=True)  # Null means valid until a new price is set

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
    changes = db.relationship('PlanChangeLog', backref='plan', lazy=True)

class SalesRecord(db.Model):
    __tablename__ = 'sales_records'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity = db.Column(db.Float, nullable=False)  # In kg
    value = db.Column(db.Float, nullable=False)  # In ETB
    sale_date = db.Column(db.Date, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class PlanChangeLog(db.Model):
    __tablename__ = 'plan_change_logs'
    id = db.Column(db.Integer, primary_key=True)
    plan_id = db.Column(db.Integer, db.ForeignKey('product_plans.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    old_value = db.Column(db.Float)
    new_value = db.Column(db.Float)
    change_description = db.Column(db.Text)
    change_date = db.Column(db.DateTime, default=datetime.utcnow)

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
    sales = db.relationship('Sale', backref='order', lazy=True)

class Sale(db.Model):
    __tablename__ = 'sales'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=True)
    sale_date = db.Column(db.Date, nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    total_price = db.Column(db.Float, nullable=False)
    sale_type = db.Column(db.String(20), nullable=False)  # 'Direct' or 'Service'
    amount = db.Column(db.Float, nullable=False)

class PurchaseOrder(db.Model):
    __tablename__ = 'purchase_orders'
    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(20), unique=True, nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    order_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    status = db.Column(db.String(20), nullable=False, default='Pending')

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

class DutyStation(db.Model):
    __tablename__ = 'duty_stations'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    employees = db.relationship('Employee', backref='duty_station', lazy=True)

class Employee(db.Model):
    __tablename__ = 'employees'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    address_woreda = db.Column(db.String(100))
    address_kifle_ketema = db.Column(db.String(100))
    phone_number = db.Column(db.String(20))
    emergency_contact_name = db.Column(db.String(100))
    emergency_contact_phone = db.Column(db.String(20))
    photo_path = db.Column(db.String(200))
    cv_path = db.Column(db.String(200))
    manager_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True)
    location = db.Column(db.String(100))
    internal_notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    duty_station_id = db.Column(db.Integer, db.ForeignKey('duty_stations.id'), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    gender = db.Column(db.String(10), nullable=False)
    department = db.Column(db.String(100), nullable=False)
    birth_date = db.Column(db.Date, nullable=False)
    hire_date = db.Column(db.Date, nullable=False)
    contract_end_date = db.Column(db.Date, nullable=True)
    seniority = db.Column(db.Integer, nullable=True)
    management_status = db.Column(db.String(10), nullable=False)
    job_grade = db.Column(db.String(20), nullable=False)
    step = db.Column(db.Integer, nullable=False)
    basic_salary = db.Column(db.Float, nullable=False, default=0.0)
    monthly_salary = db.Column(db.Float, nullable=False, default=0.0)
    additional_benefits = db.Column(db.Float, nullable=True, default=0.0)
    travel_allowance = db.Column(db.Float, nullable=True, default=0.0)
    other_allowance = db.Column(db.Float, nullable=True, default=0.0)
    non_taxable_allowance = db.Column(db.Float, nullable=True, default=0.0)
    other_deduction = db.Column(db.Float, nullable=True, default=0.0)
    lunch_deduction_employee = db.Column(db.Float, nullable=True, default=0.0)
    lunch_deduction_court = db.Column(db.Float, nullable=True, default=0.0)
    periods = db.relationship('EmployeePeriod', backref='employee', lazy=True)
    manager = db.relationship('Employee', remote_side=[id], backref='subordinates')

class EmployeePeriod(db.Model):
    __tablename__ = 'employee_periods'
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    worked_days = db.Column(db.Integer, nullable=False, default=0)

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(50), nullable=False)
    permissions = db.Column(db.JSON, default=lambda: {'dashboard': {'view': True}})
    profile_picture = db.Column(db.String(100), default='placeholder_user.jpg')
    plan_changes = db.relationship('PlanChangeLog', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def has_permission(self, module, action='view'):
        return self.is_admin() or (self.permissions.get(module, {}).get(action, False))

    def is_admin(self):
        return self.role.lower() == 'admin'