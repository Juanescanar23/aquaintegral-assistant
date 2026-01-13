from __future__ import annotations

import re
from functools import lru_cache
from typing import Set

from app.core.settings import get_settings


def _normalize_phone(value: str) -> str:
    return re.sub(r"\D", "", value or "").strip()


@lru_cache
def _allowlist() -> Set[str]:
    settings = get_settings()
    raw = settings.BOT_TEST_NUMBERS or ""
    numbers: Set[str] = set()
    for item in raw.split(","):
        cleaned = _normalize_phone(item)
        if cleaned:
            numbers.add(cleaned)
    return numbers


def is_test_mode() -> bool:
    return bool(get_settings().BOT_TEST_MODE)


def is_allowed_phone(phone: str) -> bool:
    if not is_test_mode():
        return True
    allowlist = _allowlist()
    if not allowlist:
        return True
    return _normalize_phone(phone) in allowlist


def prefix_with_test_tag(text: str) -> str:
    settings = get_settings()
    if not settings.BOT_TEST_MODE:
        return text
    tag = (settings.BOT_TEST_TAG or "").strip()
    if not tag:
        return text
    return f"{tag} {text}"
