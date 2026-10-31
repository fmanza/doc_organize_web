"""Configuración de la aplicación leída de variables de entorno (prefijo ``DOW_``) y Docker secrets."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal, Self

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DOCKER_SECRETS_DIR = Path("/run/secrets")


class Settings(BaseSettings):
    """Ajustes del proceso.

    Los secretos se leen de ``/run/secrets`` cuando la aplicación corre con Docker secrets (ficheros
    ``dow_app_secret_key`` y ``dow_fernet_keys``: pydantic-settings aplica el prefijo también a los secretos). En
    ``production`` son obligatorios: sin ellos la aplicación no arranca.

    Attributes:
        environment: ``development`` (habilita ``/api/docs``), ``test`` o ``production``.
        data_dir: Volumen local con ``config.db`` y ``projects/<id>/cache.db``; nunca una ubicación de red (ADR-005).
        workspace_dir: Raíz de los artefactos por ejecución (volumen ``workspace``).
        locations_root: Única raíz bajo la que puede registrarse una ubicación (Fase 2, ADR-007).
        models_dir: Modelos de Docling/OCR precargados (Fase 4, ADR-011).
        static_dir: Build del frontend servido por la API; si no existe, solo se sirve ``/api``.
        log_level: Nivel del logger raíz.
        app_secret_key: Clave de firma de CSRF (Fase 1, ADR-003).
        fernet_keys: Claves Fernet separadas por comas; la primera cifra (Fase 8, ADR-004).
    """

    model_config = SettingsConfigDict(env_prefix="DOW_", secrets_dir=None, extra="ignore")

    environment: Literal["development", "test", "production"] = "production"
    data_dir: Path = Path("/data")
    workspace_dir: Path = Path("/workspace")
    locations_root: Path = Path("/mnt")
    models_dir: Path = Path("/models")
    static_dir: Path = Path("/app/static")
    log_level: str = "INFO"
    app_secret_key: SecretStr | None = None
    fernet_keys: SecretStr | None = None

    @model_validator(mode="after")
    def _require_secrets_in_production(self) -> Self:
        missing = [name for name in ("app_secret_key", "fernet_keys") if getattr(self, name) is None]
        if self.environment == "production" and missing:
            files = ", ".join(f"dow_{name}" for name in missing)
            raise ValueError(f"Faltan secretos obligatorios en producción: {files} (scripts/generate_secrets.py)")
        return self

    @property
    def database_url(self) -> str:
        """URL SQLAlchemy de ``config.db``."""
        return f"sqlite:///{(self.data_dir / 'config.db').as_posix()}"


@lru_cache
def get_settings() -> Settings:
    """Ajustes del proceso, leídos una vez; con ``/run/secrets`` presente lee de ahí los secretos."""
    if DOCKER_SECRETS_DIR.is_dir():
        return Settings(_secrets_dir=DOCKER_SECRETS_DIR)
    return Settings()
