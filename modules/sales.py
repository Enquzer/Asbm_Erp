from flask import Blueprint, render_template, request, redirect, url_for, send_file, flash
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from modules.models import Product, Sale, ProductConfig, ProductPrice, ProductPlan
from database import db
import pandas as pd
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from flask_wtf.csrf import CSRFProtect

sales_bp = Blueprint('sales', __name__, template_folder='templates')
csrf = CSRFProtect()

def get_product_price(product_id, sale_date):
    price = ProductPrice.query.filter(
        ProductPrice.product_id == product_id,
        ProductPrice.start_date <= sale_date,
        (ProductPrice.end_date >= sale_date) | (ProductPrice.end_date.is_(None))
    ).order_by(ProductPrice.start_date.desc()).first()
    return price.price if price else 0

def get_days_in_month(year, month):
    if month == 2:
        if (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0):
            return 29
        return 28
    return [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1]

@sales_bp.route('/sales', methods=['GET', 'POST'])
@login_required
def sales():
    if not current_user.has_permission('sales'):
        flash('You do not have permission to access sales.', 'danger')
        return redirect(url_for('index'))

    products = Product.query.all()

    if request.method == 'POST':
        try:
            product_id = request.form.get('product_id')
            sale_date = request.form.get('sale_date')
            quantity = float(request.form.get('quantity'))
            sale_type = request.form.get('sale_type')

            product_config = ProductConfig.query.filter_by(product_id=product_id).first()
            if not product_config:
                flash('Product configuration not found. Please set up the product in System Setup.', 'danger')
                return redirect(url_for('sales.sales'))

            if sale_type == 'Direct' and not product_config.supports_direct_sales:
                flash('This product does not support Direct Sales.', 'danger')
                return redirect(url_for('sales.sales'))
            if sale_type == 'Service' and not product_config.supports_service_sales:
                flash('This product does not support Service Sales.', 'danger')
                return redirect(url_for('sales.sales'))

            sale_date_obj = datetime.strptime(sale_date, '%Y-%m-%d').date()
            price = get_product_price(product_id, sale_date_obj)
            total_price = quantity * price

            last_sale = Sale.query.order_by(Sale.id.desc()).first()
            order_id = (last_sale.id + 1) if last_sale else 1

            new_sale = Sale(
                product_id=product_id,
                order_id=order_id,
                sale_date=sale_date_obj,
                quantity=quantity,
                total_price=total_price,
                sale_type=sale_type,
                amount=total_price
            )
            db.session.add(new_sale)
            db.session.commit()
            flash('Sale recorded successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error recording sale: {str(e)}', 'danger')
        return redirect(url_for('sales.sales'))

    sales_data = Sale.query.all()
    return render_template('sales.html', products=products, sales_data=sales_data)

