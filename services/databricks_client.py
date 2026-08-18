"""Databricks connection helper."""
import os


class DatabricksClient:
    def __init__(self):
        self.host = os.environ.get("DATABRICKS_HOST")
        self.token = os.environ.get("DATABRICKS_TOKEN")

    def query(self, sql: str):
        # TODO: implement using databricks-sql-connector or SDK
        raise NotImplementedError