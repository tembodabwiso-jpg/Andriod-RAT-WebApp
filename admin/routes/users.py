from flask import Blueprint, request, jsonify, get_flashed_messages, flash, render_template, redirect, url_for
from models.users import User
from admin.routes.auth import auth_required
from config.database import db
from werkzeug.security import generate_password_hash
import uuid

users = Blueprint('users', __name__)


@users.route('/users')
@auth_required
def index():
    alert = get_flashed_messages()
    no_users = False
    if len(alert) > 0:
        alert = alert[0]
    users = User.query.all()
    if len(users) == 0:
        no_users = True
    return render_template('pages/users.html', users=users, alert=alert, no_users=no_users)


@users.route('/users/add', methods=['POST'])
@auth_required
def add_user():
    name = request.form.get('fullname')
    email = request.form.get('email')
    password = request.form.get('password')

    if not name or not email or not password:
        alert = {
                'status': 'warning',
                'message': 'All fields are required, please fill all fields!',
                'title': 'Missing Fields!'
            }
        flash(alert)
        return redirect(url_for('users.index'))
    
    if User.query.filter_by(email=email).first():
        alert = {
            'status': 'warning',
            'message': 'User with this email already exists!, Please use another email.',
            'title': 'User Already Exists!'
        }
        flash(alert)
        return redirect(url_for('users.index'))
    
    if len(password) < 8:
        alert = {
            'status': 'warning',
            'message': 'Password must be at least 8 characters long!',
            'title': 'Invalid Password!'
        }
        flash(alert)
        return redirect(url_for('users.index'))
    
    user = User(id=str(uuid.uuid4()), fullname=name, email=email, password=generate_password_hash(password), is_active=1)
    db.session.add(user)
    db.session.commit()

    alert = {
        'status': 'success',
        'message': 'User added successfully!',
        'title': 'User Added!'
    }
    flash(alert)
    return redirect(url_for('users.index'))

@users.route('/users/delete', methods=['POST'])
@auth_required
def delete_user():
    user_id = request.form.get('user_id')

    if not user_id:
        alert = {
                'status': 'warning',
                'message': 'All fields are required, please fill all fields!',
                'title': 'Missing Fields!'
            }
        flash(alert)
        return redirect(url_for('users.index'))
    
    User.query.filter_by(id=user_id).delete()
    db.session.commit()

    alert = {
        'status': 'success',
        'message': 'User deleted successfully!',
        'title': 'User Deleted!'
    }
    flash(alert)
    return redirect(url_for('users.index'))