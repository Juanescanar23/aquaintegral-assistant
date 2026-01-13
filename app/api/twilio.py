import logging
from xml.etree.ElementTree import Element, SubElement, tostring

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

from app.services.conversation import process_incoming_message
from app.utils.test_mode import is_allowed_phone

logger = logging.getLogger(__name__)
router = APIRouter()


def _normalize_from(from_value: str) -> str:
    # Esperado: "whatsapp:+5730..."
    return (from_value or "").strip()


def _phone_digits(from_value: str) -> str:
    """
    Para tu logica actual: numero sin 'whatsapp:' y sin '+'
    ej: whatsapp:+573001112233 -> 573001112233
    """
    v = _normalize_from(from_value)
    if v.startswith("whatsapp:"):
        v = v.replace("whatsapp:", "", 1)
    return v.lstrip("+").strip()


def _twiml_message(body: str) -> bytes:
    """
    Construye TwiML valido para responder un mensaje entrante.
    Twilio lee este XML y envia el mensaje automaticamente.
    """
    root = Element("Response")
    msg = SubElement(root, "Message")
    msg.text = body or ""
    return tostring(root, encoding="utf-8", xml_declaration=True)


@router.post("/webhook/twilio")
async def twilio_webhook(request: Request):
    """
    Webhook inbound para Twilio WhatsApp.
    - Lee form-urlencoded (From, Body)
    - Ejecuta tu logica existente (Clientify + Woo)
    - Devuelve TwiML con la respuesta (Twilio la envia al usuario)
    """
    try:
        form = await request.form()
    except Exception:
        logger.exception("No se pudo leer form-data de Twilio")
        raise HTTPException(status_code=400, detail="Invalid form-data")

    from_whatsapp = _normalize_from(str(form.get("From") or ""))
    body_in = str(form.get("Body") or "").strip()

    if not from_whatsapp:
        raise HTTPException(status_code=400, detail="Missing From")

    if not body_in:
        # No respondemos nada util si llega vacio
        return Response(content=_twiml_message(""), media_type="application/xml")

    phone = _phone_digits(from_whatsapp)

    if not is_allowed_phone(phone):
        logger.info(
            "Modo pruebas: ignorando mensaje fuera de la lista permitida",
            extra={"phone": phone},
        )
        return Response(content=_twiml_message(""), media_type="application/xml")

    try:
        reply_text = await process_incoming_message(phone, body_in)
    except Exception:
        logger.exception("Error procesando conversacion (Clientify/Woo/etc)")
        reply_text = (
            "Recibi tu mensaje, pero tuve un error procesandolo. "
            "Un asesor te contactara en breve."
        )

    return Response(content=_twiml_message(reply_text), media_type="application/xml")
