from flask import Blueprint, jsonify, session as flask_session
from skatetrax.models.cyberconnect2 import Session
from skatetrax.models.t_auth import uAuthTable
from skatetrax.models.ops.data_aggregates import SkaterAggregates, uMaintenanceV4

# Create a blueprint instance
dashboard_blueprint = Blueprint("dashboard_blueprint", __name__)

@dashboard_blueprint.route('/dashboard', methods=['GET'])
def protected():
    user_id = flask_session.get('user_id')
    if not user_id:
        return jsonify({"message": "Unauthorized"}), 401

    with Session() as db:
        user = db.query(uAuthTable).filter_by(id=user_id).first()
        if not user:
            return jsonify({"message": "Unauthorized"}), 401

    uSkaterUUID=flask_session['uSkaterUUID']
    
    ice_times = SkaterAggregates(uSkaterUUID)
    
    total_time = ice_times.skated('total')
    monthly_hours_practice = ice_times.skated("current_month")
    monthly_hours_coached = ice_times.coached("current_month")
    yearly_hours_practice = ice_times.skated("12m")
    yearly_hours_coached = ice_times.coached("12m")
    
    chart_maint = uMaintenanceV4(uSkaterUUID).maint_clock()
    
    
    return jsonify({
        "total_time": total_time,
        "charts": {
            "monthly_ratio": {
                "practice": monthly_hours_practice,
                "coached": monthly_hours_coached
            },
            "yearly_ratio": {
                "practice": yearly_hours_practice,
                "coached": yearly_hours_coached
            }
        },
        "maintenance": chart_maint
    })
