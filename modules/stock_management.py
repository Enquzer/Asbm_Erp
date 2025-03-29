from flask import Blueprint, render_template, request, jsonify, send_file
from flask_login import login_required, current_user
from database import db
from modules.stock_models import StockCategory, StockItem, StockTransaction, StockBalance
from modules.models import DutyStation
from datetime import datetime
import pandas as pd
from io import BytesIO
import matplotlib.pyplot as plt
import seaborn as sns
import base64
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet

stock_management_bp = Blueprint('stock_management', __name__)

@stock_management_bp.route('/')
@login_required
def stock_management():
    duty_stations = DutyStation.query.all()
    categories = StockCategory.query.all()
    items = StockItem.query.all()
    balances = StockBalance.query.all()
    current_period = datetime.now().strftime('%Y-%m')
    return render_template('stock_management.html', duty_stations=duty_stations, categories=categories, 
                           items=items, balances=balances, current_period=current_period)

@stock_management_bp.route('/add_item', methods=['POST'])
@login_required
def add_item():
    name = request.form.get('name')
    category_id = request.form.get('category_id')
    unit_of_measure = request.form.get('unit_of_measure')
    duty_station_id = request.form.get('duty_station_id')
    min_stock_level = request.form.get('min_stock_level', 0.0)
    item = StockItem(
        name=name, category_id=int(category_id), unit_of_measure=unit_of_measure,
        duty_station_id=int(duty_station_id), min_stock_level=float(min_stock_level)
    )
    db.session.add(item)
    db.session.commit()
    return jsonify({'message': 'Item added successfully', 'item_id': item.id})

@stock_management_bp.route('/record_transaction', methods=['POST'])
@login_required
def record_transaction():
    item_id = request.form.get('item_id')
    transaction_type = request.form.get('transaction_type')
    quantity = float(request.form.get('quantity'))
    unit_price = float(request.form.get('unit_price', 0.0))
    duty_station_id = request.form.get('duty_station_id')
    date_str = request.form.get('date', datetime.now().strftime('%Y-%m-%d'))
    date = datetime.strptime(date_str, '%Y-%m-%d')
    
    transaction = StockTransaction(
        item_id=int(item_id), transaction_type=transaction_type, quantity=quantity,
        unit_price=unit_price, total_value=quantity * unit_price, duty_station_id=int(duty_station_id),
        transaction_date=date
    )
    db.session.add(transaction)
    
    period = date.strftime('%Y-%m')
    balance = StockBalance.query.filter_by(item_id=item_id, period=period, duty_station_id=duty_station_id).first()
    if not balance:
        prev_period = (date.replace(day=1) - pd.Timedelta(days=1)).strftime('%Y-%m')
        prev_balance = StockBalance.query.filter_by(item_id=item_id, period=prev_period, duty_station_id=duty_station_id).first()
        beginning_quantity = prev_balance.ending_quantity if prev_balance else 0.0
        beginning_value = prev_balance.ending_value if prev_balance else 0.0
        balance = StockBalance(item_id=item_id, duty_station_id=duty_station_id, period=period,
                               beginning_quantity=beginning_quantity, beginning_value=beginning_value)
        db.session.add(balance)
    
    if transaction_type == 'IN':
        balance.ending_quantity = balance.beginning_quantity + quantity
        balance.ending_value = balance.beginning_value + (quantity * unit_price)
    elif transaction_type == 'OUT':
        balance.ending_quantity = balance.beginning_quantity - quantity
        balance.ending_value = balance.beginning_value - (quantity * unit_price)
    db.session.commit()
    return jsonify({'message': 'Transaction recorded successfully'})

