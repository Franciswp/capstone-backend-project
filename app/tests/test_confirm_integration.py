# tests/test_confirm_integration.py
import os
import pytest
from pymongo import MongoClient
from redis import Redis
from bson import ObjectId

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
HOLD_PATH = os.path.join(BASE, 'app', 'hold_seats.lua')
CONFIRM_PATH = os.path.join(BASE, 'app', 'confirm_reserve.lua')

def load_script(r, path):
    with open(path, 'r') as f:
        return r.script_load(f.read())

MONGO_URI = os.environ.get('MONGO_URI')
REDIS_URL = os.environ.get('REDIS_URL')

pytestmark = pytest.mark.skipif(not (MONGO_URI and REDIS_URL), reason="Integration test requires MONGO_URI and REDIS_URL env vars")

def test_full_confirm_integration():
    mc = MongoClient(MONGO_URI)
    db = mc.get_default_database()
    r = Redis.from_url(REDIS_URL, decode_responses=True)

    # load scripts
    hold_sha = load_script(r, HOLD_PATH)
    confirm_sha = load_script(r, CONFIRM_PATH)

    # cleanup
    db.bookings.delete_many({})
    db.booking_seats.delete_many({})

    screening_id = str(ObjectId())
    seats = ['B1', 'B2']
    keys = [f"screening:{screening_id}:seat:{s}" for s in seats]
    for k in keys:
        r.set(k, 'AVAILABLE')

    hold_id = str(ObjectId())
    owner = str(ObjectId())

    # hold
    res = r.evalsha(hold_sha, len(keys), *keys, hold_id, 600, owner)
    assert isinstance(res, list) and res,[0] == '1'

    # confirm with right owner
    booking_id = str(ObjectId())
    res2 = r.evalsha(confirm_sha, len(keys), *keys, hold_id, owner, booking_id, 3600)
    assert isinstance(res2, list) and res2,[0] == '1'

    # persist to mongodb to simulate endpoint
    booking_doc = {
        '_id': ObjectId(booking_id),
        'user_id': ObjectId(owner),
        'screening_id': ObjectId(screening_id),
        'seat_labels': seats,
        'status': 'PENDING'
    }
    db.bookings.insert_one(booking_doc)
    found = db.bookings.find_one({'_id': ObjectId(booking_id)})
    assert found is not None

    # cleanup
    for k in keys:
        r.delete(k)