@sales_bp.route('/sales/report', methods=['GET', 'POST'])
@login_required
def sales_report():
    if not current_user.has_permission('sales'):
        flash('You do not have permission to access sales reports.', 'danger')
        return redirect(url_for('index'))

    start_date = datetime.now().replace(day=1, month=1).date()
    end_date = datetime.now().date()

    if request.method == 'POST':
        start_date = datetime.strptime(request.form.get('start_date'), '%Y-%m-%d').date()
        end_date = datetime.strptime(request.form.get('end_date'), '%Y-%m-%d').date()
        if end_date < start_date:
            flash('End date must be after start date.', 'danger')
            return redirect(url_for('sales.sales_report'))

    sales = Sale.query.filter(Sale.sale_date >= start_date, Sale.sale_date <= end_date).all()
    plans = ProductPlan.query.filter(ProductPlan.start_date <= end_date, ProductPlan.end_date >= start_date).all()

    sales_data = {
        'weekly': {'data': [], 'totals': {}},
        'monthly': {'data': [], 'totals': {}},
        'quarterly': {'data': [], 'totals': {}},
        'bi_annual': {'data': [], 'totals': {}},
        'annual': {'data': [], 'totals': {}},
    }

    daily_sales = {}
    for sale in sales:
        date_key = sale.sale_date.strftime('%Y-%m-%d')
        product_key = f"{sale.product_id}_{sale.sale_type}"
        if date_key not in daily_sales:
            daily_sales[date_key] = {}
        if product_key not in daily_sales[date_key]:
            daily_sales[date_key][product_key] = {'quantity': 0, 'total_price': 0}
        daily_sales[date_key][product_key]['quantity'] += sale.quantity
        daily_sales[date_key][product_key]['total_price'] += sale.total_price

    current_date = start_date
    while current_date <= end_date:
        week_end = min(current_date + timedelta(days=6), end_date)
        week_sales = {}
        week_total_quantity = 0
        week_total_value = 0
        for d in (current_date + timedelta(days=n) for n in range((week_end - current_date).days + 1)):
            date_key = d.strftime('%Y-%m-%d')
            if date_key in daily_sales:
                for product_key, data in daily_sales[date_key].items():
                    if product_key not in week_sales:
                        week_sales[product_key] = {'quantity': 0, 'total_price': 0}
                    week_sales[product_key]['quantity'] += data['quantity']
                    week_sales[product_key]['total_price'] += data['total_price']
                    week_total_quantity += data['quantity']
                    week_total_value += data['total_price']

        for product_key, data in week_sales.items():
            product_id, sale_type = product_key.split('_')
            product = Product.query.get(product_id)
            relevant_plan = next((p for p in plans if p.product_id == int(product_id) and p.start_date <= week_end and p.end_date >= current_date), None)
            sales_data['weekly']['data'].append({
                'product_name': product.name,
                'sale_type': sale_type,
                'start_date': current_date,
                'end_date': week_end,
                'actual_quantity': data['quantity'],
                'actual_value': data['total_price'],
                'planned_quantity': relevant_plan.planned_quantity if relevant_plan else 0,
                'planned_value': relevant_plan.planned_value if relevant_plan else 0,
                'quantity_percentage': (data['quantity'] / relevant_plan.planned_quantity * 100) if relevant_plan and relevant_plan.planned_quantity > 0 else 0,
                'value_percentage': (data['total_price'] / relevant_plan.planned_value * 100) if relevant_plan and relevant_plan.planned_value > 0 else 0,
                'product_share': (data['total_price'] / week_total_value * 100) if week_total_value > 0 else 0
            })
        sales_data['weekly']['totals'][f"{current_date}"] = {'quantity': week_total_quantity, 'value': week_total_value}
        current_date = week_end + timedelta(days=1)

    current_date = start_date
    while current_date <= end_date:
        month_end = current_date.replace(day=get_days_in_month(current_date.year, current_date.month))
        month_end = min(month_end, end_date)
        month_sales = {}
        month_total_quantity = 0
        month_total_value = 0
        for d in (current_date + timedelta(days=n) for n in range((month_end - current_date).days + 1)):
            date_key = d.strftime('%Y-%m-%d')
            if date_key in daily_sales:
                for product_key, data in daily_sales[date_key].items():
                    if product_key not in month_sales:
                        month_sales[product_key] = {'quantity': 0, 'total_price': 0}
                    month_sales[product_key]['quantity'] += data['quantity']
                    month_sales[product_key]['total_price'] += data['total_price']
                    month_total_quantity += data['quantity']
                    month_total_value += data['total_price']

        for product_key, data in month_sales.items():
            product_id, sale_type = product_key.split('_')
            product = Product.query.get(product_id)
            relevant_plan = next((p for p in plans if p.product_id == int(product_id) and p.start_date <= month_end and p.end_date >= current_date), None)
            sales_data['monthly']['data'].append({
                'product_name': product.name,
                'sale_type': sale_type,
                'start_date': current_date,
                'end_date': month_end,
                'actual_quantity': data['quantity'],
                'actual_value': data['total_price'],
                'planned_quantity': relevant_plan.planned_quantity if relevant_plan else 0,
                'planned_value': relevant_plan.planned_value if relevant_plan else 0,
                'quantity_percentage': (data['quantity'] / relevant_plan.planned_quantity * 100) if relevant_plan and relevant_plan.planned_quantity > 0 else 0,
                'value_percentage': (data['total_price'] / relevant_plan.planned_value * 100) if relevant_plan and relevant_plan.planned_value > 0 else 0,
                'product_share': (data['total_price'] / month_total_value * 100) if month_total_value > 0 else 0
            })
        sales_data['monthly']['totals'][f"{current_date.strftime('%Y-%m')}"] = {'quantity': month_total_quantity, 'value': month_total_value}
        current_date = month_end + timedelta(days=1)

    current_date = start_date
    while current_date <= end_date:
        quarter_end = min(current_date + timedelta(days=90), end_date)
        quarter_sales = {}
        quarter_total_quantity = 0
        quarter_total_value = 0
        for d in (current_date + timedelta(days=n) for n in range((quarter_end - current_date).days + 1)):
            date_key = d.strftime('%Y-%m-%d')
            if date_key in daily_sales:
                for product_key, data in daily_sales[date_key].items():
                    if product_key not in quarter_sales:
                        quarter_sales[product_key] = {'quantity': 0, 'total_price': 0}
                    quarter_sales[product_key]['quantity'] += data['quantity']
                    quarter_sales[product_key]['total_price'] += data['total_price']
                    quarter_total_quantity += data['quantity']
                    quarter_total_value += data['total_price']

        for product_key, data in quarter_sales.items():
            product_id, sale_type = product_key.split('_')
            product = Product.query.get(product_id)
            relevant_plan = next((p for p in plans if p.product_id == int(product_id) and p.start_date <= quarter_end and p.end_date >= current_date), None)
            sales_data['quarterly']['data'].append({
                'product_name': product.name,
                'sale_type': sale_type,
                'start_date': current_date,
                'end_date': quarter_end,
                'actual_quantity': data['quantity'],
                'actual_value': data['total_price'],
                'planned_quantity': relevant_plan.planned_quantity if relevant_plan else 0,
                'planned_value': relevant_plan.planned_value if relevant_plan else 0,
                'quantity_percentage': (data['quantity'] / relevant_plan.planned_quantity * 100) if relevant_plan and relevant_plan.planned_quantity > 0 else 0,
                'value_percentage': (data['total_price'] / relevant_plan.planned_value * 100) if relevant_plan and relevant_plan.planned_value > 0 else 0,
                'product_share': (data['total_price'] / quarter_total_value * 100) if quarter_total_value > 0 else 0
            })
        sales_data['quarterly']['totals'][f"{current_date}"] = {'quantity': quarter_total_quantity, 'value': quarter_total_value}
        current_date = quarter_end + timedelta(days=1)

    current_date = start_date
    while current_date <= end_date:
        bi_annual_end = min(current_date + timedelta(days=181), end_date)
        bi_annual_sales = {}
        bi_annual_total_quantity = 0
        bi_annual_total_value = 0
        for d in (current_date + timedelta(days=n) for n in range((bi_annual_end - current_date).days + 1)):
            date_key = d.strftime('%Y-%m-%d')
            if date_key in daily_sales:
                for product_key, data in daily_sales[date_key].items():
                    if product_key not in bi_annual_sales:
                        bi_annual_sales[product_key] = {'quantity': 0, 'total_price': 0}
                    bi_annual_sales[product_key]['quantity'] += data['quantity']
                    bi_annual_sales[product_key]['total_price'] += data['total_price']
                    bi_annual_total_quantity += data['quantity']
                    bi_annual_total_value += data['total_price']

        for product_key, data in bi_annual_sales.items():
            product_id, sale_type = product_key.split('_')
            product = Product.query.get(product_id)
            relevant_plan = next((p for p in plans if p.product_id == int(product_id) and p.start_date <= bi_annual_end and p.end_date >= current_date), None)
            sales_data['bi_annual']['data'].append({
                'product_name': product.name,
                'sale_type': sale_type,
                'start_date': current_date,
                'end_date': bi_annual_end,
                'actual_quantity': data['quantity'],
                'actual_value': data['total_price'],
                'planned_quantity': relevant_plan.planned_quantity if relevant_plan else 0,
                'planned_value': relevant_plan.planned_value if relevant_plan else 0,
                'quantity_percentage': (data['quantity'] / relevant_plan.planned_quantity * 100) if relevant_plan and relevant_plan.planned_quantity > 0 else 0,
                'value_percentage': (data['total_price'] / relevant_plan.planned_value * 100) if relevant_plan and relevant_plan.planned_value > 0 else 0,
                'product_share': (data['total_price'] / bi_annual_total_value * 100) if bi_annual_total_value > 0 else 0
            })
        sales_data['bi_annual']['totals'][f"{current_date}"] = {'quantity': bi_annual_total_quantity, 'value': bi_annual_total_value}
        current_date = bi_annual_end + timedelta(days=1)

    current_date = start_date
    while current_date <= end_date:
        year_end = current_date.replace(month=12, day=31)
        year_end = min(year_end, end_date)
        year_sales = {}
        year_total_quantity = 0
        year_total_value = 0
        for d in (current_date + timedelta(days=n) for n in range((year_end - current_date).days + 1)):
            date_key = d.strftime('%Y-%m-%d')
            if date_key in daily_sales:
                for product_key, data in daily_sales[date_key].items():
                    if product_key not in year_sales:
                        year_sales[product_key] = {'quantity': 0, 'total_price': 0}
                    year_sales[product_key]['quantity'] += data['quantity']
                    year_sales[product_key]['total_price'] += data['total_price']
                    year_total_quantity += data['quantity']
                    year_total_value += data['total_price']

        for product_key, data in year_sales.items():
            product_id, sale_type = product_key.split('_')
            product = Product.query.get(product_id)
            relevant_plan = next((p for p in plans if p.product_id == int(product_id) and p.start_date <= year_end and p.end_date >= current_date), None)
            sales_data['annual']['data'].append({
                'product_name': product.name,
                'sale_type': sale_type,
                'start_date': current_date,
                'end_date': year_end,
                'actual_quantity': data['quantity'],
                'actual_value': data['total_price'],
                'planned_quantity': relevant_plan.planned_quantity if relevant_plan else 0,
                'planned_value': relevant_plan.planned_value if relevant_plan else 0,
                'quantity_percentage': (data['quantity'] / relevant_plan.planned_quantity * 100) if relevant_plan and relevant_plan.planned_quantity > 0 else 0,
                'value_percentage': (data['total_price'] / relevant_plan.planned_value * 100) if relevant_plan and relevant_plan.planned_value > 0 else 0,
                'product_share': (data['total_price'] / year_total_value * 100) if year_total_value > 0 else 0
            })
        sales_data['annual']['totals'][f"{current_date.strftime('%Y')}"] = {'quantity': year_total_quantity, 'value': year_total_value}
        current_date = year_end + timedelta(days=1)

    chart_data = {
        'weekly': {'labels': [], 'actual_sales': {}, 'planned_sales': {}},
        'monthly': {'labels': [], 'actual_sales': {}, 'planned_sales': {}},
        'quarterly': {'labels': [], 'actual_sales': {}, 'planned_sales': {}},
        'bi_annual': {'labels': [], 'actual_sales': {}, 'planned_sales': {}},
        'annual': {'labels': [], 'actual_sales': {}, 'planned_sales': {}},
    }

    for period in chart_data:
        for entry in sales_data[period]['data']:
            label = f"{entry['start_date']}"
            key = f"{entry['product_name']}_{entry['sale_type']}"
            if label not in chart_data[period]['labels']:
                chart_data[period]['labels'].append(label)
            if key not in chart_data[period]['actual_sales']:
                chart_data[period]['actual_sales'][key] = []
                chart_data[period]['planned_sales'][key] = []
            chart_data[period]['actual_sales'][key].append(entry['actual_value'])
            chart_data[period]['planned_sales'][key].append(entry['planned_value'])

    return render_template('sales_report.html', 
                          sales_data=sales_data, 
                          chart_data=chart_data, 
                          start_date=start_date, 
                          end_date=end_date)

