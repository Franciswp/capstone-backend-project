# app/blueprints/reviews.py
from flask import Blueprint, request, current_app, jsonify
from models_mongo import make_review, doc_to_json
from bson import ObjectId

reviews_bp = Blueprint('reviews', __name__)

@reviews_bp.route('', methods=['POST'])
def create_review():
    data = request.get_json()
    user_id = data.get('user_id')
    movie_id = data.get('movie_id')
    rating = data.get('rating')
    comment = data.get('comment')
    if not (user_id and movie_id and rating is not None):
        return jsonify({'error': 'user_id, movie_id, rating required'}), 400
    try:
        user_oid = ObjectId(user_id)
        movie_oid = ObjectId(movie_id)
    except Exception:
        return jsonify({'error': 'invalid id format'}), 400
    rev = make_review(user_oid, movie_oid, int(rating), comment=comment)
    current_app.mdb.reviews.insert_one(rev)
    return jsonify(doc_to_json(rev)), 201

@reviews_bp.route('/movie/<movie_id>', methods=['GET'])
def get_movie_reviews(movie_id):
    try:
        movie_oid = ObjectId(movie_id)
    except Exception:
        return jsonify({'error': 'invalid id'}), 400
    cursor = current_app.mdb.reviews.find({'movie_id': movie_oid})
    reviews = [doc_to_json(d) for d in cursor]
    return jsonify(reviews), 200