"""AI-срез (Спринт/Прогноз) — генерация текстовой сводки по уже посчитанным данным."""

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import current_config
from app.db import models
from app.schemas.ai import AiSummaryResponse, ForecastSummaryRequest, SprintSummaryRequest
from app.services import ai_summary_service
from app.services.ai_summary_service import AiSummaryError

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/sprint-summary", response_model=AiSummaryResponse)
def sprint_summary(
    body: SprintSummaryRequest,
    config: models.Config = Depends(current_config),
):
    try:
        summary = ai_summary_service.generate_summary(config, "sprint", body.model_dump())
    except AiSummaryError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return AiSummaryResponse(summary=summary, generated_at=ai_summary_service.now_iso())


@router.post("/forecast-summary", response_model=AiSummaryResponse)
def forecast_summary(
    body: ForecastSummaryRequest,
    config: models.Config = Depends(current_config),
):
    try:
        summary = ai_summary_service.generate_summary(config, "forecast", body.model_dump())
    except AiSummaryError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return AiSummaryResponse(summary=summary, generated_at=ai_summary_service.now_iso())
