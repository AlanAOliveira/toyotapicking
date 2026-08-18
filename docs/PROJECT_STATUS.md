Here's the full replacement for `docs/PROJECT_STATUS.md`.

```markdown
# 📦 Toyota Picking — Project Status

> Live tracking document for the Toyota Picking system.
> **Last updated:** 2026-08-21
> **Owner:** Alan Aves
> **Platform target:** Samsung Galaxy Tab Active5 (8" — 1920×1200, landscape)
> **Deployment target:** Databricks Apps (Azure)

---

## 🎯 Project Goal

Build a touch-friendly picking interface for warehouse operators to:
- View picking lists in real time (sorted by warehouse address, filtered by order + route + dolly)
- Scan QR-coded boxes to mark kanbans as picked
- Track box/order progress
- Call supervisor support
- Advance through carts/routes

The app must run reliably on rugged 8" Android tablets in a warehouse environment.

---

## 🗂️ Current Project Structure

```text
toyotapicking/
├── app.py                          # Flask factory + entrypoint (+ VERSION for cache-busting)
├── config.py                       # Config classes
├── app.yaml                        # Databricks Apps deployment (PAT + warehouse ID)
├── manifest.yaml                   # Databricks Apps manifest
├── requirements.txt
│
├── database/                       # ✅ Data access layer
│   ├── __init__.py                 # 🔴 empty
│   ├── databricks_conn.py          # ✅ SQL connection via PAT
│   ├── iek_repository.py           # ✅ eKanban pick-list + route/dolly + P/F flag resolution
│   ├── lakebase_conn.py            # ✅ Postgres pool w/ OAuth token minting
│   ├── lakebase_schema.py          # ✅ picking_status + picking_scans schema init
│   ├── parts_repository.py         # 🔴 empty (planned: box_per_kanban resolution)
│   ├── picking_status_repository.py # ✅ record_scan / mark_kse / status reads
│   └── sql/
│       └── picking_status.sql      # ✅ Migration reference (matches lakebase_schema.py)
│
├── docs/
│   ├── DATA_STANDARDS.md           # ✅ §1 Part Number, §2 Scanner (v2), §3 Address, §9 Status — locked
│   └── PROJECT_STATUS.md           # ← this file
│
├── models/
│   ├── __init__.py                 # 🔴 empty
│   ├── picking_item.py             # ✅ dataclass defined (unused)
│   └── operator.py                 # 🔴 empty
│
├── routes/
│   ├── __init__.py                 # 🔴 empty
│   ├── main.py                     # ✅ / (GET landing)
│   ├── picking.py                  # ✅ /picking/<order>?route=X&dolly=Y&flag=F
│   └── api.py                      # ✅ selectors + scan/KSE/call + diagnostics
│
├── services/
│   ├── __init__.py                 # 🔴 empty
│   ├── picking_service.py          # ✅ threads route/dolly/flag through repo layer
│   ├── scanner_service.py          # ✅ §2 QR parser (separator-tolerant since 2026-08-21)
│   ├── databricks_client.py        # 🔴 DEAD CODE — schedule deletion
│   └── operator_service.py         # 🔴 empty
│
├── static/
│   ├── css/
│   │   ├── base.css                # 🔴 empty
│   │   └── picking.css             # 🔴 empty (CSS still inline in picking.html + index.html)
│   ├── img/                        # 🔴 empty
│   └── js/
│       ├── common.js               # 🔴 empty
│       └── picking.js              # ✅ modal + scan + camera + optimistic UI
│
├── templates/
│   ├── base.html                   # ✅ Bootstrap 5.3
│   ├── main/
│   │   └── index.html              # ✅ Cascading selector: order → route → dolly (CSS+JS inlined)
│   ├── picking/
│   │   └── picking.html            # ✅ Picking screen + status modal (CSS inlined)
│   └── components/
│       ├── clock.html              # 🔴 empty
│       └── info_card.html          # 🔴 empty
│
└── tests/
    ├── __init__.py                 # 🔴 empty
    ├── test_picking.py             # 🔴 empty
    └── test_services.py            # 🔴 empty
