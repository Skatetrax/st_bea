from flask import Blueprint, jsonify, session as flask_session
from skatetrax.models.cyberconnect2 import Session
from skatetrax.models.t_auth import uAuthTable
from skatetrax.models.t_skaterMeta import uSkaterRoles
from skatetrax.models.ops.data_aggregates import UserMeta


# Create a blueprint instance
skater_profile_blueprint = Blueprint("skater_profile_blueprint", __name__)


@skater_profile_blueprint.route('/skater_overview', methods=['GET'])
def skater_profile():
    user_id = flask_session.get('user_id')
    if not user_id:
        return jsonify({"message": "Unauthorized"}), 401

    with Session() as db:
        auth_user = db.query(uAuthTable).filter_by(id=user_id).first()
        if not auth_user:
            return jsonify({"message": "Unauthorized"}), 401
        auth_email = auth_user.aEmail
        auth_phone = auth_user.phone_number
        auth_username = auth_user.aLogin

    uSkaterUUID = flask_session['uSkaterUUID']

    meta = UserMeta(uSkaterUUID)
    user = meta.to_dict()
    profile = meta.skater_profile()

    user_general = {
        "user_first_name": user['uSkaterFname'],
        "user_middle_name": user['uSkaterMname'],
        "user_last_name": user['uSkaterLname'],
        "user_location_zip": user['uSkaterZip'],
        "user_location_city": user['uSkaterCity'],
        "user_location_state": user['uSkaterState'],
        "user_location_country": user['uSkaterCountry'],
    }
    user_contact = {
        "email": auth_email,
        "phone": auth_phone,
        "username": auth_username,
    }
    role_ids = user.get('uSkaterRoles') or []
    role_labels = []
    if role_ids:
        with Session() as db:
            roles = db.query(uSkaterRoles.label).filter(uSkaterRoles.id.in_(role_ids)).all()
            role_labels = [r.label for r in roles if r.label]

    user_meta = {
        'user_creation_date': user['date_created'],
        'user_timezone': user['uSkaterTZ'],
        'user_preferred_rink': user['uSkaterRinkPref'],
        'user_preferred_rink_id': str(profile.uSkaterRinkPref) if profile and profile.uSkaterRinkPref else None,
        'user_preferred_maint_hours': user['uSkaterMaintPref'],
        'user_primary_coach': user['activeCoach'],
        'user_primary_coach_id': str(profile.activeCoach) if profile and profile.activeCoach else None,
        'user_ice_config': user['uSkaterComboIce'],
        'user_roles': role_labels,
    }
    user_memberships = {
        'affiliated_club_name': user['org_Club'],
        'affiliated_club_date': user['org_Club_Join_Date'],
        'usfsa_number': user['org_USFSA_number'],
    }

    response = {
        'user_general': user_general,
        'user_contact': user_contact,
        'user_meta': user_meta,
        'user_memberships': user_memberships,
    }

    return jsonify(response)
