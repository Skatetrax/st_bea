from datetime import date
from uuid import UUID

from flask import Blueprint, jsonify, request, session as flask_session
from flask_login import login_required, current_user
from pydantic import BaseModel, ValidationError

from skatetrax.models.cyberconnect2 import create_session
from skatetrax.models.ops.data_aggregates import uMaintenanceV4
from skatetrax.models.ops.pencil import Equipment_Data
from skatetrax.models.t_skaterMeta import uSkaterConfig
from skatetrax.models.t_equip import uSkateConfig

maintenance_blueprint = Blueprint("maintenance_blueprint", __name__)


def _get_skater_uuid():
    return getattr(current_user, "uSkaterUUID", None) or flask_session.get("uSkaterUUID")


class AddMaintenancePayload(BaseModel):
    m_date: date
    m_location: UUID | None = None
    m_hours_on: int = 0
    m_cost: float = 0
    m_notes: str | None = None
    m_roh: str | None = None

    class Config:
        arbitrary_types_allowed = True


@maintenance_blueprint.route('/maintenance', methods=['GET'])
@login_required
def maintenance_overview():
    uuid = _get_skater_uuid()
    maint = uMaintenanceV4(uuid)

    return jsonify({
        "clock": maint.maint_clock(),
        "total_cost": maint.maint_cost(),
        "blades": maint.maint_data_all(),
    })


@maintenance_blueprint.route('/maintenance', methods=['POST'])
@login_required
def add_maintenance():
    """Add a blade sharpening record for the skater's active config."""
    uuid = _get_skater_uuid()
    if not uuid:
        return jsonify({"error": "Missing skater UUID"}), 400

    data = request.get_json()
    if not data:
        return jsonify({"error": "Missing JSON payload"}), 400

    try:
        payload = AddMaintenancePayload(**data)
    except ValidationError as ve:
        return jsonify({"error": "Invalid input", "details": ve.errors()}), 400

    with create_session() as sess:
        profile = (
            sess.query(uSkaterConfig)
            .filter(uSkaterConfig.uSkaterUUID == uuid)
            .first()
        )
        if not profile or not profile.uSkaterComboIce:
            return jsonify({"error": "No active skate config found"}), 400

        combo = (
            sess.query(uSkateConfig)
            .filter(uSkateConfig.sConfigID == profile.uSkaterComboIce)
            .first()
        )
        if not combo:
            return jsonify({"error": "Active skate config not found"}), 400

    record = {
        "m_date": payload.m_date,
        "m_hours_on": payload.m_hours_on,
        "m_cost": payload.m_cost,
        "m_location": str(payload.m_location) if payload.m_location else None,
        "m_notes": payload.m_notes,
        "m_roh": payload.m_roh,
        "m_pref_hours": profile.uSkaterMaintPref,
        "uSkaterBladesID": str(combo.uSkaterBladesID),
        "uSkateConfig": str(combo.sConfigID),
        "uSkaterUUID": str(uuid),
    }

    try:
        Equipment_Data.add_maintenance([record])
    except Exception as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({"status": "ok"}), 201
