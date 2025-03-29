# modules/hr.py
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from database import db
from modules.models import Employee, DutyStation
from modules.forms import EmployeeForm
from flask_wtf.csrf import validate_csrf, CSRFError
import os
from werkzeug.utils import secure_filename
from datetime import datetime
import json
from dateutil.relativedelta import relativedelta
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

hr_bp = Blueprint('hr', __name__, url_prefix='/hr')

# Ensure upload directories exist
def ensure_upload_dirs():
    photo_dir = os.path.join('static', 'uploads', 'employee_photos')
    cv_dir = os.path.join('static', 'uploads', 'employee_cvs')
    os.makedirs(photo_dir, exist_ok=True)
    os.makedirs(cv_dir, exist_ok=True)
    return photo_dir, cv_dir

@hr_bp.route('/', methods=['GET', 'POST'])
@login_required
def hr():
    if not current_user.has_permission('hr'):
        flash('You do not have permission to access HR module.', 'danger')
        return redirect(url_for('dashboard.dashboard'))

    form = EmployeeForm()
    duty_stations = DutyStation.query.all()
    form.duty_station_id.choices = [(ds.id, ds.name) for ds in duty_stations]
    form.manager_id.choices = [(0, 'None')] + [(emp.id, emp.name) for emp in Employee.query.all()]

    # Handle filter form
    name_filter = request.args.get('name', '')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    duty_station_id = request.args.get('duty_station_id')
    hire_date = request.args.get('hire_date')

    query = Employee.query
    if name_filter:
        query = query.filter(Employee.name.ilike(f'%{name_filter}%'))
    if start_date:
        query = query.filter(Employee.created_at >= datetime.strptime(start_date, '%Y-%m-%d'))
    if end_date:
        query = query.filter(Employee.created_at <= datetime.strptime(end_date, '%Y-%m-%d'))
    if duty_station_id:
        query = query.filter_by(duty_station_id=duty_station_id)
    if hire_date:
        query = query.filter_by(hire_date=datetime.strptime(hire_date, '%Y-%m-%d').date())
    employees = query.all()

    # Calculate monthly expenses and employee counts per duty station
    start_date_chart = request.args.get('start_date_chart', (datetime.now().replace(day=1) - relativedelta(months=1)).strftime('%Y-%m-%d'))
    end_date_chart = request.args.get('end_date_chart', datetime.now().strftime('%Y-%m-%d'))
    duty_station_data = {}
    for ds in duty_stations:
        employees_in_ds = Employee.query.filter_by(duty_station_id=ds.id).all()
        total_expense = sum(e.monthly_salary + (e.additional_benefits or 0) for e in employees_in_ds if start_date_chart <= e.created_at.strftime('%Y-%m-%d') <= end_date_chart)
        duty_station_data[ds.name] = {
            'expense': total_expense,
            'employee_count': len(employees_in_ds)
        }

    # Handle POST requests (e.g., remove, modify, add)
    if request.method == 'POST':
        # Handle JSON requests (e.g., remove)
        if request.headers.get('Content-Type') == 'application/json':
            data = request.get_json()
            action = data.get('action')

            if action == 'remove_employee':
                csrf_token = request.headers.get('X-CSRFToken')
                if not csrf_token:
                    logger.error("No CSRF token provided in request headers")
                    return jsonify({'status': 'error', 'message': 'CSRF token missing'}), 403

                try:
                    validate_csrf(csrf_token)
                    logger.debug("CSRF token validated successfully")
                except CSRFError as e:
                    logger.error(f"CSRF validation failed: {str(e)}")
                    return jsonify({'status': 'error', 'message': 'Invalid CSRF token'}), 403

                employee_id = data.get('employee_id')
                if not employee_id:
                    logger.error("Employee ID not provided in request")
                    return jsonify({'status': 'error', 'message': 'Employee ID required'}), 400

                employee = Employee.query.get(employee_id)
                if not employee:
                    logger.warning(f"Employee with ID {employee_id} not found")
                    return jsonify({'status': 'error', 'message': 'Employee not found'}), 404

                try:
                    db.session.delete(employee)
                    db.session.commit()
                    logger.info(f"Employee with ID {employee_id} removed successfully")
                    return jsonify({
                        'status': 'success',
                        'message': 'Employee removed successfully',
                        'employee_id': employee_id
                    }), 200
                except Exception as e:
                    db.session.rollback()
                    logger.error(f"Database error removing employee ID {employee_id}: {str(e)}")
                    return jsonify({'status': 'error', 'message': f'Database error: {str(e)}'}), 500

        # Handle form submissions (e.g., add, modify)
        else:
            try:
                validate_csrf(request.form.get('csrf_token'))
                logger.debug("CSRF token validated successfully for form submission")
            except CSRFError as e:
                logger.error(f"CSRF validation failed: {str(e)}")
                return jsonify({'status': 'error', 'message': 'Invalid CSRF token'}), 403

            action = request.form.get('action')

            if action == 'add_employee':
                photo_dir, cv_dir = ensure_upload_dirs()
                photo_path = None
                if form.photo.data:
                    photo = form.photo.data
                    photo_filename = secure_filename(photo.filename)
                    photo_path = os.path.join(photo_dir, photo_filename)
                    photo.save(photo_path)
                cv_path = None
                if form.cv.data:
                    cv = form.cv.data
                    cv_filename = secure_filename(cv.filename)
                    cv_path = os.path.join(cv_dir, cv_filename)
                    cv.save(cv_path)

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
                    location=form.location.data,
                    birth_date=form.birth_date.data,
                    hire_date=form.hire_date.data,
                    internal_notes=form.internal_notes.data,
                    monthly_salary=form.monthly_salary.data,
                    additional_benefits=form.additional_benefits.data,
                    title=form.title.data,
                    gender=form.gender.data,
                    department=form.department.data,
                    contract_end_date=form.contract_end_date.data,
                    seniority=form.seniority.data,
                    management_status=form.management_status.data,
                    job_grade=form.job_grade.data,
                    step=form.step.data,
                    basic_salary=form.basic_salary.data,
                    travel_allowance=form.travel_allowance.data,
                    other_allowance=form.other_allowance.data,
                    non_taxable_allowance=form.non_taxable_allowance.data,
                    other_deduction=form.other_deduction.data,
                    lunch_deduction_employee=form.lunch_deduction_employee.data,
                    lunch_deduction_court=form.lunch_deduction_court.data,
                    duty_station_id=form.duty_station_id.data
                )
                db.session.add(employee)
                db.session.commit()
                logger.info(f"Employee {employee.name} added successfully")
                return jsonify({'status': 'success', 'message': 'Employee added successfully', 'action': 'continue'})

            elif action == 'modify_employee':
                employee_id = request.form.get('employee_id')
                logger.debug(f"Modifying employee with ID: {employee_id}, Form data: {dict(request.form)}")
                employee = Employee.query.get(employee_id)
                if employee:
                    try:
                        # Update employee fields
                        employee.name = request.form.get('name', employee.name)
                        employee.address_woreda = request.form.get('address_woreda', employee.address_woreda)
                        employee.address_kifle_ketema = request.form.get('address_kifle_ketema', employee.address_kifle_ketema)
                        employee.phone_number = request.form.get('phone_number', employee.phone_number)
                        employee.emergency_contact_name = request.form.get('emergency_contact_name', employee.emergency_contact_name)
                        employee.emergency_contact_phone = request.form.get('emergency_contact_phone', employee.emergency_contact_phone)
                        employee.monthly_salary = float(request.form.get('monthly_salary', employee.monthly_salary))
                        employee.additional_benefits = float(request.form.get('additional_benefits', employee.additional_benefits))
                        employee.title = request.form.get('title', employee.title)
                        employee.gender = request.form.get('gender', employee.gender)
                        employee.department = request.form.get('department', employee.department)
                        employee.hire_date = datetime.strptime(request.form.get('hire_date'), '%Y-%m-%d').date() if request.form.get('hire_date') else employee.hire_date
                        employee.duty_station_id = int(request.form.get('duty_station_id', employee.duty_station_id))

                        db.session.commit()
                        logger.info(f"Employee with ID {employee_id} modified successfully")

                        # Return updated employee data for UI
                        updated_employee = {
                            'id': employee.id,
                            'name': employee.name,
                            'title': employee.title,
                            'department': employee.department,
                            'location': employee.location,
                            'phone_number': employee.phone_number,
                            'duty_station': employee.duty_station.name if employee.duty_station else 'N/A',
                            'manager': employee.manager.name if employee.manager else 'None',
                            'photo_path': employee.photo_path,
                            'cv_path': employee.cv_path,
                            'monthly_salary': employee.monthly_salary,
                            'additional_benefits': employee.additional_benefits,
                            'hire_date': employee.hire_date.strftime('%Y-%m-%d') if employee.hire_date else '',
                            'created_at': employee.created_at.strftime('%Y-%m-%d %H:%M:%S') if employee.created_at else ''
                        }
                        return jsonify({
                            'status': 'success',
                            'message': 'Employee modified successfully',
                            'employee': updated_employee
                        }), 200
                    except Exception as e:
                        db.session.rollback()
                        logger.error(f"Failed to modify employee with ID {employee_id}: {str(e)}")
                        return jsonify({'status': 'error', 'message': f'Failed to modify employee: {str(e)}'}), 500
                else:
                    logger.warning(f"Employee with ID {employee_id} not found")
                    return jsonify({'status': 'error', 'message': 'Employee not found'}), 404

    return render_template('hr/hr.html', form=form, employees=employees, duty_station_data=duty_station_data,
                          start_date_chart=start_date_chart, end_date_chart=end_date_chart, duty_stations=duty_stations)

@hr_bp.route('/add_employee', methods=['GET'])
@login_required
def add_employee_popup():
    form = EmployeeForm()
    duty_stations = DutyStation.query.all()
    form.duty_station_id.choices = [(ds.id, ds.name) for ds in duty_stations]
    form.manager_id.choices = [(0, 'None')] + [(emp.id, emp.name) for emp in Employee.query.all()]
    return render_template('hr/add_employee.html', form=form)

@hr_bp.route('/modify_employee/<int:employee_id>', methods=['GET'])
@login_required
def modify_employee_popup(employee_id):
    employee = Employee.query.get_or_404(employee_id)
    form = EmployeeForm(obj=employee)
    duty_stations = DutyStation.query.all()
    form.duty_station_id.choices = [(ds.id, ds.name) for ds in duty_stations]
    form.manager_id.choices = [(0, 'None')] + [(emp.id, emp.name) for emp in Employee.query.all()]
    return render_template('hr/modify_employee.html', form=form, employee_id=employee_id)