import time
from collections import defaultdict
from pathlib import Path

from flask import Flask, jsonify, send_from_directory, request
from flask_cors import CORS
from werkzeug.exceptions import HTTPException

import config as C
from routes.orders import bp as orders_bp
from routes.upload import bp as upload_bp
from routes.admin import bp as admin_bp

BASE_DIR = Path(__file__).resolve().parent

app = Flask(__name__, static_folder=None)
app.config["MAX_CONTENT_LENGTH"] = 26 * 1024 * 1024  # slightly above the 25 MB per-file limit

# CORS_ORIGIN in config.py is always a LIST, never a string —
# so check "*" in it directly; a typeof-string check would be wrong.
_origins = "*" if "*" in C.CORS_ORIGIN else C.CORS_ORIGIN
CORS(app, resources={r"/api/*": {"origins": _origins}}, methods=["GET", "POST", "PUT", "PATCH"])


@app.after_request
def set_security_headers(resp):
    # A light hand-rolled equivalent of helmet() — CSP is left off so CDN
    # scripts (fonts, pdf.js) aren't blocked, same as the Node version.
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "no-referrer-when-downgrade"
    return resp


# Simple per-IP rate limit — to prevent brute force and spam.
_hits = defaultdict(list)


@app.before_request
def rate_limit():
    ip = request.headers.get("X-Forwarded-For", request.remote_addr) or "unknown"
    now = time.time()
    hits = [t for t in _hits[ip] if now - t < 60]
    hits.append(now)
    _hits[ip] = hits
    if len(hits) > 60:
        return jsonify({"error": "Too many requests. Try again in a bit."}), 429


@app.route("/uploads/<path:filename>")
def serve_uploads(filename):
    return send_from_directory(BASE_DIR / "uploads", filename)


# assets/ = files committed to the repo (like the default payment QR) — these don't
# disappear on a restart/redeploy, because they're part of the actual code, not a runtime upload.
@app.route("/assets/<path:filename>")
def serve_assets(filename):
    return send_from_directory(BASE_DIR / "assets", filename)


app.register_blueprint(upload_bp, url_prefix="/api/files")
app.register_blueprint(admin_bp, url_prefix="/api/admin")
app.register_blueprint(orders_bp, url_prefix="/api/orders")


@app.get("/api/health")
def health():
    return jsonify({"ok": True, "dev": C.DEV})


# The frontend file here is named "index.html" —
# if you rename it, update this path to match.
@app.route("/")
def index():
    resp = send_from_directory(BASE_DIR, "index.html")
    # no-store so the browser doesn't cache an old index.html during dev/testing —
    # otherwise the old UI keeps showing even after changing the file or restarting the server.
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    return resp


@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Route not found."}), 404


@app.errorhandler(HTTPException)
def handle_http_error(e):
    return jsonify({"error": e.description}), e.code


@app.errorhandler(Exception)
def handle_error(e):
    app.logger.exception(e)
    return jsonify({"error": "Server error."}), 500


if __name__ == "__main__":
    print(f"PrintCampus backend -> http://localhost:{C.PORT}")
    app.run(host="0.0.0.0", port=C.PORT, debug=C.DEV)
