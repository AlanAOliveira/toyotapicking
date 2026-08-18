"""Picking screen routes."""
from flask import Blueprint, render_template, request
from services.picking_service import get_picking_data

picking_bp = Blueprint("picking", __name__)


@picking_bp.route("/")
@picking_bp.route("/<order_number>")
def picking_screen(order_number: str = None):
    if not order_number:
        order_number = request.args.get("order")

    # Optional filters from the selector
    route = request.args.get("route")   # may be "" (special items) or None
    dolly = request.args.get("dolly")   # may be None
    flag  = request.args.get("flag")    # 'F', 'P', or None (auto-resolve)

    # Normalize flag: accept F/P (case-insensitive), reject anything else
    if flag:
        flag = flag.strip().upper()
        if flag not in ("F", "P"):
            flag = None

    # Databricks Apps injects the logged-in user's OAuth token here
    user_token = request.headers.get("X-Forwarded-Access-Token")

    items, info = get_picking_data(
        order_number,
        route=route,
        dolly=dolly,
        flag=flag,
        user_access_token=user_token,
    )
    return render_template("picking/picking.html", items=items, info=info)