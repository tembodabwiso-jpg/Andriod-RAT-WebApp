from flask import Blueprint, flash, get_flashed_messages, render_template, redirect, url_for, current_app
from ..auth import auth_required
from models.devices import SMSMessage
import requests
from utils.caching import cache
from datetime import datetime, timedelta

messages_command = Blueprint('messages_command', __name__)

def format_message_time(timestamp):
    now = datetime.now()
    today = now.date()
    
    if timestamp.date() == today:
        diff_seconds = (now - timestamp).total_seconds()
        if diff_seconds < 3600:  # Less than 1 hour
            return f"{int(diff_seconds / 60)} min"
        return timestamp.strftime("%I:%M%p").lower()
    elif timestamp.date() > (today - timedelta(days=7)):
        return timestamp.strftime("%a")  # Weekday name
    else:
        return timestamp.strftime("%d %b")  # Day and Month

def format_datetime(value):
    # 15 Jan 2021 07:00 PM
    return value.strftime('%d %b %Y %I:%M %p')

@messages_command.route('/device/<device_id>/commands/messages')
@auth_required
def device_messages(device_id):
    alert = get_flashed_messages()
    if len(alert) > 0:
        alert = alert[0]
    
    messages = SMSMessage.query.filter_by(device_id=device_id).order_by(SMSMessage.timestamp.desc()).all()
    
    # Prepare messages data with formatted timestamps
    messages_data = []
    for msg in messages:
        messages_data.append({
            "id": msg.id,
            "device_id": msg.device_id,
            "phone_number": msg.phone_number,
            "contact_name": msg.contact_name,
            "message_type": msg.message_type,
            "message_body": msg.message_body.replace('\n', ' ').replace('\r', ' ') if msg.message_body else '',
            "timestamp": format_datetime(msg.timestamp) if msg.timestamp else '',
            "created_at": format_datetime(msg.created_at) if msg.created_at else '',
            "formatted_time": format_message_time(msg.timestamp) if msg.timestamp else ''
        })
    
    return render_template(
        "pages/commands/messages.html",
        alert=alert,
        messages=messages,
        messages_json=messages_data,
        format_message_time=format_message_time
    )

@messages_command.route('/get-messages/<device_id>', methods=['POST'])
@auth_required
def get_messages(device_id):
    pass