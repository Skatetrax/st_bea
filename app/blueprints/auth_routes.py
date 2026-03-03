import os
from datetime import datetime, timezone

from flask import Blueprint, request, jsonify, session as flask_session
from flask_login import login_required, login_user, logout_user, current_user

from skatetrax.auth import service as auth_service
from skatetrax.models.cyberconnect2 import create_session
from skatetrax.models.t_skaterMeta import uSkaterConfig

auth_blueprint = Blueprint("auth_blueprint", __name__)


@auth_blueprint.route("/register", methods=["POST"])
def register():
    data = request.get_json() or {}

    invite_token = data.get("invite_token")
    if not invite_token:
        return jsonify({"message": "Registration is invite-only. A valid invite token is required."}), 403

    token_obj = auth_service.validate_invite_token(invite_token)
    if token_obj is None:
        return jsonify({"message": "Invalid or expired invite token."}), 403

    aLogin = data.get("aLogin")
    aEmail = data.get("aEmail")
    password = data.get("aPasswordHash")
    if not aLogin or not aEmail or not password:
        return jsonify({"message": "aLogin, aEmail, and aPasswordHash required"}), 400

    existing = (
        auth_service.find_user(identifier=aLogin)
        or auth_service.find_user(identifier=aEmail)
    )
    if existing:
        return jsonify({"message": "User already exists"}), 400

    ALLOWED_SELF_REGISTER_ROLES = {"adult", "coach", "guardian"}
    requested_roles = data.get("roles") or ["adult"]
    if not isinstance(requested_roles, list):
        return jsonify({"message": "roles must be an array of strings"}), 400
    requested_roles = [r.lower().strip() for r in requested_roles]
    if "minor" in requested_roles:
        return jsonify({"message": "Minors cannot self-register. A guardian must create a minor profile."}), 400
    invalid = set(requested_roles) - ALLOWED_SELF_REGISTER_ROLES
    if invalid:
        return jsonify({"message": f"Invalid role(s): {', '.join(sorted(invalid))}. Allowed: {', '.join(sorted(ALLOWED_SELF_REGISTER_ROLES))}"}), 400

    user = auth_service.create_user(
        aLogin=aLogin,
        aEmail=aEmail,
        password=password,
        phone_number=data.get("phone_number"),
    )

    for role_name in requested_roles:
        auth_service.add_role_to_user(user, role_name)

    auth_service.consume_invite_token(invite_token)

    return jsonify({"message": "User registered successfully"})


@auth_blueprint.route("/register/validate-token", methods=["GET"])
def validate_invite_token():
    """Frontend preflight: check if an invite token is valid before showing the form."""
    token_str = request.args.get("token")
    if not token_str:
        return jsonify({"valid": False, "message": "Registration is currently invite-only."}), 403

    token_obj = auth_service.validate_invite_token(token_str)
    if token_obj is None:
        return jsonify({"valid": False, "message": "This invite has expired or has already been used."}), 403

    return jsonify({"valid": True})


