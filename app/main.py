import logging

from fastapi import FastAPI
from fastapi.responses import Response

from app.core.settings import get_settings
from app.api.woocommerce import router as woocommerce_router
from app.api.twilio import router as twilio_router
from app.api.whatsapp import router as whatsapp_router

logger = logging.getLogger(__name__)
settings = get_settings()

app = FastAPI(
    title="Aquaintegral Conversational Assistant",
    version="0.1.0",
)

# Importa el router de WhatsApp tal como ya lo tienes
app.include_router(whatsapp_router)
app.include_router(woocommerce_router)
app.include_router(twilio_router)

# PNG 1x1 de relleno para iconos (placeholder)
_PLACEHOLDER_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\x0bIDATx\x9cc``\x00\x00\x00\x02\x00\x01"
    b"\xe2!\xbc3\x00\x00\x00\x00IEND\xaeB`\x82"
)


@app.get("/", tags=["system"])
async def root() -> dict:
    """
    Endpoint raíz para ver que el backend está vivo.
    """
    return {
        "status": "ok",
        "message": "Aquaintegral Conversational Assistant",
    }


@app.get("/health", tags=["system"])
async def health() -> dict:
    """
    Endpoint de health-check.

    Incluye el ENV actual para saber en qué entorno estamos.
    """
    return {
        "status": "ok",
        "env": settings.ENV,
    }


@app.get("/favicon.ico", include_in_schema=False)
async def favicon() -> Response:
    """
    Placeholder para favicon.
    """
    return Response(content=_PLACEHOLDER_PNG, media_type="image/png")


@app.get("/apple-touch-icon.png", include_in_schema=False)
async def apple_touch_icon() -> Response:
    """
    Placeholder para icono de Apple.
    """
    return Response(content=_PLACEHOLDER_PNG, media_type="image/png")


@app.get("/icon-192.png", include_in_schema=False)
async def icon_192() -> Response:
    """
    Placeholder para icono PWA.
    """
    return Response(content=_PLACEHOLDER_PNG, media_type="image/png")
