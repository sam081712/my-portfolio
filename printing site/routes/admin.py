import re
import time
import uuid
from functools import wraps
from pathlib import Path

import bcrypt
import jwt
from flask import Blueprint, request, jsonify, send_file, g

import config as C
from store import store, OwnerEmailAlreadySet

bp = Blueprint("admin", __name__)

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


# This is the real guard — hiding the owner panel's HTML is not security;
# checking the JWT on every admin request is the actual protection.
def require_owner(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        token = auth[7:] if auth.startswith("Bearer ") else None
        if not token:
            return jsonify({"error": "Login required."}), 401
        try:
            g.owner = jwt.decode(token, C.JWT_SECRET, algorithms=["HS256"])
        except jwt.PyJWTError:
            return jsonify({"error": "Session expired, please log in again."}), 401
        return fn(*args, **kwargs)
    return wrapper


# ---------------- owner email (one-time) + login ----------------

@bp.get("/owner-status")
def owner_status():
    return jsonify(store.owner_status())


@bp.post("/setup-email")
def setup_email():
    body = request.get_json(silent=True) or {}
    email = str(body.get("email") or "").strip().lower()
    if not EMAIL_RE.match(email):
        return jsonify({"error": "Enter a valid email."}), 400
    try:
        saved = store.set_owner_email(email)
        return jsonify({"email": saved})
    except OwnerEmailAlreadySet as e:
        return jsonify({"error": str(e)}), e.status


@bp.post("/login")
def login():
    body = request.get_json(silent=True) or {}
    email = str(body.get("email") or "").strip().lower()
    password = str(body.get("password") or "")
    status = store.owner_status()

    if not status["emailSet"]:
        return jsonify({"error": "Set the owner email first."}), 400
    if email != status["email"]:
        return jsonify({"error": "Incorrect email or password."}), 401
    if not C.OWNER_PASSWORD_HASH:
        return jsonify({"error": "OWNER_PASSWORD_HASH is not set on the server (check .env)."}), 500

    ok = bcrypt.checkpw(password.encode("utf-8"), C.OWNER_PASSWORD_HASH.encode("utf-8"))
    if not ok:
        return jsonify({"error": "Incorrect email or password."}), 401

    payload = {"owner": email, "iat": int(time.time()), "exp": int(time.time()) + 8 * 3600}
    token = jwt.encode(payload, C.JWT_SECRET, algorithm="HS256")
    return jsonify({"token": token})


@bp.get("/me")
@require_owner
def me():
    return jsonify({"owner": g.owner["owner"]})


# ---------------- rates / extras / shop config ----------------

@bp.put("/config")
@require_owner
def update_config():
    body = request.get_json(silent=True) or {}
    config = store.update_config({
        "rates": body.get("rates"),
        "extras": body.get("extras"),
        "shop": body.get("shop"),
    })
    return jsonify({"config": config})


# ---------------- payment QR ----------------

@bp.post("/qr")
@require_owner
def upload_qr():
    f = request.files.get("qr")
    if not f or not (f.mimetype or "").startswith("image/"):
        return jsonify({"error": "Only image files can be uploaded."}), 400
    ext = Path(f.filename or "").suffix or ".png"
    stored_name = "qr-" + uuid.uuid4().hex[:16] + ext
    dest = Path(store.UPLOAD_DIR) / stored_name
    f.save(dest)
    qr_url = "/uploads/" + stored_name
    store.set_qr_url(qr_url)
    return jsonify({"qrUrl": qr_url})


# ---------------- orders ----------------

@bp.get("/orders")
@require_owner
def list_orders():
    return jsonify({"orders": store.list_orders()})


@bp.patch("/orders/<order_id>")
@require_owner
def patch_order(order_id):
    body = request.get_json(silent=True) or {}
    status_val = str(body.get("status") or "").upper()
    if status_val not in {"PLACED", "ADVANCE_PAID", "PRINTING", "READY", "DELIVERED"}:
        return jsonify({"error": "Invalid status."}), 400
    order = store.set_order_status(order_id, status_val)
    if not order:
        return jsonify({"error": "Order not found."}), 404
    return jsonify({"order": order})


# ---------------- uploaded files (view / track "seen") ----------------

@bp.get("/files")
@require_owner
def list_files():
    recent, seen = store.list_files()

    def strip(f):
        return {"id": f["id"], "name": f["name"], "size": f["size"], "kind": f["kind"], "order": f["order"], "seen": f["seen"]}

    return jsonify({"recent": [strip(f) for f in recent], "seen": [strip(f) for f in seen]})


@bp.get("/files/<file_id>")
@require_owner
def get_file(file_id):
    record = store.get_file(file_id)
    if not record:
        return jsonify({"error": "File not found."}), 404
    file_path = Path(store.UPLOAD_DIR) / record["storedName"]
    if not file_path.exists():
        return jsonify({"error": "File not found on disk."}), 404
    store.mark_file_seen(file_id)
    return send_file(
        file_path,
        mimetype=record["mime"],
        as_attachment=False,
        download_name=record["name"],
    )
