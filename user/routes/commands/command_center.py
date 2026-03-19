from flask import Blueprint, render_template, request, jsonify, session, current_app
from ..auth import auth_required
from models.devices import Device, Command
from config.database import db
import requests as http_requests
import os
import json

command_center_command = Blueprint('command_center_command', __name__)

API_BASE = None

def get_api_base():
    global API_BASE
    if API_BASE is None:
        host = os.getenv('API_HOST', '127.0.0.1')
        port = os.getenv('API_PORT', '8000')
        API_BASE = f'http://{host}:{port}'
    return API_BASE


@command_center_command.route('/device/<device_id>/command-center')
@auth_required
def command_center_page(device_id):
    device = Device.query.get(device_id)
    if not device:
        return "Device not found", 404

    # Get recent commands for this device
    commands = Command.query.filter_by(device_id=device_id)\
        .order_by(Command.created_at.desc()).limit(50).all()

    return render_template(
        'pages/commands/command_center.html',
        device=device,
        commands=[c.to_dict() for c in commands],
    )


@command_center_command.route('/device/<device_id>/send-command', methods=['POST'])
@auth_required
def send_command(device_id):
    """Send a command to a device via the API server."""
    try:
        command_type = request.form.get('command_type')
        payload_str = request.form.get('payload', '{}')

        try:
            payload = json.loads(payload_str) if payload_str else {}
        except json.JSONDecodeError:
            payload = {}

        response = http_requests.post(
            f'{get_api_base()}/commands/send',
            json={
                'device_id': device_id,
                'command_type': command_type,
                'payload': payload,
            },
            timeout=10
        )

        return jsonify(response.json()), response.status_code

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@command_center_command.route('/device/<device_id>/commands-history')
@auth_required
def commands_history(device_id):
    """Get command history as JSON (for AJAX refresh)."""
    try:
        commands = Command.query.filter_by(device_id=device_id)\
            .order_by(Command.created_at.desc()).limit(50).all()
        return jsonify([c.to_dict() for c in commands])
    except Exception as e:
        return jsonify({'error': str(e)}), 500
