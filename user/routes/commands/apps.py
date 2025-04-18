from flask import Blueprint, flash, get_flashed_messages, render_template, redirect, url_for, current_app, jsonify, request
from ..auth import auth_required
from models.devices import AppInfo
from datetime import datetime

apps_command = Blueprint('apps_command', __name__)

def format_datetime(dt):
    if not dt:
        return "Never"
    return dt.strftime("%d %b %Y %I:%M %p")

def format_duration(minutes):
    if not minutes or minutes == '0':
        return "0 minutes"
    try:
        minutes = int(minutes)
        if minutes < 60:
            return f"{minutes} minutes"
        hours = minutes // 60
        remaining_minutes = minutes % 60
        if remaining_minutes == 0:
            return f"{hours} hours"
        return f"{hours}h {remaining_minutes}m"
    except:
        return "0 minutes"

@apps_command.route('/device/<device_id>/commands/apps')
@auth_required
def device_apps(device_id):
    alert = get_flashed_messages()
    if len(alert) > 0:
        alert = alert[0]
    
    app_data = AppInfo.query.filter_by(device_id=device_id).order_by(AppInfo.install_time.desc()).all()
    
    formatted_apps = []
    for app in app_data:
        formatted_apps.append({
            'id': app.id,
            'device_id': app.device_id,
            'package_name': app.package_name,
            'app_name': app.app_name if app.app_name != app.package_name else app.package_name.split('.')[-1].title(),
            'is_system_app': app.is_system_app,
            'install_time': format_datetime(app.install_time),
            'app_version': app.app_version,
            'is_enabled': app.is_enabled,
            'last_used_time': format_datetime(app.last_used_time),
            'total_time_in_foreground': format_duration(app.total_time_in_foreground)
        })
    
    return render_template(
        "pages/commands/apps.html",
        alert=alert,
        app_data=formatted_apps,
        total_apps=len(formatted_apps),
        system_apps=sum(1 for app in formatted_apps if app['is_system_app'] == 1),
        user_apps=sum(1 for app in formatted_apps if app['is_system_app'] == 0)
    )

@apps_command.route('/device/<device_id>/commands/apps/delete/<app_id>', methods=['POST'])
@auth_required
def delete_app(device_id, app_id):
    try:
        app = AppInfo.query.get(app_id)
        if app and app.device_id == device_id:
            # Add your app deletion logic here
            return jsonify({'success': True, 'message': 'Application deleted successfully'})
        return jsonify({'success': False, 'message': 'Application not found'}), 404
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500