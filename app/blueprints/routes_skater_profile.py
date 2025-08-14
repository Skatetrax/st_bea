from flask import Blueprint, jsonify, session as flask_session
from skatetrax.models.cyberconnect2 import Session
from skatetrax.models.t_auth import uAuthTable
from skatetrax.models.ops.data_aggregates import UserMeta

# Create a blueprint instance
skater_profile_blueprint = Blueprint("skater_profile_blueprint", __name__)

@skater_profile_blueprint.route('/protected', methods=['GET'])
def protected():
    user_id = flask_session.get('user_id')
    if not user_id:
        return jsonify({"message": "Unauthorized"}), 401

    with Session() as db:
        user = db.query(uAuthTable).filter_by(id=user_id).first()
        if not user:
            return jsonify({"message": "Unauthorized"}), 401

    profile_obj = UserMeta.skater_profile(uSkaterUUID=flask_session['uSkaterUUID'])

    # Convert SQLAlchemy object to a dict
    profile = {
        column.name: getattr(profile_obj, column.name)
        for column in profile_obj.__table__.columns
    } if profile_obj else None

    return jsonify({
        "message": f"Welcome {user.aLogin}!",
        "profile": profile
    })
