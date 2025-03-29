from flask import Blueprint, render_template, redirect, url_for, flash, request, Response
from flask_login import login_required
from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, SelectField, IntegerField, DateField, SubmitField
from wtforms.validators import DataRequired
from .production_models import Machine, ProductionConfig, ProductionRecord, db
from .production_bridge import get_production_data, get_duty_station_summary, calculate_plan
from .models import DutyStation  # Import DutyStation from modules.models
from reportlab.platypus import SimpleDocTemplate, Table
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from io import BytesIO
import pandas as pd
from datetime import datetime
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from PIL import Image

# Define the blueprint first
production_bp = Blueprint('production', __name__)

# Setup Form
class MachineSetupForm(FlaskForm):
    name = StringField('Machine Name', validators=[DataRequired()])
    duty_station = SelectField('Duty Station', coerce=int)
    process_type = SelectField('Process Type', choices=[
        ('Spinning', 'Spinning'), ('Knitting', 'Knitting'), ('Dyeing', 'Dyeing'),
        ('Weaving', 'Weaving'), ('Printing', 'Printing'), ('Garment', 'Garment'),
        ('Denim', 'Denim')
    ])
    installed_capacity = FloatField('Installed Capacity', validators=[DataRequired()])
    efficiency_factor = FloatField('Efficiency Factor (0-1)', default=0.8)
    working_hours = FloatField('Working Hours/Day', default=8.0)
    working_days = IntegerField('Working Days/Period', default=25)
    manual_capacity = FloatField('Manual Capacity (Optional)')
    submit = SubmitField('Save Machine')

# Production Form
class ProductionForm(FlaskForm):
    machine = SelectField('Machine', coerce=int)
    period_type = SelectField('Period', choices=[
        ('Daily', 'Daily'), ('Weekly', 'Weekly'), ('Monthly', 'Monthly'),
        ('Quarterly', 'Quarterly'), ('Semi-Annual', 'Semi-Annual')
    ])
    start_date = DateField('Start Date', format='%Y-%m-%d', validators=[DataRequired()])
    end_date = DateField('End Date', format='%Y-%m-%d', validators=[DataRequired()])
    actual_quantity = FloatField('Actual Quantity', validators=[DataRequired()])
    uom = SelectField('Unit', choices=[('Kg', 'Kg'), ('Pcs', 'Pcs')])
    submit = SubmitField('Register Production')

