"""JSON API endpoints (called by frontend JS)."""
import os
import logging
import traceback
from flask import Blueprint, jsonify, request

from services.picking_service import (
    call_supervisor_for_order,
    call_supervisor_for_kanban,
    notify_kse,
    next_cart,
    DEFAULT_OPERATOR,
)
from services.scanner_service import parse_scan_payload, ScanParseError

from database.databricks_conn import get_connection as get_sqlwh_connection
from database.iek_repository import (
    is_valid_order_number,
    fetch_pick_list,
    fetch_routes_for_order,
    fetch_dollies_for_order_route,
)
from database.picking_status_repository import (
    record_scan,
    mark_kse,
    PickingStatusError,
    DuplicateScanError,
    KanbanCompleteError,
    WrongPartError,
)

log = logging.getLogger(__name__)

api_bp = Blueprint("api", __name__)


# ======================================================================
# Selector endpoints — cascading dropdowns on landing page
# ======================================================================

@api_bp.get("/orders/<order_number>/routes")
def api_routes_for_order(order_number: str):
    """
    Return distinct routes for an order, plus the effective flag.
    Response: { ok, routes: [...], flag: 'F' | 'P' | null }
    """
    if not is_valid_order_number(order_number):
        return jsonify({"ok": False, "error": "Pedido inválido"}), 400
    try:
        result = fetch_routes_for_order(order_number)
        return jsonify({
            "ok":     True,
            "routes": result.get("routes", []),
            "flag":   result.get("flag"),
        }), 200
    except Exception as e:
        log.exception("Failed to fetch routes for %s", order_number)
        return jsonify({
            "ok": False,
            "error": f"{type(e).__name__}: {e}",
        }), 500


@api_bp.get("/orders/<order_number>/dollies")
def api_dollies_for_order(order_number: str):
    """
    Return distinct dollies for an (order, route) pair.
    Query params:
        route: may be empty (special items) — always required
        flag:  'F' or 'P' (optional; auto-resolved if absent)
    """
    if not is_valid_order_number(order_number):
        return jsonify({"ok": False, "error": "Pedido inválido"}), 400

    route = request.args.get("route", "")   # empty is meaningful
    flag = (request.args.get("flag") or "").strip().upper() or None
    if flag and flag not in ("F", "P"):
        flag = None

    try:
        dollies = fetch_dollies_for_order_route(order_number, route, flag=flag)
        return jsonify({"ok": True, "dollies": dollies}), 200
    except Exception as e:
        log.exception("Failed to fetch dollies for %s/%r", order_number, route)
        return jsonify({
            "ok": False,
            "error": f"{type(e).__name__}: {e}",
        }), 500


# ======================================================================
# Global buttons (right-side panel)
# ======================================================================

@api_bp.post("/chamar")
def chamar():
    """Global 'Chamar' — supervisor notification for the whole order."""
    data = request.get_json(silent=True) or {}
    order_number = (data.get("order_number") or "").strip()
    return jsonify(call_supervisor_for_order(order_number, DEFAULT_OPERATOR))


@api_bp.post("/proximo-carrinho")
def proximo_carrinho():
    return jsonify(next_cart())


# ======================================================================
# Per-kanban status writes (from the picking-row modal)
# ======================================================================

def _find_kanban_row(order_number: str, kanban_number: str):
    """
    Return the raw kanban row from the pick list, or None.
    Uses default flag resolution (F preferred, P fallback).
    """
    result = fetch_pick_list(order_number)
    items = result.get("items") or []
    for item in items:
        if item.get("caixa") == kanban_number:
            return item
    return None


