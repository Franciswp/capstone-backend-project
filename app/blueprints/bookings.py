import os
import uuid
from flask import Blueprint, request, jsonify, g, current_app
from bson import ObjectId
from datetime import datetime

# Ensure this import is near the top of the file, before any @auth_required usage
try:
    from auth import auth_required
except ImportError:
    from app.auth import auth_required

bookings_bp = Blueprint('bookings', __name__)

def _load_lua_into_app(app, path, attr_name):
    if not getattr(app, attr_name, None):
        with open(path, 'r') as fh:
            sha = app.redis.script_load(fh.read())
        setattr(app, attr_name, sha)
    return getattr(app, attr_name)

@bookings_bp.route('/confirm', methods=['POST'])
@auth_required
def confirm_booking():
    body = request.get_json() or {}
    hold_id = body.get('hold_id')
    seat_labels = body.get('seat_labels', [])
    screening_id = body.get('screening_id')
    idempotency_key = body.get('idempotency_key')  # optional
    total_amount = body.get('total_amount', 0.0)

    if not (hold_id and seat_labels and screening_id):
        return jsonify({'error': 'hold_id, screening_id and seat_labels required'}), 400

    # Prepare redis keys
    keys = [f"screening:{screening_id}:seat:{s}" for s in seat_labels]
    r = current_app.redis

    # Load confirm script into redis if needed
    confirm_path = current_app.config.get('LUA_CONFIRM_PATH', os.path.join(os.path.dirname(__file__), '..', 'confirm_reserve.lua'))
    confirm_sha = _load_lua_into_app(current_app, confirm_path, 'confirm_reserve_sha')

    # Owner must be the authenticated user id
    owner = getattr(g, 'user_id', None)
    if not owner:
        return jsonify({'error': 'authentication_required'}), 401

    booking_id = str(ObjectId())
    reserve_ttl = current_app.config.get('RESERVE_TTL_SECONDS', 3600)

    # ARGV order for confirm_reserve.lua: hold_id, owner, booking_id, ttl
    try:
        res = r.evalsha(confirm_sha, len(keys), *keys, hold_id, owner, booking_id, reserve_ttl)
    except Exception as e:
        # Reload script in case of SCRIPTFLUSH and retry once
        with open(confirm_path, 'r') as fh:
            confirm_sha = r.script_load(fh.read())
        current_app.confirm_reserve_sha = confirm_sha
        res = r.evalsha(confirm_sha, len(keys), *keys, hold_id, owner, booking_id, reserve_ttl)

    # res shape: ["1"] or ["0", "<n>", key1, key2...]
    if isinstance(res, list) and res and res[1] == "1":
        bookings_col = current_app.mdb.bookings
        booking_doc = {
            '_id': ObjectId(booking_id),
            'user_id': ObjectId(owner),
            'screening_id': ObjectId(screening_id),
            'seat_labels': seat_labels,
            'total_amount': total_amount,
            'status': 'PENDING',
            'idempotency_key': idempotency_key if idempotency_key else None,
            'created_at': datetime.utcnow()
        }
        try:
            bookings_col.insert_one(booking_doc)
        except Exception as e:
            # If idempotency triggers a duplicate key error, return existing booking
            if idempotency_key:
                existing = bookings_col.find_one({'idempotency_key': idempotency_key})
                if existing:
                    return jsonify({'ok': True, 'booking': existing, 'idempotent': True}), 200

            # Rollback Redis reservation best-effort
            for k in keys:
                try:
                    current_app.redis.set(k, 'AVAILABLE')
                except Exception:
                    pass
            return jsonify({'error': 'db_insert_failed', 'detail': str(e)}), 500

        # Persist booking seats
        seat_docs = []
        now = datetime.utcnow()
        for s in seat_labels:
            seat_docs.append({
                'booking_id': booking_doc['_id'],
                'screening_id': booking_doc['screening_id'],
                'seat_label': s,
                'created_at': now
            })
        if seat_docs:
            current_app.mdb.booking_seats.insert_many(seat_docs)

        return jsonify({'ok': True, 'booking_id': str(booking_doc['_id'])}), 201
    else:
        unavailable = []
        if isinstance(res, list) and res and res[0] == "0":
            unavailable = res[2:] if len(res) > 2 else []

        return jsonify({'ok': False, 'unavailable_keys': unavailable}), 409