@sales_bp.route('/sales/export_excel/<period>')
@login_required
def export_excel(period):
    if not current_user.has_permission('sales'):
        flash('You do not have permission to export sales reports.', 'danger')
        return redirect(url_for('sales.sales_report'))

    start_date = datetime.strptime(request.args.get('start_date'), '%Y-%m-%d').date()
    end_date = datetime.strptime(request.args.get('end_date'), '%Y-%m-%d').date()
    sales = Sale.query.filter(Sale.sale_date >= start_date, Sale.sale_date <= end_date).all()
    plans = ProductPlan.query.filter(ProductPlan.start_date <= end_date, ProductPlan.end_date >= start_date).all()

    sales_data = {
        'weekly': {'data': [], 'totals': {}},
        'monthly': {'data': [], 'totals': {}},
        'quarterly': {'data': [], 'totals': {}},
        'bi_annual': {'data': [], 'totals': {}},
        'annual': {'data': [], 'totals': {}},
    }

    daily_sales = {}
    for sale in sales:
        date_key = sale.sale_date.strftime('%Y-%m-%d')
        product_key = f"{sale.product_id}_{sale.sale_type}"
        if date_key not in daily_sales:
            daily_sales[date_key] = {}
        if product_key not in daily_sales[date_key]:
            daily_sales[date_key][product_key] = {'quantity': 0, 'total_price': 0}
        daily_sales[date_key][product_key]['quantity'] += sale.quantity
        daily_sales[date_key][product_key]['total_price'] += sale.total_price

    current_date = start_date
    if period == 'weekly':
        while current_date <= end_date:
            week_end = min(current_date + timedelta(days=6), end_date)
            week_sales = {}
            week_total_quantity = 0
            week_total_value = 0
            for d in (current_date + timedelta(days=n) for n in range((week_end - current_date).days + 1)):
                date_key = d.strftime('%Y-%m-%d')
                if date_key in daily_sales:
                    for product_key, data in daily_sales[date_key].items():
                        if product_key not in week_sales:
                            week_sales[product_key] = {'quantity': 0, 'total_price': 0}
                        week_sales[product_key]['quantity'] += data['quantity']
                        week_sales[product_key]['total_price'] += data['total_price']
                        week_total_quantity += data['quantity']
                        week_total_value += data['total_price']

            for product_key, data in week_sales.items():
                product_id, sale_type = product_key.split('_')
                product = Product.query.get(product_id)
                relevant_plan = next((p for p in plans if p.product_id == int(product_id) and p.start_date <= week_end and p.end_date >= current_date), None)
                sales_data['weekly']['data'].append({
                    'product_name': product.name,
                    'sale_type': sale_type,
                    'start_date': current_date,
                    'end_date': week_end,
                    'actual_quantity': data['quantity'],
                    'actual_value': data['total_price'],
                    'planned_quantity': relevant_plan.planned_quantity if relevant_plan else 0,
                    'planned_value': relevant_plan.planned_value if relevant_plan else 0,
                    'quantity_percentage': (data['quantity'] / relevant_plan.planned_quantity * 100) if relevant_plan and relevant_plan.planned_quantity > 0 else 0,
                    'value_percentage': (data['total_price'] / relevant_plan.planned_value * 100) if relevant_plan and relevant_plan.planned_value > 0 else 0,
                    'product_share': (data['total_price'] / week_total_value * 100) if week_total_value > 0 else 0
                })
            current_date = week_end + timedelta(days=1)

    period_data = sales_data[period]['data']
    data = []
    for entry in period_data:
        data.append({
            'Product': entry['product_name'],
            'Sale Type': entry['sale_type'],
            'Start Date': entry['start_date'],
            'End Date': entry['end_date'],
            'Actual Quantity': entry['actual_quantity'],
            'Actual Value': entry['actual_value'],
            'Planned Quantity': entry['planned_quantity'],
            'Planned Value': entry['planned_value'],
            'Quantity %': entry['quantity_percentage'],
            'Value %': entry['value_percentage'],
            'Product Share %': entry['product_share']
        })

    df = pd.DataFrame(data)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name=f'{period.capitalize()} Sales Report', index=False)
    output.seek(0)
    return send_file(output, download_name=f'{period}_sales_report.xlsx', as_attachment=True)

