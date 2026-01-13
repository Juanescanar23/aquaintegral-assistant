import re
import unicodedata
from typing import Optional, Tuple, List, Dict, Any, Sequence

from app.domain.playbook import WELCOME_MESSAGE
from app.services.openai_product_query import build_product_search_plan
from app.services.woocommerce import woocommerce_client
from app.services.catalog_cache import search_catalog
from app.utils.formatting import format_cop

try:
    from app.services.openai_rerank import rerank_products
except Exception:  # pragma: no cover - optional dependency
    rerank_products = None


_STOPWORDS = {
    "a",
    "al",
    "algo",
    "alguien",
    "as",
    "con",
    "como",
    "cual",
    "cuando",
    "de",
    "del",
    "donde",
    "el",
    "ella",
    "ellos",
    "en",
    "es",
    "esta",
    "estoy",
    "fue",
    "ha",
    "hola",
    "las",
    "lo",
    "los",
    "la",
    "me",
    "mi",
    "mis",
    "necesito",
    "quiero",
    "que",
    "para",
    "por",
    "ser",
    "si",
    "sin",
    "su",
    "sus",
    "una",
    "un",
    "unos",
    "unas",
    "y",
    "o",
}

_BROAD_TERMS = {
    "agua",
    "aguas",
    "equipo",
    "equipos",
    "producto",
    "productos",
    "sistema",
    "sistemas",
    "linea",
    "lineas",
    "piscina",
    "piscinas",
    "servicio",
    "servicios",
}

_SHORT_TERMS = {"uv", "ph"}


def _normalize(text: str) -> str:
    t = (text or "").strip().lower()
    t = "".join(
        ch for ch in unicodedata.normalize("NFD", t)
        if unicodedata.category(ch) != "Mn"
    )
    t = re.sub(r"\s+", " ", t)
    return t


def _keyword_queries(text: str) -> List[str]:
    norm = _normalize(text)
    if not norm:
        return []

    keywords: List[str] = []
    if "bomba" in norm or "bombeo" in norm:
        keywords.append("bomba")
    if "piscin" in norm:
        keywords.append("piscina")
    if "filtro" in norm or "filtracion" in norm:
        keywords.append("filtro")
    if "cartucho" in norm:
        keywords.append("cartucho")
    if "arena" in norm:
        keywords.append("arena")
    if "cloro" in norm:
        keywords.append("cloro")
    if "alguicida" in norm:
        keywords.append("alguicida")
    if "clarificador" in norm:
        keywords.append("clarificador")
    if "dosificador" in norm or "dosificacion" in norm:
        keywords.append("dosificador")
    if "osmosis" in norm:
        keywords.append("osmosis")
    if "uv" in norm or "ultravioleta" in norm:
        keywords.append("ultravioleta")
    if "fotometro" in norm:
        keywords.append("fotometro")
    if "turbid" in norm:
        keywords.append("turbidimetro")

    # dedup manteniendo orden
    seen = set()
    out: List[str] = []
    for k in keywords:
        if k not in seen:
            seen.add(k)
            out.append(k)
    return out


def _extract_specific_terms(text: str) -> List[str]:
    norm = _normalize(text)
    if not norm:
        return []
    tokens = re.findall(r"[a-z0-9]+", norm)
    terms: List[str] = []
    for t in tokens:
        if t.isdigit():
            continue
        if len(t) < 4 and t not in _SHORT_TERMS:
            continue
        if t in _STOPWORDS or t in _BROAD_TERMS:
            continue
        terms.append(t)
    # dedup
    seen = set()
    out: List[str] = []
    for t in terms:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


