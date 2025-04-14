from flask import Blueprint, flash, get_flashed_messages, render_template, redirect, url_for, current_app
from ..auth import auth_required
from models.devices import Device, CallLog
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