from flask import Blueprint, render_template, request, redirect, url_for, flash, send_from_directory
from flask_login import login_required, current_user
from modules.models import db, Resource
from flask_wtf import FlaskForm
from wtforms import StringField, FileField, SelectField, SubmitField
from wtforms.validators import DataRequired
import os
from werkzeug.utils import secure_filename
import uuid

resources_bp = Blueprint('resources', __name__)
UPLOAD_FOLDER = 'static/resources'
ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'xls', 'xlsx'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

class ResourceUploadForm(FlaskForm):
    title = StringField('Title', validators=[DataRequired()])
    category = SelectField('Category', choices=[
        ('sops', 'SOPs'),
        ('guidelines', 'Guidelines'),
        ('rules', 'Rules & Regulations'),
        ('howto', 'How to Use ERP')
    ], validators=[DataRequired()])
    file = FileField('Resource File', validators=[DataRequired()])
    submit = SubmitField('Upload')

@resources_bp.route('/resources', methods=['GET'])
@login_required
def resources():
    category = request.args.get('category')
    if category:
        resources = Resource.query.filter_by(category=category).all()
    else:
        resources = Resource.query.all()
    return render_template('resources.html', resources=resources, category=category)

@resources_bp.route('/upload_resource', methods=['GET', 'POST'])
@login_required
def upload_resource():
    if not current_user.is_admin():
        flash('Only admins can upload resources.', 'danger')
        return redirect(url_for('resources.resources'))
    
    form = ResourceUploadForm()
    if form.validate_on_submit():
        file = form.file.data
        if file and allowed_file(file.filename):
            if file.content_length > MAX_FILE_SIZE:
                flash('File size exceeds 10MB limit.', 'danger')
                return redirect(url_for('resources.upload_resource'))
            
            filename = secure_filename(file.filename)
            ext = filename.rsplit('.', 1)[1].lower()
            new_filename = f"{uuid.uuid4().hex}.{ext}"
            file_path = os.path.join(UPLOAD_FOLDER, new_filename)
            
            try:
                file.save(file_path)
                resource = Resource(
                    title=form.title.data,
                    category=form.category.data,
                    filename=new_filename,
                    uploaded_by=current_user.id
                )
                db.session.add(resource)
                db.session.commit()
                flash('Resource uploaded successfully!', 'success')
                return redirect(url_for('resources.resources'))
            except Exception as e:
                db.session.rollback()
                flash(f'Error uploading resource: {str(e)}', 'danger')
        else:
            flash('Invalid file type. Allowed types: pdf, doc, docx, xls, xlsx', 'danger')
    return render_template('upload_resource.html', form=form)

@resources_bp.route('/resources/<filename>')
@login_required
def download_resource(filename):
    return send_from_directory(UPLOAD_FOLDER, filename, as_attachment=False)