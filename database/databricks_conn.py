"""
Databricks SQL connection helper.

Uses PAT from DATABRICKS_TOKEN env var (set via app.yaml in Databricks Apps).
"""

import os
import logging
from contextlib import contextmanager

from databricks import sql

log = logging.getLogger(__name__)

DATABRICKS_HOST = os.environ.get("DATABRICKS_HOST", "").replace("https://", "").rstrip("/")
DATABRICKS_WAREHOUSE_ID = os.environ.get("DATABRICKS_WAREHOUSE_ID", "")
DATABRICKS_TOKEN = os.environ.get("DATABRICKS_TOKEN", "")

HTTP_PATH = (
    f"/sql/1.0/warehouses/{DATABRICKS_WAREHOUSE_ID}"
    if DATABRICKS_WAREHOUSE_ID
    else os.environ.get("DATABRICKS_HTTP_PATH", "")
)


@contextmanager
def get_connection(user_access_token=None):
    """
    Open a Databricks SQL connection using PAT from env.

    `user_access_token` is accepted for API compatibility but ignored —
    we always use the PAT.
    """
    if not DATABRICKS_HOST:
        raise RuntimeError("DATABRICKS_HOST env var is not set")
    if not HTTP_PATH:
        raise RuntimeError("DATABRICKS_WAREHOUSE_ID env var is not set")
    if not DATABRICKS_TOKEN:
        raise RuntimeError("DATABRICKS_TOKEN env var is not set")

    log.info("Databricks SQL connect (PAT) → %s%s", DATABRICKS_HOST, HTTP_PATH)

    conn = sql.connect(
        server_hostname=DATABRICKS_HOST,
        http_path=HTTP_PATH,
        access_token=DATABRICKS_TOKEN,
    )
    try:
        yield conn
    finally:
        conn.close()