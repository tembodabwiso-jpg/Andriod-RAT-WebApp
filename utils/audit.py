"""
Audit logging helper. Records admin/user actions for accountability.
"""

from flask import request, g
from config.database import db
from models.devices import AuditLog
import json


def log_action(action: str, target_type: str = None, target_id: str = None, details: dict = None):
    """Log an admin/user action to the audit_logs table."""
    try:
        user_id = getattr(g, 'current_user_id', None)
        ip_address = request.remote_addr if request else None

        entry = AuditLog(
            user_id=user_id,
            action=action,
            target_type=target_type,
            target_id=str(target_id) if target_id else None,
            details=json.dumps(details) if details else None,
            ip_address=ip_address,
        )
        db.session.add(entry)
        db.session.commit()
    except Exception:
        db.session.rollback()
