import os
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import httpx

from app.core.settings import get_settings

settings = get_settings()
_CATEGORY_CACHE: Dict[str, int] = {}

def _get_env(name: str) -> str:
    v = getattr(settings, name, None) or os.getenv(name)
    if not v:
        raise RuntimeError(f"Missing env var: {name}")
    return v


def _woo_base_products_url(base_url: str) -> str:
    """
    Acepta base tipo https://tusitio.com o https://tusitio.com/
    y construye endpoint wc/v3/products
    """
    base = base_url.rstrip("/") + "/"
    return urljoin(base, "wp-json/wc/v3/products")


def _woo_base_categories_url(base_url: str) -> str:
    base = base_url.rstrip("/") + "/"
    return urljoin(base, "wp-json/wc/v3/products/categories")


async def _get_category_id_by_slug(slug: str) -> Optional[int]:
    slug = (slug or "").strip()
    if not slug:
        return None
    if slug in _CATEGORY_CACHE:
        return _CATEGORY_CACHE[slug]

    base_url = _get_env("WOOCOMMERCE_BASE_URL")
    ck = _get_env("WOOCOMMERCE_CONSUMER_KEY")
    cs = _get_env("WOOCOMMERCE_CONSUMER_SECRET")

    url = _woo_base_categories_url(base_url)
    params = {
        "slug": slug,
        "per_page": 1,
        "consumer_key": ck,
        "consumer_secret": cs,
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(url, params=params)
        r.raise_for_status()
        data = r.json()

    if isinstance(data, list) and data:
        cat_id = data[0].get("id")
        if isinstance(cat_id, int):
            _CATEGORY_CACHE[slug] = cat_id
            return cat_id
    return None


async def search_products_by_text(
    query: Optional[str],
    per_page: int = 5,
    category_slug: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Busqueda basica WooCommerce por texto (endpoint ?search=).
    Devuelve lista de productos (dicts Woo).
    """
    base_url = _get_env("WOOCOMMERCE_BASE_URL")
    ck = _get_env("WOOCOMMERCE_CONSUMER_KEY")
    cs = _get_env("WOOCOMMERCE_CONSUMER_SECRET")

    url = _woo_base_products_url(base_url)

    params = {
        "per_page": per_page,
        "status": "publish",
        # Auth por query-string (como ya lo tienes en tu cliente actual)
        "consumer_key": ck,
        "consumer_secret": cs,
    }
    if query:
        params["search"] = query
    if category_slug:
        cat_id = await _get_category_id_by_slug(category_slug)
        if cat_id:
            params["category"] = cat_id

    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(url, params=params)
        r.raise_for_status()
        data = r.json()

    if not isinstance(data, list):
        return []
    return data
