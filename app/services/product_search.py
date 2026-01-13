import re
import unicodedata
from typing import Optional, Tuple, List, Dict, Any

from app.domain.playbook import WELCOME_MESSAGE
from app.services.openai_product_query import build_product_search_plan
from app.services.woocommerce import woocommerce_client
from app.services.catalog_cache import search_catalog


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


def _format_products_reply(products: List[Dict[str, Any]]) -> str:
    lines = ["Encontré estas opciones relacionadas con tu solicitud:"]
    for i, p in enumerate(products[:3], start=1):
        name = p["name"]
        sku = p["sku"]
        price = p["price"]
        stock_status = p["stock_status"]
        stock_qty = p["stock_quantity"]

        stock_part = ""
        if stock_qty is not None:
            stock_part = f"stock: {stock_qty}"
        elif stock_status:
            stock_part = f"estado: {stock_status}"

        price_part = f"precio: ${price} COP" if price else "precio: N/D"
        sku_part = f"SKU {sku}" if sku else "SKU N/D"

        line = (
            f"{i}) {name} ({sku_part}) — {price_part}"
            f"{f' — {stock_part}' if stock_part else ''}"
        )
        lines.append(line)

    lines.append("Respóndeme con el número (1, 2 o 3) o con el SKU para darte disponibilidad y cotización.")
    return "\n".join(lines)


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
) -> Tuple[str, List[Dict[str, Any]]]:
    raw = (original_text or "").strip()
    if not raw:
        return WELCOME_MESSAGE, []

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
    keyword_tokens = set(keywords)
    if keywords:
        if plan_used:
            queries = keywords + queries
        else:
            queries = keywords

    # 2) intento 1: Woo search normal (rápido)
    seen_ids = set()
    merged: List[Dict[str, Any]] = []

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
            if keyword_tokens:
                text = _normalize(_product_text(p))
                if not any(k in text for k in keyword_tokens):
                    continue
            pid = p.get("id")
            if pid in seen_ids:
                continue
            seen_ids.add(pid)
            merged.append(_summarize_product(p))
        if len(merged) >= 5:
            break

    if merged:
        return _format_products_reply(merged), merged

    # 3) intento 2 (el que te quita el “zombie”): catálogo local + ranking
    try:
        candidates = await search_catalog(raw, line_hint=line_hint, limit=50)
    except Exception:
        candidates = []

    if candidates:
        top = [_summarize_product(p) for p in candidates[:5]]
        return _format_products_reply(top), top

    return _no_results_reply(), []
