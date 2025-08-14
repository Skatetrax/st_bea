from flask import Blueprint, jsonify
from skatetrax.models.cyberconnect2 import check_db_health
import importlib

# Create a blueprint instance
util_blueprint = Blueprint("util_blueprint", __name__)


@util_blueprint.route("/version", methods=["GET"])
def version():
    try:
        version = importlib.metadata.version("skatetrax_core")
    except importlib.metadata.PackageNotFoundError:
        version = None
    return jsonify({"package": "skatetrax_core", "version": version})


@util_blueprint.route("/health", methods=["GET"])
def health():
    db_ok = check_db_health()
    if db_ok:
        return jsonify(status="ok", details="DB connection healthy")
    else:
        return jsonify(status="error", details="DB connection failed"), 500
