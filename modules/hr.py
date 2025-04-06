from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, send_file, current_app
from flask_login import login_required, current_user
from database import db
from modules.models import Employee, DutyStation, Overtime, Attendance, AnnualLeave, EmploymentLetter, Contract, Position
from modules.forms import EmployeeForm
from flask_wtf.csrf import validate_csrf, CSRFError
from werkzeug.utils import secure_filename
from datetime import datetime, date
import os
import logging
from sqlalchemy.exc import OperationalError, IntegrityError
import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from io import BytesIO
import qrcode
import cv2
import numpy as np

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

hr_bp = Blueprint('hr', __name__, url_prefix='/hr')

# Ensure upload directories exist
def ensure_upload_dirs():
    photo_dir = os.path.join('static', 'uploads', 'employee_photos')
    cv_dir = os.path.join('static', 'uploads', 'employee_cvs')
    letter_dir = os.path.join('static', 'uploads', 'letters')
    contract_dir = os.path.join('static', 'uploads', 'contracts')
    for d in [photo_dir, cv_dir, letter_dir, contract_dir]:
        os.makedirs(d, exist_ok=True)
    return photo_dir, cv_dir, letter_dir, contract_dir

# Generate PDF function
def generate_pdf(content, file_path):
    c = canvas.Canvas(file_path, pagesize=letter)
    width, height = letter
    c.drawString(100, height - 50, "ASBM ERP Document")
    text = c.beginText(100, height - 100)
    text.setFont("Helvetica", 12)
    for line in content.split('\n'):
        text.textLine(line)
    c.drawText(text)
    c.save()

@hr_bp.route('/employees_by_duty_station', methods=['GET'])
@login_required
def employees_by_duty_station():
    duty_station_id = request.args.get('duty_station_id')
    if not duty_station_id:
        return jsonify({'employees': []})
    employees = Employee.query.filter_by(duty_station_id=int(duty_station_id), management_status='Active').all()
    return jsonify({'employees': [{'id': emp.id, 'name': emp.name} for emp in employees]})

