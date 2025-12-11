import base64

from fastapi import FastAPI
from fastapi.responses import Response

from .core.config import settings
from app.api.whatsapp import router as whatsapp_router

app = FastAPI(
    title="Aquaintegral Conversational Assistant",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Single-pixel transparent PNG for browsers asking for icons; avoids noisy 404s.
_PLACEHOLDER_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAE0lEQVR4nGP8/5+hHgAHggJ/PiAtWAAAAABJRU5ErkJggg=="
)

app.include_router(whatsapp_router)


@app.get("/")
def root():
    return {
        "message": "Aquaintegral assistant API",
        "endpoints": {
            "health": "/health",
            "docs": "/docs",
            "redoc": "/redoc",
        },
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "env": settings.ENV,
    }


@app.get("/favicon.ico")
def favicon():
    return Response(
        content=_PLACEHOLDER_PNG,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@app.get("/apple-touch-icon.png")
def apple_touch_icon():
    return Response(
        content=_PLACEHOLDER_PNG,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@app.get("/apple-touch-icon-precomposed.png")
def apple_touch_icon_precomposed():
    return Response(
        content=_PLACEHOLDER_PNG,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=86400"},
    )
