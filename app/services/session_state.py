import time
from typing import Any, Dict, List, Optional

from app.core.settings import get_settings

_TTL_SECONDS = 60 * 60 * 6  # 6 horas
_GREETING_TTL_SECONDS = 60 * 60 * 6  # 6 horas
_state: Dict[str, Dict[str, Any]] = {}


def _now() -> float:
    return time.time()


def _purge() -> None:
    settings = get_settings()
    final_after = int(getattr(settings, "IDLE_FINAL_AFTER_MINUTES", 60)) * 60
    ttl = max(_TTL_SECONDS, final_after + 60 * 10)
    cutoff = _now() - ttl
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


def mark_user_activity(phone: str, *, channel: str) -> None:
    _purge()
    st = _state.get(phone, {})
    st["last_user_at"] = _now()
    st["channel"] = channel or "meta"
    st["followup_count"] = 0
    st.pop("followup_sent_at", None)
    st.pop("final_sent_at", None)
    st.pop("closed_at", None)
    st["updated_at"] = _now()
    _state[phone] = st


def get_idle_actions(
    *,
    now: float,
    followup_after: float,
    final_after: float,
    max_followups: int,
) -> List[Dict[str, Any]]:
    _purge()
    actions: List[Dict[str, Any]] = []
    for phone, st in _state.items():
        last_user = st.get("last_user_at")
        if not isinstance(last_user, (int, float)):
            continue
        if st.get("closed_at"):
            continue
        elapsed = now - float(last_user)
        channel = st.get("channel") or "meta"
        followup_count = int(st.get("followup_count") or 0)
        final_sent = st.get("final_sent_at")

        if elapsed >= final_after and not final_sent:
            actions.append({"phone": phone, "channel": channel, "kind": "final"})
            continue

        if elapsed >= followup_after and followup_count < max_followups:
            last_follow = st.get("followup_sent_at")
            if not isinstance(last_follow, (int, float)):
                actions.append({"phone": phone, "channel": channel, "kind": "followup"})
            elif (now - float(last_follow)) >= followup_after:
                actions.append({"phone": phone, "channel": channel, "kind": "followup"})

    return actions


def mark_followup_sent(phone: str) -> None:
    _purge()
    st = _state.get(phone, {})
    count = int(st.get("followup_count") or 0)
    st["followup_count"] = count + 1
    st["followup_sent_at"] = _now()
    st["updated_at"] = _now()
    _state[phone] = st


def close_session(phone: str) -> None:
    _purge()
    st = _state.get(phone, {})
    st["final_sent_at"] = _now()
    st["closed_at"] = _now()
    st["updated_at"] = _now()
    _state[phone] = st


def clear_session(phone: str) -> None:
    _purge()
    _state.pop(phone, None)
