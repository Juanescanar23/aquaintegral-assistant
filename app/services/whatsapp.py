import logging
from typing import Any, Dict

import httpx

from app.core.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


async def send_message(phone: str, text: str) -> None:
    """
    Envía un mensaje de texto simple usando la API de WhatsApp Cloud (Meta).

    - phone: número en formato internacional SIN el '+' (ej: 573001234567).
    - text: cuerpo del mensaje.

    Lanza httpx.HTTPStatusError si la API responde con error 4xx/5xx.
    """
    # Endpoint: /{phone-number-id}/messages
    # Ej: https://graph.facebook.com/v19.0/123456789012345/messages
    url = f"{settings.WHATSAPP_BASE_URL.rstrip('/')}/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"

    payload: Dict[str, Any] = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "text",
        "text": {
            "preview_url": False,
            "body": text,
        },
    }

    headers = {
        "Authorization": f"Bearer {settings.WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }

    logger.info(
        "Enviando mensaje WhatsApp",
        extra={"to": phone, "body": text},
    )

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(url, json=payload, headers=headers)

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError:
            logger.error(
                "Error al enviar mensaje WhatsApp",
                extra={
                    "status_code": response.status_code,
                    "response_text": response.text,
                },
            )
            # Dejamos que el caller decida cómo manejar el error
            raise
