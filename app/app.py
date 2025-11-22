import os
import sys
import socket
import io
from dotenv import load_dotenv
from flask import Flask, jsonify, request, make_response
from flask_cors import CORS

from common import init_db_and_redis, ensure_indexes_db

# Import blueprints
from blueprints.users import users_bp
from blueprints.movies import movies_bp
from blueprints.bookings import bookings_bp
from blueprints.payments import payments_bp
from blueprints.reviews import reviews_bp

# Load environment variables from the .env file
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "config.example"))

def create_app() -> Flask:
    app = Flask(__name__)

    # Enable CORS for specified origins
    CORS(app, resources={r"/*": {"origins": ["*"]}}, supports_credentials=True)

    # Load configuration into app.config for convenience
    app.config["HOLD_TTL_SECONDS"] = int(os.environ.get("HOLD_TTL_SECONDS", 600))
    app.config["JWT_SECRET"] = os.environ.get("JWT_SECRET")
    app.config["LUA_PATH"] = os.path.join(os.path.dirname(__file__), "hold_seats.lua")

    # Initialize database and Redis
    mc, mdb, r, hold_seats_sha = init_db_and_redis(app)
    ensure_indexes_db(mdb)

    # Attach the database clients to the app
    app.mongodb_client = mc
    app.mdb = mdb
    app.redis = r
    app.hold_seats_sha = hold_seats_sha

    # Register blueprints
    app.register_blueprint(users_bp, url_prefix="/users")
    app.register_blueprint(movies_bp, url_prefix="/movies")
    app.register_blueprint(bookings_bp, url_prefix="/bookings")
    app.register_blueprint(payments_bp, url_prefix="/payments")
    app.register_blueprint(reviews_bp, url_prefix="/reviews")

    @app.route("/screenings/<string:screening_id>", methods=["GET", "OPTIONS"])
    def get_screening(screening_id: str):
        if request.method == "OPTIONS":
            resp = make_response("", 204)
            resp.headers["Access-Control-Allow-Origin"] = "*"
            resp.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
            resp.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
            resp.headers["Access-Control-Allow-Credentials"] = "true"
            return resp

        # Normal GET logic
        resp = make_response("...", 200)
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Credentials"] = "true"
        return resp

    @app.route("/health", methods=["GET"])
    def health():
        return jsonify({"ok": True}), 200

    return app

def is_port_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.2)
        return sock.connect_ex((host, port)) == 0

def _stream_output(prefix: str, stream: io.TextIOBase) -> None:
    for line in iter(stream.readline, ""):
        sys.stdout.write(f"{prefix} {line}")
    stream.close()

if __name__ == "__main__":
    try:
        # Run the backend application
        application = create_app()
        application.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)
    except Exception as e:
        print(f"An error occurred: {e}")