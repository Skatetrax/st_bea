from flask import Blueprint, jsonify, session as flask_session
import pandas as pd
from flask_login import login_required, current_user

from skatetrax.models.ops.data_tables import Sessions_Tables
from skatetrax.models.ops.data_aggregates import SkaterAggregates

# Create a blueprint instance
ice_time_blueprint = Blueprint("ice_time_blueprint", __name__)


@ice_time_blueprint.route('/ice_time', methods=['GET'])
@login_required
def protected():
    uSkaterUUID = getattr(current_user, "uSkaterUUID", None) or flask_session.get("uSkaterUUID")

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
