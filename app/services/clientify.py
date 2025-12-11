import logging
from typing import Any, Dict, List, Optional

import httpx

from app.core.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class ClientifyClient:
    """
    Cliente asíncrono para la API de Clientify.

    Expone métodos de alto nivel:
    - get_or_create_contact_by_phone
    - create_deal
    - add_note_to_contact
    """

    def __init__(self) -> None:
        # En Pydantic v2 CLIENTIFY_BASE_URL es AnyHttpUrl, lo casteamos a str
        base_url = str(settings.CLIENTIFY_BASE_URL).rstrip("/")
        self.base_url = base_url
        self.api_key = settings.CLIENTIFY_API_KEY
        self.timeout = 10.0

        if not self.api_key:
            raise RuntimeError("CLIENTIFY_API_KEY no está configurada")

        self.headers = {
            "Authorization": f"Token {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
    ) -> httpx.Response:
        """
        Método interno para hacer peticiones HTTP a Clientify.

        - Lanza httpx.HTTPStatusError en caso de status 4xx/5xx.
        """
        url = f"{self.base_url}{path}"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.request(
                method=method,
                url=url,
                headers=self.headers,
                params=params,
                json=json,
            )

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError:
            logger.error(
                "Error en petición a Clientify",
                extra={
                    "method": method,
                    "url": url,
                    "status_code": response.status_code,
                    "response_text": response.text,
                },
            )
            raise

        return response

    async def get_or_create_contact_by_phone(self, phone: str) -> Dict[str, Any]:
        """
        Busca un contacto por teléfono; si no existe, lo crea.

        - phone: número en formato internacional (idealmente con país).
        - Devuelve el dict del contacto.
        """
        # 1) Buscar contacto existente
        response = await self._request(
            "GET",
            "/contacts/",
            params={"phone": phone},
        )

        data = response.json()
        # Clientify suele devolver {"results": [...], "count": N, ...}
        contacts: List[Dict[str, Any]] = data.get("results", []) if isinstance(data, dict) else data

        if contacts:
            contact = contacts[0]
            logger.info(
                "Contacto Clientify encontrado",
                extra={"phone": phone, "contact_id": contact.get("id")},
            )
            return contact

        # 2) Crear contacto nuevo
        payload = {
            "phone": phone,
            "source": "WhatsApp Bot",
            "tags": ["whatsapp", "bot"],
        }

        response = await self._request(
            "POST",
            "/contacts/",
            json=payload,
        )
        contact = response.json()

        logger.info(
            "Contacto Clientify creado",
            extra={"phone": phone, "contact_id": contact.get("id")},
        )

        return contact

    async def create_deal(
        self,
        *,
        contact_id: int,
        name: str,
        value: Optional[float] = None,
        currency: str = "COP",
    ) -> Dict[str, Any]:
        """
        Crea una oportunidad (deal) asociada a un contacto.

        Los campos adicionales (pipeline, stage, owner, etc.) los podemos
        parametrizar más adelante vía settings si hace falta.
        """
        payload: Dict[str, Any] = {
            "contact": contact_id,
            "name": name,
            "source": "WhatsApp Bot",
        }

        if value is not None:
            payload["value"] = value
            payload["currency"] = currency

        response = await self._request(
            "POST",
            "/deals/",
            json=payload,
        )
        deal = response.json()

        logger.info(
            "Deal Clientify creado",
            extra={
                "contact_id": contact_id,
                "deal_id": deal.get("id"),
                "name": name,
            },
        )

        return deal

    async def add_note_to_contact(
        self,
        *,
        contact_id: int,
        text: str,
    ) -> Dict[str, Any]:
        """
        Añade una nota a un contacto.
        """
        payload = {
            "text": text,
        }

        path = f"/contacts/{contact_id}/notes/"
        response = await self._request(
            "POST",
            path,
            json=payload,
        )
        note = response.json()

        logger.info(
            "Nota añadida a contacto Clientify",
            extra={
                "contact_id": contact_id,
                "note_id": note.get("id"),
            },
        )

        return note


# Instancia global reutilizable en el proyecto
clientify_client = ClientifyClient()
