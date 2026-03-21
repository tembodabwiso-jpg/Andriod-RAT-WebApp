"""
QR Code Provisioning API routes.
Generates QR codes for Android device enrollment via device owner provisioning.
"""

import io
import json
import base64

from flask import Blueprint, request, jsonify, send_file
import qrcode
from PIL import Image

provisioning_bp = Blueprint('provisioning', __name__)

# Cache the last generated QR image bytes so /qr-image can serve it
_last_qr_png: bytes | None = None


def _build_provisioning_payload(server_ip: str, wifi_ssid: str | None = None) -> dict:
    """Build the Android provisioning JSON payload."""
    apk_url = f"http://{server_ip}:8000/static/apk/mdm-client.apk"

    payload = {
        "android.app.extra.PROVISIONING_DEVICE_ADMIN_COMPONENT_NAME":
            "com.mdm.client/.commands.MdmDeviceAdminReceiver",
        "android.app.extra.PROVISIONING_DEVICE_ADMIN_PACKAGE_DOWNLOAD_LOCATION":
            apk_url,
        "android.app.extra.PROVISIONING_SKIP_ENCRYPTION": True,
        "server_ip": server_ip,
    }

    if wifi_ssid:
        payload["android.app.extra.PROVISIONING_WIFI_SSID"] = wifi_ssid

    return payload


def _generate_qr_png(data: str) -> bytes:
    """Generate a QR code PNG image and return the raw bytes."""
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)

    img: Image.Image = qr.make_image(fill_color="black", back_color="white").convert("RGB")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.read()


# ── POST /provisioning/generate-qr ──────────────────────────────────────────

@provisioning_bp.route('/provisioning/generate-qr', methods=['POST'])
def generate_qr():
    """
    Generate a QR code for device enrollment.

    Accepts JSON body with optional fields:
      - server_ip: str  (defaults to the request host)
      - wifi_ssid: str  (optional)

    Returns JSON with a base64-encoded PNG image of the QR code.
    """
    global _last_qr_png

    data = request.get_json(silent=True) or {}
    server_ip = data.get('server_ip') or request.host.split(':')[0]
    wifi_ssid = data.get('wifi_ssid') or None

    payload = _build_provisioning_payload(server_ip, wifi_ssid)
    payload_json = json.dumps(payload)

    png_bytes = _generate_qr_png(payload_json)
    _last_qr_png = png_bytes

    b64_image = base64.b64encode(png_bytes).decode('utf-8')

    return jsonify({
        'qr_base64': b64_image,
        'payload': payload,
    }), 200


# ── GET /provisioning/qr-image ──────────────────────────────────────────────

@provisioning_bp.route('/provisioning/qr-image', methods=['GET'])
def qr_image():
    """
    Serve the most recently generated QR code as a PNG image.
    If none has been generated yet, create one using the request host.
    """
    global _last_qr_png

    if _last_qr_png is None:
        server_ip = request.host.split(':')[0]
        payload = _build_provisioning_payload(server_ip)
        payload_json = json.dumps(payload)
        _last_qr_png = _generate_qr_png(payload_json)

    buf = io.BytesIO(_last_qr_png)
    buf.seek(0)
    return send_file(buf, mimetype='image/png', download_name='enrollment-qr.png')


# ── GET /provisioning/enroll/<device_id> ─────────────────────────────────────

@provisioning_bp.route('/provisioning/enroll/<device_id>', methods=['GET'])
def enroll_device(device_id: str):
    """
    Return enrollment configuration JSON for a specific device.
    The Android client hits this endpoint after scanning the QR code.
    """
    server_ip = request.host.split(':')[0]

    config = {
        'device_id': device_id,
        'server_ip': server_ip,
        'api_base_url': f'http://{server_ip}:8000',
        'heartbeat_interval': 60,
        'enrollment_status': 'pending',
    }

    return jsonify(config), 200
