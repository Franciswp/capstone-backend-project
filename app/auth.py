import os
import time
from datetime import datetime, timedelta
from functools import wraps

import jwt
from flask import request, jsonify, current_app, g
from werkzeug.security import generate_password_hash, check_password_hash

from bson import ObjectId

JWT_SECRET = os.environ.get('JWT_SECRET', 'changeme_super_secret_replace')
ACCESS_EXPIRE_MINUTES = int(os.environ.get('ACCESS_TOKEN_EXPIRES_MINUTES', '15'))
REFRESH_EXPIRE_DAYS = int(os.environ.get('REFRESH_TOKEN_EXPIRES_DAYS', '7'))

ALGORITHM = 'HS256'

def make_access_token(user_id: str, role: str, expires_minutes: int = ACCESS_EXPIRE_MINUTES):
    now = datetime.utcnow()
    exp = now + timedelta(minutes=expires_minutes)
    payload = {
        'sub': str(user_id),
        'role': role,
        'iat': int(now.timestamp()),
        'exp': int(exp.timestamp()),
        'typ': 'access'
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=ALGORITHM)

def make_refresh_token(user_id: str, expires_days: int = REFRESH_EXPIRE_DAYS):
    now = datetime.utcnow()
    exp = now + timedelta(days=expires_days)
    payload = {
        'sub': str(user_id),
        'iat': int(now.timestamp()),
        'exp': int(exp.timestamp()),
        'typ': 'refresh'
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=ALGORITHM)

def decode_token(token: str):
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return {'error': 'token_expired'}
    except jwt.InvalidTokenError:
        return {'error': 'invalid_token'}

def auth_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        auth = request.headers.get('Authorization', '')

        if not auth:
            return jsonify({'error': 'missing Authorization header'}), 401

        parts = auth.split(None, 1)
        if len(parts) != 2:
            return jsonify({'error': 'invalid Authorization header'}), 401

        scheme, token = parts[0], parts[1].strip()
        if scheme.lower() != 'bearer' or not token:
            return jsonify({'error': 'invalid auth scheme or token'}), 401

        # continue with verifying `token`...
        payload = decode_token(token)
        if 'error' in payload:
            return jsonify({'error': payload['error']}), 401
        # access tokens must have typ=access
        if payload.get('typ') != 'access':
            return jsonify({'error': 'invalid_token_type'}), 401
        # attach user info to flask.g
        g.user_id = payload.get('sub')
        g.user_role = payload.get('role')
        return fn(*args, **kwargs)
    return wrapper

def requires_role(role):
    def decorator(fn):
        @wraps(fn)
        @auth_required
        def wrapper(*args, **kwargs):
            user_role = getattr(g, 'user_role', None)
            # allow admin to access any role-protected route
            if user_role == 'admin' or user_role == role:
                return fn(*args, **kwargs)
            return jsonify({'error': 'forbidden'}), 403
        return wrapper
    return decorator

# Password helpers (convenience)
def hash_password(plain: str) -> str:
    return generate_password_hash(plain)

def verify_password(hashed: str, plain: str) -> bool:
    return check_password_hash(hashed, plain)