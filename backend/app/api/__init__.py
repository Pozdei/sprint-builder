"""Главный API-роутер.

Открытые: /health, /auth.
Защищённые JWT: /sprint, /sprints, /configs, /export, /admin, /jira.
"""

from fastapi import APIRouter, Depends

from app.api import admin, auth, configs, epic, export, health, jira, sprint, sprints
from app.api.deps import get_current_user

router = APIRouter()

router.include_router(health.router)
router.include_router(auth.router)

_protected = [Depends(get_current_user)]
router.include_router(sprint.router, dependencies=_protected)
router.include_router(sprints.router, dependencies=_protected)
router.include_router(configs.router, dependencies=_protected)
router.include_router(export.router, dependencies=_protected)
router.include_router(admin.router, dependencies=_protected)
router.include_router(jira.router, dependencies=_protected)
router.include_router(epic.router, dependencies=_protected)
