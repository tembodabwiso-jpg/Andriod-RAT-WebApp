import sys
import os
import threading
import socket
import struct
import cv2
import numpy as np
import time
import logging
from flask import Blueprint, render_template, Response, jsonify, request, current_app
import base64
from threading import Lock
from ..auth import auth_required
from models.devices import Device
import requests
from datetime import datetime

# ---------------------------------------------------------------------------
# NOTE: Legacy TCP camera streaming implementation still present below but the
# new UI now uses the external Socket.IO server (see test-stream.py) that
# emits 'camera_update' events. We add lightweight REST endpoints to control
# the device camera (front/back) and to persist snapshots to disk.
# ---------------------------------------------------------------------------

# Configure logging
# logging.basicConfig(
#     level=logging.DEBUG,
#     format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
# )
logger = logging.getLogger('CameraStreamCommand')

# Create blueprint
stream_camera_bp = Blueprint('stream_camera_command', __name__)

# Global variables for frame sharing
current_frame = None
frame_lock = Lock()
last_frame_time = 0
client_connected = False
camera_server_thread = None
keep_running = True
stream_control = {}  # Dictionary to track stream status for each device
camera_states = {}   # Simplified state tracking for new socket.io driven flow

SNAPSHOT_ROOT = os.path.join('static', 'camera_snapshots')


def _get_snapshot_dir(device_id):
    root_abs = os.path.join(current_app.root_path, '..', SNAPSHOT_ROOT)
    root_abs = os.path.abspath(root_abs)
    device_dir = os.path.join(root_abs, device_id)
    os.makedirs(device_dir, exist_ok=True)
    return device_dir


def _list_snapshots(device_id):
    device_dir = _get_snapshot_dir(device_id)
    if not os.path.isdir(device_dir):
        return []
    files = []
    for f in os.listdir(device_dir):
        if f.lower().endswith(('.jpg', '.jpeg', '.png')):
            full_path = os.path.join(device_dir, f)
            files.append({
                'name': f,
                'url': f"/static/camera_snapshots/{device_id}/{f}",
                'mtime': os.path.getmtime(full_path)
            })
    # Sort newest first
    files.sort(key=lambda x: x['mtime'], reverse=True)
    return files


# Change socket port from 5000 to 5005
SOCKET_PORT = 5001

# Routes


@stream_camera_bp.route('/device/<device_id>/commands/stream-camera')
@auth_required
def stream_camera_page(device_id):
    """Render the camera streaming command page (Socket.IO based)."""
    device = Device.query.get(device_id)
    if not device:
        return "Device not found", 404
    # Initialize simplified camera state
    state = camera_states.setdefault(device_id, {
        'active': False,
        'camera': None,  # 'front' or 'back'
        'started_at': None
    })
    snapshots = _list_snapshots(device_id)
    return render_template(
        'pages/commands/stream_camera.html',
        device_id=device_id,
        device_ip=device.device_ip,
        stream_active=state['active'],
        active_camera=state['camera'],
        started_at=state['started_at'],
        snapshot_files=snapshots
    )

# ---------------- New REST endpoints for Socket.IO based camera flow --------


@stream_camera_bp.route('/device/<device_id>/apis/camera/start', methods=['POST'])
@auth_required
def camera_start(device_id):
    data = request.get_json(force=True, silent=True) or {}
    camera = data.get('camera')  # expected 'front' or 'back'
    if camera not in ('front', 'back'):
        return jsonify(success=False, message='Invalid camera selection'), 400
    device = Device.query.get(device_id)
    if not device:
        return jsonify(success=False, message='Device not found'), 404
    device_ip = device.device_ip
    url = f"http://{device_ip}:8080/camera/start/{camera}"
    try:
        resp = requests.get(url, timeout=10)
        if resp.ok:
            camera_states[device_id] = {
                'active': True,
                'camera': camera,
                'started_at': datetime.utcnow().isoformat()
            }
            return jsonify(success=True, active=True, camera=camera)
        return jsonify(success=False, message=f'Device responded {resp.status_code}'), 502
    except Exception as e:
        return jsonify(success=False, message=str(e)), 500


@stream_camera_bp.route('/device/<device_id>/apis/camera/stop', methods=['POST'])
@auth_required
def camera_stop(device_id):
    device = Device.query.get(device_id)
    if not device:
        return jsonify(success=False, message='Device not found'), 404
    device_ip = device.device_ip
    url = f"http://{device_ip}:8080/camera/stop"
    try:
        resp = requests.get(url, timeout=10)
        # Regardless of response, mark inactive (device may have died)
        state = camera_states.setdefault(device_id, {})
        state['active'] = False
        state['camera'] = None
        return jsonify(success=resp.ok, active=False)
    except Exception as e:
        state = camera_states.setdefault(device_id, {})
        state['active'] = False
        state['camera'] = None
        return jsonify(success=False, active=False, message=str(e)), 500


@stream_camera_bp.route('/device/<device_id>/apis/camera/snapshot', methods=['POST'])
@auth_required
def camera_snapshot_save(device_id):
    payload = request.get_json(force=True, silent=True) or {}
    img_data = payload.get('image')  # can be data URI or raw base64
    if not img_data:
        return jsonify(success=False, message='Missing image data'), 400
    # Strip data URI prefix if present
    if img_data.startswith('data:'):
        try:
            img_data = img_data.split(',', 1)[1]
        except Exception:
            return jsonify(success=False, message='Invalid data URI'), 400
    try:
        binary = base64.b64decode(img_data)
    except Exception:
        return jsonify(success=False, message='Invalid base64'), 400
    ts = datetime.utcnow().strftime('%Y%m%d_%H%M%S_%f')
    filename = f'snapshot_{ts}.jpg'
    out_dir = _get_snapshot_dir(device_id)
    out_path = os.path.join(out_dir, filename)
    with open(out_path, 'wb') as f:
        f.write(binary)
    rel_url = f"/static/camera_snapshots/{device_id}/{filename}"
    return jsonify(success=True, file=rel_url)


@stream_camera_bp.route('/device/<device_id>/apis/camera/snapshots', methods=['GET'])
@auth_required
def camera_snapshot_list(device_id):
    files = _list_snapshots(device_id)
    return jsonify(success=True, files=files)
