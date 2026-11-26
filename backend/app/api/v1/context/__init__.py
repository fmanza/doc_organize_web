"""Contexto y taxonomías (Fase 7): plantillas, contexto del proyecto, manifiesto y acceso al sitio aislado.

Construir (``context_build``) y borrar (``context_delete``) el contexto son runs: ``POST /projects/{id}/runs``. El
sitio se sirve fuera de ``/api`` (``/site/<token>/…``, ``app.api.site``).
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.context import documents, manifest, profile, quality, review, templates

router = APIRouter()
router.include_router(templates.router)
router.include_router(documents.router)
router.include_router(manifest.router)
router.include_router(profile.router)
router.include_router(review.router)
router.include_router(quality.router)
