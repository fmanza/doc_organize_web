"""Hotfix 0.10.1: un subproceso que mata el OOM del contenedor se cierra como ``out_of_memory``, no como «terminó de
forma inesperada» (escaneo de 521 documentos reales con el worker en 6 GiB: ``exitcode -9`` y ``OOMKilled``)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.jobs import worker

CGROUP_V2 = "low 0\nhigh 0\nmax 74749\noom 4\noom_kill 1\noom_group_kill 0\n"
CGROUP_V1 = "oom_kill_disable 0\nunder_oom 0\noom_kill 3\n"


def test_oom_kills_reads_cgroup_v2_and_v1(tmp_path: Path) -> None:
    v2 = tmp_path / "memory.events"
    v2.write_text(CGROUP_V2, encoding="ascii")
    v1 = tmp_path / "memory.oom_control"
    v1.write_text(CGROUP_V1, encoding="ascii")
    missing = str(tmp_path / "no-existe")

    assert worker.oom_kills((str(v2),)) == 1
    assert worker.oom_kills((missing, str(v1))) == 3
    assert worker.oom_kills((missing,)) is None


@pytest.mark.parametrize(
    ("exitcode", "before", "now", "code"),
    [
        (-9, 1, 2, "out_of_memory"),  # SIGKILL y el contador del cgroup sube: el OOM
        (-9, None, None, "out_of_memory"),  # sin cgroup legible, un SIGKILL ajeno casi siempre es el OOM
        (-9, 2, 2, "crashed"),  # SIGKILL de otro origen
        (1, 1, 2, "crashed"),  # una excepción no capturada no es falta de memoria
        (-11, None, None, "crashed"),  # segfault
    ],
)
def test_crash_reason(exitcode: int, before: int | None, now: int | None, code: str) -> None:
    status, reason, message = worker.crash_reason(exitcode, before, now)

    assert status == "failed" and reason == code
    if code == "out_of_memory":
        assert "DOW_WORKER_MEM_LIMIT" in message and "relanzarlo" in message


def test_resources_reads_the_container_memory(tmp_path: Path) -> None:
    from app.core.config import Settings

    (tmp_path / "max").write_text("6442450944\n", encoding="ascii")
    (tmp_path / "peak").write_text("6000000000\n", encoding="ascii")
    (tmp_path / "unlimited").write_text("max\n", encoding="ascii")
    (tmp_path / "v1").write_text(str(1 << 62), encoding="ascii")  # cgroup v1 sin límite
    memory = {
        "memory_limit_bytes": (str(tmp_path / "no-existe"), str(tmp_path / "max")),
        "memory_peak_bytes": (str(tmp_path / "peak"),),
        "memory_current_bytes": (str(tmp_path / "unlimited"),),
        "other": (str(tmp_path / "v1"),),
    }

    settings = Settings(
        environment="test", scan_recycle_documents=50, worker_concurrency=2, scan_io_retries=3, scan_reuse_hashes=False
    )
    found = worker.resources(settings, memory)

    assert found["memory_limit_bytes"] == 6442450944 and found["memory_peak_bytes"] == 6000000000
    assert found["memory_current_bytes"] is None and found["other"] is None
    assert found["scan_recycle_documents"] == 50
    # 1.1.0: huecos y ajustes del escaneo de este worker, para la ficha de workers.
    assert (found["slots"], found["scan_io_retries"], found["scan_reuse_hashes"]) == (2, 3, False)
    assert found["scan_document_timeout_seconds"] == 0
