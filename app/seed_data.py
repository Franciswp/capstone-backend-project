# app/seed_data.py
"""
Seed sample movie/theater/auditorium/screening and set Redis seat keys to AVAILABLE.
Run inside container or locally (with env configured).
"""
import os
from datetime import datetime, timedelta
from pymongo import MongoClient
from bson import ObjectId
import redis
from dotenv import load_dotenv

from models_mongo import make_movie, make_theater, make_auditorium, make_screening

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '.env'))
MONGO_URI = os.environ.get('MONGO_URI')
MONGO_DB_NAME = os.environ.get('MONGO_DB_NAME', 'movie_booking')
REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')

mc = MongoClient(MONGO_URI)
mdb = mc[MONGO_DB_NAME]
r = redis.Redis.from_url(REDIS_URL, decode_responses=True)

def seed():
    # Movie
    movie_doc = make_movie("Example Movie", "An example", genre="Drama", runtime=100)
    mdb.movies.insert_one(movie_doc)

    # Theater + auditorium
    theater_doc = make_theater("Example Theater", "123 Example St")
    mdb.theaters.insert_one(theater_doc)

    seats = []
    rows = ['A','B','C']
    cols = 6
    for r_label in rows:
        for c in range(1, cols+1):
            seats.append(f"{r_label}{c}")

    aud_doc = make_auditorium(theater_doc['_id'], "Main Hall", rows=len(rows), seats_layout=[{'label': s} for s in seats])
    mdb.auditoriums.insert_one(aud_doc)

    # Screening
    start = datetime.utcnow() + timedelta(hours=2)
    scr_doc = make_screening(movie_doc['_id'], aud_doc['_id'], start_time=start)
    mdb.screenings.insert_one(scr_doc)

    # Seed seats in Redis
    pipeline = r.pipeline()
    for s in seats:
        k = f"screening:{str(scr_doc['_id'])}:seat:{s}"
        pipeline.set(k, 'AVAILABLE')
    pipeline.execute()

    print("Seeded movie, theater, auditorium, screening and seats.")
    print("screening_id:", str(scr_doc['_id']))

if __name__ == '__main__':
    seed()