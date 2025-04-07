from flask import Blueprint, render_template, request, get_flashed_messages
from routes.auth import auth_required

profile = Blueprint('profile', __name__)

@profile.route('/profile')
@auth_required
def index():
    alert = get_flashed_messages()
    if len(alert) > 0:
        alert = alert[0]
    return render_template('pages/profile.html', alert=alert)
