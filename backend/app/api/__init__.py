"""Главный API-роутер: собирает все подроутеры по доменам.

Чтобы добавить новый домен — создать app/api/<domain>.py с APIRouter,
импортировать и подключить здесь.
"""

from fastapi import APIRouter

from app.api import configs, export, health, sprint, sprints

router = APIRouter()

router.include_router(health.router)
router.include_router(sprint.router)
router.include_router(sprints.router)
router.include_router(configs.router)
router.include_router(export.router)
