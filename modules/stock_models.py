from database import db
from modules.models import DutyStation, Product
from modules.purchasing_models import ProcurementOrder
from datetime import datetime

class StockCategory(db.Model):
    __tablename__ = 'stock_categories'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)  # e.g., Raw Material, Finished Goods, Consumables
    description = db.Column(db.Text)

class StockItem(db.Model):
    __tablename__ = 'stock_items'
    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey('stock_categories.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    unit_of_measure = db.Column(db.String(20), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=True)  # Link to Product if applicable
    duty_station_id = db.Column(db.Integer, db.ForeignKey('duty_stations.id'), nullable=False)
    min_stock_level = db.Column(db.Float, default=0.0)
    category = db.relationship('StockCategory', backref='items')
    product = db.relationship('Product', backref='stock_items')
    duty_station = db.relationship('DutyStation', backref='stock_items')

class StockTransaction(db.Model):
    __tablename__ = 'stock_transactions'
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('stock_items.id'), nullable=False)
    transaction_type = db.Column(db.String(20), nullable=False)  # IN, OUT, ADJUST
    quantity = db.Column(db.Float, nullable=False)
    unit_price = db.Column(db.Float, nullable=False, default=0.0)
    total_value = db.Column(db.Float, nullable=False, default=0.0)
    procurement_order_id = db.Column(db.Integer, db.ForeignKey('procurement_orders.id'), nullable=True)
    production_record_id = db.Column(db.Integer, db.ForeignKey('production_records.id'), nullable=True)
    duty_station_id = db.Column(db.Integer, db.ForeignKey('duty_stations.id'), nullable=False)
    transaction_date = db.Column(db.DateTime, default=datetime.utcnow)
    item = db.relationship('StockItem', backref='transactions')
    procurement_order = db.relationship('ProcurementOrder', backref='stock_transactions')
    production_record = db.relationship('ProductionRecord', backref='stock_transactions')
    duty_station = db.relationship('DutyStation', backref='transactions')

class StockBalance(db.Model):
    __tablename__ = 'stock_balances'
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('stock_items.id'), nullable=False)
    duty_station_id = db.Column(db.Integer, db.ForeignKey('duty_stations.id'), nullable=False)
    period = db.Column(db.String(20), nullable=False)  # e.g., '2025-07'
    beginning_quantity = db.Column(db.Float, default=0.0)
    beginning_value = db.Column(db.Float, default=0.0)
    ending_quantity = db.Column(db.Float, default=0.0)
    ending_value = db.Column(db.Float, default=0.0)
    item = db.relationship('StockItem', backref='balances')
    duty_station = db.relationship('DutyStation', backref='balances')