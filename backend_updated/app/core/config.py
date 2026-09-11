"""
WeatherGPT Backend — Core Configuration

Reads all environment variables via pydantic-settings.
Defaults are set so the app can boot even with no .env file (using mocks).
"""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings, loaded from environment / .env file."""

    # --- Core ---
    app_name: str = "WeatherGPT"
    debug: bool = False
    frontend_origin: str = "http://localhost:3000"

    # --- Weather Data ---
    openweather_api_key: Optional[str] = None

    # --- Vector DB ---
    qdrant_url: str = "http://localhost:6333"
    chroma_persist_dir: str = "./chroma_data"

    # --- LLM ---
    groq_api_key: Optional[str] = None
    groq_model: str = "llama-3.3-70b-versatile"
    groq_fallback_model: str = "llama-3.1-8b-instant"

    # --- Translation ---
    bhashini_user_id: Optional[str] = None
    bhashini_ulca_api_key: Optional[str] = None
    bhashini_inference_key: Optional[str] = None

    # --- WhatsApp (Twilio) ---
    twilio_account_sid: Optional[str] = None
    twilio_auth_token: Optional[str] = None
    twilio_whatsapp_from: str = "whatsapp:+14155238886"

    # Optional protection for the local subscription-inspection endpoint.
    admin_api_key: Optional[str] = None

    # --- Database ---
    database_url: str = "sqlite+aiosqlite:///./weathergpt.db"

    # --- Auth (Phase 7) ---
    # Used to sign JWT access tokens. Override this in .env for any real
    # deployment — the default is only safe for local demo use.
    secret_key: str = "dev-only-change-me-in-production"
    access_token_expire_minutes: int = 60 * 24 * 7  # 7 days

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()
