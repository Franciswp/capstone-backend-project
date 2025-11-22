# app/common.py
import os
from typing import Optional, Tuple

from bson import ObjectId
from dotenv import load_dotenv
from pymongo import MongoClient
import redis

# Reuse project's helpers
from models_mongo import ensure_indexes, doc_to_json  # ensure_indexes and doc_to_json expected in models_mongo

load_dotenv()


def init_db_and_redis(app: Optional[object] = None) -> Tuple[MongoClient, object, redis.Redis, Optional[str]]:
    """
    Initialize MongoClient, Mongo DB handle, Redis client, and load the hold_seats Lua script.

    Returns:
        (mc, mdb, r, hold_sha)
        - mc: pymongo.MongoClient
        - mdb: database handle (mc[MONGO_DB_NAME])
        - r: redis.Redis client
        - hold_sha: SHA of the loaded Lua script or None if load failed
    """
    MONGO_URI = os.environ.get('MONGO_URI')
    MONGO_DB_NAME = os.environ.get('MONGO_DB_NAME', 'movie_booking')
    REDIS_URL = os.environ.get('REDIS_URL', 'redis://redis:6379/0')

    # Initialize Mongo
    mc = MongoClient(MONGO_URI)
    mdb = mc[MONGO_DB_NAME]

    # Create sparse unique index for idempotency_key (idempotency handling)
    # This is idempotent: create_index will not duplicate the index if it already exists.
    mdb.bookings.create_index(
        'idempotency_key',
        unique=True,
        sparse=True,
        background=True
    )

    # Initialize Redis
    r = redis.Redis.from_url(REDIS_URL, decode_responses=True)

    # Load hold_seats.lua into Redis (if present)
    lua_path = os.path.join(os.path.dirname(__file__), 'hold_seats.lua')
    hold_sha = None
    try:
        if os.path.exists(lua_path):
            with open(lua_path, 'r') as fh:
                lua_script = fh.read()
            try:
                hold_sha = r.script_load(lua_script)
            except Exception:
                # Script load may fail if Redis not reachable or scripts disabled; keep hold_sha as None
                hold_sha = None
    except Exception:
        # Best-effort: do not raise here so callers can decide how to handle partial failures
        hold_sha = None

    return mc, mdb, r, hold_sha


def ensure_indexes_db(mdb) -> None:
    """
    Ensure application-specific indexes exist in the given MongoDB database handle.

    Delegates to models_mongo.ensure_indexes for central index management.
    """
    ensure_indexes(mdb)