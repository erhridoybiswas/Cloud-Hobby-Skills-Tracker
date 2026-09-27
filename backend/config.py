"""
Application configuration.

Every value can be overridden by an environment variable so that the same
code runs locally (SQLite + local disk) and in the cloud (Postgres + S3)
without any code change.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

# Project root = one level above /backend
BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env from the project root (does nothing if the file is absent)
load_dotenv(BASE_DIR / ".env")


class Config:
    """Default (local development) configuration."""

    # --- Security ---
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me-in-production")
    JWT_ALGORITHM = "HS256"
    JWT_EXPIRES_MINUTES = int(os.getenv("JWT_EXPIRES_MINUTES", "1440"))

    # --- Database ---
    DATABASE_PATH = os.getenv("DATABASE_PATH", str(BASE_DIR / "backend" / "data" / "app.db"))

    # --- Object storage ---
    STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "local")
    UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", str(BASE_DIR / "backend" / "uploads"))
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH_MB", "5")) * 1024 * 1024
    ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp", "pdf", "txt", "md"}
    ALLOWED_FOLDERS = {"profile", "skills", "posts", "misc"}

    # --- Frontend ---
    FRONTEND_DIR = str(BASE_DIR / "frontend")

    # --- Misc ---
    JSON_SORT_KEYS = False
    PROPAGATE_EXCEPTIONS = False


class TestConfig(Config):
    """Configuration used by the pytest suite (isolated in-memory-ish DB)."""

    TESTING = True
    SECRET_KEY = "test-secret"
    DATABASE_PATH = ":memory:"