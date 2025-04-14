from flask import Blueprint, flash, get_flashed_messages, render_template, redirect, url_for, current_app
from ..auth import auth_required
from models.devices import Contact
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