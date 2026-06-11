import os

from dotenv import load_dotenv

load_dotenv()

DEFAULT_ALLOWED_ORIGINS = ["http://localhost:8080", "http://127.0.0.1:8080"]


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        raise ValueError(f"Missing required environment variable: {name}")
    return value.strip()


def _get_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"Environment variable {name} must be an integer.") from exc


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


def _get_allowed_origins() -> list[str]:
    value = os.getenv("CET_CORS_ALLOWED_ORIGINS")
    if value is None or value.strip() == "":
        return DEFAULT_ALLOWED_ORIGINS[:]
    return [item.strip() for item in value.split(",") if item.strip()]


def load_config() -> dict:
    return {
        "db": {
            "host": os.getenv("CET_DB_HOST", "localhost"),
            "port": _get_int("CET_DB_PORT", 3306),
            "user": _require_env("CET_DB_USER"),
            "password": _require_env("CET_DB_PASSWORD"),
            "name": _require_env("CET_DB_NAME"),
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
            "allowed_origins": _get_allowed_origins(),
        },
    }
