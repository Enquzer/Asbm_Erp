from main import app, db
from modules.models import User
import hashlib

with app.app_context():
    admin = User.query.filter_by(username='admin').first()
    if admin and hashlib.sha256('admin'.encode()).hexdigest() == admin.password_hash:
        admin.set_password('admin')
        db.session.commit()
        print("Admin password migrated successfully.")
    else:
        print("Admin user not found or password already migrated.")