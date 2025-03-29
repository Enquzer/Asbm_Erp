from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_login import login_required, current_user
from database import db
from modules.purchasing_models import PurchaseRequest, ProcurementOrder, Supplier, YearlyPurchasePlan
from modules.models import Product, DutyStation
from modules.notifications import send_notification
from datetime import datetime
import logging
import pandas as pd
from io import BytesIO
import matplotlib.pyplot as plt
import seaborn as sns
import base64
import os
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet

purchasing_bp = Blueprint('purchasing', __name__)

COST_CATEGORIES = ["Construction", "Customs Service Payment", "Machine Accessories", "Project Raw Material", 
                   "Project Service Payment", "Raw Material", "Salts and Chemicals", "Service Payment", 
                   "Spare Parts", "Vehicle Service Payment", "Wood"]

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def export_to_pdf(data, columns, filename):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()
    elements.append(Paragraph("Purchasing Report", styles['Title']))
    
    table_data = [columns] + [[str(row.get(col, '')) for col in columns] for row in data]
    table = Table(table_data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 14),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    elements.append(table)
    doc.build(elements)
    buffer.seek(0)
    return send_file(buffer, download_name=filename, as_attachment=True)

@purchasing_bp.route('/')
@login_required
def purchasing():
    if not current_user.has_permission('purchasing'):
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('dashboard.dashboard'))
    
    new_requests_count = PurchaseRequest.query.filter_by(status="Pending").count()
    requests = PurchaseRequest.query.order_by(PurchaseRequest.created_at.desc()).all()
    procurement_orders = ProcurementOrder.query.order_by(ProcurementOrder.registered_date.desc()).all()
    products = Product.query.all()
    duty_stations = DutyStation.query.all()
    suppliers = Supplier.query.all()
    payables = ProcurementOrder.query.filter(ProcurementOrder.payment_status.in_(['Unpaid', 'Partially Paid', 'Credit'])).all()
    yearly_plans = YearlyPurchasePlan.query.all()
    return render_template('purchasing.html', new_requests_count=new_requests_count, requests=requests,
                           procurement_orders=procurement_orders, products=products, duty_stations=duty_stations,
                           suppliers=suppliers, cost_categories=COST_CATEGORIES, payables=payables, yearly_plans=yearly_plans)

@purchasing_bp.route('/request', methods=['GET', 'POST'])
@login_required
def purchase_request():
    if request.method == 'POST':
        request_code = request.form.get('request_code') or f"PUR-{PurchaseRequest.query.count() + 1:04d}"
        dept_name = request.form.get('dept_name')
        item_name = request.form.get('item_name')
        description = request.form.get('description')
        unit_of_measure = request.form.get('unit_of_measure')
        quantity = request.form.get('quantity')
        expected_delivery_date = request.form.get('expected_delivery_date')

        if not all([request_code, dept_name, item_name, unit_of_measure, quantity, expected_delivery_date]):
            flash('All fields are required!', 'danger')
            return redirect(url_for('purchasing.purchasing'))

        new_request = PurchaseRequest(
            request_code=request_code,
            dept_name=dept_name,
            requested_by_id=current_user.id,
            item_name=item_name,
            description=description,
            unit_of_measure=unit_of_measure,
            quantity=int(quantity),
            expected_delivery_date=datetime.strptime(expected_delivery_date, '%Y-%m-%d'),
            status="Pending"
        )
        db.session.add(new_request)
        db.session.commit()
        send_notification(f"New purchase request {request_code} submitted by {current_user.username}", "Purchasing")
        flash('Purchase request submitted!', 'success')
        return redirect(url_for('purchasing.purchasing'))
    return redirect(url_for('purchasing.purchasing'))

