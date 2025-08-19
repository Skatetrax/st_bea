import pandas as pd
from flask import Blueprint, jsonify
from skatetrax.models.cyberconnect2 import Session
from skatetrax.models.ops.data_tables import Skating_Locations

import importlib

# Create a blueprint instance
locations_blueprint = Blueprint("locations_blueprint", __name__)


@locations_blueprint.route("/rinks", methods=["GET"])
def rinks():
    rink_list = Skating_Locations.rinks()
    df_as_dict = rink_list.to_dict(orient="records")
    
    return jsonify(df_as_dict)