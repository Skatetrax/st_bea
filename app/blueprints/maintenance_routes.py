from flask import Blueprint, jsonify, session as flask_session
from flask_login import login_required, current_user

from skatetrax.models.ops.data_aggregates import uMaintenanceV4

maintenance_blueprint = Blueprint("maintenance_blueprint", __name__)


@maintenance_blueprint.route('/maintenance', methods=['GET'])
@login_required
def maintenance_overview():
    uSkaterUUID = getattr(current_user, "uSkaterUUID", None) or flask_session.get("uSkaterUUID")
    maint = uMaintenanceV4(uSkaterUUID)

    return jsonify({
        "clock": maint.maint_clock(),
        "total_cost": maint.maint_cost(),
        "blades": maint.maint_data_all(),
    })
