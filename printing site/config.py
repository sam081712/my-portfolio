import os
from dotenv import load_dotenv

load_dotenv()

NODE_ENV = os.environ.get("NODE_ENV", "development")
DEV = NODE_ENV != "production"

# CORS_ORIGIN is always a LIST, never a string — app.py checks "in" directly,
# so we split the comma-separated string into a list right here.
_cors_raw = os.environ.get("CORS_ORIGIN", "*")
CORS_ORIGIN = [s.strip() for s in _cors_raw.split(",") if s.strip()]

PORT = int(os.environ.get("PORT", "4000"))
JWT_SECRET = os.environ.get("JWT_SECRET", "dev_only_insecure_secret_change_me")
OWNER_PASSWORD_HASH = os.environ.get("OWNER_PASSWORD_HASH", "")
OWNER_EMAIL = (os.environ.get("OWNER_EMAIL") or "").strip() or None
SHOP_PHONE = os.environ.get("SHOP_PHONE", "910000000000")
