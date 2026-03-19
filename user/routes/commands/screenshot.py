import os
from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from ..auth import auth_required
from models.devices import Device, Screenshot
from config.database import db
from user.apis.devices import captureScreenshot
from datetime import datetime
from logzero import logger

screenshot_command = Blueprint('screenshot_command', __name__)

SCREENSHOT_ROOT = os.path.join('static', 'screenshots')


def _get_screenshot_dir(device_id):
    from flask import current_app
    root_abs = os.path.abspath(os.path.join(current_app.root_path, '..', SCREENSHOT_ROOT))
    device_dir = os.path.join(root_abs, device_id)
    os.makedirs(device_dir, exist_ok=True)
    return device_dir


@screenshot_command.route('/device/<device_id>/commands/screenshot')
@auth_required
def screenshot_page(device_id):
    device = Device.query.get(device_id)
    if not device:
        return redirect(url_for('devices.get_devices'))
    screenshots = Screenshot.query.filter_by(device_id=device_id)\
        .order_by(Screenshot.created_at.desc()).all()
    return render_template(
        'pages/commands/screenshot.html',
        device=device,
        device_id=device_id,
        device_ip=device.device_ip,
        screenshots=screenshots
    )


@screenshot_command.route('/device/<device_id>/apis/screenshot/capture', methods=['POST'])
@auth_required
def capture_screenshot(device_id):
    device = Device.query.get(device_id)
    if not device:
        return jsonify(success=False, message='Device not found'), 404

    result = captureScreenshot(device_id, device.device_ip)
    if not result:
        return jsonify(success=False, message='Device unreachable or capture failed'), 502

    # result expected: { "filename": "...", "file_url": "..." }
    filename = result.get('filename') or result.get('file_name')
    file_url = result.get('file_url') or result.get('url')

    if not filename or not file_url:
        return jsonify(success=False, message='Invalid response from device'), 500

    screenshot = Screenshot(
        device_id=device_id,
        filename=filename,
        file_url=file_url,
        created_at=datetime.now()
    )
    db.session.add(screenshot)
    db.session.commit()
    return jsonify(success=True, screenshot=screenshot.to_dict())


@screenshot_command.route('/device/<device_id>/apis/screenshot/list', methods=['GET'])
@auth_required
def list_screenshots(device_id):
    screenshots = Screenshot.query.filter_by(device_id=device_id)\
        .order_by(Screenshot.created_at.desc()).all()
    return jsonify(success=True, screenshots=[s.to_dict() for s in screenshots])


@screenshot_command.route('/device/<device_id>/apis/screenshot/<int:screenshot_id>/delete', methods=['DELETE'])
@auth_required
def delete_screenshot(device_id, screenshot_id):
    screenshot = Screenshot.query.filter_by(id=screenshot_id, device_id=device_id).first()
    if not screenshot:
        return jsonify(success=False, message='Screenshot not found'), 404
    db.session.delete(screenshot)
    db.session.commit()
    return jsonify(success=True)