@stock_management_bp.route('/upload_excel', methods=['POST'])
@login_required
def upload_excel():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    df = pd.read_excel(file)
    for _, row in df.iterrows():
        item_name = row['Item']
        duty_station_name = row['Duty Station']
        category_name = row.get('Category', 'Uncategorized')
        transaction_type = row['Transaction Type']
        quantity = float(row['Quantity'])
        unit_price = float(row.get('Unit Price', 0.0))
        date_str = row['Date']
        date = pd.to_datetime(date_str).to_pydatetime()

        duty_station = DutyStation.query.filter_by(name=duty_station_name).first()
        if not duty_station:
            duty_station = DutyStation(name=duty_station_name)
            db.session.add(duty_station)
            db.session.commit()

        category = StockCategory.query.filter_by(name=category_name).first()
        if not category:
            category = StockCategory(name=category_name)
            db.session.add(category)
            db.session.commit()

        item = StockItem.query.filter_by(name=item_name, duty_station_id=duty_station.id).first()
        if not item:
            item = StockItem(name=item_name, category_id=category.id, unit_of_measure='unit', duty_station_id=duty_station.id)
            db.session.add(item)
            db.session.commit()

        transaction = StockTransaction(
            item_id=item.id, transaction_type=transaction_type, quantity=quantity,
            unit_price=unit_price, total_value=quantity * unit_price, duty_station_id=duty_station.id,
            transaction_date=date
        )
        db.session.add(transaction)

        period = date.strftime('%Y-%m')
        balance = StockBalance.query.filter_by(item_id=item.id, period=period, duty_station_id=duty_station.id).first()
        if not balance:
            prev_period = (date.replace(day=1) - pd.Timedelta(days=1)).strftime('%Y-%m')
            prev_balance = StockBalance.query.filter_by(item_id=item.id, period=prev_period, duty_station_id=duty_station.id).first()
            beginning_quantity = prev_balance.ending_quantity if prev_balance else 0.0
            beginning_value = prev_balance.ending_value if prev_balance else 0.0
            balance = StockBalance(item_id=item.id, duty_station_id=duty_station.id, period=period,
                                   beginning_quantity=beginning_quantity, beginning_value=beginning_value)
            db.session.add(balance)

        if transaction_type == 'IN':
            balance.ending_quantity = balance.beginning_quantity + quantity
            balance.ending_value = balance.beginning_value + (quantity * unit_price)
        elif transaction_type == 'OUT':
            balance.ending_quantity = balance.beginning_quantity - quantity
            balance.ending_value = balance.beginning_value - (quantity * unit_price)

    db.session.commit()
    return jsonify({'message': 'Excel data uploaded successfully'})

