import logging
import httpx

from app.core.settings import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()


def _require_env() -> None:
    missing = []
    if not settings.TWILIO_ACCOUNT_SID:
        missing.append("TWILIO_ACCOUNT_SID")
    if not settings.TWILIO_AUTH_TOKEN:
        missing.append("TWILIO_AUTH_TOKEN")
    if not settings.TWILIO_WHATSAPP_FROM:
        missing.append("TWILIO_WHATSAPP_FROM")
    if missing:
        raise RuntimeError(f"Missing env vars: {', '.join(missing)}")


async def send_twilio_whatsapp_message(*, to_whatsapp: str, body: str) -> None:
    """
    Envia WhatsApp por Twilio.
    - to_whatsapp: 'whatsapp:+57...'
    - body: texto a enviar
    """
    _require_env()

    url = (
        "https://api.twilio.com/2010-04-01/Accounts/"
        f"{settings.TWILIO_ACCOUNT_SID}/Messages.json"
    )
    data = {
        "From": settings.TWILIO_WHATSAPP_FROM,
        "To": to_whatsapp,
        "Body": body,
    }

    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(
            url,
            data=data,
            auth=(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN),
        )
        if r.status_code >= 400:
            logger.error(
                "Twilio send failed",
                extra={"status": r.status_code, "body": r.text},
            )
