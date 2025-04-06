# main.py
import os
import time
from datetime import datetime, date, timedelta
import logging
from PIL import Image

import matplotlib
matplotlib.use('Agg')
from flask import Flask, render_template, redirect, url_for, send_file, jsonify
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect, generate_csrf
from flask_migrate import Migrate
from database import db
from modules.stock_models import StockCategory, StockItem, StockTransaction, StockBalance
from modules.hr import generate_pdf
from modules.models import User, DutyStation, Product, PurchaseOrder, Customer, Order, Sale, Employee, Overtime, Attendance, AnnualLeave, EmploymentLetter, Contract, Position, Project, Resource
from modules.purchasing_models import PurchaseRequest, ProcurementOrder, Supplier, YearlyPurchasePlan
from modules.production_models import Machine, ProductionConfig, ProductionRecord
from modules.admin_activities import admin_activities_bp

try:
    import pandas as pd
    import xlsxwriter
    import matplotlib.pyplot as plt
    import seaborn as sns
    import reportlab
except ImportError as e:
    logging.error(f"Missing required dependency: {str(e)}. Please install with 'pip install pandas xlsxwriter matplotlib seaborn reportlab'")
    raise

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder='templates', static_folder='static')

app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-here-change-me')
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'instance', 'asbm_erp.db') + '?timeout=10'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,
    'pool_timeout': 30,
}
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'images', 'uploads')
app.config['PRODUCT_UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'images', 'products')
app.config['LETTER_UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'uploads', 'letters')
app.config['CONTRACT_UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'uploads', 'contracts')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

for folder in [app.config['UPLOAD_FOLDER'], app.config['PRODUCT_UPLOAD_FOLDER'], app.config['LETTER_UPLOAD_FOLDER'], app.config['CONTRACT_UPLOAD_FOLDER']]:
    if not os.path.exists(folder):
        os.makedirs(folder)

placeholder_path = os.path.join(app.config['UPLOAD_FOLDER'], 'placeholder_user.jpg')
if not os.path.exists(placeholder_path):
    img = Image.new('RGB', (100, 100), color=(200, 200, 200))
    img.save(placeholder_path)

db.init_app(app)
csrf = CSRFProtect(app)
login_manager = LoginManager(app)
login_manager.login_view = 'user_management.login'
migrate = Migrate(app, db)

csrf.exempt('purchasing.search_suppliers')

logger.debug(f"Database URI: {app.config['SQLALCHEMY_DATABASE_URI']}")

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError

@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA busy_timeout = 10000")
    cursor.execute("PRAGMA journal_mode = WAL")
    cursor.close()

def import_blueprints():
    try:
        from modules.dashboard import dashboard_bp
        from modules.order import order_bp
        from modules.product import product_bp
        from modules.hr import hr_bp
        from modules.notifications import notifications_bp
        from modules.planning import planning_bp
        from modules.production import production_bp
        from modules.project import project_bp
        from modules.purchasing import purchasing_bp
        from modules.stock_management import stock_management_bp
        from modules.sales import sales_bp
        from modules.system_setup import system_setup_bp
        from modules.user_management import user_management_bp
        from modules.chat import chat_bp
        from modules.resources import resources_bp
        return [
            (dashboard_bp, '/dashboard'),
            (order_bp, '/order'),
            (product_bp, '/product'),
            (hr_bp, '/hr'),
            (notifications_bp, '/notifications'),
            (planning_bp, '/planning'),
            (production_bp, '/production'),
            (project_bp, '/project'),
            (purchasing_bp, '/purchasing'),
            (stock_management_bp, '/stock_management'),
            (sales_bp, '/sales'),
            (system_setup_bp, '/system_setup'),
            (user_management_bp, '/user_management'),
            (chat_bp, '/chat'),
            (resources_bp, '/resources')
        ]
    except ImportError as e:
        logger.error(f"Blueprint import failed: {str(e)}")
        raise

def register_blueprints():
    blueprints = import_blueprints()
    for bp, url_prefix in blueprints:
        app.register_blueprint(bp, url_prefix=url_prefix)
    app.register_blueprint(admin_activities_bp)

@app.route('/')
def index():
    return redirect(url_for('dashboard.dashboard'))

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

@app.errorhandler(404)
def not_found_error(error):
    logger.error(f"404 Error: {error}")
    try:
        return render_template('errors/404.html'), 404
    except Exception as e:
        logger.error(f"Error rendering 404 template: {str(e)}")
        return "<h1>404 Not Found</h1><p>The requested page does not exist.</p>", 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    logger.error(f"500 Error: {error}")
    try:
        return render_template('errors/500.html'), 500
    except Exception as e:
        logger.error(f"Error rendering 500 template: {str(e)}")
        return "<h1>500 Internal Server Error</h1><p>Something went wrong.</p>", 500

@app.context_processor
def inject_csrf_token():
    return {'csrf_token': generate_csrf, 'now': lambda: datetime.now().timestamp()}

def format_currency_filter(value):
    return f"ETB {value:,.2f}" if value is not None else "ETB 0.00"

def date_filter(value, format='%Y-%m-%d'):
    return value.strftime(format) if value else ''

app.jinja_env.filters['format_currency'] = format_currency_filter
app.jinja_env.filters['date'] = date_filter

from flask.json.provider import DefaultJSONProvider

class CustomJSONProvider(DefaultJSONProvider):
    def default(self, obj):
        try:
            return super().default(obj)
        except TypeError as e:
            logger.error(f"Serialization error for object {obj}: {str(e)}")
            raise

app.json_provider_class = CustomJSONProvider

def init_db():
    with app.app_context():
        max_retries = 5
        retry_delay = 2
        for attempt in range(max_retries):
            try:
                db.drop_all()
                db.create_all()
                logger.info("Database tables ensured successfully")
                break
            except OperationalError as e:
                if "database is locked" in str(e):
                    logger.warning(f"Database locked on attempt {attempt + 1}/{max_retries}. Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                else:
                    logger.error(f"Error initializing database: {str(e)}")
                    raise
        else:
            logger.error("Failed to initialize database after all retries due to persistent lock.")
            raise RuntimeError("Database initialization failed due to persistent lock.")

        admin_user = User.query.filter_by(username='admin').first()
        if admin_user:
            if not admin_user.check_password('admin'):
                admin_user.set_password('admin')
                db.session.commit()
                logger.info("Admin password reset to 'admin'.")
        else:
            admin_user = User(
                username='admin',
                role='Admin',
                permissions={
                    'dashboard': {'view': True, 'edit': True, 'delete': True},
                    'orders': {'view': True, 'edit': True, 'delete': True},
                    'products': {'view': True, 'edit': True, 'delete': True},
                    'customers': {'view': True, 'edit': True, 'delete': True},
                    'hr': {'view': True, 'edit': True, 'delete': True},
                    'notifications': {'view': True, 'edit': True, 'delete': True},
                    'planning': {'view': True, 'edit': True, 'delete': True},
                    'production': {'view': True, 'edit': True, 'delete': True},
                    'project': {'view': True, 'edit': True, 'delete': True},
                    'purchasing': {'view': True, 'edit': True, 'delete': True},
                    'stock_management': {'view': True, 'edit': True, 'delete': True},
                    'sales': {'view': True, 'edit': True, 'delete': True},
                    'system_setup': {'view': True, 'edit': True, 'delete': True},
                    'user_management': {'view': True, 'edit': True, 'delete': True},
                    'chat': {'view': True, 'edit': True, 'delete': True},
                    'admin_activities': {'view': True, 'edit': True, 'delete': True},
                    'resources': {'view': True, 'edit': True, 'delete': True}
                }
            )
            admin_user.set_password('admin')
            db.session.add(admin_user)
            db.session.commit()
            logger.info("Admin user created with username 'admin' and password 'admin'.")

        duty_stations = [
            DutyStation(id=1, name='Sendafa'),
            DutyStation(id=2, name='Kality'),
            DutyStation(id=3, name='Mojo'),
            DutyStation(id=4, name='Eba'),
            DutyStation(id=5, name='Addis Ababa')
        ]
        for ds in duty_stations:
            if not DutyStation.query.filter_by(id=ds.id).first():
                db.session.add(ds)
        db.session.commit()

        if not Employee.query.filter_by(name='John Doe').first():
            emp1 = Employee(
                name='John Doe',
                title='Manager',
                phone_number='0912345678',
                monthly_salary=5000.0,
                hire_date=datetime.strptime('2023-01-01', '%Y-%m-%d').date(),
                duty_station_id=1,
                birth_date=datetime.strptime('1980-01-01', '%Y-%m-%d').date(),
                gender='Male',
                department='IT',
                management_status='Active',
                job_grade='A',
                step=1,
                additional_benefits=500.0
            )
            db.session.add(emp1)
        if not Employee.query.filter_by(name='Jane Smith').first():
            emp2 = Employee(
                name='Jane Smith',
                title='Developer',
                phone_number='0987654321',
                monthly_salary=4000.0,
                hire_date=datetime.strptime('2023-02-01', '%Y-%m-%d').date(),
                duty_station_id=2,
                birth_date=datetime.strptime('1985-05-15', '%Y-%m-%d').date(),
                gender='Female',
                department='IT',
                management_status='Active',
                job_grade='B',
                step=2,
                additional_benefits=400.0
            )
            db.session.add(emp2)
        db.session.commit()
        logger.info("Dummy employees added: John Doe, Jane Smith")

        if not Customer.query.filter_by(email='customer@example.com').first():
            sample_customer = Customer(
                name='Sample Customer',
                email='customer@example.com',
                phone_number='1234567890',
                location_address='123 Sample St',
                product_types='Yarn, Garment',
                contact_details='Phone: 1234567890, Address: 123 Sample St',
                rating=4.5
            )
            db.session.add(sample_customer)
            db.session.commit()
            logger.info("Sample customer created")

        if not Product.query.filter_by(product_code='YRN001').first():
            sample_product = Product(
                name='Sample Yarn Product',
                description='A sample yarn product',
                product_code='YRN001',
                product_type='Yarn',
                selling_price=100.0,
                cost=80.0,
                supplier="Sample Supplier",
                batch_number="B001",
                sku="SKU-YRN001",
                stock_quantity=100
            )
            db.session.add(sample_product)
            db.session.commit()
            logger.info("Sample product created")

        if not Supplier.query.filter_by(name='Sample Supplier').first():
            sample_supplier = Supplier(
                name='Sample Supplier',
                contact_info='Phone: 123-456-7890'
            )
            db.session.add(sample_supplier)
            db.session.commit()
            logger.info("Sample supplier created")

        if not PurchaseOrder.query.filter_by(order_number='PO-PROD-001').first():
            sample_product = Product.query.filter_by(product_code='YRN001').first()
            if sample_product:
                sample_po = PurchaseOrder(
                    order_number='PO-PROD-001',
                    product_id=sample_product.id,
                    quantity=50,
                    order_date=datetime.now(),
                    status='Pending'
                )
                db.session.add(sample_po)
                db.session.commit()
                logger.info("Sample purchase order created: PO-PROD-001")

        if not PurchaseRequest.query.filter_by(request_code='PUR-PRO-001').first():
            admin_user = User.query.filter_by(username='admin').first()
            if admin_user:
                sample_request = PurchaseRequest(
                    request_code='PUR-PRO-001',
                    dept_name='Production',
                    duty_station_id=1,
                    requested_by_id=admin_user.id,
                    item_name='Cotton Yarn',
                    description='High-quality cotton yarn for spinning',
                    unit_of_measure='Kg',
                    quantity=500,
                    expected_delivery_date=datetime.now().date(),
                    status='Pending',
                    created_at=datetime.now()
                )
                db.session.add(sample_request)
                db.session.commit()
                logger.info("Sample purchase request created: PUR-PRO-001")

        if not ProcurementOrder.query.filter_by(order_number='PO-PRO-001').first():
            sample_product = Product.query.filter_by(product_code='YRN001').first()
            sample_request = PurchaseRequest.query.filter_by(request_code='PUR-PRO-001').first()
            sample_supplier = Supplier.query.filter_by(name='Sample Supplier').first()
            if sample_product and sample_request and sample_supplier:
                sample_po = ProcurementOrder(
                    order_number='PO-PRO-001',
                    request_id=sample_request.id,
                    product_id=sample_product.id,
                    quantity=500,
                    unit_of_measure='Kg',
                    unit_price=80.0,
                    total_price=40000.0,
                    status='Pending',
                    cost_category='Raw Material',
                    duty_station_id=1,
                    supplier_id=sample_supplier.id,
                    cost_type='Project Cost',
                    payment_status='Unpaid',
                    payment_amount=0.0,
                    registered_date=datetime.now()
                )
                db.session.add(sample_po)
                db.session.commit()
                logger.info("Sample procurement order created: PO-PRO-001")

        if not YearlyPurchasePlan.query.filter_by(year=2025, duty_station_id=1).first():
            sample_plan = YearlyPurchasePlan(
                year=2025,
                duty_station_id=1,
                cost_category='Raw Material',
                planned_cost=1000000.0,
                q1_cost=250000.0,
                q2_cost=250000.0,
                q3_cost=250000.0,
                q4_cost=250000.0
            )
            db.session.add(sample_plan)
            db.session.commit()
            logger.info("Sample yearly purchase plan created for Sendafa 2025")

        if not Machine.query.filter_by(name='Spinning Machine 1').first():
            sample_machine = Machine(
                name='Spinning Machine 1',
                duty_station_id=1,
                process_type='Spinning',
                installed_capacity=1000.0,
                efficiency_factor=0.8
            )
            db.session.add(sample_machine)
            db.session.commit()
            logger.info("Sample machine created: Spinning Machine 1")

        if not ProductionConfig.query.filter_by(duty_station_id=1).first():
            sample_config = ProductionConfig(
                duty_station_id=1,
                working_hours=8.0,
                working_days=25
            )
            db.session.add(sample_config)
            db.session.commit()
            logger.info("Sample production config created for Sendafa")

        if not Position.query.filter_by(title='Software Engineer').first():
            pos = Position(
                title='Software Engineer',
                description='Develop software solutions',
                department='IT',
                salary_range_min=4000,
                salary_range_max=6000,
                duty_station_id=1
            )
            db.session.add(pos)

        if not Overtime.query.first():
            ot = Overtime(employee_id=1, date=datetime.now().date(), hours=2.5, rate=1.5)
            db.session.add(ot)

        if not Attendance.query.first():
            att = Attendance(employee_id=1, date=datetime.now().date(), check_in=datetime.now(), status='Present')
            db.session.add(att)

        if not AnnualLeave.query.first():
            leave = AnnualLeave(employee_id=1, start_date=datetime.now().date(), end_date=(datetime.now() + timedelta(days=5)).date(), total_days=6)
            db.session.add(leave)

        if not EmploymentLetter.query.first():
            letter = EmploymentLetter(employee_id=1, letter_type='Offer', content='Dear Employee,\nWe are pleased to offer you a position...')
            db.session.add(letter)
            db.session.flush()
            file_path = os.path.join(app.config['LETTER_UPLOAD_FOLDER'], f"letter_{letter.id}.pdf")
            try:
                generate_pdf(letter.content, file_path)
                letter.file_path = file_path.replace(app.root_path, '').lstrip(os.sep)
            except Exception as e:
                logger.error(f"Failed to generate PDF for EmploymentLetter {letter.id}: {str(e)}")
                letter.file_path = None

        if not Contract.query.first():
            contract = Contract(employee_id=1, title='Employment Contract', content='This contract outlines...', start_date=datetime.now().date())
            db.session.add(contract)
            db.session.flush()
            file_path = os.path.join(app.config['CONTRACT_UPLOAD_FOLDER'], f"contract_{contract.id}.pdf")
            try:
                generate_pdf(contract.content, file_path)
                contract.file_path = file_path.replace(app.root_path, '').lstrip(os.sep)
            except Exception as e:
                logger.error(f"Failed to generate PDF for Contract {contract.id}: {str(e)}")
                contract.file_path = None

        if not ProductionRecord.query.first():
            sample_machine = Machine.query.filter_by(name='Spinning Machine 1').first()
            if sample_machine:
                sample_record = ProductionRecord(
                    machine_id=sample_machine.id,
                    period_type='Monthly',
                    start_date=datetime.now().date().replace(day=1),
                    end_date=datetime.now().date(),
                    actual_quantity=800.0,
                    uom='Kg',
                    utilized_capacity=80.0
                )
                db.session.add(sample_record)
                db.session.commit()
                logger.info("Sample production record created")

        if not Project.query.filter_by(name='Project Alpha').first():
            project1 = Project(
                name='Project Alpha',
                description='A sample project for testing',
                start_date=datetime.now().date(),
                end_date=(datetime.now() + timedelta(days=365)).date(),
                status='Active',
                duty_station_id=1
            )
            db.session.add(project1)
        if not Project.query.filter_by(name='Project Beta').first():
            project2 = Project(
                name='Project Beta',
                description='Another sample project for testing',
                start_date=datetime.now().date(),
                end_date=(datetime.now() + timedelta(days=180)).date(),
                status='Active',
                duty_station_id=2
            )
            db.session.add(project2)
        db.session.commit()
        logger.info("Sample projects added: Project Alpha, Project Beta")

        categories = [
            StockCategory(name='Raw Material', description='Cotton, Yarn, etc.'),
            StockCategory(name='Finished Goods', description='Yarn, Fabric, etc.'),
            StockCategory(name='Consumables', description='Stationery, Chemicals, etc.')
        ]
        for cat in categories:
            if not StockCategory.query.filter_by(name=cat.name).first():
                db.session.add(cat)
        db.session.commit()

if __name__ == '__main__':
    instance_dir = os.path.join(basedir, 'instance')
    if not os.path.exists(instance_dir):
        os.makedirs(instance_dir)
        logger.info(f"Created instance directory at: {instance_dir}")

    try:
        register_blueprints()
        init_db()
        logger.info("Application starting...")
        app.run(debug=True, host='0.0.0.0', port=8000)
    except Exception as e:
        logger.error(f"Failed to start application: {str(e)}")
        raise