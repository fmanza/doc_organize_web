"""Fixtures compartidas de los jobs: el proyecto con conversiones sintéticas y el lanzador de runs de
``test_context_operation`` también las usa la IA (``test_ai_operation``, Fase 8)."""

from tests.jobs.test_context_operation import project, run  # noqa: F401 - se registran como fixtures

__all__ = ["project", "run"]
