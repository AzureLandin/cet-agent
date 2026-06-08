import os
import yaml


DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.yaml")

REQUIRED_KEYS = [
    ("db", "host"),
    ("db", "port"),
    ("db", "user"),
    ("db", "password"),
    ("db", "name"),
    ("model", "base_url"),
    ("model", "api_key"),
    ("model", "model"),
    ("session", "secret_key"),
]


def load_config(path: str = DEFAULT_CONFIG_PATH) -> dict:
    if not os.path.isfile(path):
        raise FileNotFoundError(
            f"Config file not found: {path}. "
            "Please copy config.yaml.example to config.yaml and fill in your settings."
        )

    with open(path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    if not isinstance(config, dict):
        raise ValueError("Config file must contain a YAML mapping.")

    for section, key in REQUIRED_KEYS:
        if section not in config or key not in config[section]:
            raise ValueError(f"Missing required config key: {section}.{key}")

    return config
