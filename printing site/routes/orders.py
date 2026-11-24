import re
from flask import Blueprint, request, jsonify
from store import store

bp = Blueprint("orders", __name__)

# Checks the phone format — this is now the student's identity, in place of verifyToken/OTP.
# 91 + 10-digit Indian mobile number.
PHONE_RE = re.compile(r"^91[6-9]\d{9}$")
UTR_RE = re.compile(r"^[A-Za-z0-9]{8,24}$")


def is_valid_phone(phone):
    return bool(phone) and bool(PHONE_RE.match(str(phone)))


# GET /api/orders/config — rates, extras, shop settings (public, no auth required)
@bp.get("/config")
def get_config():
    return jsonify(store.get_config())


# POST /api/orders/quote — live price preview (the server does the calculation)
@bp.post("/quote")
def quote():
    body = request.get_json(silent=True) or {}
    return jsonify(store.quote(body))


# POST /api/orders — create a new order. Phone comes from the header (x-phone) or body.phone.
@bp.route("", methods=["POST"])
def create_order():
    body = request.get_json(silent=True) or {}
    phone = body.get("phone") or request.headers.get("x-phone")
    if not is_valid_phone(phone):
        return jsonify({"error": "A valid WhatsApp number was not provided."}), 400

    name = str(body.get("name") or "").strip()
    if len(name) < 2:
        return jsonify({"error": "Name is required."}), 400

    files = body.get("files")
    if not isinstance(files, list) or not files:
        return jsonify({"error": "At least one file is required."}), 400

    # make sure the files were genuinely uploaded by this phone, so no one can use someone else's file id
    for f in files:
        rec = store.get_file(f.get("id"))
        if not rec or rec.get("phone") != phone:
            return jsonify({"error": "File couldn't be verified — please upload again."}), 400

    job = {
        "pdfPages": body.get("pdfPages"),
        "images": body.get("images"),
        "copies": body.get("copies"),
        "printType": body.get("printType"),
        "sides": body.get("sides"),
        "paper": body.get("paper"),
        "layout": body.get("layout"),
        "binding": body.get("binding"),
        "range": body.get("range"),
        "extras": body.get("extras"),
    }

    order = store.create_order(
        phone=phone,
        name=name,
        notes=body.get("notes"),
        files=[{"id": f["id"], "name": f.get("name"), "size": f.get("size"), "kind": f.get("kind")} for f in files],
        job=job,
    )

    return jsonify({"order": order})


# POST /api/orders/:id/payment — submit the 50% advance UTR to confirm the order.
@bp.post("/<order_id>/payment")
def pay_order(order_id):
    order = store.get_order(order_id)
    if not order:
        return jsonify({"error": "Order not found."}), 404

    body = request.get_json(silent=True) or {}
    phone = body.get("phone") or request.headers.get("x-phone")
    if order["phone"] != phone:
        return jsonify({"error": "This order does not belong to you."}), 403

    utr = str(body.get("utr") or "").strip()
    if not UTR_RE.match(utr):
        return jsonify({"error": "A valid UTR/Transaction ID is required."}), 400

    updated = store.record_payment(order_id, utr)
    return jsonify({"order": updated})
