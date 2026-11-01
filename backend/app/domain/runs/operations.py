"""Catálogo de operaciones: parámetros (validados con Pydantic en la API y otra vez en el worker), rol mínimo, cola y
si escriben en el proyecto.

Las operaciones que mueven o borran ficheros (regla 7) se lanzan primero con ``dry_run`` (vista previa, sin escritura)
y después con ``preview_run_id`` de esa vista previa y ``confirm_name`` igual al nombre del proyecto.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator

from app.db.models import MemberRole, RunQueue

FolderName = Annotated[str, Field(min_length=1, max_length=120)]


class _Params(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NoopParams(_Params):
    """Prueba del motor: ``steps`` pasos de ``step_seconds`` con progreso; ``fail_at_step`` simula un fallo."""

    operation: Literal["noop"] = "noop"
    steps: int = Field(default=5, ge=1, le=100)
    step_seconds: float = Field(default=1.0, ge=0, le=10)
    fail_at_step: int | None = Field(default=None, ge=1, le=100)


class _Destructive(_Params):
    """Parámetros comunes de las operaciones con vista previa."""

    dry_run: bool = True
    preview_run_id: str | None = Field(default=None, max_length=36)
    confirm_name: str | None = Field(default=None, max_length=128)


class HistoryClearParams(_Destructive):
    """Vaciar el histórico: borra las salidas y el estado de doc_organize del proyecto."""

    operation: Literal["history_clear"] = "history_clear"


class ProjectMoveParams(_Destructive):
    """Mover la carpeta de salidas a ``destination_parent/new_folder`` de una ubicación destino ``rw``."""

    operation: Literal["project_move"] = "project_move"
    destination_location_id: int = Field(ge=1)
    destination_parent: str = Field(default="", max_length=4096)
    new_folder: FolderName


class ProjectDeleteParams(_Destructive):
    """Borrar el proyecto; con ``delete_outputs`` también su carpeta de salidas (el estado se borra siempre)."""

    operation: Literal["project_delete"] = "project_delete"
    delete_outputs: bool = False


class ScanParams(_Params):
    """Escanear y convertir carpetas de origen del proyecto (``ScanOptions`` de doc_organize, G13).

    ``folders`` vacío = todas las carpetas de origen. Con ``force`` (vacía la caché y **borra** las salidas de lo que
    ya no está en el origen) son obligatorias todas las carpetas, el rol ``owner`` y el patrón de vista previa
    (``dry_run``, ``preview_run_id``, ``confirm_name``); sin ``force`` no hay vista previa.
    """

    operation: Literal["scan"] = "scan"
    folders: list[Annotated[str, Field(max_length=4096)]] = Field(default_factory=list, max_length=20)
    use_ocr: bool = True
    use_gpu: bool = False
    force: bool = False
    include_audio_video: bool = False
    extract_images: bool = False
    use_picture_description: bool = False
    dry_run: bool = False
    preview_run_id: str | None = Field(default=None, max_length=36)
    confirm_name: str | None = Field(default=None, max_length=128)

    @model_validator(mode="after")
    def _preview_only_with_force(self) -> ScanParams:
        if self.dry_run and not self.force:
            raise ValueError("La vista previa solo existe para «forzar reconversión»")
        return self


RunParams = Annotated[
    NoopParams | HistoryClearParams | ProjectMoveParams | ProjectDeleteParams | ScanParams,
    Field(discriminator="operation"),
]
RUN_PARAMS: Final[TypeAdapter[RunParams]] = TypeAdapter(RunParams)

#: Parámetros que deben coincidir entre la vista previa y la ejecución real.
_PREVIEW_KEYS: Final[dict[str, tuple[str, ...]]] = {
    "history_clear": (),
    "project_move": ("destination_location_id", "destination_parent", "new_folder"),
    "project_delete": ("delete_outputs",),
    "scan": ("force",),
}


@dataclass(frozen=True)
class OperationSpec:
    """Propiedades fijas de una operación.

    Attributes:
        min_role: Rol mínimo en el proyecto para lanzarla.
        queue: Cola por defecto (``scan`` con ``use_gpu`` va a ``gpu``, ver ``queue_for``).
        destructive: Mueve o borra ficheros: exige vista previa (``dry_run``) y confirmación.
        produces_artifacts: Deja ficheros en el workspace (cuenta para la cuota).
    """

    min_role: MemberRole
    queue: RunQueue = "cpu"
    destructive: bool = False
    produces_artifacts: bool = False


OPERATIONS: Final[dict[str, OperationSpec]] = {
    "noop": OperationSpec(min_role="editor", produces_artifacts=True),
    "history_clear": OperationSpec(min_role="owner", destructive=True),
    "project_move": OperationSpec(min_role="owner", destructive=True),
    "project_delete": OperationSpec(min_role="owner", destructive=True),
    "scan": OperationSpec(min_role="editor", produces_artifacts=True),
}


def is_write(params: RunParams) -> bool:
    """Si el run escribe en el proyecto (bloqueo de una escritura a la vez): las destructivas sin ``dry_run`` y el
    escaneo (escribe las salidas), salvo su vista previa."""
    if isinstance(params, ScanParams):
        return not params.dry_run
    return isinstance(params, _Destructive) and not params.dry_run


def needs_preview(params: RunParams) -> bool:
    """Si la ejecución real exige una vista previa confirmada (regla 7)."""
    if isinstance(params, ScanParams):
        return params.force and not params.dry_run
    return OPERATIONS[params.operation].destructive and is_write(params)


def min_role(params: RunParams) -> MemberRole:
    """Rol mínimo para lanzar ``params``: «forzar reconversión» borra salidas, así que es de ``owner``."""
    if isinstance(params, ScanParams) and params.force:
        return "owner"
    return OPERATIONS[params.operation].min_role


def queue_for(params: RunParams) -> RunQueue:
    """Cola del run: un escaneo con GPU necesita un worker de la cola ``gpu``."""
    if isinstance(params, ScanParams) and params.use_gpu and not params.dry_run:
        return "gpu"
    return OPERATIONS[params.operation].queue


def preview_matches(params: RunParams, preview: dict[str, object]) -> bool:
    """Si la vista previa ``preview`` (``params`` guardados) corresponde a la ejecución real ``params``."""
    if preview.get("operation") != params.operation or preview.get("dry_run") is not True:
        return False
    return all(preview.get(key) == getattr(params, key) for key in _PREVIEW_KEYS.get(params.operation, ()))


def stored_params(params: RunParams) -> dict[str, object]:
    """Parámetros tal como se guardan en ``runs.params`` (sin secretos: ninguna operación los recibe)."""
    return params.model_dump(mode="json")
