from functools import lru_cache
from typing import Optional

from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Configuración de la aplicación, cargada desde variables de entorno (.env).

    Usamos nombres de variables exactamente iguales a los campos de este modelo.
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
    WHATSAPP_TOKEN: str = Field(
        ...,
        description="Token (Bearer) de la API de WhatsApp Cloud",
    )
    WHATSAPP_PHONE_NUMBER_ID: str = Field(
        ...,
        description="ID del número de teléfono de WhatsApp Cloud",
    )
    WHATSAPP_VERIFY_TOKEN: str = Field(
        ...,
        description="Token de verificación del webhook configurado en Meta",
    )

    # === OpenAI (para después) ===
    OPENAI_API_KEY: Optional[str] = Field(
        default=None,
        description="API key de OpenAI (opcional por ahora)",
    )

    # === Base de datos (si la usas después) ===
    DATABASE_URL: Optional[str] = Field(
        default=None,
        description="URL de la base de datos (opcional por ahora)",
    )

    # === Parámetros de servidor (por si los usas en scripts) ===
    HOST: str = Field(
        "0.0.0.0",
        description="Host para levantar la app (no crítico aquí)",
    )
    PORT: int = Field(
        8000,
        description="Puerto para levantar la app",
    )

    # Configuración de pydantic-settings
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # Ignora variables extra que haya en .env
    )


@lru_cache
def get_settings() -> Settings:
    """
    Devuelve una única instancia de Settings (cacheada).
    """
    return Settings()
