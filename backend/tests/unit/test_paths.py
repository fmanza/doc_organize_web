"""Resolvedor de rutas (ADR-007): sintaxis, escape por enlaces simbólicos, oráculo de existencia y timeouts."""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from app.domain.locations.errors import FolderNotFoundError, InvalidRelativePathError, LocationUnavailableError
from app.domain.locations.paths import (
    list_subfolders,
    normalize_relative,
    parent_of,
    resolve_within,
    run_with_timeout,
)


def _can_symlink(tmp_path: Path) -> bool:
    try:
        (tmp_path / "_probe_link").symlink_to(tmp_path, target_is_directory=True)
    except (OSError, NotImplementedError):
        return False
    (tmp_path / "_probe_link").unlink()
    return True


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    """``root/{a/b, c}`` con un fichero en la raíz y una carpeta hermana fuera de la raíz."""
    root = tmp_path / "root"
    (root / "a" / "b").mkdir(parents=True)
    (root / "c").mkdir()
    (root / "fichero.txt").write_text("x", encoding="utf-8")
    (tmp_path / "fuera" / "secreta").mkdir(parents=True)
    return root


@pytest.mark.parametrize(
    ("raw", "expected"), [(None, ""), ("", ""), (".", ""), ("a/b", "a/b"), ("a//b/", "a/b"), ("./a/./b", "a/b")]
)
def test_normalize_accepts_relative_paths(raw: str | None, expected: str) -> None:
    assert normalize_relative(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "/etc",
        "//nas.example.internal/share",
        "\\\\nas\\share",
        "C:\\Windows",
        "c:/x",
        "a\\b",
        "../fuera",
        "a/../../x",
        "a\x00b",
    ],
)
def test_normalize_rejects_absolute_unc_drive_backslash_dotdot_and_nul(raw: str) -> None:
    with pytest.raises(InvalidRelativePathError):
        normalize_relative(raw)


def test_resolve_inside_root(tree: Path) -> None:
    resolved = resolve_within(tree, "a/b", timeout=5)

    assert resolved.relative == "a/b"
    assert resolved.absolute == (tree / "a" / "b").resolve()
    assert resolve_within(tree, "", timeout=5).relative == ""


@pytest.mark.parametrize("raw", ["no-existe", "a/no-existe", "fichero.txt"])
def test_missing_or_not_a_folder_is_not_found(tree: Path, raw: str) -> None:
    with pytest.raises(FolderNotFoundError):
        resolve_within(tree, raw, timeout=5)


def test_symlink_escaping_root_is_not_found_like_a_missing_folder(tree: Path, tmp_path: Path) -> None:
    if not _can_symlink(tmp_path):
        pytest.skip("Sin permiso para crear enlaces simbólicos (Windows sin modo desarrollador)")
    (tree / "salida").symlink_to(tmp_path / "fuera", target_is_directory=True)

    with pytest.raises(FolderNotFoundError) as escaped:
        resolve_within(tree, "salida/secreta", timeout=5)
    with pytest.raises(FolderNotFoundError) as missing:
        resolve_within(tree, "salida/no-existe", timeout=5)

    assert (escaped.value.status, escaped.value.detail) == (missing.value.status, missing.value.detail)


def test_symlink_inside_root_is_followed(tree: Path, tmp_path: Path) -> None:
    if not _can_symlink(tmp_path):
        pytest.skip("Sin permiso para crear enlaces simbólicos (Windows sin modo desarrollador)")
    (tree / "atajo").symlink_to(tree / "a", target_is_directory=True)

    assert resolve_within(tree, "atajo/b", timeout=5).relative == "a/b"


def test_missing_root_is_unavailable(tmp_path: Path) -> None:
    with pytest.raises(LocationUnavailableError):
        resolve_within(tmp_path / "desmontada", "", timeout=5)


def test_list_subfolders_sorted_without_files_or_escaping_links(tree: Path, tmp_path: Path) -> None:
    (tree / "B-mayúscula").mkdir()
    if _can_symlink(tmp_path):
        (tree / "salida").symlink_to(tmp_path / "fuera", target_is_directory=True)

    names = list_subfolders(resolve_within(tree, "", timeout=5), timeout=5)

    assert names == ["a", "B-mayúscula", "c"]


def test_slow_io_becomes_unavailable() -> None:
    start = time.monotonic()
    with pytest.raises(LocationUnavailableError):
        run_with_timeout(lambda: time.sleep(2), timeout=0.1)

    assert time.monotonic() - start < 1.5


@pytest.mark.parametrize(("relative", "parent"), [("", None), ("a", ""), ("a/b/c", "a/b")])
def test_parent_of(relative: str, parent: str | None) -> None:
    assert parent_of(relative) == parent


def test_unreadable_folder_is_unavailable(tree: Path) -> None:
    if os.name == "nt" or os.geteuid() == 0:
        pytest.skip("Los permisos POSIX no aplican en Windows ni como root")
    locked = tree / "a"
    locked.chmod(0)
    try:
        with pytest.raises(LocationUnavailableError):
            list_subfolders(resolve_within(tree, "a", timeout=5), timeout=5)
    finally:
        locked.chmod(0o755)
