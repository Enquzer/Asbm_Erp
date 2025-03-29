from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_login import login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, SelectField, FileField, SubmitField, IntegerField
from wtforms.validators import DataRequired
from database import db
from modules.models import Product, ProductPlan, PlanChangeLog, Customer, Order, DutyStation, ProductConfig, ProductPrice
from werkzeug.utils import secure_filename
import os
import logging
import pandas as pd
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
from reportlab.lib import colors
from datetime import datetime

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

product_bp = Blueprint('product', __name__)

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), '..', 'static', 'images', 'products')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def generate_product_code():
    last_product = Product.query.order_by(Product.id.desc()).first()
    if last_product and last_product.product_code:
        try:
            parts = last_product.product_code.split('-')
            if len(parts) == 2 and parts[0] == 'PROD' and parts[1].isdigit():
                last_id = int(parts[1])
                new_id = last_id + 1
            else:
                logger.warning(f"Invalid product_code format: {last_product.product_code}. Starting from 1.")
                new_id = 1
        except (ValueError, IndexError) as e:
            logger.error(f"Error parsing product_code {last_product.product_code}: {str(e)}. Starting from 1.")
            new_id = 1
    else:
        new_id = 1
    return f"PROD-{new_id:06d}"

def calculate_customer_rating(customer_id):
    customer_order_count = db.session.query(db.func.count(Order.id)).filter(Order.customer_id == customer_id).scalar() or 0
    max_order_count = db.session.query(db.func.count(Order.id)).group_by(Order.customer_id).order_by(db.func.count(Order.id).desc()).first()
    max_order_count = max_order_count[0] if max_order_count else 0
    if max_order_count > 0:
        rating = (customer_order_count / max_order_count) * 5
    else:
        rating = 0.0
    return round(rating, 2)

class EditProductForm(FlaskForm):
    name = StringField('Product Name', validators=[DataRequired()])
    description = StringField('Description')
    product_type = SelectField('Product Type', choices=[
        ('Garment', 'Garment'), ('Knitted', 'Knitted'), ('Woven', 'Woven'),
        ('Yarn', 'Yarn'), ('Dyed', 'Dyed'), ('Printed', 'Printed'), ('Denim', 'Denim')
    ], validators=[DataRequired()])
    selling_price = FloatField('Selling Price', validators=[DataRequired()])
    cost = FloatField('Cost', validators=[DataRequired()])
    customer_id = SelectField('Customer', coerce=int)
    supplier = StringField('Supplier')
    batch_number = StringField('Batch Number')
    sku = StringField('SKU', validators=[DataRequired()])
    stock_quantity = IntegerField('Stock Quantity', validators=[DataRequired()])
    image = FileField('Product Image')
    submit = SubmitField('Save Changes')

class CustomerForm(FlaskForm):
    name = StringField('Customer Name', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired()])
    phone_number = StringField('Phone Number')
    location_address = StringField('Location Address')
    submit = SubmitField('Save Customer')

@product_bp.route('/products')
@login_required
def products():
    if not (current_user.is_admin() or current_user.has_permission('products')):
        flash('You do not have permission to view products!', 'danger')
        return redirect(url_for('dashboard.dashboard'))
    search_query = request.args.get('search', '')
    category = request.args.get('category', 'all').lower()
    
    query = Product.query
    if search_query:
        query = query.filter(
            Product.name.ilike(f'%{search_query}%') |
            Product.product_code.ilike(f'%{search_query}%') |
            Product.product_type.ilike(f'%{search_query}%')
        )
    if category != 'all':
        query = query.filter(Product.product_type.ilike(category))
    
    products = query.all()
    customers = Customer.query.all()
    return render_template('products.html', products=products, search_query=search_query, category=category, customers=customers)