@purchasing_bp.route('/fulfill_request/<int:request_id>', methods=['POST'])
@login_required
def fulfill_request(request_id):
    req = PurchaseRequest.query.get_or_404(request_id)
    order_number = request.form.get('order_number') or f"PO-{ProcurementOrder.query.count() + 1:04d}"
    product_id = request.form.get('product_id')
    supplier_name = request.form.get('supplier_name')
    total_price = request.form.get('total_price')

    if not all([order_number, supplier_name, total_price]):
        flash('Required fields missing!', 'danger')
        return redirect(url_for('purchasing.purchasing'))

    supplier = Supplier.query.filter_by(name=supplier_name).first()
    if not supplier:
        supplier = Supplier(name=supplier_name, contact_info="N/A")
        db.session.add(supplier)
        db.session.commit()

    new_order = ProcurementOrder(
        order_number=order_number,
        request_id=req.id,
        product_id=int(product_id) if product_id else None,
        quantity=req.quantity,
        unit_of_measure=req.unit_of_measure,
        total_price=float(total_price),
        supplier_id=supplier.id,
        status="Fulfilled",
        cost_category=req.dept_name,
        duty_station_id=current_user.duty_station_id if hasattr(current_user, 'duty_station_id') else 1,
        description=req.description,
        registered_date=datetime.utcnow()
    )
    req.status = "Fulfilled"
    db.session.add(new_order)
    db.session.commit()
    send_notification(f"Purchase request {req.request_code} fulfilled with order {order_number}", "Purchasing")
    flash('Purchase request fulfilled!', 'success')
    return redirect(url_for('purchasing.purchasing'))

@purchasing_bp.route('/register_purchase', methods=['POST'])
@login_required
def register_purchase():
    order_number = request.form.get('order_number') or f"PO-{ProcurementOrder.query.count() + 1:04d}"
    description = request.form.get('description')
    cost_category = request.form.get('cost_category')
    supplier_name = request.form.get('supplier_name')
    duty_station_id = request.form.get('duty_station_id')
    cost_type = request.form.get('cost_type')
    total_price = request.form.get('total_price')
    payment_status = request.form.get('payment_status')
    payment_amount = request.form.get('payment_amount', 0.0)
    payment_date = request.form.get('payment_date')
    unit_of_measure = request.form.get('unit_of_measure')
    quantity = request.form.get('quantity', 1)

    if not all([order_number, description, cost_category, supplier_name, duty_station_id, total_price, unit_of_measure, quantity]):
        flash('Required fields missing!', 'danger')
        return redirect(url_for('purchasing.purchasing'))

    supplier = Supplier.query.filter_by(name=supplier_name).first()
    if not supplier:
        supplier = Supplier(name=supplier_name, contact_info="N/A")
        db.session.add(supplier)
        db.session.commit()

    new_purchase = ProcurementOrder(
        order_number=order_number,
        description=description,
        cost_category=cost_category,
        supplier_id=supplier.id,
        duty_station_id=int(duty_station_id),
        cost_type=cost_type,
        total_price=float(total_price),
        payment_status=payment_status,
        payment_amount=float(payment_amount) if payment_amount else 0.0,
        payment_date=datetime.strptime(payment_date, '%Y-%m-%d') if payment_date else None,
        unit_of_measure=unit_of_measure,
        quantity=int(quantity),
        status="Pending",
        registered_date=datetime.utcnow()
    )
    db.session.add(new_purchase)
    db.session.commit()
    send_notification(f"New purchase {order_number} registered by {current_user.username}", "Purchasing")
    flash('New purchase registered!', 'success')
    return redirect(url_for('purchasing.purchasing'))

