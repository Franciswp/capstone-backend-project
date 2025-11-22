# app/models_mongo.py
from datetime import datetime
from typing import List, Dict, Any, Optional

from bson import ObjectId

# Add this import near the top of the file
try:
    from auth import hash_password
except ImportError:
    from app.auth import hash_password

# Helpers --------------------------------------------------------------------

def new_oid() -> ObjectId:
    return ObjectId()

def oid_str(o):
    if isinstance(o, ObjectId):
        return str(o)
    return o

def doc_to_json(doc: dict) -> dict:
    if not doc:
        return doc
    out = dict(doc)
    if '_id' in out:
        out['id'] = str(out.pop('_id'))
    # convert common ObjectId refs
    for k, v in list(out.items()):
        if isinstance(v, ObjectId):
            out[k] = str(v)
    return out

# Factories ------------------------------------------------------------------

def make_user(name: str, email: str, hashed_password: str, role: str = 'customer') -> dict:
    return {
        '_id': new_oid(),
        'name': name,
        'email': email.lower(),
        'hashed_password': hashed_password,
        'role': role,
        'created_at': datetime.utcnow(),
        'updated_at': datetime.utcnow()
    }

def make_movie(title: str, description: str = None, genre: str = None,
               runtime: int = None, rating: float = None, poster_url: str = None) -> dict:
    return {
        '_id': new_oid(),
        'title': title,
        'description': description,
        'genre': genre,
        'runtime': runtime,
        'rating': rating,
        'poster_url': poster_url,
        'created_at': datetime.utcnow()
    }

def make_theater(name: str, address: str = None) -> dict:
    return {
        '_id': new_oid(),
        'name': name,
        'address': address,
        'auditoriums': [],
        'created_at': datetime.utcnow()
    }

def make_auditorium(theater_id: ObjectId, name: str, rows: int = None, seats_layout: List[dict] = None) -> dict:
    return {
        '_id': new_oid(),
        'theater_id': theater_id,
        'name': name,
        'rows': rows,
        'seats_layout': seats_layout or [],
        'created_at': datetime.utcnow()
    }

def make_screening(movie_id: ObjectId, auditorium_id: ObjectId, start_time: datetime,
                   end_time: datetime = None, language: str = None, price_policy_id: str = None) -> dict:
    return {
        '_id': new_oid(),
        'movie_id': movie_id,
        'auditorium_id': auditorium_id,
        'start_time': start_time,
        'end_time': end_time,
        'language': language,
        'price_policy_id': price_policy_id,
        'created_at': datetime.utcnow()
    }

def make_booking(user_id: ObjectId, screening_id: ObjectId, status: str = 'PENDING',
                 total_amount: float = 0.0, expires_at: datetime = None, idempotency_key: str = None) -> dict:
    return {
        '_id': new_oid(),
        'user_id': user_id,
        'screening_id': screening_id,
        'status': status,
        'total_amount': total_amount,
        'payment_id': None,
        'created_at': datetime.utcnow(),
        'expires_at': expires_at,
        'idempotency_key': idempotency_key
    }

def make_booking_seat(booking_id: ObjectId, screening_id: ObjectId, seat_label: str) -> dict:
    return {
        '_id': new_oid(),
        'booking_id': booking_id,
        'screening_id': screening_id,
        'seat_label': seat_label,
        'created_at': datetime.utcnow()
    }

def make_payment(booking_id: ObjectId, provider: str, amount: float, status: str = 'INITIATED',
                 provider_reference: str = None) -> dict:
    return {
        '_id': new_oid(),
        'booking_id': booking_id,
        'provider': provider,
        'status': status,
        'amount': amount,
        'provider_reference': provider_reference,
        'created_at': datetime.utcnow()
    }

def make_review(user_id: ObjectId, movie_id: ObjectId, rating: int, comment: str = None) -> dict:
    return {
        '_id': new_oid(),
        'user_id': user_id,
        'movie_id': movie_id,
        'rating': rating,
        'comment': comment,
        'created_at': datetime.utcnow()
    }

# Indexes --------------------------------------------------------------------

def ensure_indexes(db):
    db.users.create_index('email', unique=True)
    db.movies.create_index('title')
    db.theaters.create_index('name')
    db.auditoriums.create_index([('theater_id', 1)])
    db.screenings.create_index([('auditorium_id', 1), ('start_time', 1)])
    db.bookings.create_index([('user_id', 1)])
    db.bookings.create_index([('screening_id', 1)])
    db.booking_seats.create_index([('screening_id', 1), ('seat_label', 1)], unique=True)
    db.payments.create_index([('booking_id', 1)])
    db.reviews.create_index([('movie_id', 1), ('user_id', 1)])