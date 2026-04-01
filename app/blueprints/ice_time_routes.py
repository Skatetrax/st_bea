from flask import Blueprint, jsonify, request, session as flask_session
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

    months_back = min(max(int(request.args.get("months_back", 0)), 0), 120)
    window = min(max(int(request.args.get("window", 12)), 1), 36)

    agg = SkaterAggregates(uSkaterUUID)
    fsc = agg.monthly_times_json(months_back=months_back, window=window)
    total_time = agg.skated('total')

    sessions = Sessions_Tables.ice_time(uSkaterUUID)
    session_table = pd.DataFrame(sessions)

    return jsonify({
        "total_time": total_time,
        "fsc_graph": fsc,
        "session_table": session_table.to_dict(orient="records"),
    })
