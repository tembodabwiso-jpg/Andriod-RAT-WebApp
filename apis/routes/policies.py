"""
Policy and Device Group API routes.
"""

from flask import Blueprint, request, jsonify
from sqlalchemy.exc import SQLAlchemyError
from models.devices import Policy, DeviceGroup, Device
from config.database import db
from utils.audit import log_action
from utils.jwt_auth import require_auth, require_admin
from logzero import logger
import json

policies_bp = Blueprint('policies', __name__)


# ── Device Groups ─────────────────────────────────────────────────────────────

@policies_bp.route('/groups', methods=['GET'])
@require_auth
def get_groups():
    try:
        groups = DeviceGroup.query.all()
        return jsonify([g.to_dict() for g in groups]), 200
    except SQLAlchemyError as e:
        return jsonify({'error': str(e)}), 500


@policies_bp.route('/groups', methods=['POST'])
@require_admin
def create_group():
    try:
        data = request.get_json()
        name = data.get('name')
        if not name:
            return jsonify({'error': 'Missing group name'}), 400

        group = DeviceGroup(
            name=name,
            description=data.get('description', ''),
        )
        db.session.add(group)
        db.session.commit()

        log_action('create_group', 'device_group', group.id, {'name': name})
        return jsonify(group.to_dict()), 201

    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@policies_bp.route('/groups/<int:group_id>', methods=['PUT'])
@require_admin
def update_group(group_id):
    try:
        data = request.get_json()
        group = DeviceGroup.query.get(group_id)
        if not group:
            return jsonify({'error': 'Group not found'}), 404

        if 'name' in data:
            group.name = data['name']
        if 'description' in data:
            group.description = data['description']

        db.session.commit()
        return jsonify(group.to_dict()), 200

    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@policies_bp.route('/groups/<int:group_id>', methods=['DELETE'])
@require_admin
def delete_group(group_id):
    try:
        group = DeviceGroup.query.get(group_id)
        if not group:
            return jsonify({'error': 'Group not found'}), 404

        db.session.delete(group)
        db.session.commit()
        log_action('delete_group', 'device_group', group_id)
        return jsonify({'message': 'Group deleted'}), 200

    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@policies_bp.route('/groups/<int:group_id>/devices', methods=['POST'])
@require_admin
def add_device_to_group(group_id):
    try:
        data = request.get_json()
        device_id = data.get('device_id')
        device = Device.query.get(device_id)
        if not device:
            return jsonify({'error': 'Device not found'}), 404

        device.group_id = group_id
        db.session.commit()
        return jsonify({'message': 'Device added to group'}), 200

    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


# ── Policies ──────────────────────────────────────────────────────────────────

@policies_bp.route('/policies', methods=['GET'])
@require_auth
def get_policies():
    try:
        policies = Policy.query.all()
        return jsonify([p.to_dict() for p in policies]), 200
    except SQLAlchemyError as e:
        return jsonify({'error': str(e)}), 500


@policies_bp.route('/policies', methods=['POST'])
@require_admin
def create_policy():
    try:
        data = request.get_json()
        name = data.get('name')
        if not name:
            return jsonify({'error': 'Missing policy name'}), 400

        policy = Policy(
            name=name,
            description=data.get('description', ''),
            rules_json=json.dumps(data.get('rules', {})),
            group_id=data.get('group_id'),
            is_active=data.get('is_active', True),
        )
        db.session.add(policy)
        db.session.commit()

        log_action('create_policy', 'policy', policy.id, {'name': name})
        return jsonify(policy.to_dict()), 201

    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@policies_bp.route('/policies/<int:policy_id>', methods=['GET'])
@require_auth
def get_policy(policy_id):
    try:
        policy = Policy.query.get(policy_id)
        if not policy:
            return jsonify({'error': 'Policy not found'}), 404
        return jsonify(policy.to_dict()), 200
    except SQLAlchemyError as e:
        return jsonify({'error': str(e)}), 500


@policies_bp.route('/policies/<int:policy_id>', methods=['PUT'])
@require_admin
def update_policy(policy_id):
    try:
        data = request.get_json()
        policy = Policy.query.get(policy_id)
        if not policy:
            return jsonify({'error': 'Policy not found'}), 404

        if 'name' in data:
            policy.name = data['name']
        if 'description' in data:
            policy.description = data['description']
        if 'rules' in data:
            policy.rules_json = json.dumps(data['rules'])
        if 'group_id' in data:
            policy.group_id = data['group_id']
        if 'is_active' in data:
            policy.is_active = data['is_active']

        db.session.commit()
        log_action('update_policy', 'policy', policy_id)
        return jsonify(policy.to_dict()), 200

    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@policies_bp.route('/policies/<int:policy_id>', methods=['DELETE'])
@require_admin
def delete_policy(policy_id):
    try:
        policy = Policy.query.get(policy_id)
        if not policy:
            return jsonify({'error': 'Policy not found'}), 404

        db.session.delete(policy)
        db.session.commit()
        log_action('delete_policy', 'policy', policy_id)
        return jsonify({'message': 'Policy deleted'}), 200

    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


# ── Audit Logs ────────────────────────────────────────────────────────────────

@policies_bp.route('/audit-logs', methods=['GET'])
@require_admin
def get_audit_logs():
    from models.devices import AuditLog
    try:
        limit = request.args.get('limit', 100, type=int)
        logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(limit).all()
        return jsonify([l.to_dict() for l in logs]), 200
    except SQLAlchemyError as e:
        return jsonify({'error': str(e)}), 500
