"""
Lakebase schema initialization.

Run at app startup via init_lakebase_schema(). Idempotent — all statements
use IF NOT EXISTS. Safe to call on every boot.
"""

import logging
from database.lakebase_conn import get_connection, get_schema_name

log = logging.getLogger(__name__)


PICKING_STATUS_DDL = """
    CREATE TABLE IF NOT EXISTS picking_status (
        order_number    VARCHAR(10)   NOT NULL,
        kanban_number   VARCHAR(10)   NOT NULL,
        status          VARCHAR(10)   NOT NULL DEFAULT 'PENDING',
        boxes_scanned   INTEGER       NOT NULL DEFAULT 0,
        boxes_required  INTEGER       NOT NULL DEFAULT 1,
        updated_by      VARCHAR(50),
        updated_at      TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
        CONSTRAINT picking_status_pk
            PRIMARY KEY (order_number, kanban_number),
        CONSTRAINT picking_status_valid_status
            CHECK (status IN ('PENDING', 'OK', 'KSE', 'WARNING')),
        CONSTRAINT picking_status_nonneg_scanned
            CHECK (boxes_scanned >= 0),
        CONSTRAINT picking_status_positive_required
            CHECK (boxes_required >= 1)
    )
"""

PICKING_STATUS_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_picking_status_order ON picking_status (order_number)",
]

PICKING_SCANS_DDL = """
    CREATE TABLE IF NOT EXISTS picking_scans (
        order_number    VARCHAR(10)   NOT NULL,
        kanban_number   VARCHAR(10)   NOT NULL,
        label_seq       VARCHAR(16)   NOT NULL,
        part_number     VARCHAR(14)   NOT NULL,
        scanned_by      VARCHAR(50)   NOT NULL,
        scanned_at      TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
        CONSTRAINT picking_scans_pk
            PRIMARY KEY (order_number, kanban_number, label_seq),
        CONSTRAINT picking_scans_status_fk
            FOREIGN KEY (order_number, kanban_number)
            REFERENCES picking_status (order_number, kanban_number)
            ON DELETE CASCADE,
        CONSTRAINT picking_scans_label_seq_format
            CHECK (label_seq ~ '^[0-9]{16}$'),
        CONSTRAINT picking_scans_part_number_format
            CHECK (part_number ~ '^[A-Z0-9]{5}-[A-Z0-9]{5}-[A-Z0-9]{2}$')
    )
"""

PICKING_SCANS_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_picking_scans_order ON picking_scans (order_number)",
    "CREATE INDEX IF NOT EXISTS idx_picking_scans_scanned_at ON picking_scans (scanned_at)",
]


def init_lakebase_schema() -> dict:
    """
    Ensure the app's schema and all required tables exist.
    Called once at Flask startup. Idempotent.
    """
    schema = get_schema_name()
    log.info("Initializing Lakebase schema: %s", schema)

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')
            cur.execute(f'SET search_path TO "{schema}"')

            cur.execute(PICKING_STATUS_DDL)
            for stmt in PICKING_STATUS_INDEXES:
                cur.execute(stmt)

            cur.execute(PICKING_SCANS_DDL)
            for stmt in PICKING_SCANS_INDEXES:
                cur.execute(stmt)

        conn.commit()

    log.info("Lakebase schema init complete")
    return {"schema": schema, "ok": True}