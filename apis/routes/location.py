from flask import Blueprint, request, jsonify, current_app
from datetime import datetime
from sqlalchemy.exc import SQLAlchemyError
from models.devices import DeviceLocation, DeviceNotification
from config.database import db
from logzero import logger

location_bp = Blueprint('location', __name__)


def _create_notification(device_id, event_type, message):
    try:
        notif = DeviceNotification(device_id=device_id, event_type=event_type, message=message)
        db.session.add(notif)
        db.session.commit()
    except Exception as e:
        logger.error(f"Failed to create notification: {e}")
        db.session.rollback()


@location_bp.route('/location', methods=['POST'])
def save_location():
    try:
        data = request.get_json()
        device_id = data.get('deviceId')

        if not device_id or data.get('status') != 'success':
            print("Invalid data received:", data)
            return jsonify({'error': 'Invalid location data'}), 400

        location = DeviceLocation(
            device_id=device_id,
            latitude=data.get('latitude'),
            longitude=data.get('longitude'),
            accuracy=data.get('accuracy'),
            provider=data.get('provider'),
            timestamp=datetime.fromtimestamp(data.get('timestamp') / 1000.0)
        )
        db.session.add(location)
        db.session.commit()

        _create_notification(device_id, 'new_location', f'New location update from device {device_id[:8]}')

        # Emit real-time location update via Socket.IO
        emit_event = current_app.config.get('EMIT_EVENT')
        if emit_event:
            emit_event('location_updated', {
                'device_id': device_id,
                'latitude': data.get('latitude'),
                'longitude': data.get('longitude'),
                'accuracy': data.get('accuracy'),
                'provider': data.get('provider'),
            })

        return jsonify({'message': 'Location saved successfully'}), 200

    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@location_bp.route('/device/<device_id>/locations', methods=['GET'])
def get_device_locations(device_id):
    try:
        locations = DeviceLocation.query.filter_by(device_id=device_id)\
            .order_by(DeviceLocation.timestamp.desc()).all()
        return jsonify([location.to_dict() for location in locations]), 200

    except SQLAlchemyError as e:
        return jsonify({'error': str(e)}), 500


@location_bp.route('/device/<device_id>/last-location', methods=['GET'])
def get_device_last_location(device_id):
    try:
        location = DeviceLocation.query.filter_by(device_id=device_id)\
            .order_by(DeviceLocation.timestamp.desc()).first()

        if not location:
            return jsonify({'error': 'No location data found'}), 404

        return jsonify(location.to_dict()), 200

    except SQLAlchemyError as e:
        return jsonify({'error': str(e)}), 500
