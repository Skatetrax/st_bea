import os

from flask_cors import CORS
from flask import Flask

# Load blueprints
from blueprints.auth_routes import auth_blueprint
from blueprints.util_routes import util_blueprint
from blueprints.routes_skater_profile import skater_profile_blueprint

app = Flask(__name__)
CORS(app, supports_credentials=True, origins=["http://localhost:3000"])
app.secret_key = os.environ.get("FLASK_SECRET_KEY")

app.register_blueprint(auth_blueprint, url_prefix='/api/v4/auth')
app.register_blueprint(util_blueprint, url_prefix='/api/v4/utils')
app.register_blueprint(skater_profile_blueprint, url_prefix='/api/v4/members')

if __name__ == "__main__":
    app.run(debug=True)
