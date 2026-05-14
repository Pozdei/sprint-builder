"""Эндпоинты экспорта в xlsx."""

from io import BytesIO
from urllib.parse import quote

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.schemas.export import CandidatesExportRequest, SprintExportRequest
from app.sprint.excel import build_candidates_xlsx, build_sprint_xlsx

router = APIRouter(tags=["export"])


def _xlsx_response(content: bytes, filename: str) -> StreamingResponse:
    """Завернуть байты в HTTP-ответ с правильными заголовками для скачивания.

    Имя файла кодируем по RFC 5987 — чтобы кириллица не ломалась.
    """
    encoded = quote(filename)
    return StreamingResponse(
        BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded}"},
    )


@router.post("/sprint/export")
def export_sprint(req: SprintExportRequest):
    content = build_sprint_xlsx(
        allocated=[t.model_dump() for t in req.allocated],
        owner_stats=[s.model_dump() for s in req.owner_stats],
        max_sprint_num=req.max_sprint_num,
        closed_tasks=[c.model_dump() if c else None for c in req.closed_tasks]
                      if req.closed_tasks is not None else None,
        terminal_statuses=req.terminal_statuses,
    )
    suffix = f"_{req.max_sprint_num}" if req.max_sprint_num else ""
    return _xlsx_response(content, f"sprint{suffix}.xlsx")


@router.post("/candidates/export")
def export_candidates(req: CandidatesExportRequest):
    content = build_candidates_xlsx(
        candidates=[t.model_dump() for t in req.candidates],
    )
    suffix = f"_{req.max_sprint_num}" if req.max_sprint_num else ""
    return _xlsx_response(content, f"candidates{suffix}.xlsx")
