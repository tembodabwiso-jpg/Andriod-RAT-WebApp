from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from ..auth import auth_required
from models.devices import Device, MicRecording
from config.database import db
from user.apis.devices import startMicRecording, stopMicRecording, getMicRecordings
from datetime import datetime
from logzero import logger

microphone_command = Blueprint('microphone_command', __name__)

# Per-device recording state (in-memory; resets on server restart)
_recording_state = {}  # device_id -> bool


@microphone_command.route('/device/<device_id>/commands/microphone')
@auth_required
def microphone_page(device_id):
    device = Device.query.get(device_id)
    if not device:
        return redirect(url_for('devices.get_devices'))
    recordings = MicRecording.query.filter_by(device_id=device_id)\
        .order_by(MicRecording.created_at.desc()).all()
    is_recording = _recording_state.get(device_id, False)
    return render_template(
        'pages/commands/microphone.html',
        device=device,
        device_id=device_id,
        device_ip=device.device_ip,
        recordings=recordings,
        is_recording=is_recording
    )


@microphone_command.route('/device/<device_id>/apis/mic/start', methods=['POST'])
@auth_required
def mic_start(device_id):
    device = Device.query.get(device_id)
    if not device:
        return jsonify(success=False, message='Device not found'), 404

    data = request.get_json(force=True, silent=True) or {}
    duration = int(data.get('duration', 30))

    result = startMicRecording(device_id, device.device_ip, duration)
    if not result:
        return jsonify(success=False, message='Device unreachable or failed to start recording'), 502

    _recording_state[device_id] = True
    return jsonify(success=True, message=result.get('message', 'Recording started'))


@microphone_command.route('/device/<device_id>/apis/mic/stop', methods=['POST'])
@auth_required
def mic_stop(device_id):
    device = Device.query.get(device_id)
    if not device:
        return jsonify(success=False, message='Device not found'), 404

    result = stopMicRecording(device_id, device.device_ip)
    _recording_state[device_id] = False

    if not result:
        return jsonify(success=False, message='Device unreachable or failed to stop recording'), 502

    # result may contain { filename, file_url, duration_seconds }
    filename = result.get('filename') or result.get('file_name')
    file_url = result.get('file_url') or result.get('url')
    duration_seconds = result.get('duration_seconds') or result.get('duration')

    if filename and file_url:
        recording = MicRecording(
            device_id=device_id,
            filename=filename,
            file_url=file_url,
            duration_seconds=duration_seconds,
            created_at=datetime.now()
        )
        db.session.add(recording)
        db.session.commit()
        return jsonify(success=True, recording=recording.to_dict())

    return jsonify(success=True, message=result.get('message', 'Recording stopped'))


@microphone_command.route('/device/<device_id>/apis/mic/status', methods=['GET'])
@auth_required
def mic_status(device_id):
    is_recording = _recording_state.get(device_id, False)
    return jsonify(success=True, is_recording=is_recording)


@microphone_command.route('/device/<device_id>/apis/mic/<int:recording_id>/delete', methods=['DELETE'])
@auth_required
def delete_recording(device_id, recording_id):
    recording = MicRecording.query.filter_by(id=recording_id, device_id=device_id).first()
    if not recording:
        return jsonify(success=False, message='Recording not found'), 404
    db.session.delete(recording)
    db.session.commit()
    return jsonify(success=True)