# Routes (now defined after the blueprint)
@production_bp.route('/production', methods=['GET', 'POST'])
@login_required
def production():
    active_tab = request.args.get('tab', 'production')  # Default to 'production' tab
    print("DEBUG: Active tab:", active_tab)

    # Initialize both forms
    setup_form = MachineSetupForm()
    form = ProductionForm()

    # Debugging: Confirm forms are initialized
    print("DEBUG: setup_form initialized:", setup_form)
    print("DEBUG: form initialized:", form)

    # Populate form choices
    try:
        duty_stations = DutyStation.query.all()
        print("DEBUG: Duty stations retrieved:", [(d.id, d.name) for d in duty_stations])
        setup_form.duty_station.choices = [(d.id, d.name) for d in duty_stations]
        machines = Machine.query.all()
        print("DEBUG: Machines retrieved:", machines)
        form.machine.choices = [(m.id, f"{m.name} ({m.process_type})") for m in machines]
    except Exception as e:
        print(f"DEBUG: Error populating form choices: {e}")
        flash(f"Error populating form choices: {e}", 'danger')
        setup_form.duty_station.choices = [(0, 'None')]
        form.machine.choices = [(0, 'None')]

    # Handle Setup form submission
    if request.method == 'POST' and active_tab == 'setup':
        print("DEBUG: Setup form submitted with data:", setup_form.data)
        print("DEBUG: Setup form errors:", setup_form.errors)
        if setup_form.validate_on_submit():
            machine = Machine(
                name=setup_form.name.data,
                duty_station_id=setup_form.duty_station.data,
                process_type=setup_form.process_type.data,
                installed_capacity=setup_form.installed_capacity.data,
                efficiency_factor=setup_form.efficiency_factor.data,
                manual_capacity=setup_form.manual_capacity.data
            )
            config = ProductionConfig.query.filter_by(duty_station_id=setup_form.duty_station.data).first()
            if not config:
                config = ProductionConfig(
                    duty_station_id=setup_form.duty_station.data,
                    working_hours=setup_form.working_hours.data,
                    working_days=setup_form.working_days.data
                )
            db.session.add(machine)
            db.session.add(config)
            db.session.commit()
            flash('Machine setup completed!', 'success')
            return redirect(url_for('production.production', tab='setup'))
        else:
            flash('Form validation failed. Please check your inputs.', 'danger')

    # Handle Production form submission
    if request.method == 'POST' and active_tab == 'production':
        print("DEBUG: Production form submitted with data:", form.data)
        print("DEBUG: Production form errors:", form.errors)
        if form.validate_on_submit():
            machine = Machine.query.get(form.machine.data)
            config = ProductionConfig.query.filter_by(duty_station_id=machine.duty_station_id).first()
            if not config:
                flash('Production configuration not found for this machine’s duty station.', 'danger')
                return redirect(url_for('production.production', tab='production'))
            capacity = machine.manual_capacity or (machine.installed_capacity * machine.efficiency_factor * config.working_hours * config.working_days)
            if capacity == 0:
                flash('Capacity is zero. Please check machine configuration.', 'danger')
                return redirect(url_for('production.production', tab='production'))
            record = ProductionRecord(
                machine_id=form.machine.data,
                period_type=form.period_type.data,
                start_date=form.start_date.data,
                end_date=form.end_date.data,
                actual_quantity=form.actual_quantity.data,
                uom=form.uom.data,
                utilized_capacity=(form.actual_quantity.data / capacity) * 100
            )
            db.session.add(record)
            db.session.commit()
            flash('Production registered!', 'success')
            return redirect(url_for('production.production', tab='production'))
        else:
            flash('Form validation failed. Please check your inputs.', 'danger')

    # Prepare data for the templates
    machines = Machine.query.all()
    records = ProductionRecord.query.all()
    
    # Resolve machine names for production records
    records_with_machine_names = []
    for record in records:
        machine = Machine.query.get(record.machine_id)
        machine_name = machine.name if machine else 'Unknown'
        records_with_machine_names.append({
            'machine_name': machine_name,
            'period_type': record.period_type,
            'start_date': record.start_date,
            'end_date': record.end_date,
            'actual_quantity': record.actual_quantity,
            'uom': record.uom,
            'utilized_capacity': record.utilized_capacity
        })

    # Resolve duty station names for machines (for the setup tab)
    machines_with_duty_stations = []
    for machine in machines:
        ds = DutyStation.query.get(machine.duty_station_id)
        duty_station_name = ds.name if ds else 'Unknown'
        machines_with_duty_stations.append({
            'name': machine.name,
            'duty_station_name': duty_station_name,
            'process_type': machine.process_type,
            'installed_capacity': machine.installed_capacity
        })

    # Prepare data for the Reporting tab
    period = request.args.get('period', 'Monthly')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    # Filter records by date range if provided
    records_query = ProductionRecord.query.filter_by(period_type=period)
    if start_date and end_date:
        try:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            records_query = records_query.filter(
                ProductionRecord.start_date >= start_date,
                ProductionRecord.end_date <= end_date
            )
        except ValueError:
            flash('Invalid date format. Please use YYYY-MM-DD.', 'danger')

    filtered_records = records_query.all()

    # Prepare data for bar chart (Planned vs Actual by Process Type)
    process_types = set(m.process_type for m in machines)
    planned_values = []
    actual_values = []
    perf_values = []
    for process_type in process_types:
        process_machines = [m for m in machines if m.process_type == process_type]
        total_plan = 0
        total_actual = 0
        for machine in process_machines:
            config = ProductionConfig.query.filter_by(duty_station_id=machine.duty_station_id).first()
            if not config:
                continue
            capacity = machine.manual_capacity or (machine.installed_capacity * machine.efficiency_factor * config.working_hours * config.working_days)
            total_plan += capacity
            machine_records = [r for r in filtered_records if r.machine_id == machine.id]
            total_actual += sum(r.actual_quantity for r in machine_records)
        planned_values.append(total_plan)
        actual_values.append(total_actual)
        perf = (total_actual / total_plan * 100) if total_plan else 0
        perf_values.append(perf)

    # Calculate average performance
    average_performance = sum(perf_values) / len(perf_values) if perf_values else 0

    # Prepare data for production performance table
    data = [['Factory', 'Cost Center', 'UoM', 'Plan', 'Actual', '% Perf']]
    for record in filtered_records:
        machine = Machine.query.get(record.machine_id)
        ds = DutyStation.query.get(machine.duty_station_id) if machine else None
        plan = calculate_plan(machine, period, record.start_date, record.end_date)
        perf = (record.actual_quantity / plan) * 100 if plan else 0
        data.append([ds.name if ds else 'Unknown', machine.process_type if machine else 'Unknown', record.uom, plan, record.actual_quantity, f"{perf:.1f}"])

    # Prepare data for donut chart (Percent Contribution by Factory)
    factory_contributions = {}
    total_actual = sum(r.actual_quantity for r in filtered_records)
    for record in filtered_records:
        machine = Machine.query.get(record.machine_id)
        ds = DutyStation.query.get(machine.duty_station_id) if machine else None
        factory = ds.name if ds else 'Unknown'
        if factory not in factory_contributions:
            factory_contributions[factory] = 0
        factory_contributions[factory] += record.actual_quantity

    factory_labels = list(factory_contributions.keys())
    factory_contributions = [factory_contributions[factory] / total_actual * 100 if total_actual else 0 for factory in factory_labels]

    # Prepare summary by duty station
    summary = get_duty_station_summary(period)

    # Common template variables
    template_vars = {
        'form': form,
        'setup_form': setup_form,
        'machines': machines_with_duty_stations,
        'records': records_with_machine_names,
        'data': data,
        'summary': summary,
        'period': period,
        'start_date': start_date,
        'end_date': end_date,
        'process_types': list(process_types),
        'planned_values': planned_values,
        'actual_values': actual_values,
        'perf_values': perf_values,
        'average_performance': average_performance,
        'factory_labels': factory_labels,
        'factory_contributions': factory_contributions,
        'active_tab': active_tab,
        'title': 'Production'
    }

    return render_template('production.html', **template_vars)

