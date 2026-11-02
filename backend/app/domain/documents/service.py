"""Documentos de un proyecto (caché de doc_organize) y salidas convertidas para el visor (WB-5.1, WB-5.2).

Solo consultas: la API no escribe nada en el proyecto. Las cachés son una por carpeta de origen (Fase 4); el listado
las recorre en el orden de las carpetas y, dentro de cada una, por ruta (``load_cache_page``), así que la paginación
es estable aunque crucen varias cachés.
"""

from __future__ import annotations

import json
import os
import stat
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from app.core.config import Settings
from app.db.models import Project
from app.domain.documents.errors import (
    FolderNotInProjectError,
    OutputNotFoundError,
    OutputTooLargeError,
    OutputTypeNotAllowedError,
)
from app.domain.documents.outputs import output_paths
from app.domain.documents.paths import DocumentNamer, folder_roots
from app.domain.locations.errors import FolderNotFoundError
from app.domain.locations.paths import join_relative, normalize_relative, resolve_within, run_with_timeout
from app.domain.projects.service import state_dir
from app.domain.scan.state import CONVERSION_DIR, folder_cache
from app.integrations.doc_organize import cache as library_cache

#: Tamaño máximo que sirve el visor; lo demás se obtiene con una exportación.
MAX_OUTPUT_BYTES: Final = 20 * 1024 * 1024
#: Tipos que sirve el visor, con ``Content-Type`` fijo. Nada que el navegador ejecute (SVG, HTML, PDF).
OUTPUT_TYPES: Final[dict[str, str]] = {
    ".md": "text/markdown; charset=utf-8",
    ".json": "application/json",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}
MAX_ERROR_MESSAGE: Final = 2000


@dataclass(frozen=True)
class DocumentRow:
    """Documento de la caché tal como lo ve el usuario.

    Attributes:
        folder: Carpeta de origen (``""`` = la raíz de la ubicación).
        path: Ruta relativa a la carpeta.
        output_path: Markdown relativo a ``Conversión/`` si se convirtió.
    """

    folder: str
    path: str
    status: str
    conversion_status: str | None
    error_message: str | None
    error_retry_count: int
    updated_at: datetime
    output_path: str | None


def select_folders(project: Project, folder: str | None) -> list[str]:
    """Carpetas de origen del proyecto (o solo ``folder``, validada).

    Raises:
        FolderNotInProjectError: ``folder`` no es una carpeta de origen del proyecto.
    """
    folders = sorted(project.source_subpaths, key=str.casefold)
    if folder is None:
        return folders
    clean = normalize_relative(folder)
    if clean not in folders:
        raise FolderNotInProjectError(f"«{clean or '(raíz)'}» no es una carpeta de origen del proyecto.")
    return [clean]


def list_documents(
    settings: Settings,
    project: Project,
    *,
    folder: str | None = None,
    search: str | None = None,
    limit: int,
    offset: int,
) -> tuple[list[DocumentRow], int]:
    """Página de documentos del proyecto (o de una carpeta) y el total, con búsqueda en la ruta.

    Raises:
        FolderNotInProjectError: ``folder`` no es una carpeta de origen del proyecto.
    """
    state = state_dir(settings, project.id)
    search = (search or "").strip() or None
    counts = [
        (subpath, library_cache.count_documents(folder_cache(state, subpath), search))
        for subpath in select_folders(project, folder)
    ]
    total = sum(count for _, count in counts)
    rows: list[DocumentRow] = []
    skip, wanted = offset, limit
    for subpath, count in counts:
        if wanted <= 0:
            break
        if skip >= count:
            skip -= count
            continue
        page = library_cache.documents_page(folder_cache(state, subpath), limit=wanted, offset=skip, search=search)
        skip = 0
        wanted -= len(page)
        source = project.source_location
        roots = folder_roots(source.container_path, subpath, timeout=settings.location_probe_timeout_seconds)
        namer = DocumentNamer([(subpath, roots)], source.name)
        for entry in page:
            parts = namer.split(entry.path)
            relative = parts[1] if parts else Path(entry.path).name
            rows.append(
                DocumentRow(
                    folder=subpath,
                    path=relative,
                    status=entry.status,
                    conversion_status=entry.conversion_status,
                    error_message=namer.text(entry.error_message)[:MAX_ERROR_MESSAGE] if entry.error_message else None,
                    error_retry_count=entry.error_retry_count,
                    updated_at=datetime.fromtimestamp(entry.updated_at, UTC),
                    output_path=output_paths(subpath, relative).markdown
                    if entry.conversion_status == "success" and parts
                    else None,
                )
            )
    return rows, total


