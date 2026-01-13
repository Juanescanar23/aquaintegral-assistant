from __future__ import annotations

import asyncio
import re
import time
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

from app.services.woocommerce import woocommerce_client


_CACHE_TTL_SECONDS = 60 * 10  # 10 min
_MAX_PAGES = 30              # 30 * 100 = 3000 productos max (sobrado para 860)
_PER_PAGE = 100

_lock = asyncio.Lock()
_cache_updated_at: float = 0.0
_cache_products: List[Dict[str, Any]] = []
_cache_tokens_by_id: Dict[int, set[str]] = {}


def _now() -> float:
    return time.time()


def _norm(s: str) -> str:
    s = (s or "").strip().lower()
    s = "".join(
        ch for ch in unicodedata.normalize("NFD", s)
        if unicodedata.category(ch) != "Mn"
    )
    s = re.sub(r"\s+", " ", s)
    return s


def _tokenize(s: str) -> List[str]:
    s = _norm(s)
    parts = re.split(r"[^a-z0-9]+", s)
    return [p for p in parts if len(p) >= 3]


def _product_text(p: Dict[str, Any]) -> str:
    name = p.get("name") or ""
    short_desc = p.get("short_description") or ""
    cats = p.get("categories") or []
    cat_names = " ".join([c.get("name", "") for c in cats if isinstance(c, dict)])
    return f"{name} {cat_names} {short_desc}"


def _expand_query_tokens(query: str, line_hint: Optional[str]) -> List[str]:
    """
    Expansión mínima (NO inventa): solo agrega tokens de búsqueda reales para cubrir términos genéricos.
    """
    qn = _norm(query)
    extra: List[str] = []

    # filtración -> filtro/cartucho/arena/válvula
    if "filtracion" in qn or "filtración" in query.lower() or "filtro" in qn:
        extra += ["filtro", "filtros", "filtracion", "cartucho", "arena", "valvula"]

    # producto químico piscina -> cloro/ph/alguicida/clarificador
    if ("quimic" in qn or "químic" in query.lower()) and (line_hint == "piscinas" or "piscin" in qn):
        extra += ["cloro", "ph", "alguicida", "clarificador", "reductor", "incrementador", "acidet"]

    # si estás en piscinas, boost por tokens típicos del catálogo
    if line_hint == "piscinas":
        extra += ["piscina", "piscinas"]

    toks = _tokenize(query) + extra
    # dedup
    seen = set()
    out: List[str] = []
    for t in toks:
        k = _norm(t)
        if k and k not in seen:
            seen.add(k)
            out.append(k)
    return out


async def _refresh_catalog_if_needed() -> None:
    global _cache_updated_at, _cache_products, _cache_tokens_by_id

    if _cache_products and (_now() - _cache_updated_at) < _CACHE_TTL_SECONDS:
        return

    async with _lock:
        if _cache_products and (_now() - _cache_updated_at) < _CACHE_TTL_SECONDS:
            return

        products: List[Dict[str, Any]] = []
        page = 1

        while page <= _MAX_PAGES:
            batch = await woocommerce_client.list_products(per_page=_PER_PAGE, page=page)
            if not batch:
                break

            products.extend(batch)

            if len(batch) < _PER_PAGE:
                break

            page += 1

        tokens_by_id: Dict[int, set[str]] = {}
        for p in products:
            pid = p.get("id")
            if not isinstance(pid, int):
                continue
            toks = set(_tokenize(_product_text(p)))
            tokens_by_id[pid] = toks

        _cache_products = products
        _cache_tokens_by_id = tokens_by_id
        _cache_updated_at = _now()


def _score(pid: int, qtokens: List[str], line_hint: Optional[str]) -> int:
    ptoks = _cache_tokens_by_id.get(pid, set())
    score = 0
    for t in qtokens:
        if t in ptoks:
            score += 3

    # pequeño boost si coincide la línea (por tokens)
    if line_hint and _norm(line_hint) in ptoks:
        score += 2

    return score


async def search_catalog(query: str, *, line_hint: Optional[str], limit: int = 50) -> List[Dict[str, Any]]:
    """
    Devuelve candidatos ordenados por score (ranking local).
    """
    await _refresh_catalog_if_needed()

    qtokens = _expand_query_tokens(query, line_hint)

    ranked: List[Tuple[int, Dict[str, Any]]] = []
    for p in _cache_products:
        pid = p.get("id")
        if not isinstance(pid, int):
            continue
        s = _score(pid, qtokens, line_hint)
        if s > 0:
            ranked.append((s, p))

    ranked.sort(key=lambda x: x[0], reverse=True)
    return [p for _, p in ranked[:limit]]
