from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse


router = APIRouter()
frontend_file = Path(__file__).resolve().parents[1] / "frontend_dist" / "index.html"


@router.get("/", response_class=FileResponse, include_in_schema=False)
def home() -> FileResponse:
    return FileResponse(
        frontend_file,
        media_type="text/html",
        headers={"Cache-Control": "no-cache"},
    )
