"""
Lakebase (Postgres) connection helper.

Mirrors the pattern used by the ipmsorderapp project — reads pre-injected
env vars from the Database resource binding and uses a connection pool
with per-connection OAuth token minting.

Env vars auto-injected by Databricks Apps (from Database resource binding):
    PGENDPOINT   — instance endpoint identifier (used to mint credentials)
    PGHOST       — Postgres hostname
    PGPORT       — port (usually 5432)
    PGUSER       — username (the app's service principal)
    PGDATABASE   — database name (usually 'databricks_postgres')
    PGSSLMODE    — usually 'require'
    PGAPPNAME    — used as part of the schema name

Schema:
    Each app gets its own Postgres schema, named {PGAPPNAME}_schema_{PGUSER}
    (with hyphens stripped from PGUSER).
"""

import os
import logging
import threading
from contextlib import contextmanager
from typing import Optional

import psycopg
from psycopg_pool import ConnectionPool
from databricks.sdk import WorkspaceClient
from databricks.sdk.core import Config

log = logging.getLogger(__name__)

_pool: Optional[ConnectionPool] = None
_pool_lock = threading.Lock()

_schema_cache: Optional[str] = None


def _get_workspace_client() -> WorkspaceClient:
    """
    Build a SDK client using OAuth (service principal) only — ignoring the
    PAT that DATABRICKS_TOKEN carries for the SQL Warehouse.
    """
    host = os.environ.get("DATABRICKS_HOST", "")
    client_id = os.environ.get("DATABRICKS_CLIENT_ID", "")
    client_secret = os.environ.get("DATABRICKS_CLIENT_SECRET", "")

    if not client_id or not client_secret:
        raise RuntimeError(
            "DATABRICKS_CLIENT_ID / DATABRICKS_CLIENT_SECRET not injected. "
            "Are we running inside a Databricks App with proper permissions?"
        )

    cfg = Config(
        host=host,
        client_id=client_id,
        client_secret=client_secret,
        auth_type="oauth-m2m",
    )
    return WorkspaceClient(config=cfg)


class _OAuthConnection(psycopg.Connection):
    """psycopg Connection subclass that mints a fresh OAuth token per connection."""

    @classmethod
    def connect(cls, conninfo="", **kwargs):
        endpoint = os.getenv("PGENDPOINT", "")
        if not endpoint:
            raise RuntimeError("PGENDPOINT env var is not set")

        ws = _get_workspace_client()
        cred = ws.postgres.generate_database_credential(endpoint=endpoint)
        kwargs["password"] = cred.token
        return super().connect(conninfo, **kwargs)


def _get_pool() -> ConnectionPool:
    """Lazily create and return the shared connection pool."""
    global _pool
    if _pool is not None:
        return _pool

    with _pool_lock:
        if _pool is not None:
            return _pool

        required = ["PGHOST", "PGPORT", "PGUSER", "PGDATABASE"]
        missing = [k for k in required if not os.getenv(k)]
        if missing:
            raise RuntimeError(f"Missing Postgres env vars: {missing}")

        conn_string = (
            f"dbname={os.getenv('PGDATABASE')} "
            f"user={os.getenv('PGUSER')} "
            f"host={os.getenv('PGHOST')} "
            f"port={os.getenv('PGPORT')} "
            f"sslmode={os.getenv('PGSSLMODE', 'require')} "
            f"application_name={os.getenv('PGAPPNAME', 'toyotapicking')}"
        )

        log.info("Lakebase pool init → %s@%s/%s",
                 os.getenv("PGUSER"), os.getenv("PGHOST"), os.getenv("PGDATABASE"))

        _pool = ConnectionPool(
            conn_string,
            connection_class=_OAuthConnection,
            min_size=1,
            max_size=5,
            open=True,
        )
        return _pool


@contextmanager
def get_connection():
    """Context manager yielding a pooled Lakebase Postgres connection."""
    pool = _get_pool()
    with pool.connection() as conn:
        yield conn


def get_schema_name() -> str:
    """
    Return the app's Postgres schema name.

    Format: {PGAPPNAME}_schema_{PGUSER}  (with hyphens stripped from PGUSER)
    Matches the pattern used by ipmsorderapp.
    """
    global _schema_cache
    if _schema_cache is not None:
        return _schema_cache

    pgappname = os.getenv("PGAPPNAME", "toyotapicking")
    pguser = os.getenv("PGUSER", "").replace("-", "")

    if not pguser:
        raise RuntimeError("PGUSER env var is not set")

    _schema_cache = f"{pgappname}_schema_{pguser}"
    log.info("Lakebase schema: %s", _schema_cache)
    return _schema_cache


@contextmanager
def get_connection_with_schema():
    """Like get_connection(), but SETs search_path to the app's schema first."""
    schema = get_schema_name()
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(f'SET search_path TO "{schema}"')
        yield conn