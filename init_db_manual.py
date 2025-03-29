import os
from flask import Flask, render_template, redirect, url_for
from flask_login import LoginManager, current_user
from flask_wtf.csrf import CSRFProtect, generate_csrf
from flask_migrate import Migrate
from database import db
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
import logging
from sqlalchemy import event
from sqlalchemy.engine import Engine
from datetime import datetime, timedelta

app = Flask(__name__, template_folder='templates', static_folder='static')

app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-here-change-me')
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'instance', 'asbm_erp.db') + '?timeout=10'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'images', 'products')

db.init_app(app)
csrf = CSRFProtect(app)
login_manager = LoginManager(app)
login_manager.login_view = 'user_management.login'
migrate = Migrate(app, db)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

logger.debug(f"Database URI: {app.config['SQLALCHEMY_DATABASE_URI']}")

@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA busy_timeout = 10000")
    cursor.close()

def register_blueprints():
    from modules.models import (
        User, DutyStation, Product, ProductPlan, Customer, Order,
        ProductionPlan, ProductionActual, RevenuePlan, RevenueActual,
        Employee, Sale, PurchaseOrder, EmployeePeriod, PlanChangeLog
    )
    blueprints = [
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
        (chat_bp, '/chat')
    ]
    for bp, url_prefix in blueprints:
        app.register_blueprint(bp, url_prefix=url_prefix)

@app.route('/')
def index():
    return redirect(url_for('dashboard.dashboard'))

@login_manager.user_loader
def load_user(user_id):
    from modules.models import User
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
    return {'csrf_token': generate_csrf}

def format_currency_filter(value):
    return f"ETB {value:,.2f}" if value is not None else "ETB 0.00"

app.jinja_env.filters['format_currency'] = format_currency_filter

