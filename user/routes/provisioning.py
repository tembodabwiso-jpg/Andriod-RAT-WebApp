"""
User-facing provisioning routes.
Renders the QR code page and proxies API calls.
"""

from flask import Blueprint, render_template, request, jsonify
from user.routes.auth import auth_required
import requests as http_requests
import os

provisioning = Blueprint('provisioning', __name__)


def _get_api_base():
    host = os.getenv('API_HOST', '127.0.0.1')
    port = os.getenv('API_PORT', '8000')
    return f'http://{host}:{port}'


@provisioning.route('/provisioning')
@auth_required
def index():
    """Render the device provisioning / QR code enrollment page."""
    return render_template('pages/provisioning.html')


@provisioning.route('/provisioning/generate-qr', methods=['POST'])
@auth_required
def generate_qr():
    """Proxy QR generation to the API server."""
    try:
        data = request.get_json(silent=True) or {}
        resp = http_requests.post(
            f'{_get_api_base()}/provisioning/generate-qr',
            json=data,
            timeout=10
        )
        return jsonify(resp.json()), resp.status_code
    except Exception as e:
        return jsonify({'error': str(e)}), 500
