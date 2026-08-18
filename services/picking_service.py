"""Picking domain logic — bridges routes ↔ database repositories."""
import logging
from typing import Tuple, List, Dict, Any, Optional

from database.iek_repository import fetch_pick_list, is_valid_order_number
from database.picking_status_repository import (
    fetch_statuses_for_order,
    DEFAULT_STATUS,
)

log = logging.getLogger(__name__)

# v1: hardcoded operator nickname per DATA_STANDARDS §5 (deferred).
DEFAULT_OPERATOR = "TKLpicker"


def _empty_info(order_number: Optional[str] = None,
                message: str = "Aguardando pedido",
                route: Optional[str] = None,
                dolly: Optional[str] = None,
                flag: Optional[str] = None) -> Dict[str, Any]:
    return {
        "operador":         "—",
        "operador_status":  "—",
        "numero_pedido":    order_number or "—",
        "lane":             "—",
        "rota":             ("(Sem rota)" if route == "" else (route or "—")),
        "dolly":            dolly or "—",
        "caixas_restantes": 0,
        "mensagem":         message,
        "flag":             flag,             # 'F' | 'P' | None
        "is_provisional":   flag == "P",
    }


def _enrich_with_status(items: List[Dict[str, Any]], order_number: str) -> None:
    """In-place enrichment: adds status, boxes_scanned, boxes_required."""
    if not items:
        return

    try:
        statuses = fetch_statuses_for_order(order_number)
    except Exception:
        log.exception("Failed to fetch statuses for %s; defaulting all to PENDING",
                      order_number)
        statuses = {}

    for item in items:
        kanban = item.get("caixa", "")
        row = statuses.get(kanban)
        if row:
            item["boxes_scanned"]   = int(row.get("boxes_scanned") or 0)
            item["boxes_required"]  = int(row.get("boxes_required") or 1)
        else:
            item["status"]          = DEFAULT_STATUS
            item["boxes_scanned"]   = 0
            item["boxes_required"]  = 1


def get_picking_data(
    order_number: Optional[str] = None,
    route: Optional[str] = None,
    dolly: Optional[str] = None,
    flag: Optional[str] = None,
    user_access_token: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Return (items, info) for the picking screen.

    `flag` may be 'F', 'P', or None. If None, the repository resolves the
    effective flag automatically (prefers F, falls back to P).
    """
    if not order_number:
        return [], _empty_info()

    if not is_valid_order_number(order_number):
        log.warning("Invalid order number requested: %r", order_number)
        return [], _empty_info(order_number, f"Pedido inválido: {order_number}")

    try:
        result = fetch_pick_list(
            order_number,
            route=route,
            dolly=dolly,
            flag=flag,
            user_access_token=user_access_token,
        )
    except Exception as e:
        log.exception("Failed to fetch pick list for %s", order_number)
        err_msg = f"{type(e).__name__}: {e}"
        return [], _empty_info(order_number,
                               f"Erro ao buscar pedido: {err_msg}",
                               route=route, dolly=dolly)

    effective_flag = result.get("flag")
    items = result.get("items") or []

    for item in items:
        item.setdefault("back", "—")

    _enrich_with_status(items, order_number)

    info = _empty_info(order_number, route=route, dolly=dolly,
                       flag=effective_flag)
    info["caixas_restantes"] = sum(
        1 for item in items if item.get("status") != "OK"
    )
    info["lane"] = order_number[-2:]
    info["operador"] = DEFAULT_OPERATOR
    info["mensagem"] = "OK" if items else "Pedido vazio"

    return items, info


# ----------------------------------------------------------------------
# Supervisor notifications
# ----------------------------------------------------------------------
# v1: log-only implementation. Notification channel (Teams / Slack / DB write)
# to be decided later. API contract (§9.5 / §9.7) stays stable across changes.

def call_supervisor_for_order(order_number: str, operator: str) -> Dict[str, Any]:
    """Global 'Chamar' button — sends order/lane info only."""
    log.info(
        "SUPERVISOR_CALL event=ORDER_CALL order=%s operator=%s",
        order_number, operator,
    )
    return {"ok": True, "notified": True, "event": "ORDER_CALL"}


def call_supervisor_for_kanban(
    order_number: str,
    kanban_number: str,
    part_number: str,
    operator: str,
) -> Dict[str, Any]:
    """Per-kanban 'Chamar operador' button from the status modal."""
    log.info(
        "SUPERVISOR_CALL event=OPERATOR_CALL order=%s kanban=%s part=%s operator=%s",
        order_number, kanban_number, part_number, operator,
    )
    return {"ok": True, "notified": True, "event": "OPERATOR_CALL"}


def notify_kse(
    order_number: str,
    kanban_number: str,
    part_number: str,
    parts_lacking: int,
    operator: str,
) -> None:
    """Fire-and-forget supervisor notification when a kanban is marked KSE."""
    log.info(
        "SUPERVISOR_CALL event=KANBAN_KSE order=%s kanban=%s part=%s "
        "parts_lacking=%d operator=%s",
        order_number, kanban_number, part_number, parts_lacking, operator,
    )


# ----------------------------------------------------------------------
# Legacy compatibility
# ----------------------------------------------------------------------

def next_cart() -> Dict[str, Any]:
    """TODO: advance to next cart in the route."""
    return {"status": "ok", "next_cart": "D02"}


def call_supervisor() -> Dict[str, Any]:
    """Legacy shim — routes/api.py used this name for the global button."""
    return call_supervisor_for_order(order_number="unknown", operator=DEFAULT_OPERATOR)