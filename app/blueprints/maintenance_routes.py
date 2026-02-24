from flask import Blueprint, jsonify, session as flask_session

from skatetrax.models.cyberconnect2 import create_session
from skatetrax.models.t_auth import uAuthTable
from skatetrax.models.ops.data_aggregates import uMaintenanceV4

maintenance_blueprint = Blueprint("maintenance_blueprint", __name__)


@maintenance_blueprint.route('/maintenance', methods=['GET'])
def maintenance_overview():
    user_id = flask_session.get('user_id')
    if not user_id:
        return jsonify({"message": "Unauthorized"}), 401

    with create_session() as db:
        user = db.query(uAuthTable).filter_by(id=user_id).first()
        if not user:
            return jsonify({"message": "Unauthorized"}), 401

    uSkaterUUID = flask_session['uSkaterUUID']
    maint = uMaintenanceV4(uSkaterUUID)

    return jsonify({
        "clock": maint.maint_clock(),
        "total_cost": maint.maint_cost(),
        "blades": maint.maint_data_all(),
    })
