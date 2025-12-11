from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request
from httpx import HTTPStatusError

from app.services.conversation import process_incoming_message
from app.services.whatsapp import send_message

router = APIRouter()


def extraer_telefono(payload: Dict[str, Any]) -> str:
    # Typical Meta webhook shape
    try:
        return (
            payload["entry"][0]["changes"][0]["value"]["contacts"][0]["wa_id"]
        )  # type: ignore[index]
    except (KeyError, IndexError, TypeError):
        pass

    # Alternative: read from the message itself
    try:
        return payload["entry"][0]["changes"][0]["value"]["messages"][0]["from"]
    except (KeyError, IndexError, TypeError):
        pass

    phone = payload.get("phone")
    if phone:
        return str(phone)

    raise HTTPException(status_code=400, detail="Phone not found in webhook payload")


def extraer_texto(payload: Dict[str, Any]) -> Optional[str]:
    try:
        return payload["entry"][0]["changes"][0]["value"]["messages"][0]["text"]["body"]
    except (KeyError, IndexError, TypeError):
        return None


@router.post("/webhook/whatsapp")
async def whatsapp_webhook(request: Request):
    payload = await request.json()
    phone = extraer_telefono(payload)
    text = extraer_texto(payload)
    if text is None:
        raise HTTPException(status_code=400, detail="Message text not found")

    try:
        reply_text = await process_incoming_message(phone=phone, text=text)
    except HTTPStatusError as exc:
        raise HTTPException(status_code=502, detail="Clientify request failed") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Unexpected error") from exc

    await send_message(phone, reply_text)

    return {"status": "ok"}
