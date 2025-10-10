from flask import Blueprint, flash, get_flashed_messages, render_template, redirect, url_for, current_app
from ..auth import auth_required
from models.devices import Contact, Device
from apis.devices import getFreshContacts
import requests
from utils.caching import cache
from datetime import datetime, timedelta

contacts_command = Blueprint('contacts_command', __name__)

@contacts_command.route('/device/<device_id>/commands/contacts')
@auth_required
def device_contacts(device_id):
    alert = get_flashed_messages()
    if len(alert) > 0:
        alert = alert[0]
    contacts = Contact.query.filter_by(device_id=device_id).order_by(Contact.last_updated.desc()).all()
    return render_template("pages/commands/contacts.html", alert=alert, contacts=contacts, now=datetime.now(), timedelta=timedelta)


@contacts_command.route('/get-fresh-contacts/<device_id>', methods=['POST'])
@auth_required
def get_fresh_contacts(device_id):
    device = Device.query.filter_by(device_id=device_id).first()
    if device is None:
        alert = {
            'type': 'warning',
            'message': 'Invalid Device ID, please try again!',
            'title': 'Device Not Found'
        }
        flash(alert)
        return redirect(url_for('contacts_command.device_contacts', device_id=device_id))

    res = getFreshContacts(device_id, device.device_ip)
    if res:
        alert = {
            'type': 'success',
            'message': 'Contacts updated successfully!',
            'title': 'Contacts Updated'
        }
        flash(alert)
    else:
        alert = {
            'type': 'warning',
            'message': 'Failed to update contacts, please try again!',
            'title': 'Contacts Update Failed'
        }
        flash(alert)
    return redirect(url_for('contacts_command.device_contacts', device_id=device_id))