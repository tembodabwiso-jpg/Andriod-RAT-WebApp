"""
init_db.py — Initialize or migrate the database.

Usage:
  python init_db.py          # Create all tables (first-time setup)
  python init_db.py migrate  # Generate a new migration after model changes
  python init_db.py upgrade  # Apply pending migrations

For first-time setup, just run:
  python init_db.py
"""

import sys
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from dotenv import load_dotenv
load_dotenv()

from apis.app import app, db

def create_all():
    """Create all tables from scratch (safe for first-time setup)."""
    with app.app_context():
        db.create_all()
        print("All database tables created successfully.")
        print("Tables:", db.engine.table_names() if hasattr(db.engine, 'table_names') else "check DB directly")

def migrate():
    """Generate a new migration (requires flask db init first)."""
    os.system(f'cd "{ROOT}" && set FLASK_APP=apis/app.py && flask db migrate -m "add mdm models"')

def upgrade():
    """Apply pending migrations."""
    os.system(f'cd "{ROOT}" && set FLASK_APP=apis/app.py && flask db upgrade')

def init_migrations():
    """Initialize the migrations folder (one-time)."""
    os.system(f'cd "{ROOT}" && set FLASK_APP=apis/app.py && flask db init')

if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "create"

    if action == "create":
        create_all()
    elif action == "init":
        init_migrations()
    elif action == "migrate":
        migrate()
    elif action == "upgrade":
        upgrade()
    else:
        print(f"Unknown action: {action}")
        print("Usage: python init_db.py [create|init|migrate|upgrade]")
        sys.exit(1)
