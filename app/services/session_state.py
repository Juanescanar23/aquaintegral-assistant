import time
from typing import Any, Dict, List, Optional

_TTL_SECONDS = 60 * 30  # 30 min
_GREETING_TTL_SECONDS = 60 * 60 * 6  # 6 horas
_state: Dict[str, Dict[str, Any]] = {}


def _now() -> float:
    return time.time()


def _purge() -> None:
    cutoff = _now() - _TTL_SECONDS
    dead = [k for k, v in _state.items() if float(v.get("updated_at", 0.0)) < cutoff]
    for k in dead:
        _state.pop(k, None)


def set_line_hint(phone: str, hint: str) -> None:
    _purge()
    st = _state.get(phone, {})
    prev_hint = st.get("line_hint")
    st["line_hint"] = hint
    if prev_hint and prev_hint != hint:
        st.pop("consult_questions", None)
    st["updated_at"] = _now()
    _state[phone] = st


def get_line_hint(phone: str) -> Optional[str]:
    _purge()
    st = _state.get(phone)
    if not st:
        return None
    v = st.get("line_hint")
    return v if isinstance(v, str) else None


def set_last_candidates(phone: str, products: List[Dict[str, Any]]) -> None:
    """
    Guarda los últimos productos resumidos (los que ya devolviste al usuario).
    Así el usuario puede responder '1/2/3' y tú lo interpretas como selección.
    """
    _purge()
    st = _state.get(phone, {})
    st["pending_mode"] = "products"
    st["candidates"] = products[:5]
    st["updated_at"] = _now()
    _state[phone] = st


def clear_last_candidates(phone: str) -> None:
    _purge()
    st = _state.get(phone)
    if not st:
        return
    st.pop("pending_mode", None)
    st.pop("candidates", None)
    st["updated_at"] = _now()
    _state[phone] = st


def get_candidate_by_choice(phone: str, choice_1_based: int) -> Optional[Dict[str, Any]]:
    _purge()
    st = _state.get(phone)
    if not st or st.get("pending_mode") != "products":
        return None
    candidates = st.get("candidates")
    if not isinstance(candidates, list):
        return None
    idx = choice_1_based - 1
    if idx < 0 or idx >= len(candidates):
        return None
    c = candidates[idx]
    return c if isinstance(c, dict) else None


def should_greet(phone: str) -> bool:
    _purge()
    st = _state.get(phone, {})
    last = st.get("greeted_at")
    if not isinstance(last, (int, float)):
        return True
    return (_now() - float(last)) > _GREETING_TTL_SECONDS


def mark_greeted(phone: str) -> None:
    _purge()
    st = _state.get(phone, {})
    st["greeted_at"] = _now()
    st["updated_at"] = _now()
    _state[phone] = st


def set_search_pool(phone: str, query: str, products: List[Dict[str, Any]], *, batch_size: int = 3) -> None:
    _purge()
    st = _state.get(phone, {})
    st["search_query"] = query
    st["search_results"] = products[:15]
    st["search_offset"] = min(batch_size, len(st["search_results"]))
    st["updated_at"] = _now()
    _state[phone] = st


def get_next_search_results(phone: str, *, batch_size: int = 3) -> List[Dict[str, Any]]:
    _purge()
    st = _state.get(phone)
    if not st:
        return []
    results = st.get("search_results")
    if not isinstance(results, list):
        return []
    offset = st.get("search_offset")
    try:
        offset_value = int(offset)
    except Exception:
        offset_value = 0
    if offset_value >= len(results):
        return []
    next_chunk = results[offset_value : offset_value + batch_size]
    st["search_offset"] = offset_value + len(next_chunk)
    st["updated_at"] = _now()
    _state[phone] = st
    return [p for p in next_chunk if isinstance(p, dict)]


def clear_search_pool(phone: str) -> None:
    _purge()
    st = _state.get(phone)
    if not st:
        return
    st.pop("search_results", None)
    st.pop("search_offset", None)
    st.pop("search_query", None)
    st["updated_at"] = _now()
    _state[phone] = st


def get_consult_questions(phone: str) -> List[str]:
    _purge()
    st = _state.get(phone, {})
    items = st.get("consult_questions")
    if not isinstance(items, list):
        return []
    out: List[str] = []
    for item in items:
        if isinstance(item, str) and item:
            out.append(item)
    return out


def add_consult_question(phone: str, key: str) -> None:
    if not key:
        return
    _purge()
    st = _state.get(phone, {})
    items = st.get("consult_questions")
    if not isinstance(items, list):
        items = []
    if key not in items:
        items.append(key)
    st["consult_questions"] = items
    st["updated_at"] = _now()
    _state[phone] = st


def set_customer_name(phone: str, name: str) -> None:
    if not name:
        return
    _purge()
    st = _state.get(phone, {})
    st["customer_name"] = name
    st["updated_at"] = _now()
    _state[phone] = st


def get_customer_name(phone: str) -> Optional[str]:
    _purge()
    st = _state.get(phone)
    if not st:
        return None
    name = st.get("customer_name")
    return name if isinstance(name, str) and name.strip() else None
