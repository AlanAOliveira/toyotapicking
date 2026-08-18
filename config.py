"""Application configuration."""
import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    DEBUG = False
    DATABRICKS_HOST = os.environ.get("DATABRICKS_HOST")
    DATABRICKS_TOKEN = os.environ.get("DATABRICKS_TOKEN")


class DevConfig(Config):
    DEBUG = True


class ProdConfig(Config):
    DEBUG = False