@purchasing_bp.route('/export_purchases', methods=['GET'])
@login_required
def export_purchases():
    export_format = request.args.get('format', 'excel')
    orders = ProcurementOrder.query.order_by(ProcurementOrder.registered_date.desc()).all()
    data = [{
        'Order Number': o.order_number,
        'Description': o.description,
        'Cost Category': o.cost_category,
        'Supplier': o.supplier.name if o.supplier else 'N/A',
        'Duty Station': o.duty_station.name if o.duty_station else 'N/A',
        'Quantity': o.quantity,
        'Unit': o.unit_of_measure,
        'Total Price': o.total_price,
        'Payment Status': o.payment_status,
        'Payment Amount': o.payment_amount,
        'Payment Date': o.payment_date,
        'Registered Date': o.registered_date
    } for o in orders]
    
    if export_format == 'excel':
        df = pd.DataFrame(data)
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='Purchases', index=False)
        output.seek(0)
        return send_file(output, download_name='purchases.xlsx', as_attachment=True)
    elif export_format == 'pdf':
        columns = ['Order Number', 'Description', 'Cost Category', 'Supplier', 'Duty Station', 'Quantity', 'Unit', 
                   'Total Price', 'Payment Status', 'Payment Amount', 'Payment Date', 'Registered Date']
        return export_to_pdf(data, columns, 'purchases.pdf')
    return redirect(url_for('purchasing.purchasing'))

@purchasing_bp.route('/search_suppliers', methods=['GET'])
@login_required
def search_suppliers():
    query = request.args.get('q', '')
    suppliers = Supplier.query.filter(Supplier.name.ilike(f'%{query}%')).limit(10).all()
    return jsonify([{'id': s.id, 'name': s.name} for s in suppliers])

@purchasing_bp.route('/register_supplier', methods=['POST'])
@login_required
def register_supplier():
    name = request.form.get('name')
    contact_name = request.form.get('contact_name')
    phone = request.form.get('phone')
    email = request.form.get('email')
    location = request.form.get('location')
    supplied_items = request.form.get('supplied_items')
    rating = request.form.get('rating', 0.0)

    if not name:
        flash('Supplier name is required!', 'danger')
        return redirect(url_for('purchasing.purchasing'))

    supplier = Supplier(
        name=name,
        contact_name=contact_name,
        phone=phone,
        email=email,
        location=location,
        supplied_items=supplied_items,
        rating=float(rating) if rating else 0.0
    )
    db.session.add(supplier)
    db.session.commit()
    flash('Supplier registered!', 'success')
    return redirect(url_for('purchasing.purchasing'))

@purchasing_bp.route('/modify_supplier/<int:supplier_id>', methods=['POST'])
@login_required
def modify_supplier(supplier_id):
    supplier = Supplier.query.get_or_404(supplier_id)
    supplier.name = request.form.get('name', supplier.name)
    supplier.contact_name = request.form.get('contact_name', supplier.contact_name)
    supplier.phone = request.form.get('phone', supplier.phone)
    supplier.email = request.form.get('email', supplier.email)
    supplier.location = request.form.get('location', supplier.location)
    supplier.supplied_items = request.form.get('supplied_items', supplier.supplied_items)
    supplier.rating = float(request.form.get('rating', supplier.rating) or supplier.rating)
    db.session.commit()
    flash('Supplier modified!', 'success')
    return redirect(url_for('purchasing.purchasing'))

@purchasing_bp.route('/delete_supplier/<int:supplier_id>', methods=['POST'])
@login_required
def delete_supplier(supplier_id):
    supplier = Supplier.query.get_or_404(supplier_id)
    if ProcurementOrder.query.filter_by(supplier_id=supplier_id).first():
        flash('Cannot delete supplier with associated purchases!', 'danger')
    else:
        db.session.delete(supplier)
        db.session.commit()
        flash('Supplier deleted!', 'success')
    return redirect(url_for('purchasing.purchasing'))

@purchasing_bp.route('/export_suppliers', methods=['GET'])
@login_required
def export_suppliers():
    export_format = request.args.get('format', 'excel')
    suppliers = Supplier.query.all()
    data = [{
        'Name': s.name,
        'Contact Name': s.contact_name,
        'Phone': s.phone,
        'Email': s.email,
        'Location': s.location,
        'Supplied Items': s.supplied_items,
        'Rating': s.rating
    } for s in suppliers]
    
    if export_format == 'excel':
        df = pd.DataFrame(data)
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='Suppliers', index=False)
        output.seek(0)
        return send_file(output, download_name='suppliers.xlsx', as_attachment=True)
    elif export_format == 'pdf':
        columns = ['Name', 'Contact Name', 'Phone', 'Email', 'Location', 'Supplied Items', 'Rating']
        return export_to_pdf(data, columns, 'suppliers.pdf')
    return redirect(url_for('purchasing.purchasing'))

