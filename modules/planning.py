from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file, abort
from flask_login import login_required, current_user
from database import db
from modules.models import Product, ProductConfig, ProductPlan, Sale, User, Customer, SalesRecord
from datetime import datetime, timedelta
import pandas as pd
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
from reportlab.lib import colors
import logging
import sqlite3
from flask_wtf.csrf import CSRFProtect, validate_csrf

csrf = CSRFProtect()

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

planning_bp = Blueprint('planning', __name__)

def get_week_start(date):
    return date - timedelta(days=date.weekday())

def aggregate_plans(plans, period, is_service=False):
    periods = {'weekly': 'W', 'monthly': 'M', 'quarterly': 'Q', 'bi-annual': '6M', 'annual': 'Y'}
    grouped = {}
    totals = {'planned_quantity': 0, 'actual_quantity': 0, 'planned_value': 0, 'actual_value': 0}
    
    for plan in plans:
        product_config = plan.product.config
        supports_direct = product_config.supports_direct_sales if product_config else True
        supports_service = product_config.supports_service_sales if product_config else False
        if is_service and not supports_service:
            continue
        if not is_service and not supports_direct:
            continue
        
        start_date = datetime.combine(plan.start_date, datetime.min.time())
        if period == 'weekly':
            period_key = get_week_start(start_date).strftime('%Y-%m-%d')
        else:
            period_key = start_date.strftime(f'%Y-{periods[period]}')
        
        if period_key not in grouped:
            grouped[period_key] = {'plans': [], 'totals': {'planned_quantity': 0, 'actual_quantity': 0, 'planned_value': 0, 'actual_value': 0}}
        
        sales = Sale.query.filter(Sale.product_id == plan.product_id, Sale.sale_date.between(plan.start_date, plan.end_date)).all()
        actual_quantity = sum(sale.quantity for sale in sales)
        actual_value = sum(sale.total_price for sale in sales)
        
        customer_name = plan.product.customer.name if plan.product.customer else 'N/A'
        
        plan_data = {
            'plan': {
                'id': plan.id,
                'product_id': plan.product_id,
                'start_date': plan.start_date.strftime('%Y-%m-%d'),
                'end_date': plan.end_date.strftime('%Y-%m-%d'),
                'planned_quantity': float(plan.planned_quantity),
                'planned_value': float(plan.planned_value)
            },
            'customer_name': customer_name,
            'product_name': plan.product.name,
            'actual_quantity': float(actual_quantity),
            'quantity_percentage': float((actual_quantity / plan.planned_quantity * 100) if plan.planned_quantity > 0 else 0),
            'actual_value': float(actual_value),
            'value_percentage': float((actual_value / plan.planned_value * 100) if plan.planned_value > 0 else 0),
            'product_share': 0
        }
        
        grouped[period_key]['plans'].append(plan_data)
        grouped[period_key]['totals']['planned_quantity'] += float(plan.planned_quantity)
        grouped[period_key]['totals']['actual_quantity'] += float(actual_quantity)
        grouped[period_key]['totals']['planned_value'] += float(plan.planned_value)
        grouped[period_key]['totals']['actual_value'] += float(actual_value)
        
        totals['planned_quantity'] += float(plan.planned_quantity)
        totals['actual_quantity'] += float(actual_quantity)
        totals['planned_value'] += float(plan.planned_value)
        totals['actual_value'] += float(actual_value)

    for period_key, data in grouped.items():
        total_value = data['totals']['actual_value']
        for plan_data in data['plans']:
            plan_data['product_share'] = float((plan_data['actual_value'] / total_value * 100) if total_value > 0 else 0)
        data['totals']['quantity_percentage'] = float((data['totals']['actual_quantity'] / data['totals']['planned_quantity'] * 100) if data['totals']['planned_quantity'] > 0 else 0)
        data['totals']['value_percentage'] = float((data['totals']['actual_value'] / data['totals']['planned_value'] * 100) if data['totals']['planned_value'] > 0 else 0)

    totals['quantity_percentage'] = float((totals['actual_quantity'] / totals['planned_quantity'] * 100) if totals['planned_quantity'] > 0 else 0)
    totals['value_percentage'] = float((totals['actual_value'] / totals['planned_value'] * 100) if totals['planned_value'] > 0 else 0)
    return {'grouped': grouped, 'totals': totals}

