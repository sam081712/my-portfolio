"""
A very simple JSON-file database — plenty for a college project.
To move to Firestore/MongoDB, just change the functions inside this
one file — no other file (routes) needs to be touched. (See README.md for an example.)
"""
import json
import random
import string
import threading
import time
import datetime
from pathlib import Path

import config as C

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DB_FILE = DATA_DIR / "db.json"
UPLOAD_DIR = BASE_DIR / "uploads"

_lock = threading.Lock()

DEFAULT_RATES = {
    "bwSingle": 1, "bwDouble": 1.6,
    "colorSingle": 5, "colorDouble": 9,
    "a3Extra": 2, "photo": 10,
    "staple": 5, "spiral": 30,
    "minOrder": 5,
}


class OwnerEmailAlreadySet(Exception):
    status = 409

    def __str__(self):
        return "Owner email is already set — this can only be done once."


def _fresh_db():
    return {
        "owner": {"email": C.OWNER_EMAIL},
        "config": {
            "rates": dict(DEFAULT_RATES),
            "extras": [],
            "shop": {
                "discountOn": False,
                "discountPct": 0,
                "discountText": "Limited time offer",
                "upi": "",
                "advancePct": 50,
                "qrUrl": None,
            },
        },
        "orders": {},
        "files": {},
    }


def _ensure_dirs():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def _write(db):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2)


def _load():
    _ensure_dirs()
    if not DB_FILE.exists():
        db = _fresh_db()
        _write(db)
        return db
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            db = json.load(f)
        # older db files may be missing newer keys (upgrade safety)
        fresh = _fresh_db()
        db.setdefault("owner", fresh["owner"])
        db.setdefault("config", fresh["config"])
        db["config"].setdefault("rates", dict(DEFAULT_RATES))
        db["config"].setdefault("extras", [])
        db["config"].setdefault("shop", fresh["config"]["shop"])
        db.setdefault("orders", {})
        db.setdefault("files", {})
        return db
    except Exception as e:
        print("data/db.json was corrupt, creating a fresh db:", e)
        db = _fresh_db()
        _write(db)
        return db


def _new_id(prefix):
    rand = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
    return f"{prefix}{int(time.time() * 1000):x}{rand}"


def _round2(n):
    return round((float(n or 0)) * 100) / 100


def _now_iso():
    return datetime.datetime.utcnow().isoformat() + "Z"


# ---------------- pricing ----------------

def count_pages_in_range(range_str, total_pages):
    """Converts a range string like "1-3,5,7-8" into an actual page count.
    Empty or "all" -> every page. If it can't be parsed, the safe default is: every page."""
    total = max(0, int(total_pages or 0))
    if not total:
        return 0
    r = (range_str or "").strip()
    if not r or r.lower() == "all":
        return total

    pages = set()
    for part in r.split(","):
        p = part.strip()
        if not p:
            continue
        if "-" in p:
            bits = p.split("-")
            if len(bits) == 2 and bits[0].strip().isdigit() and bits[1].strip().isdigit():
                a, b = int(bits[0]), int(bits[1])
                if a > b:
                    a, b = b, a
                for i in range(a, b + 1):
                    if 1 <= i <= total:
                        pages.add(i)
        elif p.isdigit():
            n = int(p)
            if 1 <= n <= total:
                pages.add(n)
    return len(pages) or total