@purchasing_bp.route('/update_payment/<int:order_id>', methods=['POST'])
@login_required
def update_payment(order_id):
    order = ProcurementOrder.query.get_or_404(order_id)
    payment_amount = request.form.get('payment_amount')
    payment_date = request.form.get('payment_date')
    payment_status = request.form.get('payment_status')

    if not all([payment_amount, payment_status]):
        flash('Payment amount and status are required!', 'danger')
        return redirect(url_for('purchasing.purchasing'))

    order.payment_amount = float(payment_amount)
    order.payment_date = datetime.strptime(payment_date, '%Y-%m-%d') if payment_date else order.payment_date
    order.payment_status = payment_status
    if order.payment_amount >= order.total_price:
        order.payment_status = "Paid"
    elif order.payment_amount > 0:
        order.payment_status = "Partially Paid"
    db.session.commit()
    send_notification(f"Payment updated for order {order.order_number}", "Purchasing")
    flash('Payment updated!', 'success')
    return redirect(url_for('purchasing.purchasing'))

@purchasing_bp.route('/export_payables', methods=['GET'])
@login_required
def export_payables():
    export_format = request.args.get('format', 'excel')
    payables = ProcurementOrder.query.filter(ProcurementOrder.payment_status.in_(['Unpaid', 'Partially Paid', 'Credit'])).all()
    data = [{
        'Order Number': o.order_number,
        'Description': o.description,
        'Supplier': o.supplier.name if o.supplier else 'N/A',
        'Duty Station': o.duty_station.name if o.duty_station else 'N/A',
        'Total Price': o.total_price,
        'Payment Status': o.payment_status,
        'Payment Amount': o.payment_amount,
        'Remaining': o.total_price - o.payment_amount
    } for o in payables]
    
    if export_format == 'excel':
        df = pd.DataFrame(data)
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='Payables', index=False)
        output.seek(0)
        return send_file(output, download_name='payables.xlsx', as_attachment=True)
    elif export_format == 'pdf':
        columns = ['Order Number', 'Description', 'Supplier', 'Duty Station', 'Total Price', 'Payment Status', 'Payment Amount', 'Remaining']
        return export_to_pdf(data, columns, 'payables.pdf')
    return redirect(url_for('purchasing.purchasing'))

@purchasing_bp.route('/export_report', methods=['GET'])
@login_required
def export_report():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    duty_station_id = request.args.get('duty_station_id')
    export_format = request.args.get('format', 'excel')

    query = ProcurementOrder.query
    if start_date:
        query = query.filter(ProcurementOrder.registered_date >= datetime.strptime(start_date, '%Y-%m-%d'))
    if end_date:
        query = query.filter(ProcurementOrder.registered_date <= datetime.strptime(end_date, '%Y-%m-%d'))
    if duty_station_id:
        query = query.filter_by(duty_station_id=int(duty_station_id))

    orders = query.all()
    data = [{
        'Order Number': o.order_number,
        'Description': o.description,
        'Cost Category': o.cost_category,
        'Supplier': o.supplier.name if o.supplier else 'N/A',
        'Duty Station': o.duty_station.name if o.duty_station else 'N/A',
        'Quantity': o.quantity,
        'Unit': o.unit_of_measure,
        'Total Price': o.total_price,
        'Payment Status': o.payment_status,
        'Payment Amount': o.payment_amount,
        'Payment Date': o.payment_date,
        'Registered Date': o.registered_date
    } for o in orders]

    if export_format == 'excel':
        df = pd.DataFrame(data)
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='Purchasing Report', index=False)
        output.seek(0)
        return send_file(output, download_name='purchasing_report.xlsx', as_attachment=True)
    elif export_format == 'pdf':
        columns = ['Order Number', 'Description', 'Cost Category', 'Supplier', 'Duty Station', 'Quantity', 'Unit', 
                   'Total Price', 'Payment Status', 'Payment Amount', 'Payment Date', 'Registered Date']
        return export_to_pdf(data, columns, 'purchasing_report.pdf')
    return redirect(url_for('purchasing.purchasing'))