@production_bp.route('/production/export/<format>', methods=['GET'])
@login_required
def export_report(format):
    period = request.args.get('period', 'Monthly')
    records = get_production_data(period_type=period)
    data = [['Factory', 'Cost Center', 'UoM', 'Plan', 'Actual', '% Perf']]
    for record in records:
        machine = Machine.query.get(record.machine_id)
        ds = DutyStation.query.get(machine.duty_station_id) if machine else None
        plan = calculate_plan(machine, period, record.start_date, record.end_date)
        perf = (record.actual_quantity / plan) * 100 if plan else 0
        data.append([ds.name if ds else 'Unknown', machine.process_type if machine else 'Unknown', record.uom, plan, record.actual_quantity, f"{perf:.1f}"])

    # Prepare data for charts (same as in the main route)
    machines = Machine.query.all()
    filtered_records = ProductionRecord.query.filter_by(period_type=period).all()
    process_types = set(m.process_type for m in machines)
    planned_values = []
    actual_values = []
    perf_values = []
    for process_type in process_types:
        process_machines = [m for m in machines if m.process_type == process_type]
        total_plan = 0
        total_actual = 0
        for machine in process_machines:
            config = ProductionConfig.query.filter_by(duty_station_id=machine.duty_station_id).first()
            if not config:
                continue
            capacity = machine.manual_capacity or (machine.installed_capacity * machine.efficiency_factor * config.working_hours * config.working_days)
            total_plan += capacity
            machine_records = [r for r in filtered_records if r.machine_id == machine.id]
            total_actual += sum(r.actual_quantity for r in machine_records)
        planned_values.append(total_plan)
        actual_values.append(total_actual)
        perf = (total_actual / total_plan * 100) if total_plan else 0
        perf_values.append(perf)

    factory_contributions = {}
    total_actual = sum(r.actual_quantity for r in filtered_records)
    for record in filtered_records:
        machine = Machine.query.get(record.machine_id)
        ds = DutyStation.query.get(machine.duty_station_id) if machine else None
        factory = ds.name if ds else 'Unknown'
        if factory not in factory_contributions:
            factory_contributions[factory] = 0
        factory_contributions[factory] += record.actual_quantity

    factory_labels = list(factory_contributions.keys())
    factory_contributions = [factory_contributions[factory] / total_actual * 100 if total_actual else 0 for factory in factory_labels]

    if format == 'pdf':
        # Render the page with charts to take screenshots
        html_content = render_template('production.html', 
            form=ProductionForm(), 
            setup_form=MachineSetupForm(), 
            machines=[],
            records=[],
            data=data,
            summary=get_duty_station_summary(period),
            period=period,
            start_date=None,
            end_date=None,
            process_types=list(process_types),
            planned_values=planned_values,
            actual_values=actual_values,
            perf_values=perf_values,
            average_performance=sum(perf_values) / len(perf_values) if perf_values else 0,
            factory_labels=factory_labels,
            factory_contributions=factory_contributions,
            active_tab='reporting',
            title='Production'
        )

        # Save HTML to a temporary file
        with open('temp.html', 'w', encoding='utf-8') as f:
            f.write(html_content)

        # Set up Selenium with headless Chrome
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--disable-gpu')
        driver = webdriver.Chrome(options=chrome_options)

        # Load the HTML file
        driver.get('file://' + os.path.abspath('temp.html'))
        driver.set_window_size(1280, 800)

        # Take screenshots of the charts
        bar_chart = driver.find_element_by_id('productionBarChart')
        bar_chart.screenshot('bar_chart.png')

        donut_chart = driver.find_element_by_id('factoryContributionChart')
        donut_chart.screenshot('donut_chart.png')

        driver.quit()

        # Generate PDF with charts
        output = BytesIO()
        doc = SimpleDocTemplate(output, pagesize=letter)
        elements = []

        # Add bar chart
        bar_img = Image.open('bar_chart.png')
        bar_img = Image('bar_chart.png', width=500, height=300)
        elements.append(bar_img)

        # Add donut chart
        donut_img = Image.open('donut_chart.png')
        donut_img = Image('donut_chart.png', width=300, height=300)
        elements.append(donut_img)

        # Add table
        table = Table(data)
        table.setStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ])
        elements.append(table)

        doc.build(elements)
        output.seek(0)

        # Clean up temporary files
        os.remove('temp.html')
        os.remove('bar_chart.png')
        os.remove('donut_chart.png')

        return Response(output.getvalue(), mimetype='application/pdf', headers={'Content-Disposition': 'attachment;filename=production_report.pdf'})
    
    elif format == 'excel':
        # For Excel, include chart data as a table
        df = pd.DataFrame(data[1:], columns=data[0])

        # Add chart data as additional sheets
        chart_data = pd.DataFrame({
            'Process Type': list(process_types),
            'Planned': planned_values,
            'Actual': actual_values,
            '% Perf': perf_values
        })
        factory_data = pd.DataFrame({
            'Factory': factory_labels,
            'Contribution (%)': factory_contributions
        })

        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='Production Report', index=False)
            chart_data.to_excel(writer, sheet_name='Bar Chart Data', index=False)
            factory_data.to_excel(writer, sheet_name='Donut Chart Data', index=False)
        output.seek(0)
        return Response(output.getvalue(), mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', headers={'Content-Disposition': 'attachment;filename=production_report.xlsx'})

    flash('Invalid export format.', 'danger')
    return redirect(url_for('production.production', tab='reporting'))