from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, send_file
from flask_login import login_required, current_user
from database import db
from modules.models import Employee, DutyStation
from modules.forms import EmployeeForm
from flask_wtf.csrf import validate_csrf, CSRFError
from werkzeug.utils import secure_filename
from datetime import datetime
import os
import logging
from sqlalchemy.exc import OperationalError
import time
import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from io import BytesIO

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

hr_bp = Blueprint('hr', __name__, url_prefix='/hr')

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
        flash('No permission for HR module.', 'danger')
        return redirect(url_for('dashboard.dashboard'))

    form = EmployeeForm()
    duty_stations = DutyStation.query.all()
    # Optimize manager dropdown by filtering active employees
    active_employees = Employee.query.filter_by(management_status='Active').all()
    form.duty_station_id.choices = [(ds.id, ds.name) for ds in duty_stations]
    form.manager_id.choices = [(0, 'None')] + [(emp.id, emp.name) for emp in active_employees]

    # Search and Filter Logic
    query = Employee.query
    search_name = request.args.get('search_name', '')
    duty_station_id = request.args.get('duty_station_id', 'all')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')

    if search_name:
        query = query.filter(Employee.name.ilike(f'%{search_name}%'))
    if duty_station_id != 'all':
        query = query.filter(Employee.duty_station_id == int(duty_station_id))
    if start_date:
        try:
            query = query.filter(Employee.hire_date >= datetime.strptime(start_date, '%Y-%m-%d'))
        except ValueError:
            flash('Invalid start date format. Use YYYY-MM-DD.', 'danger')
            start_date = ''
    if end_date:
        try:
            query = query.filter(Employee.hire_date <= datetime.strptime(end_date, '%Y-%m-%d'))
        except ValueError:
            flash('Invalid end date format. Use YYYY-MM-DD.', 'danger')
            end_date = ''

    employees = query.all()

    # Chart Data
    salary_by_duty_station = {}
    employee_distribution = {}
    for ds in duty_stations:
        ds_employees = [emp for emp in employees if emp.duty_station_id == ds.id]
        total_salary = sum(emp.monthly_salary for emp in ds_employees)
        salary_by_duty_station[ds.name] = total_salary
        employee_distribution[ds.name] = len(ds_employees)

    # Fallback for empty data
    if not salary_by_duty_station:
        salary_by_duty_station = {"No Data": 0}
    if not employee_distribution:
        employee_distribution = {"No Data": 0}

    # Log chart data for debugging
    logger.debug(f"Salary by duty station: {salary_by_duty_station}")
    logger.debug(f"Employee distribution: {employee_distribution}")

    # Convert dictionary keys and values to lists for JSON serialization
    salary_labels = list(salary_by_duty_station.keys())
    salary_data = list(salary_by_duty_station.values())
    distribution_labels = list(employee_distribution.keys())
    distribution_data = list(employee_distribution.values())

    # Handle Form Submission
    if request.method == 'POST':
        try:
            validate_csrf(request.form.get('csrf_token'))
        except CSRFError:
            return jsonify({'status': 'error', 'message': 'Invalid CSRF token'}), 403

        action = request.form.get('action')

        if action == 'add_employee':
            photo_dir, cv_dir = ensure_upload_dirs()
            photo_path = None
            if form.photo.data:
                photo = form.photo.data
                photo_filename = secure_filename(photo.filename)
                photo_path = os.path.join(photo_dir, photo_filename)
                try:
                    photo.save(photo_path)
                except Exception as e:
                    logger.error(f"Failed to save photo: {e}")
                    return jsonify({'status': 'error', 'message': 'Failed to save photo'}), 500
            cv_path = None
            if form.cv.data:
                cv = form.cv.data
                cv_filename = secure_filename(cv.filename)
                cv_path = os.path.join(cv_dir, cv_filename)
                try:
                    cv.save(cv_path)
                except Exception as e:
                    logger.error(f"Failed to save CV: {e}")
                    return jsonify({'status': 'error', 'message': 'Failed to save CV'}), 500

            employee = Employee(
                name=request.form.get('name'),
                address_woreda=request.form.get('address_woreda'),
                address_kifle_ketema=request.form.get('address_kifle_ketema'),
                phone_number=request.form.get('phone_number'),
                emergency_contact_name=request.form.get('emergency_contact_name'),
                emergency_contact_phone=request.form.get('emergency_contact_phone'),
                photo_path=photo_path,
                cv_path=cv_path,
                manager_id=int(request.form.get('manager_id')) if request.form.get('manager_id') != '0' else None,
                location=request.form.get('location'),
                birth_date=datetime.strptime(request.form.get('birth_date'), '%Y-%m-%d').date(),
                hire_date=datetime.strptime(request.form.get('hire_date'), '%Y-%m-%d').date(),
                internal_notes=request.form.get('internal_notes'),
                monthly_salary=float(request.form.get('monthly_salary', 0.0)),
                additional_benefits=float(request.form.get('additional_benefits', 0.0)) or 0.0,
                title=request.form.get('title'),
                gender=request.form.get('gender'),
                department=request.form.get('department'),
                contract_end_date=datetime.strptime(request.form.get('contract_end_date'), '%Y-%m-%d').date() if request.form.get('contract_end_date') else None,
                seniority=int(request.form.get('seniority', 0)) or 0,
                management_status=request.form.get('management_status', 'Active'),
                job_grade=request.form.get('job_grade'),
                step=int(request.form.get('step', 0)),
                travel_allowance=float(request.form.get('travel_allowance', 0.0)) or 0.0,
                other_allowance=float(request.form.get('other_allowance', 0.0)) or 0.0,
                non_taxable_allowance=float(request.form.get('non_taxable_allowance', 0.0)) or 0.0,
                other_deduction=float(request.form.get('other_deduction', 0.0)) or 0.0,
                lunch_deduction_employee=float(request.form.get('lunch_deduction_employee', 0.0)) or 0.0,
                lunch_deduction_court=float(request.form.get('lunch_deduction_court', 0.0)) or 0.0,
                duty_station_id=int(request.form.get('duty_station_id'))
            )
            db.session.add(employee)
            max_retries = 5
            for attempt in range(max_retries):
                try:
                    db.session.commit()
                    return jsonify({'status': 'success', 'message': f'Employee {employee.name} added successfully'})
                except OperationalError as e:
                    db.session.rollback()
                    if "database is locked" in str(e):
                        time.sleep(2)
                    else:
                        return jsonify({'status': 'error', 'message': str(e)}), 500
            return jsonify({'status': 'error', 'message': 'Database locked'}), 500

        elif action == 'modify_employee':
            employee_id = request.form.get('employee_id')
            employee = Employee.query.get(employee_id)
            if employee:
                employee.name = request.form.get('name', employee.name)
                employee.address_woreda = request.form.get('address_woreda', employee.address_woreda)
                employee.address_kifle_ketema = request.form.get('address_kifle_ketema', employee.address_kifle_ketema)
                employee.phone_number = request.form.get('phone_number', employee.phone_number)
                employee.emergency_contact_name = request.form.get('emergency_contact_name', employee.emergency_contact_name)
                employee.emergency_contact_phone = request.form.get('emergency_contact_phone', employee.emergency_contact_phone)
                employee.manager_id = int(request.form.get('manager_id')) if request.form.get('manager_id') != '0' else None
                employee.location = request.form.get('location', employee.location)
                birth_date = request.form.get('birth_date')
                if birth_date:
                    employee.birth_date = datetime.strptime(birth_date, '%Y-%m-%d').date()
                hire_date = request.form.get('hire_date')
                if hire_date:
                    employee.hire_date = datetime.strptime(hire_date, '%Y-%m-%d').date()
                employee.internal_notes = request.form.get('internal_notes', employee.internal_notes)
                employee.monthly_salary = float(request.form.get('monthly_salary', employee.monthly_salary))
                employee.additional_benefits = float(request.form.get('additional_benefits', employee.additional_benefits))
                employee.title = request.form.get('title', employee.title)
                employee.gender = request.form.get('gender', employee.gender)
                employee.department = request.form.get('department', employee.department)
                contract_end_date = request.form.get('contract_end_date')
                employee.contract_end_date = datetime.strptime(contract_end_date, '%Y-%m-%d').date() if contract_end_date else employee.contract_end_date
                employee.seniority = int(request.form.get('seniority', employee.seniority))
                employee.management_status = request.form.get('management_status', employee.management_status)
                employee.job_grade = request.form.get('job_grade', employee.job_grade)
                employee.step = int(request.form.get('step', employee.step))
                employee.travel_allowance = float(request.form.get('travel_allowance', employee.travel_allowance))
                employee.other_allowance = float(request.form.get('other_allowance', employee.other_allowance))
                employee.non_taxable_allowance = float(request.form.get('non_taxable_allowance', employee.non_taxable_allowance))
                employee.other_deduction = float(request.form.get('other_deduction', employee.other_deduction))
                employee.lunch_deduction_employee = float(request.form.get('lunch_deduction_employee', employee.lunch_deduction_employee))
                employee.lunch_deduction_court = float(request.form.get('lunch_deduction_court', employee.lunch_deduction_court))
                employee.duty_station_id = int(request.form.get('duty_station_id', employee.duty_station_id))
                max_retries = 5
                for attempt in range(max_retries):
                    try:
                        db.session.commit()
                        return jsonify({'status': 'success', 'message': f'Employee {employee.name} updated', 'employee': {
                            'id': employee.id,
                            'name': employee.name,
                            'title': employee.title,
                            'phone_number': employee.phone_number,
                            'monthly_salary': employee.monthly_salary,
                            'hire_date': employee.hire_date.strftime('%Y-%m-%d') if employee.hire_date else '',
                            'duty_station': employee.duty_station.name if employee.duty_station else 'N/A',
                            'department': employee.department,
                            'gender': employee.gender,
                            'job_grade': employee.job_grade,
                            'location': employee.location,
                            'additional_benefits': employee.additional_benefits,
                            'created_at': employee.created_at.strftime('%Y-%m-%d') if employee.created_at else ''
                        }})
                    except OperationalError as e:
                        db.session.rollback()
                        if "database is locked" in str(e):
                            time.sleep(2)
                        else:
                            return jsonify({'status': 'error', 'message': str(e)}), 500
                return jsonify({'status': 'error', 'message': 'Database locked'}), 500
            return jsonify({'status': 'error', 'message': 'Employee not found'}), 404

        elif action == 'remove_employee' and request.is_json:
            data = request.get_json()
            employee_id = data.get('employee_id')
            employee = Employee.query.get(employee_id)
            if employee:
                db.session.delete(employee)
                max_retries = 5
                for attempt in range(max_retries):
                    try:
                        db.session.commit()
                        return jsonify({'status': 'success', 'message': 'Employee removed', 'employee_id': employee_id})
                    except OperationalError as e:
                        db.session.rollback()
                        if "database is locked" in str(e):
                            time.sleep(2)
                        else:
                            return jsonify({'status': 'error', 'message': str(e)}), 500
                return jsonify({'status': 'error', 'message': 'Database locked'}), 500
            return jsonify({'status': 'error', 'message': 'Employee not found'}), 404

    return render_template('hr.html', form=form, employees=employees, duty_stations=duty_stations,
                          salary_labels=salary_labels, salary_data=salary_data,
                          distribution_labels=distribution_labels, distribution_data=distribution_data,
                          search_name=search_name, duty_station_id=duty_station_id, start_date=start_date, end_date=end_date)