@hr_bp.route('/', methods=['GET', 'POST'])
@login_required
def hr():
    if not current_user.has_permission('hr'):
        flash('No permission for HR module.', 'danger')
        return redirect(url_for('dashboard.dashboard'))

    form = EmployeeForm()
    duty_stations = DutyStation.query.all()
    positions = Position.query.all()
    active_employees = Employee.query.filter_by(management_status='Active').all()
    form.duty_station_id.choices = [(ds.id, ds.name) for ds in duty_stations]
    form.manager_id.choices = [(0, 'None')] + [(emp.id, emp.name) for emp in active_employees]
    form.position_id.choices = [(0, 'None')] + [(pos.id, pos.title) for pos in positions]

    tab = request.args.get('tab', 'employees')
    search_name = request.args.get('search_name', '')
    duty_station_id = request.args.get('duty_station_id', 'all')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    gender = request.args.get('gender', 'all')
    department = request.args.get('department', 'all')

    departments = sorted(set(emp.department for emp in Employee.query.all() if emp.department))

    # Filter queries
    emp_query = Employee.query
    if search_name:
        emp_query = emp_query.filter(Employee.name.ilike(f'%{search_name}%'))
    if duty_station_id != 'all':
        emp_query = emp_query.filter(Employee.duty_station_id == int(duty_station_id))
    if start_date:
        try:
            emp_query = emp_query.filter(Employee.hire_date >= datetime.strptime(start_date, '%Y-%m-%d'))
        except ValueError:
            flash('Invalid start date format.', 'danger')
            start_date = ''
    if end_date:
        try:
            emp_query = emp_query.filter(Employee.hire_date <= datetime.strptime(end_date, '%Y-%m-%d'))
        except ValueError:
            flash('Invalid end date format.', 'danger')
            end_date = ''
    if gender != 'all':
        emp_query = emp_query.filter(Employee.gender == gender)
    if department != 'all':
        emp_query = emp_query.filter(Employee.department == department)
    employees = emp_query.all()

    # Modified query to explicitly specify the join condition
    ot_query = Overtime.query.join(Employee, Overtime.employee_id == Employee.id)
    att_query = Attendance.query.join(Employee, Attendance.employee_id == Employee.id)
    leave_query = AnnualLeave.query.join(Employee, AnnualLeave.employee_id == Employee.id)
    letter_query = EmploymentLetter.query.join(Employee, EmploymentLetter.employee_id == Employee.id)
    contract_query = Contract.query.join(Employee, Contract.employee_id == Employee.id)
    pos_query = Position.query

    if duty_station_id != 'all':
        ot_query = ot_query.filter(Employee.duty_station_id == int(duty_station_id))
        att_query = att_query.filter(Employee.duty_station_id == int(duty_station_id))
        leave_query = leave_query.filter(Employee.duty_station_id == int(duty_station_id))
        letter_query = letter_query.filter(Employee.duty_station_id == int(duty_station_id))
        contract_query = contract_query.filter(Employee.duty_station_id == int(duty_station_id))
        pos_query = pos_query.filter(Position.duty_station_id == int(duty_station_id))

    if start_date:
        try:
            start = datetime.strptime(start_date, '%Y-%m-%d')
            ot_query = ot_query.filter(Overtime.date >= start)
            att_query = att_query.filter(Attendance.date >= start)
            leave_query = leave_query.filter(AnnualLeave.start_date >= start)
            letter_query = letter_query.filter(EmploymentLetter.created_at >= start)
            contract_query = contract_query.filter(Contract.start_date >= start)
        except ValueError:
            pass
    if end_date:
        try:
            end = datetime.strptime(end_date, '%Y-%m-%d')
            ot_query = ot_query.filter(Overtime.date <= end)
            att_query = att_query.filter(Attendance.date <= end)
            leave_query = leave_query.filter(AnnualLeave.end_date <= end)
            letter_query = letter_query.filter(EmploymentLetter.created_at <= end)
            contract_query = contract_query.filter(Contract.end_date <= end)
        except ValueError:
            pass

    # Debug: Print the query to inspect the SQL
    print("Overtime Query:", ot_query)

    overtime_records = ot_query.all()
    attendance_records = att_query.all()
    leave_records = leave_query.all()
    letters = letter_query.all()
    contracts = contract_query.all()
    positions = pos_query.all()

    # Chart data generation
    chart_data = {'title': '', 'type': 'bar', 'labels': [], 'datasets': [], 'data': [], 'backgroundColor': '#000000'}
    if tab == 'employees':
        emp_by_month = {ds.name: {f"{i+1}": 0 for i in range(12)} for ds in duty_stations}
        for emp in employees:
            if emp.duty_station_id and emp.hire_date:
                ds = DutyStation.query.get(emp.duty_station_id)
                emp_by_month[ds.name][f"{emp.hire_date.month}"] += 1
        chart_data = {
            'title': 'Employee Count by Month per Duty Station',
            'type': 'line',
            'labels': [f"Month {i+1}" for i in range(12)],
            'datasets': [
                {'label': ds_name, 'data': list(months.values()), 'borderColor': f'rgba({i*50 % 255}, {i*100 % 255}, {i*150 % 255}, 1)', 'fill': False}
                for i, (ds_name, months) in enumerate(emp_by_month.items())
            ]
        }
    elif tab == 'overtime':
        ot_by_ds = {ds.name: 0 for ds in duty_stations}
        for ot in overtime_records:
            if ot.employee.duty_station_id:
                ot_by_ds[ot.employee.duty_station.name] += ot.hours
        chart_data = {
            'title': 'Total Overtime Hours by Duty Station',
            'type': 'bar',
            'labels': list(ot_by_ds.keys()),
            'data': list(ot_by_ds.values()),
            'backgroundColor': 'rgba(255, 99, 132, 0.6)'
        }
    elif tab == 'attendance':
        att_by_ds = {ds.name: {'Present': 0, 'Late': 0, 'Absent': 0} for ds in duty_stations}
        for att in attendance_records:
            if att.employee.duty_station_id:
                att_by_ds[att.employee.duty_station.name][att.status] += 1
        chart_data = {
            'title': 'Attendance Status by Duty Station',
            'type': 'bar',
            'labels': list(att_by_ds.keys()),
            'datasets': [
                {'label': 'Present', 'data': [data['Present'] for data in att_by_ds.values()], 'backgroundColor': '#36A2EB'},
                {'label': 'Late', 'data': [data['Late'] for data in att_by_ds.values()], 'backgroundColor': '#FFCE56'},
                {'label': 'Absent', 'data': [data['Absent'] for data in att_by_ds.values()], 'backgroundColor': '#FF6384'}
            ]
        }
    elif tab == 'leave':
        leave_by_ds = {ds.name: {'Pending': 0, 'Approved': 0, 'Rejected': 0} for ds in duty_stations}
        for leave in leave_records:
            if leave.employee.duty_station_id:
                leave_by_ds[leave.employee.duty_station.name][leave.status] += 1
        chart_data = {
            'title': 'Leave Status by Duty Station',
            'type': 'bar',
            'labels': list(leave_by_ds.keys()),
            'datasets': [
                {'label': 'Pending', 'data': [data['Pending'] for data in leave_by_ds.values()], 'backgroundColor': '#FFCE56'},
                {'label': 'Approved', 'data': [data['Approved'] for data in leave_by_ds.values()], 'backgroundColor': '#36A2EB'},
                {'label': 'Rejected', 'data': [data['Rejected'] for data in leave_by_ds.values()], 'backgroundColor': '#FF6384'}
            ]
        }
    elif tab == 'letters':
        letter_types = set(letter.letter_type for letter in letters)
        letter_by_ds = {ds.name: {lt: 0 for lt in letter_types} for ds in duty_stations}
        for letter in letters:
            if letter.employee.duty_station_id:
                letter_by_ds[letter.employee.duty_station.name][letter.letter_type] += 1
        chart_data = {
            'title': 'Letters by Type per Duty Station',
            'type': 'bar',
            'labels': list(letter_by_ds.keys()),
            'datasets': [
                {'label': lt, 'data': [data[lt] for data in letter_by_ds.values()], 'backgroundColor': f'rgba({i*50 % 255}, {i*100 % 255}, {i*150 % 255}, 0.6)'}
                for i, lt in enumerate(letter_types)
            ]
        }
    elif tab == 'contracts':
        contract_by_ds = {ds.name: {'Active': 0, 'Expired': 0} for ds in duty_stations}
        for contract in contracts:
            if contract.employee.duty_station_id:
                status = 'Active' if (contract.end_date is None or contract.end_date > date.today()) else 'Expired'
                contract_by_ds[contract.employee.duty_station.name][status] += 1
        chart_data = {
            'title': 'Contract Status by Duty Station',
            'type': 'bar',
            'labels': list(contract_by_ds.keys()),
            'datasets': [
                {'label': 'Active', 'data': [data['Active'] for data in contract_by_ds.values()], 'backgroundColor': '#36A2EB'},
                {'label': 'Expired', 'data': [data['Expired'] for data in contract_by_ds.values()], 'backgroundColor': '#FF6384'}
            ]
        }
    elif tab == 'positions':
        pos_by_ds = {ds.name: 0 for ds in duty_stations}
        for pos in positions:
            if pos.duty_station_id:
                pos_by_ds[pos.duty_station.name] += 1
        chart_data = {
            'title': 'Positions by Duty Station',
            'type': 'bar',
            'labels': list(pos_by_ds.keys()),
            'data': list(pos_by_ds.values()),
            'backgroundColor': 'rgba(75, 192, 192, 0.2)'
        }

    # POST handling
    if request.method == 'POST':
        try:
            validate_csrf(request.form.get('csrf_token'))
        except CSRFError:
            logger.error("CSRF validation failed")
            return jsonify({'status': 'error', 'message': 'Invalid CSRF token.'}), 403

        action = request.form.get('action')
        photo_dir, cv_dir, letter_dir, contract_dir = ensure_upload_dirs()
        logger.debug(f"POST action: {action}, form data: {request.form}")

        if action == 'add_employee':
            if not form.validate_on_submit():
                errors = {field: errors[0] for field, errors in form.errors.items()}
                logger.error(f"Form validation failed: {errors}")
                return jsonify({'status': 'error', 'message': 'Form validation failed.', 'errors': errors}), 400

            photo_path = None
            if form.photo.data:
                photo = form.photo.data
                photo_filename = secure_filename(f"{form.name.data}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{photo.filename}")
                photo_path = os.path.join(photo_dir, photo_filename)
                photo.save(photo_path)

            cv_path = None
            if form.cv.data:
                cv = form.cv.data
                cv_filename = secure_filename(f"{form.name.data}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{cv.filename}")
                cv_path = os.path.join(cv_dir, cv_filename)
                cv.save(cv_path)

            try:
                employee = Employee(
                    name=form.name.data,
                    address_woreda=form.address_woreda.data,
                    address_kifle_ketema=form.address_kifle_ketema.data,
                    phone_number=form.phone_number.data,
                    emergency_contact_name=form.emergency_contact_name.data,
                    emergency_contact_phone=form.emergency_contact_phone.data,
                    photo_path=photo_path,
                    cv_path=cv_path,
                    manager_id=form.manager_id.data if form.manager_id.data != 0 else None,
                    position_id=form.position_id.data if form.position_id.data != 0 else None,
                    badge_id=form.badge_id.data,
                    location=form.location.data,
                    birth_date=form.birth_date.data,
                    hire_date=form.hire_date.data,
                    internal_notes=form.internal_notes.data,
                    monthly_salary=form.monthly_salary.data or 0.0,
                    additional_benefits=form.additional_benefits.data or 0.0,
                    title=form.job_title.data,
                    gender=form.gender.data,
                    department=form.department.data,
                    contract_end_date=form.contract_end_date.data,
                    seniority=form.seniority.data or 0,
                    management_status=form.management_status.data or 'Active',
                    job_grade=form.job_grade.data,
                    step=form.step.data or 0,
                    travel_allowance=form.travel_allowance.data or 0.0,
                    other_allowance=form.other_allowance.data or 0.0,
                    non_taxable_allowance=form.non_taxable_allowance.data or 0.0,
                    other_deduction=form.other_deduction.data or 0.0,
                    lunch_deduction_employee=form.lunch_deduction_employee.data or 0.0,
                    lunch_deduction_court=form.lunch_deduction_court.data or 0.0,
                    duty_station_id=form.duty_station_id.data,
                    basic_salary=form.monthly_salary.data or 0.0
                )
                db.session.add(employee)
                db.session.commit()
                logger.info(f"Employee {employee.name} added successfully")
                return jsonify({'status': 'success', 'message': f'Employee {employee.name} added successfully.'})
            except IntegrityError as e:
                db.session.rollback()
                error_field = str(e).split("NOT NULL constraint failed: ")[1] if "NOT NULL" in str(e) else str(e)
                logger.error(f"IntegrityError adding employee: {error_field}")
                return jsonify({'status': 'error', 'message': f'Missing required field: {error_field}'}), 400
            except OperationalError as e:
                db.session.rollback()
                logger.error(f"OperationalError adding employee: {str(e)}")
                return jsonify({'status': 'error', 'message': f'Database error: {str(e)}'}), 500

        elif action == 'modify_employee':
            employee_id = request.form.get('employee_id')
            employee = Employee.query.get(employee_id)
            if not employee:
                logger.error(f"Employee {employee_id} not found")
                return jsonify({'status': 'error', 'message': 'Employee not found.'}), 404
            try:
                employee.name = request.form.get('name')
                employee.phone_number = request.form.get('phone_number')
                employee.monthly_salary = float(request.form.get('monthly_salary', 0.0))
                employee.basic_salary = float(request.form.get('monthly_salary', 0.0))
                employee.hire_date = datetime.strptime(request.form.get('hire_date'), '%Y-%m-%d').date()
                employee.title = request.form.get('job_title')
                employee.department = request.form.get('department')
                employee.duty_station_id = int(request.form.get('duty_station_id'))
                employee.manager_id = int(request.form.get('manager_id')) if request.form.get('manager_id') != '0' else None
                employee.badge_id = request.form.get('badge_id')
                db.session.commit()
                logger.info(f"Employee {employee.name} updated successfully")
                return jsonify({'status': 'success', 'message': f'Employee {employee.name} updated successfully.'})
            except Exception as e:
                db.session.rollback()
                logger.error(f"Error updating employee {employee_id}: {str(e)}")
                return jsonify({'status': 'error', 'message': f'Error updating employee: {str(e)}'}), 500

        elif action == 'delete_employee':
            employee_id = request.form.get('employee_id')
            employee = Employee.query.get(employee_id)
            if not employee:
                logger.error(f"Employee {employee_id} not found")
                return jsonify({'status': 'error', 'message': 'Employee not found.'}), 404
            try:
                employee.management_status = 'Inactive'
                employee.contract_end_date = employee.contract_end_date or date.today()
                db.session.commit()
                logger.info(f"Employee {employee.name} terminated")
                return jsonify({'status': 'success', 'message': f'Employee {employee.name} terminated.'})
            except Exception as e:
                db.session.rollback()
                logger.error(f"Error deleting employee {employee_id}: {str(e)}")
                return jsonify({'status': 'error', 'message': f'Error terminating employee: {str(e)}'}), 500

        elif action == 'add_overtime':
            try:
                ot = Overtime(
                    employee_id=int(request.form.get('employee_id')),
                    date=datetime.strptime(request.form.get('date'), '%Y-%m-%d').date(),
                    hours=float(request.form.get('hours')),
                    rate=float(request.form.get('rate', 1.5))
                )
                db.session.add(ot)
                db.session.commit()
                logger.info(f"Overtime added for employee {ot.employee_id}")
                return jsonify({'status': 'success', 'message': 'Overtime added successfully.'})
            except Exception as e:
                db.session.rollback()
                logger.error(f"Error adding overtime: {str(e)}")
                return jsonify({'status': 'error', 'message': f'Error adding overtime: {str(e)}'}), 500

        elif action == 'add_attendance':
            try:
                att = Attendance(
                    employee_id=int(request.form.get('employee_id')),
                    date=datetime.strptime(request.form.get('date'), '%Y-%m-%d').date(),
                    check_in=datetime.strptime(request.form.get('check_in'), '%Y-%m-%dT%H:%M') if request.form.get('check_in') else None,
                    check_out=datetime.strptime(request.form.get('check_out'), '%Y-%m-%dT%H:%M') if request.form.get('check_out') else None,
                    badge_id=request.form.get('badge_id'),
                    status=request.form.get('status', 'Present')
                )
                db.session.add(att)
                db.session.commit()
                logger.info(f"Attendance added for employee {att.employee_id}")
                return jsonify({'status': 'success', 'message': 'Attendance recorded successfully.'})
            except Exception as e:
                db.session.rollback()
                logger.error(f"Error adding attendance: {str(e)}")
                return jsonify({'status': 'error', 'message': f'Error adding attendance: {str(e)}'}), 500

        elif action == 'add_leave':
            try:
                start = datetime.strptime(request.form.get('start_date'), '%Y-%m-%d').date()
                end = datetime.strptime(request.form.get('end_date'), '%Y-%m-%d').date()
                leave = AnnualLeave(
                    employee_id=int(request.form.get('employee_id')),
                    start_date=start,
                    end_date=end,
                    total_days=(end - start).days + 1,
                    status=request.form.get('status', 'Pending')
                )
                db.session.add(leave)
                db.session.commit()
                logger.info(f"Leave added for employee {leave.employee_id}")
                return jsonify({'status': 'success', 'message': 'Leave request added successfully.'})
            except Exception as e:
                db.session.rollback()
                logger.error(f"Error adding leave: {str(e)}")
                return jsonify({'status': 'error', 'message': f'Error adding leave: {str(e)}'}), 500

        elif action == 'add_letter':
            try:
                content = request.form.get('content')
                letter = EmploymentLetter(
                    employee_id=int(request.form.get('employee_id')),
                    letter_type=request.form.get('letter_type'),
                    content=content,
                    created_at=datetime.now()
                )
                db.session.add(letter)
                db.session.flush()  # Get ID before PDF generation
                file_path = os.path.join(letter_dir, f"letter_{letter.id}.pdf")
                generate_pdf(content, file_path)
                letter.file_path = file_path
                if letter.letter_type == 'Termination':
                    employee = Employee.query.get(letter.employee_id)
                    if employee:
                        employee.management_status = 'Inactive'
                        employee.contract_end_date = employee.contract_end_date or date.today()
                db.session.commit()
                logger.info(f"Letter {letter.id} added for employee {letter.employee_id}")
                return jsonify({'status': 'success', 'message': 'Letter generated successfully.'})
            except Exception as e:
                db.session.rollback()
                logger.error(f"Error adding letter: {str(e)}")
                return jsonify({'status': 'error', 'message': f'Error adding letter: {str(e)}'}), 500

        elif action == 'add_contract':
            try:
                content = request.form.get('content')
                contract = Contract(
                    employee_id=int(request.form.get('employee_id')),
                    title=request.form.get('title'),
                    content=content,
                    start_date=datetime.strptime(request.form.get('start_date'), '%Y-%m-%d').date(),
                    end_date=datetime.strptime(request.form.get('end_date'), '%Y-%m-%d').date() if request.form.get('end_date') else None
                )
                db.session.add(contract)
                db.session.flush()  # Get ID before PDF generation
                file_path = os.path.join(contract_dir, f"contract_{contract.id}.pdf")
                generate_pdf(content, file_path)
                contract.file_path = file_path
                db.session.commit()
                logger.info(f"Contract {contract.id} added for employee {contract.employee_id}")
                return jsonify({'status': 'success', 'message': 'Contract generated successfully.'})
            except Exception as e:
                db.session.rollback()
                logger.error(f"Error adding contract: {str(e)}")
                return jsonify({'status': 'error', 'message': f'Error adding contract: {str(e)}'}), 500

        elif action == 'add_position':
            try:
                pos = Position(
                    title=request.form.get('title'),
                    description=request.form.get('description'),
                    department=request.form.get('department'),
                    salary_range_min=float(request.form.get('salary_range_min')),
                    salary_range_max=float(request.form.get('salary_range_max')),
                    duty_station_id=int(request.form.get('duty_station_id')) if request.form.get('duty_station_id') else None
                )
                db.session.add(pos)
                db.session.commit()
                logger.info(f"Position {pos.title} added successfully")
                return jsonify({'status': 'success', 'message': 'Position added successfully.'})
            except Exception as e:
                db.session.rollback()
                logger.error(f"Error adding position: {str(e)}")
                return jsonify({'status': 'error', 'message': f'Error adding position: {str(e)}'}), 500

        logger.error(f"Invalid action: {action}")
        return jsonify({'status': 'error', 'message': 'Invalid action.'}), 400

    return render_template('hr.html', form=form, employees=employees, duty_stations=duty_stations,
                           overtime_records=overtime_records, attendance_records=attendance_records,
                           leave_records=leave_records, letters=letters, contracts=contracts, positions=positions,
                           chart_data=chart_data, departments=departments,
                           tab=tab, search_name=search_name, duty_station_id=duty_station_id,
                           start_date=start_date, end_date=end_date, gender=gender, department=department)

