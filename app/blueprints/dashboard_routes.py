from flask import Blueprint, jsonify, session as flask_session
from skatetrax.models.cyberconnect2 import Session
from skatetrax.models.t_auth import uAuthTable
from skatetrax.models.ops.data_aggregates import SkaterAggregates

# Create a blueprint instance
dashboard_blueprint = Blueprint("dashboard_blueprint", __name__)

@dashboard_blueprint.route('/dashboard', methods=['GET'])
def protected():
    user_id = flask_session.get('user_id')
    if not user_id:
        return jsonify({"message": "Unauthorized"}), 401

    with Session() as db:
        user = db.query(uAuthTable).filter_by(id=user_id).first()
        if not user:
            return jsonify({"message": "Unauthorized"}), 401

    #total_time = Sessions_Time.skated_total(uSkaterUUID=flask_session['uSkaterUUID'])
    total_time = SkaterAggregates(uSkaterUUID=flask_session['uSkaterUUID']).skated('total')

    return jsonify({
        # "message": f"Welcome {user.aLogin}!",
        "total_time": total_time,
    })
