# app/blueprints/users.py
from flask import Blueprint, request, current_app, jsonify, g
from bson import ObjectId
from datetime import datetime

from models_mongo import make_user, doc_to_json
from schemas import UserCreate
from auth import make_access_token, make_refresh_token, decode_token, hash_password, verify_password

users_bp = Blueprint('users', __name__)

@users_bp.route('/register', methods=['POST'])
def register():
    payload = request.get_json() or {}

    # Extract raw password and validate it exists
    password = payload.pop('password', None)
    if not password:
        return jsonify({'error': 'password is required'}), 400

    # Hash and map to the field expected by the schema
    payload['hashed_password'] = hash_password(password)

    # Validate input with the schema
    obj = UserCreate(**payload)

    # Create the user document and insert
    doc = make_user(obj.name, obj.email, obj.hashed_password, obj.role)
    try:
        current_app.mdb.users.insert_one(doc)
    except Exception as e:
        return jsonify({'error': 'user_exists_or_db_error', 'detail': str(e)}), 400

    out = doc_to_json(doc)
    out.pop('hashed_password', None)
    return jsonify(out), 201

@users_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    if not (email and password):
        return jsonify({'error': 'email_and_password_required'}), 400
    user = current_app.mdb.users.find_one({'email': email.lower()})
    if not user:
        return jsonify({'error': 'invalid_credentials'}), 401
    if not verify_password(user.get('hashed_password', ''), password):
        return jsonify({'error': 'invalid_credentials'}), 401

    user_id = str(user['_id'])
    role = user.get('role', 'customer')
    access = make_access_token(user_id, role)
    refresh = make_refresh_token(user_id)

    # Persist refresh token in DB for possible revocation and rotation
    current_app.mdb.refresh_tokens.insert_one({
        '_id': refresh,  # store token itself as _id for quick lookup
        'user_id': ObjectId(user_id),
        'created_at': datetime.utcnow()
    })
    return jsonify({'access_token': access, 'refresh_token': refresh, 'role': role}), 200

@users_bp.route('/refresh', methods=['POST'])
def refresh():
    data = request.get_json()
    token = data.get('refresh_token')
    if not token:
        return jsonify({'error': 'refresh_token_required'}), 400
    payload = decode_token(token)
    if 'error' in payload:
        return jsonify({'error': payload['error']}), 401
    if payload.get('typ') != 'refresh':
        return jsonify({'error': 'invalid_token_type'}), 401
    # ensure token exists in DB (not revoked)
    doc = current_app.mdb.refresh_tokens.find_one({'_id': token})
    if not doc:
        return jsonify({'error': 'token_revoked_or_unknown'}), 401
    user_id = payload.get('sub')
    user = current_app.mdb.users.find_one({'_id': ObjectId(user_id)})
    if not user:
        return jsonify({'error': 'user_not_found'}), 404
    new_access = make_access_token(user_id, user.get('role', 'customer'))
    return jsonify({'access_token': new_access}), 200

@users_bp.route('/logout', methods=['POST'])
def logout():
    data = request.get_json(silent=True) or {}
    refresh = data.get('refresh_token')
    if not refresh:
        return jsonify({'error': 'refresh_token_required'}), 400

    # delete persisted refresh token to revoke it
    result = current_app.mdb.refresh_tokens.delete_one({'_id': refresh})

    if result.deleted_count:
        # Log to server and return a friendly message
        current_app.logger.info('You have successfully log out')
        return jsonify({'message': 'You have successfully log out'}), 200

    return jsonify({'error': 'invalid_refresh_token'}), 400

# simple profile endpoint
@users_bp.route('/me', methods=['GET'])
def me():
    # Try Authorization header first; fall back to cookie
    auth = request.headers.get('Authorization', '')
    token = None

    if auth.startswith('Bearer '):
        token = auth.split(' ', 1)[1].strip()
    else:
        token = request.cookies.get('access_token_cookie') or request.cookies.get('access_token')

    if not token:
        return jsonify({'error': 'authorization_required'}), 401

    try:
        payload = decode_token(token)
    except Exception:
        return jsonify({'error': 'invalid_token'}), 401

    if not isinstance(payload, dict):
        return jsonify({'error': 'invalid_token'}), 401
    if 'error' in payload:
        return jsonify({'error': payload['error']}), 401

    user_id = payload.get('sub') or payload.get('user_id') or payload.get('id')
    if not user_id:
        return jsonify({'error': 'invalid_token'}), 401

    try:
        oid = ObjectId(user_id)
    except Exception:
        return jsonify({'error': 'invalid_token'}), 401

    user = current_app.mdb.users.find_one({'_id': oid})
    if not user:
        return jsonify({'error': 'not_found'}), 404

    out = doc_to_json(user)
    for k in ('hashed_password', 'password', 'salt'):
        out.pop(k, None)
    return jsonify(out), 200

#List Users Route
@users_bp.route("/", methods=["GET"])
def list_users():
    """GET /users/ Fetch all users from the database."""
    try:
        limit = int(request.args.get("limit", 50))
        skip = int(request.args.get("skip", 0))
    except ValueError:
        return jsonify({"error": "invalid_pagination_params"}), 400

    # Safety cap on limit
    limit = max(1, min(limit, 200))
    cursor = (current_app.mdb.users.find({})
              .skip(skip)
              .limit(limit))

    users = []
    for doc in cursor:
        user_json = doc_to_json(doc)
        # Remove sensitive fields
        for k in ("hashed_password", "password", "salt"):
            user_json.pop(k, None)
        users.append(user_json)

    return jsonify(users), 200
