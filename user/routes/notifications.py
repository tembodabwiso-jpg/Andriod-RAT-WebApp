from flask import Blueprint, jsonify, session
from .auth import auth_required
from models.devices import DeviceNotification, Device
from config.database import db

notifications_bp = Blueprint('notifications', __name__)


@notifications_bp.route('/api/notifications', methods=['GET'])
@auth_required
def get_notifications():
    user_id = session.get('user_id')
    # Get owned device IDs
    device_ids = [d.device_id for d in Device.query.filter(
        (Device.user_id == user_id) | (Device.user_id == None)
    ).all()]

    notifs = DeviceNotification.query.filter(
        DeviceNotification.device_id.in_(device_ids)
    ).order_by(DeviceNotification.created_at.desc()).limit(20).all()

    unread_count = DeviceNotification.query.filter(
        DeviceNotification.device_id.in_(device_ids),
        DeviceNotification.is_read == False
    ).count()

    return jsonify(
        success=True,
        notifications=[n.to_dict() for n in notifs],
        unread_count=unread_count
    )


@notifications_bp.route('/api/notifications/<int:notif_id>/read', methods=['POST'])
@auth_required
def mark_read(notif_id):
    notif = DeviceNotification.query.get(notif_id)
    if notif:
        notif.is_read = True
        db.session.commit()
    return jsonify(success=True)


@notifications_bp.route('/api/notifications/read-all', methods=['POST'])
@auth_required
def mark_all_read():
    user_id = session.get('user_id')
    device_ids = [d.device_id for d in Device.query.filter(
        (Device.user_id == user_id) | (Device.user_id == None)
    ).all()]
    DeviceNotification.query.filter(
        DeviceNotification.device_id.in_(device_ids),
        DeviceNotification.is_read == False
    ).update({'is_read': True}, synchronize_session=False)
    db.session.commit()
    return jsonify(success=True)
