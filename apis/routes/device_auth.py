"""
Device authentication endpoints.
Handles device registration with token issuance and token refresh with rotation.

Flow:
1. Device calls POST /auth/device/register with deviceId + deviceIp
   → receives access_token (1h) + refresh_token (30d)
2. Device includes access_token as Bearer in all API requests
3. When access_token expires (HTTP 401), device calls POST /auth/device/refresh
   with the refresh_token → receives new access_token + new refresh_token (rotation)
"""

from flask import Blueprint, request, jsonify, current_app
from datetime import datetime, timezone
from sqlalchemy.exc import SQLAlchemyError
from models.devices import Device, RefreshToken
from config.database import db
from utils.jwt_auth import create_access_token
from logzero import logger
import os

device_auth_bp = Blueprint('device_auth', __name__)


@device_auth_bp.route('/auth/device/register', methods=['POST'])
def device_register():
    """
    Register a device and issue JWT access + refresh tokens.
    This replaces the old unauthenticated /register-device endpoint.
    """
    try:
        data = request.get_json()
        device_id = data.get('deviceId')
        device_ip = data.get('deviceIp')
        device_name = data.get('deviceName')
        fcm_token = data.get('fcmToken')
        fingerprint = data.get('fingerprint')  # device hardware fingerprint

        if not device_id:
            return jsonify({'error': 'Missing deviceId'}), 400

        # Upsert device record
        device = Device.query.get(device_id)
        if device:
            device.device_ip = device_ip or device.device_ip
            device.last_seen = datetime.now()
            device.status = 'online'
            if device_name:
                device.device_name = device_name
            if fcm_token:
                device.fcm_token = fcm_token
        else:
            device = Device(
                device_id=device_id,
                device_ip=device_ip,
                device_name=device_name,
                fcm_token=fcm_token,
                status='online',
            )
            db.session.add(device)

        # Issue tokens
        access_token = create_access_token(device_id, role='device', token_type='device')
        refresh_raw, _ = RefreshToken.create_for_device(
            device_id,
            fingerprint=fingerprint,
            ip=request.remote_addr,
        )
        db.session.commit()

        # Emit real-time event
        from flask import current_app
        emit_event = current_app.config.get('EMIT_EVENT')
        if emit_event:
            emit_event('device_registered', device.to_dict())

        return jsonify({
            'access_token': access_token,
            'refresh_token': refresh_raw,
            'device_id': device_id,
            'token_type': 'Bearer',
        }), 200

    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Device registration error: {e}")
        return jsonify({'error': 'Registration failed'}), 500


@device_auth_bp.route('/auth/device/refresh', methods=['POST'])
def device_refresh():
    """
    Refresh an expired access token using a valid refresh token.
    The old refresh token is revoked and a new one is issued (rotation).
    """
    try:
        data = request.get_json()
        refresh_token = data.get('refresh_token')

        if not refresh_token:
            return jsonify({'error': 'Missing refresh_token'}), 400

        # Validate and rotate
        new_refresh_raw, new_rt = RefreshToken.validate_and_rotate(
            refresh_token, ip=request.remote_addr
        )

        if not new_rt:
            return jsonify({'error': 'Invalid or expired refresh token'}), 401

        # Issue new access token
        access_token = create_access_token(
            new_rt.subject_id,
            role=new_rt.role,
            token_type=new_rt.subject_type,
        )

        # Update device last_seen
        if new_rt.subject_type == 'device':
            device = Device.query.get(new_rt.subject_id)
            if device:
                device.last_seen = datetime.now()
                device.status = 'online'
                db.session.commit()

        return jsonify({
            'access_token': access_token,
            'refresh_token': new_refresh_raw,
            'token_type': 'Bearer',
        }), 200

    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Token refresh error: {e}")
        return jsonify({'error': 'Refresh failed'}), 500


@device_auth_bp.route('/auth/device/revoke', methods=['POST'])
def device_revoke():
    """Revoke all tokens for a device (called when device is compromised)."""
    from utils.jwt_auth import require_admin
    # This needs admin auth — inline check since we can't use decorator easily here
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return jsonify({'error': 'Admin auth required'}), 401

    try:
        from utils.jwt_auth import decode_token
        payload = decode_token(auth_header.split(' ', 1)[1])
        if payload.get('role') != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
    except Exception:
        return jsonify({'error': 'Invalid admin token'}), 401

    data = request.get_json()
    device_id = data.get('device_id')
    if not device_id:
        return jsonify({'error': 'Missing device_id'}), 400

    RefreshToken.revoke_all_for_subject(device_id)
    return jsonify({'message': f'All tokens revoked for device {device_id}'}), 200
