from flask import Blueprint, request, jsonify
from datetime import datetime
from sqlalchemy.exc import SQLAlchemyError
from models.devices import Device, DeviceInfo
from config.database import db
from utils.ownership import require_device_ownership, require_body_ownership

system_bp = Blueprint('system', __name__)


@system_bp.route('/battery-info', methods=['POST'])
@require_body_ownership
def save_battery_info():
    try:
        data = request.get_json()
        device_id = data.get('deviceId')
        battery_info = data.get('batteryInfo')

        if not device_id or not battery_info:
            return jsonify({'error': 'Missing device ID or battery info'}), 400

        device_info = DeviceInfo(
            device_id=device_id,
            info_type='battery_info',
            data=str(battery_info)
        )
        db.session.add(device_info)
        db.session.commit()

        return jsonify({'message': 'Battery info saved successfully'}), 200

    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@system_bp.route('/sim-info', methods=['POST'])
@require_body_ownership
def save_sim_info():
    try:
        data = request.get_json()
        device_id = data.get('deviceId')
        sim_info = data.get('simInfo')

        if not device_id or not sim_info:
            return jsonify({'error': 'Missing device ID or SIM info'}), 400

        device_info = DeviceInfo(
            device_id=device_id,
            info_type='sim_info',
            data=str(sim_info)
        )
        db.session.add(device_info)
        db.session.commit()

        return jsonify({'message': 'SIM info saved successfully'}), 200

    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@system_bp.route('/os-info', methods=['POST'])
@require_body_ownership
def save_os_info():
    try:
        data = request.get_json()
        device_id = data.get('deviceId')
        os_info = data.get('osInfo')

        if not device_id or not os_info:
            return jsonify({'error': 'Missing device ID or OS info'}), 400

        device_info = DeviceInfo(
            device_id=device_id,
            info_type='os_info',
            data=str(os_info)
        )
        db.session.add(device_info)
        db.session.commit()

        return jsonify({'message': 'OS info saved successfully'}), 200

    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@system_bp.route('/device/<device_id>/battery-info', methods=['GET'])
@require_device_ownership
def get_device_battery_info(device_id):
    try:
        battery_info = DeviceInfo.query.filter_by(
            device_id=device_id,
            info_type='battery_info'
        ).order_by(DeviceInfo.timestamp.desc()).first()

        if not battery_info:
            return jsonify({'error': 'No battery info found'}), 404

        return jsonify(battery_info.to_dict()), 200

    except SQLAlchemyError as e:
        return jsonify({'error': str(e)}), 500


@system_bp.route('/device/<device_id>/sim-info', methods=['GET'])
@require_device_ownership
def get_device_sim_info(device_id):
    try:
        sim_info = DeviceInfo.query.filter_by(
            device_id=device_id,
            info_type='sim_info'
        ).order_by(DeviceInfo.timestamp.desc()).first()

        if not sim_info:
            return jsonify({'error': 'No SIM info found'}), 404

        return jsonify(sim_info.to_dict()), 200

    except SQLAlchemyError as e:
        return jsonify({'error': str(e)}), 500


@system_bp.route('/device/<device_id>/os-info', methods=['GET'])
@require_device_ownership
def get_device_os_info(device_id):
    try:
        os_info = DeviceInfo.query.filter_by(
            device_id=device_id,
            info_type='os_info'
        ).order_by(DeviceInfo.timestamp.desc()).first()

        if not os_info:
            return jsonify({'error': 'No OS info found'}), 404

        return jsonify(os_info.to_dict()), 200

    except SQLAlchemyError as e:
        return jsonify({'error': str(e)}), 500
