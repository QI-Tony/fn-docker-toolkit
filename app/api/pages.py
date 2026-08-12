from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates


router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).resolve().parents[1] / "templates")


@router.get("/", response_class=HTMLResponse)
def home(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request=request, name="index.html")


@router.get("/tools/empty-directories", response_class=HTMLResponse)
def empty_directories_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request=request, name="empty_directories.html")


@router.get("/tools/duplicates", response_class=HTMLResponse)
def duplicates_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request=request, name="duplicates.html")
