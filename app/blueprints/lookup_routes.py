from flask import Blueprint, jsonify, request, session as flask_session
import pandas as pd

from skatetrax.models.cyberconnect2 import create_session
from skatetrax.models.t_auth import uAuthTable
from skatetrax.models.ops.data_tables import CoachesTable, Sessions_Tables

# Create a blueprint instance
lookup_blueprint = Blueprint("lookup_blueprint", __name__)

@lookup_blueprint.route('/coaches', methods=['GET'])
def protected_coaches():
    user_id = flask_session.get('user_id')
    
    if not user_id:
        return jsonify({"message": "Unauthorized"}), 401

    with create_session() as db:
        user = db.query(uAuthTable).filter_by(id=user_id).first()
        if not user:
            return jsonify({"message": "Unauthorized"}), 401

    # Optional filter param
    coach_id = request.args.get("id")

    # Fetch all coaches
    coaches = pd.DataFrame(CoachesTable.list_coaches())

    # Apply filter if `id` param provided
    if coach_id is not None:
        coaches = coaches[coaches["coach_id"] == coach_id]

    return jsonify(coaches.to_dict(orient="records"))


@lookup_blueprint.route("/ice_types", methods=["GET"])
def ice_types():
    '''
    Leaving protected so that we can filter types based on
    role in the future.
    '''

    user_id = flask_session.get('user_id')
    
    if not user_id:
        return jsonify({"message": "Unauthorized"}), 401

    with create_session() as db:
        user = db.query(uAuthTable).filter_by(id=user_id).first()
        if not user:
            return jsonify({"message": "Unauthorized"}), 401
        
    type_list = pd.DataFrame(Sessions_Tables.ice_type())
    df_as_dict = type_list.to_dict(orient="records")

    return jsonify(df_as_dict)