@dataclass(frozen=True)
class OutputContent:
    """Salida leída para el visor: nombre del fichero, contenido y ``Content-Type`` fijo."""

    name: str
    content: bytes
    content_type: str


def _read_inside(target: Path, root: Path) -> bytes:
    """Lee ``target`` si, **una vez abierto**, sigue siendo un fichero normal dentro de ``root``.

    Se comprueba el descriptor y no solo la ruta: si alguien cambia el fichero o una carpeta por un enlace simbólico
    entre la comprobación y la lectura, lo abierto ya no está dentro de ``root`` y no se sirve.
    """
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    try:
        fd = os.open(target, flags)
    except OSError:
        raise OutputNotFoundError() from None
    with os.fdopen(fd, "rb") as handle:
        info = os.fstat(handle.fileno())
        if not stat.S_ISREG(info.st_mode):
            raise OutputNotFoundError()
        proc = Path(f"/proc/self/fd/{handle.fileno()}")
        opened = Path(os.readlink(proc)) if proc.is_symlink() else target
        if not opened.is_relative_to(root):
            raise OutputNotFoundError()
        if info.st_size > MAX_OUTPUT_BYTES:
            raise OutputTooLargeError("El fichero pasa de 20 MB: descárgalo con «Exportar».")
        data = handle.read(MAX_OUTPUT_BYTES + 1)
    if len(data) > MAX_OUTPUT_BYTES:
        raise OutputTooLargeError("El fichero pasa de 20 MB: descárgalo con «Exportar».")
    return data


def read_output(settings: Settings, project: Project, path: str) -> OutputContent:
    """Fichero de ``Conversión/`` del proyecto que pide el visor, con su ``Content-Type``.

    Pasa por el resolvedor de ubicaciones; el fichero, una vez resuelto y abierto, debe seguir dentro de
    ``Conversión/``. Inexistente o fuera dan el mismo error. El JSON se sirve sin rutas del contenedor (G23).

    Raises:
        InvalidRelativePathError: Ruta no relativa o con ``..``.
        OutputTypeNotAllowedError: Extensión que el visor no sirve.
        OutputNotFoundError: No existe, no es un fichero normal o queda fuera de ``Conversión/``.
        OutputTooLargeError: Supera ``MAX_OUTPUT_BYTES``.
        LocationUnavailableError: La ubicación destino no responde.
    """
    clean = normalize_relative(path)
    content_type = OUTPUT_TYPES.get(Path(clean).suffix.lower())
    if not clean:
        raise OutputNotFoundError()
    if content_type is None:
        raise OutputTypeNotAllowedError("El visor solo muestra Markdown, JSON e imágenes PNG, JPEG, GIF o WebP.")
    destination = project.destination_location
    timeout = settings.location_probe_timeout_seconds
    try:
        conversion = resolve_within(
            Path(destination.container_path),
            join_relative(project.destination_subpath, CONVERSION_DIR),
            timeout=timeout,
        )
    except FolderNotFoundError:
        raise OutputNotFoundError() from None

    def _read() -> tuple[Path, bytes]:
        try:
            target = (conversion.absolute / clean).resolve(strict=True)
        except OSError:
            raise OutputNotFoundError() from None
        if not target.is_relative_to(conversion.absolute):
            raise OutputNotFoundError()
        return target, _read_inside(target, conversion.absolute)

    target, data = run_with_timeout(_read, timeout)
    if content_type == "application/json":
        data = json_output(settings, project, data)
    return OutputContent(name=target.name, content=data, content_type=content_type)


def project_namer(settings: Settings, project: Project) -> DocumentNamer:
    """Nombres de documentos relativos a las carpetas de origen del proyecto (sin rutas del contenedor)."""
    source = project.source_location
    timeout = settings.location_probe_timeout_seconds
    return DocumentNamer(
        [
            (subpath, folder_roots(source.container_path, subpath, timeout=timeout))
            for subpath in project.source_subpaths
        ],
        source.name,
    )


def json_output(settings: Settings, project: Project, raw: bytes) -> bytes:
    """JSON de un documento convertido sin rutas del contenedor.

    doc_organize escribe en ``source_path`` la ruta absoluta del documento de origen (G23); el visor la sustituye por
    la relativa a su carpeta (``2024/facturas/a.pdf``). Si el fichero no es un objeto JSON válido, se sirve tal cual
    (el visor lo muestra como texto).
    """
    try:
        data = json.loads(raw)
    except ValueError:
        return raw
    if isinstance(data, dict) and isinstance(data.get("source_path"), str):
        data["source_path"] = project_namer(settings, project).display(data["source_path"])
        return json.dumps(data, ensure_ascii=False).encode("utf-8")
    return raw
