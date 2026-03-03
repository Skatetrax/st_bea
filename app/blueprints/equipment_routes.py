from flask import Blueprint, jsonify, session as flask_session
import pandas as pd
from flask_login import login_required, current_user

from skatetrax.models.ops.data_tables import Equipment
from skatetrax.models.ops.data_aggregates import Equipment as EquipmentAgg

equipment_blueprint = Blueprint("equipment_blueprint", __name__)


@equipment_blueprint.route('/equipment', methods=['GET'])
@login_required
def equipment_overview():
    uSkaterUUID = getattr(current_user, "uSkaterUUID", None) or flask_session.get("uSkaterUUID")

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
