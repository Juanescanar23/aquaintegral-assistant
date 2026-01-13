import time
from typing import Any, Dict, Optional

_DEFAULT_TTL_SECONDS = 15 * 60
_store: Dict[str, Dict[str, Any]] = {}


def get_state(phone: str) -> Optional[Dict[str, Any]]:
    item = _store.get(phone)
    if not item:
        return None
    if item["expires_at"] < time.time():
        _store.pop(phone, None)
        return None
    return item["data"]


def set_state(phone: str, data: Dict[str, Any], ttl_seconds: int = _DEFAULT_TTL_SECONDS) -> None:
    _store[phone] = {"data": data, "expires_at": time.time() + ttl_seconds}


def clear_state(phone: str) -> None:
    _store.pop(phone, None)
