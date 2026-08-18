"""
Picking status data access — Lakebase Postgres.

Reads and writes to picking_status + picking_scans tables.
Implements the state transitions defined in DATA_STANDARDS.md §9.
"""

import logging
from typing import Optional, Dict, Any, List

from psycopg import errors as pg_errors

from database.lakebase_conn import get_connection, get_schema_name

log = logging.getLogger(__name__)

VALID_STATUSES = {"PENDING", "OK", "KSE", "WARNING"}
DEFAULT_STATUS = "PENDING"


# ----------------------------------------------------------------------
# Exceptions — one per error case in DATA_STANDARDS §9.5
# ----------------------------------------------------------------------

class PickingStatusError(Exception):
    """Base for status-write errors surfaced to the API layer."""
    http_status = 400


class DuplicateScanError(PickingStatusError):
    """The same label_seq was already scanned for this kanban."""
    http_status = 409


class KanbanCompleteError(PickingStatusError):
    """Row is already OK; further scans rejected."""
    http_status = 400


class WrongPartError(PickingStatusError):
    """Scanned part number doesn't match the kanban's expected PN."""
    http_status = 400


# ----------------------------------------------------------------------
# Read
# ----------------------------------------------------------------------

def fetch_statuses_for_order(order_number: str) -> Dict[str, Dict[str, Any]]:
    """
    Return {kanban_number: {status, boxes_scanned, boxes_required, ...}}
    for a whole order. Rows not yet touched are absent — caller treats
    them as PENDING with zero scans.
    """
    schema = get_schema_name()
    query = f"""
        SELECT kanban_number, status, boxes_scanned, boxes_required,
               updated_by, updated_at
        FROM "{schema}".picking_status
        WHERE order_number = %s
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, [order_number])
            rows = cur.fetchall()
            columns = [d[0] for d in cur.description]

    return {
        row[0]: dict(zip(columns, row))
        for row in rows
    }


# ----------------------------------------------------------------------
# Write — scan
# ----------------------------------------------------------------------

def record_scan(
    *,
    order_number: str,
    kanban_number: str,
    expected_part_number: str,
    scanned_part_number: str,
    label_seq: str,
    scanned_by: str,
    boxes_required: int = 1,
) -> Dict[str, Any]:
    """
    Record a QR scan for a kanban.

    Business rules:
      - expected_part_number must equal scanned_part_number (WrongPartError)
      - (order, kanban, label_seq) must be new (DuplicateScanError)
      - Current status must not already be OK (KanbanCompleteError)

    On success:
      - Insert into picking_scans (uniqueness enforced by PK)
      - Upsert picking_status: increment boxes_scanned, flip to OK if complete

    Returns the new state dict.
    """
    if expected_part_number != scanned_part_number:
        raise WrongPartError(
            f"Peça errada: esperado {expected_part_number}, "
            f"escaneado {scanned_part_number}"
        )

    schema = get_schema_name()

    with get_connection() as conn:
        with conn.cursor() as cur:
            # 1. Ensure a status row exists (create as PENDING if not)
            cur.execute(f"""
                INSERT INTO "{schema}".picking_status
                    (order_number, kanban_number, status,
                     boxes_scanned, boxes_required, updated_by)
                VALUES (%s, %s, 'PENDING', 0, %s, %s)
                ON CONFLICT (order_number, kanban_number) DO NOTHING
            """, [order_number, kanban_number, boxes_required, scanned_by])

            # 2. Read current state (with row lock to prevent races)
            cur.execute(f"""
                SELECT status, boxes_scanned, boxes_required
                FROM "{schema}".picking_status
                WHERE order_number = %s AND kanban_number = %s
                FOR UPDATE
            """, [order_number, kanban_number])
            row = cur.fetchone()
            current_status, boxes_scanned, boxes_required_db = row

            if current_status == "OK":
                raise KanbanCompleteError("Kanban já completo")

            # 3. Insert the scan (unique PK gives us free duplicate detection)
            try:
                cur.execute(f"""
                    INSERT INTO "{schema}".picking_scans
                        (order_number, kanban_number, label_seq,
                         part_number, scanned_by)
                    VALUES (%s, %s, %s, %s, %s)
                """, [order_number, kanban_number, label_seq,
                      scanned_part_number, scanned_by])
            except pg_errors.UniqueViolation:
                raise DuplicateScanError("Caixa já escaneada")

            # 4. Increment counter, flip status if complete
            new_scanned = boxes_scanned + 1
            new_status = "OK" if new_scanned >= boxes_required_db else "PENDING"

            cur.execute(f"""
                UPDATE "{schema}".picking_status
                SET boxes_scanned = %s,
                    status = %s,
                    updated_by = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE order_number = %s AND kanban_number = %s
                RETURNING status, boxes_scanned, boxes_required, updated_at
            """, [new_scanned, new_status, scanned_by,
                  order_number, kanban_number])
            updated = cur.fetchone()

        conn.commit()

    return {
        "order_number": order_number,
        "kanban_number": kanban_number,
        "status":         updated[0],
        "boxes_scanned":  updated[1],
        "boxes_required": updated[2],
        "updated_at":     updated[3].isoformat() + "Z",
    }


# ----------------------------------------------------------------------
# Write — KSE
# ----------------------------------------------------------------------

def mark_kse(
    *,
    order_number: str,
    kanban_number: str,
    updated_by: str,
    boxes_required: int = 1,
) -> Dict[str, Any]:
    """
    Mark a kanban as KSE (not on rack). boxes_scanned is preserved.
    Returns the new state, including parts_lacking for the supervisor
    notification. Idempotent.
    """
    schema = get_schema_name()

    with get_connection() as conn:
        with conn.cursor() as cur:
            # Ensure row exists
            cur.execute(f"""
                INSERT INTO "{schema}".picking_status
                    (order_number, kanban_number, status,
                     boxes_scanned, boxes_required, updated_by)
                VALUES (%s, %s, 'PENDING', 0, %s, %s)
                ON CONFLICT (order_number, kanban_number) DO NOTHING
            """, [order_number, kanban_number, boxes_required, updated_by])

            # Flip to KSE, keep boxes_scanned intact
            cur.execute(f"""
                UPDATE "{schema}".picking_status
                SET status = 'KSE',
                    updated_by = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE order_number = %s AND kanban_number = %s
                RETURNING status, boxes_scanned, boxes_required, updated_at
            """, [updated_by, order_number, kanban_number])
            updated = cur.fetchone()

        conn.commit()

    return {
        "order_number":  order_number,
        "kanban_number": kanban_number,
        "status":        updated[0],
        "boxes_scanned": updated[1],
        "boxes_required": updated[2],
        "updated_at":    updated[3].isoformat() + "Z",
    }