@product_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_product():
    if not (current_user.is_admin() or current_user.has_permission('products')):
        flash('You do not have permission to add products!', 'danger')
        return redirect(url_for('dashboard.dashboard'))
    
    customers = Customer.query.all()
    form = EditProductForm()
    form.customer_id.choices = [(c.id, c.name) for c in customers]
    
    if form.validate_on_submit():
        try:
            product_code = generate_product_code()
            parameters = {}
            size_range = request.form.getlist('size_range') or []
            colors = request.form.get('colors', '').split(',') if request.form.get('colors') else []

            if form.product_type.data == 'Garment':
                target_group = request.form.get('target_group')
                parameters = {
                    'garment_type': request.form.get('garment_type', ''),
                    'fabric_type': request.form.get('fabric_type', ''),
                    'fabric_gsm': request.form.get('fabric_gsm', ''),
                    'fabric_composition': request.form.get('fabric_composition', ''),
                    'target_group': target_group or '',
                    'size_range': size_range,
                    'colors': colors,
                    'print_type': request.form.get('print_type', ''),
                    'embroidery': request.form.get('embroidery', ''),
                    'packaging_method': request.form.get('packaging_method', '')
                }
            elif form.product_type.data == 'Knitted':
                parameters = {
                    'fabric_type': request.form.get('fabric_type', ''),
                    'fabric_gsm': request.form.get('fabric_gsm', ''),
                    'fabric_width': request.form.get('fabric_width', ''),
                    'gauge': request.form.get('gauge', ''),
                    'yarn_count': request.form.get('yarn_count', ''),
                    'colors': colors,
                    'packaging_method': request.form.get('packaging_method', '')
                }
            elif form.product_type.data == 'Woven':
                parameters = {
                    'fabric_type': request.form.get('fabric_type', ''),
                    'fabric_gsm': request.form.get('fabric_gsm', ''),
                    'fabric_width': request.form.get('fabric_width', ''),
                    'yarn_count': request.form.get('yarn_count', ''),
                    'weave_type': request.form.get('weave_type', ''),
                    'colors': colors,
                    'packaging_method': request.form.get('packaging_method', '')
                }
            elif form.product_type.data == 'Yarn':
                parameters = {
                    'yarn_type': request.form.get('yarn_type', ''),
                    'yarn_count': request.form.get('yarn_count', ''),
                    'yarn_composition': request.form.get('yarn_composition', ''),
                    'twist_per_inch': request.form.get('twist_per_inch', ''),
                    'colors': colors,
                    'yarn_packaging': request.form.get('yarn_packaging', '')
                }
            elif form.product_type.data == 'Dyed':
                parameters = {
                    'fabric_type': request.form.get('fabric_type', ''),
                    'fabric_gsm': request.form.get('fabric_gsm', ''),
                    'fabric_width': request.form.get('fabric_width', ''),
                    'colors': colors,
                    'dyeing_method': request.form.get('dyeing_method', ''),
                    'packaging_method': request.form.get('packaging_method', '')
                }
            elif form.product_type.data == 'Printed':
                parameters = {
                    'fabric_type': request.form.get('fabric_type', ''),
                    'fabric_gsm': request.form.get('fabric_gsm', ''),
                    'fabric_width': request.form.get('fabric_width', ''),
                    'print_design': request.form.get('print_design', ''),
                    'print_type': request.form.get('print_type', ''),
                    'colors': colors,
                    'packaging_method': request.form.get('packaging_method', '')
                }
            elif form.product_type.data == 'Denim':
                parameters = {
                    'fabric_type': request.form.get('fabric_type', ''),
                    'fabric_gsm': request.form.get('fabric_gsm', ''),
                    'fabric_width': request.form.get('fabric_width', ''),
                    'yarn_count': request.form.get('yarn_count', ''),
                    'weave_type': request.form.get('weave_type', ''),
                    'indigo_dye_level': request.form.get('indigo_dye_level', ''),
                    'colors': colors,
                    'packaging_method': request.form.get('packaging_method', '')
                }

            image = form.image.data
            image_path = None
            if image and allowed_file(image.filename):
                filename = secure_filename(image.filename)
                image_path = os.path.join(UPLOAD_FOLDER, filename)
                image.save(image_path)
                image_path = f'/static/images/products/{filename}'

            new_product = Product(
                name=form.name.data,
                description=form.description.data,
                product_code=product_code,
                product_type=form.product_type.data,
                selling_price=form.selling_price.data,
                cost=form.cost.data,
                customer_id=form.customer_id.data,
                supplier=form.supplier.data,
                batch_number=form.batch_number.data,
                sku=form.sku.data,
                stock_quantity=form.stock_quantity.data,
                image_path=image_path,
                parameters=parameters
            )
            db.session.add(new_product)
            db.session.commit()
            flash('Product added successfully!', 'success')
            return redirect(url_for('product.products'))
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error adding product: {str(e)}")
            flash(f'Error adding product: {str(e)}', 'danger')
    return render_template('add_product.html', form=form, customers=customers)

