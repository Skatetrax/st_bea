from flask import Blueprint, jsonify, request
import pandas as pd
from flask_login import login_required

from skatetrax.models.ops.data_tables import CoachesTable, Sessions_Tables

# Create a blueprint instance
lookup_blueprint = Blueprint("lookup_blueprint", __name__)


@lookup_blueprint.route('/coaches', methods=['GET'])
@login_required
def protected_coaches():
    # Optional filter param
    coach_id = request.args.get("id")

    # Fetch all coaches
    coaches = pd.DataFrame(CoachesTable.list_coaches())

    # Apply filter if `id` param provided
    if coach_id is not None:
        coaches = coaches[coaches["coach_id"] == coach_id]

    return jsonify(coaches.to_dict(orient="records"))


@lookup_blueprint.route("/ice_types", methods=["GET"])
@login_required
def ice_types():
    '''
    Leaving protected so that we can filter types based on
    role in the future.
    '''
    type_list = pd.DataFrame(Sessions_Tables.ice_type())
    df_as_dict = type_list.to_dict(orient="records")

    return jsonify(df_as_dict)