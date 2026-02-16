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

    # === Twilio WhatsApp ===
    TWILIO_ACCOUNT_SID: str = Field(
        ...,
        description="Account SID de Twilio",
    )
    TWILIO_AUTH_TOKEN: str = Field(
        ...,
        description="Auth Token de Twilio",
    )
    TWILIO_WHATSAPP_FROM: str = Field(
        "whatsapp:+14155238886",
        description="Número de WhatsApp de Twilio (con prefijo whatsapp:)",
    )

    # === WooCommerce / WordPress ===
    WOOCOMMERCE_BASE_URL: AnyHttpUrl = Field(
        ...,
        description="URL base de la tienda WooCommerce (sin /wp-json). Ej: https://tienda.aquaintegral.co",
    )
    WOOCOMMERCE_CONSUMER_KEY: str = Field(
        ...,
        description="Consumer Key de la API REST de WooCommerce",
    )
    WOOCOMMERCE_CONSUMER_SECRET: str = Field(
        ...,
        description="Consumer Secret de la API REST de WooCommerce",
    )

    # === OpenAI (para después) ===
    OPENAI_API_KEY: Optional[str] = Field(
        default=None,
        description="API key de OpenAI (opcional por ahora)",
    )
    OPENAI_MODEL: Optional[str] = Field(
        default=None,
        description="Modelo por defecto de OpenAI (opcional).",
    )
    OPENAI_KB_MODEL: Optional[str] = Field(
        default=None,
        description="Modelo para borradores de base de conocimiento (opcional).",
    )
    OPENAI_INTENT_MODEL: Optional[str] = Field(
        default=None,
        description="Modelo específico para clasificación de intentos (opcional).",
    )
    OPENAI_CONSULTANT_MODEL: Optional[str] = Field(
        default=None,
        description="Modelo específico para preguntas consultivas (opcional).",
    )
    OPENAI_RERANK_MODEL: Optional[str] = Field(
        default=None,
        description="Modelo específico para rerank de productos (opcional).",
    )

    # === Knowledge base (auto-aprendizaje controlado) ===
    KB_AUTO_DRAFT: bool = Field(
        False,
        description="Genera borradores de conocimiento con OpenAI cuando falta respuesta.",
    )
    KB_AUTO_PUBLISH: bool = Field(
        False,
        description="Publica borradores automaticamente en la base de conocimiento.",
    )
    KB_MIN_SCORE: int = Field(
        2,
        description="Score minimo para usar una respuesta de la base de conocimiento.",
    )
    KB_REQUIRE_VERIFIED: bool = Field(
        True,
        description="Solo usa entradas verificadas en la base de conocimiento.",
    )

    # === Mensajes por inactividad ===
    IDLE_FOLLOWUP_ENABLED: bool = Field(
        False,
        description="Activa mensajes automáticos por inactividad (seguimiento y cierre).",
    )
    IDLE_FOLLOWUP_AFTER_MINUTES: int = Field(
        15,
        description="Minutos de inactividad antes del primer seguimiento.",
    )
    IDLE_FINAL_AFTER_MINUTES: int = Field(
        60,
        description="Minutos de inactividad antes del mensaje de cierre.",
    )
    IDLE_CHECK_INTERVAL_SECONDS: int = Field(
        60,
        description="Intervalo de chequeo para inactividad (segundos).",
    )
    IDLE_MAX_FOLLOWUPS: int = Field(
        1,
        description="Cantidad máxima de seguimientos por conversación.",
    )
    IDLE_FOLLOWUP_MESSAGE: str = Field(
        "¿Sigues ahí? 😊 Si quieres, cuéntame qué necesitas y te ayudo con opciones de Aqua Integral. 💧",
        description="Mensaje de seguimiento por inactividad.",
    )
    IDLE_FINAL_MESSAGE: str = Field(
        "¡Gracias por escribir a Aqua Integral! 🙌 Si ahora no es el momento, estaré aquí para ayudarte cuando quieras. 💧",
        description="Mensaje de cierre por inactividad.",
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

    # === Modo pruebas en producción ===
    BOT_TEST_MODE: bool = Field(
        False,
        description="Activa modo pruebas para restringir a números permitidos.",
    )
    BOT_TEST_NUMBERS: str = Field(
        "",
        description="Lista de números permitidos separados por coma (solo dígitos).",
    )
    BOT_TEST_TAG: str = Field(
        "[TEST]",
        description="Prefijo para notas y deals cuando el bot está en pruebas.",
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
