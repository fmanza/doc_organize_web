"""Capa anticorrupción con doc_organize (ADR-006).

Es el **único** paquete de la aplicación que importa ``doc_organize`` (lo comprueba
``tests/unit/test_architecture.py``). El resto del backend depende de las funciones y tipos propios que se exponen
aquí, de modo que un cambio de API de la librería solo obliga a tocar esta capa. Los rodeos temporales de huecos de
la librería llevan su ``G<n>`` de ``docs/plan/DOC_ORGANIZE_GAPS.md``.
"""

from app.integrations.doc_organize.version import library_version

__all__ = ["library_version"]
