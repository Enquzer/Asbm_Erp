from flask import Blueprint, render_template

project_bp = Blueprint('project', __name__)

@project_bp.route('/')
def project():
    return render_template('project.html')