@hr_bp.route('/dashboard', methods=['GET'])
@login_required
def hr_dashboard():
    duty_stations = DutyStation.query.all()
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    duty_station_id = request.args.get('duty_station_id', 'all')
    month = request.args.get('month', 'all')
    year = request.args.get('year', 'all')

    emp_query = Employee.query
    leave_query = AnnualLeave.query
    letter_query = EmploymentLetter.query
    contract_query = Contract.query
    ot_query = Overtime.query
    att_query = Attendance.query
    pos_query = Position.query

    if start_date:
        try:
            start = datetime.strptime(start_date, '%Y-%m-%d')
            emp_query = emp_query.filter(Employee.hire_date >= start)
            leave_query = leave_query.filter(AnnualLeave.start_date >= start)
            letter_query = letter_query.filter(EmploymentLetter.created_at >= start)
            contract_query = contract_query.filter(Contract.start_date >= start)
            ot_query = ot_query.filter(Overtime.date >= start)
            att_query = att_query.filter(Attendance.date >= start)
        except ValueError:
            start_date = ''
    if end_date:
        try:
            end = datetime.strptime(end_date, '%Y-%m-%d')
            emp_query = emp_query.filter(Employee.hire_date <= end)
            leave_query = leave_query.filter(AnnualLeave.end_date <= end)
            letter_query = letter_query.filter(EmploymentLetter.created_at <= end)
            contract_query = contract_query.filter(Contract.end_date <= end)
            ot_query = ot_query.filter(Overtime.date <= end)
            att_query = att_query.filter(Attendance.date <= end)
        except ValueError:
            end_date = ''
    if duty_station_id != 'all':
        emp_query = emp_query.filter(Employee.duty_station_id == int(duty_station_id))
        leave_query = leave_query.join(Employee, AnnualLeave.employee_id == Employee.id).filter(Employee.duty_station_id == int(duty_station_id))
        letter_query = letter_query.join(Employee, EmploymentLetter.employee_id == Employee.id).filter(Employee.duty_station_id == int(duty_station_id))
        contract_query = contract_query.join(Employee, Contract.employee_id == Employee.id).filter(Employee.duty_station_id == int(duty_station_id))
        ot_query = ot_query.join(Employee, Overtime.employee_id == Employee.id).filter(Employee.duty_station_id == int(duty_station_id))
        att_query = att_query.join(Employee, Attendance.employee_id == Employee.id).filter(Employee.duty_station_id == int(duty_station_id))
        pos_query = pos_query.filter(Position.duty_station_id == int(duty_station_id))
    if month != 'all':
        leave_query = leave_query.filter(db.extract('month', AnnualLeave.start_date) == int(month))
        ot_query = ot_query.filter(db.extract('month', Overtime.date) == int(month))
        att_query = att_query.filter(db.extract('month', Attendance.date) == int(month))
    if year != 'all':
        emp_query = emp_query.filter(db.extract('year', Employee.hire_date) == int(year))
        leave_query = leave_query.filter(db.extract('year', AnnualLeave.start_date) == int(year))
        letter_query = letter_query.filter(db.extract('year', EmploymentLetter.created_at) == int(year))
        contract_query = contract_query.filter(db.extract('year', Contract.start_date) == int(year))
        ot_query = ot_query.filter(db.extract('year', Overtime.date) == int(year))
        att_query = att_query.filter(db.extract('year', Attendance.date) == int(year))

    employees = emp_query.all()
    leave_records = leave_query.all()
    letters = letter_query.all()
    contracts = contract_query.all()
    overtime_records = ot_query.all()
    attendance_records = att_query.all()
    positions = pos_query.all()

    duty_station_summary = []
    total_employees = len(emp_query.all())
    total_leaves = len(leave_query.all())
    total_letters = len(letter_query.all())
    total_contracts = len(contract_query.all())
    total_overtime = len(ot_query.all())
    total_attendance = len(att_query.all())
    total_positions = len(pos_query.all())

    for ds in duty_stations:
        ds_employees = len([emp for emp in employees if emp.duty_station_id == ds.id])
        ds_leaves = len([leave for leave in leave_records if leave.employee.duty_station_id == ds.id])
        ds_letters = len([letter for letter in letters if letter.employee.duty_station_id == ds.id])
        ds_contracts = len([contract for contract in contracts if contract.employee.duty_station_id == ds.id])
        ds_overtime = len([ot for ot in overtime_records if ot.employee.duty_station_id == ds.id])
        ds_attendance = len([att for att in attendance_records if att.employee.duty_station_id == ds.id])
        ds_positions = len([pos for pos in positions if pos.duty_station_id == ds.id])
        duty_station_summary.append({
            'name': ds.name,
            'employees': ds_employees,
            'leaves': ds_leaves,
            'letters': ds_letters,
            'contracts': ds_contracts,
            'overtime': ds_overtime,
            'attendance': ds_attendance,
            'positions': ds_positions
        })

    gender_data = {ds.name: {'Male': 0, 'Female': 0, 'Other': 0} for ds in duty_stations if duty_station_id == 'all' or ds.id == int(duty_station_id)}
    for emp in employees:
        if emp.duty_station_id:
            gender_data[emp.duty_station.name][emp.gender] += 1
    gender_chart = {
        'labels': list(gender_data.keys()),
        'datasets': [
            {'label': 'Male', 'data': [data['Male'] for data in gender_data.values()], 'backgroundColor': '#36A2EB'},
            {'label': 'Female', 'data': [data['Female'] for data in gender_data.values()], 'backgroundColor': '#FF6384'},
            {'label': 'Other', 'data': [data['Other'] for data in gender_data.values()], 'backgroundColor': '#FFCE56'}
        ]
    }

    leave_by_month = {f"Month {i+1}": 0 for i in range(12)}
    for leave in leave_records:
        if leave.start_date:
            leave_by_month[f"Month {leave.start_date.month}"] += 1
    leave_chart = {
        'labels': list(leave_by_month.keys()),
        'datasets': [{
            'label': 'Leaves Taken',
            'data': list(leave_by_month.values()),
            'backgroundColor': 'rgba(54, 162, 235, 0.2)',
            'borderColor': 'rgba(54, 162, 235, 1)',
            'borderWidth': 1
        }]
    }

    turnover_data = {ds.name: {f"Month {i+1}": 0 for i in range(12)} for ds in duty_stations if duty_station_id == 'all' or ds.id == int(duty_station_id)}
    terminated_employees = Employee.query.filter((Employee.management_status == 'Inactive') | (Employee.contract_end_date.isnot(None))).all()
    for emp in terminated_employees:
        if emp.duty_station_id:
            termination_date = emp.contract_end_date or (EmploymentLetter.query.filter_by(employee_id=emp.id, letter_type='Termination').first().created_at.date() if EmploymentLetter.query.filter_by(employee_id=emp.id, letter_type='Termination').first() else date.today())
            if start_date and termination_date < datetime.strptime(start_date, '%Y-%m-%d').date():
                continue
            if end_date and termination_date > datetime.strptime(end_date, '%Y-%m-%d').date():
                continue
            if month != 'all' and termination_date.month != int(month):
                continue
            if year != 'all' and termination_date.year != int(year):
                continue
            turnover_data[emp.duty_station.name][f"Month {termination_date.month}"] += 1
    turnover_chart = {
        'labels': [f"Month {i+1}" for i in range(12)],
        'datasets': [
            {'label': ds_name, 'data': list(months.values()), 'borderColor': f'rgba({i*50 % 255}, {i*100 % 255}, {i*150 % 255}, 1)', 'fill': True}
            for i, (ds_name, months) in enumerate(turnover_data.items())
        ]
    }

    action_data = {ds.name: {'Promotions': 0, 'Demotions': 0, 'Warnings': 0} for ds in duty_stations if duty_station_id == 'all' or ds.id == int(duty_station_id)}
    total_promotions = total_demotions = total_warnings = 0
    for letter in letters:
        if letter.employee.duty_station_id:
            if letter.letter_type == 'Promotion':
                action_data[letter.employee.duty_station.name]['Promotions'] += 1
                total_promotions += 1
            elif letter.letter_type == 'Demotion':
                action_data[letter.employee.duty_station.name]['Demotions'] += 1
                total_demotions += 1
            elif letter.letter_type == 'Warning':
                action_data[letter.employee.duty_station.name]['Warnings'] += 1
                total_warnings += 1
    action_chart = {
        'labels': list(action_data.keys()),
        'datasets': [
            {'label': 'Promotions', 'data': [data['Promotions'] for data in action_data.values()], 'backgroundColor': '#36A2EB'},
            {'label': 'Demotions', 'data': [data['Demotions'] for data in action_data.values()], 'backgroundColor': '#FF6384'},
            {'label': 'Warnings', 'data': [data['Warnings'] for data in action_data.values()], 'backgroundColor': '#FFCE56'}
        ]
    }

    total_absent_days = sum(1 for att in Attendance.query.all() if att.status == 'Absent')
    total_working_days = len(Attendance.query.all())
    absenteeism_rate = (total_absent_days / total_working_days * 100) if total_working_days > 0 else 0
    today = date.today()
    tenures = [(today - emp.hire_date).days / 365 for emp in employees if emp.hire_date]
    average_tenure = sum(tenures) / len(tenures) if tenures else 0

    return render_template('hr_dashboard.html', duty_stations=duty_stations,
                           gender_chart=gender_chart, leave_chart=leave_chart,
                           turnover_chart=turnover_chart, action_chart=action_chart,
                           absenteeism_rate=round(absenteeism_rate, 2),
                           average_tenure=round(average_tenure, 2),
                           total_promotions=total_promotions, total_demotions=total_demotions, total_warnings=total_warnings,
                           start_date=start_date, end_date=end_date,
                           duty_station_id=duty_station_id, month=month, year=year,
                           duty_station_summary=duty_station_summary,
                           total_employees=total_employees, total_leaves=total_leaves, total_letters=total_letters,
                           total_contracts=total_contracts, total_overtime=total_overtime,
                           total_attendance=total_attendance, total_positions=total_positions)

