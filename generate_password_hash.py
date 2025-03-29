# generate_password_hash.py
from werkzeug.security import generate_password_hash
print(generate_password_hash('admin'))