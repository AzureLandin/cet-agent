from __future__ import annotations

import os
import httpx


def sanitize_no_proxy_env() -> None:
    """Normalize bracketed IPv6 literals (e.g. [::1]) in NO_PROXY/no_proxy for httpx<0.28.

    On macOS, proxy tools often append `[::1]` to `no_proxy`, which causes
    `httpx.URLPattern` in httpx 0.27.x to build `all://*[::1]` and raise
    `httpx.InvalidURL: Invalid port: ':1]'`.
    """
    for key in ("NO_PROXY", "no_proxy"):
        raw = os.environ.get(key)
        if not raw:
            continue
        cleaned: list[str] = []
        seen: set[str] = set()
        for part in raw.split(","):
            item = part.strip()
            if not item:
                continue
            if item.startswith("[") and item.endswith("]"):
                item = item[1:-1]
            if item not in seen:
                seen.add(item)
                cleaned.append(item)
        os.environ[key] = ",".join(cleaned)


def create_httpx_client(**kwargs) -> httpx.Client:
    """Create an httpx.Client resilient to malformed system proxy env vars."""
    sanitize_no_proxy_env()
    try:
        return httpx.Client(**kwargs)
    except (httpx.InvalidURL, ImportError):
        return httpx.Client(trust_env=False, **kwargs)
