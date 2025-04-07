from flask import Blueprint, request, jsonify
from datetime import datetime
from sqlalchemy.exc import SQLAlchemyError
from models.devices import Device, AppInfo
from config.database import db
from logzero import logger

apps_bp = Blueprint('apps', __name__)

@apps_bp.route('/apps-info', methods=['POST'])
def save_apps_info():
    try:
        data = request.get_json()
        device_id = data.get('deviceId')
        apps_data = data.get('apps', [])

        if not device_id or not apps_data:
            return jsonify({'error': 'Missing device ID or apps data'}), 400

        # Delete existing apps info for this device
        AppInfo.query.filter_by(device_id=device_id).delete()

        for app in apps_data:
            install_timestamp = app.get('install_time')
            last_used_timestamp = app.get('last_used_time')
            app_info = AppInfo(
                device_id=device_id,
                package_name=app.get('package_name'),
                app_name=app.get('app_name'),
                app_version=app.get('app_version'),
                install_time=datetime.fromtimestamp(install_timestamp / 1000.0) if install_timestamp else None,
                last_used_time=datetime.fromtimestamp(last_used_timestamp / 1000.0) if last_used_timestamp else None,
                is_system_app=app.get('is_system_app', False),
                is_enabled=app.get('is_enabled', True),
                total_time_in_foreground=app.get('total_time_in_foreground')
            )
            db.session.add(app_info)

        db.session.commit()
        return jsonify({'message': 'Apps info saved successfully'}), 200

    except SQLAlchemyError as e:
        # Log the error for debugging
        logger.error(f"SQLAlchemyErro in save_apps_info: {str(e)}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@apps_bp.route('/device/<device_id>/apps', methods=['GET'])
def get_device_apps(device_id):
    try:
        apps = AppInfo.query.filter_by(device_id=device_id)\
            .order_by(AppInfo.app_name).all()
        return jsonify([app.to_dict() for app in apps]), 200

    except SQLAlchemyError as e:
        return jsonify({'error': str(e)}), 500

@apps_bp.route('/device/<device_id>/apps/system', methods=['GET'])
def get_device_system_apps(device_id):
    try:
        apps = AppInfo.query.filter_by(device_id=device_id, is_system_app=True)\
            .order_by(AppInfo.app_name).all()
        return jsonify([app.to_dict() for app in apps]), 200

    except SQLAlchemyError as e:
        return jsonify({'error': str(e)}), 500

@apps_bp.route('/device/<device_id>/apps/user', methods=['GET'])
def get_device_user_apps(device_id):
    try:
        apps = AppInfo.query.filter_by(device_id=device_id, is_system_app=False)\
            .order_by(AppInfo.app_name).all()
        return jsonify([app.to_dict() for app in apps]), 200

    except SQLAlchemyError as e:
        return jsonify({'error': str(e)}), 500 