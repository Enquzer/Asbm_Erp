from flask import Blueprint, render_template, jsonify
from flask_login import login_required
from database import db
from modules.models import Customer, Order, ProductionPlan, ProductionActual, RevenuePlan, RevenueActual, DutyStation, Employee, Product, Sale
from datetime import datetime
import logging

# Define the Blueprint first
dashboard_bp = Blueprint('dashboard', __name__)

# Logging setup
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

@dashboard_bp.route('/')
@login_required
def dashboard():
    try:
        num_customers = Customer.query.count()
        num_orders = Order.query.count()
        planned_production = db.session.query(db.func.sum(ProductionPlan.planned_quantity)).scalar() or 0
        actual_production = db.session.query(db.func.sum(ProductionActual.actual_quantity)).scalar() or 0
        planned_revenue = db.session.query(db.func.sum(RevenuePlan.planned_revenue)).scalar() or 0.0
        actual_revenue = db.session.query(db.func.sum(RevenueActual.actual_revenue)).scalar() or 0.0
        current_month = datetime.now().month
        current_year = datetime.now().year
        last_month = current_month - 1 if current_month > 1 else 12
        last_year = current_year if current_month > 1 else current_year - 1

        current_month_revenue = db.session.query(db.func.sum(Sale.amount)).filter(
            db.extract('month', Sale.sale_date) == current_month,
            db.extract('year', Sale.sale_date) == current_year
        ).scalar() or 0.0

        last_month_revenue = db.session.query(db.func.sum(Sale.amount)).filter(
            db.extract('month', Sale.sale_date) == last_month,
            db.extract('year', Sale.sale_date) == last_year
        ).scalar() or 0.0

        current_year_revenue = db.session.query(db.func.sum(Sale.amount)).filter(
            db.extract('year', Sale.sale_date) == current_year
        ).scalar() or 0.0

        last_year_revenue = db.session.query(db.func.sum(Sale.amount)).filter(
            db.extract('year', Sale.sale_date) == current_year - 1
        ).scalar() or 0.0

        customer_month_diff = 0.0
        order_month_diff = 0.0
        revenue_month_diff = 0.0
        revenue_year_diff = 0.0

        top_product = Product.query.join(Order).join(Sale).group_by(Product.id).order_by(db.func.sum(Sale.amount).desc()).first()
        if top_product:
            top_product.total_revenue = db.session.query(db.func.sum(Sale.amount)).filter(Sale.order.has(product_id=top_product.id)).scalar() or 0.0
            top_product.total_quantity = db.session.query(db.func.sum(Order.quantity)).filter(Order.product_id == top_product.id).scalar() or 0
        else:
            top_product = None

        duty_station_counts = dict(db.session.query(DutyStation.name, db.func.count(Employee.id)).join(Employee).group_by(DutyStation.name).all())

        logger.info("Dashboard data loaded successfully")
        return render_template('dashboard.html',
                               num_customers=num_customers,
                               customer_month_diff=customer_month_diff,
                               num_orders=num_orders,
                               order_month_diff=order_month_diff,
                               planned_production=planned_production,
                               actual_production=actual_production,
                               planned_revenue=planned_revenue,
                               actual_revenue=actual_revenue,
                               current_month_revenue=current_month_revenue,
                               last_month_revenue=last_month_revenue,
                               revenue_month_diff=revenue_month_diff,
                               current_year_revenue=current_year_revenue,
                               last_year_revenue=last_year_revenue,
                               revenue_year_diff=revenue_year_diff,
                               top_product=top_product,
                               duty_station_counts=duty_station_counts)
    except Exception as e:
        logger.error(f"Error in dashboard route: {str(e)}")
        return render_template('error.html', error=str(e)), 500

# AJAX endpoint for dynamic updates
@dashboard_bp.route('/dashboard_data', methods=['GET'])
@login_required
def dashboard_data():
    try:
        num_customers = Customer.query.count()
        num_orders = Order.query.count()
        planned_production = db.session.query(db.func.sum(ProductionPlan.planned_quantity)).scalar() or 0
        actual_production = db.session.query(db.func.sum(ProductionActual.actual_quantity)).scalar() or 0
        planned_revenue = db.session.query(db.func.sum(RevenuePlan.planned_revenue)).scalar() or 0.0
        actual_revenue = db.session.query(db.func.sum(RevenueActual.actual_revenue)).scalar() or 0.0
        current_month = datetime.now().month
        current_year = datetime.now().year
        last_month = current_month - 1 if current_month > 1 else 12
        last_year = current_year if current_month > 1 else current_year - 1

        current_month_revenue = db.session.query(db.func.sum(Sale.amount)).filter(
            db.extract('month', Sale.sale_date) == current_month,
            db.extract('year', Sale.sale_date) == current_year
        ).scalar() or 0.0

        last_month_revenue = db.session.query(db.func.sum(Sale.amount)).filter(
            db.extract('month', Sale.sale_date) == last_month,
            db.extract('year', Sale.sale_date) == last_year
        ).scalar() or 0.0

        current_year_revenue = db.session.query(db.func.sum(Sale.amount)).filter(
            db.extract('year', Sale.sale_date) == current_year
        ).scalar() or 0.0

        last_year_revenue = db.session.query(db.func.sum(Sale.amount)).filter(
            db.extract('year', Sale.sale_date) == current_year - 1
        ).scalar() or 0.0

        top_product = Product.query.join(Order).join(Sale).group_by(Product.id).order_by(db.func.sum(Sale.amount).desc()).first()
        top_product_data = {
            'name': top_product.name if top_product else 'N/A',
            'total_revenue': top_product.total_revenue if top_product else 0.0,
            'total_quantity': top_product.total_quantity if top_product else 0
        } if top_product else {'name': 'N/A', 'total_revenue': 0.0, 'total_quantity': 0}

        duty_station_counts = dict(db.session.query(DutyStation.name, db.func.count(Employee.id)).join(Employee).group_by(DutyStation.name).all())

        data = {
            'num_customers': num_customers,
            'num_orders': num_orders,
            'planned_production': planned_production,
            'actual_production': actual_production,
            'planned_revenue': planned_revenue,
            'actual_revenue': actual_revenue,
            'current_month_revenue': current_month_revenue,
            'last_month_revenue': last_month_revenue,
            'current_year_revenue': current_year_revenue,
            'last_year_revenue': last_year_revenue,
            'top_product': top_product_data,
            'duty_station_counts': duty_station_counts
        }
        return jsonify(data)
    except Exception as e:
        logger.error(f"Error in dashboard_data route: {str(e)}")
        return jsonify({'error': str(e)}), 500