@hr_bp.route('/scan_badge', methods=['POST'])
@login_required
def scan_badge():
    if 'image' not in request.files:
        logger.error("No image provided for badge scan")
        return jsonify({'status': 'error', 'message': 'No image provided'}), 400
    image = request.files['image']
    img = cv2.imdecode(np.frombuffer(image.read(), np.uint8), cv2.IMREAD_COLOR)
    qr_decoder = cv2.QRCodeDetector()
    badge_id, _, _ = qr_decoder.detectAndDecode(img)
    if badge_id:
        employee = Employee.query.filter_by(badge_id=badge_id).first()
        if employee:
            att = Attendance(employee_id=employee.id, date=date.today(), check_in=datetime.now(), badge_id=badge_id, status='Present')
            db.session.add(att)
            db.session.commit()
            logger.info(f"Check-in recorded for {employee.name} via badge {badge_id}")
            return jsonify({'status': 'success', 'message': f'Check-in recorded for {employee.name}'})
        logger.error(f"Employee not found for badge {badge_id}")
        return jsonify({'status': 'error', 'message': 'Employee not found'})
    logger.error("No QR code detected in image")
    return jsonify({'status': 'error', 'message': 'No QR code detected'}), 400

@hr_bp.route('/export_report/<report_type>')
@login_required
def export_report(report_type):
    if report_type == 'employees':
        data = [{
            'ID': emp.id, 'Name': emp.name, 'Job Title': emp.title, 'Department': emp.department,
            'Location': emp.location, 'Phone': emp.phone_number,
            'Duty Station': emp.duty_station.name if emp.duty_station else 'N/A',
            'Manager': emp.manager.name if emp.manager else 'None',
            'Salary': emp.monthly_salary, 'Benefits': emp.additional_benefits,
            'Hire Date': emp.hire_date.strftime('%Y-%m-%d') if emp.hire_date else ''
        } for emp in Employee.query.all()]
    elif report_type == 'overtime':
        data = [{
            'Employee': ot.employee.name,
            'Duty Station': ot.employee.duty_station.name if ot.employee.duty_station else 'N/A',
            'Date': ot.date, 'Hours': ot.hours, 'Rate': ot.rate, 'Approved': ot.approved
        } for ot in Overtime.query.all()]
    elif report_type == 'attendance':
        data = [{
            'Employee': a.employee.name,
            'Duty Station': a.employee.duty_station.name if a.employee.duty_station else 'N/A',
            'Date': a.date, 'Check In': a.check_in, 'Check Out': a.check_out, 'Status': a.status
        } for a in Attendance.query.all()]
    elif report_type == 'leave':
        data = [{
            'Employee': l.employee.name,
            'Duty Station': l.employee.duty_station.name if l.employee.duty_station else 'N/A',
            'Start Date': l.start_date, 'End Date': l.end_date, 'Days': l.total_days, 'Status': l.status
        } for l in AnnualLeave.query.all()]
    else:
        logger.error(f"Invalid report type: {report_type}")
        return "Invalid report type", 400

    df = pd.DataFrame(data)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name=report_type.capitalize(), index=False)
    output.seek(0)
    logger.info(f"Exported {report_type} report as Excel")
    return send_file(output, download_name=f"{report_type}_report.xlsx", as_attachment=True)

