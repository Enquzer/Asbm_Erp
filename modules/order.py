from flask import Blueprint, render_template, request, redirect, url_for, flash, Response
from flask_login import login_required, current_user
from flask_wtf.csrf import generate_csrf
from database import db
from modules.models import Order, Product, Customer
from datetime import datetime
import logging
import pandas as pd
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
from reportlab.lib import colors

order_bp = Blueprint('order', __name__)

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

@order_bp.route('/orders')
@login_required
def order_list():
    if not (current_user.is_admin() or current_user.has_permission('orders')):
        flash('You do not have permission to view orders!', 'danger')
        return redirect(url_for('dashboard.dashboard'))

    # Get search parameters from the request
    product_category = request.args.get('product_category', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    order_number = request.args.get('order_number', '')
    sort = request.args.get('sort', 'latest')  # Default to latest first

    # Base query
    query = Order.query.join(Customer).join(Product)

    # Filter by product category
    if product_category:
        query = query.filter(Product.product_type == product_category)

    # Filter by date range
    if start_date:
        try:
            start_date_obj = datetime.strptime(start_date, '%Y-%m-%d')
            query = query.filter(Order.order_placed_date >= start_date_obj)
        except ValueError:
            flash('Invalid start date format. Use YYYY-MM-DD.', 'error')

    if end_date:
        try:
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d')
            query = query.filter(Order.order_placed_date <= end_date_obj)
        except ValueError:
            flash('Invalid end date format. Use YYYY-MM-DD.', 'error')

    # Filter by order number
    if order_number:
        query = query.filter(Order.order_number.ilike(f'%{order_number}%'))

    # Sort by date
    if sort == 'latest':
        query = query.order_by(Order.order_placed_date.desc())
    elif sort == 'oldest':
        query = query.order_by(Order.order_placed_date.asc())

    # Execute the query
    orders = query.all()

    # Pass search parameters back to the template for persistence
    return render_template('order.html',
                           orders=orders,
                           product_category=product_category,
                           start_date=start_date,
                           end_date=end_date,
                           order_number=order_number,
                           sort=sort,
                           csrf_token=generate_csrf())

@order_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_order():
    products = Product.query.all()
    customers = Customer.query.all()
    
    if request.method == 'POST':
        try:
            product_id = request.form.get('product_id')
            if not product_id:
                flash('Product ID is required', 'error')
                return redirect(url_for('order.add_order'))
            product = Product.query.get_or_404(product_id)
            
            customer_id = request.form.get('customer_id')
            if not customer_id:
                flash('Customer ID is required', 'error')
                return redirect(url_for('order.add_order'))
            
            quantity = request.form.get('quantity')
            if not quantity or not quantity.isdigit():
                flash('Valid quantity is required', 'error')
                return redirect(url_for('order.add_order'))
            quantity = int(quantity)

            order_placed_date = request.form.get('order_placed_date')
            if not order_placed_date:
                flash('Order placed date is required', 'error')
                return redirect(url_for('order.add_order'))
            order_placed_date = datetime.strptime(order_placed_date, '%Y-%m-%d').date()

            required_delivery_date = request.form.get('required_delivery_date')
            if not required_delivery_date:
                flash('Required delivery date is required', 'error')
                return redirect(url_for('order.add_order'))
            required_delivery_date = datetime.strptime(required_delivery_date, '%Y-%m-%d').date()

            size_range = request.form.getlist('size_range')  # Multi-select for BOM
            colors = request.form.get('colors', '').split(',') if request.form.get('colors') else []  # Comma-separated colors

            last_order = Order.query.order_by(Order.order_number.desc()).first()
            prefix = product.product_type[:3].upper()
            if last_order and prefix in last_order.order_number:
                seq = int(last_order.order_number.split('-')[1]) + 1
            else:
                seq = 1
            order_number = f"{prefix}-{seq:03d}"

            tax = product.selling_price * quantity * 0.15
            total = (product.selling_price * quantity) + tax

            order = Order(
                order_number=order_number,
                customer_id=customer_id,
                product_id=product_id,
                quantity=quantity,
                payment_status='Pending',
                order_status='Placed',
                tax=tax,
                total=total,
                delivery_info=request.form.get('delivery_info', ''),
                order_placed_date=order_placed_date,
                required_delivery_date=required_delivery_date,
                total_value=total
            )
            db.session.add(order)
            db.session.commit()

            # Update product parameters with size_range and colors
            product.parameters.update({'size_range': size_range, 'colors': colors})
            db.session.commit()

            logger.info(f"Order {order_number} added successfully")
            flash('Order added successfully!', 'success')
            return redirect(url_for('order.order_list'))
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error adding order: {str(e)}")
            flash(f"Error adding order: {str(e)}", 'error')
            return redirect(url_for('order.add_order'))
    
    return render_template('order_add.html', products=products, customers=customers, csrf_token=generate_csrf())

@order_bp.route('/update_status/<int:order_id>', methods=['POST'])
@login_required
def update_status(order_id):
    order = Order.query.get_or_404(order_id)
    try:
        new_status = request.form.get('order_status')
        if new_status in ['Placed', 'Packed', 'Shipped', 'Delivered']:
            order.order_status = new_status
        order.payment_status = request.form.get('payment_status')
        db.session.commit()
        flash('Order status updated!', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating status: {str(e)}")
        flash(f"Error updating status: {str(e)}", 'error')
    return redirect(url_for('order.order_list'))

@order_bp.route('/edit/<int:order_id>', methods=['GET', 'POST'])
@login_required
def edit_order(order_id):
    order = Order.query.get_or_404(order_id)
    products = Product.query.all()
    customers = Customer.query.all()

    if request.method == 'POST':
        try:
            order.customer_id = request.form.get('customer_id')
            order.product_id = request.form.get('product_id')
            order.quantity = int(request.form.get('quantity'))
            order.delivery_info = request.form.get('delivery_info', '')
            order.order_placed_date = datetime.strptime(request.form.get('order_placed_date'), '%Y-%m-%d').date()
            order.required_delivery_date = datetime.strptime(request.form.get('required_delivery_date'), '%Y-%m-%d').date()

            tax = Product.query.get(order.product_id).selling_price * order.quantity * 0.15
            order.tax = tax
            order.total = (Product.query.get(order.product_id).selling_price * order.quantity) + tax
            order.total_value = order.total

            size_range = request.form.getlist('size_range')
            colors = request.form.get('colors', '').split(',') if request.form.get('colors') else []
            product = Product.query.get(order.product_id)
            product.parameters.update({'size_range': size_range, 'colors': colors})

            db.session.commit()
            flash('Order updated successfully!', 'success')
            return redirect(url_for('order.order_list'))
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error editing order: {str(e)}")
            flash(f"Error editing order: {str(e)}", 'error')
            return redirect(url_for('order.edit_order', order_id=order_id))

    return render_template('order_edit.html', order=order, products=products, customers=customers, csrf_token=generate_csrf())

@order_bp.route('/details/<int:order_id>')
@login_required
def order_details(order_id):
    order = Order.query.get_or_404(order_id)
    return render_template('order_details.html', order=order, csrf_token=generate_csrf())

@order_bp.route('/export/excel')
@login_required
def export_to_excel():
    orders = Order.query.all()
    data = [{
        'Order Number': order.order_number,
        'Customer': order.customer.name,
        'Product': order.product.name,
        'Quantity': order.quantity,
        'Total': order.total,
        'Status': order.order_status
    } for order in orders]

    df = pd.DataFrame(data)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Orders')
    output.seek(0)

    return Response(
        output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment;filename=orders.xlsx"}
    )

@order_bp.route('/export/pdf')
@login_required
def export_to_pdf():
    orders = Order.query.all()
    data = [['Order Number', 'Customer', 'Product', 'Quantity', 'Total', 'Status']]
    data.extend([
        [order.order_number, order.customer.name, order.product.name, str(order.quantity), f"{order.total} ETB", order.order_status]
        for order in orders
    ])

    output = BytesIO()
    doc = SimpleDocTemplate(output, pagesize=letter)
    table = Table(data)
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
    doc.build([table])
    output.seek(0)

    return Response(
        output,
        mimetype="application/pdf",
        headers={"Content-Disposition": "attachment;filename=orders.pdf"}
    )