def _required_groups_from_text(text: str) -> List[List[str]]:
    norm = _normalize(text)
    if not norm:
        return []

    groups: List[List[str]] = []

    if "bomba" in norm or "bombeo" in norm or "motobomba" in norm:
        groups.append(["bomba", "bombeo", "motobomba"])
    if "filtro" in norm or "filtracion" in norm:
        groups.append(["filtro", "filtracion"])
    if "piscin" in norm:
        groups.append(["piscina", "piscinas"])
    if "cartucho" in norm:
        groups.append(["cartucho", "cartuchos"])
    if "arena" in norm:
        groups.append(["arena"])
    if "cloro" in norm:
        groups.append(["cloro"])
    if "alguicida" in norm:
        groups.append(["alguicida"])
    if "clarificador" in norm:
        groups.append(["clarificador"])
    if "dosificador" in norm or "dosificacion" in norm:
        groups.append(["dosificador", "dosificacion", "dosificar"])
    if "osmosis" in norm:
        groups.append(["osmosis", "osmosis inversa"])
    if "uv" in norm or "ultravioleta" in norm:
        groups.append(["uv", "ultravioleta"])
    if "fotometro" in norm:
        groups.append(["fotometro"])
    if "turbid" in norm:
        groups.append(["turbidimetro", "turbidez"])

    # Dedup por contenido
    seen = set()
    out: List[List[str]] = []
    for g in groups:
        key = tuple(g)
        if key in seen:
            continue
        seen.add(key)
        out.append(g)
    return out


def _matches_required_groups(text: str, groups: List[List[str]]) -> bool:
    if not groups:
        return True
    norm = _normalize(text)
    for group in groups:
        if not any(token in norm for token in group):
            return False
    return True


def _matches_specific_terms(text: str, terms: Sequence[str]) -> bool:
    if not terms:
        return True
    norm = _normalize(text)
    return any(t in norm for t in terms)


def _summarize_product(p: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": p.get("id"),
        "name": p.get("name") or "Producto",
        "sku": p.get("sku") or "",
        "price": p.get("price") or p.get("regular_price") or "",
        "stock_status": p.get("stock_status") or "",
        "stock_quantity": p.get("stock_quantity"),
        "permalink": p.get("permalink") or "",
    }


def _product_text(p: Dict[str, Any]) -> str:
    name = p.get("name") or ""
    short_desc = p.get("short_description") or ""
    cats = p.get("categories") or []
    cat_names = " ".join([c.get("name", "") for c in cats if isinstance(c, dict)])
    return f"{name} {cat_names} {short_desc}"


def _truncate(text: str, limit: int = 80) -> str:
    if not text:
        return ""
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


def _format_stock(stock_qty: Optional[Any], stock_status: str) -> str:
    if stock_qty is not None:
        try:
            qty = int(stock_qty)
        except Exception:
            qty = None
        if qty is not None:
            return "agotado" if qty <= 0 else str(qty)

    status_map = {
        "instock": "disponible",
        "outofstock": "agotado",
        "onbackorder": "en pedido",
    }
    return status_map.get(stock_status or "", "N/D")


def _format_products_reply(products: List[Dict[str, Any]]) -> str:
    lines = ["Opciones relacionadas:"]
    for i, p in enumerate(products[:3], start=1):
        name = _truncate(p["name"])
        sku = p["sku"]
        price = p["price"]
        stock_status = p["stock_status"]
        stock_qty = p["stock_quantity"]

        lines.append("")
        lines.append(f"{i}) *{name}*")
        lines.append(f"SKU: {sku or 'N/D'}")
        lines.append(f"Precio: {format_cop(price)}" if price not in (None, "") else "Precio: N/D")
        lines.append(f"Stock: {_format_stock(stock_qty, stock_status)}")

    lines.append("")
    lines.append("Responde con 1, 2 o 3, o con el SKU para cotizar.")
    return "\n".join(lines)


def format_products_reply(products: List[Dict[str, Any]]) -> str:
    return _format_products_reply(products)


async def _maybe_rerank(
    user_text: str,
    candidates: Sequence[Dict[str, Any]],
    *,
    top_k: int = 3,
) -> Tuple[Optional[List[Dict[str, Any]]], Optional[str]]:
    if rerank_products is None:
        return None, None
    try:
        reranked = await rerank_products(user_text, candidates, top_k=top_k)
    except Exception:
        return None, None

    selected_ids = reranked.get("selected_ids") or []
    question = (reranked.get("clarifying_question") or "").strip()
    if selected_ids:
        id_map = {p.get("id"): p for p in candidates if p.get("id") is not None}
        selected = [id_map.get(int(pid)) for pid in selected_ids if int(pid) in id_map]
        selected = [p for p in selected if isinstance(p, dict)]
        if selected:
            return selected, None
    if question:
        return [], question
    return None, None


