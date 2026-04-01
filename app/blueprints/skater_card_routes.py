from uuid import UUID, uuid4

from flask import Blueprint, request, jsonify, session as flask_session
from flask_login import login_required, current_user

from skatetrax.models.cyberconnect2 import create_session
from skatetrax.models.t_skaterMeta import uSkaterConfig
from skatetrax.models.t_music import MusicPlaylist, MusicPlaylistTrack
from sqlalchemy import func, distinct
from skatetrax.models.t_events import SkaterEvent, EventEntry, EventType
from skatetrax.models.t_locations import Locations
from skatetrax.models.ops.data_aggregates import UserMeta, SkaterAggregates

skater_card_blueprint = Blueprint("skater_card_blueprint", __name__)

VALID_CONTACT_PREFS = {"email", "text", "phone", "social"}


def _get_skater_uuid():
    return getattr(current_user, "uSkaterUUID", None) or flask_session.get("uSkaterUUID")


def _parse_uuid(value):
    try:
        return UUID(str(value))
    except (ValueError, AttributeError):
        return None


def _hrs(val):
    """Convert minutes_to_hours dict {'hours': h, 'minutes': m} to a float."""
    if isinstance(val, dict):
        return val.get("hours", 0) + val.get("minutes", 0) / 60.0
    return float(val or 0)


def _build_card(uuid):
    """Assemble the skater card dict from existing data."""
    meta = UserMeta(uuid)
    profile_dict = meta.to_dict()
    if not profile_dict:
        return None

    agg = SkaterAggregates(uuid)

    earliest = agg.earliest_session_date()
    total_sessions = agg.session_count("total")

    weeks_active = None
    if earliest:
        from datetime import date
        today = date.today()
        delta_days = (today - earliest.date()).days if hasattr(earliest, 'date') else (today - earliest).days
        weeks_active = max(delta_days / 7.0, 1)

    total_h = _hrs(agg.skated("total"))
    coached_h = _hrs(agg.coached("total"))
    group_h = _hrs(agg.group_time("total"))
    solo_h = _hrs(agg.practice("total"))

    with create_session() as sess:
        shared_playlists = (
            sess.query(MusicPlaylist.name, MusicPlaylist.share_token)
            .filter(MusicPlaylist.uSkaterUUID == uuid,
                    MusicPlaylist.share_token.isnot(None))
            .filter(
                sess.query(MusicPlaylistTrack)
                .filter(MusicPlaylistTrack.playlist_id == MusicPlaylist.id)
                .exists()
            )
            .all()
        )
        shared_playlist_list = [
            {"name": p.name, "token": str(p.share_token)}
            for p in shared_playlists
        ]

        comp_join = (EventEntry.event_type == EventType.id)
        comp_cat = (EventType.category == "Competition")

        comp_events = (
            sess.query(func.count(distinct(SkaterEvent.id)))
            .join(EventEntry, EventEntry.event_id == SkaterEvent.id)
            .join(EventType, comp_join)
            .filter(comp_cat, SkaterEvent.uSkaterUUID == uuid)
            .scalar()
        )
        comp_entries = (
            sess.query(func.count(EventEntry.id))
            .join(EventType, comp_join)
            .filter(comp_cat, EventEntry.uSkaterUUID == uuid)
            .scalar()
        )
        comp_podiums = (
            sess.query(func.count(EventEntry.id))
            .join(EventType, comp_join)
            .filter(
                comp_cat,
                EventEntry.uSkaterUUID == uuid,
                EventEntry.placement.isnot(None),
                EventEntry.placement <= 3,
            )
            .scalar()
        )

        last_event_row = (
            sess.query(
                SkaterEvent.event_label,
                SkaterEvent.event_date,
                Locations.rink_city,
                Locations.rink_state,
            )
            .join(EventEntry, EventEntry.event_id == SkaterEvent.id)
            .join(EventType, comp_join)
            .outerjoin(Locations, SkaterEvent.event_location == Locations.rink_id)
            .filter(comp_cat, EventEntry.uSkaterUUID == uuid)
            .order_by(SkaterEvent.event_date.desc())
            .first()
        )

        last_event = None
        if last_event_row:
            loc_parts = [last_event_row.rink_city, last_event_row.rink_state]
            loc_str = ", ".join(p for p in loc_parts if p)
            evt_date = last_event_row.event_date
            last_event = {
                "name": last_event_row.event_label,
                "date": evt_date.strftime("%B %Y") if evt_date else None,
                "location": loc_str or None,
            }

    return {
        "identity": {
            "first_name": profile_dict.get("uSkaterFname"),
            "middle_name": profile_dict.get("uSkaterMname"),
            "last_name": profile_dict.get("uSkaterLname"),
            "city": profile_dict.get("uSkaterCity"),
            "state": profile_dict.get("uSkaterState"),
            "club": profile_dict.get("org_Club"),
            "usfsa_number": profile_dict.get("org_USFSA_number"),
            "contact_preference": profile_dict.get("contact_preference"),
        },
        "lifetime": {
            "skating_since": earliest.isoformat() if earliest else None,
            "coached_pct": round(coached_h / total_h * 100) if total_h else 0,
            "group_pct": round(group_h / total_h * 100) if total_h else 0,
            "solo_pct": round(solo_h / total_h * 100) if total_h else 0,
            "sessions_per_week": round(total_sessions / weeks_active, 1) if weeks_active else 0,
            "avg_session_min": round(total_h * 60 / total_sessions) if total_sessions else 0,
            "events": comp_events,
            "entries": comp_entries,
            "podiums": comp_podiums,
            "previous_coaches": agg.distinct_coach_count("total"),
        },
        "recent": (lambda rh, rc, rg, rs, rsess: {
            "coached_pct": round(rc / rh * 100) if rh else 0,
            "group_pct": round(rg / rh * 100) if rh else 0,
            "solo_pct": round(rs / rh * 100) if rh else 0,
            "sessions_per_week": round(rsess / 13.0, 1),
            "avg_session_min": round(rh * 60 / rsess) if rsess else 0,
            "last_event": last_event,
            "distinct_rinks": agg.distinct_rink_count("90d"),
            "rinks": agg.rinks_list("90d"),
        })(
            _hrs(agg.skated("90d")),
            _hrs(agg.coached("90d")),
            _hrs(agg.group_time("90d")),
            _hrs(agg.practice("90d")),
            agg.session_count("90d"),
        ),
        "current": {
            "coach": profile_dict.get("activeCoach"),
            "home_rink": profile_dict.get("uSkaterRinkPref"),
            "boots": (profile_dict.get("uSkaterComboIce") or "").split(" / ")[0] or None,
            "blades": (profile_dict.get("uSkaterComboIce") or "").split(" / ")[1] if " / " in (profile_dict.get("uSkaterComboIce") or "") else None,
            "shared_playlists": shared_playlist_list,
        },
        "share_token": profile_dict.get("share_token"),
    }


