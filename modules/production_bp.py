from flask import Blueprint, render_template, redirect, url_for, flash, request, Response
from flask_login import login_required
from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, SelectField, IntegerField, DateField, SubmitField
from wtforms.validators import DataRequired
from production_models import Machine, ProductionConfig, ProductionRecord, db
from production_bridge import get_production_data, get_duty_station_summary, calculate_plan
from reportlab.platypus import SimpleDocTemplate, Table
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from io import BytesIO

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

# Routes
@production_bp.route('/production', methods=['GET', 'POST'])
@login_required
def production():
    # Initialize both forms
    setup_form = MachineSetupForm()
    form = ProductionForm()  # Renamed to 'form' to match the template

    # Populate form choices
    setup_form.duty_station.choices = [(d.id, d.name) for d in db.session.query(db.Model).filter_by(__tablename__='duty_stations').all()]
    form.machine.choices = [(m.id, f"{m.name} ({m.process_type})") for m in Machine.query.all()]
    active_tab = request.args.get('tab', 'production')  # Default to 'production' tab

    # Handle Setup form submission
    if setup_form.validate_on_submit() and active_tab == 'setup':
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

    # Handle Production form submission
    if form.validate_on_submit() and active_tab == 'production':
        machine = Machine.query.get(form.machine.data)
        config = ProductionConfig.query.filter_by(duty_station_id=machine.duty_station_id).first()
        capacity = machine.manual_capacity or (machine.installed_capacity * machine.efficiency_factor * config.working_hours * config.working_days)
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

    # Prepare data for the Reporting tab
    machines = Machine.query.all()
    records = ProductionRecord.query.all()
    period = request.args.get('period', 'Monthly')
    data = [['Factory', 'Cost Center', 'UoM', 'Plan', 'Actual', '% Perf']]
    for record in get_production_data(period_type=period):
        machine = Machine.query.get(record.machine_id)
        ds = db.session.query(db.Model).filter_by(__tablename__='duty_stations').get(machine.duty_station_id)
        plan = calculate_plan(machine, period, record.start_date, record.end_date)
        perf = (record.actual_quantity / plan) * 100 if plan else 0
        data.append([ds.name, machine.process_type, record.uom, plan, record.actual_quantity, f"{perf:.1f}"])
    summary = get_duty_station_summary(period)

    # Render the template, ensuring both forms are passed
    return render_template('production.html', 
                          form=form, 
                          setup_form=setup_form,  # Ensure setup_form is passed
                          machines=machines, 
                          records=records, 
                          data=data, 
                          summary=summary, 
                          period=period, 
                          active_tab=active_tab, 
                          title='Production')

@production_bp.route('/production/reporting', methods=['GET'])
@login_required
def reporting():
    period = request.args.get('period', 'Monthly')
    records = get_production_data(period_type=period)
    summary = get_duty_station_summary(period)
    data = [['Factory', 'Cost Center', 'UoM', 'Plan', 'Actual', '% Perf']]
    for record in records:
        machine = Machine.query.get(record.machine_id)
        ds = db.session.query(db.Model).filter_by(__tablename__='duty_stations').get(machine.duty_station_id)
        plan = calculate_plan(machine, period, record.start_date, record.end_date)
        perf = (record.actual_quantity / plan) * 100 if plan else 0
        data.append([ds.name, machine.process_type, record.uom, plan, record.actual_quantity, f"{perf:.1f}"])
    
    if 'export' in request.args:
        output = BytesIO()
        doc = SimpleDocTemplate(output, pagesize=letter)
        table = Table(data)
        table.setStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ])
        doc.build([table])
        output.seek(0)
        return Response(output.getvalue(), mimetype='application/pdf', headers={'Content-Disposition': 'attachment;filename=production_report.pdf'})
    
    # Initialize forms for the template
    setup_form = MachineSetupForm()
    form = ProductionForm()
    setup_form.duty_station.choices = [(d.id, d.name) for d in db.session.query(db.Model).filter_by(__tablename__='duty_stations').all()]
    form.machine.choices = [(m.id, f"{m.name} ({m.process_type})") for m in Machine.query.all()]
    
    return render_template('production.html', 
                          form=form, 
                          setup_form=setup_form,  # Ensure setup_form is passed
                          machines=Machine.query.all(), 
                          records=ProductionRecord.query.all(), 
                          data=data, 
                          summary=summary, 
                          period=period, 
                          active_tab='reporting', 
                          title='Production')