@hr_bp.route('/export_excel')
@login_required
def export_excel():
    employees = Employee.query.all()
    data = []
    for emp in employees:
        data.append({
            'ID': emp.id,
            'Name': emp.name,
            'Title': emp.title,
            'Department': emp.department,
            'Location': emp.location,
            'Phone': emp.phone_number,
            'Duty Station': emp.duty_station.name if emp.duty_station else 'N/A',
            'Manager': emp.manager.name if emp.manager else 'None',
            'Monthly Salary': emp.monthly_salary,
            'Additional Benefits': emp.additional_benefits,
            'Hire Date': emp.hire_date.strftime('%Y-%m-%d') if emp.hire_date else '',
            'Uploaded Date': emp.created_at.strftime('%Y-%m-%d') if emp.created_at else ''
        })
    df = pd.DataFrame(data)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Employees', index=False)
    output.seek(0)
    return send_file(output, download_name='employees.xlsx', as_attachment=True)

@hr_bp.route('/export_pdf')
@login_required
def export_pdf():
    employees = Employee.query.all()
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    y = height - 50
    c.drawString(100, y, "Employee Report")
    y -= 30
    c.drawString(30, y, "ID  Name                Title       Department  Location    Phone       Duty Station  Manager  Salary  Benefits  Hire Date  Uploaded Date")
    y -= 20
    for emp in employees:
        if y < 50:
            c.showPage()
            y = height - 50
        line = f"{emp.id:<4}{emp.name[:20]:<20}{emp.title[:12]:<12}{emp.department[:12]:<12}{str(emp.location)[:12]:<12}{str(emp.phone_number)[:12]:<12}{emp.duty_station.name[:12] if emp.duty_station else 'N/A':<12}{emp.manager.name[:8] if emp.manager else 'None':<8}{emp.monthly_salary:<8.2f}{emp.additional_benefits:<10.2f}{emp.hire_date.strftime('%Y-%m-%d') if emp.hire_date else '':<11}{emp.created_at.strftime('%Y-%m-%d') if emp.created_at else ''}"
        c.drawString(30, y, line)
        y -= 20
    c.save()
    buffer.seek(0)
    return send_file(buffer, download_name='employees.pdf', as_attachment=True)