```

---

## 🚦 Overall Status

| Area                        | Status         | Notes                                                                    |
|-----------------------------|----------------|--------------------------------------------------------------------------|
| Data standards (docs)       | 🟡 In progress | §1, §2, §3, §9 ✅ locked. §4–§8 🔴 TBD.                                  |
| Frontend layout             | 🟢 Done        | Fits 8" tablet, responsive `clamp()`, empty-state handled                |
| Live clock                  | 🟢 Done        | Updates every 1s, BR timezone                                            |
| Databricks connection       | 🟢 Done        | PAT via `DATABRICKS_TOKEN` in `app.yaml`                                 |
| eKanban data access         | 🟢 Done        | `iek_repository` — TRIM, LENGTH filter, P/F flag resolution              |
| Lakebase connection         | 🟢 Done        | Postgres pool + per-conn OAuth token minting                             |
| Lakebase schema init        | 🟢 Done        | Auto-created at startup, idempotent                                      |
| Service ↔ Repo wiring       | 🟢 Done        | `picking_service` threads route/dolly/flag through                       |
| Order selection UI          | 🟢 Done        | Cascading selector (order → route → dolly) with P/F flag badge           |
| P/F flag resolution         | 🟢 Done        | F preferred, P fallback per-order; badge on picking screen               |
| Diagnostics                 | 🟢 Done        | `/api/health`, `/api/health/lakebase`, `/api/health/lakebase/tables`, `/api/debug/env` |
| Backend routes              | 🟢 Done        | main + picking + api all wired                                           |
| **End-to-end pick list**    | 🟢 **Done**    | Real order → real rows, filtered by route + dolly ✅                     |
| Scan flow (modal → API)     | 🟢 Done        | Modal + text input + camera + optimistic UI + rollback on error          |
| Scanner input parsing       | 🟢 Done        | §2 locked; separator-tolerant (accepts `\|`, `}`, `{`, space, etc.)      |
| Scan → Lakebase writes      | 🟢 Done        | `picking_status` + `picking_scans` updates, duplicate detection          |
| KSE flow                    | 🟢 Done        | Marks kanban KSE, logs supervisor notification, computes parts_lacking   |
| Global "Chamar" button      | 🟢 Done        | Hits `/api/chamar`, logs supervisor notification                          |
| Per-kanban "Chamar" button  | 🟢 Done        | Hits `/api/picking/…/call`, logs notification                            |
| "Próximo carrinho" button   | 🔴 Stub        | Returns fake `{"next_cart": "D02"}`, no real logic                       |
| Supervisor notifications    | 🟡 Log-only    | API contract stable; actual channel (Teams/DB) deferred                  |
| Multi-box kanbans           | 🔴 Broken      | `boxes_required` hardcoded to 1; can't complete multi-unit kanbans. See P1. |
| Authentication              | 🔴 Deferred    | Using PAT for now; operator identity not tracked                         |
| CSS externalization         | 🔴 Not started | CSS inline in `picking.html` AND `index.html`; `.css` files empty        |
| Auto-refresh                | 🔴 Not started | Page is static after load                                                |
| Deployment                  | 🟢 Done        | Databricks Apps on Azure, `app.yaml` env vars verified via `/api/debug/env` |
| Tablet testing              | 🔴 Not started | Need physical device test                                                |
| Tests                       | 🔴 Not started | All test files empty                                                     |

Legend: 🟢 Done · 🟡 In progress · 🔴 Not started · ⚪ Backlog

---

## 🔥 Immediate Next Steps (P0 — this week)

1. **Delete `services/databricks_client.py`** — dead code, redundant with `database/databricks_conn.py`.
2. **Populate the `Operador` card** — pull from `X-Forwarded-Email` header (already available in Databricks Apps) and pass through to the template. Replaces hardcoded `TKLpicker`.
3. **Test on the actual Galaxy Tab Active5** — layout assumptions and camera/scanner behavior are unverified on real hardware.

---

## 📋 Backlog — Priority Order

### 🟠 P1 — Important

- [ ] **Multi-box kanbans — `boxes_required` must reflect real box count.**
  Some parts (e.g. `PIPE ASSY FUEL TANK FILLER`) are shipped one unit per
  physical box, so a single row in `ekanban_orders` with
  `box_part_quantity = 3` actually represents **3 physical boxes**, all
  labeled with the same `kanban_number`. Current app hardcodes
  `boxes_required = 1`, so after the first scan the row flips to `OK` and
  the 2nd/3rd scans get rejected with HTTP 400 "Kanban já completo".

  **Unknown before implementing:**
  - Whether `box_part_quantity` maps directly to box count, or whether a
    per-part `lote_size` divisor is required (screws example:
    `box_part_quantity = 2000` for 1 box).
  - Whether all N physical boxes carry the same QR (same `label_seq`) or
    different QRs. If same-QR, `picking_scans` PK
    `(order, kanban, label_seq)` blocks the 2nd scan and needs redesign.
  - Where the "N boxes per kanban" info actually lives — eKanban column,
    Lakebase parts table, or somewhere else entirely.

  **Design decisions deferred until data source is confirmed.**
  Reference: field test 2026081709 / route A / dolly 3 — expected 5
  physical boxes to scan, list shows 2 rows.

- [ ] **Modal auto-close delay after scan feels slow.**
  Current: on a successful "Kanban completo!" scan, `onScan` in
  `picking.js` waits 800ms before closing the modal (via `setTimeout`).
  The row underneath is *already* green (optimistic update fires before
  the POST), but the operator can't see it because the modal is still on
  top. On a fast picking floor this reads as sluggish.

  **Candidate fixes (need to pick one):**
  - Reduce timeout from 800ms → 200–300ms.
  - Close modal immediately, rely on toast for confirmation.
  - Keep 800ms but make modal semi-transparent so the row shows through.

- [ ] Populate `Back` column from real source (currently `—` fallback). Source unknown.
- [ ] Extract inline CSS from `picking.html` → `static/css/picking.css`.
- [ ] Extract inline CSS + JS from `index.html` → `static/css/index.css` + `static/js/index.js`.
- [ ] Auto-refresh pick list (polling every N seconds, or SSE).
- [ ] Loading indicators + inline error states.
- [ ] Confirmation dialogs for `Exit` / `Próximo carrinho`.
- [ ] Fill out `DATA_STANDARDS.md` §4 Order, §5 Operator, §6 Dolly, §7 Lane, §8 Dates.
- [ ] Add `{% block scripts %}` to `base.html` and un-nest it from `content` in `picking.html`.
- [ ] Rotate PAT and move `DATABRICKS_TOKEN` from `app.yaml` plaintext → Databricks secret scope.

### 🟡 P2 — Nice to Have

- [ ] Real supervisor notifications (replace log-only shims in `picking_service.py`). Channel TBD: Teams webhook? Slack? DB table for supervisor dashboard?
- [ ] Wire "Próximo carrinho" button to real advance-cart logic.
- [ ] Auto-hide finished routes/dollies in the landing selector.
- [ ] Sound/vibration feedback on scan / status change.
- [ ] PWA manifest for install-as-app on tablet.
- [ ] Offline / poor-Wi-Fi handling.
- [ ] Multi-language (PT / EN / JP).
- [ ] Basic unit tests in `tests/` — start with `scanner_service.parse_scan_payload` (§2 has ready-made test cases).
- [ ] Delete empty `components/*.html` templates (or fill them).
- [ ] Optimize `_find_kanban_row` in `routes/api.py` — currently fetches whole order to verify one kanban.

### ⚪ Backlog

- [ ] Admin panel for supervisors.
- [ ] Historical reporting.
- [ ] WMS integration.
- [ ] Switch from PAT → OBO or Service Principal auth.
- [ ] Status-history table (every transition, not just current state) — see `DATA_STANDARDS.md` §9.11.

---

## 🐛 Known Issues / Risks

| #  | Issue                                                             | Severity | Notes                                                     |
|----|-------------------------------------------------------------------|----------|-----------------------------------------------------------|
| 1  | `services/databricks_client.py` is dead code                      | Low      | Delete when convenient                                    |
| 2  | No operator identity                                              | Medium   | `Operador` card always shows `TKLpicker`; header `X-Forwarded-Email` available but unused |
| 3  | Tablet not yet tested physically                                  | Medium   | Layout + camera + scanner behavior unverified             |
| 4  | PAT stored in plaintext in `app.yaml`                             | Medium   | Works, but should move to secret scope for production     |
| 5  | `Back` column value is a placeholder (`—`)                        | Low      | Source of truth undefined                                 |
| 6  | CSS inline in templates                                            | Low      | `picking.html` and `index.html` both inline; empty `.css` files exist unused |
| 7  | Empty `components/` templates                                     | Low      | Delete or fill                                            |
| 8  | `{% block scripts %}` nested inside `{% block content %}`         | Low      | Works, but sloppy — `base.html` has no `scripts` block    |
| 9  | "Próximo carrinho" is a stub                                       | Low      | Frontend shows a toast; backend returns fake data         |
| 10 | Supervisor notifications are log-only                              | Medium   | API contract stable; production needs a real channel      |
| 11 | Multi-box kanbans can't be completed                              | **High** | `boxes_required` hardcoded to 1. Blocks any PN where one row = N physical boxes. See P1 backlog. |
| 12 | Modal auto-close delay reads as slow after scan                    | Low      | 800ms setTimeout in `onScan`. See P1 backlog.             |
| 13 | Same-`label_seq` scans across kanbans are permitted by design      | Low      | Intentional per §2.6 / §9.4; note here in case it surprises during audit |

---

## 🧪 Testing Checklist

### Visual / UX
- [ ] Renders correctly on Galaxy Tab Active5 (landscape)
- [ ] All buttons reachable with thumb in landscape grip
- [ ] Readable from ~50cm under warehouse lighting
- [ ] Works with gloves

### Functional
- [x] Clock updates every second without drift
- [x] Status colors render correctly for each row state
- [x] Long part numbers wrap without breaking layout
- [x] Empty pick list handled gracefully
- [x] Invalid order number surfaces a clean error message
- [x] Databricks connection errors surface a clean message
- [x] `/api/health` returns green in production
- [x] `/api/health/lakebase` returns green in production
- [x] Real order fetches real rows end-to-end
- [x] Cascading selector (order → route → dolly) works end-to-end
- [x] `(Sem rota)` special-items path works
- [x] P flag badge appears on picking screen when order is provisional
- [x] Scan modal opens on row tap
- [x] Text-input scan flow works (canonical `|` separator)
- [x] Text-input scan flow works (tolerant `}` / `{` / space separator)
- [x] Camera-scan flow works on tablet with BarcodeDetector
- [x] Successful scan updates picking_status in Lakebase
- [x] Duplicate scan (same label_seq, same kanban) is rejected
- [x] Wrong-part scan is rejected client-side + server-side
- [x] KSE button marks kanban KSE and logs notification
- [x] Global "Chamar" button hits `/api/chamar`
- [ ] Multi-box kanban (e.g. `PIPE ASSY` with qtd=3) can be completed (BLOCKED — see P1)

### Performance
- [ ] Initial page load < 2s on tablet
- [ ] Smooth scrolling / interaction (60fps target)
- [ ] No memory leaks during 8h+ shifts

---

## 🛠️ Tech Stack

- **Backend:** Python 3 + Flask 3
- **Frontend:** Jinja2 templates, vanilla JS, custom CSS + Bootstrap 5.3
- **Data (read):** Databricks SQL Warehouse via `databricks-sql-connector`, PAT auth
- **Data (write):** Lakebase Postgres via `psycopg` + connection pool with OAuth token minting
- **Auth (current):** PAT in `DATABRICKS_TOKEN` env var; service principal for Lakebase (auto-injected)
- **Deployment:** Databricks Apps (Azure)
- **Target device:** Samsung Galaxy Tab Active5 (Android)
- **Browser:** Chrome (Android WebView)
- **QR scanning:** BarcodeDetector API (native browser) or external hardware scanner (keyboard emulation)

---

## 📝 Decision Log

| Date       | Decision                                                              | Reason                                                       |
|------------|-----------------------------------------------------------------------|--------------------------------------------------------------|
| 2026-05-19 | Use vanilla JS, no framework                                          | Keep lightweight for tablet                                  |
| 2026-06-03 | Use `clamp()` for fonts                                               | One layout for tablet + dev machine                          |
| 2026-06-03 | Lock viewport, disable zoom                                           | Prevent accidental zoom in warehouse                         |
| 2026-06-03 | Separate JS into `static/js/picking.js`                               | Cleaner templates, better caching                            |
| 2026-06-03 | Use `databricks-sql-connector` + OAuth via SDK                        | Works with Databricks Apps auth                              |
| 2026-06-05 | Lock Part Number canonical format (§1 in `DATA_STANDARDS.md`)         | Prevent input ambiguity                                      |
| 2026-06-05 | Lock Address canonical format (§3 in `DATA_STANDARDS.md`)             | Enables consistent sorting                                   |
| 2026-06-09 | Move DB code into `database/` package                                 | Group repositories + connection helpers together             |
| 2026-07-14 | Landing page uses `order_number` form input; route is `/picking/<n>`  | Simplest possible operator entry point                       |
| 2026-07-15 | Use explicit PAT via `DATABRICKS_TOKEN` env var                       | Simplest auth path; unblocks development                     |
| 2026-07-15 | `TRIM(order_number)` in WHERE clause                                  | Source column is CHAR-padded; equality without TRIM returns zero rows |
| 2026-07-15 | Two-table Lakebase design: `picking_status` + `picking_scans`         | Cached counter + audit log; PK on scans prevents dup scans   |
| 2026-07-15 | Optimistic UI on scan/KSE with rollback on error                       | Perceived latency matters more than strict consistency       |
| 2026-08-13 | `app.yaml` schema fixed — plain `env:` entries with quoted names       | Old `valueFrom: database` syntax was silently dropping the entire env block |
| 2026-08-20 | Landing page redesigned as cascading selector (order → route → dolly)  | Supervisor assigns picker to a specific (order, route, dolly) triple |
| 2026-08-20 | P/F flag resolution — F preferred, P fallback per-order                | Handles transition from provisional → fixed without mixing rows |
| 2026-08-20 | Effective flag threaded through URL as `?flag=F` / `?flag=P`           | Stateless; picking screen can be bookmarked; skips one probe query |
| 2026-08-20 | Small "P" badge on picking screen when order is provisional            | Operator needs to know they're working provisional data      |
| 2026-08-21 | Scanner regex loosened to accept any non-alphanumeric separator (§2)   | ABNT keyboard layouts mis-map `\|` (0x7C) → `}` (0x7D); field workaround |

---

## 📞 Open Questions

- [ ] How does the operator select their assigned order? **Answered 2026-08-20**: manual textbox; supervisor tells them the number. Long-term: badge scan / auto-assign from route table.
- [ ] How often should pick list refresh? (Polling interval — 5s? 30s?)
- [ ] Does the tablet have a built-in barcode scanner or external?
- [ ] Portrait or landscape only? (Assumed landscape for now)
- [ ] What happens if Wi-Fi drops mid-pick?
- [ ] Where does the `Back` column value come from? Currently `—` fallback.
- [ ] Where does "N physical boxes per kanban" info live? Needed to unblock P1 multi-box-kanban work. Candidates: (a) a `lote_size` column on eKanban we haven't queried yet, (b) a parts master table in Lakebase, (c) somewhere else entirely.
- [ ] Do multi-box kanbans print one QR per box (different `label_seq`) or share a QR across all N boxes? Affects `picking_scans` PK design.
- [ ] Notification channel for supervisor events (KSE / operator call / order call) — Teams webhook? DB table for a supervisor dashboard? Email?
