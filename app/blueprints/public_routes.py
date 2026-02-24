import math
import pandas as pd
from flask import Blueprint, jsonify, request
from skatetrax.models.cyberconnect2 import create_session
from skatetrax.models.ops.data_tables import Skating_Locations

# Create a blueprint instance
locations_blueprint = Blueprint("locations_blueprint", __name__)


def _scrub_nan(records):
    for row in records:
        for k, v in row.items():
            if isinstance(v, float) and math.isnan(v):
                row[k] = None
    return records


@locations_blueprint.route("/rinks", methods=["GET"])
def rinks():
    rink_list = Skating_Locations.rinks()
    df_as_dict = _scrub_nan(rink_list.to_dict(orient="records"))

    rink_id = request.args.get("id")
    state = request.args.get("state")

    filtered = df_as_dict  # start with all

    if rink_id:
        filtered = [r for r in filtered if str(r.get("rink_id")) == str(rink_id)]
    if state:
        filtered = [r for r in filtered if str(r.get("rink_state")).lower() == state.lower()]

    # Handle no matches for either param
    if (rink_id or state) and not filtered:
        return jsonify({"error": "No rinks found"}), 404

    # If ID query, return single item instead of list
    if rink_id and filtered:
        return jsonify(filtered[0])

    return jsonify(filtered)