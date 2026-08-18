"""Main / index routes."""
from flask import Blueprint, render_template

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    """Landing page — selector for order + route + dolly."""
    return render_template("main/index.html")