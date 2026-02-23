from flask import Blueprint, jsonify, session as flask_session
import pandas as pd

from skatetrax.models.cyberconnect2 import Session

from skatetrax.models.t_auth import uAuthTable
from skatetrax.models.ops.data_tables import Sessions_Tables
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
    
    # build various time line perspectives for coach/group/ice times
    ice_times = SkaterAggregates(uSkaterUUID)
    
    total_time = ice_times.skated('total')

    monthly_hours_practice = ice_times.practice("current_month")
    monthly_hours_coached = ice_times.coached("current_month")
    monthly_hours_group = ice_times.group_time("current_month")

    yearly_hours_practice = ice_times.practice("12m")
    yearly_hours_coached = ice_times.coached("12m")
    yearly_hours_group = ice_times.group_time("12m")
    
    # build maintenance chart data
    chart_maint = uMaintenanceV4(uSkaterUUID).maint_clock()
    
    # pseudo-financial data
    chart_spend = {
        "equipment": "3,908.97",
        "maintenance": "331.31",
        "performance": "540.00",
        "membership": "35.00",
        "competition": "88.35",
        "ice_time": "35.00",
        "coaching": "4,520.00",
        "class": "10,836.20",
        "total": "20,294.83"
    }
    
    # set up sessions table for current month
    sessions = Sessions_Tables.ice_time_current_month(uSkaterUUID)
    session_table = pd.DataFrame(sessions)
    
    return jsonify({
        "total_time": total_time,
        "charts": {
            "monthly_ratio": {
                "practice": monthly_hours_practice,
                "coached": monthly_hours_coached,
                "group": monthly_hours_group
            },
            "yearly_ratio": {
                "practice": yearly_hours_practice,
                "coached": yearly_hours_coached,
                "group": yearly_hours_group
            },
            "spend": chart_spend
        },
        "maintenance": chart_maint,
        "session_table": session_table.to_dict(orient="records")
    })
