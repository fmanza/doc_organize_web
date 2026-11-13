"""Configuración de la aplicación leída de variables de entorno (prefijo ``DOW_``) y Docker secrets."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, SecretStr, model_validator
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
        session_idle_minutes: Caducidad de la sesión por inactividad.
        session_absolute_hours: Caducidad absoluta de la sesión desde el inicio de sesión.
        login_max_attempts: Intentos fallidos seguidos que bloquean la cuenta.
        login_lockout_minutes: Duración del bloqueo temporal.
        password_min_length: Longitud mínima de contraseña (la máxima es fija, 128).
        location_probe_timeout_seconds: Tiempo máximo de un sondeo o listado de una ubicación (montajes colgados).
        location_latency_degraded_ms: Latencia de ``stat`` a partir de la que una ubicación está ``degraded``.
        location_min_free_gb: Espacio libre por debajo del que una ubicación está ``degraded`` (0 = no se comprueba).
        location_probe_interval_minutes: Cada cuánto sondea el worker las ubicaciones (0 = nunca; Fase 3).
        worker_queues: Colas que atiende el worker, separadas por comas (``cpu``, ``gpu``; ADR-002).
        worker_concurrency: Jobs simultáneos por worker (Docling consume mucha memoria).
        worker_heartbeat_seconds: Intervalo del latido del worker y de sus runs.
        job_timeout_seconds: Duración máxima de un run; después se termina su subproceso.
        cancel_grace_seconds: Plazo para que un run atienda la cancelación antes de terminar su subproceso.
        timeout_grace_seconds: Plazo para la parada ordenada al vencer el timeout: doc_organize solo para entre
            documentos y un PDF grande con OCR tarda minutos (si no para, se pierde la caché en curso, G16).
        run_retention_days: Días que se conservan las carpetas del workspace de los runs terminados.
        user_quota_mb: Espacio máximo de artefactos por usuario en el workspace (0 = sin límite).
        context_site_timeout_seconds: Tiempo máximo de ``zensical build`` al construir el contexto (Fase 7); si se
            pasa, el contexto queda sin sitio y con un aviso.
        ai_timeout_seconds: Tiempo máximo de cada petición a un servicio de IA (Fase 8).
        ai_retries: Reintentos de un timeout o error de conexión de cada petición a un servicio de IA (Fase 8, L-3b).
        ai_max_documents_per_run: Documentos que un run puede enviar a la IA como mucho (presupuesto, Fase 8).
        ai_draft_timeout_seconds: Tiempo máximo de la petición del borrador de manifiesto, que es una sola y mucho
            más larga que una clasificación (un modelo local puede tardar minutos); sustituye a ``ai_timeout_seconds``
            en esa familia.
        ai_draft_retries: Reintentos del borrador de manifiesto ante un timeout o error de conexión; 0 por defecto,
            porque reintentar un timeout vuelve a encolar la misma generación en el modelo.
        scan_recycle_documents: Documentos convertidos tras los que el escaneo sigue en un subproceso nuevo del mismo
            run (la memoria de Docling crece durante un escaneo largo, G38; 0 = nunca; Fase 10). Desde la 1.1.0 lo
            aplica doc_organize (``ScanOptions.max_documents``).
        scan_document_timeout_seconds: Segundos máximos por documento y pasada de conversión; el que los supera queda
            como error y el escaneo sigue (G11, 1.1.0). 0 = sin límite. El hilo de Docling no se interrumpe: termina en
            segundo plano y deja un pico de memoria.
        scan_io_retries: Reintentos ante errores de E/S transitorios al listar, leer, hashear y copiar (G11, 1.1.0).
        scan_reuse_hashes: No rehashear un fichero cuyo tamaño y fecha coinciden con la caché (G11, 1.1.0); «forzar»
            rehashea todo. No detecta un cambio que conserve tamaño y fecha.
        rate_limit_login: Intentos de inicio de sesión por minuto e IP (Fase 10).
        rate_limit_write: Peticiones de escritura a ``/api/v1`` por minuto e IP (Fase 10).
        max_request_mb: Tamaño máximo del cuerpo de una petición (413 si se pasa; Fase 10).
        metrics_token: Token *Bearer* de ``/metrics``; sin él, ``/metrics`` no existe (404; secreto
            ``dow_metrics_token``, Fase 10).

    Los ajustes de identidad, sondeo, retención, cuota e IA son administrables desde la web (ADR-012): estos valores
    son el defecto.
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
    session_idle_minutes: int = Field(default=60, ge=5, le=24 * 60)
    session_absolute_hours: int = Field(default=12, ge=1, le=24 * 30)
    login_max_attempts: int = Field(default=5, ge=1, le=100)
    login_lockout_minutes: int = Field(default=15, ge=1, le=24 * 60)
    password_min_length: int = Field(default=12, ge=8, le=128)
    location_probe_timeout_seconds: int = Field(default=10, ge=1, le=120)
    location_latency_degraded_ms: int = Field(default=500, ge=10, le=60_000)
    location_min_free_gb: int = Field(default=5, ge=0, le=100_000)
    location_probe_interval_minutes: int = Field(default=5, ge=0, le=24 * 60)
    worker_queues: str = Field(default="cpu", pattern=r"^(cpu|gpu)(,(cpu|gpu))*$")
    worker_concurrency: int = Field(default=1, ge=1, le=8)
    worker_heartbeat_seconds: int = Field(default=10, ge=2, le=60)
    job_timeout_seconds: int = Field(default=21_600, ge=60, le=7 * 24 * 3600)
    cancel_grace_seconds: int = Field(default=30, ge=5, le=600)
    timeout_grace_seconds: int = Field(default=600, ge=5, le=3600)
    run_retention_days: int = Field(default=30, ge=1, le=3650)
    user_quota_mb: int = Field(default=0, ge=0, le=10_000_000)
    context_site_timeout_seconds: int = Field(default=600, ge=10, le=24 * 3600)
    ai_timeout_seconds: int = Field(default=30, ge=5, le=300)
    ai_retries: int = Field(default=2, ge=0, le=5)
    ai_max_documents_per_run: int = Field(default=500, ge=1, le=100_000)
    ai_draft_timeout_seconds: int = Field(default=300, ge=5, le=900)
    ai_draft_retries: int = Field(default=0, ge=0, le=5)
    scan_recycle_documents: int = Field(default=200, ge=0, le=1_000_000)
    scan_document_timeout_seconds: int = Field(default=0, ge=0, le=7 * 24 * 3600)
    scan_io_retries: int = Field(default=2, ge=0, le=10)
    scan_reuse_hashes: bool = True
    rate_limit_login: int = Field(default=10, ge=1, le=10_000)
    rate_limit_write: int = Field(default=120, ge=1, le=100_000)
    max_request_mb: int = Field(default=16, ge=1, le=1024)
    metrics_token: SecretStr | None = None

    @model_validator(mode="after")
    def _require_secrets_in_production(self) -> Self:
        missing = [name for name in ("app_secret_key", "fernet_keys") if getattr(self, name) is None]
        if self.environment == "production" and missing:
            files = ", ".join(f"dow_{name}" for name in missing)
            raise ValueError(f"Faltan secretos obligatorios en producción: {files} (scripts/generate_secrets.py)")
        return self

    @property
    def cookie_secure(self) -> bool:
        """``Secure`` en las cookies salvo en ``development`` (HTTP local sin TLS, ADR-003)."""
        return self.environment != "development"

    @property
    def session_cookie(self) -> str:
        """Cookie de sesión: con prefijo ``__Host-`` (exige ``Secure``, ``Path=/`` y sin ``Domain``) fuera de desarrollo."""
        return "__Host-dow_session" if self.cookie_secure else "dow_session"

    @property
    def csrf_cookie(self) -> str:
        """Cookie del token CSRF de doble envío, legible por la SPA."""
        return "__Host-dow_csrf" if self.cookie_secure else "dow_csrf"

    @property
    def queues(self) -> tuple[str, ...]:
        """Colas de ``worker_queues`` sin repetir, en orden."""
        return tuple(dict.fromkeys(self.worker_queues.split(",")))

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
