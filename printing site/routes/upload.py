import os
import re
import uuid
from pathlib import Path
from flask import Blueprint, request, jsonify
from store import store

bp = Blueprint("upload", __name__)

ALLOWED = {"application/pdf", "image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_SIZE = 25 * 1024 * 1024  # 25 MB, matches the frontend's own check
PHONE_RE = re.compile(r"^91[6-9]\d{9}$")


def is_valid_phone(phone):
    return bool(phone) and bool(PHONE_RE.match(str(phone)))


# POST /api/files — a student's PDF/photo upload. Identified by the phone header.
@bp.route("", methods=["POST"])
def upload_files():
    phone = request.headers.get("x-phone")
    if not is_valid_phone(phone):
        return jsonify({"error": "Phone number was not recognized, please try again."}), 400

    files = request.files.getlist("files")
    if not files:
        return jsonify({"error": "No file was received."}), 400

    out = []
    for f in files:
        mime = f.mimetype or "application/octet-stream"
        if mime not in ALLOWED:
            return jsonify({"error": "Only PDF or image files are allowed."}), 400

        f.stream.seek(0, os.SEEK_END)
        size = f.stream.tell()
        f.stream.seek(0)
        if size > MAX_SIZE:
            return jsonify({"error": f"{f.filename} is larger than 25 MB."}), 400

        ext = Path(f.filename or "").suffix
        stored_name = uuid.uuid4().hex + ext
        dest = Path(store.UPLOAD_DIR) / stored_name
        f.save(dest)

        kind = "pdf" if mime == "application/pdf" else "image"
        record = store.add_file(f.filename, stored_name, mime, size, kind, phone)
        out.append({"id": record["id"], "name": record["name"], "size": record["size"], "kind": record["kind"]})

    return jsonify({"files": out})
