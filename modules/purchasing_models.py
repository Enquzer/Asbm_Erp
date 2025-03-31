# modules/purchasing_models.py
from database import db
from modules.models import Product, DutyStation, User
from datetime import datetime

class Supplier(db.Model):
    __tablename__ = 'suppliers'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    contact_info = db.Column(db.String(200))

class PurchaseRequest(db.Model):
    __tablename__ = 'purchase_requests'
    id = db.Column(db.Integer, primary_key=True)
    request_code = db.Column(db.String(20), unique=True, nullable=False)
    dept_name = db.Column(db.String(50), nullable=False)
    duty_station_id = db.Column(db.Integer, db.ForeignKey('duty_stations.id'), nullable=False)
    requested_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    item_name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    unit_of_measure = db.Column(db.String(20), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    expected_delivery_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), default="Pending")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    requested_by = db.relationship('User', backref='purchase_requests')
    duty_station = db.relationship('DutyStation', backref='purchase_requests')
    procurement_orders = db.relationship('ProcurementOrder', backref='request', lazy=True)

class ProcurementOrder(db.Model):
    __tablename__ = 'procurement_orders'
    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(20), unique=True, nullable=False)
    request_id = db.Column(db.Integer, db.ForeignKey('purchase_requests.id'), nullable=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=True)
    quantity = db.Column(db.Integer, nullable=False)
    unit_of_measure = db.Column(db.String(20), nullable=False)
    unit_price = db.Column(db.Float, nullable=True)
    total_price = db.Column(db.Float, nullable=False, default=0.0)
    status = db.Column(db.String(20), default="Pending")
    cost_category = db.Column(db.String(50))
    duty_station_id = db.Column(db.Integer, db.ForeignKey('duty_stations.id'), nullable=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'), nullable=True)
    cost_type = db.Column(db.String(20))
    payment_status = db.Column(db.String(20), default="Unpaid")
    payment_amount = db.Column(db.Float, nullable=False, default=0.0)
    payment_date = db.Column(db.Date, nullable=True)
    description = db.Column(db.Text)
    registered_date = db.Column(db.DateTime, default=datetime.utcnow)
    product = db.relationship('Product', backref='procurement_orders')
    duty_station = db.relationship('DutyStation', backref='procurement_orders')
    supplier = db.relationship('Supplier', backref='procurement_orders')
    
class YearlyPurchasePlan(db.Model):
    __tablename__ = 'yearly_purchase_plans'
    id = db.Column(db.Integer, primary_key=True)
    year = db.Column(db.Integer, nullable=False)
    duty_station_id = db.Column(db.Integer, db.ForeignKey('duty_stations.id'), nullable=False)
    cost_category = db.Column(db.String(50), nullable=False)
    planned_cost = db.Column(db.Float, nullable=False)
    q1_cost = db.Column(db.Float, default=0.0)
    q2_cost = db.Column(db.Float, default=0.0)
    q3_cost = db.Column(db.Float, default=0.0)
    q4_cost = db.Column(db.Float, default=0.0)
    duty_station = db.relationship('DutyStation', backref='yearly_plans')