@product_bp.route('/edit/<int:product_id>', methods=['GET', 'POST'])
@login_required
def edit_product(product_id):
    if not (current_user.is_admin() or current_user.has_permission('products')):
        flash('You do not have permission to edit products!', 'danger')
        return redirect(url_for('dashboard.dashboard'))
    
    product = Product.query.get_or_404(product_id)
    if product.parameters is None:
        product.parameters = {}
    
    customers = Customer.query.all()
    form = EditProductForm(obj=product)
    form.customer_id.choices = [(c.id, c.name) for c in customers]
    
    product_config = ProductConfig.query.filter_by(product_id=product_id).first()
    current_price = ProductPrice.query.filter(
        ProductPrice.product_id == product_id,
        ProductPrice.start_date <= datetime.today().date()
    ).filter(
        (ProductPrice.end_date >= datetime.today().date()) | (ProductPrice.end_date.is_(None))
    ).order_by(ProductPrice.start_date.desc()).first()

    if form.validate_on_submit():
        try:
            product.name = form.name.data
            product.description = form.description.data
            product.product_type = form.product_type.data
            product.selling_price = form.selling_price.data
            product.cost = form.cost.data
            product.customer_id = form.customer_id.data
            product.supplier = form.supplier.data
            product.batch_number = form.batch_number.data
            product.sku = form.sku.data
            product.stock_quantity = form.stock_quantity.data

            image = form.image.data
            if image and allowed_file(image.filename):
                filename = secure_filename(image.filename)
                image_path = os.path.join(UPLOAD_FOLDER, filename)
                image.save(image_path)
                product.image_path = f'/static/images/products/{filename}'

            supports_direct_sales = 'supports_direct_sales' in request.form
            supports_service_sales = 'supports_service_sales' in request.form
            uom = request.form.get('uom')
            if not product_config:
                product_config = ProductConfig(product_id=product_id)
            product_config.supports_direct_sales = supports_direct_sales
            product_config.supports_service_sales = supports_service_sales
            product_config.uom = uom
            db.session.add(product_config)

            price = float(request.form.get('price'))
            price_start_date_str = request.form.get('price_start_date')
            price_end_date_str = request.form.get('price_end_date') or None

            if price_start_date_str:
                price_start_date = datetime.strptime(price_start_date_str, '%Y-%m-%d').date()
            else:
                flash('Price start date is required.', 'danger')
                return redirect(url_for('product.edit_product', product_id=product_id))

            price_end_date = None
            if price_end_date_str:
                price_end_date = datetime.strptime(price_end_date_str, '%Y-%m-%d').date()

            if price_start_date:
                if current_price and (not current_price.end_date or current_price.end_date >= price_start_date):
                    current_price.end_date = price_start_date
                    db.session.add(current_price)
                
                new_price = ProductPrice(
                    product_id=product_id,
                    price=price,
                    start_date=price_start_date,
                    end_date=price_end_date
                )
                db.session.add(new_price)

            parameters = product.parameters or {}
            size_range = request.form.getlist('size_range') or []
            colors = request.form.get('colors', '').split(',') if request.form.get('colors') else []

            if product.product_type == 'Garment':
                target_group = request.form.get('target_group')
                parameters = {
                    'garment_type': request.form.get('garment_type', parameters.get('garment_type', '')),
                    'fabric_type': request.form.get('fabric_type', parameters.get('fabric_type', '')),
                    'fabric_gsm': request.form.get('fabric_gsm', parameters.get('fabric_gsm', '')),
                    'fabric_composition': request.form.get('fabric_composition', parameters.get('fabric_composition', '')),
                    'target_group': target_group or parameters.get('target_group', ''),
                    'size_range': size_range,
                    'colors': colors,
                    'print_type': request.form.get('print_type', parameters.get('print_type', '')),
                    'embroidery': request.form.get('embroidery', parameters.get('embroidery', '')),
                    'packaging_method': request.form.get('packaging_method', parameters.get('packaging_method', ''))
                }
            elif product.product_type == 'Knitted':
                parameters = {
                    'fabric_type': request.form.get('fabric_type', parameters.get('fabric_type', '')),
                    'fabric_gsm': request.form.get('fabric_gsm', parameters.get('fabric_gsm', '')),
                    'fabric_width': request.form.get('fabric_width', parameters.get('fabric_width', '')),
                    'gauge': request.form.get('gauge', parameters.get('gauge', '')),
                    'yarn_count': request.form.get('yarn_count', parameters.get('yarn_count', '')),
                    'colors': colors,
                    'packaging_method': request.form.get('packaging_method', parameters.get('packaging_method', ''))
                }
            elif product.product_type == 'Woven':
                parameters = {
                    'fabric_type': request.form.get('fabric_type', parameters.get('fabric_type', '')),
                    'fabric_gsm': request.form.get('fabric_gsm', parameters.get('fabric_gsm', '')),
                    'fabric_width': request.form.get('fabric_width', parameters.get('fabric_width', '')),
                    'yarn_count': request.form.get('yarn_count', parameters.get('yarn_count', '')),
                    'weave_type': request.form.get('weave_type', parameters.get('weave_type', '')),
                    'colors': colors,
                    'packaging_method': request.form.get('packaging_method', parameters.get('packaging_method', ''))
                }
            elif product.product_type == 'Yarn':
                parameters = {
                    'yarn_type': request.form.get('yarn_type', parameters.get('yarn_type', '')),
                    'yarn_count': request.form.get('yarn_count', parameters.get('yarn_count', '')),
                    'yarn_composition': request.form.get('yarn_composition', parameters.get('yarn_composition', '')),
                    'twist_per_inch': request.form.get('twist_per_inch', parameters.get('twist_per_inch', '')),
                    'colors': colors,
                    'yarn_packaging': request.form.get('yarn_packaging', parameters.get('yarn_packaging', ''))
                }
            elif product.product_type == 'Dyed':
                parameters = {
                    'fabric_type': request.form.get('fabric_type', parameters.get('fabric_type', '')),
                    'fabric_gsm': request.form.get('fabric_gsm', parameters.get('fabric_gsm', '')),
                    'fabric_width': request.form.get('fabric_width', parameters.get('fabric_width', '')),
                    'colors': colors,
                    'dyeing_method': request.form.get('dyeing_method', parameters.get('dyeing_method', '')),
                    'packaging_method': request.form.get('packaging_method', parameters.get('packaging_method', ''))
                }
            elif product.product_type == 'Printed':
                parameters = {
                    'fabric_type': request.form.get('fabric_type', parameters.get('fabric_type', '')),
                    'fabric_gsm': request.form.get('fabric_gsm', parameters.get('fabric_gsm', '')),
                    'fabric_width': request.form.get('fabric_width', parameters.get('fabric_width', '')),
                    'print_design': request.form.get('print_design', parameters.get('print_design', '')),
                    'print_type': request.form.get('print_type', parameters.get('print_type', '')),
                    'colors': colors,
                    'packaging_method': request.form.get('packaging_method', parameters.get('packaging_method', ''))
                }
            elif product.product_type == 'Denim':
                parameters = {
                    'fabric_type': request.form.get('fabric_type', parameters.get('fabric_type', '')),
                    'fabric_gsm': request.form.get('fabric_gsm', parameters.get('fabric_gsm', '')),
                    'fabric_width': request.form.get('fabric_width', parameters.get('fabric_width', '')),
                    'yarn_count': request.form.get('yarn_count', parameters.get('yarn_count', '')),
                    'weave_type': request.form.get('weave_type', parameters.get('weave_type', '')),
                    'indigo_dye_level': request.form.get('indigo_dye_level', parameters.get('indigo_dye_level', '')),
                    'colors': colors,
                    'packaging_method': request.form.get('packaging_method', parameters.get('packaging_method', ''))
                }

            product.parameters = parameters
            db.session.commit()
            flash('Product updated successfully!', 'success')
            return redirect(url_for('product.products'))
        except ValueError as e:
            db.session.rollback()
            flash(f'Invalid date format: {str(e)}', 'danger')
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error updating product: {str(e)}")
            flash(f'Error updating product: {str(e)}', 'danger')
    
    return render_template(
        'edit_product.html',
        product=product,
        form=form,
        customers=customers,
        product_config=product_config,
        current_price=current_price
    )

