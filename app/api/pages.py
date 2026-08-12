from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates


router = APIRouter()
app_path = Path(__file__).resolve().parents[1]
templates = Jinja2Templates(directory=app_path / "templates")
static_path = app_path / "static"
templates.env.globals.update(
    app_css=(static_path / "style.css").read_text(encoding="utf-8"),
    common_js=(static_path / "common.js").read_text(encoding="utf-8"),
    empty_directories_js=(static_path / "empty-directories.js").read_text(
        encoding="utf-8"
    ),
    duplicates_js=(static_path / "duplicates.js").read_text(encoding="utf-8"),
)


@router.get("/", response_class=HTMLResponse)
def home(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request=request, name="index.html")


@router.get("/tools/empty-directories", response_class=HTMLResponse)
def empty_directories_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request=request, name="empty_directories.html")


@router.get("/tools/duplicates", response_class=HTMLResponse)
def duplicates_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request=request, name="duplicates.html")
