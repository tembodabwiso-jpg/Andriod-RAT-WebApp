from flask import Blueprint, render_template, request, get_flashed_messages
from admin.routes.auth import auth_required

dashboard = Blueprint('dashboard', __name__)


@dashboard.route('/dashboard')
@auth_required
def index():
    alert = get_flashed_messages()
    if len(alert) > 0:
        alert = alert[0]
    return render_template('pages/dashboard.html', alert=alert)
