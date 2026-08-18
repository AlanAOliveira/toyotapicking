"""
IEK (Internal eKanban) data access layer.

Fetches pick lists and route/dolly selectors from
tdb_prd_trusted.sorprd_iek.ekanban_orders.

Flag policy (P vs. F):
    - F = "Fixed" — order sent to downstream systems, source of truth.
    - P = "Provisional" — planned but not finalized.
    An order might have F rows, P rows, both, or (transiently) neither.
    Rule: if the order has any F rows, we use ONLY F. Otherwise we use P.
    We never mix. The chosen flag is called the "effective flag" and
    the UI shows a small "P" indicator when it's P.
"""

import logging
import re
from typing import List, Dict, Any, Optional

from database.databricks_conn import get_connection

log = logging.getLogger(__name__)

TABLE = "tdb_prd_trusted.sorprd_iek.ekanban_orders"

VALID_FLAGS = ("F", "P")

# ----------------------------------------------------------
# Order number validation
#   Format: YYYYMMDDLL (10 digits)
# ----------------------------------------------------------
ORDER_NUMBER_REGEX = re.compile(r"^\d{8}(0[1-9]|[12]\d|30)$")


def is_valid_order_number(order_number: str) -> bool:
    return bool(ORDER_NUMBER_REGEX.match(str(order_number)))


# ----------------------------------------------------------
# Part number normalization (per DATA_STANDARDS §1)
# ----------------------------------------------------------
def normalize_part_number(pn: str) -> str:
    """12-char form -> canonical 14-char (XXXXX-XXXXX-XX)."""
    if pn is None:
        return ""
    s = str(pn).strip().upper().replace("-", "")
    if len(s) == 12 and s.isalnum():
        return f"{s[:5]}-{s[5:10]}-{s[10:]}"
    if len(s) == 10 and s.isalnum():
        return f"{s[:5]}-{s[5:]}-00"
    log.warning("Unexpected part number format: %r", pn)
    return str(pn).strip()


# ----------------------------------------------------------
# Effective flag resolution
# ----------------------------------------------------------
def resolve_effective_flag(
    order_number: str,
    user_access_token: Optional[str] = None,
) -> Optional[str]:
    """
    Decide which flag to use for this order.

    Returns:
        'F'  — if the order has any F rows
        'P'  — if it has no F rows but has P rows
        None — if the order has no rows at all
    """
    if not is_valid_order_number(order_number):
        raise ValueError(f"Invalid order number: {order_number!r}")

    query = f"""
        SELECT fix_provisional_flag, COUNT(*) AS n
        FROM {TABLE}
        WHERE TRIM(order_number) = ?
          AND LENGTH(TRIM(order_number)) = 10
          AND fix_provisional_flag IN ('F', 'P')
        GROUP BY fix_provisional_flag
    """

    with get_connection(user_access_token=user_access_token) as conn:
        with conn.cursor() as cur:
            cur.execute(query, [str(order_number)])
            rows = cur.fetchall()

    counts = {row[0]: row[1] for row in rows}
    log.info("Order %s flag counts: %r", order_number, counts)

    if counts.get("F", 0) > 0:
        return "F"
    if counts.get("P", 0) > 0:
        return "P"
    return None