def get_chart_data(plans, period):
    result = aggregate_plans(plans, period)
    grouped = result['grouped']
    labels = sorted(grouped.keys())
    sales = {}
    quantities = {}
    for period_key, data in grouped.items():
        for plan_data in data['plans']:
            product_name = plan_data['product_name']
            if product_name not in sales:
                sales[product_name] = []
                quantities[product_name] = []
            while len(sales[product_name]) < len(labels):
                sales[product_name].append(0)
                quantities[product_name].append(0)
            idx = labels.index(period_key)
            sales[product_name][idx] = plan_data['actual_value']
            quantities[product_name][idx] = plan_data['actual_quantity']
    return {'labels': labels, 'sales': sales, 'quantities': quantities}

@planning_bp.route('/planning')
@login_required
def planning():
    if not (current_user.is_admin() or 'planning' in current_user.permissions and current_user.permissions['planning'].get('view', False)):
        flash('You do not have permission to access planning!', 'danger')
        return redirect(url_for('dashboard.dashboard'))

    plans = ProductPlan.query.join(Product).outerjoin(ProductConfig, Product.id == ProductConfig.product_id).all()
    products = Product.query.all()
    date_range = [datetime.today().date()]

    weekly_data = aggregate_plans(plans, 'weekly')
    monthly_data = aggregate_plans(plans, 'monthly')
    quarterly_data = aggregate_plans(plans, 'quarterly')
    bi_annual_data = aggregate_plans(plans, 'bi-annual')
    annual_data = aggregate_plans(plans, 'annual')
    service_data = aggregate_plans(plans, 'annual', is_service=True)

    sales_data = {
        'weekly': weekly_data['totals'],
        'monthly': monthly_data['totals'],
        'quarterly': quarterly_data['totals'],
        'bi_annual': bi_annual_data['totals'],
        'annual': annual_data['totals'],
        'service': service_data['totals'],
        'summary': {
            'direct': {
                'planned_quantity': float(sum(p.planned_quantity for p in plans if not p.product.config or p.product.config.supports_direct_sales)),
                'actual_quantity': float(sum(sum(s.quantity for s in Sale.query.filter_by(product_id=p.product_id).all()) for p in plans if not p.product.config or p.product.config.supports_direct_sales)),
                'planned_value': float(sum(p.planned_value for p in plans if not p.product.config or p.product.config.supports_direct_sales)),
                'actual_value': float(sum(sum(s.total_price for s in Sale.query.filter_by(product_id=p.product_id).all()) for p in plans if not p.product.config or p.product.config.supports_direct_sales)),
                'quantity_percentage': 0,
                'value_percentage': 0
            },
            'service': {
                'planned_quantity': float(sum(p.planned_quantity for p in plans if p.product.config and p.product.config.supports_service_sales)),
                'actual_quantity': float(sum(sum(s.quantity for s in Sale.query.filter_by(product_id=p.product_id).all()) for p in plans if p.product.config and p.product.config.supports_service_sales)),
                'planned_value': float(sum(p.planned_value for p in plans if p.product.config and p.product.config.supports_service_sales)),
                'actual_value': float(sum(sum(s.total_price for s in Sale.query.filter_by(product_id=p.product_id).all()) for p in plans if p.product.config and p.product.config.supports_service_sales)),
                'quantity_percentage': 0,
                'value_percentage': 0
            }
        }
    }
    for cat in ['direct', 'service']:
        sales_data['summary'][cat]['quantity_percentage'] = float((sales_data['summary'][cat]['actual_quantity'] / sales_data['summary'][cat]['planned_quantity'] * 100) if sales_data['summary'][cat]['planned_quantity'] > 0 else 0)
        sales_data['summary'][cat]['value_percentage'] = float((sales_data['summary'][cat]['actual_value'] / sales_data['summary'][cat]['planned_value'] * 100) if sales_data['summary'][cat]['planned_value'] > 0 else 0)

    sales_data['weekly']['plans'] = weekly_data['grouped'].get(next(iter(weekly_data['grouped']), None), {}).get('plans', [])
    sales_data['monthly']['plans'] = monthly_data['grouped'].get(next(iter(monthly_data['grouped']), None), {}).get('plans', [])
    sales_data['quarterly']['plans'] = quarterly_data['grouped'].get(next(iter(quarterly_data['grouped']), None), {}).get('plans', [])
    sales_data['bi_annual']['plans'] = bi_annual_data['grouped'].get(next(iter(bi_annual_data['grouped']), None), {}).get('plans', [])
    sales_data['annual']['plans'] = annual_data['grouped'].get(next(iter(annual_data['grouped']), None), {}).get('plans', [])
    sales_data['service']['plans'] = service_data['grouped'].get(next(iter(service_data['grouped']), None), {}).get('plans', [])

    chart_data = {
        'weekly': get_chart_data(plans, 'weekly'),
        'monthly': get_chart_data(plans, 'monthly'),
        'quarterly': get_chart_data(plans, 'quarterly'),
        'bi_annual': get_chart_data(plans, 'bi-annual'),
        'annual': get_chart_data(plans, 'annual'),
        'service': get_chart_data([p for p in plans if p.product.config and p.product.config.supports_service_sales], 'annual')
    }

    pareto_data = sorted([(p.product.name, sum(s.total_price for s in Sale.query.filter_by(product_id=p.product_id).all())) for p in plans], key=lambda x: x[1], reverse=True)
    pareto_labels = [x[0] for x in pareto_data]
    pareto_values = [float(x[1]) for x in pareto_data]
    total = sum(pareto_values)
    pareto_cumulative = [float(sum(pareto_values[:i+1]) / total * 100) for i in range(len(pareto_values))] if total > 0 else [0] * len(pareto_values)

    comparison_data = {p.name: {'this_month': 0, 'last_month': 0, 'last_year': 0} for p in products}

    return render_template('planning.html', products=products, date_range=date_range, sales_data=sales_data, chart_data=chart_data, pareto_labels=pareto_labels, pareto_values=pareto_values, pareto_cumulative=pareto_cumulative, comparison_data=comparison_data, quantity_uom='Units', value_uom='ETB')

