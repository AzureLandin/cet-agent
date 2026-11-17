from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 5000
DEFAULT_DB_PATH = os.path.join(BASE_DIR, "data", "cet_agent.db")
DEFAULT_MINERU_BASE_URL = "https://mineru.net/api/v4"
DEFAULT_ALLOWED_ORIGINS = ["http://localhost:8080", "http://127.0.0.1:8080"]


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        raise ValueError(f"Missing required environment variable: {name}")
    return value.strip()


def _get_str(name: str, default: str = "") -> str:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return value.strip()


def _get_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _get_port(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    try:
        port = int(value)
    except ValueError as exc:
        raise ValueError(f"Environment variable {name} must be an integer between 1 and 65535.") from exc
    if port < 1 or port > 65535:
        raise ValueError(f"Environment variable {name} must be between 1 and 65535.")
    return port


def _get_probability(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    try:
        probability = float(value)
    except ValueError as exc:
        raise ValueError(f"Environment variable {name} must be a number between 0 and 1.") from exc
    if probability < 0 or probability > 1:
        raise ValueError(f"Environment variable {name} must be between 0 and 1.")
    return probability


def _get_csv(name: str, default: list[str] | None = None) -> list[str]:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return list(default) if default is not None else []
    return [item.strip() for item in value.split(",") if item.strip()]


def load_config() -> dict:
    return {
        "server": {
            "host": _get_str("CET_HOST", DEFAULT_HOST),
            "port": _get_port("CET_PORT", DEFAULT_PORT),
        },
        "db": {
            "path": _get_str("CET_DB_PATH", DEFAULT_DB_PATH),
        },
        "auth": {
            "admin_usernames": _get_csv("CET_ADMIN_USERNAMES", []),
        },
        "mineru": {
            "api_key": _get_str("CET_MINERU_API_KEY", ""),
            "base_url": _get_str("CET_MINERU_BASE_URL", DEFAULT_MINERU_BASE_URL),
        },
        "model": {
            "base_url": _require_env("CET_MODEL_BASE_URL"),
            "api_key": _require_env("CET_MODEL_API_KEY"),
            "model": _require_env("CET_MODEL_NAME"),
        },
        "session": {
            "secret_key": _require_env("CET_SESSION_SECRET_KEY"),
            "cookie_secure": _get_bool("CET_COOKIE_SECURE", False),
            "auth_session_cleanup_probability": _get_probability("CET_AUTH_SESSION_CLEANUP_PROBABILITY", 0.01),
        },
        "cors": {
            "allowed_origins": _get_csv("CET_CORS_ALLOWED_ORIGINS", DEFAULT_ALLOWED_ORIGINS),
        },
    }
