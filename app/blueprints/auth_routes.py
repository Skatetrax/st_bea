from flask import Flask, Blueprint, request, jsonify, session as flask_session
from skatetrax.models.cyberconnect2 import create_session, check_db_health
from skatetrax.models.t_auth import uAuthTable

# Create a blueprint instance
auth_blueprint = Blueprint("auth_blueprint", __name__)


@auth_blueprint.route('/register', methods=['POST'])
def register():
    data = request.json

    with create_session() as db:
        existing = db.query(uAuthTable).filter_by(aLogin=data['aLogin']).first()
        if existing:
            return jsonify({"message": "User already exists"}), 400

        user = uAuthTable(
            aLogin=data['aLogin'],
            aEmail=data['aEmail'],
            phone_number=data.get('phone_number')
        )
        user.set_password(data['aPasswordHash'])

        db.add(user)
        db.commit()

    return jsonify({"message": "User registered successfully"})


@auth_blueprint.route('/login', methods=['POST'])
def login():
    data = request.json
    with create_session() as db:
        user = db.query(uAuthTable).filter_by(aLogin=data['aLogin']).first()
        if not user or not user.check_password(data['aPasswordHash']):
            return jsonify({"message": "Invalid credentials"}), 401

    flask_session['user_id'] = user.id
    flask_session['uSkaterUUID'] = user.uSkaterUUID

    return jsonify({"message": "Login successful"})


@auth_blueprint.route('/session', methods=['GET'])
def session_check():
    user_id = flask_session.get('user_id')
    u_skater_uuid = flask_session.get('uSkaterUUID')

    if not user_id:
        return jsonify({"logged_in": False}), 401

    return jsonify({
        "logged_in": True,
        "user_id": user_id,
        "uSkaterUUID": u_skater_uuid
    })


@auth_blueprint.route('/logout', methods=['POST'])
def logout():
    flask_session.pop('user_id', None)
    return jsonify({"message": "Logged out"})