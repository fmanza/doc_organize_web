"""Capa anticorrupción con doc_organize (ADR-006).

Es el **único** paquete de la aplicación que importa ``doc_organize`` (lo comprueba
``tests/unit/test_architecture.py``). El resto del backend depende de las funciones y tipos propios que se exponen
aquí, de modo que un cambio de API de la librería solo obliga a tocar esta capa. Los rodeos temporales de huecos de
la librería llevan su ``G<n>`` de ``docs/plan/DOC_ORGANIZE_GAPS.md``.

Importar este paquete **no** importa doc_organize (G15): ``library_version`` lee los metadatos, las capacidades se
obtienen en un subproceso y las operaciones importan la librería dentro de la función, solo en el subproceso del job.
Lo comprueba ``tests/unit/test_architecture.py``.
"""

from app.integrations.doc_organize.capabilities import Capabilities, run_probe
from app.integrations.doc_organize.models import ModelsStatus
from app.integrations.doc_organize.models import status as models_status
from app.integrations.doc_organize.projects import DocOrganizeOperationError, clear_project_history
from app.integrations.doc_organize.scan import (
    ScanFailure,
    ScanOutcome,
    ScanProgress,
    ScanRequest,
    cached_paths,
    conversion_dir,
    run_scan,
)
from app.integrations.doc_organize.version import library_version

__all__ = [
    "Capabilities",
    "DocOrganizeOperationError",
    "ModelsStatus",
    "ScanFailure",
    "ScanOutcome",
    "ScanProgress",
    "ScanRequest",
    "cached_paths",
    "clear_project_history",
    "conversion_dir",
    "library_version",
    "models_status",
    "run_probe",
    "run_scan",
]
