"""API v1: auth, users, sessions y audit (Fase 1); engines y connections (Fase 2); projects y runs (Fase 3)…

Todo método no seguro bajo ``/api/v1`` exige token CSRF (``csrf_protect``).
"""

from fastapi import APIRouter, Depends

from app.api.deps import csrf_protect
from app.api.v1 import audit, auth, sessions, users

router = APIRouter(prefix="/v1", dependencies=[Depends(csrf_protect)])
router.include_router(auth.router)
router.include_router(users.router)
router.include_router(sessions.router)
router.include_router(audit.router)
