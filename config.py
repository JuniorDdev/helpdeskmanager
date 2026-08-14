import os
from datetime import timedelta
from urllib.parse import quote_plus

from dotenv import load_dotenv


load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


def env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def build_database_uri():
    # Railway fornece MYSQL_URL; DATABASE_URL continua sendo a opção padrão
    # para outros provedores e para ambientes locais.
    explicit_uri = os.getenv("DATABASE_URL") or os.getenv("MYSQL_URL")
    if explicit_uri:
        # O esquema mysql:// pode selecionar um driver não instalado. O
        # projeto usa PyMySQL explicitamente em todos os ambientes.
        if explicit_uri.startswith("mysql://"):
            explicit_uri = "mysql+pymysql://" + explicit_uri[len("mysql://") :]
        return explicit_uri

    user = quote_plus(os.getenv("DB_USER") or os.getenv("MYSQLUSER", "root"))
    password = quote_plus(os.getenv("DB_PASSWORD") or os.getenv("MYSQLPASSWORD", ""))
    host = os.getenv("DB_HOST") or os.getenv("MYSQLHOST", "localhost")
    port = os.getenv("DB_PORT") or os.getenv("MYSQLPORT", "3306")
    name = os.getenv("DB_NAME") or os.getenv("MYSQLDATABASE", "helpdesk_manager")
    return f"mysql+pymysql://{user}:{password}@{host}:{port}/{name}?charset=utf8mb4"


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = build_database_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True, "pool_recycle": 280}

    DEBUG = env_bool("FLASK_DEBUG", False)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", False)
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    WTF_CSRF_TIME_LIMIT = 3600
    MAX_CONTENT_LENGTH = 8 * 1024 * 1024

    RATELIMIT_STORAGE_URI = os.getenv("RATELIMIT_STORAGE_URI", "memory://")
    RATELIMIT_HEADERS_ENABLED = True

    UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
