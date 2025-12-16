import logging
from typing import Any, Dict, List, Optional

import httpx

from app.core.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class WooCommerceClient:
    """
    Cliente asíncrono para la API REST de WooCommerce.

    Usa autenticación con consumer_key / consumer_secret por query string.
    """

    def __init__(self) -> None:
        # Base URL de la tienda, ej: https://tienda.aquaintegral.co
        base_url = str(settings.WOOCOMMERCE_BASE_URL).rstrip("/")
        # Endpoint raíz de la API REST
        self.api_base = f"{base_url}/wp-json/wc/v3"
        self.consumer_key = settings.WOOCOMMERCE_CONSUMER_KEY
        self.consumer_secret = settings.WOOCOMMERCE_CONSUMER_SECRET
        self.timeout = 10.0

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
    ) -> httpx.Response:
        """
        Método interno para hacer peticiones a WooCommerce.

        - Añade consumer_key y consumer_secret a los params.
        - Lanza httpx.HTTPStatusError si Woo responde 4xx/5xx.
        """
        if params is None:
            params = {}

        # Auth por query string
        params.update(
            {
                "consumer_key": self.consumer_key,
                "consumer_secret": self.consumer_secret,
            }
        )

        url = f"{self.api_base}{path}"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.request(
                method=method,
                url=url,
                params=params,
                json=json,
            )

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError:
            logger.error(
                "Error en petición a WooCommerce",
                extra={
                    "method": method,
                    "url": url,
                    "status_code": response.status_code,
                    "response_text": response.text,
                },
            )
            raise

        return response

    async def get_products_by_sku(self, sku: str) -> List[Dict[str, Any]]:
        """
        Devuelve una lista de productos con un SKU exacto.

        WooCommerce permite filtrar por ?sku=SKU.
        """
        response = await self._request(
            "GET",
            "/products",
            params={"sku": sku},
        )
        data = response.json()
        if not isinstance(data, list):
            logger.warning("Respuesta inesperada de WooCommerce /products", extra={"data": data})
            return []
        return data

    async def get_product_by_sku(self, sku: str) -> Optional[Dict[str, Any]]:
        """
        Devuelve el primer producto que coincida con el SKU, o None si no hay.
        """
        products = await self.get_products_by_sku(sku)
        if not products:
            return None
        return products[0]

    async def search_products(self, query: str, per_page: int = 10) -> List[Dict[str, Any]]:
        """
        Busca productos por texto (nombre, descripción, etc.) usando ?search=.
        """
        response = await self._request(
            "GET",
            "/products",
            params={"search": query, "per_page": per_page},
        )
        data = response.json()
        if not isinstance(data, list):
            logger.warning("Respuesta inesperada de WooCommerce /products search", extra={"data": data})
            return []
        return data

    async def get_stock_by_sku(self, sku: str) -> Optional[Dict[str, Any]]:
        """
        Devuelve información resumida de inventario para un SKU:

        {
          "id": ...,
          "name": ...,
          "sku": ...,
          "manage_stock": bool,
          "stock_quantity": int | None,
          "stock_status": "instock" | "outofstock" | "onbackorder",
          "type": "simple" | "variable" | ...
        }

        Para productos variables, esta función NO desglosa variaciones.
        """
        product = await self.get_product_by_sku(sku)
        if product is None:
            return None

        return {
            "id": product.get("id"),
            "name": product.get("name"),
            "sku": product.get("sku"),
            "manage_stock": product.get("manage_stock"),
            "stock_quantity": product.get("stock_quantity"),
            "stock_status": product.get("stock_status"),
            "type": product.get("type"),
        }


woocommerce_client = WooCommerceClient()
