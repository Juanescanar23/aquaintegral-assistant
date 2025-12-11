from functools import lru_cache
from typing import Optional

from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Configuración de la aplicación, cargada desde variables de entorno (.env).

    Adaptado a Pydantic v2 + pydantic-settings.
    """

    # === Entorno general ===
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

    # Mapeamos el token al nombre que ya tienes en .env: whatsapp_access_token
    WHATSAPP_TOKEN: str = Field(
        ...,
        description="Token (Bearer) de la API de WhatsApp Cloud",
        env="whatsapp_access_token",
    )

    # Estos dos sí te los voy a pedir explícitamente en el .env
    WHATSAPP_PHONE_NUMBER_ID: str = Field(
        ...,
        description="ID del número de teléfono de WhatsApp Cloud",
        env="whatsapp_phone_number_id",
    )
    WHATSAPP_VERIFY_TOKEN: str = Field(
        ...,
        description="Token de verificación del webhook configurado en Meta",
        env="whatsapp_verify_token",
    )

    # === OpenAI (usaremos después) ===
    OPENAI_API_KEY: Optional[str] = Field(
        default=None,
        description="API key de OpenAI (puede estar vacía por ahora)",
        env="openai_api_key",
    )

    # === Base de datos (si la usas después) ===
    DATABASE_URL: Optional[str] = Field(
        default=None,
        description="URL de la base de datos (opcional por ahora)",
        env="database_url",
    )

    # === Parámetros de servidor (por si los usas en scripts) ===
    HOST: str = Field(
        "0.0.0.0",
        description="Host para levantar la app (no crítico aquí)",
        env="host",
    )
    PORT: int = Field(
        8000,
        description="Puerto para levantar la app",
        env="port",
    )

    # Config Pydantic Settings
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # Ignora otras variables que haya en .env
    )


@lru_cache
def get_settings() -> Settings:
    """
    Devuelve una única instancia de Settings (cacheada).
    """
    return Settings()
