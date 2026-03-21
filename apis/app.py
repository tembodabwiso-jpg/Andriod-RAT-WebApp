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
from apis.routes.provisioning import provisioning_bp
from apis.routes.device_auth import device_auth_bp
from utils.jwt_auth import create_token, create_access_token
# Models
from models.devices import *  # noqa: F403
from models.devices import RefreshToken
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

# ── Rate Limiting ────────────────────────────────────────────────────────
# Token bucket strategy — allows short bursts but enforces sustained limits.
# Key function extracts device_id from JWT or falls back to IP.
def _rate_limit_key():
    """Extract rate limit key: device_id from JWT token, or IP address."""
    auth = request.headers.get('Authorization', '')
    if auth.startswith('Bearer '):
        try:
            from utils.jwt_auth import decode_token
            payload = decode_token(auth.split(' ', 1)[1])
            return f"device:{payload.get('sub', request.remote_addr)}"
        except Exception:
            pass
    return f"ip:{request.remote_addr}"

limiter = Limiter(
    app,
    key_func=_rate_limit_key,
    default_limits=["120 per hour", "30 per minute"],  # default for all endpoints
    storage_uri="memory://",
)

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
        access_token = create_access_token(admin.id, role='admin', token_type='user')
        refresh_raw, _ = RefreshToken.create_for_user(
            admin.id, role='admin', ip=request.remote_addr
        )
        db.session.commit()
        return jsonify({
            'token': access_token,
            'access_token': access_token,
            'refresh_token': refresh_raw,
            'user': {'id': admin.id, 'email': admin.email, 'name': admin.fullname, 'role': 'admin'}
        }), 200

    # Check regular user
    user = User.query.filter_by(email=email).first()
    if user and check_password_hash(user.password, password):
        access_token = create_access_token(user.id, role='user', token_type='user')
        refresh_raw, _ = RefreshToken.create_for_user(
            user.id, role='user', ip=request.remote_addr
        )
        db.session.commit()
        return jsonify({
            'token': access_token,
            'access_token': access_token,
            'refresh_token': refresh_raw,
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
app.register_blueprint(provisioning_bp)
app.register_blueprint(device_auth_bp)

# ── Per-Endpoint Rate Limits (sensitive operations) ──────────────────────────

# Enrollment: 10 per day per IP (devices rarely register)
limiter.limit("10 per day", key_func=lambda: f"ip:{request.remote_addr}")(
    app.view_functions.get('device_auth.device_register')
)
# Token refresh: 30 per hour (one refresh per expired token)
limiter.limit("30 per hour")(
    app.view_functions.get('device_auth.device_refresh')
)
# Login: 10 per minute per IP (brute-force protection)
limiter.limit("10 per minute", key_func=lambda: f"ip:{request.remote_addr}")(
    app.view_functions.get('api_login')
)
# Dangerous commands (wipe, lock): 5 per day per device
limiter.limit("5 per day")(
    app.view_functions.get('commands.send_command')
)


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    socketio.run(app, debug=True, host="0.0.0.0", port=8000, allow_unsafe_werkzeug=True)
