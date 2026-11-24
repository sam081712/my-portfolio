# PrintCampus Backend (Python / Flask port)

This is a line-for-line port of the Node/Express backend to Python (Flask) — same routes, same request/response shapes, same `index.html` frontend works against it unchanged. OTP has already been removed (see the "2-Step confirmation" flow in `index.html`); student identity is just the phone number (`x-phone` header / `phone` field), and the real confirmation is the WhatsApp message the student sends after paying the advance.

## 1. Setup (5 minutes)

```bash
cd printcampus-backend
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Generate secrets:

```bash
python -c "import secrets; print(secrets.token_hex(48))"   # JWT_SECRET
python scripts/hash_password.py "YourStrongPassword123"     # OWNER_PASSWORD_HASH
```

Paste both into `.env`, then:

```bash
python app.py       # http://localhost:4000
```

Open `http://localhost:4000` — that's `index.html` being served, and it talks to this same backend. Go to the Owner Panel, set your email once (one-time lock), then log in with that email and the password you hashed above.

## 2. API

Identical to the Node version:

| Method | Route | Auth | Purpose |
|---|---|---|---|
| GET | `/api/orders/config` | — | rates, extras, offer, QR URL |
| POST | `/api/orders/quote` | — | live total (server-calculated) |
| POST | `/api/files` | `x-phone` header | PDF/image upload |
| POST | `/api/orders` | phone (body/header) | create order, price from server |
| POST | `/api/orders/:id/payment` | phone (body/header) | submit 50% advance UTR |
| POST | `/api/admin/setup-email` | — | lock the owner email once |
| POST | `/api/admin/login` | — | owner JWT (email + password) |
| GET | `/api/admin/me` | owner JWT | current logged-in owner |
| PUT | `/api/admin/config` | owner JWT | rates / extras / offer / advance % |
| POST | `/api/admin/qr` | owner JWT | upload payment QR |
| GET | `/api/admin/orders` | owner JWT | all orders |
| PATCH | `/api/admin/orders/:id` | owner JWT | status: PLACED / ADVANCE_PAID / PRINTING / READY / DELIVERED |
| GET | `/api/admin/files` | owner JWT | uploaded files (recent / seen) |
| GET | `/api/admin/files/:id` | owner JWT | file preview/download ("View" — opens in a new tab) |

## 3. What changed from the Node version (implementation only — behaviour is identical)

| Node | Python |
|---|---|
| Express | Flask |
| `cors` | `Flask-Cors` |
| `helmet` | hand-rolled security headers in `app.py` (CSP intentionally left off, same as the Node version, so pdf.js from a CDN still loads) |
| `multer` | Flask's built-in `request.files` |
| `bcryptjs` | `bcrypt` |
| `jsonwebtoken` | `PyJWT` |
| `dotenv` | `python-dotenv` |
| `src/store.js` (JSON file) | `store.py` (same JSON file, same shape, same `data/db.json`) |
| `src/routes/*.js` | `routes/*.py` (Flask Blueprints) |
| `npm run hash -- "pwd"` | `python scripts/hash_password.py "pwd"` |

Every validation rule, error message, and the pricing formula (`calc_price` in `store.py`) are a direct port of the JS version — tested end to end (config, quote, login, order creation, payment, admin orders/files, file download, and the wrong-phone security check) before packaging.

## 4. Deploy

Works on Render / Railway / Fly.io / PythonAnywhere:
- Build: `pip install -r requirements.txt`
- Start (production): `gunicorn -w 2 -b 0.0.0.0:$PORT app:app` (install with `pip install gunicorn`; the built-in `python app.py` server is for local development only)
- Put all `.env` values into the platform's Environment section
- Set `NODE_ENV=production` and `CORS_ORIGIN` to your real website domain
- Attach a persistent disk for `data/` and `uploads/`, otherwise data is lost on every restart

## 5. Database upgrade

`store.py` still uses a single JSON file (`data/db.json`) — fine for a college project. To move to Postgres/MongoDB, only the functions inside `store.py` need to change; no route file needs to be touched.
