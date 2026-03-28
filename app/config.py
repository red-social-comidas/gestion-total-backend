"""
app/config.py
Punto único de acceso a variables de entorno.
Falla en startup si falta una variable requerida — nunca en runtime.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── Base de datos ─────────────────────────────────────────────────────────
    database_url: str

    # ── JWT ───────────────────────────────────────────────────────────────────
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_hours: int = 8
    refresh_token_expire_days: int = 30

    # ── Cloudinary (opcional en MVP) ──────────────────────────────────────────
    cloudinary_cloud_name: str = ""
    cloudinary_api_key: str = ""
    cloudinary_api_secret: str = ""

    # ── Sync API ──────────────────────────────────────────────────────────────
    sync_api_key: str 

    # ── Entorno ───────────────────────────────────────────────────────────────
    environment: str = "development"

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def cloudinary_configured(self) -> bool:
        return bool(
            self.cloudinary_cloud_name
            and self.cloudinary_api_key
            and self.cloudinary_api_secret
        )

    model_config = {"env_file": ".env"}


@lru_cache()
def get_settings() -> Settings:
    return Settings()
