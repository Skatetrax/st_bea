from flask import Blueprint, request, jsonify, session as flask_session
from skatetrax.models.cyberconnect2 import Session as DBSession
from skatetrax.models.ops.pencil import AddSession


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

    # --- inject user UUID into the payload ---
    data['uSkaterUUID'] = uSkaterUUID

    try:
        with DBSession() as db_session:
            new_row = AddSession(db_session)(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({
        "ice_time_id": new_row.ice_time_id,
        "timestamp": new_row.date.isoformat()
    }), 201