# ----------------------------------------------------------
# Selector queries — routes and dollies for an order
# ----------------------------------------------------------
def fetch_routes_for_order(
    order_number: str,
    flag: Optional[str] = None,
    user_access_token: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Return the distinct routes present in one order, plus the effective flag.

    Returns:
        {
            "flag":   'F' | 'P' | None,
            "routes": [str, ...],   # may include "" for special items
        }

    If `flag` is None, the effective flag is resolved automatically.
    """
    if not is_valid_order_number(order_number):
        raise ValueError(f"Invalid order number: {order_number!r}")

    if flag is None:
        flag = resolve_effective_flag(order_number, user_access_token)

    if flag is None:
        # No rows at all
        return {"flag": None, "routes": []}

    if flag not in VALID_FLAGS:
        raise ValueError(f"Invalid flag: {flag!r}")

    query = f"""
        SELECT DISTINCT
            COALESCE(TRIM(conveyance_route_internal), '') AS route
        FROM {TABLE}
        WHERE TRIM(order_number) = ?
          AND LENGTH(TRIM(order_number)) = 10
          AND fix_provisional_flag = ?
        ORDER BY route
    """

    log.info("Fetching routes for order %s (flag=%s)", order_number, flag)
    with get_connection(user_access_token=user_access_token) as conn:
        with conn.cursor() as cur:
            cur.execute(query, [str(order_number), flag])
            rows = cur.fetchall()

    routes = [row[0] for row in rows]
    log.info("Order %s (flag=%s) → %d route(s): %r",
             order_number, flag, len(routes), routes)
    return {"flag": flag, "routes": routes}


def fetch_dollies_for_order_route(
    order_number: str,
    route: str,
    flag: Optional[str] = None,
    user_access_token: Optional[str] = None,
) -> List[str]:
    """
    Return the distinct dollies present in one (order, route) pair.

    `route` may be an empty string (special items).
    If `flag` is None, it will be resolved automatically.
    """
    if not is_valid_order_number(order_number):
        raise ValueError(f"Invalid order number: {order_number!r}")

    if flag is None:
        flag = resolve_effective_flag(order_number, user_access_token)

    if flag is None:
        return []

    if flag not in VALID_FLAGS:
        raise ValueError(f"Invalid flag: {flag!r}")

    route_norm = (route or "").strip()

    query = f"""
        SELECT DISTINCT
            COALESCE(TRIM(dolly), '') AS dolly
        FROM {TABLE}
        WHERE TRIM(order_number) = ?
          AND LENGTH(TRIM(order_number)) = 10
          AND fix_provisional_flag = ?
          AND COALESCE(TRIM(conveyance_route_internal), '') = ?
        ORDER BY dolly
    """

    log.info("Fetching dollies for order %s / route %r (flag=%s)",
             order_number, route_norm, flag)
    with get_connection(user_access_token=user_access_token) as conn:
        with conn.cursor() as cur:
            cur.execute(query, [str(order_number), flag, route_norm])
            rows = cur.fetchall()

    dollies = [row[0] for row in rows if row[0]]
    log.info("Order %s / route %r (flag=%s) → %d dolly/dollies: %r",
             order_number, route_norm, flag, len(dollies), dollies)
    return dollies


# ----------------------------------------------------------
# Fetch pick list for a given (order, route, dolly)
# ----------------------------------------------------------
def fetch_pick_list(
    order_number: str,
    route: Optional[str] = None,
    dolly: Optional[str] = None,
    flag: Optional[str] = None,
    user_access_token: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Fetch the pick list for one order, optionally filtered by route + dolly.

    Returns:
        {
            "flag":  'F' | 'P' | None,
            "items": [dict, ...],
        }

    If `flag` is None, the effective flag is resolved automatically.
    """
    if not is_valid_order_number(order_number):
        raise ValueError(f"Invalid order number: {order_number!r}")

    if flag is None:
        flag = resolve_effective_flag(order_number, user_access_token)

    if flag is None:
        return {"flag": None, "items": []}

    if flag not in VALID_FLAGS:
        raise ValueError(f"Invalid flag: {flag!r}")

    where_clauses = [
        "TRIM(order_number) = ?",
        "LENGTH(TRIM(order_number)) = 10",
        "fix_provisional_flag = ?",
    ]
    params: List[Any] = [str(order_number), flag]

    if route is not None:
        where_clauses.append(
            "COALESCE(TRIM(conveyance_route_internal), '') = ?"
        )
        params.append((route or "").strip())

    if dolly is not None and dolly != "":
        where_clauses.append("COALESCE(TRIM(dolly), '') = ?")
        params.append(dolly.strip())

    where_sql = " AND ".join(where_clauses)

    query = f"""
        SELECT
            kanban_print_address  AS endereco,
            complete_part_number  AS part_number_raw,
            box_part_quantity     AS qtd,
            supplier_code         AS exporter,
            kanban_number         AS caixa,
            printing_sequence     AS printing_sequence
        FROM {TABLE}
        WHERE {where_sql}
        ORDER BY kanban_print_address ASC
    """

    log.info(
        "Fetching pick list for order=%s route=%r dolly=%r flag=%s",
        order_number, route, dolly, flag,
    )

    with get_connection(user_access_token=user_access_token) as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            rows = cur.fetchall()
            columns = [desc[0] for desc in cur.description]

    log.info(
        "Fetched %d rows for order %s (route=%r dolly=%r flag=%s)",
        len(rows), order_number, route, dolly, flag,
    )

    items = []
    for row in rows:
        record = dict(zip(columns, row))
        items.append({
            "endereco":    (record.get("endereco") or "").strip(),
            "part_number": normalize_part_number(record.get("part_number_raw")),
            "qtd":         record.get("qtd"),
            "exporter":    (record.get("exporter") or "").strip(),
            "caixa":       (record.get("caixa") or "").strip(),
            "status":      "",
        })

    return {"flag": flag, "items": items}