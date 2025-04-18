from flask import Blueprint, flash, get_flashed_messages, render_template, redirect, url_for, current_app
from ..auth import auth_required
from models.devices import DeviceInfo
import requests
from utils.caching import cache

device_info_command = Blueprint('device_info_command', __name__)


@device_info_command.route('/device/<device_id>/commands/device-info')
@auth_required
def device_info(device_id):
    alert = get_flashed_messages()
    if len(alert) > 0:
        alert = alert[0]
    os_info = DeviceInfo.query.filter_by(device_id=device_id, info_type='os_info').order_by(DeviceInfo.timestamp.desc()).first().to_dict()
    battery_info = DeviceInfo.query.filter_by(device_id=device_id, info_type='battery_info').order_by(DeviceInfo.timestamp.desc()).first().to_dict()
    device_info = DeviceInfo.query.filter_by(device_id=device_id, info_type='device_info').order_by(DeviceInfo.timestamp.desc()).first().to_dict()
    sim_info = DeviceInfo.query.filter_by(device_id=device_id, info_type='sim_info').order_by(DeviceInfo.timestamp.desc()).first().to_dict()
    print(os_info, battery_info, device_info, sim_info)
    return render_template("pages/commands/device_info.html", alert=alert, os_info=os_info, battery_info=battery_info, device_info=device_info, sim_info=sim_info)

@device_info_command.route('/get-device-details/<device_id>', methods=['POST'])
@auth_required
def get_device_details(device_id):
    pass