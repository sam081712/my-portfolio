# index.html ↔ backend contract (Python port)

`index.html` lives in this same folder and is served by the backend itself (`GET /`). The contract below is already implemented inside `index.html` — nothing needs to change there, since this Python backend was built to match the exact same request/response shapes as the Node version it replaces.

```js
const API = "http://localhost:4000/api";   // your domain after deploy
let studentPhone = null;                   // "91xxxxxxxxxx" — this is the student's identity (no OTP)
```

### 1. Rates from the server

```js
const c = await fetch(`${API}/orders/config`).then(r => r.json());
rates = c.rates; extras = c.extras; shop = c.shop;
```

### 2. Total from the server (the browser only shows a preview)

```js
const p = await fetch(`${API}/orders/quote`, {
  method: "POST", headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ pdfPages, images, copies, printType, sides, paper, layout, binding, range, extras })
}).then(r => r.json());
```

### 3. Files + order + payment

```js
studentPhone = "91" + phone;

const fd = new FormData();
selectedFiles.forEach(f => fd.append("files", f));
const up = await fetch(`${API}/files`, {
  method: "POST", headers: { "x-phone": studentPhone }, body: fd
}).then(r => r.json());

const res = await fetch(`${API}/orders`, {
  method: "POST", headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ phone: studentPhone, name, files: up.files, ...jobOptions })
}).then(r => r.json());
order = res.order;

await fetch(`${API}/orders/${order.id}/payment`, {
  method: "POST", headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ phone: studentPhone, utr })
});
```

Order confirmation shows a `wa.me` link the student taps to send the order to the shop on WhatsApp — this is the real confirmation now, the server doesn't send any WhatsApp message itself.

### 4. Owner panel

```js
const r = await fetch(`${API}/admin/login`, {
  method: "POST", headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ email, password })
}).then(r => r.json());
sessionStorage.setItem("pc_owner_token", r.token);

await fetch(`${API}/admin/config`, {
  method: "PUT",
  headers: { "Content-Type": "application/json", Authorization: "Bearer " + token },
  body: JSON.stringify({ rates, extras, shop })
});
```

### 5. Uploaded files preview ("View")

Opens a new tab with the browser's own PDF/image viewer (no custom iframe/modal):

```js
const win = window.open("", "_blank");   // opened synchronously inside the click, before any await
const res = await fetch(`${API}/admin/files/${id}`, { headers: authHeader() });
const blob = await res.blob();
win.location.href = URL.createObjectURL(blob);
```

---

**Remember:** hiding the owner panel's HTML is not security — the real guard is the `require_owner` decorator in `routes/admin.py`, which checks the JWT on every admin request. The frontend only hides the UI.
