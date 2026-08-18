-- =====================================================================
-- Migration: 001_picking_status
-- Created:   2026-07-15
-- Purpose:   Introduce picking status + scan audit tables.
--
-- Target:    Lakebase Postgres, schema {PGAPPNAME}_schema_{PGUSER}
--            (search_path is set by the app connection)
--
-- Safe to re-run: uses IF NOT EXISTS / IF EXISTS guards.
-- =====================================================================

BEGIN;

-- ---------------------------------------------------------------------
-- picking_status
--   One row per (order_number, kanban_number). Created lazily on first
--   write. Absence = PENDING with zero scans.
-- ---------------------------------------------------------------------
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
);

CREATE INDEX IF NOT EXISTS idx_picking_status_order
    ON picking_status (order_number);

COMMENT ON TABLE  picking_status IS
    'Per-kanban picking progress. See DATA_STANDARDS.md §9.';
COMMENT ON COLUMN picking_status.status IS
    'PENDING | OK | KSE | WARNING (see §9.2)';
COMMENT ON COLUMN picking_status.boxes_scanned IS
    'Cached counter; ground truth is COUNT(*) FROM picking_scans.';
COMMENT ON COLUMN picking_status.boxes_required IS
    'ceil(box_part_quantity / lote_size). Defaults to 1 in v1.';
COMMENT ON COLUMN picking_status.updated_by IS
    'Operator nickname (v1: hardcoded "TKLpicker"; see §5).';


-- ---------------------------------------------------------------------
-- picking_scans
--   One row per confirmed QR scan. Composite PK enforces that the same
--   physical box cannot be scanned twice within the same kanban.
--   Cross-kanban duplicates ARE permitted by design.
-- ---------------------------------------------------------------------
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
);

CREATE INDEX IF NOT EXISTS idx_picking_scans_order
    ON picking_scans (order_number);

CREATE INDEX IF NOT EXISTS idx_picking_scans_scanned_at
    ON picking_scans (scanned_at);

COMMENT ON TABLE  picking_scans IS
    'Per-scan audit log. See DATA_STANDARDS.md §9.4.';
COMMENT ON COLUMN picking_scans.label_seq IS
    '16-digit sequence from QR: YYYYMMDDHHMMSSTT (see §2.3).';
COMMENT ON COLUMN picking_scans.part_number IS
    'Canonical 14-char form (see §1.2).';
COMMENT ON COLUMN picking_scans.scanned_by IS
    'Operator nickname (v1: hardcoded "TKLpicker"; see §5).';


-- ---------------------------------------------------------------------
-- Verification queries (safe to run; no side effects)
-- ---------------------------------------------------------------------
-- SELECT table_name, column_name, data_type, is_nullable, column_default
-- FROM information_schema.columns
-- WHERE table_name IN ('picking_status', 'picking_scans')
-- ORDER BY table_name, ordinal_position;

-- SELECT conname, contype, pg_get_constraintdef(oid)
-- FROM pg_constraint
-- WHERE conrelid IN ('picking_status'::regclass, 'picking_scans'::regclass)
-- ORDER BY conrelid::text, conname;

COMMIT;


-- =====================================================================
-- Rollback (for reference — DO NOT include when applying forward):
-- =====================================================================
-- BEGIN;
-- DROP TABLE IF EXISTS picking_scans;
-- DROP TABLE IF EXISTS picking_status;
-- COMMIT;