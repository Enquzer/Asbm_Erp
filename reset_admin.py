from database import db
from modules.models import User
from werkzeug.security import generate_password_hash
import os

# Initialize the database
db_file = os.path.join(os.path.dirname(__file__), 'instance', 'asbm_erp.db')
if not os.path.exists(db_file):
    raise FileNotFoundError("Database file not found. Run init_db.py first.")

# Drop the existing admin user if it exists
db.session.query(User).filter_by(username='admin').delete()
db.session.commit()

# Create a new admin user
admin_user = User(
    username='admin',
    password_hash=generate_password_hash('admin'),
    role='Admin'
)
admin_user.permissions = {
    'dashboard': True, 'orders': True, 'products': True, 'hr': True,
    'notifications': True, 'planning': True, 'production': True,
    'project': True, 'purchasing': True, 'stock_management': True,
    'sales': True, 'system_setup': True, 'user_management': True, 'chat': True
}
db.session.add(admin_user)
db.session.commit()

print("Admin user reset successfully. Username: admin, Password: admin")