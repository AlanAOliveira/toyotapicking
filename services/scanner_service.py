"""
Scanner input parsing.

Implements DATA_STANDARDS.md §2. Parses QR payloads from box labels
into structured data. Rejects malformed input with clear errors.

Separator tolerance (§2.7):
    Some scanner/keyboard combinations on Portuguese/ABNT layouts
    mis-map ASCII '|' (0x7C) to adjacent characters like '}' (0x7D).
    Rather than reconfigure every tablet, we accept any single
    non-alphanumeric character as the separator between the part
    number and the label sequence. Two-char separators and
    no-separator payloads are still rejected.
"""

import re
from datetime import datetime
from typing import NamedTuple

# Regex explanation:
#   ^([A-Z0-9]{5}-[A-Z0-9]{5}-[A-Z0-9]{2})   → canonical 14-char part number
#   [^A-Z0-9]                                 → exactly one non-alphanumeric separator
#   (\d{16})$                                 → 16-digit label sequence
#
# The [^A-Z0-9] class deliberately excludes hyphens from being valid
# separators, protecting the hyphens inside the part number.
SCAN_PAYLOAD_RE = re.compile(
    r"^([A-Z0-9]{5}-[A-Z0-9]{5}-[A-Z0-9]{2})[^A-Z0-9](\d{16})$"
)


class ScanPayload(NamedTuple):
    """Parsed scan payload — see DATA_STANDARDS.md §2.2."""
    part_number: str    # canonical 14-char
    label_seq: str      # 16-digit sequence
    printed_at: datetime
    station: str        # 2-digit


class ScanParseError(ValueError):
    """Raised when a scan payload cannot be parsed."""
    pass


def parse_scan_payload(raw: str) -> ScanPayload:
    """
    Parse a QR scan payload.

    Format: {PART_NUMBER}{SEP}{LABEL_SEQ}
      where SEP = any single non-alphanumeric char
      and   LABEL_SEQ = YYYYMMDDHHMMSSTT (16 digits)

    Raises:
        ScanParseError: any malformed input
    """
    if raw is None:
        raise ScanParseError("Scan payload is required")

    text = str(raw).strip().upper()
    m = SCAN_PAYLOAD_RE.match(text)
    if not m:
        raise ScanParseError(f"Invalid scan payload format: {raw!r}")

    part_number, label_seq = m.group(1), m.group(2)

    # Timestamp portion (positions 0-13) — must be a real date/time
    try:
        printed_at = datetime.strptime(label_seq[:14], "%Y%m%d%H%M%S")
    except ValueError as e:
        raise ScanParseError(
            f"Invalid timestamp in label sequence: {label_seq[:14]}"
        ) from e

    # Station code (positions 14-15)
    station = label_seq[14:16]
    if station == "00":
        raise ScanParseError(f"Invalid station code: {station}")

    return ScanPayload(
        part_number=part_number,
        label_seq=label_seq,
        printed_at=printed_at,
        station=station,
    )


def is_valid_scan(raw: str) -> bool:
    """True if the scan payload parses cleanly."""
    try:
        parse_scan_payload(raw)
        return True
    except ScanParseError:
        return False