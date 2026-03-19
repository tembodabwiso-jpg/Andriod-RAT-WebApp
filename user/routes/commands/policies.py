from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from ..auth import auth_required
from models.devices import Policy, DeviceGroup, Device
from config.database import db
import json

policies_command = Blueprint('policies_command', __name__)


@policies_command.route('/policies')
@auth_required
def policies_page():
    policies = Policy.query.all()
    groups = DeviceGroup.query.all()
    return render_template(
        'pages/commands/policies.html',
        policies=[p.to_dict() for p in policies],
        groups=[g.to_dict() for g in groups],
    )


@policies_command.route('/policies/create', methods=['POST'])
@auth_required
def create_policy():
    try:
        name = request.form.get('name')
        description = request.form.get('description', '')
        rules_str = request.form.get('rules', '{}')
        group_id = request.form.get('group_id')

        policy = Policy(
            name=name,
            description=description,
            rules_json=rules_str,
            group_id=int(group_id) if group_id else None,
        )
        db.session.add(policy)
        db.session.commit()
        flash({'status': 'success', 'message': 'Policy created successfully', 'title': 'Success'})
    except Exception as e:
        db.session.rollback()
        flash({'status': 'error', 'message': str(e), 'title': 'Error'})

    return redirect(url_for('policies_command.policies_page'))


@policies_command.route('/policies/<int:policy_id>/delete', methods=['POST'])
@auth_required
def delete_policy(policy_id):
    try:
        policy = Policy.query.get(policy_id)
        if policy:
            db.session.delete(policy)
            db.session.commit()
            flash({'status': 'success', 'message': 'Policy deleted', 'title': 'Success'})
    except Exception as e:
        db.session.rollback()
        flash({'status': 'error', 'message': str(e), 'title': 'Error'})

    return redirect(url_for('policies_command.policies_page'))


@policies_command.route('/groups/create', methods=['POST'])
@auth_required
def create_group():
    try:
        name = request.form.get('name')
        description = request.form.get('description', '')

        group = DeviceGroup(name=name, description=description)
        db.session.add(group)
        db.session.commit()
        flash({'status': 'success', 'message': 'Group created', 'title': 'Success'})
    except Exception as e:
        db.session.rollback()
        flash({'status': 'error', 'message': str(e), 'title': 'Error'})

    return redirect(url_for('policies_command.policies_page'))