@api_bp.post("/picking/<order_number>/<kanban_number>/scan")
def picking_scan(order_number: str, kanban_number: str):
    """Record a QR scan. Body: { "payload": "<full QR string>" }"""
    if not is_valid_order_number(order_number):
        return jsonify({"ok": False, "error": "Pedido inválido"}), 400

    data = request.get_json(silent=True) or {}
    raw = data.get("payload") or ""

    try:
        payload = parse_scan_payload(raw)
    except ScanParseError as e:
        return jsonify({"ok": False, "error": "Formato de QR inválido",
                        "detail": str(e)}), 400

    kanban_row = _find_kanban_row(order_number, kanban_number)
    if kanban_row is None:
        return jsonify({"ok": False, "error": "Kanban não encontrado"}), 404

    expected_pn = kanban_row.get("part_number", "")

    try:
        result = record_scan(
            order_number=order_number,
            kanban_number=kanban_number,
            expected_part_number=expected_pn,
            scanned_part_number=payload.part_number,
            label_seq=payload.label_seq,
            scanned_by=DEFAULT_OPERATOR,
            boxes_required=1,
        )
        result["ok"] = True
        return jsonify(result), 200

    except PickingStatusError as e:
        return jsonify({"ok": False, "error": str(e)}), e.http_status
    except Exception as e:
        log.exception("Scan failed for order=%s kanban=%s", order_number, kanban_number)
        return jsonify({
            "ok": False,
            "error": f"{type(e).__name__}: {e}",
        }), 500


@api_bp.post("/picking/<order_number>/<kanban_number>/kse")
def picking_kse(order_number: str, kanban_number: str):
    """Mark a kanban as KSE. Notifies supervisor."""
    if not is_valid_order_number(order_number):
        return jsonify({"ok": False, "error": "Pedido inválido"}), 400

    kanban_row = _find_kanban_row(order_number, kanban_number)
    if kanban_row is None:
        return jsonify({"ok": False, "error": "Kanban não encontrado"}), 404

    part_number = kanban_row.get("part_number", "")
    box_part_qty = int(kanban_row.get("qtd") or 0)
    lote_size = 1  # v1

    try:
        result = mark_kse(
            order_number=order_number,
            kanban_number=kanban_number,
            updated_by=DEFAULT_OPERATOR,
            boxes_required=1,
        )

        parts_lacking = max(
            0, box_part_qty - (result["boxes_scanned"] * lote_size)
        )
        result["parts_lacking"] = parts_lacking

        notify_kse(
            order_number=order_number,
            kanban_number=kanban_number,
            part_number=part_number,
            parts_lacking=parts_lacking,
            operator=DEFAULT_OPERATOR,
        )

        result["ok"] = True
        return jsonify(result), 200

    except Exception as e:
        log.exception("KSE failed for order=%s kanban=%s", order_number, kanban_number)
        return jsonify({
            "ok": False,
            "error": f"{type(e).__name__}: {e}",
        }), 500


@api_bp.post("/picking/<order_number>/<kanban_number>/call")
def picking_call(order_number: str, kanban_number: str):
    """Chamar operador for a specific kanban. Does not change status."""
    if not is_valid_order_number(order_number):
        return jsonify({"ok": False, "error": "Pedido inválido"}), 400

    kanban_row = _find_kanban_row(order_number, kanban_number)
    if kanban_row is None:
        return jsonify({"ok": False, "error": "Kanban não encontrado"}), 404

    part_number = kanban_row.get("part_number", "")
    result = call_supervisor_for_kanban(
        order_number=order_number,
        kanban_number=kanban_number,
        part_number=part_number,
        operator=DEFAULT_OPERATOR,
    )
    return jsonify(result), 200


# ======================================================================
# Diagnostics
# ======================================================================

@api_bp.get("/health")
def health():
    """SQL Warehouse connectivity check."""
    result = {
        "env": {
            "DATABRICKS_HOST": os.environ.get("DATABRICKS_HOST", "(unset)"),
            "DATABRICKS_WAREHOUSE_ID": os.environ.get("DATABRICKS_WAREHOUSE_ID", "(unset)"),
            "DATABRICKS_CLIENT_ID": "set" if os.environ.get("DATABRICKS_CLIENT_ID") else "(unset)",
        },
        "headers": {
            "X-Forwarded-Email": request.headers.get("X-Forwarded-Email", "(absent)"),
            "X-Forwarded-Access-Token": "present" if request.headers.get("X-Forwarded-Access-Token") else "(absent)",
        },
        "token_preview": None,
        "connection": None,
        "query": None,
    }

    user_token = request.headers.get("X-Forwarded-Access-Token", "")
    if user_token:
        result["token_preview"] = f"{user_token[:6]}...{user_token[-6:]} (len={len(user_token)})"

    try:
        with get_sqlwh_connection(user_access_token=user_token) as conn:
            result["connection"] = "ok"
            with conn.cursor() as cur:
                cur.execute("SELECT 1 AS test")
                row = cur.fetchone()
                result["query"] = {"success": True, "value": row[0] if row else None}
    except Exception as e:
        result["connection"] = "failed"
        chain = []
        cur_exc = e
        while cur_exc is not None:
            chain.append(f"{type(cur_exc).__name__}: {cur_exc}")
            cur_exc = cur_exc.__cause__ or cur_exc.__context__
            if len(chain) > 5:
                break
        result["query"] = {
            "success": False,
            "error": chain[0] if chain else str(e),
            "exception_chain": chain,
            "traceback": traceback.format_exc().splitlines()[-15:],
        }

    return jsonify(result), 200


