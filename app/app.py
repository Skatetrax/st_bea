import os
import warnings

from flask_cors import CORS
from flask import Flask
from flask_security import Security

from user_datastore import skatetrax_user_datastore

# Load blueprints
from blueprints.auth_routes import auth_blueprint
from blueprints.util_routes import util_blueprint
from blueprints.routes_skater_profile import skater_profile_blueprint
from blueprints.dashboard_routes import dashboard_blueprint
from blueprints.ice_time_routes import ice_time_blueprint
from blueprints.public_routes import locations_blueprint
from blueprints.submit_routes import sessions_blueprint
from blueprints.lookup_routes import lookup_blueprint
from blueprints.maintenance_routes import maintenance_blueprint
from blueprints.equipment_routes import equipment_blueprint

app = Flask(__name__)

cors_origin_env = os.environ.get("CORS_ORIGIN")
if cors_origin_env:
    cors_origin = [o.strip() for o in cors_origin_env.split(",")]
else:
    cors_origin = r"http://(localhost|127\.0\.0\.1|192\.168\.\d+\.\d+):3000"

CORS(
    app,
    supports_credentials=True,
    resources={r"/api/*": {"origins": cors_origin}}
)

app.config['SESSION_COOKIE_NAME'] = 'session'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = os.environ.get("SESSION_COOKIE_SECURE", "false").lower() == "true"

cookie_domain = os.environ.get("SESSION_COOKIE_DOMAIN")
if cookie_domain:
    app.config['SESSION_COOKIE_DOMAIN'] = cookie_domain

app.secret_key = os.environ.get("FLASK_SECRET_KEY")
if not app.secret_key:
    if os.environ.get("FLASK_ENV") == "production":
        raise RuntimeError("FLASK_SECRET_KEY must be set in production")
    warnings.warn("FLASK_SECRET_KEY not set -- using ephemeral key; sessions will not persist across restarts")
    app.secret_key = os.urandom(32).hex()

# Flask-Security-Too (Phase 1: auth only; no FST blueprint, we use our own auth routes)
app.config.setdefault("SECURITY_PASSWORD_SALT", os.environ.get("SECURITY_PASSWORD_SALT", "skatetrax-salt"))
app.config.setdefault("SECURITY_REGISTERABLE", False)
app.config.setdefault("SECURITY_SEND_REGISTER_EMAIL", False)
app.config.setdefault("SECURITY_RECOVERABLE", False)
security = Security(app, datastore=skatetrax_user_datastore, register_blueprint=False)

# Flask-Mail (optional; only initialized when MAIL_SERVER is set)
mail = None
if os.environ.get("MAIL_SERVER"):
    from flask_mail import Mail
    app.config["MAIL_SERVER"] = os.environ["MAIL_SERVER"]
    app.config["MAIL_PORT"] = int(os.environ.get("MAIL_PORT", 587))
    app.config["MAIL_USE_TLS"] = os.environ.get("MAIL_USE_TLS", "false").lower() == "true"
    app.config["MAIL_USE_SSL"] = os.environ.get("MAIL_USE_SSL", "false").lower() == "true"
    app.config["MAIL_USERNAME"] = os.environ.get("MAIL_USERNAME")
    app.config["MAIL_PASSWORD"] = os.environ.get("MAIL_PASSWORD")
    app.config["MAIL_DEFAULT_SENDER"] = os.environ.get("MAIL_DEFAULT_SENDER", "noreply@skatetrax.com")
    mail = Mail(app)

# Public/Diag/Auth End Points
app.register_blueprint(auth_blueprint, url_prefix='/api/v4/auth')
app.register_blueprint(util_blueprint, url_prefix='/api/v4/utils')
app.register_blueprint(locations_blueprint, url_prefix='/api/v4/public')

# Protected Lookup Routes
app.register_blueprint(lookup_blueprint, url_prefix='/api/v4/lookup')

# Routes based on legacy structures
app.register_blueprint(dashboard_blueprint, url_prefix='/api/v4/members')
app.register_blueprint(ice_time_blueprint, url_prefix='/api/v4/members')
app.register_blueprint(skater_profile_blueprint, url_prefix='/api/v4/members')
app.register_blueprint(maintenance_blueprint, url_prefix='/api/v4/members')
app.register_blueprint(equipment_blueprint, url_prefix='/api/v4/members')

# Routes for POST datas
app.register_blueprint(sessions_blueprint, url_prefix='/api/v4/submit')


if __name__ == "__main__":
    app.run(host='0.0.0.0', debug=True)
