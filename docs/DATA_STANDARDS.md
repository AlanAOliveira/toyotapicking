# 📐 Data Standards — Toyota Picking

> Canonical reference for all data formats used in the Toyota Picking system.
> **Owner:** Alan Aves
> **Last updated:** 2026-08-21
> **Status:** Living document — update as new fields are defined.

---

## Table of Contents

1. [General Principles](#general-principles)
2. [Part Number](#1-part-number) — ✅ LOCKED
3. [Scanner Input Parsing](#2-scanner-input-parsing) — ✅ LOCKED
4. [Address / Location](#3-address--location) — ✅ LOCKED
5. [Order / Pedido](#4-order--pedido) — 🔴 TBD
6. [Operator](#5-operator) — 🔴 TBD
7. [Dolly / Cart](#6-dolly--cart) — 🔴 TBD
8. [Lane / Route](#7-lane--route) — 🔴 TBD
9. [Dates & Times](#8-dates--times) — 🔴 TBD
10. [Picking Status](#9-picking-status) — ✅ LOCKED

---

## General Principles

These rules apply to **every** data type in the system unless explicitly overridden.

| Principle | Rule |
|---|---|
| **Normalize at the edge** | Inbound data is normalized to canonical form immediately. Internal code never handles raw/ambiguous input. |
| **Canonical storage** | Database, cache, and session always hold canonical form. |
| **Canonical output** | API responses, logs, and UI all display canonical form. |
| **Case** | Uppercase for all identifiers (part numbers, addresses, codes). |
| **Encoding** | ASCII only for identifiers — no accents, no Unicode. UTF-8 for free-text fields. |
| **Validation** | Every field has a regex + a normalization function. Both must be enforced server-side. |
| **Errors** | Reject invalid input with a clear error. Never silently coerce malformed data. |
| **Logs** | Always log canonical form. Never log raw user input verbatim. |

---

## 1. Part Number

> **Status:** ✅ LOCKED — 2026-06-05

### 1.1 Definition

A **Part Number** is the unique identifier of a physical part. Every part number is treated as a **unique, exclusive item** — variants of the same base part with different colors are **distinct items** and are **never grouped** in the system.

### 1.2 Canonical Format

```
XXXXX-XXXXX-XX   (14 characters)
```

- 5 alphanumeric + `-` + 5 alphanumeric + `-` + 2 alphanumeric
- Character set: `[A-Z0-9]` (uppercase only)
- Letters and digits may appear at any position
- Total length: **14 characters** (12 alphanumeric + 2 hyphens)

### 1.3 Structure

A part number has **two semantic segments**:

| Segment | Length | Meaning |
|---|---|---|
| **Base** | 10 alphanumeric | Unique identifier of the physical part |
| **Suffix** | 2 alphanumeric | Color / variant code |

The base is displayed as two groups of 5 characters separated by a hyphen (`XXXXX-XXXXX`) **purely as a reading aid** — the two halves carry no independent meaning. The base is a single opaque 10-character code.

```
XXXXX-XXXXX-XX
└─────┬─────┘ └┬┘
   Base (10)  Suffix (2)
```

### 1.4 Suffix Rules

| Suffix | Meaning |
|---|---|
| `00` | Generic — part has no color variant |
| Any other `[A-Z0-9]{2}` | Specific color / variant (e.g. `B0`, `C1`, `AA`, `1A`) |

### 1.5 Accepted Input Forms

The system accepts these forms from external sources and normalizes to canonical:

| Form | Length | Example | Normalization |
|---|---|---|---|
| Canonical | 14 | `99999-CCCCC-B0` | (no change) |
| No hyphens | 12 | `99999CCCCCB0` | Insert hyphens at positions 5 and 10 |
| Base only (suffix `00` implied) | 10 | `99999CCCCC` | Append `-00`, insert hyphens |
| Base with hyphen, no suffix | 11 | `99999-CCCCC` | Append `-00` |

> **Note:** A 10- or 11-char input is **only valid if the part is generic** (suffix `00`). Colored variants must be specified explicitly in 12- or 14-char form.

### 1.6 Scanner Input

Barcode scans contain the part number plus additional data (a label sequence). Full parsing rules are defined in **§2 Scanner Input Parsing**. The part number is extracted from the scan payload, then validated against the canonical regex in this section.

### 1.7 Validation

**Canonical regex (storage / API):**

```
^[A-Z0-9]{5}-[A-Z0-9]{5}-[A-Z0-9]{2}$
```

**Input regex (accepts all 4 forms):**

```
^[A-Z0-9]{5}-?[A-Z0-9]{5}(-?[A-Z0-9]{2})?$
```

### 1.8 Sorting & Grouping

| Rule | Decision |
|---|---|
| **Sort key** | Part number is **NOT** used for sorting. Pick lists are sorted by **address** (see §3). |
| **Grouping** | Parts are **never grouped** by base. Each part number is a unique item, even if it shares a base with another. |

### 1.9 Display

- Always render the **full 14-character canonical form** in the UI.
- Use a monospace font for part numbers in lists/tables.
- Long part numbers must wrap or shrink without breaking row layout.

### 1.10 Edge Cases

| Case | Behavior |
|---|---|
| Empty / null | Reject with error |
| Lowercase | Auto-uppercase, accept |
| Leading/trailing whitespace | Trim, accept |
| Internal whitespace | Reject (scanner error indicator) |
| Wrong length (11, 13, etc.) | Reject |
| Non-alphanumeric (besides `-`) | Reject |
| 10-char with non-generic color | Not representable — must use 12 or 14 form |

### 1.11 Reference Implementation

#### Python

```python
import re

PART_NUMBER_CANONICAL = re.compile(r"^[A-Z0-9]{5}-[A-Z0-9]{5}-[A-Z0-9]{2}$")
PART_NUMBER_INPUT     = re.compile(r"^[A-Z0-9]{5}-?[A-Z0-9]{5}(-?[A-Z0-9]{2})?$")

GENERIC_SUFFIX = "00"


def normalize_part_number(pn: str) -> str:
    """Normalize any accepted input form to canonical 14-char format."""
    if pn is None:
        raise ValueError("Part number is required")

    raw = pn.strip().upper()
    stripped = raw.replace("-", "")

    if not stripped.isalnum():
        raise ValueError(f"Invalid characters in part number: {pn!r}")

    if len(stripped) == 12:
        base, suffix = stripped[:10], stripped[10:]
    elif len(stripped) == 10:
        base, suffix = stripped, GENERIC_SUFFIX
    else:
        raise ValueError(f"Invalid part number length: {pn!r}")

    canonical = f"{base[:5]}-{base[5:]}-{suffix}"

    if not PART_NUMBER_CANONICAL.match(canonical):
        raise ValueError(f"Invalid part number format: {pn!r}")

    return canonical


def is_valid_part_number(pn: str) -> bool:
    try:
        normalize_part_number(pn)
        return True
    except ValueError:
        return False


def get_base_part(pn: str) -> str:
    """Return the 10-char base (no hyphens, no suffix)."""
    canonical = normalize_part_number(pn)
    return canonical[:5] + canonical[6:11]


def get_suffix(pn: str) -> str:
    """Return the 2-char color/variant suffix."""
    return normalize_part_number(pn)[-2:]


def is_generic(pn: str) -> bool:
    """True if part has no color variant (suffix == '00')."""
    return get_suffix(pn) == GENERIC_SUFFIX
```

#### JavaScript

```javascript
const PART_NUMBER_CANONICAL = /^[A-Z0-9]{5}-[A-Z0-9]{5}-[A-Z0-9]{2}$/;
const GENERIC_SUFFIX = "00";

export function normalizePartNumber(pn) {
  if (pn == null) throw new Error("Part number is required");

  const raw = String(pn).trim().toUpperCase();
  const stripped = raw.replace(/-/g, "");

  if (!/^[A-Z0-9]+$/.test(stripped)) {
    throw new Error(`Invalid characters in part number: ${pn}`);
  }

  let base, suffix;
  if (stripped.length === 12) {
    base = stripped.slice(0, 10);
    suffix = stripped.slice(10);
  } else if (stripped.length === 10) {
    base = stripped;
    suffix = GENERIC_SUFFIX;
  } else {
    throw new Error(`Invalid part number length: ${pn}`);
  }

  const canonical = `${base.slice(0, 5)}-${base.slice(5)}-${suffix}`;
  if (!PART_NUMBER_CANONICAL.test(canonical)) {
    throw new Error(`Invalid part number format: ${pn}`);
  }
  return canonical;
}

export const isValidPartNumber = (pn) => {
  try { normalizePartNumber(pn); return true; } catch { return false; }
};

export const getBasePart = (pn) => {
  const c = normalizePartNumber(pn);
  return c.slice(0, 5) + c.slice(6, 11);
};
export const getSuffix  = (pn) => normalizePartNumber(pn).slice(-2);
export const isGeneric  = (pn) => getSuffix(pn) === GENERIC_SUFFIX;
```

### 1.12 Test Cases

| Input | Expected Output | Notes |
|---|---|---|
| `"99999-CCCCC-B0"` | `"99999-CCCCC-B0"` | Canonical passthrough |
| `"99999CCCCCB0"` | `"99999-CCCCC-B0"` | 12-char form |
| `"99999CCCCC"` | `"99999-CCCCC-00"` | 10-char generic |
| `"99999-CCCCC"` | `"99999-CCCCC-00"` | 11-char generic |
| `"aa123-456bb-00"` | `"AA123-456BB-00"` | Lowercase normalization |
| `"  99999-CCCCC-B0  "` | `"99999-CCCCC-B0"` | Whitespace trim |
| `""` | ❌ ValueError | Empty |
| `"99999-CCCCC-B"` | ❌ ValueError | Bad length (13) |
| `"99999 CCCCC B0"` | ❌ ValueError | Internal whitespace |
| `"99999-CCCC@-B0"` | ❌ ValueError | Invalid char |
| `"99999-CCCCC-XYZ"` | ❌ ValueError | Suffix too long |

---

## 2. Scanner Input Parsing

> **Status:** ✅ LOCKED — 2026-07-15 · **Updated 2026-08-21** (separator tolerance)

### 2.1 Definition

A **Scan Payload** is the string produced when an operator scans a box label with the tablet's scanner. Every scan payload identifies both **which part** is in the box and **which specific physical box** it is.

Box labels are generated by the internal label-printing app (`Reader`), which is the sole source of truth for label content and formatting.

### 2.2 Canonical Format

```
{PART_NUMBER}{SEP}{LABEL_SEQ}
```

- **PART_NUMBER**: canonical 14-char form (see §1)
- **SEP**: a single character; canonically ASCII pipe `|` (0x7C)
- **LABEL_SEQ**: 16 decimal digits — timestamp + printing-station code

Total length: **31 characters** (14 + 1 + 16).

**Separator tolerance:** the parser accepts **any single non-alphanumeric character** as `SEP` — not just `|`. This is a field-hardening decision documented in §2.7.

### 2.3 Label Sequence Structure

`LABEL_SEQ` is 16 digits with fixed positional meaning:

```
YYYY MM DD HH MM SS TT
 4    2  2  2  2  2  2   = 16 digits
```

| Field | Positions | Range | Meaning |
|---|---|---|---|
| `year` | 0–3 | 4 digits | Calendar year |
| `month` | 4–5 | `01`–`12` | Calendar month |
| `day` | 6–7 | `01`–`31` | Calendar day |
| `hour` | 8–9 | `00`–`23` | Hour, 24h |
| `minute` | 10–11 | `00`–`59` | Minute |
| `second` | 12–13 | `00`–`59` | Second |
| `station` | 14–15 | `01`–`99` | Printing-station code |

**Example:**

```
2026071514231207
= 2026-07-15 14:23:12  printed on station 07
```

### 2.4 Full Payload Examples

Canonical (correct separator):

```
85370-BZJ60-00|2026071514231207
890C0-BZ060-00|2026071514231508
9004A-16036-00|2026071514231907
```

Also accepted (separator-tolerant — see §2.7):

```
G920Q-66010-00}2026081714235002       ← } instead of |
85370-BZJ60-00{2026071514231207       ← { instead of |
85370-BZJ60-00 2026071514231207       ← space instead of |
```

### 2.5 Validation Regex

```
^([A-Z0-9]{5}-[A-Z0-9]{5}-[A-Z0-9]{2})[^A-Z0-9](\d{16})$
```

Two capture groups:

- Group 1 (`part_number`): canonical part number
- Group 2 (`label_seq`): 16-digit sequence

The `[^A-Z0-9]` character class matches exactly **one** character that is not `A-Z` and not `0-9`. This deliberately excludes hyphens from being valid separators (protecting the hyphens inside the part number), while accepting `|`, `}`, `{`, `\`, space, and other punctuation.


### 2.6 Uniqueness

`LABEL_SEQ` is unique per box **in practice**: two labels can only share a sequence if printed on the same station in the same second.

The system treats `LABEL_SEQ` as a globally unique box identifier.

Duplicate detection: within one `(order_number, kanban_number)`, no `label_seq` may be scanned twice (see §9.5). Cross-kanban duplicates are permitted (the same physical box being scanned for a different order is a valid — if rare — real-world event).

### 2.7 Accepted Input Forms

Only the position-canonical form (14 + 1 + 16) is accepted. The one exception is the separator character, which may be any non-alphanumeric.

**Why the tolerance?**

Some barcode scanners on Portuguese/ABNT keyboard layouts mis-map the byte 0x7C (`|`) to adjacent characters like 0x7D (`}`). The scanner hardware and the label content are both correct; the browser receives the wrong ASCII character because of keyboard-driver translation. Rather than require every tablet to be reconfigured, we accept the family of near-`|` characters at parse time.

Rejected regardless:

- No separator at all (30 chars, e.g. `85370-BZJ60-002026071514231207`)
- Two-character separators (`||`, `|}`, ` |`)
- Any character in `[A-Z0-9]` — protects the part-number hyphens and digits

Whitespace handling: trim leading/trailing whitespace before matching. Reject internal whitespace *inside* the part number or label sequence (though a single internal whitespace character between them is a valid separator).

### 2.8 Validation Rules Summary

A scan payload is **accepted** iff all of the following hold:

1. It matches the regex in §2.5
2. Group 1 additionally passes canonical part-number validation (§1.7)
3. Group 2's `YYYYMMDDHHMMSS` (positions 0–13) parses as a real calendar date/time (rejects `20260230...` etc.)
4. Group 2's `TT` (positions 14–15) is in range `01`–`99`

Anything else: **reject with HTTP 400 and error `"Formato de QR inválido"`**.

### 2.9 Edge Cases

| Case | Behavior |
|---|---|
| Empty / whitespace only | Reject |
| Missing separator (30 chars) | Reject |
| Two separator chars | Reject |
| Lowercase in PN portion | Auto-uppercase, then validate |
| Separator is `}` / `{` / space / etc. | ✅ Accept (§2.7) |
| Separator is `|` | ✅ Accept (canonical) |
| Non-digit in `LABEL_SEQ` | Reject |
| Impossible date (`20260230`) | Reject |
| Station code `00` | Reject |
| Extra characters after station | Reject |
| Leading/trailing whitespace | Trim, accept |
| PN not in current pick list | Handled at business-logic layer (§9), not parsing |

### 2.10 Reference Implementation

#### Python

```python
import re
from datetime import datetime
from typing import NamedTuple

SCAN_PAYLOAD_RE = re.compile(
    r"^([A-Z0-9]{5}-[A-Z0-9]{5}-[A-Z0-9]{2})[^A-Z0-9](\d{16})$"
)


class ScanPayload(NamedTuple):
    part_number: str
    label_seq: str
    printed_at: datetime
    station: str


def parse_scan_payload(raw: str) -> ScanPayload:
    if raw is None:
        raise ValueError("Scan payload is required")

    text = raw.strip().upper()
    m = SCAN_PAYLOAD_RE.match(text)
    if not m:
        raise ValueError(f"Invalid scan payload format: {raw!r}")

    part_number, label_seq = m.group(1), m.group(2)

    try:
        printed_at = datetime.strptime(label_seq[:14], "%Y%m%d%H%M%S")
    except ValueError as e:
        raise ValueError(f"Invalid timestamp in label sequence: {label_seq[:14]}") from e

    station = label_seq[14:16]
    if station == "00":
        raise ValueError(f"Invalid station code: {station}")

    return ScanPayload(
        part_number=part_number,
        label_seq=label_seq,
        printed_at=printed_at,
        station=station,
    )


def is_valid_scan(raw: str) -> bool:
    try:
        parse_scan_payload(raw)
        return True
    except ValueError:
        return False
```


#### JavaScript

```javascript
const SCAN_PAYLOAD_RE =
  /^([A-Z0-9]{5}-[A-Z0-9]{5}-[A-Z0-9]{2})[^A-Z0-9](\d{16})$/;

export function parseScanPayload(raw) {
  if (raw == null) throw new Error("Scan payload is required");

  const text = String(raw).trim().toUpperCase();
  const m = SCAN_PAYLOAD_RE.exec(text);
  if (!m) throw new Error(`Invalid scan payload format: ${raw}`);

  const [, partNumber, labelSeq] = m;

  const y  = parseInt(labelSeq.slice(0, 4), 10);
  const mo = parseInt(labelSeq.slice(4, 6), 10);
  const d  = parseInt(labelSeq.slice(6, 8), 10);
  const h  = parseInt(labelSeq.slice(8, 10), 10);
  const mi = parseInt(labelSeq.slice(10, 12), 10);
  const s  = parseInt(labelSeq.slice(12, 14), 10);
  const station = labelSeq.slice(14, 16);

  const dt = new Date(Date.UTC(y, mo - 1, d, h, mi, s));
  const ok =
    dt.getUTCFullYear() === y &&
    dt.getUTCMonth() === mo - 1 &&
    dt.getUTCDate() === d &&
    dt.getUTCHours() === h &&
    dt.getUTCMinutes() === mi &&
    dt.getUTCSeconds() === s;
  if (!ok) throw new Error(`Invalid timestamp in label sequence: ${labelSeq.slice(0, 14)}`);

  if (station === "00") throw new Error(`Invalid station code: ${station}`);

  return { partNumber, labelSeq, printedAt: dt, station };
}

export const isValidScan = (raw) => {
  try { parseScanPayload(raw); return true; } catch { return false; }
};
```


### 2.11 Test Cases

| Input | Expected | Notes |
|---|---|---|
| `"85370-BZJ60-00\|2026071514231207"` | ✅ parse OK | Canonical |
| `"G920Q-66010-00}2026081714235002"` | ✅ parse OK | `}` separator (§2.7) |
| `"85370-BZJ60-00{2026071514231207"` | ✅ parse OK | `{` separator |
| `"85370-BZJ60-00 2026071514231207"` | ✅ parse OK | space separator |
| `"  85370-BZJ60-00\|2026071514231207  "` | ✅ parse OK | Whitespace trimmed |
| `"85370-bzj60-00\|2026071514231207"` | ✅ parse OK | Lowercase auto-uppercase |
| `"85370BZJ6000\|2026071514231207"` | ❌ ValueError | Missing hyphens in PN |
| `"85370-BZJ60-002026071514231207"` | ❌ ValueError | No separator (30 chars) |
| `"85370-BZJ60-00\|\|2026071514231207"` | ❌ ValueError | Two separator chars |
| `"85370-BZJ60-00\|202607151423120"` | ❌ ValueError | 15 digits |
| `"85370-BZJ60-00\|20260715142312077"` | ❌ ValueError | 17 digits |
| `"85370-BZJ60-00\|2026023014231207"` | ❌ ValueError | Feb 30 impossible |
| `"85370-BZJ60-00\|2026071514231200"` | ❌ ValueError | Station `00` |
| `"85370-BZJ60-00\|abcd071514231207"` | ❌ ValueError | Non-digit |
| `""` | ❌ ValueError | Empty |
| `null` | ❌ ValueError | Null |

---

## 3. Address / Location

> **Status:** ✅ LOCKED — 2026-06-05

### 3.1 Definition

An **Address** identifies a physical location in the warehouse where a part is stored. It is the **primary sort key** for pick lists — operators walk the warehouse following address order.

### 3.2 Address Categories

The system recognizes **three** categories of address:

| Category | Description | Example |
|---|---|---|
| **Rack** | Standard storage: corridor + rack + shelf | `A01C`, `H21C` |
| **Pallet** | Open-module pallet storage: corridor + rack only | `D17`, `F03` |
| **Special** | Named non-rack locations | `DTL`, `KDB`, `WELDING` |

A part with **no assigned address** is stored as `NULL`. It is not a fourth category — it represents missing data.

### 3.3 Rack Address — Canonical Format

Format: `CRRS` (4 characters)

| Segment | Length | Allowed values | Meaning |
|---|---|---|---|
| **C** | 1 | `A`–`H` | Corridor (8 corridors total) |
| **RR** | 2 | `01`–`28` | Rack number, zero-padded |
| **S** | 1 | `A`–`G` | Shelf within the rack |

Examples: `A01C`, `B27D`, `C24G`, `H21A`

### 3.4 Pallet Address — Canonical Format

Format: `CRR` (3 characters)

| Segment | Length | Allowed values | Meaning |
|---|---|---|---|
| **C** | 1 | `D`, `F` | Corridor (only D and F have pallets) |
| **RR** | 2 | `01`–`28` | Rack number, zero-padded |

Examples: `D17`, `D25`, `F03`, `F09`, `F11`

> **Note:** Corridors D and F contain **both** rack addresses (e.g. `D02A`) and pallet addresses (e.g. `D17`). They are distinguished by length.

### 3.5 Special Address — Canonical Format

A fixed enumeration of named locations:

| Canonical | Accepted Aliases (case-insensitive) | Meaning |
|---|---|---|
| `DTL` | `dtl`, `DTL - Big Parts`, `DTL/Transbordo` | Direct-to-line / large assemblies |
| `KDB` | `kdb` | KD bumper area |
| `BOSCH` | `bosch` | Bosch supplier staging |
| `WELDING` | `welding` | Welding line (beams) |
| `PAINT` | `paint` | Paint shop |
| `CACAMBINHA` | `caçambinha`, `cacambinha` | Reinforcement bin area |
| `TRANSBORDO` | `transbordo`, `F11/Transbordo` | Transfer area |
| `DIRECTF` | `DIRECT F`, `direct f` | Direct-F supply |

Special addresses are **opaque identifiers**. Stored uppercase, ASCII, no spaces.

### 3.6 Accepted Input Forms

| Input | Type | Normalization |
|---|---|---|
| `A01C`, `a01c`, ` A01C ` | Rack | Trim, uppercase |
| `A1C` | Rack | Zero-pad → `A01C` |
| `D17`, `d17`, `D 17` | Pallet | Strip spaces, uppercase |
| `D7` | Pallet | Zero-pad → `D07` |
| `dtl - big parts` | Special | Alias → `DTL` |
| `0,0`, empty, `null` | Missing | Return `None` (not an error) |

### 3.7 Validation

Canonical regexes:

- **Rack:** `^[A-H](0[1-9]|1[0-9]|2[0-8])[A-G]$`
- **Pallet:** `^[DF](0[1-9]|1[0-9]|2[0-8])$`
- **Special:** `^(DTL|KDB|BOSCH|WELDING|PAINT|CACAMBINHA|TRANSBORDO|DIRECTF)$`

An address is valid if it matches **exactly one** of the three.

### 3.8 Sort Order

Pick lists are sorted by address using:

1. **Bucket** — Rack/Pallet first; Special last; `NULL` excluded from active lists.
2. Within Rack/Pallet:
   - Corridor `A→H`
   - Rack number `01→28`
   - Pallets sort **before** any shelf at the same `(corridor, rack)`
   - Shelf `A→G`
3. Within Special: alphabetical.

Example sorted order:
`A01C → A02A → A02C → ... → D02A → D02B → D17 → ... → F03 → ... → H21D → BOSCH → DTL → KDB`

### 3.9 Display

- Render canonical form in monospace.
- Rack: 4 chars (`A01C`)
- Pallet: 3 chars (`D17`)
- Special: 3–10 chars (`DTL`, `WELDING`)
- `NULL` displays as `—` and **never appears in active pick lists**.

### 3.10 Edge Cases

| Case | Behavior |
|---|---|
| `0,0` | Treat as `NULL` |
| Empty / whitespace / `null` | Treat as `NULL` |
| `A29A` (rack > 28) | Reject |
| `I01A` (corridor > H) | Reject |
| `A01H` (shelf > G) | Reject |
| `A00A` (rack 00) | Reject |
| `A1C` | Accept, normalize to `A01C` |
| Lowercase | Accept, uppercase |
| Trailing/leading whitespace | Trim, accept |
| Internal whitespace | Strip, accept |
| Unknown special name | Reject |

### 3.11 Reference Implementation (Python)

```python
import re
from typing import Optional

RACK_RE   = re.compile(r"^[A-H](0[1-9]|1[0-9]|2[0-8])[A-G]$")
PALLET_RE = re.compile(r"^[DF](0[1-9]|1[0-9]|2[0-8])$")

SPECIAL_SET = {"DTL", "KDB", "BOSCH", "WELDING", "PAINT",
               "CACAMBINHA", "TRANSBORDO", "DIRECTF"}

SPECIAL_ALIASES = {
    "DTL": "DTL",
    "DTL - BIG PARTS": "DTL",
    "DTL/TRANSBORDO": "DTL",
    "KDB": "KDB",
    "BOSCH": "BOSCH",
    "WELDING": "WELDING",
    "PAINT": "PAINT",
    "CAÇAMBINHA": "CACAMBINHA",
    "CACAMBINHA": "CACAMBINHA",
    "TRANSBORDO": "TRANSBORDO",
    "F11/TRANSBORDO": "TRANSBORDO",
    "DIRECT F": "DIRECTF",
    "DIRECTF": "DIRECTF",
}

NULL_TOKENS = {"", "0,0", "NULL", "NONE", "-", "—"}


def normalize_address(addr: Optional[str]) -> Optional[str]:
    if addr is None:
        return None
    raw = str(addr).strip().upper()
    if raw in NULL_TOKENS:
        return None
    if raw in SPECIAL_ALIASES:
        return SPECIAL_ALIASES[raw]

    compact = raw.replace(" ", "")
    m = re.match(r"^([A-H])(\d{1,2})([A-G]?)$", compact)
    if m:
        corridor, rack, shelf = m.groups()
        compact = f"{corridor}{rack.zfill(2)}{shelf}"

    if RACK_RE.match(compact) or PALLET_RE.match(compact):
        return compact
    raise ValueError(f"Invalid address: {addr!r}")


def is_valid_address(addr) -> bool:
    try:
        return normalize_address(addr) is not None
    except ValueError:
        return False


def address_category(addr: Optional[str]) -> Optional[str]:
    if addr is None:
        return None
    if RACK_RE.match(addr):   return "RACK"
    if PALLET_RE.match(addr): return "PALLET"
    if addr in SPECIAL_SET:   return "SPECIAL"
    return None


def address_sort_key(addr: Optional[str]) -> tuple:
    if addr is None:
        return (3, "", 0, 0, "")
    cat = address_category(addr)
    if cat == "RACK":
        return (0, addr[0], int(addr[1:3]), 1, addr[3])
    if cat == "PALLET":
        return (0, addr[0], int(addr[1:3]), 0, "")
    if cat == "SPECIAL":
        return (1, addr, 0, 0, "")
    return (3, "", 0, 0, "")
```

### 3.12 Test Cases

| Input | Expected | Notes |
|---|---|---|
| `"A01C"` | `"A01C"` | Canonical rack |
| `"a01c"` | `"A01C"` | Lowercase |
| `"  A01C  "` | `"A01C"` | Whitespace |
| `"A1C"` | `"A01C"` | Zero-pad |
| `"D17"` | `"D17"` | Canonical pallet |
| `"D 17"` | `"D17"` | Internal space |
| `"d7"` | `"D07"` | Pallet zero-pad |
| `"DTL - Big Parts"` | `"DTL"` | Alias |
| `"F11/Transbordo"` | `"TRANSBORDO"` | Alias |
| `"caçambinha"` | `"CACAMBINHA"` | Accent variant |
| `"0,0"` | `None` | Unassigned |
| `""` | `None` | Empty |
| `None` | `None` | Null passthrough |
| `"A29A"` | ❌ ValueError | Rack > 28 |
| `"I01A"` | ❌ ValueError | Corridor > H |
| `"A01H"` | ❌ ValueError | Shelf > G |
| `"A00A"` | ❌ ValueError | Rack 00 |
| `"FOO"` | ❌ ValueError | Garbage |

---

## 4. Order / Pedido

> **Status:** 🔴 TBD

---

## 5. Operator

> **Status:** 🔴 TBD

Deferred. Placeholder: for now, all scans are attributed to the constant nickname `"TKLpicker"`. Full operator model to be defined once the order-selection form is expanded to include picker + dolly selection.

---

## 6. Dolly / Cart

> **Status:** 🔴 TBD

---

## 7. Lane / Route

> **Status:** 🔴 TBD

---

## 8. Dates & Times

> **Status:** 🔴 TBD

Backend exchange in ISO 8601 UTC. UI displays in `DD/MM/YYYY HH:MM:SS` (BR locale, `America/Sao_Paulo`). To be fully defined.

---

## 9. Picking Status

> **Status:** ✅ LOCKED — 2026-07-15

### 9.1 Definition

**Picking Status** tracks the operator's progress on a single pick-list line — one row corresponds to one kanban box request in one order. It is the primary signal used by the UI to color rows and by supervisors to detect problems in real time.

Every pick-list row has exactly **one** current status. Status transitions are recorded with a timestamp and the operator who made the change.

### 9.2 Canonical Values

The system recognizes **four** statuses:

| Canonical | Meaning | Default? | CSS class |
|---|---|---|---|
| `PENDING` | Not yet fully picked (initial state, or partial scan in progress) | ✅ | `row-pending` |
| `OK` | All required boxes scanned | | `row-ok` |
| `KSE` | Part not available at rack; supervisor notified | | `row-kse` |
| `WARNING` | Reserved for future manual flagging (not used in v1) | | `row-warning` |

- Storage: uppercase ASCII, `[A-Z]{2,10}`.
- Enum is **closed** — new values require updating this document and the DB check constraint.
- Empty string, `NULL`, and unknown values are treated as `PENDING` on read.

### 9.3 State Machine

```
        ┌──────────────────────────────┐
        ▼                              │
    PENDING ──► OK                     │
        │        ▲                     │
        ├───► KSE│                     │
        │        │                     │
        └───► WARNING ─────────────────┘
```

- `PENDING` is the initial state for every fresh row.
- Every successful QR scan increments `boxes_scanned`; the row stays `PENDING` until `boxes_scanned == boxes_required`, at which point it flips to `OK`.
- `KSE` can be set manually from any state. Once `KSE`, `boxes_scanned` is **frozen** at its current value (not reset).
- Any status can transition back to `PENDING` via an explicit "Reset" action (v1 does not expose Reset in the UI; deferred).
- `WARNING` is defined for future use. v1 UI has no way to set it.
- The state machine is **advisory** — the backend accepts any canonical value. UX enforces sensible transitions.

### 9.4 Storage

Two tables in Lakebase Postgres.

**`picking_status`** — one row per pick-list line:

```sql
CREATE TABLE picking_status (
    order_number    VARCHAR(10)   NOT NULL,
    kanban_number   VARCHAR(10)   NOT NULL,
    status          VARCHAR(10)   NOT NULL DEFAULT 'PENDING',
    boxes_scanned   INTEGER       NOT NULL DEFAULT 0,
    boxes_required  INTEGER       NOT NULL DEFAULT 1,
    updated_by      VARCHAR(50),
    updated_at      TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (order_number, kanban_number),
    CONSTRAINT picking_status_valid CHECK (status IN ('PENDING','OK','KSE','WARNING'))
);

CREATE INDEX idx_picking_status_order ON picking_status(order_number);
```

**`picking_scans`** — one row per confirmed QR scan (audit + duplicate detection):

```sql
CREATE TABLE picking_scans (
    order_number    VARCHAR(10)   NOT NULL,
    kanban_number   VARCHAR(10)   NOT NULL,
    label_seq       VARCHAR(16)   NOT NULL,
    part_number     VARCHAR(14)   NOT NULL,
    scanned_by      VARCHAR(50)   NOT NULL,
    scanned_at      TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (order_number, kanban_number, label_seq),
    FOREIGN KEY (order_number, kanban_number)
        REFERENCES picking_status(order_number, kanban_number)
        ON DELETE CASCADE
);

CREATE INDEX idx_picking_scans_order ON picking_scans(order_number);
```

**Key design decisions:**

- `(order_number, kanban_number)` is the natural key for status. The same part number can appear across multiple kanbans; each kanban gets its own status row.
- Rows in `picking_status` are **created lazily** on first write. A freshly loaded order has no rows in `picking_status`. Absent = `PENDING`.
- The primary key of `picking_scans` prevents duplicate scans of the same physical box within the same kanban — Postgres refuses the INSERT.
- `boxes_scanned` in `picking_status` is a **cached counter**; the ground truth is `COUNT(*) FROM picking_scans` filtered by `(order_number, kanban_number)`. On any inconsistency, `picking_scans` wins.
- `updated_by` and `scanned_by` hold operator nicknames (see §5). For v1, this is hardcoded to `"TKLpicker"`.
- `boxes_required` is computed at first-write time from eKanban's `box_part_quantity` divided by the part's `lote_size`. In v1 it defaults to `1` (single-box) until Lakebase parts fetching is wired up.

### 9.5 API Contract

**Read** (bundled inside the pick-list response — no separate endpoint):

Every pick-list row returned by `GET /picking/<order_number>` includes:

```json
{
  "endereco": "A24A",
  "part_number": "85370-BZJ60-00",
  "qtd": 60,
  "exporter": "807B",
  "caixa": "0947",
  "status": "PENDING",
  "boxes_scanned": 0,
  "boxes_required": 1
}
```

**Write — scan a box:**

```
POST /api/picking/<order_number>/<kanban_number>/scan
Content-Type: application/json

{ "payload": "85370-BZJ60-00|2026071514231207" }
```

Success (`200`):

```json
{
  "ok": true,
  "order_number": "2026051809",
  "kanban_number": "0947",
  "status": "OK",
  "boxes_scanned": 1,
  "boxes_required": 1,
  "updated_at": "2026-07-15T14:23:12Z"
}
```

Errors (`400` / `409`):

| Code | Error | Cause |
|---|---|---|
| 400 | `"Formato de QR inválido"` | Payload doesn't match §2.5 |
| 400 | `"Peça errada"` | PN in payload ≠ kanban's expected PN |
| 409 | `"Caixa já escaneada"` | `label_seq` already recorded for this kanban |
| 400 | `"Kanban já completo"` | Row is already `OK` |

**Write — mark KSE:**

```
POST /api/picking/<order_number>/<kanban_number>/kse
Content-Type: application/json

{ }
```

Success:

```json
{
  "ok": true,
  "order_number": "2026051809",
  "kanban_number": "0947",
  "status": "KSE",
  "boxes_scanned": 0,
  "boxes_required": 1,
  "parts_lacking": 60,
  "updated_at": "2026-07-15T14:24:03Z"
}
```

`parts_lacking = box_part_quantity - (boxes_scanned × lote_size)`. This value is sent to the supervisor notification (see §9.7).

**Write — call operator:**

```
POST /api/picking/<order_number>/<kanban_number>/call
Content-Type: application/json

{ }
```

Success:

```json
{
  "ok": true,
  "notified": true
}
```

Does not change `status`.

### 9.6 Validation

**Status value regex** (server-side):

```
^(PENDING|OK|KSE|WARNING)$
```

**Scan payload:** delegated to §2 parsing rules.

**Kanban existence:** `(order_number, kanban_number)` pair must exist in the eKanban source table for the write endpoints to accept the request. Otherwise HTTP 404.

### 9.7 Notifications

Two supervisor-notification events emit from status writes:

| Event | Trigger | Payload |
|---|---|---|
| `KANBAN_KSE` | Any transition to `KSE` | `order_number`, `kanban_number`, `part_number`, `parts_lacking`, `operator` |
| `OPERATOR_CALL` | POST to `/call` endpoint | `order_number`, `kanban_number`, `part_number`, `operator` |

The **global** "Chamar" button on the picking screen emits a third variant:

| Event | Trigger | Payload |
|---|---|---|
| `ORDER_CALL` | POST to `/api/chamar` | `order_number`, `operator` |

**v1 implementation:** all three events log a structured record server-side and return success. The actual notification channel (Teams, Slack, DB write, email) is deferred — the API contract stays stable so swapping the backend later is a one-file change.

### 9.8 Display

- Row color matches the CSS class in §9.2.
- The `Status` column shows:
  - Empty for `PENDING` when `boxes_scanned == 0`
  - `n/m` for `PENDING` when partial (e.g. `1/4`)
  - `OK` for `OK`
  - `KSE` for `KSE`
  - `WARNING` for `WARNING` (unused in v1)
- Rows are tappable when status ≠ `OK`. Tap opens the status modal (§9.9).
- `OK` rows are non-interactive but remain visible.

### 9.9 UX — Status Modal

Operator taps a pick-list row → modal appears:

```
┌───────────────────────────────────────┐
│  ✕                                     │
│  Endereço:  A24A                       │
│  Part:      85370-BZJ60-00             │
│  Caixa:     0947                       │
│  Progresso: 0 / 1 caixas escaneadas    │
│                                        │
│  ┌─────────────────────────────────┐   │
│  │  📷 Escaneie o QR da caixa       │   │
│  │  [       input field        ]   │   │
│  └─────────────────────────────────┘   │
│                                        │
│  ┌───────────┐  ┌─────────────────┐    │
│  │  ✗ KSE    │  │ 📞 Chamar op.   │    │
│  └───────────┘  └─────────────────┘    │
│                                        │
│  [           Cancelar             ]    │
└───────────────────────────────────────┘
```

**Behavior:**

- The scan input is auto-focused when the modal opens.
- Each successful scan calls the `/scan` endpoint. On success:
  - `boxes_scanned` increments; progress line updates.
  - If `boxes_scanned == boxes_required`, status flips to `OK`, modal auto-closes after 800 ms.
- Scan errors (invalid format, wrong part, duplicate) display an inline error message in the modal without closing it. The input clears and refocuses.
- `KSE` button → calls `/kse` endpoint, closes modal on success.
- `Chamar operador` button → calls `/call` endpoint, shows a "Supervisor notificado" toast, keeps modal open.
- `Cancelar` and `✕` → close modal, no state change.
- Minimum touch-target size: 88 × 88 px for all buttons (glove-friendly).

**Optimistic UI:**

- On any successful action, the pick-list row updates in the underlying table **immediately** — before the POST completes.
- If the POST fails, the row reverts to its previous state and a toast displays the error.
- Applies to `/scan` and `/kse`. `/call` is not optimistic (no visible state to revert).

### 9.10 Concurrency

Last-write-wins. Two operators editing the same order will overwrite each other silently.

Acceptable for v1. Future work will divide orders by picker + dolly so operators cannot work the same kanban simultaneously (see §5 and §6).

### 9.11 Auditing

`updated_by` and `updated_at` on `picking_status` give a point-in-time snapshot. `picking_scans` gives a full per-box scan log with timestamp and operator.

Together these are sufficient for:

- "When was this kanban marked OK, and by whom?"
- "How long did operator X take on order Y?"
- "Which physical boxes were scanned for kanban Z, and in what order?"

If a full status-history table is needed later (every status transition, not just current state), add `picking_status_history` with the same columns plus `previous_status`, populated by an AFTER UPDATE trigger.

### 9.12 Edge Cases

| Case | Behavior |
|---|---|
| Order not in `picking_status` yet | All rows treated as `PENDING`, `boxes_scanned = 0` |
| `status = NULL` or empty in DB | Treated as `PENDING` |
| `status` = unknown value in DB | Treated as `PENDING`, log warning |
| POST with status not in enum | HTTP 400, no DB change |
| POST while offline | Frontend surfaces network error toast; queue-and-retry deferred |
| Operator scans an already-OK row's QR | HTTP 400 `"Kanban já completo"` |
| Operator scans a QR for a different kanban | HTTP 400 `"Peça errada"` |
| Operator scans same box twice in a row | HTTP 409 `"Caixa já escaneada"` |
| `boxes_required = 0` in DB (bad data) | Treat as `1`; log warning |
| `boxes_scanned > boxes_required` (bad data) | Treat as `OK`; log warning |
| KSE on already-KSE row | Idempotent; `updated_at` bumps, no notification re-sent |
| Cross-kanban duplicate scan | Permitted (same physical box, different kanban) |

### 9.13 Reference Implementation (Python — status transitions)

```python
from typing import Optional

VALID_STATUSES = {"PENDING", "OK", "KSE", "WARNING"}


def normalize_status(raw: Optional[str]) -> str:
    """Coerce any incoming value to a canonical status."""
    if not raw:
        return "PENDING"
    s = str(raw).strip().upper()
    return s if s in VALID_STATUSES else "PENDING"


def compute_status_after_scan(boxes_scanned: int, boxes_required: int) -> str:
    """Determine status after a successful scan increment."""
    if boxes_required <= 0:
        return "OK"                     # defensive; treat bad data as complete
    if boxes_scanned >= boxes_required:
        return "OK"
    return "PENDING"


def compute_parts_lacking(
    boxes_scanned: int,
    box_part_quantity: int,
    lote_size: int,
) -> int:
    """Parts still needed to complete the kanban (used in KSE notifications)."""
    if lote_size <= 0:
        return box_part_quantity
    return max(0, box_part_quantity - (boxes_scanned * lote_size))
```

### 9.14 Test Cases

| Scenario | Expected |
|---|---|
| Fresh order, first scan of a 1-box kanban | Status flips `PENDING → OK` |
| Fresh order, first scan of a 4-box kanban | Status stays `PENDING`, `boxes_scanned = 1` |
| 4-box kanban after 4th scan | Status flips `PENDING → OK` |
| Scan same box twice | Second call returns HTTP 409, no state change |
| Scan wrong part | HTTP 400, no state change |
| Malformed QR payload | HTTP 400, no state change |
| KSE button on `PENDING (2/4)` | Status → `KSE`, `boxes_scanned` stays at 2, supervisor notified with `parts_lacking` computed |
| KSE button on already-`KSE` row | Idempotent success, `updated_at` bumps, no new notification |
| Chamar operador button | Supervisor notified, status unchanged |
| Row is `OK`, operator taps it | Modal opens but shows read-only summary; scan input disabled |
| Two operators mark same kanban simultaneously | Last write wins, no error surfaced (see §9.10) |

---

## 📅 Changelog

### 2026-08-21
- §2 Scanner Input Parsing — **separator tolerance** added. Parser now accepts any single non-alphanumeric character as the separator between PN and label sequence (fixes ABNT keyboard `|` → `}` mis-mapping observed in the field).
- Regex updated from `\|` to `[^A-Z0-9]`.
- Test cases and edge-case table updated.

### 2026-07-15
- §2 Scanner Input Parsing — locked (QR format `{PART_NUMBER}|{LABEL_SEQ}`, 31 chars total)
- §9 Picking Status — locked (4 statuses, two-table storage in Lakebase, optimistic UI)
- §5 Operator — noted as deferred; v1 uses hardcoded nickname `"TKLpicker"`

### 2026-06-05
- Document created
- §1 Part Number — locked
- §3 Address / Location — locked
- §2, §4–§8 — placeholders added