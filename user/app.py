import sys
import os

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

from models.users import User
from flask import Flask, render_template, session, redirect, url_for
from dotenv import load_dotenv
from flask_wtf.csrf import CSRFProtect, CSRFError
from datetime import timedelta
from user.routes import (auth, dashboard)
import os
from config.database import init_app, db

app = Flask(__name__)


load_dotenv()

app = Flask(__name__, static_folder="../static")
app.secret_key = os.getenv("SECRET_KEY")
app.config['WTF_CSRF_ENABLED'] = True  # Enable CSRF protection
app.config['WTF_CSRF_TIME_LIMIT'] = None  # No time limit for CSRF tokens
app.permanent_session_lifetime = timedelta(
    hours=12)  # Set session timeout to 12 hours
csrf = CSRFProtect(app)

init_app(app)


@app.errorhandler(404)
def page_not_found(e):
    return render_template('errors/404.html'), 404


@app.errorhandler(500)
def internal_server_error():
    return render_template('errors/500.html'), 500


@app.errorhandler(CSRFError)
def handle_csrf_error(e):
    return render_template('errors/400.html'), 400


@app.route('/')
def index():
    if 'admin_id' in session:
        return redirect(url_for('dashboard.index'))
    return redirect(url_for('auth.login'))


app.register_blueprint(auth.auth)
app.register_blueprint(dashboard.dashboard)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