@hr_bp.route('/export_pdf/<report_type>')
@login_required
def export_pdf(report_type):
    if report_type == 'employees':
        employees = Employee.query.all()
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter
        c.drawString(100, height - 50, "Employee Report")
        y = height - 100
        c.setFont("Helvetica", 10)
        for emp in employees:
            text = f"ID: {emp.id}, Name: {emp.name}, Job Title: {emp.title}, Dept: {emp.department}, Salary: {emp.monthly_salary}, Hire Date: {emp.hire_date}"
            c.drawString(50, y, text)
            y -= 20
            if y < 50:
                c.showPage()
                y = height - 50
        c.save()
        buffer.seek(0)
        logger.info("Exported employees report as PDF")
        return send_file(buffer, download_name="employees_report.pdf", as_attachment=True)
    logger.error(f"PDF export not implemented for {report_type}")
    return "PDF export only available for employees", 400

@hr_bp.route('/export_dashboard_report')
@login_required
def export_dashboard_report():
    duty_stations = DutyStation.query.all()
    duty_station_summary = []
    total_employees = len(Employee.query.all())
    total_leaves = len(AnnualLeave.query.all())
    total_letters = len(EmploymentLetter.query.all())
    total_contracts = len(Contract.query.all())
    total_overtime = len(Overtime.query.all())
    total_attendance = len(Attendance.query.all())
    total_positions = len(Position.query.all())

    for ds in duty_stations:
        ds_employees = len([emp for emp in Employee.query.all() if emp.duty_station_id == ds.id])
        ds_leaves = len([leave for leave in AnnualLeave.query.all() if leave.employee.duty_station_id == ds.id])
        ds_letters = len([letter for letter in EmploymentLetter.query.all() if letter.employee.duty_station_id == ds.id])
        ds_contracts = len([contract for contract in Contract.query.all() if contract.employee.duty_station_id == ds.id])
        ds_overtime = len([ot for ot in Overtime.query.all() if ot.employee.duty_station_id == ds.id])
        ds_attendance = len([att for att in Attendance.query.all() if att.employee.duty_station_id == ds.id])
        ds_positions = len([pos for pos in Position.query.all() if pos.duty_station_id == ds.id])
        duty_station_summary.append({
            'Duty Station': ds.name, 'Employees': ds_employees, 'Leaves': ds_leaves, 'Letters': ds_letters,
            'Contracts': ds_contracts, 'Overtime Records': ds_overtime, 'Attendance Records': ds_attendance,
            'Positions': ds_positions
        })

    total_absent_days = sum(1 for att in Attendance.query.all() if att.status == 'Absent')
    total_working_days = len(Attendance.query.all())
    absenteeism_rate = (total_absent_days / total_working_days * 100) if total_working_days > 0 else 0
    today = date.today()
    tenures = [(today - emp.hire_date).days / 365 for emp in Employee.query.all() if emp.hire_date]
    average_tenure = sum(tenures) / len(tenures) if tenures else 0
    letters = EmploymentLetter.query.all()
    total_promotions = sum(1 for letter in letters if letter.letter_type == 'Promotion')
    total_demotions = sum(1 for letter in letters if letter.letter_type == 'Demotion')
    total_warnings = sum(1 for letter in letters if letter.letter_type == 'Warning')

    summary_data = {
        'Metric': [
            'Total Employees', 'Total Leaves', 'Total Letters', 'Total Contracts',
            'Total Overtime Records', 'Total Attendance Records', 'Total Positions',
            'Absenteeism Rate (%)', 'Average Tenure (Years)', 'Total Promotions',
            'Total Demotions', 'Total Warnings'
        ],
        'Value': [
            total_employees, total_leaves, total_letters, total_contracts,
            total_overtime, total_attendance, total_positions,
            round(absenteeism_rate, 2), round(average_tenure, 2),
            total_promotions, total_demotions, total_warnings
        ]
    }

    df_summary = pd.DataFrame(summary_data)
    df_duty_stations = pd.DataFrame(duty_station_summary)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_summary.to_excel(writer, sheet_name='Summary', index=False)
        df_duty_stations.to_excel(writer, sheet_name='Duty Stations', index=False)
    output.seek(0)
    logger.info("Exported dashboard report as Excel")
    return send_file(output, download_name="hr_dashboard_report.xlsx", as_attachment=True)