@skater_card_blueprint.route('/skater_card', methods=['GET'])
@login_required
def get_skater_card():
    uuid = _get_skater_uuid()
    if not uuid:
        return jsonify({"error": "Missing skater UUID"}), 400

    card = _build_card(uuid)
    if not card:
        return jsonify({"error": "Profile not found"}), 404
    return jsonify(card)


@skater_card_blueprint.route('/skater_card/share', methods=['POST'])
@login_required
def share_card():
    uuid = _get_skater_uuid()
    if not uuid:
        return jsonify({"error": "Missing skater UUID"}), 400

    with create_session() as sess:
        profile = sess.query(uSkaterConfig).filter(
            uSkaterConfig.uSkaterUUID == uuid).first()
        if not profile:
            return jsonify({"error": "Profile not found"}), 404

        if not profile.share_token:
            profile.share_token = uuid4()
            sess.commit()
            sess.refresh(profile)

        return jsonify({"share_token": str(profile.share_token)})


@skater_card_blueprint.route('/skater_card/share', methods=['DELETE'])
@login_required
def unshare_card():
    uuid = _get_skater_uuid()
    if not uuid:
        return jsonify({"error": "Missing skater UUID"}), 400

    with create_session() as sess:
        profile = sess.query(uSkaterConfig).filter(
            uSkaterConfig.uSkaterUUID == uuid).first()
        if not profile:
            return jsonify({"error": "Profile not found"}), 404

        profile.share_token = None
        sess.commit()
        return jsonify({"status": "ok"})


@skater_card_blueprint.route('/shared_card/<share_token>', methods=['GET'])
def get_shared_card(share_token):
    parsed = _parse_uuid(share_token)
    if not parsed:
        return jsonify({"error": "Invalid share link"}), 400

    with create_session() as sess:
        profile = sess.query(uSkaterConfig).filter(
            uSkaterConfig.share_token == parsed).first()
        if not profile:
            return jsonify({"error": "Skater card not found or no longer shared"}), 404

        card = _build_card(profile.uSkaterUUID)
        if not card:
            return jsonify({"error": "Profile data unavailable"}), 404

        card.pop("share_token", None)
        return jsonify(card)


@skater_card_blueprint.route('/contact_preference', methods=['PATCH'])
@login_required
def update_contact_preference():
    uuid = _get_skater_uuid()
    if not uuid:
        return jsonify({"error": "Missing skater UUID"}), 400

    data = request.get_json()
    if not data:
        return jsonify({"error": "Missing JSON payload"}), 400

    pref = data.get("contact_preference")
    if pref is not None and pref not in VALID_CONTACT_PREFS:
        return jsonify({"error": f"Invalid preference. Must be one of: {', '.join(sorted(VALID_CONTACT_PREFS))}"}), 400

    with create_session() as sess:
        profile = sess.query(uSkaterConfig).filter(
            uSkaterConfig.uSkaterUUID == uuid).first()
        if not profile:
            return jsonify({"error": "Profile not found"}), 404

        profile.contact_preference = pref
        sess.commit()
        return jsonify({"contact_preference": pref})