@api_bp.get("/health/lakebase")
def health_lakebase():
    """Lakebase Postgres connectivity check."""
    from database.lakebase_conn import get_connection, get_schema_name

    result = {
        "env": {
            "PGENDPOINT": "(set)" if os.environ.get("PGENDPOINT") else "(unset)",
            "PGHOST":     os.environ.get("PGHOST", "(unset)"),
            "PGPORT":     os.environ.get("PGPORT", "(unset)"),
            "PGUSER":     os.environ.get("PGUSER", "(unset)"),
            "PGDATABASE": os.environ.get("PGDATABASE", "(unset)"),
            "PGAPPNAME":  os.environ.get("PGAPPNAME", "(unset)"),
        },
        "schema": None,
        "connection": None,
        "query": None,
    }

    try:
        result["schema"] = get_schema_name()

        with get_connection() as conn:
            result["connection"] = "ok"
            with conn.cursor() as cur:
                cur.execute("SELECT current_user, current_database(), current_schema(), version()")
                row = cur.fetchone()
                result["query"] = {
                    "success":          True,
                    "current_user":     row[0],
                    "current_database": row[1],
                    "current_schema":   row[2],
                    "server_version":   row[3][:80],
                }

    except Exception as e:
        result["connection"] = "failed"
        chain = []
        cur_exc = e
        while cur_exc is not None:
            chain.append(f"{type(cur_exc).__name__}: {cur_exc}")
            cur_exc = cur_exc.__cause__ or cur_exc.__context__
            if len(chain) > 5:
                break
        result["query"] = {
            "success": False,
            "error": chain[0] if chain else str(e),
            "chain": chain,
            "traceback": traceback.format_exc().splitlines()[-15:],
        }

    return jsonify(result), 200


@api_bp.get("/health/lakebase/tables")
def health_lakebase_tables():
    """Verify the picking tables exist in our schema."""
    from database.lakebase_conn import get_connection, get_schema_name

    try:
        schema = get_schema_name()
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT table_name,
                           (SELECT COUNT(*) FROM information_schema.columns c
                            WHERE c.table_schema = t.table_schema
                              AND c.table_name = t.table_name) AS col_count
                    FROM information_schema.tables t
                    WHERE table_schema = %s
                      AND table_name IN ('picking_status', 'picking_scans')
                    ORDER BY table_name
                """, [schema])
                tables = [{"name": r[0], "columns": r[1]} for r in cur.fetchall()]

        return jsonify({
            "ok": True,
            "schema": schema,
            "tables": tables,
        }), 200

    except Exception as e:
        return jsonify({
            "ok": False,
            "error": f"{type(e).__name__}: {e}",
        }), 500


@api_bp.get("/debug/env")
def debug_env():
    """Show Databricks/Postgres env vars (redacted)."""
    keys = {
        k: (v if not any(s in k.upper() for s in ("SECRET", "TOKEN", "PASSWORD", "KEY"))
            else f"(set, len={len(v)})")
        for k, v in os.environ.items()
        if any(t in k.upper() for t in (
            "DATABRICKS", "SQL", "WAREHOUSE",
            "PG", "POSTGRES", "DATABASE", "LAKEBASE"
        ))
    }
    return jsonify(keys), 200