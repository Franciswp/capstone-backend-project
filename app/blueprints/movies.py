# app/blueprints/movies.py
from flask import Blueprint, request, current_app, jsonify
from bson import ObjectId
from datetime import datetime

from models_mongo import make_movie, make_screening, doc_to_json
from auth import requires_role
from auth import auth_required

movies_bp = Blueprint('movies', __name__)

@movies_bp.route('', methods=['POST'])
@requires_role('admin')   # only admins (or role==admin) can create movies
def create_movie():
    payload = request.get_json()
    title = payload.get('title')
    if not title:
        return jsonify({'error': 'title required'}), 400
    doc = make_movie(title, description=payload.get('description'), genre=payload.get('genre'),
                     runtime=payload.get('runtime'), rating=payload.get('rating'),
                     poster_url=payload.get('poster_url'))
    current_app.mdb.movies.insert_one(doc)
    return jsonify(doc_to_json(doc)), 201

@movies_bp.route('/<movie_id>', methods=['GET'])
def get_movie(movie_id):
    try:
        _id = ObjectId(movie_id)
    except Exception:
        return jsonify({'error': 'invalid id'}), 400
    doc = current_app.mdb.movies.find_one({'_id': _id})
    if not doc:
        return jsonify({'error': 'not found'}), 404
    return jsonify(doc_to_json(doc)), 200

@movies_bp.route('all', methods=['GET'])
def list_movies():
    docs = current_app.mdb.movies.find({})
    return jsonify([doc_to_json(doc) for doc in docs]), 200