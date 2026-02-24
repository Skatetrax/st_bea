from flask import Blueprint, request, jsonify, session as flask_session
from skatetrax.models.cyberconnect2 import create_session
from skatetrax.models.ops.data_aggregates import UserMeta
from skatetrax.models.ops.pencil import AddSession

import datetime
from uuid import UUID
from pydantic import BaseModel, ValidationError, Field

# -------------------------------
# Reusable Pydantic model
# -------------------------------
class IceTimePayload(BaseModel):
    date: datetime.date = Field(..., description="Date of the session")
    ice_time: int = Field(..., description="Length of ice time in minutes")
    ice_cost: float = Field(..., description="Cost of the ice time")
    coach_time: int = Field(..., description="Length of coach time in minutes")
    skate_type: UUID = Field(..., description="UUID for ice type")
    rink_id: UUID = Field(..., description="UUID for rink")
    coach_id: UUID = Field(..., description="UUID for coach")
    coach_cost: float = Field(..., description="Rate paid to coach")
    uSkaterUUID: UUID = Field(..., description="UUID of the skater")
    uSkaterConfig: UUID = Field(..., description="UUID of the skater config")
    has_video: int = Field(default=0)
    has_notes: int = Field(default=0)
    uSkaterType: int = Field(default=1)

    class Config:
        arbitrary_types_allowed = True


# -------------------------------
# Flask blueprint
# -------------------------------
sessions_blueprint = Blueprint("sessions_blueprint", __name__)

@sessions_blueprint.route('add_icetime', methods=['POST'])
def add_icetime():
    # --- session auth check ---
    user_id = flask_session.get('user_id')
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    # --- grab logged-in user's skater UUID ---
    uSkaterUUID = flask_session.get('uSkaterUUID')
    if not uSkaterUUID:
        return jsonify({"error": "Missing skater UUID"}), 400

    # --- grab payload ---
    data = request.get_json()
    if not data:
        return jsonify({"error": "Missing JSON payload"}), 400

    # --- inject user UUID and active config into the payload ---
    data['uSkaterUUID'] = uSkaterUUID

    meta = UserMeta(uSkaterUUID)
    profile = meta.skater_profile()
    if not profile or not profile.uSkaterComboIce:
        return jsonify({"error": "No active skate config found"}), 400
    data['uSkaterConfig'] = str(profile.uSkaterComboIce)

    # --- validate & normalize payload ---
    try:
        validated = IceTimePayload(**data)
        print("[VALIDATION] Payload successfully validated.")
    except ValidationError as ve:
        print("[VALIDATION ERROR] One or more fields failed:")
        for err in ve.errors():
            print(f"  Field '{err['loc'][0]}': {err['msg']}")
        return jsonify({"error": "Invalid input", "details": ve.errors()}), 400

    # --- log type conversions ---
    for key, value in validated.dict().items():
        if str(data.get(key)) != str(value):
            print(f"[TYPE COERCION] Field '{key}' was converted from {data.get(key)} ({type(data.get(key))}) "
                  f"to {value} ({type(value)})")

    # --- insert into DB ---
    try:
        with create_session() as db_session:
            new_row = AddSession(db_session)(validated.dict())
    except Exception as e:
        print(f"[DB ERROR] {e}")
        return jsonify({"error": str(e)}), 400

    return jsonify({
        "ice_time_id": new_row.ice_time_id,
        "timestamp": new_row.date.isoformat()
    }), 201