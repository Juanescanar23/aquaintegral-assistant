from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    ENV: str = "local"

    OPENAI_API_KEY: Optional[str] = None
    DATABASE_URL: Optional[str] = None

    WHATSAPP_VERIFY_TOKEN: Optional[str] = None
    WHATSAPP_ACCESS_TOKEN: Optional[str] = None

    CLIENTIFY_API_KEY: Optional[str] = None
    CLIENTIFY_BASE_URL: str = "https://api.clientify.com/v1"

    HOST: str = "0.0.0.0"
    PORT: int = 8000

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
