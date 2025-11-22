# tests/test_confirm_unit.py
import os
import pytest
import fakeredis
import mongomock
from redis import Redis
from bson import ObjectId

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
HOLD_PATH = os.path.join(BASE, 'app', 'hold_seats.lua')
CONFIRM_PATH = os.path.join(BASE, 'app', 'confirm_reserve.lua')

def load_script(r, path):
    with open(path, 'r') as f:
        return r.script_load(f.read())

@pytest.fixture
def fake_redis():
    return fakeredis.FakeRedis(decode_responses=True)

@pytest.fixture
def fake_mongo():
    return mongomock.MongoClient().db

def test_hold_then_confirm_success(fake_redis, fake_mongo):
    hold_sha = load_script(fake_redis, HOLD_PATH)
    confirm_sha = load_script(fake_redis, CONFIRM_PATH)

    screening_id = str(ObjectId())
    seats = ['A1', 'A2']
    keys = [f"screening:{screening_id}:seat:{s}" for s in seats]

    # seed seats as AVAILABLE
    for k in keys:
        fake_redis.set(k, 'AVAILABLE')

    hold_id = str(ObjectId())
    owner = str(ObjectId())  # simulated user id

    # hold seats (owner-aware)
    res = fake_redis.evalsha(hold_sha, len(keys), *keys, hold_id, 600, owner)
    assert isinstance(res, list) and res,[0] == '1'

    # confirm reservation with correct owner
    booking_id = str(ObjectId())
    res2 = fake_redis.evalsha(confirm_sha, len(keys), *keys, hold_id, owner, booking_id, 3600)
    assert isinstance(res2, list) and res2,[0] == '1'

    # ensure keys are RESERVED:booking_id
    for k in keys:
        assert fake_redis.get(k) == f"RESERVED:{booking_id}"

def test_confirm_fails_if_wrong_owner(fake_redis):
    hold_sha = load_script(fake_redis, HOLD_PATH)
    confirm_sha = load_script(fake_redis, CONFIRM_PATH)

    screening_id = str(ObjectId())
    keys = [f"screening:{screening_id}:seat:A1", f"screening:{screening_id}:seat:A2"]

    # seed and set hold by owner1
    for k in keys:
        fake_redis.set(k, 'AVAILABLE')
    hold_id = str(ObjectId())
    owner1 = str(ObjectId())
    fake_redis.evalsha(hold_sha, len(keys), *keys, hold_id, 600, owner1)

    # attempt to confirm using a different owner (owner2)
    owner2 = str(ObjectId())
    booking_id = str(ObjectId())
    res = fake_redis.evalsha(confirm_sha, len(keys), *keys, hold_id, owner2, booking_id, 3600)
    assert isinstance(res, list) and res,[0] == '0'