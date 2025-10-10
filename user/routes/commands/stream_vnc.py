from flask import Blueprint, render_template, jsonify, request
from ..auth import auth_required
from models.devices import Device
import requests
from datetime import datetime
import logging

logger = logging.getLogger('VNCStreamCommand')

stream_vnc_bp = Blueprint('stream_vnc_command', __name__)

# State tracking for VNC streams
vnc_states = {}


@stream_vnc_bp.route('/device/<device_id>/commands/stream-vnc')
@auth_required
def stream_vnc_page(device_id):
    # Get current VNC state for this device
    state = vnc_states.get(device_id, {})
    active = state.get('active', False)
    
    return render_template(
        'pages/commands/stream_vnc.html',
        device_id=device_id,
        vnc_port=5002,
        active_stream=active
    )


@stream_vnc_bp.route('/device/<device_id>/apis/vnc/start', methods=['POST'])
@auth_required
def vnc_start(device_id):
    """Start VNC streaming on the device"""
    device = Device.query.get(device_id)
    if not device:
        return jsonify(success=False, message='Device not found'), 404
    
    device_ip = device.device_ip
    url = f"http://{device_ip}:8080/vnc/start"
    
    try:
        logger.info(f"Starting VNC stream for device {device_id} at {device_ip}")
        resp = requests.get(url, timeout=10)
        
        if resp.ok:
            # Update state tracking
            vnc_states[device_id] = {
                'active': True,
                'started_at': datetime.utcnow().isoformat(),
                'device_ip': device_ip
            }
            logger.info(f"VNC stream started successfully for device {device_id}")
            return jsonify(success=True, active=True, message='VNC stream started')
        else:
            logger.error(f"Device responded with status {resp.status_code} for VNC start")
            return jsonify(success=False, message=f'Device responded {resp.status_code}'), 502
            
    except requests.exceptions.Timeout:
        logger.error(f"Timeout starting VNC stream for device {device_id}")
        return jsonify(success=False, message='Device timeout'), 504
    except Exception as e:
        logger.error(f"Error starting VNC stream: {str(e)}")
        return jsonify(success=False, message=str(e)), 500


@stream_vnc_bp.route('/device/<device_id>/apis/vnc/stop', methods=['POST'])
@auth_required
def vnc_stop(device_id):
    """Stop VNC streaming on the device"""
    device = Device.query.get(device_id)
    if not device:
        return jsonify(success=False, message='Device not found'), 404
    
    device_ip = device.device_ip
    url = f"http://{device_ip}:8080/vnc/stop"
    
    try:
        logger.info(f"Stopping VNC stream for device {device_id} at {device_ip}")
        resp = requests.get(url, timeout=10)
        
        # Regardless of response, mark inactive (device may have disconnected)
        state = vnc_states.setdefault(device_id, {})
        state['active'] = False
        state['stopped_at'] = datetime.utcnow().isoformat()
        
        if resp.ok:
            logger.info(f"VNC stream stopped successfully for device {device_id}")
            return jsonify(success=True, active=False, message='VNC stream stopped')
        else:
            logger.warning(f"Device responded with status {resp.status_code} for VNC stop, but marking inactive")
            return jsonify(success=True, active=False, message='VNC stream marked as stopped')
            
    except requests.exceptions.Timeout:
        logger.warning(f"Timeout stopping VNC stream for device {device_id}, marking inactive")
        state = vnc_states.setdefault(device_id, {})
        state['active'] = False
        return jsonify(success=True, active=False, message='VNC stream marked as stopped (timeout)')
    except Exception as e:
        logger.error(f"Error stopping VNC stream: {str(e)}")
        # Still mark as inactive even if there was an error
        state = vnc_states.setdefault(device_id, {})
        state['active'] = False
        return jsonify(success=True, active=False, message='VNC stream marked as stopped (error)')


@stream_vnc_bp.route('/device/<device_id>/apis/vnc/status', methods=['GET'])
@auth_required
def vnc_status(device_id):
    """Get current VNC streaming status"""
    state = vnc_states.get(device_id, {})
    return jsonify({
        'active': state.get('active', False),
        'started_at': state.get('started_at'),
        'stopped_at': state.get('stopped_at'),
        'device_ip': state.get('device_ip')
    })
