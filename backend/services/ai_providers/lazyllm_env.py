"""Utilities for resolving LazyLLM API keys from vendor-prefixed env vars."""
import json
import os

ALLOWED_LAZYLLM_VENDORS = frozenset({
    'qwen', 'doubao', 'deepseek', 'glm', 'siliconflow',
    'sensenova', 'minimax', 'openai', 'kimi',
})


def collect_env_lazyllm_api_keys() -> str | None:
    """Scan env vars for {VENDOR}_API_KEY and return JSON string, or None."""
    keys = {}
    for vendor in ALLOWED_LAZYLLM_VENDORS:
        val = os.getenv(f"{vendor.upper()}_API_KEY", "")
        if val:
            keys[vendor] = val
    return json.dumps(keys) if keys else None


def get_lazyllm_api_key(source: str, namespace: str = "BANANA") -> str:
    """
    Resolve API key for a LazyLLM source from vendor-prefixed key only.

    Expected format: {SOURCE}_API_KEY, e.g. QWEN_API_KEY.
    """
    source_upper = (source or "").upper()
    if not source_upper:
        return ""
    from services.provider_config import active_provider_snapshot
    snapshot = active_provider_snapshot()
    if snapshot is not None:
        return snapshot.values.get(f"{source_upper}_API_KEY", "")
    return os.getenv(f"{source_upper}_API_KEY", "")


def ensure_lazyllm_namespace_key(source: str, namespace: str = "BANANA") -> bool:
    """Compatibility probe. Credentials are now supplied directly to OnlineModule."""
    return bool(get_lazyllm_api_key(source, namespace))
