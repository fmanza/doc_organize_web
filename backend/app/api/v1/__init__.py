"""API v1: auth, users, sessions y audit (Fase 1); locations, fs, admin e instance (Fase 2); projects y runs (Fase 3).

Todo método no seguro bajo ``/api/v1`` exige token CSRF (``csrf_protect``).
"""

from fastapi import APIRouter, Depends

from app.api.deps import csrf_protect
from app.api.v1 import admin, audit, auth, fs, instance, locations, projects, runs, sessions, users

router = APIRouter(prefix="/v1", dependencies=[Depends(csrf_protect)])
router.include_router(auth.router)
router.include_router(users.router)
router.include_router(sessions.router)
router.include_router(audit.router)
router.include_router(locations.router)
router.include_router(fs.router)
router.include_router(admin.router)
router.include_router(instance.router)
router.include_router(projects.router)
router.include_router(runs.router)
