from flask import Blueprint, flash, get_flashed_messages, render_template, redirect, url_for, current_app
from ..auth import auth_required
from models.devices import DeviceLocation, Device
import requests
from utils.caching import cache

location_command = Blueprint('location_command', __name__)


def format_coordinates(lat, lon):
    lat_dir = 'N' if lat >= 0 else 'S'
    lon_dir = 'E' if lon >= 0 else 'W'

    formatted_lat = f"{abs(lat):.4f}°{lat_dir}"
    formatted_lon = f"{abs(lon):.4f}°{lon_dir}"

    return f"{formatted_lat}, {formatted_lon}"


@cache.memoize(1000)
def get_place(lat, lon):

    url = 'https://nominatim.openstreetmap.org/reverse'
    params = {
        'format': 'json',
        'lat': lat,
        'lon': lon,
        'zoom': 5,
        'addressdetails': 1
    }
    headers = {'User-Agent': 'GeoApp/1.0'}
    response = requests.get(url, params=params, headers=headers)
    if response.ok:
        data = response.json()
        return data.get('display_name')
    return "Unknown Location"


def get_location_precision(accuracy, provider):
    provider = provider.lower()
    if provider == 'gps':
        if accuracy <= 5:
            return "High Precision (GPS)"
        elif accuracy <= 15:
            return "Medium Precision (GPS)"
        else:
            return "Low Precision (GPS)"

    elif provider == 'network':
        if accuracy <= 20:
            return "High Precision (Network)"
        elif accuracy <= 100:
            return "Medium Precision (Network)"
        else:
            return "Low Precision (Network)"

    else:
        return "Unknown Provider or Precision"


@location_command.route('/device/<device_id>/commands/location')
@auth_required
def device_location(device_id):
    alert = get_flashed_messages()
    if len(alert) > 0:
        alert = alert[0]
    location_gps = DeviceLocation.query.filter_by(device_id=device_id, provider='gps').order_by(
        DeviceLocation.timestamp.desc()).first()
    location_network = DeviceLocation.query.filter_by(device_id=device_id, provider='network').order_by(
        DeviceLocation.timestamp.desc()).first()
    gps_place = get_place(location_gps.latitude, location_gps.longitude)
    network_place = get_place(
        location_network.latitude, location_network.longitude)
    return render_template("pages/commands/location.html", alert=alert, location_gps=location_gps, location_network=location_network, gps_place=gps_place, network_place=network_place, format_coordinates=format_coordinates, get_location_precision=get_location_precision)


@location_command.route('/get-fresh-location/<device_id>', methods=['POST'])
@auth_required
def get_fresh_location(device_id):
    device = Device.query.filter_by(device_id=device_id).first()
    if device is None:
        alert = {
            'type': 'warning',
            'message': 'Invalid Device ID, please try again!',
            'title': 'Device Not Found'
        }
        flash(alert)
        return redirect(url_for('commands.device_location', device_id=device_id))

    url = f'http://{device.device_ip}:8080/getFreshLocation'
    response = requests.get(url, timeout=50)
    if response.status_code == 200:
        data = response.json()
        alert = {
            'type': 'success',
            'message': 'Location details updated successfully!',
            'title': 'Location Updated'
        }
        flash(alert)
        return redirect(url_for('commands.device_location', device_id=device_id))
    else:
        alert = {
            'type': 'warning',
            'message': 'Failed to update location details, please try again!',
            'title': 'Location Update Failed'
        }
        flash(alert)
        return redirect(url_for('commands.device_location', device_id=device_id))
