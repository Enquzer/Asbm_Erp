# modules/notifications.py
from flask import Blueprint, render_template, flash
from flask_login import login_required

notifications_bp = Blueprint('notifications', __name__)

def send_notification(recipient, message):
    """Send a notification to the specified recipient."""
    flash(f"Notification to {recipient}: {message}", 'info')

@notifications_bp.route('/')
@login_required
def notifications():
    return render_template('notifications.html')