def init_db():
    with app.app_context():
        try:
            db.create_all()
            logger.info("Database tables created or verified successfully")
        except Exception as e:
            logger.error(f"Error creating database tables: {str(e)}")
            raise

        from modules.models import (
            User, DutyStation, Product, ProductPlan, Customer, Order,
            ProductionPlan, ProductionActual, RevenuePlan, RevenueActual,
            Employee, Sale, PurchaseOrder, EmployeePeriod, PlanChangeLog
        )

        admin_user = User.query.filter_by(username='admin').first()
        if not admin_user:
            admin_user = User(
                username='admin',
                role='Admin',
                permissions={
                    'dashboard': True, 'orders': True, 'products': True, 'hr': True,
                    'notifications': True, 'planning': True, 'production': True,
                    'project': True, 'purchasing': True, 'stock_management': True,
                    'sales': True, 'system_setup': True, 'user_management': True,
                    'chat': True, 'customers': True
                }
            )
            admin_user.set_password('admin')
            db.session.add(admin_user)
            db.session.commit()
            logger.info("Admin user created with username 'admin' and password 'admin'")
        else:
            if not admin_user.check_password('admin'):
                admin_user.set_password('admin')
                db.session.commit()
                logger.info("Admin password reset to 'admin'")
            else:
                logger.info("Admin user already exists with correct password")

        duty_stations = [
            DutyStation(id=1, name='Sendafa'),
            DutyStation(id=2, name='Kality'),
            DutyStation(id=3, name='Mojo'),
            DutyStation(id=4, name='Eba')
        ]
        for ds in duty_stations:
            if not DutyStation.query.filter_by(id=ds.id).first():
                db.session.add(ds)
        db.session.commit()

        if not Customer.query.first():
            sample_customer = Customer(
                name="Sample Customer",
                email="customer@example.com",
                product_types="Yarn, Garment",
                contact_details="Phone: 1234567890, Address: 123 Sample St",
                rating=4.5
            )
            db.session.add(sample_customer)
            db.session.commit()
            logger.info("Sample customer created")

        sample_customer = Customer.query.first()
        if not Product.query.filter_by(product_code='YRN001').first():
            sample_product = Product(
                name='Sample Yarn Product',
                description='A sample yarn product',
                product_code='YRN001',
                product_type='Yarn',
                selling_price=100.0,
                cost=80.0,
                customer_id=sample_customer.id if sample_customer else None,
                customer_name="Sample Customer",
                supplier="Sample Supplier",
                batch_number="B001",
                image_path="/static/images/products/sample_yarn.jpg",
                parameters={}
            )
            db.session.add(sample_product)
            db.session.commit()
            logger.info("Sample product created")

        if not Order.query.first():
            sample_customer = Customer.query.first()
            sample_product = Product.query.first()
            if sample_customer and sample_product:
                sample_order = Order(
                    order_number='ORD001',
                    customer_id=sample_customer.id,
                    product_id=sample_product.id,
                    quantity=50,
                    tax=750.0,
                    total=5750.0,
                    delivery_info="Deliver to 123 Sample St",
                    order_placed_date=datetime.utcnow().date(),
                    required_delivery_date=(datetime.utcnow() + timedelta(days=7)).date(),
                    total_value=5750.0
                )
                db.session.add(sample_order)
                db.session.commit()
                logger.info("Sample order created")

        if not Sale.query.first():
            sample_order = Order.query.first()
            if sample_order:
                sample_sale = Sale(
                    order_id=sample_order.id,
                    amount=5750.0,
                    sale_date=datetime.utcnow()
                )
                db.session.add(sample_sale)
                db.session.commit()
                logger.info("Sample sale created")

        if not PurchaseOrder.query.first():
            sample_product = Product.query.first()
            if sample_product:
                sample_po = PurchaseOrder(
                    order_number='PO001',
                    product_id=sample_product.id,
                    quantity=100,
                    status='Pending'
                )
                db.session.add(sample_po)
                db.session.commit()
                logger.info("Sample purchase order created")

        if not ProductionPlan.query.first():
            sample_plan = ProductionPlan(
                planned_quantity=1000,
                plan_date=datetime.utcnow()
            )
            db.session.add(sample_plan)
            db.session.commit()
            logger.info("Sample production plan created")

        if not ProductionActual.query.first():
            sample_actual = ProductionActual(
                actual_quantity=800,
                actual_date=datetime.utcnow()
            )
            db.session.add(sample_actual)
            db.session.commit()
            logger.info("Sample production actual created")

        if not RevenuePlan.query.first():
            sample_revenue_plan = RevenuePlan(
                planned_revenue=10000.0,
                plan_date=datetime.utcnow()
            )
            db.session.add(sample_revenue_plan)
            db.session.commit()
            logger.info("Sample revenue plan created")

        if not RevenueActual.query.first():
            sample_revenue_actual = RevenueActual(
                actual_revenue=8500.0,
                actual_date=datetime.utcnow()
            )
            db.session.add(sample_revenue_actual)
            db.session.commit()
            logger.info("Sample revenue actual created")

        if not Employee.query.first():
            sample_employee = Employee(
                name="Sample Employee",
                duty_station_id=1,
                title="Worker",
                gender="Male",
                department="Production",
                birth_date=datetime(1990, 1, 1).date(),
                hire_date=datetime.utcnow().date(),
                management_status="No",
                job_grade="A",
                step=1,
                basic_salary=5000.0,
                monthly_salary=5500.0,
                travel_allowance=500.0
            )
            db.session.add(sample_employee)
            db.session.commit()
            logger.info("Sample employee created")

        if not EmployeePeriod.query.first():
            sample_employee = Employee.query.first()
            if sample_employee:
                sample_period = EmployeePeriod(
                    employee_id=sample_employee.id,
                    start_date=datetime.utcnow().date(),
                    end_date=(datetime.utcnow() + timedelta(days=30)).date(),
                    worked_days=20
                )
                db.session.add(sample_period)
                db.session.commit()
                logger.info("Sample employee period created")

        if not ProductPlan.query.first():
            sample_product = Product.query.first()
            if sample_product:
                sample_product_plan = ProductPlan(
                    product_id=sample_product.id,
                    plan_type="Production",
                    start_date=datetime.utcnow().date(),
                    end_date=(datetime.utcnow() + timedelta(days=30)).date(),
                    planned_quantity=1000
                )
                db.session.add(sample_product_plan)
                db.session.commit()
                logger.info("Sample product plan created")

        if not PlanChangeLog.query.first():
            sample_product_plan = ProductPlan.query.first()
            if sample_product_plan:
                sample_change_log = PlanChangeLog(
                    plan_id=sample_product_plan.id,
                    user_id=admin_user.id,
                    old_value=1000,
                    new_value=1200,
                    change_description="Increased due to demand"
                )
                db.session.add(sample_change_log)
                db.session.commit()
                logger.info("Sample plan change log created")

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