import sys
import os

# Get the project root directory (one level up from 'apis')
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from flask_limiter import Limiter
from flask_cors import CORS
from flask_seasurf import SeaSurf
from flask_socketio import SocketIO
import os
from dotenv import load_dotenv
from config.database import db, init_app
from config.fcm import init_fcm
from apis.routes import devices, location, keystrokes, apps, communication, system
from apis.routes.commands import commands_bp
from apis.routes.policies import policies_bp
from utils.jwt_auth import create_token
# Models
from models.devices import *
from models.admins import Admin
from models.users import User

load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")
app.config["WTF_CSRF_SECRET_KEY"] = os.getenv("CSRF_SECRET_KEY")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

init_app(app)

CORS(app, supports_credentials=True)
# API server uses JWT auth, not CSRF tokens — disable CSRF entirely
app.config['SEASURF_INCLUDE_OR_EXEMPT_VIEWS'] = 'exempt'
csrf = SeaSurf(app)
limiter = Limiter(app)

# Initialize Socket.IO for real-time updates to dashboard
socketio = SocketIO(app, cors_allowed_origins='*', async_mode='threading')

# Initialize Firebase Cloud Messaging (gracefully skips if not configured)
with app.app_context():
    init_fcm()

# ── Authentication Endpoint ───────────────────────────────────────────────────

@app.route('/auth/login', methods=['POST'])
def api_login():
    """Authenticate admin or user and return a JWT token."""
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({'error': 'Missing email or password'}), 400

    # Check admin first
    from werkzeug.security import check_password_hash
    admin = Admin.query.filter_by(email=email).first()
    if admin and check_password_hash(admin.password, password):
        token = create_token(admin.id, role='admin')
        return jsonify({
            'token': token,
            'user': {'id': admin.id, 'email': admin.email, 'name': admin.fullname, 'role': 'admin'}
        }), 200

    # Check regular user
    user = User.query.filter_by(email=email).first()
    if user and check_password_hash(user.password, password):
        token = create_token(user.id, role='user')
        return jsonify({
            'token': token,
            'user': {'id': user.id, 'email': user.email, 'name': user.fullname, 'role': 'user'}
        }), 200

    return jsonify({'error': 'Invalid credentials'}), 401


# ── Socket.IO Events ──────────────────────────────────────────────────────────

@socketio.on('connect')
def handle_connect():
    from flask_socketio import emit
    emit('connected', {'status': 'ok'})


@socketio.on('subscribe_device')
def handle_subscribe(data):
    """Dashboard clients can subscribe to updates for a specific device."""
    from flask_socketio import join_room
    device_id = data.get('device_id')
    if device_id:
        join_room(f'device_{device_id}')


# Helper to emit events from route handlers
def emit_event(event_name, data, device_id=None):
    """Emit a Socket.IO event. If device_id provided, emits to that device's room."""
    try:
        if device_id:
            socketio.emit(event_name, data, room=f'device_{device_id}')
        else:
            socketio.emit(event_name, data)
    except Exception:
        pass  # Non-critical: don't break API if socketio fails


# Make emit_event available to blueprints via app config
app.config['EMIT_EVENT'] = emit_event


# ── Register Blueprints ───────────────────────────────────────────────────────

app.register_blueprint(devices.devices_bp)
app.register_blueprint(location.location_bp)
app.register_blueprint(keystrokes.keystrokes_bp)
app.register_blueprint(apps.apps_bp)
app.register_blueprint(communication.communication_bp)
app.register_blueprint(system.system_bp)
app.register_blueprint(commands_bp)
app.register_blueprint(policies_bp)

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    socketio.run(app, debug=True, host="0.0.0.0", port=8000, allow_unsafe_werkzeug=True)
