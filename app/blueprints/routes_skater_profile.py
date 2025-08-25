from flask import Blueprint, jsonify, session as flask_session
from skatetrax.models.cyberconnect2 import Session
from skatetrax.models.t_auth import uAuthTable
from skatetrax.models.ops.data_aggregates import UserMeta


# Create a blueprint instance
skater_profile_blueprint = Blueprint("skater_profile_blueprint", __name__)


@skater_profile_blueprint.route('/skater_overview', methods=['GET'])
def skater_profile():
    user_id = flask_session.get('user_id')
    if not user_id:
        return jsonify({"message": "Unauthorized"}), 401

    with Session() as db:
        user = db.query(uAuthTable).filter_by(id=user_id).first()
        if not user:
            return jsonify({"message": "Unauthorized"}), 401

    uSkaterUUID=flask_session['uSkaterUUID']
    
    user = UserMeta(uSkaterUUID).to_dict()

    user_general = { 
                    "user_first_name": user['uSkaterFname'],
                    "user_middle_name": user['uSkaterMname'],
                    "user_last_name": user['uSkaterLname'],
                    "user_location_zip": user['uSkaterZip'],
                    "user_location_city": user['uSkaterCity'],
                    "user_location_state": user['uSkaterState'],
                    "user_location_country":user['uSkaterCountry']
                    }
    user_meta = {
        'user_creation_date': user['date_created'],
        'user_preferred_rink': user['uSkaterRinkPref'],
        'user_preferred_maint_hours': user['uSkaterMaintPref'],
        'user_primary_coach': user['activeCoach'],    
        'user_ice_config': user['uSkaterComboOff']
    }
    user_memberships = {
        'affiliated_club_name': user['org_Club_Name'],
        'affiliated_club_date': user['org_Club_Join_Date'],
        'usfsa_number': user['org_USFSA_number']
    }
    
    response = { 
        'user_general': user_general,
        'user_meta': user_meta,
        'user_memberships': user_memberships
    }
    
    return jsonify(response)
