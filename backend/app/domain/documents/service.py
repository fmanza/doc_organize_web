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
    conversion_status: str | None = None,
    limit: int,
    offset: int,
) -> tuple[list[DocumentRow], int]:
    """Página de documentos del proyecto (o de una carpeta) y el total, con búsqueda en la ruta relativa a su carpeta y
    filtro por estado de conversión.

    Raises:
        FolderNotInProjectError: ``folder`` no es una carpeta de origen del proyecto.
    """
    state = state_dir(settings, project.id)
    search = (search or "").strip() or None
    source = project.source_location
    timeout = settings.location_probe_timeout_seconds
    # La caché guarda las rutas que recibió doc_organize: la carpeta resuelta (la última raíz de folder_roots).
    roots = {
        subpath: folder_roots(source.container_path, subpath, timeout=timeout)
        for subpath in select_folders(project, folder)
    }
    counts = [
        (
            subpath,
            library_cache.count_documents(
                folder_cache(state, subpath), search, root=folder_root[-1], conversion_status=conversion_status
            ),
        )
        for subpath, folder_root in roots.items()
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
        page = library_cache.documents_page(
            folder_cache(state, subpath),
            root=roots[subpath][-1],
            limit=wanted,
            offset=skip,
            search=search,
            conversion_status=conversion_status,
        )
        skip = 0
        wanted -= len(page)
        namer = DocumentNamer([(subpath, roots[subpath])], source.name)
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


def read_inside(target: Path, root: Path, *, max_bytes: int | None = None) -> bytes:
    """Lee ``target`` si, **una vez abierto**, sigue siendo un fichero normal dentro de ``root``.

    Se comprueba el descriptor y no solo la ruta: si alguien cambia el fichero o una carpeta por un enlace simbólico
    entre la comprobación y la lectura, lo abierto ya no está dentro de ``root`` y no se sirve. También lo usan el
    manifiesto de taxonomía y el sitio de contexto (Fase 7).
    """
    if max_bytes is None:
        max_bytes = MAX_OUTPUT_BYTES
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
        too_large = f"El fichero pasa de {max_bytes // (1024 * 1024) or 1} MB: descárgalo con «Exportar»."
        if info.st_size > max_bytes:
            raise OutputTooLargeError(too_large)
        data = handle.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise OutputTooLargeError(too_large)
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
        return target, read_inside(target, conversion.absolute)

    target, data = run_with_timeout(_read, timeout)
    if content_type == "application/json":
        data = json_output(settings, project, data, clean)
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


def _folder_of(project: Project, output: str) -> str | None:
    """Carpeta de origen a la que pertenece una salida (``<carpeta>/…`` dentro de ``Conversión/``)."""
    matches = [f for f in project.source_subpaths if f == "" or output.startswith(f"{f}/")]
    return max(matches, key=len) if matches else None


def json_output(settings: Settings, project: Project, raw: bytes, output: str) -> bytes:
    """JSON de un documento convertido con ``source_path`` relativa a la carpeta de origen (``2024/facturas/a.pdf``).

    Desde doc_organize 0.12.0 (G23) ``source_path`` ya es relativa a la carpeta escaneada (``facturas/a.pdf``): se le
    antepone la carpeta. Los JSON convertidos antes llevan la ruta absoluta del contenedor hasta reconvertirse: se
    sustituye por la relativa. Si el fichero no es un objeto JSON válido, se sirve tal cual.
    """
    try:
        data = json.loads(raw)
    except ValueError:
        return raw
    source = data.get("source_path") if isinstance(data, dict) else None
    if not isinstance(source, str):
        return raw
    if source.startswith("/"):
        data["source_path"] = project_namer(settings, project).display(source)
    else:
        folder = _folder_of(project, output)
        data["source_path"] = f"{folder}/{source}" if folder else source
    return json.dumps(data, ensure_ascii=False).encode("utf-8")
