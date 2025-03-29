from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from modules.models import User, db
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, BooleanField, FileField
from wtforms.validators import DataRequired, Length, EqualTo
import os
from werkzeug.utils import secure_filename
import uuid
import logging

user_management_bp = Blueprint('user_management', __name__)
UPLOAD_FOLDER = 'static/images/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

# Logging setup
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Ensure upload folder exists and is writable
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
    logger.info(f"Created upload folder: {UPLOAD_FOLDER}")
if not os.access(UPLOAD_FOLDER, os.W_OK):
    logger.error(f"Upload folder {UPLOAD_FOLDER} is not writable! Fix permissions and restart.")
    raise PermissionError(f"Upload folder {UPLOAD_FOLDER} is not writable.")

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=4, max=50)])
    password = PasswordField('Password', validators=[DataRequired()])
    remember = BooleanField('Remember me')
    submit = SubmitField('Login')

class RegisterForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=4, max=50)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    role = StringField('Role', validators=[DataRequired()])
    submit = SubmitField('Register')

class ProfileForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=4, max=50)])
    profile_picture = FileField('Profile Picture')
    password = PasswordField('New Password', validators=[Length(min=6)])
    confirm_password = PasswordField('Confirm New Password', validators=[EqualTo('password')])
    submit = SubmitField('Update Profile')

@user_management_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.dashboard'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        logger.debug(f"Login attempt: Username={form.username.data}")
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember.data)
            flash('Login successful!', 'success')
            logger.info(f"User '{user.username}' logged in.")
            return redirect(request.args.get('next') or url_for('dashboard.dashboard'))
        flash('Invalid username or password', 'danger')
        logger.error(f"Login failed for '{form.username.data}'.")
    return render_template('login.html', form=form, title='Login')

@user_management_bp.route('/logout')
@login_required
def logout():
    logger.info(f"User '{current_user.username}' logged out.")
    logout_user()
    flash('You have been logged out.', 'success')
    return redirect(url_for('user_management.login'))

@user_management_bp.route('/register', methods=['GET', 'POST'])
@login_required
def register():
    if not current_user.is_admin():
        flash('Only admins can register new users.', 'danger')
        return redirect(url_for('dashboard.dashboard'))
    form = RegisterForm()
    if form.validate_on_submit():
        if User.query.filter_by(username=form.username.data).first():
            flash('Username already exists.', 'danger')
            logger.warning(f"Username '{form.username.data}' already exists.")
        else:
            try:
                new_user = User(
                    username=form.username.data,
                    role=form.role.data,
                    permissions={'dashboard': {'view': True}}
                )
                new_user.set_password(form.password.data)
                db.session.add(new_user)
                db.session.commit()
                flash('User registered successfully!', 'success')
                logger.info(f"New user '{form.username.data}' registered.")
                return redirect(url_for('user_management.manage_users'))
            except Exception as e:
                db.session.rollback()
                flash('Error registering user.', 'danger')
                logger.error(f"Error registering user: {str(e)}")
    return render_template('register.html', form=form, title='Register')

@user_management_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    form = ProfileForm(username=current_user.username)
    if request.method == 'POST':
        logger.debug(f"Profile POST: Form data={form.data}, Files={request.files}")
    if form.validate_on_submit():
        logger.debug(f"Profile update for '{current_user.username}' validated.")
        if User.query.filter_by(username=form.username.data).first() and form.username.data != current_user.username:
            flash('Username already taken.', 'danger')
            logger.warning(f"Username '{form.username.data}' taken.")
        else:
            current_user.username = form.username.data
            if 'profile_picture' in request.files and form.profile_picture.data:
                file = form.profile_picture.data
                if allowed_file(file.filename):
                    ext = file.filename.rsplit('.', 1)[1].lower()
                    new_filename = f"{uuid.uuid4().hex}.{ext}"
                    file_path = os.path.join(UPLOAD_FOLDER, new_filename)
                    logger.debug(f"Saving new profile picture to: {file_path}")
                    try:
                        # Remove old picture if it exists
                        if current_user.profile_picture and current_user.profile_picture != 'placeholder_user.jpg':
                            old_path = os.path.join(UPLOAD_FOLDER, current_user.profile_picture)
                            if os.path.exists(old_path):
                                os.remove(old_path)
                                logger.info(f"Removed old picture: {old_path}")
                            else:
                                logger.warning(f"Old picture not found: {old_path}")
                        # Save new picture
                        file.save(file_path)
                        if os.path.exists(file_path):
                            current_user.profile_picture = new_filename
                            db.session.commit()
                            flash('Profile picture updated!', 'success')
                            logger.info(f"Profile picture for '{current_user.username}' updated to {new_filename}")
                        else:
                            flash('Failed to save new picture.', 'danger')
                            logger.error(f"File not saved: {file_path}")
                    except Exception as e:
                        flash('Error uploading picture.', 'danger')
                        logger.error(f"Upload error: {str(e)}")
                else:
                    flash('Invalid file type. Use png, jpg, or jpeg.', 'danger')
                    logger.warning(f"Invalid file type: {file.filename}")
            if form.password.data:
                current_user.set_password(form.password.data)
                db.session.commit()
                flash('Password updated!', 'success')
                logger.info(f"Password updated for '{current_user.username}'.")
            if not form.profile_picture.data and not form.password.data:
                db.session.commit()
                flash('Profile updated!', 'success')
            return redirect(url_for('user_management.profile'))
    else:
        if request.method == 'POST':
            logger.debug(f"Form validation failed: {form.errors}")
    return render_template('profile.html', form=form, title='Profile', profile_picture=current_user.profile_picture)

@user_management_bp.route('/manage_users', methods=['GET', 'POST'])
@login_required
def manage_users():
    if not current_user.is_admin():
        flash('Only admins can manage users.', 'danger')
        return redirect(url_for('dashboard.dashboard'))
    form = RegisterForm()
    if request.method == 'POST':
        logger.debug(f"Manage users POST: {request.form}")
        user_id = request.form.get('user_id')
        action = request.form.get('action')
        user = User.query.get(user_id)
        if not user:
            flash('User not found.', 'danger')
            logger.error(f"User ID {user_id} not found.")
        elif action == 'delete':
            db.session.delete(user)
            db.session.commit()
            flash('User deleted!', 'success')
            logger.info(f"User '{user.username}' deleted.")
        elif action == 'update_permissions':
            permissions = {}
            modules = ['dashboard', 'orders', 'products', 'customers', 'hr', 'notifications', 'planning', 'production', 'project', 'purchasing', 'stock_management', 'sales', 'system_setup', 'user_management', 'chat']
            for module in modules:
                view = request.form.get(f'{module}_view') == 'on'
                edit = request.form.get(f'{module}_edit') == 'on'
                delete = request.form.get(f'{module}_delete') == 'on'
                if view or edit or delete:
                    permissions[module] = {'view': view, 'edit': edit, 'delete': delete}
            if permissions:
                user.permissions = permissions
                db.session.commit()
                flash('Permissions updated!', 'success')
                logger.info(f"Permissions for '{user.username}': {permissions}")
            else:
                flash('No permissions selected.', 'warning')
    users = User.query.all()
    modules = ['dashboard', 'orders', 'products', 'customers', 'hr', 'notifications', 'planning', 'production', 'project', 'purchasing', 'stock_management', 'sales', 'system_setup', 'user_management', 'chat']
    return render_template('manage_users.html', users=users, modules=modules, title='Manage Users', form=form)