def calc_price(job, config):
    rates = config.get("rates") or {}
    extras_list = config.get("extras") or []
    shop = config.get("shop") or {}

    total_pdf_pages = max(0, int(job.get("pdfPages") or 0))
    images = max(0, int(job.get("images") or 0))
    copies = max(1, int(job.get("copies") or 1))
    layout = max(1, int(job.get("layout") or 1))
    sides = "double" if job.get("sides") == "double" else "single"
    print_type = "color" if job.get("printType") == "color" else "bw"
    paper = "a3" if job.get("paper") == "a3" else "a4"
    binding = job.get("binding") or "none"

    doc_pages = count_pages_in_range(job.get("range"), total_pdf_pages)
    slots_per_sheet = layout * (2 if sides == "double" else 1)
    sheets = -(-doc_pages // slots_per_sheet) if doc_pages > 0 else 0  # ceil division

    rate_key = (
        ("colorDouble" if sides == "double" else "colorSingle")
        if print_type == "color"
        else ("bwDouble" if sides == "double" else "bwSingle")
    )
    per_sheet_rate = float(rates.get(rate_key) or 0)

    printing = sheets * copies * per_sheet_rate
    if paper == "a3":
        printing += doc_pages * copies * float(rates.get("a3Extra") or 0)
    printing += images * copies * float(rates.get("photo") or 0)

    addons = 0.0
    if binding == "staple":
        addons += copies * float(rates.get("staple") or 0)
    if binding == "spiral":
        addons += copies * float(rates.get("spiral") or 0)

    chosen_extra_names = job.get("extras") or []
    if isinstance(chosen_extra_names, list):
        for name in chosen_extra_names:
            ex = next((e for e in extras_list if e.get("name") == name), None)
            if ex:
                addons += float(ex.get("price") or 0)

    subtotal = printing + addons
    min_order = float(rates.get("minOrder") or 0)
    if 0 < subtotal < min_order:
        subtotal = min_order

    discount_pct = (
        float(shop.get("discountPct") or 0)
        if shop.get("discountOn") and float(shop.get("discountPct") or 0) > 0
        else 0
    )
    discount = subtotal * discount_pct / 100
    total = max(0, subtotal - discount)
    advance_pct = float(shop.get("advancePct") or 50)
    advance = _round2(total * advance_pct / 100)
    balance = _round2(total - advance)

    return {
        "docPages": doc_pages,
        "images": images,
        "sheets": sheets,
        "copies": copies,
        "printing": _round2(printing),
        "addons": _round2(addons),
        "discount": _round2(discount),
        "discountPct": discount_pct,
        "total": _round2(total),
        "advance": advance,
        "balance": balance,
    }


# ---------------- public API ----------------

class Store:
    UPLOAD_DIR = str(UPLOAD_DIR)

    def get_config(self):
        with _lock:
            return _load()["config"]

    def update_config(self, patch):
        with _lock:
            db = _load()
            if patch.get("rates"):
                db["config"]["rates"].update(patch["rates"])
            if patch.get("extras") is not None:
                db["config"]["extras"] = patch["extras"]
            if patch.get("shop"):
                db["config"]["shop"].update(patch["shop"])
            _write(db)
            return db["config"]

    def set_qr_url(self, qr_url):
        with _lock:
            db = _load()
            db["config"]["shop"]["qrUrl"] = qr_url
            _write(db)
            return db["config"]

    def quote(self, job):
        with _lock:
            db = _load()
            return calc_price(job, db["config"])

    def create_order(self, phone, name, notes, files, job):
        with _lock:
            db = _load()
            price = calc_price(job, db["config"])
            oid = _new_id("PC")
            order = {
                "id": oid,
                "phone": phone,
                "name": name,
                "notes": notes or "",
                "files": files or [],
                "job": job,
                "price": price,
                "payment": {"paid": 0, "utr": None, "paidAt": None},
                "status": "PLACED",
                "createdAt": _now_iso(),
            }
            db["orders"][oid] = order
            # link these files to the order so they show up in the owner panel
            for f in (files or []):
                if f["id"] in db["files"]:
                    db["files"][f["id"]]["order"] = {"orderId": oid}
            _write(db)
            return order

    def get_order(self, order_id):
        with _lock:
            return _load()["orders"].get(order_id)

    def record_payment(self, order_id, utr):
        with _lock:
            db = _load()
            order = db["orders"].get(order_id)
            if not order:
                return None
            order["payment"]["utr"] = utr
            order["payment"]["paid"] = order["price"]["advance"]
            order["payment"]["paidAt"] = _now_iso()
            order["status"] = "ADVANCE_PAID"
            _write(db)
            return order

    def set_order_status(self, order_id, status):
        with _lock:
            db = _load()
            order = db["orders"].get(order_id)
            if not order:
                return None
            order["status"] = status
            _write(db)
            return order

    def list_orders(self):
        with _lock:
            orders = list(_load()["orders"].values())
        return sorted(orders, key=lambda o: o["createdAt"], reverse=True)

    def add_file(self, original_name, stored_name, mime, size, kind, phone):
        with _lock:
            db = _load()
            fid = _new_id("F")
            record = {
                "id": fid,
                "name": original_name,
                "storedName": stored_name,
                "mime": mime,
                "size": size,
                "kind": kind,
                "phone": phone,
                "order": None,
                "seen": False,
                "uploadedAt": _now_iso(),
            }
            db["files"][fid] = record
            _write(db)
            return record

    def get_file(self, file_id):
        with _lock:
            return _load()["files"].get(file_id)

    def mark_file_seen(self, file_id):
        with _lock:
            db = _load()
            if file_id in db["files"]:
                db["files"][file_id]["seen"] = True
                _write(db)

    def list_files(self):
        with _lock:
            files = list(_load()["files"].values())
        files.sort(key=lambda f: f["uploadedAt"], reverse=True)
        recent = [f for f in files if not f["seen"]]
        seen = [f for f in files if f["seen"]]
        return recent, seen

    # ---------------- owner ----------------

    def owner_status(self):
        with _lock:
            db = _load()
        return {"emailSet": bool(db["owner"]["email"]), "email": db["owner"]["email"]}

    def set_owner_email(self, email):
        with _lock:
            db = _load()
            if db["owner"]["email"]:
                raise OwnerEmailAlreadySet()
            db["owner"]["email"] = email
            _write(db)
            return db["owner"]["email"]


store = Store()
