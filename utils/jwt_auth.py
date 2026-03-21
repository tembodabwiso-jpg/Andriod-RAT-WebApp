"""
JWT authentication utilities for the API server.
Implements short-lived access tokens + long-lived refresh tokens with rotation.

Access tokens:  1 hour (configurable via JWT_ACCESS_EXPIRY_MINUTES)
Refresh tokens: 30 days (configurable via JWT_REFRESH_EXPIRY_DAYS)

Access tokens are stateless (validated by signature + expiry).
Refresh tokens are stored in DB and rotated on each use.
"""

import os
import secrets
import jwt
from datetime import datetime, timedelta, timezone
from functools import wraps
from flask import request, jsonify, g

JWT_SECRET = os.getenv('JWT_SECRET', os.getenv('SECRET_KEY', 'change-me-in-production'))
JWT_ALGORITHM = 'HS256'
JWT_ISSUER = 'mdm-server'
JWT_AUDIENCE = 'mdm-api'
JWT_ACCESS_EXPIRY_MINUTES = int(os.getenv('JWT_ACCESS_EXPIRY_MINUTES', '60'))
JWT_REFRESH_EXPIRY_DAYS = int(os.getenv('JWT_REFRESH_EXPIRY_DAYS', '30'))

# Legacy compat
JWT_EXPIRY_HOURS = int(os.getenv('JWT_EXPIRY_HOURS', '24'))


def create_access_token(subject: str, role: str = 'user', token_type: str = 'user') -> str:
    """
    Create a short-lived JWT access token.
    subject: user_id or device_id
    role: 'admin', 'user', or 'device'
    token_type: 'user' or 'device'
    """
    now = datetime.now(timezone.utc)
    payload = {
        'sub': str(subject),
        'role': role,
        'type': token_type,
        'iss': JWT_ISSUER,
        'aud': JWT_AUDIENCE,
        'iat': now,
        'exp': now + timedelta(minutes=JWT_ACCESS_EXPIRY_MINUTES),
        'jti': secrets.token_hex(16),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def create_refresh_token() -> str:
    """Create a cryptographically secure opaque refresh token."""
    return secrets.token_urlsafe(64)


def create_token(user_id: str, role: str = 'user') -> str:
    """Legacy: create an access token (backward-compatible)."""
    return create_access_token(user_id, role, token_type='user')


def decode_token(token: str) -> dict:
    """Decode and validate a JWT access token with full claim verification."""
    return jwt.decode(
        token,
        JWT_SECRET,
        algorithms=[JWT_ALGORITHM],
        issuer=JWT_ISSUER,
        audience=JWT_AUDIENCE,
        options={
            'require': ['sub', 'exp', 'iat', 'iss', 'aud', 'type'],
            'verify_exp': True,
            'verify_iss': True,
            'verify_aud': True,
        }
    )


def require_auth(f):
    """Decorator: requires a valid JWT access token in the Authorization header."""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Missing or invalid Authorization header'}), 401

        token = auth_header.split(' ', 1)[1]
        try:
            payload = decode_token(token)
            g.current_user_id = payload['sub']
            g.current_user_role = payload.get('role', 'user')
            g.token_type = payload.get('type', 'user')
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token expired', 'code': 'TOKEN_EXPIRED'}), 401
        except jwt.InvalidTokenError as e:
            return jsonify({'error': f'Invalid token: {e}'}), 401

        return f(*args, **kwargs)
    return decorated


def require_device_auth(f):
    """Decorator: requires a valid device JWT token."""
    @wraps(f)
    @require_auth
    def decorated(*args, **kwargs):
        if g.token_type != 'device':
            return jsonify({'error': 'Device token required'}), 403
        return f(*args, **kwargs)
    return decorated


def require_admin(f):
    """Decorator: requires admin role."""
    @wraps(f)
    @require_auth
    def decorated(*args, **kwargs):
        if g.current_user_role != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated
