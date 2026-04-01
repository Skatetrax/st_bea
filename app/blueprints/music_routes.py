from datetime import datetime, timezone
from uuid import UUID, uuid4
import io
import json
import logging

from flask import Blueprint, request, jsonify, session as flask_session
from flask_login import login_required, current_user
from pydantic import BaseModel, ValidationError

from skatetrax.models.cyberconnect2 import create_session
from skatetrax.models.t_music import MusicTrack, MusicPlaylist, MusicPlaylistTrack
from skatetrax.models.t_skaterMeta import uSkaterConfig

from utils.storage import upload_file, delete_file, get_public_url, is_configured

log = logging.getLogger(__name__)

music_blueprint = Blueprint("music_blueprint", __name__)

MAX_FILE_BYTES = 20 * 1024 * 1024
PERFORMANCE_CUT_CEILING = 300


def _get_skater_uuid():
    return getattr(current_user, "uSkaterUUID", None) or flask_session.get("uSkaterUUID")


def _track_to_dict(t):
    return {
        "id": str(t.id),
        "title": t.title,
        "artist": t.artist,
        "duration_seconds": t.duration_seconds,
        "is_performance_cut": t.is_performance_cut,
        "cut_duration_seconds": t.cut_duration_seconds,
        "storage_key": t.storage_key,
        "src": get_public_url(t.storage_key) if t.storage_key else None,
        "clearance_status": t.clearance_status,
        "clearance_provider": t.clearance_provider,
        "clearance_ref": t.clearance_ref,
        "apple_music_url": t.apple_music_url,
        "spotify_url": t.spotify_url,
        "youtube_url": t.youtube_url,
        "created_at": t.created_at.isoformat() if t.created_at else None,
    }


def _playlist_to_dict(pl, include_tracks=False, owner_name=None):
    result = {
        "id": str(pl.id),
        "name": pl.name,
        "description": pl.description,
        "playlist_type": pl.playlist_type,
        "share_token": str(pl.share_token) if pl.share_token else None,
        "created_at": pl.created_at.isoformat() if pl.created_at else None,
        "track_ids": [str(e.track_id) for e in pl.track_entries],
    }
    if owner_name is not None:
        result["owner"] = owner_name
    if include_tracks:
        result["tracks"] = [_track_to_dict(e.track) for e in pl.track_entries]
    return result


def _parse_uuid(value, label="ID"):
    try:
        return UUID(str(value))
    except (ValueError, AttributeError):
        return None


# ── Pydantic models ──

class CreateTrackPayload(BaseModel):
    title: str
    artist: str | None = None
    is_performance_cut: bool = False
    clearance_status: str = "not_required"
    clearance_provider: str | None = None
    clearance_ref: str | None = None
    apple_music_url: str | None = None
    spotify_url: str | None = None
    youtube_url: str | None = None


class CreatePlaylistPayload(BaseModel):
    name: str
    description: str | None = None
    playlist_type: str = "practice"


class UpdatePlaylistPayload(BaseModel):
    name: str | None = None
    description: str | None = None
    playlist_type: str | None = None


# ── Track endpoints ──

@music_blueprint.route('/tracks', methods=['GET'])
@login_required
def list_tracks():
    uuid = _get_skater_uuid()
    if not uuid:
        log.warning("list_tracks: _get_skater_uuid() returned None")
        return jsonify({"error": "Missing skater UUID"}), 400

    with create_session() as sess:
        tracks = (
            sess.query(MusicTrack)
            .filter(MusicTrack.uSkaterUUID == uuid)
            .order_by(MusicTrack.created_at.desc())
            .all()
        )
        log.debug("list_tracks: uuid=%s returned %d tracks", uuid, len(tracks))
        return jsonify([_track_to_dict(t) for t in tracks])


@music_blueprint.route('/tracks', methods=['POST'])
@login_required
def upload_track():
    uuid = _get_skater_uuid()
    if not uuid:
        return jsonify({"error": "Missing skater UUID"}), 400

    if not is_configured():
        return jsonify({"error": "File storage is not configured"}), 503

    audio = request.files.get("audio")
    if not audio:
        return jsonify({"error": "No audio file provided"}), 400

    audio_bytes = audio.read()
    if len(audio_bytes) > MAX_FILE_BYTES:
        return jsonify({"error": f"File too large (max {MAX_FILE_BYTES // (1024*1024)}MB)"}), 400

    duration = None
    try:
        from mutagen import File as MutagenFile
        mf = MutagenFile(io.BytesIO(audio_bytes))
        if mf and mf.info and mf.info.length:
            duration = int(mf.info.length)
        else:
            return jsonify({"error": "Could not read audio duration -- unsupported or corrupt file"}), 400
    except Exception:
        return jsonify({"error": "Could not read audio file -- unsupported format"}), 400

    duration_hint = None
    if duration <= PERFORMANCE_CUT_CEILING:
        duration_hint = "performance_cut"
    else:
        duration_hint = "practice"

    meta_json = request.form.get("metadata", "{}")
    try:
        meta = json.loads(meta_json)
        payload = CreateTrackPayload(**meta)
    except (json.JSONDecodeError, ValidationError) as e:
        return jsonify({"error": "Invalid metadata", "details": str(e)}), 400

    track_id = uuid4()
    ext = audio.filename.rsplit(".", 1)[-1].lower() if "." in (audio.filename or "") else "mp3"
    storage_key = f"music/{uuid}/{track_id}.{ext}"

    upload_file(io.BytesIO(audio_bytes), storage_key, content_type=audio.content_type or "audio/mpeg")

    with create_session() as sess:
        track = MusicTrack(
            title=payload.title,
            uSkaterUUID=uuid,
            artist=payload.artist,
            duration_seconds=duration,
            is_performance_cut=payload.is_performance_cut,
            storage_key=storage_key,
            clearance_status=payload.clearance_status,
            clearance_provider=payload.clearance_provider,
            clearance_ref=payload.clearance_ref,
            apple_music_url=payload.apple_music_url,
            spotify_url=payload.spotify_url,
            youtube_url=payload.youtube_url,
        )
        track.id = track_id
        sess.add(track)
        sess.commit()
        sess.refresh(track)
        result = _track_to_dict(track)
        result["duration_hint"] = duration_hint
        return jsonify(result), 201


@music_blueprint.route('/tracks/<track_id>', methods=['DELETE'])
@login_required
def delete_track(track_id):
    uuid = _get_skater_uuid()
    if not uuid:
        return jsonify({"error": "Missing skater UUID"}), 400

    parsed_id = _parse_uuid(track_id, "track_id")
    if not parsed_id:
        return jsonify({"error": "Invalid track ID"}), 400

    with create_session() as sess:
        track = (
            sess.query(MusicTrack)
            .filter(MusicTrack.id == parsed_id, MusicTrack.uSkaterUUID == uuid)
            .first()
        )
        if not track:
            return jsonify({"error": "Track not found"}), 404

        affected_playlist_ids = [
            e.playlist_id for e in track.playlist_entries
        ]

        if track.storage_key:
            delete_file(track.storage_key)

        sess.delete(track)
        sess.flush()

        for pl_id in affected_playlist_ids:
            remaining = (
                sess.query(MusicPlaylistTrack)
                .filter(MusicPlaylistTrack.playlist_id == pl_id)
                .count()
            )
            if remaining == 0:
                pl = sess.query(MusicPlaylist).filter(MusicPlaylist.id == pl_id).first()
                if pl and pl.share_token:
                    log.info("Unsharing empty playlist %s after last track removed", pl.name)
                    pl.share_token = None

        sess.commit()
        return jsonify({"status": "ok"})


# ── Playlist endpoints ──

@music_blueprint.route('/playlists', methods=['GET'])
@login_required
def list_playlists():
    uuid = _get_skater_uuid()
    if not uuid:
        log.warning("list_playlists: _get_skater_uuid() returned None")
        return jsonify({"error": "Missing skater UUID"}), 400

    with create_session() as sess:
        playlists = (
            sess.query(MusicPlaylist)
            .filter(MusicPlaylist.uSkaterUUID == uuid)
            .order_by(MusicPlaylist.created_at.desc())
            .all()
        )
        log.debug("list_playlists: uuid=%s returned %d playlists", uuid, len(playlists))
        return jsonify([_playlist_to_dict(pl) for pl in playlists])


@music_blueprint.route('/playlists', methods=['POST'])
@login_required
def create_playlist():
    uuid = _get_skater_uuid()
    if not uuid:
        return jsonify({"error": "Missing skater UUID"}), 400

    data = request.get_json()
    if not data:
        return jsonify({"error": "Missing JSON payload"}), 400

    try:
        payload = CreatePlaylistPayload(**data)
    except ValidationError as ve:
        return jsonify({"error": "Invalid input", "details": ve.errors()}), 400

    with create_session() as sess:
        pl = MusicPlaylist(
            name=payload.name,
            uSkaterUUID=uuid,
            description=payload.description,
            playlist_type=payload.playlist_type,
        )
        sess.add(pl)
        sess.commit()
        sess.refresh(pl)
        return jsonify(_playlist_to_dict(pl)), 201


@music_blueprint.route('/playlists/<playlist_id>', methods=['PUT'])
@login_required
def update_playlist(playlist_id):
    uuid = _get_skater_uuid()
    if not uuid:
        return jsonify({"error": "Missing skater UUID"}), 400

    parsed_id = _parse_uuid(playlist_id, "playlist_id")
    if not parsed_id:
        return jsonify({"error": "Invalid playlist ID"}), 400

    data = request.get_json()
    if not data:
        return jsonify({"error": "Missing JSON payload"}), 400

    try:
        payload = UpdatePlaylistPayload(**data)
    except ValidationError as ve:
        return jsonify({"error": "Invalid input", "details": ve.errors()}), 400

    with create_session() as sess:
        pl = (
            sess.query(MusicPlaylist)
            .filter(MusicPlaylist.id == parsed_id, MusicPlaylist.uSkaterUUID == uuid)
            .first()
        )
        if not pl:
            return jsonify({"error": "Playlist not found"}), 404

        if payload.name is not None:
            pl.name = payload.name
        if payload.description is not None:
            pl.description = payload.description
        if payload.playlist_type is not None:
            pl.playlist_type = payload.playlist_type

        sess.commit()
        sess.refresh(pl)
        return jsonify(_playlist_to_dict(pl))


@music_blueprint.route('/playlists/<playlist_id>', methods=['DELETE'])
@login_required
def delete_playlist(playlist_id):
    uuid = _get_skater_uuid()
    if not uuid:
        return jsonify({"error": "Missing skater UUID"}), 400

    parsed_id = _parse_uuid(playlist_id, "playlist_id")
    if not parsed_id:
        return jsonify({"error": "Invalid playlist ID"}), 400

    with create_session() as sess:
        pl = (
            sess.query(MusicPlaylist)
            .filter(MusicPlaylist.id == parsed_id, MusicPlaylist.uSkaterUUID == uuid)
            .first()
        )
        if not pl:
            return jsonify({"error": "Playlist not found"}), 404

        sess.delete(pl)
        sess.commit()
        return jsonify({"status": "ok"})


# ── Playlist track management ──

