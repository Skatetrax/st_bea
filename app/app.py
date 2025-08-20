import os

from flask_cors import CORS
from flask import Flask

# Load blueprints
from blueprints.auth_routes import auth_blueprint
from blueprints.util_routes import util_blueprint
from blueprints.routes_skater_profile import skater_profile_blueprint
from blueprints.dashboard_routes import dashboard_blueprint
from blueprints.ice_time_routes import ice_time_blueprint
from blueprints.public_routes import locations_blueprint
from blueprints.submit_routes import sessions_blueprint

app = Flask(__name__)
CORS(app, supports_credentials=True, origins=["http://localhost:3000"])
app.secret_key = os.environ.get("FLASK_SECRET_KEY")


# Public/Diag/Auth End Points
app.register_blueprint(auth_blueprint, url_prefix='/api/v4/auth')
app.register_blueprint(util_blueprint, url_prefix='/api/v4/utils')
app.register_blueprint(locations_blueprint, url_prefix='/api/v4/public')

# Routes based on legacy structures
app.register_blueprint(dashboard_blueprint, url_prefix='/api/v4/members')
app.register_blueprint(ice_time_blueprint, url_prefix='/api/v4/members')
app.register_blueprint(skater_profile_blueprint, url_prefix='/api/v4/members')

# Routes for POST datas
app.register_blueprint(sessions_blueprint, url_prefix='/api/v4/submit')


if __name__ == "__main__":
    app.run(debug=True)
