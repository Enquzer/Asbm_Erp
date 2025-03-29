from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user

system_setup_bp = Blueprint('system_setup', __name__, template_folder='templates')

@system_setup_bp.route('/system_setup', methods=['GET', 'POST'])
@login_required
def system_setup():
    if not current_user.has_permission('admin'):
        flash('You do not have permission to access system setup.', 'danger')
        return redirect(url_for('index'))
    # Placeholder for future functionality
    return render_template('system_setup.html')