@sales_bp.route('/sales/export_pdf/<period>')
@login_required
def export_pdf(period):
    if not current_user.has_permission('sales'):
        flash('You do not have permission to export sales reports.', 'danger')
        return redirect(url_for('sales.sales_report'))

    start_date = datetime.strptime(request.args.get('start_date'), '%Y-%m-%d').date()
    end_date = datetime.strptime(request.args.get('end_date'), '%Y-%m-%d').date()
    sales = Sale.query.filter(Sale.sale_date >= start_date, Sale.sale_date <= end_date).all()
    plans = ProductPlan.query.filter(ProductPlan.start_date <= end_date, ProductPlan.end_date >= start_date).all()

    sales_data = {
        'weekly': {'data': [], 'totals': {}},
        'monthly': {'data': [], 'totals': {}},
        'quarterly': {'data': [], 'totals': {}},
        'bi_annual': {'data': [], 'totals': {}},
        'annual': {'data': [], 'totals': {}},
    }

    daily_sales = {}
    for sale in sales:
        date_key = sale.sale_date.strftime('%Y-%m-%d')
        product_key = f"{sale.product_id}_{sale.sale_type}"
        if date_key not in daily_sales:
            daily_sales[date_key] = {}
        if product_key not in daily_sales[date_key]:
            daily_sales[date_key][product_key] = {'quantity': 0, 'total_price': 0}
        daily_sales[date_key][product_key]['quantity'] += sale.quantity
        daily_sales[date_key][product_key]['total_price'] += sale.total_price

    current_date = start_date
    if period == 'weekly':
        while current_date <= end_date:
            week_end = min(current_date + timedelta(days=6), end_date)
            week_sales = {}
            week_total_quantity = 0
            week_total_value = 0
            for d in (current_date + timedelta(days=n) for n in range((week_end - current_date).days + 1)):
                date_key = d.strftime('%Y-%m-%d')
                if date_key in daily_sales:
                    for product_key, data in daily_sales[date_key].items():
                        if product_key not in week_sales:
                            week_sales[product_key] = {'quantity': 0, 'total_price': 0}
                        week_sales[product_key]['quantity'] += data['quantity']
                        week_sales[product_key]['total_price'] += data['total_price']
                        week_total_quantity += data['quantity']
                        week_total_value += data['total_price']

            for product_key, data in week_sales.items():
                product_id, sale_type = product_key.split('_')
                product = Product.query.get(product_id)
                relevant_plan = next((p for p in plans if p.product_id == int(product_id) and p.start_date <= week_end and p.end_date >= current_date), None)
                sales_data['weekly']['data'].append({
                    'product_name': product.name,
                    'sale_type': sale_type,
                    'start_date': current_date,
                    'end_date': week_end,
                    'actual_quantity': data['quantity'],
                    'actual_value': data['total_price'],
                    'planned_quantity': relevant_plan.planned_quantity if relevant_plan else 0,
                    'planned_value': relevant_plan.planned_value if relevant_plan else 0,
                    'quantity_percentage': (data['quantity'] / relevant_plan.planned_quantity * 100) if relevant_plan and relevant_plan.planned_quantity > 0 else 0,
                    'value_percentage': (data['total_price'] / relevant_plan.planned_value * 100) if relevant_plan and relevant_plan.planned_value > 0 else 0,
                    'product_share': (data['total_price'] / week_total_value * 100) if week_total_value > 0 else 0
                })
            current_date = week_end + timedelta(days=1)

    period_data = sales_data[period]['data']
    output = BytesIO()
    c = canvas.Canvas(output, pagesize=letter)
    width, height = letter
    y = height - 50
    c.drawString(50, y, f"{period.capitalize()} Sales Report")
    y -= 30

    headers = ['Product', 'Sale Type', 'Start', 'End', 'Act Qty', 'Act Val', 'Plan Qty', 'Plan Val', 'Qty %', 'Val %', 'Share %']
    x_positions = [50, 100, 150, 200, 250, 300, 350, 400, 450, 500, 550]
    for i, header in enumerate(headers):
        c.drawString(x_positions[i], y, header)
    y -= 20

    for entry in period_data:
        if y < 50:
            c.showPage()
            y = height - 50
        values = [
            entry['product_name'],
            entry['sale_type'],
            str(entry['start_date']),
            str(entry['end_date']),
            str(round(entry['actual_quantity'], 2)),
            str(round(entry['actual_value'], 2)),
            str(round(entry['planned_quantity'], 2)),
            str(round(entry['planned_value'], 2)),
            f"{round(entry['quantity_percentage'], 2)}%",
            f"{round(entry['value_percentage'], 2)}%",
            f"{round(entry['product_share'], 2)}%"
        ]
        for i, value in enumerate(values):
            c.drawString(x_positions[i], y, value)
        y -= 20

    c.save()
    output.seek(0)
    return send_file(output, download_name=f'{period}_sales_report.pdf', as_attachment=True)