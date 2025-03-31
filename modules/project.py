# modules/project.py
from flask import Blueprint, render_template, request, jsonify
from datetime import datetime, timedelta
from database import db
from modules.models import Project, Department, Activity, ActivityFollowup, Report
import logging
from main import csrf  # Import the csrf instance from main.py

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

project_bp = Blueprint('project', __name__)

@project_bp.route('/', methods=['GET', 'POST'])
def project():
    start_date = request.form.get('start_date', datetime.now().date()) if request.method == 'POST' else request.args.get('start_date', datetime.now().date())
    end_date = request.form.get('end_date', datetime.now().date() + timedelta(days=6)) if request.method == 'POST' else request.args.get('end_date', datetime.now().date() + timedelta(days=6))
    start_date = datetime.strptime(str(start_date), '%Y-%m-%d').date()
    end_date = datetime.strptime(str(end_date), '%Y-%m-%d').date()
    
    activities = Activity.query.filter(Activity.planned_date.between(start_date, end_date)).all()
    days = [start_date + timedelta(days=i) for i in range((end_date - start_date).days + 1)]
    
    # Monthly Overview with Status Breakdown
    monthly_summary = []
    current = start_date.replace(day=1)
    while current <= end_date:
        next_month = (current.replace(day=28) + timedelta(days=4)).replace(day=1)
        month_end = min(next_month - timedelta(days=1), end_date)
        month_activities = Activity.query.filter(Activity.planned_date.between(current, month_end)).all()
        
        status_counts = {'Achieved': 0, 'In Progress': 0, 'Not Achieved': 0, 'Cancelled': 0}
        for activity in month_activities:
            status = activity.status
            if status == 'Achieved':
                status_counts['Achieved'] += 1
            elif status == 'In Progress':
                status_counts['In Progress'] += 1
            elif status == 'Cancelled':
                status_counts['Cancelled'] += 1
            else:
                status_counts['Not Achieved'] += 1
        
        summary = {
            'week_start': current,
            'week_end': month_end,
            'activity_count': len(month_activities),
            'status_counts': status_counts
        }
        monthly_summary.append(summary)
        current = next_month

    projects = Project.query.all()
    return render_template('project.html', start_date=start_date, end_date=end_date, activities=activities, days=days, monthly_summary=monthly_summary, week_start=start_date, week_end=end_date, projects=projects)

@project_bp.route('/add_project', methods=['POST'])
@csrf.exempt
def add_project():
    try:
        name = request.form.get('project_name')
        if not name:
            return jsonify({'status': 'error', 'message': 'Project name is required'}), 400

        description = request.form.get('description')
        project_start_date = request.form.get('project_start_date')
        project_end_date = request.form.get('project_end_date')

        if not project_start_date or not project_end_date:
            return jsonify({'status': 'error', 'message': 'Start date and end date are required'}), 400

        try:
            start_date = datetime.strptime(project_start_date, '%Y-%m-%d').date()
            end_date = datetime.strptime(project_end_date, '%Y-%m-%d').date()
        except ValueError as e:
            return jsonify({'status': 'error', 'message': 'Invalid date format. Use YYYY-MM-DD'}), 400

        new_project = Project(
            name=name,
            description=description,
            start_date=start_date,
            end_date=end_date,
            created_at=datetime.now()
        )
        db.session.add(new_project)
        db.session.commit()
        logger.info(f"Project '{name}' added successfully with ID {new_project.id}")
        return jsonify({'status': 'success', 'project_id': new_project.id})
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error adding project: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@project_bp.route('/add_activity', methods=['POST'])
@csrf.exempt
def add_activity():
    try:
        # Get form data
        dept_name = request.form.get('department_name', '')
        activity_name = request.form.get('activity_name')
        planned_date = request.form.get('planned_date')
        intended_result = request.form.get('intended_result', '')

        # Log the received data for debugging
        logger.debug(f"Received activity data: dept_name={dept_name}, activity_name={activity_name}, planned_date={planned_date}, intended_result={intended_result}")

        # Validate required fields
        if not activity_name:
            return jsonify({'status': 'error', 'message': 'Activity name is required'}), 400
        if not planned_date:
            return jsonify({'status': 'error', 'message': 'Planned date is required'}), 400

        # Validate date format
        try:
            planned_date = datetime.strptime(planned_date, '%Y-%m-%d').date()
        except ValueError as e:
            logger.error(f"Invalid date format for planned_date: {planned_date}")
            return jsonify({'status': 'error', 'message': 'Invalid date format for planned date. Use YYYY-MM-DD'}), 400

        # Check if department exists, if not create it
        department = None
        if dept_name:
            department = Department.query.filter_by(name=dept_name).first()
            if not department:
                department = Department(name=dept_name)
                db.session.add(department)
                db.session.commit()
                logger.info(f"Created new department: {dept_name}")

        # Create new activity
        new_activity = Activity(
            department_id=department.id if department else None,
            activity_name=activity_name,
            planned_date=planned_date,
            intended_result=intended_result,
            status='Not Achieved'
        )
        db.session.add(new_activity)
        db.session.commit()
        logger.info(f"Activity '{activity_name}' added successfully with ID {new_activity.id}")
        return jsonify({'status': 'success'})
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error adding activity: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@project_bp.route('/update_week')
def update_week():
    start_date = request.args.get('start')
    end_date = request.args.get('end')
    activities = Activity.query.filter(Activity.planned_date.between(start_date, end_date)).all()
    days = [datetime.strptime(start_date, '%Y-%m-%d').date() + timedelta(days=i) for i in range(7)]
    html = ''
    for activity in activities:
        dept_name = activity.department.name if activity.department else 'N/A'
        html += f'<tr><td>{dept_name}</td>'
        for day in days:
            html += f'<td class="{"bg-warning" if activity.planned_date == day else ""}>{activity.activity_name if activity.planned_date == day else ""}</td>'
        html += f'<td>{activity.intended_result}</td><td>{activity.status}</td></tr>'
    return html

@project_bp.route('/update_activity_status/<int:activity_id>', methods=['POST'])
@csrf.exempt
def update_activity_status(activity_id):
    try:
        activity = Activity.query.get_or_404(activity_id)
        new_status = request.form.get('status')
        if not new_status:
            return jsonify({'status': 'error', 'message': 'Status is required'}), 400
        if new_status not in ['Achieved', 'In Progress', 'Not Achieved', 'Cancelled']:
            return jsonify({'status': 'error', 'message': 'Invalid status'}), 400
        activity.status = new_status
        db.session.commit()
        logger.info(f"Activity {activity_id} status updated to {new_status}")
        return jsonify({'status': 'success'})
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating activity status: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@project_bp.route('/get_project_activities/<int:project_id>')
def get_project_activities(project_id):
    project = Project.query.get_or_404(project_id)
    activities = Activity.query.filter_by(project_id=project_id).all()
    data = {
        'project': {
            'name': project.name,
            'start_date': project.start_date.strftime('%Y-%m-%d'),
            'end_date': project.end_date.strftime('%Y-%m-%d')
        },
        'activities': [
            {
                'name': activity.activity_name,
                'start_date': activity.planned_date.strftime('%Y-%m-%d'),
                'end_date': (activity.planned_date + timedelta(days=1)).strftime('%Y-%m-%d'),
                'budget': 1000,  # Placeholder budget
                'status': activity.status
            } for activity in activities
        ]
    }
    return jsonify(data)