import math
from datetime import date
from uuid import UUID

from flask import Blueprint, request, jsonify, session as flask_session
from flask_login import login_required, current_user
from pydantic import BaseModel, ValidationError, Field

from skatetrax.models.cyberconnect2 import create_session
from skatetrax.models.ops.data_tables import EventsTable
from skatetrax.models.ops.data_details import EventDetail
from skatetrax.models.ops.pencil import Event_Data
from skatetrax.utils.results_importer import import_entry_to_event

events_blueprint = Blueprint("events_blueprint", __name__)


def _get_skater_uuid():
    return getattr(current_user, "uSkaterUUID", None) or flask_session.get("uSkaterUUID")


def _scrub_nan(records):
    """Replace NaN floats with None for JSON serialization."""
    for row in records:
        for k, v in row.items():
            if isinstance(v, float) and math.isnan(v):
                row[k] = None
    return records


# ── Pydantic models ────────────────────────────────────────────────────

class CostItemPayload(BaseModel):
    category: str
    amount: float
    quantity: int = 1
    note: str | None = None


class CreateEventPayload(BaseModel):
    event_label: str
    event_date: date
    event_location: UUID | None = None
    hosting_club: str | None = None
    coach_id: UUID | None = None
    notes: str | None = None
    costs: list[CostItemPayload] = []

    class Config:
        arbitrary_types_allowed = True


class CreateEntryPayload(BaseModel):
    entry_date: date | None = None
    event_segment: str | None = None
    event_level: str | None = None
    status: str = "Committed"
    category: str | None = None
    scoring_system: str | None = None
    governing_body: str | None = Field(None, description="Short name, e.g. USFSA")
    placement: int | None = None
    field_size: int | None = None
    majority: str | None = None
    total_segment_score: float | None = None
    source_url: str | None = None
    video_url: str | None = None
    scores: list[dict] | None = None
    deductions: list[dict] | None = None

    class Config:
        arbitrary_types_allowed = True


class ImportEntryPayload(BaseModel):
    url: str
    skater_name: str
    entry_date: date | None = None

    class Config:
        arbitrary_types_allowed = True


# ── GET /events ────────────────────────────────────────────────────────

@events_blueprint.route("", methods=["GET"])
@login_required
def list_events():
    """List competition entries with optional category filter.

    Query params:
        category  -- comma-separated EventType.category values
                     (e.g. "Competition" or "Showcase,Exhibition")
    """
    uuid = _get_skater_uuid()
    if not uuid:
        return jsonify({"error": "Missing skater UUID"}), 400

    category = request.args.get("category")
    categories = [c.strip() for c in category.split(",")] if category else None

    try:
        df = EventsTable.list_competitions(uuid, category=categories)
        records = _scrub_nan(df.to_dict(orient="records")) if not df.empty else []
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({"entries": records})


# ── GET /events/<event_id> ─────────────────────────────────────────────

@events_blueprint.route("/<event_id>", methods=["GET"])
@login_required
def get_event_detail(event_id):
    """Full detail for a single event including entries, scores, and deductions."""
    uuid = _get_skater_uuid()
    if not uuid:
        return jsonify({"error": "Missing skater UUID"}), 400

    detail = EventDetail.get(event_id, uuid)
    if detail is None:
        return jsonify({"error": "Event not found"}), 404

    return jsonify(detail)


# ── POST /events ───────────────────────────────────────────────────────

@events_blueprint.route("", methods=["POST"])
@login_required
def create_event():
    """Create a new event (competition/showcase shell). Returns the event_id."""
    uuid = _get_skater_uuid()
    if not uuid:
        return jsonify({"error": "Missing skater UUID"}), 400

    data = request.get_json()
    if not data:
        return jsonify({"error": "Missing JSON payload"}), 400

    try:
        payload = CreateEventPayload(**data)
    except ValidationError as ve:
        return jsonify({"error": "Invalid input", "details": ve.errors()}), 400

    from skatetrax.models.t_events import COST_CATEGORIES

    dump = payload.model_dump()
    costs_raw = dump.pop("costs", [])
    dump["uSkaterUUID"] = uuid

    for ci in costs_raw:
        if ci["category"] not in COST_CATEGORIES:
            return jsonify({
                "error": f"Invalid cost category '{ci['category']}'. "
                         f"Must be one of: {COST_CATEGORIES}",
            }), 400

    costs_list = [
        {"category": c["category"], "amount": c["amount"],
         "quantity": c.get("quantity", 1), "note": c.get("note")}
        for c in costs_raw
    ]

    try:
        event = Event_Data.add_event_with_entries(
            dump, entries_list=[], costs_list=costs_list)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({"event_id": str(event.id)}), 201


# ── POST /events/<event_id>/entries ────────────────────────────────────

@events_blueprint.route("/<event_id>/entries", methods=["POST"])
@login_required
def add_entry(event_id):
    """Add an entry to an existing event (manual path)."""
    uuid = _get_skater_uuid()
    if not uuid:
        return jsonify({"error": "Missing skater UUID"}), 400

    data = request.get_json()
    if not data:
        return jsonify({"error": "Missing JSON payload"}), 400

    try:
        payload = CreateEntryPayload(**data)
    except ValidationError as ve:
        return jsonify({"error": "Invalid input", "details": ve.errors()}), 400

    entry_dict = {
        "event_segment": payload.event_segment,
        "event_level": payload.event_level,
        "status": payload.status,
        "placement": payload.placement,
        "field_size": payload.field_size,
        "majority": payload.majority,
        "total_segment_score": payload.total_segment_score,
        "source_url": payload.source_url,
        "video_url": payload.video_url,
        "uSkaterUUID": uuid,
    }
    if payload.entry_date:
        entry_dict["entry_date"] = payload.entry_date

    event_type_id = None
    if payload.category:
        event_type_id = Event_Data.resolve_event_type(
            payload.category,
            payload.scoring_system or None,
            payload.governing_body or None,
        )
    if event_type_id:
        entry_dict["event_type"] = event_type_id

    scores = payload.scores or []
    deductions = payload.deductions or []

    try:
        entry = Event_Data.add_entry(
            event_id=event_id,
            entry_dict=entry_dict,
            scores=scores,
            deductions=deductions,
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({"entry_id": str(entry.id)}), 201


# ── POST /events/<event_id>/entries/import ─────────────────────────────

@events_blueprint.route("/<event_id>/entries/import", methods=["POST"])
@login_required
def import_entry(event_id):
    """Parse a results URL and attach the entry to an existing event."""
    uuid = _get_skater_uuid()
    if not uuid:
        return jsonify({"error": "Missing skater UUID"}), 400

    data = request.get_json()
    if not data:
        return jsonify({"error": "Missing JSON payload"}), 400

    try:
        payload = ImportEntryPayload(**data)
    except ValidationError as ve:
        return jsonify({"error": "Invalid input", "details": ve.errors()}), 400

    try:
        result = import_entry_to_event(
            url=payload.url,
            skater_name=payload.skater_name,
            uSkaterUUID=uuid,
            event_id=event_id,
            entry_date=payload.entry_date,
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 400

    return jsonify(result), 201