@purchasing_bp.route('/report_data', methods=['GET'])
@login_required
def report_data():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    duty_station_id = request.args.get('duty_station_id')

    query = ProcurementOrder.query
    if start_date:
        query = query.filter(ProcurementOrder.registered_date >= datetime.strptime(start_date, '%Y-%m-%d'))
    if end_date:
        query = query.filter(ProcurementOrder.registered_date <= datetime.strptime(end_date, '%Y-%m-%d'))
    if duty_station_id:
        query = query.filter_by(duty_station_id=int(duty_station_id))

    orders = query.all()
    if not orders:
        return jsonify({'error': 'No data available for the selected filters'})

    df = pd.DataFrame([{
        'Duty Station': o.duty_station.name if o.duty_station else 'N/A',
        'Total Price': o.total_price,
        'Cost Category': o.cost_category,
        'Description': o.description,
        'Registered Date': o.registered_date
    } for o in orders])

    # Month Total Expense Per Duty Station
    total_expense = df.groupby('Duty Station')['Total Price'].sum().reset_index()
    total_expense['%'] = (total_expense['Total Price'] / total_expense['Total Price'].sum() * 100).round(2)
    plt.figure(figsize=(10, 6))
    sns.barplot(x='Duty Station', y='Total Price', data=total_expense)
    plt.title('Total Expense Per Duty Station')
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    buf = BytesIO()
    plt.savefig(buf, format='png', dpi=100)
    buf.seek(0)
    bar_chart = base64.b64encode(buf.getvalue()).decode('utf-8')
    plt.close()

    # Pie Chart for % Share
    plt.figure(figsize=(8, 8))
    plt.pie(total_expense['%'], labels=total_expense['Duty Station'], autopct='%1.1f%%', startangle=90)
    plt.title('% Share of Total Expense')
    plt.tight_layout()
    buf = BytesIO()
    plt.savefig(buf, format='png', dpi=100)
    buf.seek(0)
    pie_chart = base64.b64encode(buf.getvalue()).decode('utf-8')
    plt.close()

    # Top 5 Expensive Items per Duty Station
    top_items = df.groupby(['Duty Station', 'Description'])['Total Price'].sum().reset_index()
    top_items = top_items.groupby('Duty Station').apply(lambda x: x.nlargest(5, 'Total Price')).reset_index(drop=True)
    plt.figure(figsize=(12, 8))
    sns.barplot(x='Total Price', y='Description', hue='Duty Station', data=top_items)
    plt.title('Top 5 Expensive Items Per Duty Station')
    plt.tight_layout()
    buf = BytesIO()
    plt.savefig(buf, format='png', dpi=100)
    buf.seek(0)
    top_items_chart = base64.b64encode(buf.getvalue()).decode('utf-8')
    plt.close()

    # Spending Trend Over Time
    df['Month'] = df['Registered Date'].apply(lambda x: x.strftime('%Y-%m'))
    trend = df.groupby('Month')['Total Price'].sum().reset_index()
    plt.figure(figsize=(10, 6))
    sns.lineplot(x='Month', y='Total Price', data=trend, marker='o')
    plt.title('Spending Trend Over Time')
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    buf = BytesIO()
    plt.savefig(buf, format='png', dpi=100)
    buf.seek(0)
    trend_chart = base64.b64encode(buf.getvalue()).decode('utf-8')
    plt.close()

    return jsonify({
        'total_expense': total_expense.to_dict(orient='records'),
        'bar_chart': bar_chart,
        'pie_chart': pie_chart,
        'top_items': top_items.to_dict(orient='records'),
        'top_items_chart': top_items_chart,
        'trend': trend.to_dict(orient='records'),
        'trend_chart': trend_chart
    })

