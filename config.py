"""
config.py — Centralised Flask configuration.
Loaded by app.py via app.config.from_object(config.get_config()).
"""
import os
from dotenv import load_dotenv

load_dotenv()  # loads .env if present (ignored in production)


def _resolve_db_url():
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        # Zero-config SQLite fallback for local dev
        base = os.path.abspath(os.path.dirname(__file__))
        return f"sqlite:///{os.path.join(base, 'billsplitter.db')}"
    # Railway injects mysql:// — SQLAlchemy needs mysql+pymysql://
    if url.startswith("mysql://"):
        url = url.replace("mysql://", "mysql+pymysql://", 1)
    return url


class BaseConfig:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_DATABASE_URI = _resolve_db_url()
    CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "*")
    JSON_SORT_KEYS = False


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    SQLALCHEMY_ECHO = False   # set True to log all SQL queries


class ProductionConfig(BaseConfig):
    DEBUG = False
    # Enforce HTTPS redirects when behind a proxy (e.g. Railway / Vercel)
    PREFERRED_URL_SCHEME = "https"


class TestingConfig(BaseConfig):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False


_CONFIGS = {
    "development": DevelopmentConfig,
    "production":  ProductionConfig,
    "testing":     TestingConfig,
}


def get_config():
    env = os.environ.get("FLASK_ENV", "production")
    return _CONFIGS.get(env, ProductionConfig)