@auth_blueprint.route("/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    identifier = data.get("aLogin") or data.get("aEmail")
    password = data.get("aPasswordHash")
    if not identifier or not password:
        return jsonify({"message": "aLogin or aEmail and aPasswordHash required"}), 400

    user = auth_service.find_user(identifier=identifier)
    if not user or not user.check_password(password):
        return jsonify({"message": "Invalid credentials"}), 401

    login_user(user)
    flask_session["uSkaterUUID"] = str(user.uSkaterUUID) if user.uSkaterUUID else None
    return jsonify({"message": "Login successful"})


@auth_blueprint.route("/session", methods=["GET"])
def session_check():
    if not current_user.is_authenticated:
        return jsonify({"logged_in": False}), 401
    u_skater_uuid = getattr(current_user, "uSkaterUUID", None)
    if u_skater_uuid is not None:
        u_skater_uuid = str(u_skater_uuid)
    else:
        u_skater_uuid = flask_session.get("uSkaterUUID")

    onboarding_complete = False
    if u_skater_uuid:
        with create_session() as db:
            onboarding_complete = (
                db.query(uSkaterConfig).filter_by(uSkaterUUID=u_skater_uuid).first() is not None
            )

    return jsonify({
        "logged_in": True,
        "user_id": current_user.id,
        "uSkaterUUID": u_skater_uuid,
        "onboarding_complete": onboarding_complete,
    })


@auth_blueprint.route("/onboard", methods=["POST"])
@login_required
def onboard():
    u_skater_uuid = getattr(current_user, "uSkaterUUID", None)
    if not u_skater_uuid:
        return jsonify({"message": "No uSkaterUUID on auth record"}), 400

    with create_session() as db:
        existing = db.query(uSkaterConfig).filter_by(uSkaterUUID=str(u_skater_uuid)).first()
        if existing:
            return jsonify({"message": "Onboarding already complete"}), 409

    data = request.get_json() or {}

    first_name = data.get("first_name")
    last_name = data.get("last_name")
    if not first_name or not last_name:
        return jsonify({"message": "first_name and last_name are required"}), 400

    with create_session() as db:
        config = uSkaterConfig(
            date_created=datetime.now(timezone.utc),
            uSkaterUUID=str(u_skater_uuid),
            uSkaterFname=first_name,
            uSkaterMname=data.get("middle_name"),
            uSkaterLname=last_name,
            uSkaterZip=data.get("zip"),
            uSkaterCity=data.get("city"),
            uSkaterState=data.get("state"),
            uSkaterCountry=data.get("country"),
            uSkaterComboIce=data.get("skate_config"),
            uSkaterComboOff=None,
            uSkaterRinkPref=data.get("rink_id"),
            uSkaterMaintPref=data.get("maint_pref"),
            activeCoach=data.get("coach_id"),
            org_Club=data.get("club_id"),
            org_Club_Join_Date=None,
            org_USFSA_number=data.get("usfsa_number"),
            uSkaterTZ=data.get("timezone", "UTC"),
        )
        db.add(config)
        db.commit()

    return jsonify({"message": "Onboarding complete", "uSkaterUUID": str(u_skater_uuid)})


@auth_blueprint.route("/change-password", methods=["POST"])
@login_required
def change_password():
    data = request.get_json() or {}
    current_password = data.get("current_password")
    new_password = data.get("new_password")
    if not current_password or not new_password:
        return jsonify({"message": "current_password and new_password are required"}), 400

    if not current_user.check_password(current_password):
        return jsonify({"message": "Current password is incorrect"}), 401

    auth_service.update_password(current_user, new_password)
    return jsonify({"message": "Password updated successfully"})


@auth_blueprint.route("/reset-request", methods=["POST"])
def reset_request():
    """Send a password reset email. Always returns 200 to prevent email enumeration."""
    data = request.get_json() or {}
    email = data.get("email")
    if not email:
        return jsonify({"message": "email is required"}), 400

    from app import mail
    if mail is None:
        return jsonify({"message": "Password reset is not available (email service not configured)"}), 503

    user = auth_service.find_user(identifier=email)
    if user:
        token_obj = auth_service.create_reset_token(user.id)
        reset_base = os.environ.get("RESET_URL_BASE", "http://localhost:3000/reset")
        reset_url = f"{reset_base}?token={token_obj.token}"

        from flask_mail import Message
        msg = Message(
            subject="Skatetrax - Password Reset",
            recipients=[user.aEmail],
            body=f"Use this link to reset your password (expires in 1 hour):\n\n{reset_url}\n\nIf you did not request this, ignore this email.",
        )
        mail.send(msg)

    return jsonify({"message": "If that email is registered, a reset link has been sent."})


@auth_blueprint.route("/reset-confirm", methods=["POST"])
def reset_confirm():
    data = request.get_json() or {}
    token_str = data.get("token")
    new_password = data.get("new_password")
    if not token_str or not new_password:
        return jsonify({"message": "token and new_password are required"}), 400

    token_obj = auth_service.validate_reset_token(token_str)
    if token_obj is None:
        return jsonify({"message": "Invalid or expired reset token"}), 400

    user = auth_service.find_user(identifier=str(token_obj.user_id))
    if not user:
        return jsonify({"message": "User not found"}), 400

    auth_service.update_password(user, new_password)
    auth_service.consume_reset_token(token_str)
    return jsonify({"message": "Password has been reset."})


@auth_blueprint.route("/logout", methods=["POST"])
def logout():
    logout_user()
    flask_session.pop("user_id", None)
    flask_session.pop("uSkaterUUID", None)
    return jsonify({"message": "Logged out"})
