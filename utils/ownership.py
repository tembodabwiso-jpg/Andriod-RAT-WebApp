"""
IDOR Protection — Device/resource ownership validation.

Enforces that authenticated users/devices can only access their own resources:
  - Device tokens: can only access data matching their own device_id (JWT sub)
  - User tokens: can only access devices they own (Device.user_id == JWT sub)
  - Admin tokens: unrestricted access

Usage in routes:
    from utils.ownership import verify_device_access, verify_command_access

    @require_auth
    def get_device_info(device_id):
        check = verify_device_access(device_id)
        if check: return check  # returns 403 response if unauthorized
        ...
"""

from flask import g, jsonify
from functools import wraps


def verify_device_access(device_id: str):
    """
    Verify the current authenticated user/device can access the given device_id.
    Returns None if authorized, or a (response, status_code) tuple if denied.

    Rules:
      - admin role: always allowed
      - device token: JWT sub must match device_id
      - user token: Device.user_id must match JWT sub
    """
    role = getattr(g, 'current_user_role', None)
    subject = getattr(g, 'current_user_id', None)
    token_type = getattr(g, 'token_type', 'user')

    # No auth context — deny
    if not subject:
        return jsonify({'error': 'Authentication required'}), 401

    # Admins can access everything
    if role == 'admin':
        return None

    # Device token: can only access own data
    if token_type == 'device':
        if subject != device_id:
            return jsonify({'error': 'Access denied: device can only access its own data'}), 403
        return None

    # User token: check device ownership
    from models.devices import Device
    device = Device.query.get(device_id)
    if not device:
        return jsonify({'error': 'Device not found'}), 404
    if device.user_id and str(device.user_id) != str(subject):
        return jsonify({'error': 'Access denied: you do not own this device'}), 403

    return None


def verify_command_access(command_id: int):
    """
    Verify the current user/device can access the given command.
    Checks ownership of the command's target device.
    Returns None if authorized, or a (response, status_code) tuple if denied.
    """
    role = getattr(g, 'current_user_role', None)
    if role == 'admin':
        return None

    from models.devices import Command
    command = Command.query.get(command_id)
    if not command:
        return jsonify({'error': 'Command not found'}), 404

    return verify_device_access(command.device_id)


def verify_device_body_access():
    """
    Verify ownership for POST requests where device_id is in the request body.
    Extracts deviceId from JSON body and validates access.
    Returns None if authorized, or a (response, status_code) tuple if denied.
    """
    from flask import request
    data = request.get_json(silent=True) or {}
    device_id = data.get('deviceId') or data.get('device_id')
    if not device_id:
        return None  # Let the route handle missing device_id
    return verify_device_access(device_id)


def require_device_ownership(f):
    """
    Decorator for routes with <device_id> URL parameter.
    Combines @require_auth + ownership check.
    """
    from utils.jwt_auth import require_auth

    @wraps(f)
    @require_auth
    def decorated(*args, **kwargs):
        device_id = kwargs.get('device_id')
        if device_id:
            check = verify_device_access(device_id)
            if check:
                return check
        return f(*args, **kwargs)
    return decorated


def require_body_ownership(f):
    """
    Decorator for POST routes where deviceId is in request body.
    Combines @require_auth + body ownership check.
    """
    from utils.jwt_auth import require_auth

    @wraps(f)
    @require_auth
    def decorated(*args, **kwargs):
        check = verify_device_body_access()
        if check:
            return check
        return f(*args, **kwargs)
    return decorated
