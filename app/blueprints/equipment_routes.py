from flask import Blueprint, jsonify, session as flask_session
import pandas as pd

from skatetrax.models.cyberconnect2 import create_session
from skatetrax.models.t_auth import uAuthTable
from skatetrax.models.ops.data_tables import Equipment
from skatetrax.models.ops.data_aggregates import Equipment as EquipmentAgg

equipment_blueprint = Blueprint("equipment_blueprint", __name__)


@equipment_blueprint.route('/equipment', methods=['GET'])
def equipment_overview():
    user_id = flask_session.get('user_id')
    if not user_id:
        return jsonify({"message": "Unauthorized"}), 401

    with create_session() as db:
        user = db.query(uAuthTable).filter_by(id=user_id).first()
        if not user:
            return jsonify({"message": "Unauthorized"}), 401

    uSkaterUUID = flask_session['uSkaterUUID']

    active = EquipmentAgg.config_active(uSkaterUUID)

    configs_df = Equipment.skate_configs(uSkaterUUID)
    boots_df = Equipment.boots(uSkaterUUID)
    blades_df = Equipment.blades(uSkaterUUID)

    return jsonify({
        "active_config": active,
        "configs": configs_df.to_dict(orient="records") if not configs_df.empty else [],
        "boots": boots_df.to_dict(orient="records") if not boots_df.empty else [],
        "blades": blades_df.to_dict(orient="records") if not blades_df.empty else [],
    })
