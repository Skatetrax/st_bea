from flask import Blueprint, jsonify, session as flask_session
from flask_login import login_required, current_user
from skatetrax.models.ops.data_aggregates import UserMeta, SkaterAggregates


# Create a blueprint instance
skater_profile_blueprint = Blueprint("skater_profile_blueprint", __name__)


@skater_profile_blueprint.route('/skater_overview', methods=['GET'])
@login_required
def skater_profile():
    auth_email = getattr(current_user, "aEmail", None)
    auth_phone = getattr(current_user, "phone_number", None)
    auth_username = getattr(current_user, "aLogin", None)
    uSkaterUUID = getattr(current_user, "uSkaterUUID", None) or flask_session.get("uSkaterUUID")

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
    role_labels = [r.name for r in getattr(current_user, "roles", []) if r.name]

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
        'contact_preference': user.get('contact_preference'),
        'share_token': user.get('share_token'),
    }
    user_memberships = {
        'affiliated_club_name': user['org_Club'],
        'affiliated_club_date': user['org_Club_Join_Date'],
        'usfsa_number': user['org_USFSA_number'],
    }

    total_ice_time = SkaterAggregates(uSkaterUUID).skated('total')

    response = {
        'user_general': user_general,
        'user_contact': user_contact,
        'user_meta': user_meta,
        'user_memberships': user_memberships,
        'total_ice_time': total_ice_time,
    }

    return jsonify(response)
