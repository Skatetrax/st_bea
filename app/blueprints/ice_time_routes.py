from flask import Blueprint, jsonify, session as flask_session
import pandas as pd

from skatetrax.models.cyberconnect2 import create_session
from skatetrax.models.t_auth import uAuthTable
from skatetrax.models.ops.data_tables import Sessions_Tables
from skatetrax.models.ops.data_aggregates import SkaterAggregates

# Create a blueprint instance
ice_time_blueprint = Blueprint("ice_time_blueprint", __name__)

@ice_time_blueprint.route('/ice_time', methods=['GET'])
def protected():
    user_id = flask_session.get('user_id')
    if not user_id:
        return jsonify({"message": "Unauthorized"}), 401

    with create_session() as db:
        user = db.query(uAuthTable).filter_by(id=user_id).first()
        if not user:
            return jsonify({"message": "Unauthorized"}), 401

    uSkaterUUID = flask_session['uSkaterUUID']

    fsc = SkaterAggregates(uSkaterUUID).monthly_times_json()
    total_time = SkaterAggregates(uSkaterUUID).skated('total')

    # set up sessions table for current month
    sessions = Sessions_Tables.ice_time(uSkaterUUID)
    session_table = pd.DataFrame(sessions)

    return jsonify({

        "total_time": total_time,
        "fsc_graph": fsc,
        "session_table": session_table.to_dict(orient="records")
    })
