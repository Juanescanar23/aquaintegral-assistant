import logging
from typing import Any, Dict, List, Optional

import httpx
from httpx import HTTPStatusError

from app.core.settings import get_settings

logger = logging.getLogger(__name__)

# Cargamos settings una sola vez
_settings = get_settings()


class ClientifyClient:
    """
    Cliente ligero para la API de Clientify (v1).

    Hace:
    - Búsqueda / creación de contactos por teléfono.
    - Creación de notas asociadas al contacto.
    - Creación de deals básicos asociando el contacto.
    """

    def __init__(self) -> None:
        # CLIENTIFY_BASE_URL viene de .env, ejemplo:
        # CLIENTIFY_BASE_URL=https://api.clientify.net/v1/
        base = str(_settings.CLIENTIFY_BASE_URL).rstrip("/")
        # Ejemplo final: https://api.clientify.net/v1
        self.base_url = base

        if not _settings.CLIENTIFY_API_KEY:
            raise RuntimeError("CLIENTIFY_API_KEY no está configurado")

        self.headers = {
            "Authorization": f"Token {_settings.CLIENTIFY_API_KEY}",
            "Content-Type": "application/json",
        }

    def _build_url(self, path: str) -> str:
        """
        Construye la URL completa asegurando que no haya // raros.
        """
        return f"{self.base_url}/{path.lstrip('/')}"

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        timeout: float = 15.0,
    ) -> Any:
        """
        Envoltorio común para peticiones HTTP a Clientify.
        Lanza HTTPStatusError si la respuesta no es 2xx.
        """
        url = self._build_url(path)

        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.request(
                method=method.upper(),
                url=url,
                headers=self.headers,
                params=params,
                json=json,
            )

        try:
            response.raise_for_status()
        except HTTPStatusError:
            # Logueamos detalle para debug
            logger.error(
                "Error en petición a Clientify",
                extra={
                    "url": url,
                    "status_code": response.status_code,
                    "body": response.text,
                },
            )
            # Re-lanzamos para que el webhook devuelva 502
            raise

        if not response.content:
            return None
        return response.json()

    # -------------------------------------------------------------------------
    # Contactos
    # -------------------------------------------------------------------------
    async def get_or_create_contact_by_phone(self, phone: str) -> Dict[str, Any]:
        """
        Busca contacto por teléfono; si no existe, lo crea.

        IMPORTANTE:
        - El filtro por teléfono se hace con ?phone=...
        - El resultado típico viene paginado con 'results'.
        """
        # 1) Buscar por teléfono
        data = await self._request("GET", "contacts/", params={"phone": phone})

        if isinstance(data, dict):
            results: List[Dict[str, Any]] = data.get("results", [])
            if results:
                return results[0]

        # 2) Crear un contacto simple si no existe
        payload = {
            "first_name": phone,
            "phone": phone,
        }
        created = await self._request("POST", "contacts/", json=payload)
        return created

    # -------------------------------------------------------------------------
    # Notas
    # -------------------------------------------------------------------------
    async def add_note_to_contact(self, contact_id: int, text: str) -> Dict[str, Any]:
        """
        Añade una nota al contacto en Clientify.

        Endpoint correcto según documentación:
        POST https://api.clientify.net/v1/contacts/:contact_id/note/
        (note en singular, colgado del contacto)
        """
        payload = {
            "name": "Mensaje desde WhatsApp",  # título de la nota
            "comment": text,  # contenido de la nota
        }

        # IMPORTANTE: ruta correcta, sin /notes/
        note = await self._request(
            "POST",
            f"contacts/{contact_id}/note/",
            json=payload,
        )
        return note

    # -------------------------------------------------------------------------
    # Deals
    # -------------------------------------------------------------------------
    async def create_deal(
        self,
        *,
        contact_id: int,
        name: str,
        amount: float = 0.0,
    ) -> Dict[str, Any]:
        """
        Crea un deal mínimo válido en Clientify.

        Requisitos (según errores que vimos):
        - amount: obligatorio.
        - contact: debe ser URL, no id numérico.
        - source: es un choice → mejor NO enviarlo para evitar 400.
        """
        contact_url = self._build_url(f"contacts/{contact_id}/")

        payload = {
            "name": name,
            # Clientify suele aceptar amount como string numérico
            "amount": str(amount),
            "contact": contact_url,
        }

        deal = await self._request("POST", "deals/", json=payload)
        return deal


# Instancia reutilizable
clientify_client = ClientifyClient()