def _no_results_reply() -> str:
    return (
        "No encontré productos que coincidan con esa descripción.\n"
        "Para ayudarte a cotizar: dime el tipo (ej. filtro de arena/cartucho/químico), capacidad/tamaño y uso (hogar/industrial). "
        "Si tienes el SKU, envíamelo."
    )


async def smart_product_search(
    original_text: str,
    *,
    line_hint: Optional[str] = None,
) -> Tuple[str, List[Dict[str, Any]], List[Dict[str, Any]]]:
    raw = (original_text or "").strip()
    if not raw:
        return WELCOME_MESSAGE, [], []

    # 1) queries desde OpenAI (si falla, seguimos igual)
    plan_used = False
    try:
        plan = await build_product_search_plan(raw)
        plan_used = True
        if plan.get("should_ask"):
            question = str(plan.get("question") or "").strip()
            if question:
                return question, []
        queries: List[str] = plan.get("queries") or [raw]
    except Exception:
        queries = [raw]

    keywords = _keyword_queries(raw)
    required_groups = _required_groups_from_text(raw)
    specific_terms = _extract_specific_terms(raw)
    if keywords:
        if plan_used:
            queries = keywords + queries
        else:
            queries = keywords

    # 2) intento 1: Woo search normal (rápido)
    seen_ids = set()
    merged: List[Dict[str, Any]] = []
    merged_raw: List[Dict[str, Any]] = []

    search_queue: List[str] = []
    for q in queries:
        search_queue.append(q)
        if line_hint:
            search_queue.append(f"{q} {line_hint}".strip())

    # expansiones mínimas (para tus 2 ejemplos reales)
    n = raw.lower()
    if "filtr" in n:
        search_queue += ["filtro", "filtros", "filtracion", "filtración"]
    if "quim" in n:
        search_queue += ["cloro", "ph", "alguicida", "clarificador", "acidet"]

    # dedup
    uniq: List[str] = []
    seenq = set()
    for q in search_queue:
        k = q.strip().lower()
        if k and k not in seenq:
            seenq.add(k)
            uniq.append(q)

    for q in uniq[:12]:
        try:
            items = await woocommerce_client.search_products(q, per_page=15)
        except Exception:
            continue
        for p in items:
            text = _product_text(p)
            if not _matches_required_groups(text, required_groups):
                continue
            if not _matches_specific_terms(text, specific_terms):
                continue
            pid = p.get("id")
            if pid in seen_ids:
                continue
            seen_ids.add(pid)
            merged.append(_summarize_product(p))
            merged_raw.append(p)
        if len(merged) >= 5:
            break

    if merged_raw:
        selected_raw, question = await _maybe_rerank(raw, merged_raw, top_k=3)
        if question:
            return question, [], []
        if selected_raw:
            selected = [_summarize_product(p) for p in selected_raw]
            pool = [_summarize_product(p) for p in merged_raw[:12]]
            return _format_products_reply(selected), selected, pool
        pool = [_summarize_product(p) for p in merged_raw[:12]]
        selected = pool[:3]
        return _format_products_reply(selected), selected, pool

    # 3) intento 2 (el que te quita el “zombie”): catálogo local + ranking
    try:
        candidates = await search_catalog(raw, line_hint=line_hint, limit=50)
    except Exception:
        candidates = []

    if candidates:
        filtered = [
            p
            for p in candidates
            if _matches_required_groups(_product_text(p), required_groups)
            and _matches_specific_terms(_product_text(p), specific_terms)
        ]
        if not filtered:
            filtered = candidates
        selected_raw, question = await _maybe_rerank(raw, filtered, top_k=3)
        if question:
            return question, [], []
        if selected_raw:
            selected = [_summarize_product(p) for p in selected_raw]
            pool = [_summarize_product(p) for p in filtered[:12]]
            return _format_products_reply(selected), selected, pool
        pool = [_summarize_product(p) for p in filtered[:12]]
        selected = pool[:3]
        return _format_products_reply(selected), selected, pool

    return _no_results_reply(), [], []
