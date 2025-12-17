import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request
from httpx import HTTPStatusError

from app.services.conversation import process_incoming_message
from app.services.whatsapp import send_message

logger = logging.getLogger(__name__)

router = APIRouter()


def extraer_telefono(payload: Dict[str, Any]) -> str:
    """
    Intenta extraer el número de teléfono del payload de Meta.

    Prioridad:
    1) value.contacts[0].wa_id
    2) value.messages[0].from
    3) payload["phone"] (fallback simple)
    """
    try:
        entry = payload.get("entry", [])
        if entry:
            changes = entry[0].get("changes", [])
            if changes:
                value = changes[0].get("value", {})
                contacts = value.get("contacts", [])
                if contacts and "wa_id" in contacts[0]:
                    return contacts[0]["wa_id"]

                messages = value.get("messages", [])
                if messages and "from" in messages[0]:
                    return messages[0]["from"]
    except Exception:
        logger.exception("Error extrayendo teléfono del payload de WhatsApp")

    # Fallback muy simple
    phone = payload.get("phone", "")
    return phone or ""


def extraer_texto(payload: Dict[str, Any]) -> Optional[str]:
    """
    Extrae el texto del primer mensaje de WhatsApp en el payload.
    """
    try:
        entry = payload.get("entry", [])
        if entry:
            changes = entry[0].get("changes", [])
            if changes:
                value = changes[0].get("value", {})
                messages = value.get("messages", [])
                if messages:
                    msg = messages[0]
                    # Formato típico: {"text": {"body": "..."}}.
                    if "text" in msg and isinstance(msg["text"], dict):
                        body = msg["text"].get("body")
                        if body:
                            return body
                    # Fallback por si viene plano
                    if "body" in msg and isinstance(msg["body"], str):
                        return msg["body"]
    except Exception:
        logger.exception("Error extrayendo texto del payload de WhatsApp")

    return None


@router.post("/webhook/whatsapp")
async def whatsapp_webhook(request: Request):
    """
    Webhook de WhatsApp (POST desde Meta).

    - Extrae teléfono y texto del payload.
    - Llama a la capa de conversación (Clientify + lógica del bot).
    - Envía la respuesta al usuario.
    """
    payload = await request.json()

    phone = extraer_telefono(payload)
    text = extraer_texto(payload)

    if not phone:
        raise HTTPException(
            status_code=400,
            detail="No se pudo extraer el teléfono del payload de WhatsApp",
        )

    if text is None:
        raise HTTPException(
            status_code=400,
            detail="No se encontró texto en el mensaje de WhatsApp",
        )

    try:
        # Lógica central: Clientify + WooCommerce + negocio
        reply_text = await process_incoming_message(phone, text)

        # Envío real (o stub) a WhatsApp
        await send_message(phone, reply_text)

    except HTTPStatusError as exc:
        # Aquí capturamos los errores de Clientify (o de WhatsApp si usas httpx allí)
        status = exc.response.status_code if exc.response is not None else None
        body = exc.response.text if exc.response is not None else "Sin body"

        logger.error(
            "Error en petición a servicio externo (Clientify/WhatsApp)",
            extra={
                "upstream_status": status,
                "upstream_body": body,
            },
            exc_info=True,
        )

        # En desarrollo, devolvemos el detalle para ver exactamente qué responde Clientify
        raise HTTPException(
            status_code=502,
            detail=f"Upstream request failed ({status}): {body}",
        )

    except Exception:
        logger.exception("Error inesperado procesando webhook de WhatsApp")
        raise HTTPException(
            status_code=500,
            detail="Internal server error processing WhatsApp webhook",
        )

    return {"status": "ok"}