@stock_management_bp.route('/report', methods=['GET'])
@login_required
def report():
    duty_station_id = request.args.get('duty_station_id')
    filter_type = request.args.get('filter_type', 'month')
    period = request.args.get('period', datetime.now().strftime('%Y-%m'))
    
    if filter_type == 'year':
        balances = StockBalance.query.filter(StockBalance.period.like(f'{period}%'), 
                                             StockBalance.duty_station_id == (duty_station_id if duty_station_id else StockBalance.duty_station_id)).all()
    elif filter_type == 'quarter':
        year, quarter = period.split('-Q')
        start_month = (int(quarter) - 1) * 3 + 1
        end_month = start_month + 2
        balances = StockBalance.query.filter(StockBalance.period.between(f'{year}-{start_month:02d}', f'{year}-{end_month:02d}'),
                                             StockBalance.duty_station_id == (duty_station_id if duty_station_id else StockBalance.duty_station_id)).all()
    elif filter_type == 'daily':
        balances = StockBalance.query.join(StockTransaction).filter(StockTransaction.transaction_date == period,
                                                                    StockBalance.duty_station_id == (duty_station_id if duty_station_id else StockBalance.duty_station_id)).all()
    else:  # month
        balances = StockBalance.query.filter_by(period=period, duty_station_id=duty_station_id).all() if duty_station_id else StockBalance.query.filter_by(period=period).all()

    data = [{'Item': b.item.name, 'Duty Station': b.duty_station.name, 'Beginning Qty': b.beginning_quantity,
             'Beginning Value': b.beginning_value, 'Ending Qty': b.ending_quantity, 'Ending Value': b.ending_value}
            for b in balances]
    df = pd.DataFrame(data)
    
    plt.figure(figsize=(12, 6))
    sns.set_style("whitegrid")
    sns.barplot(x='Duty Station', y='Ending Value', hue='Item', data=df, palette="viridis")
    plt.title(f"Stock Value by Duty Station ({period})", fontsize=16, pad=20)
    plt.xlabel("Duty Station", fontsize=12)
    plt.ylabel("Ending Value (ETB)", fontsize=12)
    plt.legend(title="Item", bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.tight_layout()
    buf = BytesIO()
    plt.savefig(buf, format='png', dpi=100)
    bar_chart = base64.b64encode(buf.getvalue()).decode('utf-8')
    plt.close()
    
    return jsonify({'data': data, 'bar_chart': bar_chart})

@stock_management_bp.route('/export_excel', methods=['GET'])
@login_required
def export_excel():
    duty_station_id = request.args.get('duty_station_id')
    period = request.args.get('period', datetime.now().strftime('%Y-%m'))
    filter_type = request.args.get('filter_type', 'month')
    
    if filter_type == 'year':
        balances = StockBalance.query.filter(StockBalance.period.like(f'{period}%'), 
                                             StockBalance.duty_station_id == (duty_station_id if duty_station_id else StockBalance.duty_station_id)).all()
    elif filter_type == 'quarter':
        year, quarter = period.split('-Q')
        start_month = (int(quarter) - 1) * 3 + 1
        end_month = start_month + 2
        balances = StockBalance.query.filter(StockBalance.period.between(f'{year}-{start_month:02d}', f'{year}-{end_month:02d}'),
                                             StockBalance.duty_station_id == (duty_station_id if duty_station_id else StockBalance.duty_station_id)).all()
    elif filter_type == 'daily':
        balances = StockBalance.query.join(StockTransaction).filter(StockTransaction.transaction_date == period,
                                                                    StockBalance.duty_station_id == (duty_station_id if duty_station_id else StockBalance.duty_station_id)).all()
    else:
        balances = StockBalance.query.filter_by(period=period).all()

    data = [{'Item': b.item.name, 'Duty Station': b.duty_station.name, 'Beginning Qty': b.beginning_quantity,
             'Beginning Value': b.beginning_value, 'Ending Qty': b.ending_quantity, 'Ending Value': b.ending_value}
            for b in balances]
    df = pd.DataFrame(data)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        for ds in DutyStation.query.all():
            ds_data = df[df['Duty Station'] == ds.name]
            ds_data.to_excel(writer, sheet_name=ds.name, index=False)
        df.to_excel(writer, sheet_name='Summary', index=False)
    output.seek(0)
    return send_file(output, download_name=f'stock_{period}.xlsx', as_attachment=True)

@stock_management_bp.route('/export_pdf', methods=['GET'])
@login_required
def export_pdf():
    duty_station_id = request.args.get('duty_station_id')
    period = request.args.get('period', datetime.now().strftime('%Y-%m'))
    filter_type = request.args.get('filter_type', 'month')
    
    if filter_type == 'year':
        balances = StockBalance.query.filter(StockBalance.period.like(f'{period}%'), 
                                             StockBalance.duty_station_id == (duty_station_id if duty_station_id else StockBalance.duty_station_id)).all()
    elif filter_type == 'quarter':
        year, quarter = period.split('-Q')
        start_month = (int(quarter) - 1) * 3 + 1
        end_month = start_month + 2
        balances = StockBalance.query.filter(StockBalance.period.between(f'{year}-{start_month:02d}', f'{year}-{end_month:02d}'),
                                             StockBalance.duty_station_id == (duty_station_id if duty_station_id else StockBalance.duty_station_id)).all()
    elif filter_type == 'daily':
        balances = StockBalance.query.join(StockTransaction).filter(StockTransaction.transaction_date == period,
                                                                    StockBalance.duty_station_id == (duty_station_id if duty_station_id else StockBalance.duty_station_id)).all()
    else:
        balances = StockBalance.query.filter_by(period=period).all()

    data = [['Item', 'Duty Station', 'Beginning Qty', 'Beginning Value', 'Ending Qty', 'Ending Value']]
    data.extend([b.item.name, b.duty_station.name, b.beginning_quantity, b.beginning_value, b.ending_quantity, b.ending_value] for b in balances)

    output = BytesIO()
    doc = SimpleDocTemplate(output, pagesize=letter)
    elements = []

    styles = getSampleStyleSheet()
    elements.append(Paragraph(f"Stock Report ({period})", styles['Title']))
    elements.append(Spacer(1, 12))

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
    elements.append(table)
    doc.build(elements)
    output.seek(0)
    return send_file(output, download_name=f'stock_{period}.pdf', as_attachment=True)