@product_bp.route('/delete/<int:product_id>', methods=['POST'])
@login_required
def delete_product(product_id):
    if not (current_user.is_admin() or current_user.has_permission('products')):
        flash('You do not have permission to delete products!', 'danger')
        return redirect(url_for('dashboard.dashboard'))
    product = Product.query.get_or_404(product_id)
    try:
        db.session.delete(product)
        db.session.commit()
        flash('Product deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting product: {str(e)}")
        flash(f'Error deleting product: {str(e)}', 'danger')
    return redirect(url_for('product.products'))

@product_bp.route('/get_parameters')
@login_required
def get_parameters():
    product_type = request.args.get('type')
    parameters = []
    size_ranges = {
        'Garment': {
            'Men': ['S', 'M', 'L', 'XL', 'XXL'],
            'Women': ['XS', 'S', 'M', 'L', 'XL'],
            'Kids': ['2T', '3T', '4T', '5-6', '7-8'],
            'Newborn': ['0-3M', '3-6M', '6-9M', '9-12M']
        }
    }
    if product_type == 'Garment':
        parameters = [
            {'name': 'garment_type', 'label': 'Garment Type', 'type': 'text'},
            {'name': 'fabric_type', 'label': 'Fabric Type', 'type': 'text'},
            {'name': 'fabric_gsm', 'label': 'Fabric GSM', 'type': 'number'},
            {'name': 'fabric_composition', 'label': 'Fabric Composition', 'type': 'text'},
            {'name': 'target_group', 'label': 'Target Group', 'type': 'select', 'options': ['Men', 'Women', 'Kids', 'Newborn']},
            {'name': 'size_range', 'label': 'Size Range', 'type': 'checkbox', 'options': []},
            {'name': 'colors', 'label': 'Colors (comma-separated)', 'type': 'text'},
            {'name': 'print_type', 'label': 'Print Type', 'type': 'text'},
            {'name': 'embroidery', 'label': 'Embroidery', 'type': 'text'},
            {'name': 'packaging_method', 'label': 'Packaging Method', 'type': 'text'}
        ]
    elif product_type == 'Knitted':
        parameters = [
            {'name': 'fabric_type', 'label': 'Fabric Type', 'type': 'text'},
            {'name': 'fabric_gsm', 'label': 'Fabric GSM', 'type': 'number'},
            {'name': 'fabric_width', 'label': 'Fabric Width', 'type': 'number'},
            {'name': 'gauge', 'label': 'Gauge', 'type': 'text'},
            {'name': 'yarn_count', 'label': 'Yarn Count', 'type': 'text'},
            {'name': 'colors', 'label': 'Colors (comma-separated)', 'type': 'text'},
            {'name': 'packaging_method', 'label': 'Packaging Method', 'type': 'text'}
        ]
    elif product_type == 'Woven':
        parameters = [
            {'name': 'fabric_type', 'label': 'Fabric Type', 'type': 'text'},
            {'name': 'fabric_gsm', 'label': 'Fabric GSM', 'type': 'number'},
            {'name': 'fabric_width', 'label': 'Fabric Width', 'type': 'number'},
            {'name': 'yarn_count', 'label': 'Yarn Count', 'type': 'text'},
            {'name': 'weave_type', 'label': 'Weave Type', 'type': 'text'},
            {'name': 'colors', 'label': 'Colors (comma-separated)', 'type': 'text'},
            {'name': 'packaging_method', 'label': 'Packaging Method', 'type': 'text'}
        ]
    elif product_type == 'Yarn':
        parameters = [
            {'name': 'yarn_type', 'label': 'Yarn Type', 'type': 'text'},
            {'name': 'yarn_count', 'label': 'Yarn Count', 'type': 'text'},
            {'name': 'yarn_composition', 'label': 'Yarn Composition', 'type': 'text'},
            {'name': 'twist_per_inch', 'label': 'Twist per Inch (TPI)', 'type': 'number'},
            {'name': 'colors', 'label': 'Colors (comma-separated)', 'type': 'text'},
            {'name': 'yarn_packaging', 'label': 'Yarn Packaging', 'type': 'text'}
        ]
    elif product_type == 'Dyed':
        parameters = [
            {'name': 'fabric_type', 'label': 'Fabric Type', 'type': 'text'},
            {'name': 'fabric_gsm', 'label': 'Fabric GSM', 'type': 'number'},
            {'name': 'fabric_width', 'label': 'Fabric Width', 'type': 'number'},
            {'name': 'colors', 'label': 'Colors (comma-separated)', 'type': 'text'},
            {'name': 'dyeing_method', 'label': 'Dyeing Method', 'type': 'text'},
            {'name': 'packaging_method', 'label': 'Packaging Method', 'type': 'text'}
        ]
    elif product_type == 'Printed':
        parameters = [
            {'name': 'fabric_type', 'label': 'Fabric Type', 'type': 'text'},
            {'name': 'fabric_gsm', 'label': 'Fabric GSM', 'type': 'number'},
            {'name': 'fabric_width', 'label': 'Fabric Width', 'type': 'number'},
            {'name': 'print_design', 'label': 'Print Design', 'type': 'text'},
            {'name': 'print_type', 'label': 'Print Type', 'type': 'text'},
            {'name': 'colors', 'label': 'Colors (comma-separated)', 'type': 'text'},
            {'name': 'packaging_method', 'label': 'Packaging Method', 'type': 'text'}
        ]
    elif product_type == 'Denim':
        parameters = [
            {'name': 'fabric_type', 'label': 'Fabric Type', 'type': 'text'},
            {'name': 'fabric_gsm', 'label': 'Fabric GSM', 'type': 'number'},
            {'name': 'fabric_width', 'label': 'Fabric Width', 'type': 'number'},
            {'name': 'yarn_count', 'label': 'Yarn Count', 'type': 'text'},
            {'name': 'weave_type', 'label': 'Weave Type', 'type': 'text'},
            {'name': 'indigo_dye_level', 'label': 'Indigo Dye Level', 'type': 'text'},
            {'name': 'colors', 'label': 'Colors (comma-separated)', 'type': 'text'},
            {'name': 'packaging_method', 'label': 'Packaging Method', 'type': 'text'}
        ]
    return jsonify(parameters)

@product_bp.route('/customers')
@login_required
def customers():
    if not (current_user.is_admin() or current_user.has_permission('customers')):
        flash('You do not have permission to view customers!', 'danger')
        return redirect(url_for('dashboard.dashboard'))
    customers = Customer.query.all()
    for customer in customers:
        customer.rating = calculate_customer_rating(customer.id)
    db.session.commit()
    return render_template('customers.html', customers=customers)

@product_bp.route('/customer/add', methods=['GET', 'POST'])
@login_required
def add_customer():
    if not (current_user.is_admin() or current_user.has_permission('customers')):
        flash('You do not have permission to add customers!', 'danger')
        return redirect(url_for('dashboard.dashboard'))
    
    if request.method == 'POST':
        try:
            name = request.form.get('name')
            email = request.form.get('email')
            phone_number = request.form.get('phone_number')
            location_address = request.form.get('location_address')
            product_categories = [
                cat for cat in ['Knitted', 'Woven', 'Yarn', 'Garment', 'Dyed', 'Printed', 'Denim']
                if request.form.get(cat.lower()) == 'on'
            ]
            product_types = ','.join(product_categories) if product_categories else None

            if not name or not email:
                flash('Name and email are required!', 'danger')
                return redirect(url_for('product.add_customer'))

            new_customer = Customer(
                name=name,
                email=email,
                phone_number=phone_number,
                location_address=location_address,
                product_types=product_types
            )
            db.session.add(new_customer)
            db.session.commit()
            new_customer.rating = calculate_customer_rating(new_customer.id)
            db.session.commit()
            flash('Customer added successfully!', 'success')
            return redirect(url_for('product.customers'))
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error adding customer: {str(e)}")
            flash(f'Error adding customer: {str(e)}', 'danger')
            return redirect(url_for('product.add_customer'))
    
    return render_template('add_edit_customer.html', customer=None)

@product_bp.route('/customer/edit/<int:customer_id>', methods=['GET', 'POST'])
@login_required
def edit_customer(customer_id):
    if not (current_user.is_admin() or current_user.has_permission('customers')):
        flash('You do not have permission to edit customers!', 'danger')
        return redirect(url_for('dashboard.dashboard'))
    
    customer = Customer.query.get_or_404(customer_id)
    
    if request.method == 'POST':
        try:
            customer.name = request.form.get('name')
            customer.email = request.form.get('email')
            customer.phone_number = request.form.get('phone_number')
            customer.location_address = request.form.get('location_address')
            product_categories = [
                cat for cat in ['Knitted', 'Woven', 'Yarn', 'Garment', 'Dyed', 'Printed', 'Denim']
                if request.form.get(cat.lower()) == 'on'
            ]
            customer.product_types = ','.join(product_categories) if product_categories else None

            if not customer.name or not customer.email:
                flash('Name and email are required!', 'danger')
                return redirect(url_for('product.edit_customer', customer_id=customer_id))

            db.session.commit()
            customer.rating = calculate_customer_rating(customer_id)
            db.session.commit()
            flash('Customer updated successfully!', 'success')
            return redirect(url_for('product.customers'))
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error updating customer: {str(e)}")
            flash(f'Error updating customer: {str(e)}', 'danger')
            return redirect(url_for('product.edit_customer', customer_id=customer_id))
    
    return render_template('add_edit_customer.html', customer=customer)

@product_bp.route('/export_customers/<format>')
@login_required
def export_customers(format):
    if not (current_user.is_admin() or current_user.has_permission('customers')):
        flash('You do not have permission to export customers!', 'danger')
        return redirect(url_for('dashboard.dashboard'))
    
    customers = Customer.query.all()
    for customer in customers:
        customer.rating = calculate_customer_rating(customer.id)
    db.session.commit()

    if format == 'excel':
        data = [{
            'ID': c.id,
            'Name': c.name,
            'Email': c.email,
            'Phone Number': c.phone_number or 'N/A',
            'Location Address': c.location_address or 'N/A',
            'Product Types': c.product_types or 'N/A',
            'Rating': c.rating
        } for c in customers]
        df = pd.DataFrame(data)
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Customers')
        output.seek(0)
        return send_file(output, download_name='customers.xlsx', as_attachment=True)