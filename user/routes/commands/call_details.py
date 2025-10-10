from flask import Blueprint, flash, get_flashed_messages, render_template, redirect, url_for, current_app
from ..auth import auth_required
from models.devices import Device, CallLog
from apis.devices import getFreshCallLogs
import requests
from utils.caching import cache

call_details_command = Blueprint('call_details_command', __name__)

@call_details_command.route('/device/<device_id>/commands/call-details')
@auth_required
def device_call_details(device_id):
    alert = get_flashed_messages()
    if len(alert) > 0:
        alert = alert[0]
    call_logs = CallLog.query.filter_by(device_id=device_id).order_by(CallLog.timestamp.desc()).all()
    return render_template("pages/commands/call_details.html", alert=alert, call_logs=call_logs)


@call_details_command.route('/get-fresh-calls/<device_id>', methods=['POST'])
@auth_required
def get_fresh_calls(device_id):
    device = Device.query.filter_by(device_id=device_id).first()
    if device is None:
        alert = {
            'type': 'warning',
            'message': 'Invalid Device ID, please try again!',
            'title': 'Device Not Found'
        }
        flash(alert)
        return redirect(url_for('call_details_command.device_call_details', device_id=device_id))

    res = getFreshCallLogs(device_id, device.device_ip)
    if res:
        alert = {
            'type': 'success',
            'message': 'Call logs updated successfully!',
            'title': 'Calls Updated'
        }
        flash(alert)
    else:
        alert = {
            'type': 'warning',
            'message': 'Failed to update call logs, please try again!',
            'title': 'Calls Update Failed'
        }
        flash(alert)
    return redirect(url_for('call_details_command.device_call_details', device_id=device_id))