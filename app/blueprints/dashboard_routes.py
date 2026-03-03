from datetime import date, timedelta
from flask import Blueprint, jsonify, session as flask_session
import pandas as pd
from sqlalchemy import func
from flask_login import login_required, current_user

from skatetrax.models.cyberconnect2 import create_session
from skatetrax.models.t_ice_time import Ice_Time
from skatetrax.models.ops.data_tables import Sessions_Tables
from skatetrax.models.ops.data_aggregates import SkaterAggregates, uMaintenanceV4

# Create a blueprint instance
dashboard_blueprint = Blueprint("dashboard_blueprint", __name__)


@dashboard_blueprint.route('/dashboard', methods=['GET'])
@login_required
def protected():
    uSkaterUUID = getattr(current_user, "uSkaterUUID", None) or flask_session.get("uSkaterUUID")
    
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
    maint = uMaintenanceV4(uSkaterUUID)
    chart_maint = maint.maint_clock()

    # financial totals
    equipment = ice_times.equipment_cost()
    maintenance = maint.maint_cost()
    class_fees = ice_times.school_class_cost()
    performance = ice_times.test_cost()
    membership = ice_times.membership_cost()
    competition = ice_times.competition_cost()
    ice_cost = ice_times.ice_cost()
    coaching = ice_times.coach_cost()

    spend_values = [equipment, maintenance, class_fees, performance,
                     membership, competition, ice_cost, coaching]
    spend_total = "%0.2f" % sum(float(v) for v in spend_values)

    chart_spend = {
        "equipment": equipment,
        "maintenance": maintenance,
        "class": class_fees,
        "performance": performance,
        "membership": membership,
        "competition": competition,
        "ice_time": ice_cost,
        "coaching": coaching,
        "total": spend_total,
    }
    
    # 3-month rolling baseline: average sessions/month for the 3 full
    # calendar months preceding the current one
    today = date.today()
    first_of_this_month = today.replace(day=1)
    baseline_end = first_of_this_month - timedelta(days=1)          # last day of prev month
    m = baseline_end.month - 2
    y = baseline_end.year
    if m <= 0:
        m += 12
        y -= 1
    baseline_start = date(y, m, 1)                                  # first day, 3 months back

    with create_session() as db:
        baseline_total = (
            db.query(func.count(Ice_Time.ice_time_id))
            .filter(
                Ice_Time.uSkaterUUID == uSkaterUUID,
                Ice_Time.date >= baseline_start,
                Ice_Time.date <= baseline_end,
            )
            .scalar() or 0
        )
    baseline_monthly_avg = round(baseline_total / 3, 1)

    # 3-month average time breakdown (raw minutes -> divide by 3 -> hours/min)
    bl_total_min = ice_times.aggregate(Ice_Time, "ice_time", baseline_start, baseline_end)
    bl_coached_min = ice_times.aggregate(Ice_Time, "coach_time", baseline_start, baseline_end)
    bl_group_min = ice_times.aggregate(
        Ice_Time, "ice_time", baseline_start, baseline_end,
        ice_type_ids=ice_times.GROUP_SESSION_IDS
    )
    bl_practice_min = max(bl_total_min - bl_coached_min - bl_group_min, 0)

    def _avg_to_hm(total_minutes):
        avg = total_minutes / 3
        h, m = divmod(avg, 60)
        return {"hours": int(h), "minutes": round(m, 1)}

    baseline_ratio = {
        "coached": _avg_to_hm(bl_coached_min),
        "practice": _avg_to_hm(bl_practice_min),
        "group": _avg_to_hm(bl_group_min),
    }

    # set up sessions table for current month
    sessions = Sessions_Tables.ice_time_current_month(uSkaterUUID)
    session_table = pd.DataFrame(sessions)
    
    return jsonify({
        "total_time": total_time,
        "baseline_monthly_avg": baseline_monthly_avg,
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
            "baseline_ratio": baseline_ratio,
            "spend": chart_spend
        },
        "maintenance": chart_maint,
        "session_table": session_table.to_dict(orient="records")
    })
