from flask import Blueprint, render_template

chat_bp = Blueprint('chat', __name__)

@chat_bp.route('/')
def chat():
    return render_template('chat.html')