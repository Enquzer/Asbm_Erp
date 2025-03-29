from database import db  # Import db from the root database.py

class Machine(db.Model):
    __tablename__ = 'machines'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    duty_station_id = db.Column(db.Integer, nullable=False)
    process_type = db.Column(db.String(50), nullable=False)
    installed_capacity = db.Column(db.Float, nullable=False)
    efficiency_factor = db.Column(db.Float, default=0.8)
    manual_capacity = db.Column(db.Float, nullable=True)

class ProductionConfig(db.Model):
    __tablename__ = 'production_configs'
    id = db.Column(db.Integer, primary_key=True)
    duty_station_id = db.Column(db.Integer, nullable=False)
    working_hours = db.Column(db.Float, default=8.0)
    working_days = db.Column(db.Integer, default=25)

class ProductionRecord(db.Model):
    __tablename__ = 'production_records'
    id = db.Column(db.Integer, primary_key=True)
    machine_id = db.Column(db.Integer, nullable=False)
    period_type = db.Column(db.String(50), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    actual_quantity = db.Column(db.Float, nullable=False)
    uom = db.Column(db.String(10), nullable=False)
    utilized_capacity = db.Column(db.Float, nullable=False)