@purchasing_bp.route('/upload_plan', methods=['POST'])
@login_required
def upload_plan():
    if 'file' not in request.files:
        flash('No file part!', 'danger')
        return redirect(url_for('purchasing.purchasing'))
    
    file = request.files['file']
    if file.filename == '':
        flash('No file selected!', 'danger')
        return redirect(url_for('purchasing.purchasing'))
    
    if file and file.filename.endswith('.xlsx'):
        df = pd.read_excel(file)
        required_columns = {'year', 'duty_station_id', 'cost_category', 'planned_cost', 'q1_cost', 'q2_cost', 'q3_cost', 'q4_cost'}
        if not required_columns.issubset(df.columns):
            flash('Excel file must contain year, duty_station_id, cost_category, planned_cost, and quarterly costs (q1_cost, q2_cost, q3_cost, q4_cost)!', 'danger')
            return redirect(url_for('purchasing.purchasing'))

        for _, row in df.iterrows():
            plan = YearlyPurchasePlan(
                year=int(row['year']),
                duty_station_id=int(row['duty_station_id']),
                cost_category=row['cost_category'],
                planned_cost=float(row['planned_cost']),
                q1_cost=float(row['q1_cost']),
                q2_cost=float(row['q2_cost']),
                q3_cost=float(row['q3_cost']),
                q4_cost=float(row['q4_cost'])
            )
            db.session.add(plan)
        db.session.commit()
        flash('Yearly purchase plan uploaded!', 'success')
        return redirect(url_for('purchasing.purchasing'))
    flash('Invalid file format! Use .xlsx.', 'danger')
    return redirect(url_for('purchasing.purchasing'))

@purchasing_bp.route('/register_plan', methods=['POST'])
@login_required
def register_plan():
    year = request.form.get('year')
    duty_station_id = request.form.get('duty_station_id')
    cost_category = request.form.get('cost_category')
    planned_cost = request.form.get('planned_cost')
    q1_cost = request.form.get('q1_cost', 0.0)
    q2_cost = request.form.get('q2_cost', 0.0)
    q3_cost = request.form.get('q3_cost', 0.0)
    q4_cost = request.form.get('q4_cost', 0.0)

    if not all([year, duty_station_id, cost_category, planned_cost]):
        flash('Required fields missing!', 'danger')
        return redirect(url_for('purchasing.purchasing'))

    plan = YearlyPurchasePlan(
        year=int(year),
        duty_station_id=int(duty_station_id),
        cost_category=cost_category,
        planned_cost=float(planned_cost),
        q1_cost=float(q1_cost),
        q2_cost=float(q2_cost),
        q3_cost=float(q3_cost),
        q4_cost=float(q4_cost)
    )
    db.session.add(plan)
    db.session.commit()
    flash('Yearly purchase plan registered!', 'success')
    return redirect(url_for('purchasing.purchasing'))

@purchasing_bp.route('/export_plans', methods=['GET'])
@login_required
def export_plans():
    export_format = request.args.get('format', 'excel')
    plans = YearlyPurchasePlan.query.all()
    data = [{
        'Year': p.year,
        'Duty Station': p.duty_station.name if p.duty_station else 'N/A',
        'Cost Category': p.cost_category,
        'Planned Cost': p.planned_cost,
        'Q1 Cost': p.q1_cost,
        'Q2 Cost': p.q2_cost,
        'Q3 Cost': p.q3_cost,
        'Q4 Cost': p.q4_cost
    } for p in plans]
    
    if export_format == 'excel':
        df = pd.DataFrame(data)
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='Yearly Plans', index=False)
        output.seek(0)
        return send_file(output, download_name='yearly_plans.xlsx', as_attachment=True)
    elif export_format == 'pdf':
        columns = ['Year', 'Duty Station', 'Cost Category', 'Planned Cost', 'Q1 Cost', 'Q2 Cost', 'Q3 Cost', 'Q4 Cost']
        return export_to_pdf(data, columns, 'yearly_plans.pdf')
    return redirect(url_for('purchasing.purchasing'))