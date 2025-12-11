from functools import lru_cache

from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Configuración de la aplicación, cargada desde variables de entorno (.env).

    Adaptado a Pydantic v2: usamos pydantic-settings para BaseSettings.
    """

    ENV: str = Field(
        "development",
        description="Nombre del entorno actual (development/staging/production)",
    )

    # === Clientify ===
    CLIENTIFY_BASE_URL: AnyHttpUrl = Field(
        "https://api.clientify.com/v1",
        description="Base URL de la API de Clientify",
    )
    CLIENTIFY_API_KEY: str = Field(..., description="API key para Clientify")

    # === WhatsApp Cloud API (Meta) ===
    WHATSAPP_BASE_URL: AnyHttpUrl = Field(
        "https://graph.facebook.com/v19.0",
        description="Base URL de la API de WhatsApp Cloud",
    )
    WHATSAPP_PHONE_NUMBER_ID: str = Field(
        ...,
        description="ID del número de teléfono de WhatsApp Cloud",
    )
    WHATSAPP_TOKEN: str = Field(
        ...,
        description="Token (Bearer) de la API de WhatsApp Cloud",
    )
    WHATSAPP_VERIFY_TOKEN: str = Field(
        ...,
        description="Token de verificación del webhook configurado en Meta",
    )

    # Configuración de BaseSettings en Pydantic v2
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )


@lru_cache
def get_settings() -> Settings:
    """
    Devuelve una única instancia de Settings (cacheada).
    """
    return Settings()