@planning_bp.route('/get_products')
@login_required
def get_products():
    try:
        products = Product.query.outerjoin(ProductConfig, Product.id == ProductConfig.product_id).all()
        logger.debug(f"Fetched {len(products)} products from database")

        product_data = [
            {
                'id': product.id,
                'name': product.name,
                'product_type': product.product_type,
                'customer_name': product.customer.name if product.customer else product.customer_name if product.customer_name else 'N/A',
                'selling_price': float(product.selling_price),
                'supports_direct_sales': product.config.supports_direct_sales if product.config else True,
                'supports_service_sales': product.config.supports_service_sales if product.config else False
            }
            for product in products
        ]
        return jsonify(product_data)
    except Exception as e:
        logger.error(f"Error fetching products: {str(e)}")
        return jsonify({'error': f'Failed to load products: {str(e)}'}), 500

@planning_bp.route('/planning/create_plan', methods=['POST'])
@login_required
def create_plan():
    if not (current_user.is_admin() or 'planning' in current_user.permissions and current_user.permissions['planning'].get('edit', False)):
        flash('You do not have permission to create plans!', 'danger')
        return redirect(url_for('dashboard.dashboard'))

    try:
        validate_csrf(request.form.get('csrf_token'))
    except:
        logger.error("CSRF token validation failed")
        abort(400, description="Invalid CSRF token")

    start_date = datetime.strptime(request.form['start_date'], '%Y-%m-%d').date()
    end_date = datetime.strptime(request.form['end_date'], '%Y-%m-%d').date()
    product_ids = request.form.getlist('product_ids[]')
    sales_types = request.form.getlist('sales_types[]')

    try:
        for i, product_id in enumerate(product_ids):
            product = Product.query.get_or_404(product_id)
            row_id = request.form.getlist('product_ids[]')[i]
            total_quantity = 0
            total_value = 0
            
            for date_str in pd.date_range(start_date, end_date).strftime('%Y-%m-%d'):
                qty_key = f"quantities[{row_id}][{date_str}]"
                if qty_key in request.form:
                    qty = float(request.form[qty_key])
                    total_quantity += qty
                    total_value += qty * product.selling_price
            
            if total_quantity > 0:
                plan_type = sales_types[i] if i < len(sales_types) else 'production'
                new_plan = ProductPlan(
                    product_id=product_id,
                    plan_type=plan_type,
                    start_date=start_date,
                    end_date=end_date,
                    planned_quantity=total_quantity,
                    planned_value=total_value,
                    actual_quantity=0,
                    actual_value=0
                )
                
                sales_record = SalesRecord(
                    product_id=product_id,
                    quantity=total_quantity,
                    value=total_value,
                    sale_date=start_date
                )
                
                db.session.add(new_plan)
                db.session.add(sales_record)
        
        db.session.commit()
        flash('Plan created successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating plan: {str(e)}")
        flash(f'Error creating plan: {str(e)}', 'danger')
    return redirect(url_for('planning.planning'))

@planning_bp.route('/planning/update_plan/<int:plan_id>', methods=['POST'])
@login_required
def update_plan(plan_id):
    if not (current_user.is_admin() or 'planning' in current_user.permissions and current_user.permissions['planning'].get('edit', False)):
        flash('You do not have permission to update plans!', 'danger')
        return redirect(url_for('dashboard.dashboard'))

    try:
        validate_csrf(request.form.get('csrf_token'))
    except:
        logger.error("CSRF token validation failed")
        abort(400, description="Invalid CSRF token")

    plan = ProductPlan.query.get_or_404(plan_id)
    try:
        plan.planned_quantity = float(request.form['planned_quantity'])
        plan.planned_value = float(request.form['planned_value'])
        db.session.commit()
        flash('Plan updated successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating plan: {str(e)}")
        flash(f'Error updating plan: {str(e)}', 'danger')
    return redirect(url_for('planning.planning'))

@planning_bp.route('/planning/delete_plan/<int:plan_id>', methods=['POST'])
@login_required
def delete_plan(plan_id):
    if not (current_user.is_admin() or 'planning' in current_user.permissions and current_user.permissions['planning'].get('delete', False)):
        flash('You do not have permission to delete plans!', 'danger')
        return redirect(url_for('dashboard.dashboard'))

    try:
        validate_csrf(request.form.get('csrf_token'))
    except:
        logger.error("CSRF token validation failed")
        abort(400, description="Invalid CSRF token")

    plan = ProductPlan.query.get_or_404(plan_id)
    try:
        db.session.delete(plan)
        db.session.commit()
        flash('Plan deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting plan: {str(e)}")
        flash(f'Error deleting plan: {str(e)}', 'danger')
    return redirect(url_for('planning.planning'))

@planning_bp.route('/planning/export_excel/<period>')
@login_required
def export_excel(period):
    plans = ProductPlan.query.join(Product).outerjoin(ProductConfig, Product.id == ProductConfig.product_id).all()
    data = aggregate_plans(plans, period) if period != 'service' else aggregate_plans(plans, 'annual', is_service=True)
    sales_data = planning().get('sales_data')['summary'] if period == 'summary' else data['totals']
    grouped_data = data['grouped']

    if period == 'summary':
        data = [
            ['Category', 'Planned Quantity', 'Actual Quantity', 'Quantity %', 'Planned Value', 'Actual Value', 'Value %'],
            ['Direct Sales', sales_data['direct']['planned_quantity'], sales_data['direct']['actual_quantity'], sales_data['direct']['quantity_percentage'], sales_data['direct']['planned_value'], sales_data['direct']['actual_value'], sales_data['direct']['value_percentage']],
            ['Service Sales', sales_data['service']['planned_quantity'], sales_data['service']['actual_quantity'], sales_data['service']['quantity_percentage'], sales_data['service']['planned_value'], sales_data['service']['actual_value'], sales_data['service']['value_percentage']]
        ]
    else:
        data = [['Customer', 'Product', 'Start Date', 'End Date', 'Planned Quantity', 'Actual Quantity', 'Quantity %', 'Planned Value', 'Actual Value', 'Value %', 'Product Share %']]
        for period_key, period_data in grouped_data.items():
            for plan_data in period_data['plans']:
                data.append([
                    plan_data['customer_name'], plan_data['product_name'], plan_data['plan']['start_date'], plan_data['plan']['end_date'],
                    plan_data['plan']['planned_quantity'], plan_data['actual_quantity'], plan_data['quantity_percentage'],
                    plan_data['plan']['planned_value'], plan_data['actual_value'], plan_data['value_percentage'], plan_data['product_share']
                ])
            data.append(['Total', '', '', '', period_data['totals']['planned_quantity'], period_data['totals']['actual_quantity'], period_data['totals']['quantity_percentage'], period_data['totals']['planned_value'], period_data['totals']['actual_value'], period_data['totals']['value_percentage'], 100])

    df = pd.DataFrame(data[1:], columns=data[0])
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name=f'{period.capitalize()} Plans')
    output.seek(0)
    return send_file(output, download_name=f'{period}_plans.xlsx', as_attachment=True)

@planning_bp.route('/planning/export_pdf/<period>')
@login_required
def export_pdf(period):
    plans = ProductPlan.query.join(Product).outerjoin(ProductConfig, Product.id == ProductConfig.product_id).all()
    data = aggregate_plans(plans, period) if period != 'service' else aggregate_plans(plans, 'annual', is_service=True)
    sales_data = planning().get('sales_data')['summary'] if period == 'summary' else data['totals']
    grouped_data = data['grouped']

    if period == 'summary':
        data = [
            ['Category', 'Planned Quantity', 'Actual Quantity', 'Quantity %', 'Planned Value', 'Actual Value', 'Value %'],
            ['Direct Sales', f"{sales_data['direct']['planned_quantity']:.2f}", f"{sales_data['direct']['actual_quantity']:.2f}", f"{sales_data['direct']['quantity_percentage']:.2f}%", f"{sales_data['direct']['planned_value']:.2f}", f"{sales_data['direct']['actual_value']:.2f}", f"{sales_data['direct']['value_percentage']:.2f}%"],
            ['Service Sales', f"{sales_data['service']['planned_quantity']:.2f}", f"{sales_data['service']['actual_quantity']:.2f}", f"{sales_data['service']['quantity_percentage']:.2f}%", f"{sales_data['service']['planned_value']:.2f}", f"{sales_data['service']['actual_value']:.2f}", f"{sales_data['service']['value_percentage']:.2f}%"]
        ]
    else:
        data = [['Customer', 'Product', 'Start Date', 'End Date', 'Planned Quantity', 'Actual Quantity', 'Quantity %', 'Planned Value', 'Actual Value', 'Value %', 'Product Share %']]
        for period_key, period_data in grouped_data.items():
            for plan_data in period_data['plans']:
                data.append([
                    plan_data['customer_name'], plan_data['product_name'], plan_data['plan']['start_date'], plan_data['plan']['end_date'],
                    f"{plan_data['plan']['planned_quantity']:.2f}", f"{plan_data['actual_quantity']:.2f}", f"{plan_data['quantity_percentage']:.2f}%",
                    f"{plan_data['plan']['planned_value']:.2f}", f"{plan_data['actual_value']:.2f}", f"{plan_data['value_percentage']:.2f}%", f"{plan_data['product_share']:.2f}%"
                ])
            data.append(['Total', '', '', '', f"{period_data['totals']['planned_quantity']:.2f}", f"{period_data['totals']['actual_quantity']:.2f}", f"{period_data['totals']['quantity_percentage']:.2f}%", f"{period_data['totals']['planned_value']:.2f}", f"{period_data['totals']['actual_value']:.2f}", f"{period_data['totals']['value_percentage']:.2f}%", '100%'])

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    table = Table(data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    doc.build([table])
    buffer.seek(0)
    return send_file(buffer, download_name=f'{period}_plans.pdf', as_attachment=True)