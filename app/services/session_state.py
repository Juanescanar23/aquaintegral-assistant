import time
from typing import Any, Dict, List, Optional

_TTL_SECONDS = 60 * 30  # 30 min
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
    st["line_hint"] = hint
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
