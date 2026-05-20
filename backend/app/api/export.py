"""Эндпоинты для xlsx-выгрузки."""

import urllib.parse

from fastapi import APIRouter
from fastapi.responses import Response

from app.schemas.export import CandidatesExportRequest, SprintExportRequest
from app.sprint.excel import build_candidates_xlsx, build_sprint_xlsx

router = APIRouter(tags=["export"])


def _xlsx_response(content: bytes, filename: str) -> Response:
    encoded = urllib.parse.quote(filename)
    headers = {
        "Content-Disposition": f"attachment; filename*=UTF-8''{encoded}",
    }
    return Response(
        content=content,
        media_type=("application/vnd.openxmlformats-officedocument."
                    "spreadsheetml.sheet"),
        headers=headers,
    )


@router.post("/sprint/export")
def export_sprint(req: SprintExportRequest):
    content = build_sprint_xlsx(
        allocated=[t.model_dump() for t in req.allocated],
        owner_stats=[s.model_dump() for s in req.owner_stats],
        max_sprint_num=req.max_sprint_num,
        closed_tasks=([c.model_dump() if c else None for c in req.closed_tasks]
                       if req.closed_tasks is not None else None),
        terminal_statuses=req.terminal_statuses,
        intrusions=([i.model_dump() for i in req.intrusions]
                     if req.intrusions else None),
    )
    suffix = f"_{req.max_sprint_num}" if req.max_sprint_num else ""
    return _xlsx_response(content, f"sprint{suffix}.xlsx")


@router.post("/candidates/export")
def export_candidates(req: CandidatesExportRequest):
    content = build_candidates_xlsx(
        candidates=[t.model_dump() for t in req.candidates],
        allocated_set=set(req.allocated_set) if req.allocated_set is not None else None,
    )
    suffix = f"_{req.max_sprint_num}" if req.max_sprint_num else ""
    return _xlsx_response(content, f"candidates{suffix}.xlsx")
