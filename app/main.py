from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api import duplicates, empty_directories, pages
from app.config import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    application = FastAPI(title="NAS Toolbox", version="0.1.0")
    application.state.settings = settings or Settings.from_environment()
    static_path = Path(__file__).parent / "static"
    application.mount("/static", StaticFiles(directory=static_path), name="static")
    application.include_router(pages.router)
    application.include_router(empty_directories.router)
    application.include_router(duplicates.router)

    @application.get("/health", tags=["system"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return application


app = create_app()