@music_blueprint.route('/playlists/<playlist_id>/tracks', methods=['PUT'])
@login_required
def set_playlist_tracks(playlist_id):
    """Replace the full track list with ordered track IDs."""
    uuid = _get_skater_uuid()
    if not uuid:
        return jsonify({"error": "Missing skater UUID"}), 400

    parsed_pl_id = _parse_uuid(playlist_id, "playlist_id")
    if not parsed_pl_id:
        return jsonify({"error": "Invalid playlist ID"}), 400

    data = request.get_json()
    track_ids = data.get("track_ids", []) if data else []

    parsed_track_ids = []
    for tid in track_ids:
        parsed = _parse_uuid(tid, "track_id")
        if not parsed:
            return jsonify({"error": f"Invalid track ID: {tid}"}), 400
        parsed_track_ids.append(parsed)

    with create_session() as sess:
        pl = (
            sess.query(MusicPlaylist)
            .filter(MusicPlaylist.id == parsed_pl_id, MusicPlaylist.uSkaterUUID == uuid)
            .first()
        )
        if not pl:
            return jsonify({"error": "Playlist not found"}), 404

        if parsed_track_ids:
            owned_count = (
                sess.query(MusicTrack)
                .filter(MusicTrack.id.in_(parsed_track_ids), MusicTrack.uSkaterUUID == uuid)
                .count()
            )
            if owned_count != len(set(parsed_track_ids)):
                return jsonify({"error": "One or more track IDs are invalid or not owned by you"}), 403

        sess.query(MusicPlaylistTrack).filter(
            MusicPlaylistTrack.playlist_id == pl.id
        ).delete()

        for pos, tid in enumerate(parsed_track_ids):
            sess.add(MusicPlaylistTrack(
                playlist_id=pl.id,
                track_id=tid,
                position=pos,
            ))

        sess.commit()
        sess.refresh(pl)
        return jsonify(_playlist_to_dict(pl))


# ── Sharing ──

@music_blueprint.route('/playlists/<playlist_id>/share', methods=['POST'])
@login_required
def share_playlist(playlist_id):
    uuid = _get_skater_uuid()
    if not uuid:
        return jsonify({"error": "Missing skater UUID"}), 400

    parsed_id = _parse_uuid(playlist_id, "playlist_id")
    if not parsed_id:
        return jsonify({"error": "Invalid playlist ID"}), 400

    with create_session() as sess:
        pl = (
            sess.query(MusicPlaylist)
            .filter(MusicPlaylist.id == parsed_id, MusicPlaylist.uSkaterUUID == uuid)
            .first()
        )
        if not pl:
            return jsonify({"error": "Playlist not found"}), 404

        if not pl.share_token:
            pl.share_token = uuid4()
            sess.commit()
            sess.refresh(pl)

        return jsonify({"share_token": str(pl.share_token)})


@music_blueprint.route('/playlists/<playlist_id>/share', methods=['DELETE'])
@login_required
def unshare_playlist(playlist_id):
    uuid = _get_skater_uuid()
    if not uuid:
        return jsonify({"error": "Missing skater UUID"}), 400

    parsed_id = _parse_uuid(playlist_id, "playlist_id")
    if not parsed_id:
        return jsonify({"error": "Invalid playlist ID"}), 400

    with create_session() as sess:
        pl = (
            sess.query(MusicPlaylist)
            .filter(MusicPlaylist.id == parsed_id, MusicPlaylist.uSkaterUUID == uuid)
            .first()
        )
        if not pl:
            return jsonify({"error": "Playlist not found"}), 404

        pl.share_token = None
        sess.commit()
        return jsonify({"status": "ok"})


# ── Public shared playlist (no auth) ──

@music_blueprint.route('/shared/<share_token>', methods=['GET'])
def get_shared_playlist(share_token):
    parsed_token = _parse_uuid(share_token, "share_token")
    if not parsed_token:
        return jsonify({"error": "Invalid share link"}), 400

    with create_session() as sess:
        pl = (
            sess.query(MusicPlaylist)
            .filter(MusicPlaylist.share_token == parsed_token)
            .first()
        )
        if not pl:
            return jsonify({"error": "Playlist not found or no longer shared"}), 404

        owner_name = None
        skater = (
            sess.query(uSkaterConfig)
            .filter(uSkaterConfig.uSkaterUUID == pl.uSkaterUUID)
            .first()
        )
        if skater:
            owner_name = skater.uSkaterFname or "A Skater"

        return jsonify(_playlist_to_dict(pl, include_tracks=True, owner_name=owner_name))
