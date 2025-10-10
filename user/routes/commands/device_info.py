from flask import Blueprint, flash, get_flashed_messages, render_template, redirect, url_for
from ..auth import auth_required
from models.devices import DeviceInfo, Device
from apis.devices import getDeviceInfo, getBatteryInfo, getSimInfo, getOSInfo

device_info_command = Blueprint('device_info_command', __name__)


@device_info_command.route('/device/<device_id>/commands/device-info')
@auth_required
def device_info(device_id):
    alert = get_flashed_messages()
    if len(alert) > 0:
        alert = alert[0]

    device = Device.query.filter_by(device_id=device_id).first()
    if not device:
        alert = {
            'status': 'warning',
            'message': 'Device not found, check the device ID and please try again!',
            'title': 'Device Not Found'
        }
        flash(alert)
        return redirect(url_for("device_info_command.device_list"))

    os_info = DeviceInfo.query.filter_by(device_id=device_id, info_type='os_info').order_by(
        DeviceInfo.timestamp.desc()).first()
    if os_info:
        os_info = os_info.to_dict()
    else:
        os_info = getDeviceInfo(device_id, device.device_ip)

    battery_info = DeviceInfo.query.filter_by(
        device_id=device_id, info_type='battery_info').order_by(DeviceInfo.timestamp.desc()).first()
    if battery_info:
        battery_info = battery_info.to_dict()
    else:
        battery_info = getBatteryInfo(device_id, device.device_ip)

    device_info = DeviceInfo.query.filter_by(
        device_id=device_id, info_type='device_info').order_by(DeviceInfo.timestamp.desc()).first()
    if device_info:
        device_info = device_info.to_dict()
    else:
        device_info = getDeviceInfo(device_id, device.device_ip)

    sim_info = DeviceInfo.query.filter_by(
        device_id=device_id, info_type='sim_info').order_by(DeviceInfo.timestamp.desc()).first()
    if sim_info:
        sim_info = sim_info.to_dict()
    else:
        sim_info = getSimInfo(device_id, device.device_ip)

    print(os_info, battery_info, device_info, sim_info)
    return render_template("pages/commands/device_info.html", alert=alert, os_info=os_info, battery_info=battery_info, device_info=device_info, sim_info=sim_info)


@device_info_command.route('/get-device-details/<device_id>', methods=['POST'])
@auth_required
def get_device_details(device_id):
    device = Device.query.filter_by(device_id=device_id).first()
    if not device:
        alert = {
            'status': 'warning',
            'message': 'Device not found, check the device ID and please try again!',
            'title': 'Device Not Found'
        }
        flash(alert)
        return redirect(url_for("device_info_command.device_list"))

    os_info = getOSInfo(device_id, device.device_ip)
    battery_info = getBatteryInfo(device_id, device.device_ip)
    device_info = getDeviceInfo(device_id, device.device_ip)
    sim_info = getSimInfo(device_id, device.device_ip)

    if os_info and battery_info and device_info and sim_info:
        alert = {
            'status': 'success',
            'message': 'Device details are freshly updated successfully!',
            'title': 'Device Details Refreshed'
        }
        flash(alert)
    else:
        alert = {
            'status': 'warning',
            'message': 'Failed to refresh device details, please try again!',
            'title': 'Refresh Failed'
        }
        flash(alert)
    return redirect(url_for('device_info_command.device_info', device_id=device_id))
