from flask import Blueprint, render_template, request, redirect, url_for, get_flashed_messages, flash, session
from models.admins import Admin
from config.database import db
from werkzeug.security import check_password_hash, generate_password_hash
from functools import wraps

auth = Blueprint('auth', __name__, url_prefix='/auth')


@auth.route('/login', methods=['GET', 'POST'])
def login():
    if 'admin_id' in session:
        return redirect(url_for('dashboard.index'))
    
    alert = get_flashed_messages()
    if len(alert) > 0:
        alert = alert[0]
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        if not email or not password:
            alert = {
                'status': 'warning',
                'message': 'All fields are required, please fill all fields!',
                'title': 'Missing Fields!'
            }
            flash(alert)
            return redirect(url_for('auth.login'))

        user = Admin.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):
            session['admin_id'] = user.id
            session['admin_email'] = user.email
            session['admin_name'] = user.fullname

            alert = {
                'status': 'success',
                'message': 'You have successfully logged in!',
                'title': 'Login Successful!'
            }
            flash(alert)
            return redirect(url_for('dashboard.index'))
        else:
            alert = {
                'status': 'warning',
                'message': 'Invalid email or password, please try again!',
                'title': 'Login Failed!'
            }
            flash(alert)
            return redirect(url_for('auth.login'))

    return render_template('auth/login.html', alert=alert)



def auth_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if (
            "admin_email" not in session
            or "admin_id" not in session
            or "admin_name" not in session
            or session["admin_email"] == None
            or session["admin_id"] == None
            or session["admin_name"] == None
        ):
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)

    return decorated_function



@auth.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))